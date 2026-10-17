import os
import sys
import time
import django
import requests
import smtplib
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlparse

# Project root is three levels up: scripts/ -> scrapping_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard

SEARCH_QUERIES = [
    "zimbabwe job vacancies",
    "zimbabwe jobs recruitment",
    "harare jobs careers",
    "bulawayo job vacancies",
]

NON_JOB_BOARD_DOMAINS = [
    # Social media
    "facebook.com", "twitter.com", "linkedin.com", "youtube.com",
    "instagram.com", "wikipedia.org", "reddit.com", "tiktok.com",
    "pinterest.com", "yahoo.com",
    # Search engines
    "google.com", "bing.com", "duckduckgo.com",
    # Global aggregators (anti-bot blocks make them useless)
    "indeed.com", "ziprecruiter.com", "glassdoor.com", "monster.com",
    # Government / embassy / council
    "usembassy.gov", "gov.zw", "citybyo.co.zw", "hararecity.co.zw",
    # Travel / tourism noise
    "britannica.com", "tripadvisor.com", "worldatlas.com", "mapquest.com",
    "visitseattle.org", "seattle.gov", "pindula.co.zw", "newzimbabwe.com",
    "zimfieldguide.com", "greatzimbabweguide.com", "zimbabwetourism.net",
    "theworldfactbook.org", "countryreports.org", "gisgeography.com",
]

JOB_KEYWORDS = [
    "job", "career", "vacanc", "recruit", "employ",
    "hire", "hiring", "staffing", "talent",
]


def search_via_tavily(query):
    """Tavily keyless API - no account or card required."""
    results = []
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json",
                "X-Tavily-Access-Mode": "keyless",
            },
            json={
                "query": query,
                "max_results": 10,
                "search_depth": "basic",
            },
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
    """Strict filter: domain must look like a job board, not noise."""
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')

        # Reject blacklisted domains (partial match catches subdomains)
        if any(skip in domain for skip in NON_JOB_BOARD_DOMAINS):
            return False, None

        if '.' not in domain:
            return False, None

        # Require a job keyword in the URL
        if not any(kw in url.lower() for kw in JOB_KEYWORDS):
            return False, None

        name = domain.split('.')[0].capitalize()
        return True, name
    except Exception:
        return False, None


def _get_env(*names):
    """Returns the first non-empty environment variable from a list."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(new_added, total_boards, error_log):
    """Sends a summary email after every run."""
    print("\n--- GENERATING EMAIL REPORT ---")

    # Uses the exact environment variables you configured in GitHub
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

    subject = f"Board Discovery Report: {new_added} Added to DB - {datetime.now().strftime('%Y-%m-%d')}"

    body = (
        "Job Board Discovery Run Summary\n"
        "---------------------------------------------\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"New boards added to database: {new_added}\n"
        f"Total boards in database: {total_boards}\n\n"
    )

    if error_log:
        body += f"Errors encountered during run:\n{error_log}\n\n"

    if new_added > 0:
        body += "NOTE: New boards are added as INACTIVE by default.\n"
        body += "Log into your Django Admin panel to review them and check 'Is active' to start scraping them.\n\n"
    else:
        body += "No new boards were found in this run.\n\n"

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


def discover_boards():
    print("\n--- STARTING JOB BOARD DISCOVERY ---")

    # Load existing domains directly from MySQL Database
    known_domains = set()
    for url in JobBoard.objects.values_list('url', flat=True):
        try:
            known_domains.add(urlparse(url).netloc.lower().replace('www.', ''))
        except Exception:
            pass

    print(f"  [*] Already tracking {len(known_domains)} domains in database")

    new_added = 0
    max_stage = 15
    seen_this_run = set()
    error_log = []

    for query in SEARCH_QUERIES:
        if new_added >= max_stage:
            break

        print(f"\n  Searching: {query}")
        print("    [*] Searching via Tavily API...")
        urls = search_via_tavily(query)
        print(f"          -> {len(urls)} raw links")
        time.sleep(2)

        if not urls:
            error_log.append(f"Tavily returned 0 results for '{query}'")
            continue

        for url in urls:
            if new_added >= max_stage:
                break

            is_valid, name = is_valid_job_board(url)
            if not is_valid:
                continue

            domain = urlparse(url).netloc.lower().replace('www.', '')
            if domain in seen_this_run or domain in known_domains:
                continue

            seen_this_run.add(domain)
            known_domains.add(domain)

            # Save directly to MySQL Database
            try:
                JobBoard.objects.create(
                    name=name,
                    url=url,
                    country="Zimbabwe",
                    is_active=False  # Requires manual activation in admin
                )
                print(f"      [+] Added to DB: {name} ({domain})")
                new_added += 1
            except Exception as e:
                print(f"      [!] DB Error saving {name}: {e}")

    print(f"\n  [*] Discovery complete. {new_added} new boards added to database.")

    error_str = "\n".join(error_log) if error_log else None
    
    # Get total board count from DB for the email
    total_boards = JobBoard.objects.count()
    
    # Send Email Report
    send_summary_email(new_added, total_boards, error_str)


if __name__ == "__main__":
    print("Initializing Board Discovery Engine...")
    discover_boards()
    print("\n Boards Discovery run completed.")