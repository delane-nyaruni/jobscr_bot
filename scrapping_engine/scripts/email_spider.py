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

# Project root is three levels up: scripts/ -> scrapping_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard, JobLead, CandidateCV
from utilities.seed_utils import get_blacklist

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

# Expanded keywords to catch more job links
JOB_LINK_KEYWORDS = [
    "/job","/web developer", "/ict","/software","/post", "/detail", "/vacancy", "/careers", "/opening", 
    "/position", "/listing", "?job=", "?vacancy=", "?career="
]

MAX_LINKS_PER_ROLE = 4
MAX_EMAILS_PER_JOB = 4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def extract_emails_from_html(html_text, blacklist):
    raw_emails = re.findall(EMAIL_REGEX, html_text)
    clean = set()
    for email in raw_emails:
        email_lower = email.lower().strip('.')
        if any(domain in email_lower for domain in blacklist):
            continue
        clean.add(email_lower)
    return list(clean)


def extract_job_title(soup):
    title_tag = soup.find('h1') or soup.find('h2')
    return title_tag.get_text(strip=True)[:255] if title_tag else "N/A"


def process_job_url(url, board, role, blacklist):
    """Visits a job URL and returns the count of new leads added."""
    added = 0
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = extract_emails_from_html(response.text, blacklist)
        if not emails:
            return 0

        job_title = extract_job_title(soup)
        for email in emails[:MAX_EMAILS_PER_JOB]:
            lead, created = JobLead.objects.get_or_create(
                job_url=url,
                email_link=email,
                defaults={
                    'job_board': board,
                    'cv_career': role,
                    'job_title': job_title,
                    'country': board.country,
                    'job_type': "Remote/Full-time",
                }
            )
            if created:
                print(f"        [+] Saved: {email} for '{role}'")
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
            
            # Skip junk links
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
                
            # Properly join relative URLs with the base URL
            full_url = urljoin(board_url, href)
            
            # Check if the URL contains any job keyword
            if any(kw in full_url.lower() for kw in JOB_LINK_KEYWORDS):
                job_links.append(full_url)
                
    except Exception as e:
        print(f"      [!] Could not fetch board: {e}")
        return []

    # Deduplicate
    seen = set()
    unique = []
    for link in job_links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
            
    return unique


def _get_env(*names):
    """Returns the first non-empty environment variable from a list."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(total_new, boards_scanned, roles_searched, error_log):
    """Sends a summary email after every run."""
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

    if total_new > 0:
        body += "These leads are now saved in the database and marked as UNREPORTED.\n"
        body += "The mailing_engine will pick them up and send you the CSV during its next scheduled run.\n\n"
    else:
        body += "No new leads were found in this run.\n\n"

    body += "This is an automated report."

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)

    try:
        print("  [*] Connecting to SMTP server...")
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
        print("  [-] No CVs found. Run seed_database.py first.")
        send_summary_email(0, 0, [], "No CVs found in the database")
        return

    roles = [cv.target_role for cv in cvs]
    print(f"  [*] Target roles: {roles}")

    boards = JobBoard.objects.filter(is_active=True)
    if not boards.exists():
        print("  [-] No active job boards.")
        send_summary_email(0, 0, roles, "No active job boards in the database")
        return

    print(f"  [*] Scanning {boards.count()} active boards")
    
    total_new = 0
    error_log = []

    for board in boards:
        print(f"\n  Board: {board.name} ({board.url})")
        job_links = find_job_links(board.url)
        
        if not job_links:
            print("    [-] No job links found.")
            error_log.append(f"Could not find job links on {board.name}")
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

    # Send email report after DB operations are done
    error_str = "\n".join(error_log) if error_log else None
    send_summary_email(total_new, boards.count(), roles, error_str)


if __name__ == "__main__":
    print("Initializing Email Extraction Engine...")
    scrape_emails()
    print("\n Email extraction run complete.")