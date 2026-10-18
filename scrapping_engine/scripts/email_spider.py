import os
import sys
import re
import time
import django
import requests
import smtplib
from datetime import datetime
from email.message import EmailMessage
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard, JobLead, CandidateCV
from utilities.seed_utils import get_blacklist

# Stricter regex: requires valid TLD of 2+ letters, no double dots in domain
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'

JOB_LINK_KEYWORDS = [
    "/job", "/post", "/detail", "/vacancy", "/careers", "/opening",
    "/position", "/listing", "?job=", "?vacancy=", "?career="
]

# Placeholder local parts (before @) that are clearly junk
PLACEHOLDER_LOCAL_PARTS = {
    "your", "youremail", "yourname", "your.name", "your.email", "your-email",
    "name", "email", "username", "user", "test", "example", "sample", "demo",
    "firstname", "lastname", "first.last", "john.doe", "johndoe",
}

# Placeholder domains (after @)
PLACEHOLDER_DOMAINS = {
    "domain.com", "yourdomain.com", "email.com", "youremail.com",
    "example.com", "example.org", "test.com", "sample.com", "demo.com",
    "mydomain.com", "yourname.com", "mydomain.co.zw", "yourdomain.co.zw",
    "domain.co.zw", "email.co.zw", "sentry.io", "wixpress.com",
}

# CSS/JS noise words that appear as "local parts" in font URLs
CSS_NOISE_LOCALS = {"wght", "font", "url", "data", "import", "var", "static", "media"}

# Noreply and admin prefixes we don't want to email
REJECT_LOCAL_PREFIXES = (
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "postmaster", "mailer-daemon", "webmaster", "bounce",
    "admin", "administrator", "info", "support", "help",
)

# Valid TLDs (add more if you start scraping other countries)
VALID_TLDS = (
    ".com", ".org", ".net", ".edu", ".gov", ".mil", ".biz", ".info",
    ".co.zw", ".org.zw", ".ac.zw", ".zw",
    ".co.uk", ".org.uk", ".ac.uk", ".uk",
    ".co.za", ".org.za", ".za",
    ".io", ".ai", ".me", ".tech", ".dev",
    ".us", ".ca", ".au", ".de", ".fr", ".in",
    ".ke", ".ng", ".gh", ".tz", ".ug", ".zm", ".bw", ".mz",
)

MAX_LINKS_PER_ROLE = 4
MAX_EMAILS_PER_JOB = 4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_valid_email(email, blacklist):
    """Strict validation — rejects CSS noise, placeholders, admin, invalid TLDs."""
    email = email.lower().strip().rstrip('.,;:')
    
    if not email or '@' not in email:
        return False
    
    # Must match regex
    if not re.fullmatch(EMAIL_REGEX, email):
        return False
    
    local, _, domain = email.partition('@')
    
    if not local or not domain:
        return False
    
    # Reject CSS/JS noise (e.g., wght@300..700)
    if local in CSS_NOISE_LOCALS:
        return False
    
    # Reject double dots, leading/trailing dots
    if '..' in domain or domain.startswith('.') or domain.endswith('.'):
        return False
    if '..' in local or local.startswith('.') or local.endswith('.'):
        return False
    
    # Reject placeholders
    if local in PLACEHOLDER_LOCAL_PARTS:
        return False
    if domain in PLACEHOLDER_DOMAINS:
        return False
    
    # Reject noreply/admin/bounce
    if any(local.startswith(p) for p in REJECT_LOCAL_PREFIXES):
        return False
    
    # Reject invalid TLD
    if not any(domain.endswith(tld) for tld in VALID_TLDS):
        return False
    
    # Reject blacklisted domains (from seed/blacklist.json)
    if any(bl in domain for bl in blacklist):
        return False
    
    return True


def extract_emails_from_html(html_text, blacklist):
    """Extracts and validates emails, stripping style/script tags first."""
    # Parse and remove style/script/noscript BEFORE extracting
    soup = BeautifulSoup(html_text, 'html.parser')
    for tag in soup(['style', 'script', 'noscript']):
        tag.decompose()
    
    clean_text = soup.get_text(separator=' ')
    
    raw_emails = re.findall(EMAIL_REGEX, clean_text)
    clean = set()
    for email in raw_emails:
        if is_valid_email(email, blacklist):
            clean.add(email.lower().strip())
    return list(clean)


def extract_job_title(soup):
    title_tag = soup.find('h1') or soup.find('h2')
    return title_tag.get_text(strip=True)[:255] if title_tag else "N/A"


# Titles that indicate a sales/service page, not a real job
JUNK_TITLE_KEYWORDS = (
    "job posting package", "post a job", "pricing", "advertise",
    "recruitment services", "cv writing", "cv design", "hire talent",
    "post your cv", "register", "sign up", "login", "contact us",
)


