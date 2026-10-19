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
from utilities.seed_utils import get_blacklist, load_json
from utilities.geo_utils import generate_global_map

JOB_LINK_KEYWORDS = load_json('job_link_keywords.json')
JUNK_TITLE_KEYWORDS = load_json('junk_title_keywords.json')

PLACEHOLDER_LOCAL_PARTS = set(load_json('placeholder_local_parts.json'))
PLACEHOLDER_DOMAINS = set(load_json('placeholder_domains.json'))
CSS_NOISE_LOCALS = set(load_json('css_noise_locals.json'))
REJECT_LOCAL_PREFIXES = tuple(load_json('reject_local_prefixes.json'))
VALID_TLDS = tuple(load_json('valid_tlds.json'))

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'

# TUNED PARAMETERS
BATCH_SIZE = 25
MAX_LINKS_PER_ROLE = 4
MAX_EMAILS_PER_JOB = 4
REQUEST_TIMEOUT = 8
SLEEP_TIME = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def is_valid_email(email, blacklist):
    email = email.lower().strip().rstrip('.,;:')
    if not email or '@' not in email: return False
    if not re.fullmatch(EMAIL_REGEX, email): return False
    local, _, domain = email.partition('@')
    if not local or not domain: return False
    if local in CSS_NOISE_LOCALS: return False
    if '..' in domain or domain.startswith('.') or domain.endswith('.'): return False
    if '..' in local or local.startswith('.') or local.endswith('.'): return False
    if local in PLACEHOLDER_LOCAL_PARTS: return False
    if domain in PLACEHOLDER_DOMAINS: return False
    if any(local.startswith(p) for p in REJECT_LOCAL_PREFIXES): return False
    if not any(domain.endswith(tld) for tld in VALID_TLDS): return False
    if any(bl in domain for bl in blacklist): return False
    return True


def extract_emails_from_html(html_text, blacklist):
    soup = BeautifulSoup(html_text, 'html.parser')
    for tag in soup(['style', 'script', 'noscript']): tag.decompose()
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
    if any(kw in job_title.lower() for kw in JUNK_TITLE_KEYWORDS): return True
    if any(kw in url.lower() for kw in ['/pricing', '/services', '/post-a-job', '/advertise', '/register']): return True
    return False


def process_job_url(url, board, role, blacklist):
    added = 0
    duplicates = 0
    junk = 0
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(response.text, 'html.parser')
        job_title = extract_job_title(soup)

        if is_junk_page(job_title, url):
            return (0, 0, 1)

        emails = extract_emails_from_html(response.text, blacklist)
        if not emails: return (0, 0, 0)

        for email in emails[:MAX_EMAILS_PER_JOB]:
            if JobLead.objects.filter(email_link=email).exists():
                duplicates += 1
                continue

            lead, created = JobLead.objects.get_or_create(
                email_link=email,
                defaults={
                    'job_url': url, 'job_board': board, 'cv_career': role,
                    'job_title': job_title, 'country': board.country, 'job_type': "Remote/Full-time"
                }
            )
            if created: added += 1
            else: duplicates += 1
    except Exception:
        pass
    return (added, duplicates, junk)


def find_job_links(board_url):
    job_links = []
    try:
        response = requests.get(board_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(response.text, 'html.parser')
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].strip()
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')): continue
            full_url = urljoin(board_url, href)
            if any(kw in full_url.lower() for kw in JOB_LINK_KEYWORDS):
                job_links.append(full_url)
    except Exception:
        return []
    return list(dict.fromkeys(job_links))


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value: return value
    return None


