import os
import sys
import re
import time
import django
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard, JobLead, CandidateCV
from utilities.seed_utils import get_blacklist

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
JOB_LINK_KEYWORDS = ["/job", "/post", "/detail", "/vacancy", "/careers", "/opening"]
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


def normalize_url(base_url, href):
    if href.startswith('http'):
        return href
    return f"{base_url.rstrip('/')}/{href.lstrip('/')}"


def process_job_url(url, board, role, blacklist):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = extract_emails_from_html(response.text, blacklist)
        if not emails:
            return

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
            else:
                print(f"        [-] Duplicate: {email}")
    except requests.exceptions.Timeout:
        print(f"        [!] Timeout: {url}")
    except Exception as e:
        print(f"        [!] Error: {e}")


def find_job_links(board_url):
    job_links = []
    try:
        response = requests.get(board_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for anchor in soup.find_all('a', href=True):
            full_url = normalize_url(board_url, anchor['href'])
            if any(kw in full_url.lower() for kw in JOB_LINK_KEYWORDS):
                job_links.append(full_url)
    except Exception as e:
        print(f"      [!] Could not fetch board: {e}")

    seen = set()
    unique = []
    for link in job_links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    return unique


def scrape_emails():
    print("\n--- STARTING EMAIL EXTRACTION ---")
    blacklist = get_blacklist()
    print(f"  [*] Loaded {len(blacklist)} blacklisted domains")

    cvs = CandidateCV.objects.all()
    if not cvs.exists():
        print("  [-] No CVs found. Run seed_database.py first.")
        return

    roles = [cv.target_role for cv in cvs]
    print(f"  [*] Target roles: {roles}")

    boards = JobBoard.objects.filter(is_active=True)
    if not boards.exists():
        print("  [-] No active job boards.")
        return

    print(f"  [*] Scanning {boards.count()} active boards")
    total_new = 0

    for board in boards:
        print(f"\n  Board: {board.name} ({board.url})")
        job_links = find_job_links(board.url)
        if not job_links:
            print("    [-] No job links found.")
            continue
        print(f"    [*] Found {len(job_links)} candidate job links")

        for role in roles:
            print(f"    Role: {role}")
            for url in job_links[:MAX_LINKS_PER_ROLE]:
                print(f"      Checking: {url[:90]}")
                before = JobLead.objects.count()
                process_job_url(url, board, role, blacklist)
                total_new += (JobLead.objects.count() - before)
                time.sleep(1)

    print(f"\n  [*] Extraction complete. {total_new} new leads saved.")


if __name__ == "__main__":
    print("Initializing Email Extraction Engine...")
    scrape_emails()
    print("\nEmail extraction run complete.")