def is_junk_page(job_title, url):
    title_lower = job_title.lower()
    if any(kw in title_lower for kw in JUNK_TITLE_KEYWORDS):
        return True
    url_lower = url.lower()
    if any(kw in url_lower for kw in ['/pricing', '/services', '/post-a-job', '/advertise', '/register']):
        return True
    return False


def process_job_url(url, board, role, blacklist):
    """Visits a job URL, extracts emails, saves leads. Returns count of new leads."""
    added = 0
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get title first to check for junk
        job_title = extract_job_title(soup)
        if is_junk_page(job_title, url):
            print(f"        [-] Skipped junk page: {job_title[:60]}")
            return 0
        
        emails = extract_emails_from_html(response.text, blacklist)
        if not emails:
            return 0
        
        for email in emails[:MAX_EMAILS_PER_JOB]:
            # GLOBAL dedup: skip if this email already exists anywhere
            if JobLead.objects.filter(email_link=email).exists():
                print(f"        [-] Duplicate email: {email}")
                continue
            
            # Also check the pending list for this session
            lead, created = JobLead.objects.get_or_create(
                email_link=email,
                defaults={
                    'job_url': url,
                    'job_board': board,
                    'cv_career': role,
                    'job_title': job_title,
                    'country': "Zimbabwe",
                    'job_type': "Remote/Full-time",
                }
            )
            if created:
                print(f"        [+] Saved: {email} | {job_title[:40]}")
                added += 1
            else:
                print(f"        [-] Duplicate: {email}")
    except requests.exceptions.Timeout:
        print(f"        [!] Timeout: {url}")
    except Exception as e:
        print(f"        [!] Error: {e}")
    return added


def find_job_links(board_url):
    job_links = []
    try:
        response = requests.get(board_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].strip()
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            full_url = urljoin(board_url, href)
            if any(kw in full_url.lower() for kw in JOB_LINK_KEYWORDS):
                job_links.append(full_url)
    except Exception as e:
        print(f"      [!] Could not fetch board: {e}")
        return []
    
    seen = set()
    unique = []
    for link in job_links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    return unique


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(total_new, boards_scanned, roles_searched, error_log):
    print("\n--- GENERATING EMAIL REPORT ---")
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')
    
    if not (sender and password and receiver):
        print("  [!] Missing email secrets. Skipping email.")
        return
    
    subject = f"Email Spider Report: {total_new} New Leads - {datetime.now().strftime('%Y-%m-%d')}"
    body = (
        "Email Spider Run Summary\n"
        "---------------------------------------------\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Active boards scanned: {boards_scanned}\n"
        f"Roles searched: {', '.join(roles_searched) if roles_searched else 'None'}\n"
        f"New leads saved to DB: {total_new}\n\n"
    )
    if error_log:
        body += f"Issues encountered:\n{error_log}\n\n"
    body += "This is an automated report."
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("  [+] Email sent successfully!")
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")


def scrape_emails():
    print("\n--- STARTING EMAIL EXTRACTION ---")
    blacklist = get_blacklist()
    print(f"  [*] Loaded {len(blacklist)} blacklisted domains")
    
    cvs = CandidateCV.objects.all()
    if not cvs.exists():
        print("  [-] No CVs found.")
        send_summary_email(0, 0, [], "No CVs found")
        return
    
    roles = [cv.target_role for cv in cvs]
    print(f"  [*] Target roles: {roles}")
    
    boards = JobBoard.objects.filter(is_active=True)
    if not boards.exists():
        print("  [-] No active job boards.")
        send_summary_email(0, 0, roles, "No active boards")
        return
    
    print(f"  [*] Scanning {boards.count()} active boards")
    total_new = 0
    error_log = []
    
    for board in boards:
        print(f"\n  Board: {board.name}")
        job_links = find_job_links(board.url)
        if not job_links:
            print("    [-] No job links found.")
            error_log.append(f"No job links on {board.name}")
            continue
        
        print(f"    [*] Found {len(job_links)} candidate job links")
        for role in roles:
            print(f"    Role: {role}")
            for url in job_links[:MAX_LINKS_PER_ROLE]:
                print(f"      Checking: {url[:90]}")
                added = process_job_url(url, board, role, blacklist)
                total_new += added
                time.sleep(1)
    
    print(f"\n  [*] Extraction complete. {total_new} new leads saved.")
    error_str = "\n".join(error_log) if error_log else None
    send_summary_email(total_new, boards.count(), roles, error_str)


if __name__ == "__main__":
    print("Initializing Email Extraction Engine...")
    scrape_emails()
    print("\nEmail extraction run complete.")