def send_summary_email(status, stats, roles, board_details, start_time):
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver): return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    total_cvs = CandidateCV.objects.count()
    total_boards = JobBoard.objects.count()
    active_boards = JobBoard.objects.filter(is_active=True).count()
    total_leads = JobLead.objects.count()
    unreported = JobLead.objects.filter(is_reported=False).count()
    applied = JobLead.objects.filter(applied=True).count()
    pending = JobLead.objects.filter(is_reported=True, applied=False).count()

    subject = f"Email Spider [{status}]: {stats['leads_saved']} New Leads - {end_time.strftime('%Y-%m-%d')}"

    map_text = generate_global_map(html=False)
    map_html = generate_global_map(html=True)

    body = (
        "Email Spider Run Report\n"
        "=================================================================\n"
        f"Status:                  {status}\n"
        f"Started:                 {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:                {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:                {duration:.1f} seconds\n"
        "\n\n"
        "Database Snapshot\n"
        "-----------------------------------------------------------------\n"
        f"Candidate CVs:           {total_cvs}\n"
        f"Target Roles:            {', '.join(roles) if roles else 'None'}\n"
        f"Total Boards in Database:{total_boards}\n"
        f"Active Boards:           {active_boards}\n"
        f"Total Leads in Database: {total_leads}\n"
        f"Unreported Leads:        {unreported}\n"
        f"Awaiting Application:    {pending}\n"
        f"Already Applied:         {applied}\n"
        "\n\n"
        "Extraction Statistics\n"
        "-----------------------------------------------------------------\n"
        f"Boards Scanned:          {stats['boards_scanned']}/{active_boards}\n"
        f"Boards With No Links:    {stats['boards_no_links']}\n"
        f"Total Job Links Found:   {stats['job_links']}\n"
        f"Job Pages Visited:       {stats['pages_visited']}\n"
        f"Junk Pages Skipped:      {stats['junk']}\n"
        f"Duplicate Emails Skipped:{stats['duplicates']}\n"
        f"New Leads Saved:         {stats['leads_saved']}\n"
        f"Errors:                  {len(stats['errors'])}\n"
        "\n\n"
    )

    # Insert Map before Details
    body += map_text
    body += f"\nDetails by Board [{stats['boards_scanned']}] \n"
    body += "-----------------------------------------------------------------\n"

    for b in board_details:
        if b['links'] == 0:
            body += f"- {b['name']:<22} no job links found\n"
        else:
            body += f"- {b['name']:<22} {b['links']} Link(s), {b['leads']} Lead(s), {b['dupes']} Duplicate(s)\n"

    if stats['errors']:
        body += f"\nErrors Encountered [{len(stats['errors'])}] \n-----------------------------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['leads_saved'] > 0:
        body += "\nThese leads are now saved in the database and marked UNREPORTED.\n"

    body += "\nThis is an automated report from Jobscr Behemoth Email Crawler.\n\n\n\nPowered by ninesoftstudio."
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    
    # Set plain text fallback
    msg.set_content(body)
    
    # Create HTML version by swapping the map text with the colored HTML map
    html_body = body.replace(map_text, map_html)
    # Use pre-wrap to maintain the ASCII formatting
    msg.add_alternative(f"<div style='font-family: monospace; white-space: pre-wrap;'>{html_body}</div>", subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    except Exception:
        pass


def scrape_emails():
    start_time = datetime.now()
    stats = {"boards_scanned": 0, "boards_no_links": 0, "job_links": 0, "pages_visited": 0, "junk": 0, "duplicates": 0, "leads_saved": 0, "errors": []}
    board_details = []

    blacklist = get_blacklist()
    cvs = CandidateCV.objects.all()
    if not cvs.exists():
        send_summary_email("NO CVs", stats, [], [], start_time)
        return

    roles = [cv.target_role for cv in cvs if cv.target_role]
    if not roles:
        send_summary_email("NO ROLES", stats, [], [], start_time)
        return

    # BATCHING: Get a random sample of active boards atleast get in line as to not skip other boards.
    # This ensures all boards get scanned over time, but limits the current run to 25.
    boards = JobBoard.objects.filter(is_active=True).order_by('?')[:BATCH_SIZE]
    
    if not boards.exists():
        send_summary_email("NO BOARDS", stats, roles, [], start_time)
        return

    for board in boards:
        stats['boards_scanned'] += 1
        job_links = find_job_links(board.url)
        stats['job_links'] += len(job_links)

        if not job_links:
            stats['boards_no_links'] += 1
            board_details.append({"name": board.name, "links": 0, "leads": 0, "dupes": 0})
            continue

        board_leads = 0
        board_dupes = 0

        for role in roles:
            for url in job_links[:MAX_LINKS_PER_ROLE]:
                added, dupes, junk = process_job_url(url, board, role, blacklist)
                stats['pages_visited'] += 1
                stats['leads_saved'] += added
                stats['duplicates'] += dupes
                stats['junk'] += junk
                board_leads += added
                board_dupes += dupes
                time.sleep(SLEEP_TIME)

        board_details.append({"name": board.name, "links": len(job_links), "leads": board_leads, "dupes": board_dupes})

    status = "SUCCESS" if not stats['errors'] else ("PARTIAL" if stats['leads_saved'] > 0 else "FAILED")
    send_summary_email(status, stats, roles, board_details, start_time)


if __name__ == "__main__":
    scrape_emails()