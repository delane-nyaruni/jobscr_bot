import os
import sys
import time
import django
import requests
import smtplib
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard
from utilities.seed_utils import load_json
from utilities.geo_utils import generate_global_map

# Load configurations from seed folder
SEARCH_QUERIES = load_json('search_queries.json')
NON_JOB_BOARD_DOMAINS = load_json('ignored_domains.json')
JOB_KEYWORDS = load_json('job_keywords.json')


def search_via_tavily(query):
    results = []
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json",
                "X-Tavily-Access-Mode": "keyless",
            },
            json={"query": query, "max_results": 10, "search_depth": "basic"},
            timeout=20,
        )
        data = response.json()
        for item in data.get("results", []):
            url = item.get("url", "")
            if url.startswith("http"):
                results.append(url)
    except Exception as e:
        print(f"      [!] Tavily API error: {e}")
    return results


def is_valid_job_board(url):
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')
        if any(skip in domain for skip in NON_JOB_BOARD_DOMAINS):
            return False, None
        if '.' not in domain:
            return False, None
        if not any(kw in url.lower() for kw in JOB_KEYWORDS):
            return False, None
        name = domain.split('.')[0].capitalize()
        return True, name
    except Exception:
        return False, None


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, stats, board_details, start_time):
    print("\n--- GENERATING EMAIL REPORT ---")
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    missing = []
    if not sender: missing.append("EMAIL_SENDER or EMAIL_USER")
    if not password: missing.append("EMAIL_PASSWORD")
    if not receiver: missing.append("EMAIL_RECEIVER or RECEIVER_EMAIL")

    if missing:
        print(f"  [!] Missing secrets: {', '.join(missing)}. Skipping email.")
        return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    total_boards = JobBoard.objects.count()
    active_boards = JobBoard.objects.filter(is_active=True).count()
    inactive_boards = total_boards - active_boards

    subject = f"Board Discovery [{status}]: {stats['new_added']} Added - {end_time.strftime('%Y-%m-%d')}"

    map_text = generate_global_map(html=False)
    map_html = generate_global_map(html=True)

    body = (
        "Job Board Discovery Run Report\n"
        "==========================================================\n"
        f"Status:              {status}\n"
        f"Started:             {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:            {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:            {duration:.1f} seconds\n"
        "\n"
        "Database Snapshot\n"
        "---------------------------------------------\n"
        f"Total boards in DB:      {total_boards}\n"
        f"Active boards:           {active_boards}\n"
        f"Inactive boards:         {inactive_boards}\n"
        "\n"
        "Discovery Statistics\n"
        "---------------------------------------------\n"
        f"Search queries executed: {stats['queries_run']}/{len(SEARCH_QUERIES)}\n"
        f"Raw URLs returned:       {stats['raw_urls']}\n"
        f"URLs filtered out:       {stats['filtered_out']}\n"
        f"Duplicates skipped:      {stats['duplicates']}\n"
        f"NEW BOARDS ADDED:        {stats['new_added']}\n"
        f"Errors:                  {len(stats['errors'])}\n"
        "\n"
    )

    # Insert Map before Details
    body += map_text
    body += f"\nNew Boards Added This Run [ {stats['new_added']} ]\n"
    body += "---------------------------------------------\n"

    if board_details:
        for b in board_details:
            body += f"[+] {b['name']:<20} {b['domain']}\n"
    else:
        body += "(no new boards this run)\n"

    if stats['errors']:
        body += f"\nErrors Encountered [{len(stats['errors'])}] \n---------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['new_added'] > 0:
        body += "\nNote: New boards are added as ACTIVE by default.\n"

    body += "\nThis is an automated report from Jobscr Behemoth Boards Crawler."

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
        print("  [+] Email sent successfully!")
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")


def discover_boards():
    start_time = datetime.now()
    print("\n--- STARTING JOB BOARD DISCOVERY ---")
    
    if not SEARCH_QUERIES:
        print("  [!] No search queries found in seed/search_queries.json. Exiting.")
        return

    known_domains = set()
    for url in JobBoard.objects.values_list('url', flat=True):
        try:
            known_domains.add(urlparse(url).netloc.lower().replace('www.', ''))
        except Exception:
            pass

    stats = {"queries_run": 0, "raw_urls": 0, "filtered_out": 0, "duplicates": 0, "new_added": 0, "errors": []}
    board_details = []
    max_stage = 15
    seen_this_run = set()

    for query in SEARCH_QUERIES:
        if stats['new_added'] >= max_stage:
            break

        print(f"\n  Searching: {query}")
        urls = search_via_tavily(query)
        stats['queries_run'] += 1
        stats['raw_urls'] += len(urls)
        time.sleep(2)

        if not urls:
            stats['errors'].append(f"Tavily returned 0 results for '{query}'")
            continue

        for url in urls:
            if stats['new_added'] >= max_stage:
                break

            is_valid, name = is_valid_job_board(url)
            if not is_valid:
                stats['filtered_out'] += 1
                continue

            domain = urlparse(url).netloc.lower().replace('www.', '')
            if domain in seen_this_run or domain in known_domains:
                stats['duplicates'] += 1
                continue

            seen_this_run.add(domain)
            known_domains.add(domain)

            try:
                JobBoard.objects.create(name=name, url=url, country="Zimbabwe", is_active=True)
                stats['new_added'] += 1
                board_details.append({"name": name, "domain": domain})
                print(f"      [+] Added to DB: {name} ({domain})")
            except Exception as e:
                stats['errors'].append(f"DB error saving {name}: {e}")

    status = "SUCCESS" if not stats['errors'] else ("PARTIAL" if stats['new_added'] > 0 else "FAILED")
    send_summary_email(status, stats, board_details, start_time)


if __name__ == "__main__":
    print("Initializing Board Discovery Engine...")
    discover_boards()
    print("\nBoard Discovery run complete.")