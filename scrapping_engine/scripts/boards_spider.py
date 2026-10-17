import os
import sys
import time
import django
import requests
import smtplib
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

SEARCH_QUERIES = [
    "zimbabwe job vacancies",
    "zimbabwe careers site:.co.zw",
    "harare jobs recruitment",
    "bulawayo vacancies",
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
    "google.com", "bing.com", "duckduckgo.com", "pinterest.com", "yahoo.com"
]


def search_duckduckgo(query):
    results = []
    try:
        # Use the lighter, more scrape-friendly endpoint
        url = f"https://lite.duckduckgo.com/lite/?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        # If we get a 202, it means DDG is challenging us with a CAPTCHA
        if response.status_code == 202:
            print("      [!] DuckDuckGo blocked the request (CAPTCHA).")
            return results

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Lite version uses 'result-link' class for URLs
        for link in soup.find_all('a', class_='result-link'):
            href = link.get('href', '')
            if href.startswith('http'):
                results.append(href)
                
    except Exception as e:
        print(f"      [!] DuckDuckGo error: {e}")
    return results


def search_bing(query):
    results = []
    try:
        url = f"https://www.bing.com/search?q={requests.utils.quote(query)}&count=20"
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Bing has been changing classes. This looks for <h2> tags inside search results
        for h2 in soup.find_all('h2'):
            link = h2.find('a', href=True)
            if link and link['href'].startswith('http'):
                results.append(link['href'])
                
    except Exception as e:
        print(f"      [!] Bing error: {e}")
    return results


def is_valid_job_board(url):
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')
        if any(skip in domain for skip in NON_JOB_BOARD_DOMAINS):
            return False, None
        if '.' not in domain:
            return False, None
        name = domain.split('.')[0].capitalize()
        return True, name
    except Exception:
        return False, None


def send_summary_email(new_staged, total_pending, error_log):
    """Sends a summary email after every run, even if 0 boards were found."""
    print("\n--- GENERATING EMAIL REPORT ---")
    
    sender = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = os.environ.get('RECEIVER_EMAIL')

    if not all([sender, password, receiver]):
        print("  [!] Missing EMAIL_USER, EMAIL_PASSWORD, or RECEIVER_EMAIL. Skipping email.")
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
        body += "Please check `seed/pending_boards.json` in your repository to review the new boards and promote the good ones to `jobboards.json`.\n\n"
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
    seen_this_run = set()
    error_log = []

    for query in SEARCH_QUERIES:
        print(f"\n  Searching: {query}")

        all_urls = []
        
        print("    [1/2] DuckDuckGo...")
        ddg_results = search_duckduckgo(query)
        if not ddg_results:
            error_log.append(f"DuckDuckGo returned 0 results for '{query}'")
        all_urls.extend(ddg_results)
        time.sleep(2)
        
        print("    [2/2] Bing...")
        bing_results = search_bing(query)
        if not bing_results:
            error_log.append(f"Bing returned 0 results for '{query}'")
        all_urls.extend(bing_results)
        time.sleep(2)

        for url in all_urls:
            if new_staged >= 20:
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
                "source_query": query
            })
            print(f"      [+] Staged: {name} ({domain})")
            new_staged += 1

    # Save the updated pending list
    save_json('pending_boards.json', pending)
    print(f"\n  [*] Discovery complete. {new_staged} new boards staged.")
    
    if new_staged > 0:
        print("  [*] Review seed/pending_boards.json and promote approved boards to jobboards.json")

    # Convert error log list to string for email
    error_str = "\n".join(error_log) if error_log else None

    # Send Email Report
    send_summary_email(new_staged, len(pending), error_str)


if __name__ == "__main__":
    print("Initializing Multi-Engine Board Discovery...")
    discover_boards()
    print("\nDiscovery run complete.")