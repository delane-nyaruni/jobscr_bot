import os
import sys
import time
import django
import requests
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
    "google.com", "bing.com", "duckduckgo.com", "pinterest.com",
]


def search_duckduckgo(query):
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', class_='result__url'):
            href = link.get('href', '')
            if 'uddg=' in href:
                parsed = parse_qs(urlparse(href).query)
                if 'uddg' in parsed:
                    href = unquote(parsed['uddg'][0])
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
        for item in soup.find_all('li', class_='b_algo'):
            link = item.find('a', href=True)
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

    for query in SEARCH_QUERIES:
        print(f"\n  Searching: {query}")

        all_urls = []
        print("    [1/2] DuckDuckGo...")
        all_urls.extend(search_duckduckgo(query))
        time.sleep(2)
        print("    [2/2] Bing...")
        all_urls.extend(search_bing(query))
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

    save_json('pending_boards.json', pending)
    print(f"\n  [*] Discovery complete. {new_staged} new boards staged.")
    if new_staged > 0:
        print("  [*] Review seed/pending_boards.json and promote approved boards to jobboards.json")


if __name__ == "__main__":
    print("Initializing Multi-Engine Board Discovery...")
    discover_boards()
    print("\nDiscovery run complete.")