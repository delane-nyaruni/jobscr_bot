import os
import sys
import time
import django
import requests
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.utils import timezone
from scrapping_engine.models import JobBoard, DeadLink

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
REQUEST_TIMEOUT = 8
RETRY_AFTER_DAYS = 30


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, dead_boards, revived_boards, start_time, total_boards):
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')
    if not (sender and password and receiver): return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    subject = f"Board Cleaner [{status}]: {len(dead_boards)} Dead, {len(revived_boards)} Revived - {end_time.strftime('%Y-%m-%d')}"

    body = (
        "Job Board Cleaner Report\n"
        "=================================================================\n"
        f"Status:                  {status}\n"
        f"Started:                 {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:                {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:                {duration:.1f} seconds\n"
        "\n"
        "Database Snapshot\n"
        "-----------------------------------------------------------------\n"
        f"Total Boards Checked:    {total_boards}\n"
        f"Newly Dead Deactivated:  {len(dead_boards)}\n"
        f"Revived (From Graveyard):{len(revived_boards)}\n"
        "\n"
        "Newly Dead Boards\n"
        "-----------------------------------------------------------------\n"
    )

    if dead_boards:
        for b in dead_boards:
            body += f"[DEAD] {b['name']:<20} {b['url']} ({b['error']})\n"
    else:
        body += "(No new dead boards found.)\n"

    body += "\nRevived Boards\n-----------------------------------------------------------------\n"
    if revived_boards:
        for b in revived_boards:
            body += f"[ALIVE] {b['name']:<19} {b['url']}\n"
    else:
        body += "(No boards were revived.)\n"

    body += "\nThis is an automated report from Jobscr Behemoth Boards Cleaner.\n\n\n\nPowered by NineSoftStudio."

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)
    msg.add_alternative(f"<div style='font-family: monospace; white-space: pre-wrap;'>{body}</div>", subtype='html')

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("  [+] Summary email sent successfully.")
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")


def check_url(url):
    """Returns (is_alive, reason)."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        # 403/429 means ALIVE but protected
        if response.status_code in [403, 429]:
            return True, f"Protected (HTTP {response.status_code})"
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, "OK"
    except requests.exceptions.Timeout:
        return True, "Timeout (kept active)"
    except requests.exceptions.ConnectionError:
        return False, "DNS/Connection Error"
    except Exception as e:
        return True, f"Unknown (kept active): {str(e)[:40]}"


def clean_boards():
    start_time = datetime.now()
    print("\n--- STARTING BOARD CLEANER ---")

    dead_boards = []
    revived_boards = []

    # ---- PART 1: Scan all ACTIVE boards for new deaths ----
    boards = JobBoard.objects.filter(is_active=True)
    total_boards = boards.count()
    print(f"  [*] Checking {total_boards} active boards...")

    for board in boards:
        is_alive, reason = check_url(board.url)
        if not is_alive:
            print(f"      [X] {board.name} DIED: {reason}")
            board.is_active = False
            board.save()
            DeadLink.objects.update_or_create(
                url=board.url,
                defaults={"domain": board.url.split('/')[2].lower().replace('www.', ''), "reason": reason}
            )
            dead_boards.append({"name": board.name, "url": board.url, "error": reason})
        else:
            print(f"      [+] {board.name} OK: {reason}")
        time.sleep(1)

    # ---- PART 2: Retry boards in the graveyard ----
    cutoff = timezone.now() - timedelta(days=RETRY_AFTER_DAYS)
    old_dead = DeadLink.objects.filter(last_retry__lte=cutoff)
    print(f"\n  [*] Retrying {old_dead.count()} dead links older than {RETRY_AFTER_DAYS} days...")

    for dead in old_dead:
        is_alive, reason = check_url(dead.url)
        if is_alive:
            print(f"      [♻] {dead.domain} is ALIVE again! Reviving.")
            JobBoard.objects.filter(url=dead.url).update(is_active=True)
            revived_boards.append({"name": dead.domain, "url": dead.url})
            dead.delete()
        else:
            print(f"      [X] {dead.domain} still dead ({reason}).")
            dead.retry_count += 1
            dead.reason = reason
            dead.save()   # updates last_retry automatically
        time.sleep(1)

    status = "SUCCESS" if not dead_boards else "PARTIAL"
    send_summary_email(status, dead_boards, revived_boards, start_time, total_boards)


if __name__ == "__main__":
    clean_boards()