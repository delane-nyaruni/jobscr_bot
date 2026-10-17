import os
import sys
import time
import django
import requests
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime
from email.message import EmailMessage
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

# Project root is three levels up: scripts/ -> scrapping_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard
from utilities.seed_utils import load_json, save_json

# Simple, unquoted queries - quoted phrases break Bing RSS
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
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def search_bing_rss(query):
    """Bing RSS feed without broken mkt param, using cc=zw for Zimbabwe."""
    results = []
    try:
        url = (
            f"https://www.bing.com/search"
            f"?q={requests.utils.quote(query)}"
            f"&format=rss&cc=zw&count=20"
        )
        response = requests.get(url, headers=HEADERS, timeout=15)

        root = ET.fromstring(response.content)
        for item in root.findall('.//item'):
            link = item.find('link')
            if link is not None and link.text and link.text.startswith('http'):
                results.append(link.text)

    except Exception as e:
        print(f"      [!] Bing RSS error: {e}")
    return results


def search_duckduckgo_lite(query):
    """DuckDuckGo Lite endpoint (more lenient than html.duckduckgo.com)."""
    results = []
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 202:
            print("      [!] DuckDuckGo returned CAPTCHA (202).")
            return results

        soup = BeautifulSoup(response.text, 'html.parser')

        # Lite version uses 'result-link' class for URL anchors
        for link in soup.find_all('a', class_='result-link'):
            href = link.get('href', '')
            if href.startswith('http'):
                results.append(href)

        # Fallback: some versions wrap in redirect
        if not results:
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'uddg=' in href:
                    parsed = parse_qs(urlparse(href).query)
                    if 'uddg' in parsed:
                        href = unquote(parsed['uddg'][0])
                if href.startswith('http') and 'duckduckgo' not in href:
                    results.append(href)

    except Exception as e:
        print(f"      [!] DuckDuckGo Lite error: {e}")
    return results


def is_valid_job_board(url):
    """Strict filter: domain or path must contain a job keyword."""
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')

        if any(skip in domain for skip in NON_JOB_BOARD_DOMAINS):
            return False, None

        if '.' not in domain:
            return False, None

        # Require a job keyword in the full URL
        if not any(kw in url.lower() for kw in JOB_KEYWORDS):
            return False, None

        name = domain.split('.')[0].capitalize()
        return True, name
    except Exception:
        return False, None


def _get_env(*names):
    """Returns the first non-empty env variable from a list of names."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(new_staged, total_pending, error_log):
    """Sends a summary email after every run."""
    print("\n--- GENERATING EMAIL REPORT ---")

    # Accept BOTH naming conventions so GitHub Secrets don't need to change
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

    known_urls = set(JobBoard.objects.values_list('url', flat=True))
    known_domains = set()
    for url in known_urls:
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

        # Engine 1: Bing RSS
        print("    [1/2] Bing RSS...")
        bing = search_bing_rss(query)
        print(f"          -> {len(bing)} raw links")
        time.sleep(2)

        # Engine 2: DuckDuckGo Lite
        print("    [2/2] DuckDuckGo Lite...")
        ddg = search_duckduckgo_lite(query)
        print(f"          -> {len(ddg)} raw links")
        time.sleep(2)

        all_urls = bing + ddg

        if not all_urls:
            error_log.append(f"Both engines returned 0 results for '{query}'")
            continue

        for url in all_urls:
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