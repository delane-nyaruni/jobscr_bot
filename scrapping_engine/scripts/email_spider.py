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
from urllib.parse import urljoin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard, JobLead, CandidateCV
from utilities.seed_utils import get_blacklist

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'

JOB_LINK_KEYWORDS = [
    "/job", "/post", "/detail", "/vacancy", "/careers", "/opening",
    "/position", "/listing", "?job=", "?vacancy=", "?career="
]

PLACEHOLDER_LOCAL_PARTS = {
    "your", "youremail", "yourname", "your.name", "your.email", "your-email",
    "name", "email", "username", "user", "test", "example", "sample", "demo",
    "firstname", "lastname", "first.last", "john.doe", "johndoe",
}

PLACEHOLDER_DOMAINS = {
    "domain.com", "yourdomain.com", "email.com", "youremail.com",
    "example.com", "example.org", "test.com", "sample.com", "demo.com",
    "mydomain.com", "yourname.com", "mydomain.co.zw", "yourdomain.co.zw",
    "domain.co.zw", "email.co.zw", "sentry.io", "wixpress.com",
}

CSS_NOISE_LOCALS = {"wght", "font", "url", "data", "import", "var", "static", "media"}

REJECT_LOCAL_PREFIXES = (
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "postmaster", "mailer-daemon", "webmaster", "bounce",
    "admin", "administrator", "info", "support", "help",
)

VALID_TLDS = (
    ".com", ".org", ".net", ".edu", ".gov", ".mil", ".biz", ".info",
    ".co.zw", ".org.zw", ".ac.zw", ".zw",
    ".co.uk", ".org.uk", ".ac.uk", ".uk",
    ".co.za", ".org.za", ".za",
    ".io", ".ai", ".me", ".tech", ".dev",
    ".us", ".ca", ".au", ".de", ".fr", ".in",
    ".ke", ".ng", ".gh", ".tz", ".ug", ".zm", ".bw", ".mz",
)

