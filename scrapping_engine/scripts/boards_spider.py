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
from utilities.seed_utils import load_json, save_json

# Targeted queries for Zimbabwe job boards
SEARCH_QUERIES = [
    "zimbabwe job vacancies",
    "zimbabwe jobs recruitment",
    "harare jobs careers",
    "bulawayo job vacancies",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

NON_JOB_BOARD_DOMAINS = [
    "facebook.com", "twitter.com", "linkedin.com", "youtube.com",
    "instagram.com", "wikipedia.org", "reddit.com", "tiktok.com",
    "google.com", "bing.com", "duckduckgo.com", "pinterest.com", "yahoo.com",
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
    """
    Uses Tavily's keyless API for web search.
    No API key, no account, no credit card required.
    Docs: https://docs.tavily.com/documentation/keyless
    """
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
    """Strict filter: domain or path must contain a job keyword."""
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
    """Returns the first non-empty environment variable from a list."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(new_staged, total_pending, error_log):
    """Sends a summary email after every run."""
    print("\n--- GENERATING EMAIL REPORT ---")

    # Accept BOTH naming conventions so existing GitHub Secrets work
    sender = _get_env('EMAIL_USER', 'EMAIL_SENDER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('RECEIVER_EMAIL', 'EMAIL_RECEIVER')

    missing = []
    if not sender:
        missing.append("EMAIL_USER or EMAIL_SENDER")
    if not password:
        missing.append("EMAIL_PASSWORD")
    if not receiver:
        missing.append("RECEIVER_EMAIL or EMAIL_RECEIVER")

    if missing:
        print(f"  [!] Missing secrets: {', '.join(missing)}. Skipping email.")
        print("      Add them at: GitHub Repo -> Settings -> Secrets and variables -> Actions.")
        return

    subject = f"Board Discovery Report: {new_staged} New - {datetime.now().strftime('%Y-%m-%d')}"

    body = (
        "Job Board Discovery Run Summary\n"
        "---------------------------------------------\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"New boards staged: {new_staged}\n"
        f"Total boards in pending list: {total_pending}\n\n"
    )

    if error_log:
        body += f"Errors encountered during run:\n{error_log}\n\n"

    if new_staged > 0:
        body += "Review seed/pending_boards.json and promote approved boards to jobboards.json.\n\n"
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

    # Load existing URLs from DB and pending file
    known_domains = set()
    for url in JobBoard.objects.values_list('url', flat=True):
        try:
            known_domains.add(urlparse(url).netloc.lower().replace('www.', ''))
        except Exception:
            pass

    pending = load_json('pending_boards.json')
    for board in pending:
        try:
            known_domains.add(urlparse(board['url']).netloc.lower().replace('www.', ''))
        except Exception:
            pass

    print(f"  [*] Already tracking {len(known_domains)} domains")

    new_staged = 0
    max_stage = 15
    seen_this_run = set()
    error_log = []

    for query in SEARCH_QUERIES:
        if new_staged >= max_stage:
            break

        print(f"\n  Searching: {query}")

        # Use Tavily API (keyless, reliable)
        print("    [*] Searching via Tavily API...")
        urls = search_via_tavily(query)
        print(f"          -> {len(urls)} raw links")
        time.sleep(2)  # Be polite even with API

        if not urls:
            error_log.append(f"Tavily returned 0 results for '{query}'")
            continue

        for url in urls:
            if new_staged >= max_stage:
                break

            is_valid, name = is_valid_job_board(url)
            if not is_valid:
                continue

            domain = urlparse(url).netloc.lower().replace('www.', '')
            if domain in seen_this_run or domain in known_domains:
                continue

            seen_this_run.add(domain)
            known_domains.add(domain)

            pending.append({
                "name": name,
                "url": url,
                "country": "Zimbabwe",
                "source_query": query,
            })
            print(f"      [+] Staged: {name} ({domain})")
            new_staged += 1

    # Save the updated pending list
    save_json('pending_boards.json', pending)
    print(f"\n  [*] Discovery complete. {new_staged} new boards staged.")

    if new_staged > 0:
        print("  [*] Review seed/pending_boards.json and promote approved boards to jobboards.json")

    error_str = "\n".join(error_log) if error_log else None
    send_summary_email(new_staged, len(pending), error_str)


if __name__ == "__main__":
    print("Initializing Multi-Engine Board Discovery...")
    discover_boards()
    print("\nDiscovery run complete.")