JUNK_TITLE_KEYWORDS = (
    "job posting package", "post a job", "pricing", "advertise",
    "recruitment services", "cv writing", "cv design", "hire talent",
    "post your cv", "register", "sign up", "login", "contact us",
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
    email = email.lower().strip().rstrip('.,;:')
    if not email or '@' not in email:
        return False
    if not re.fullmatch(EMAIL_REGEX, email):
        return False
    local, _, domain = email.partition('@')
    if not local or not domain:
        return False
    if local in CSS_NOISE_LOCALS:
        return False
    if '..' in domain or domain.startswith('.') or domain.endswith('.'):
        return False
    if '..' in local or local.startswith('.') or local.endswith('.'):
        return False
    if local in PLACEHOLDER_LOCAL_PARTS:
        return False
    if domain in PLACEHOLDER_DOMAINS:
        return False
    if any(local.startswith(p) for p in REJECT_LOCAL_PREFIXES):
        return False
    if not any(domain.endswith(tld) for tld in VALID_TLDS):
        return False
    if any(bl in domain for bl in blacklist):
        return False
    return True


def extract_emails_from_html(html_text, blacklist):
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


def is_junk_page(job_title, url):
    if any(kw in job_title.lower() for kw in JUNK_TITLE_KEYWORDS):
        return True
    if any(kw in url.lower() for kw in ['/pricing', '/services', '/post-a-job', '/advertise', '/register']):
        return True
    return False


def process_job_url(url, board, role, blacklist):
    """Returns (added, duplicates, junk_skipped)."""
    added = 0
    duplicates = 0
    junk = 0
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        job_title = extract_job_title(soup)

        if is_junk_page(job_title, url):
            print(f"        [-] Skipped junk page: {job_title[:60]}")
            return (0, 0, 1)

        emails = extract_emails_from_html(response.text, blacklist)
        if not emails:
            return (0, 0, 0)

        for email in emails[:MAX_EMAILS_PER_JOB]:
            if JobLead.objects.filter(email_link=email).exists():
                print(f"        [-] Duplicate email: {email}")
                duplicates += 1
                continue

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
                duplicates += 1
    except requests.exceptions.Timeout:
        print(f"        [!] Timeout: {url}")
    except Exception as e:
        print(f"        [!] Error: {e}")
    return (added, duplicates, junk)


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


def send_summary_email(status, stats, roles, board_details, start_time):
    print("\n--- GENERATING EMAIL REPORT ---")

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    missing = []
    if not sender:
        missing.append("EMAIL_SENDER or EMAIL_USER")
    if not password:
        missing.append("EMAIL_PASSWORD")
    if not receiver:
        missing.append("EMAIL_RECEIVER or RECEIVER_EMAIL")

    if missing:
        print(f"  [!] Missing secrets: {', '.join(missing)}. Skipping email.")
        return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Database snapshot
    total_cvs = CandidateCV.objects.count()
    total_boards = JobBoard.objects.count()
    active_boards = JobBoard.objects.filter(is_active=True).count()
    total_leads = JobLead.objects.count()
    unreported = JobLead.objects.filter(is_reported=False).count()
    applied = JobLead.objects.filter(applied=True).count()
    pending = JobLead.objects.filter(is_reported=True, applied=False).count()

    subject = (
        f"Email Spider [{status}]: {stats['leads_saved']} New Leads - "
        f"{end_time.strftime('%Y-%m-%d')}"
    )

    body = (
        "Email Spider Run Report\n"
        "=================================================================\n"
        f"Status:              {status}\n"
        f"Started:             {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:            {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:            {duration:.1f} seconds\n"
        "\n"
        "Database Snapshot\n"
        "---------------------------------------------\n"
        f"Candidate CVs:           {total_cvs}\n"
        f"Target roles:            {', '.join(roles) if roles else 'None'}\n"
        f"Total boards in DB:      {total_boards}\n"
        f"Active boards:           {active_boards}\n"
        f"Total leads in DB:       {total_leads}\n"
        f"Unreported leads:        {unreported}\n"
        f"Awaiting application:    {pending}\n"
        f"Already applied:         {applied}\n"
        "\n"
        "Extraction Statistics\n"
        "---------------------------------------------\n"
        f"Boards scanned:          {stats['boards_scanned']}/{active_boards}\n"
        f"Boards with no links:    {stats['boards_no_links']}\n"
        f"Total job links found:   {stats['job_links']}\n"
        f"Job pages visited:       {stats['pages_visited']}\n"
        f"Junk pages skipped:      {stats['junk']}\n"
        f"Duplicate emails skipped:{stats['duplicates']}\n"
        f"NEW LEADS SAVED:         {stats['leads_saved']}\n"
        f"Errors:                  {len(stats['errors'])}\n"
        "\n"
        "Details by Board\n"
        "---------------------------------------------\n"
    )

    if board_details:
        for b in board_details:
            if b['links'] == 0:
                body += f"- {b['name']:<22} no job links found\n"
            else:
                body += (
                    f"- {b['name']:<22} {b['links']} links, "
                    f"{b['leads']} new lead(s), "
                    f"{b['dupes']} duplicate(s)\n"
                )
    else:
        body += "(no boards processed)\n"

    if stats['errors']:
        body += "\nErrors Encountered\n"
        body += "---------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['leads_saved'] > 0:
        body += (
            "\nThese leads are now saved in the database and marked UNREPORTED.\n"
            "The mailing_engine will pick them up during its next scheduled run.\n"
        )

    body += "\nThis is an automated report from Jobscr Behemoth Email Crawler."

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
    start_time = datetime.now()
    print("\n--- STARTING EMAIL EXTRACTION ---")
    print(f"  [*] Run started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    stats = {
        "boards_scanned": 0,
        "boards_no_links": 0,
        "job_links": 0,
        "pages_visited": 0,
        "junk": 0,
        "duplicates": 0,
        "leads_saved": 0,
        "errors": [],
    }
    board_details = []

    blacklist = get_blacklist()
    print(f"  [*] Loaded {len(blacklist)} blacklisted domains")

    cvs = CandidateCV.objects.all()
    if not cvs.exists():
        print("  [-] No CVs found.")
        send_summary_email("NO CVs", stats, [], [], start_time)
        return

    # This now successfully pulls the auto-parsed 'target_role' from your new UI uploads
    roles = [cv.target_role for cv in cvs]
    print(f"  [*] Target roles: {roles}")

    boards = JobBoard.objects.filter(is_active=True)
    if not boards.exists():
        print("  [-] No active job boards.")
        send_summary_email("NO BOARDS", stats, roles, [], start_time)
        return

    print(f"  [*] Scanning {boards.count()} active boards")

    for board in boards:
        print(f"\n  Board: {board.name}")
        stats['boards_scanned'] += 1

        job_links = find_job_links(board.url)
        stats['job_links'] += len(job_links)

        if not job_links:
            print("    [-] No job links found.")
            stats['boards_no_links'] += 1
            stats['errors'].append(f"No job links on {board.name}")
            board_details.append({
                "name": board.name, "links": 0, "leads": 0, "dupes": 0,
            })
            continue

        print(f"    [*] Found {len(job_links)} candidate job links")
        board_leads = 0
        board_dupes = 0

        for role in roles:
            print(f"    Role: {role}")
            for url in job_links[:MAX_LINKS_PER_ROLE]:
                print(f"      Checking: {url[:90]}")
                added, dupes, junk = process_job_url(url, board, role, blacklist)
                stats['pages_visited'] += 1
                stats['leads_saved'] += added
                stats['duplicates'] += dupes
                stats['junk'] += junk
                board_leads += added
                board_dupes += dupes
                time.sleep(1)

        board_details.append({
            "name": board.name,
            "links": len(job_links),
            "leads": board_leads,
            "dupes": board_dupes,
        })

    print(f"\n  [*] Extraction complete. {stats['leads_saved']} new leads saved.")

    if not stats['errors']:
        status = "SUCCESS"
    elif stats['leads_saved'] > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"

    send_summary_email(status, stats, roles, board_details, start_time)


if __name__ == "__main__":
    print("Initializing Email Extraction Engine...")
    scrape_emails()
    print("\nEmail extraction run complete.")