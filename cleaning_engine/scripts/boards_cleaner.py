import os
import sys
import time
import django
import requests
import smtplib
from datetime import datetime
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
REQUEST_TIMEOUT = 5


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, dead_boards, start_time, total_boards):
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')
    if not (sender and password and receiver): return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    subject = f"Board Cleaner [{status}]: {len(dead_boards)} Dead Boards - {end_time.strftime('%Y-%m-%d')}"

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
        f"Dead Boards Deactivated: {len(dead_boards)}\n"
        "\n"
        "Dead Boards\n"
        "-----------------------------------------------------------------\n"
    )

    if dead_boards:
        for b in dead_boards:
            body += f"[DEAD] {b['name']:<20} {b['url']} (Error: {b['error']})\n"
    else:
        body += "(No dead boards found. All systems operational.)\n"

    body += "\nThis is an automated report from Jobscr Behemoth Boards Cleaner.\n\nPowered by NineSoftStudio."

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


def clean_boards():
    start_time = datetime.now()
    print("\n--- STARTING BOARD CLEANER ---")

    boards = JobBoard.objects.filter(is_active=True)
    total_boards = boards.count()
    dead_boards = []

    print(f"  [*] Checking {total_boards} active boards...")

    for board in boards:
        try:
            response = requests.get(
                board.url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            if response.status_code >= 400:
                print(f"      [X] {board.name} returned status {response.status_code}")
                board.is_active = False
                board.save()
                dead_boards.append({"name": board.name, "url": board.url, "error": f"HTTP {response.status_code}"})
            else:
                print(f"      [+] {board.name} is alive.")
        except requests.exceptions.Timeout:
            print(f"      [X] {board.name} timed out.")
            board.is_active = False
            board.save()
            dead_boards.append({"name": board.name, "url": board.url, "error": "Timeout"})
        except requests.exceptions.RequestException as e:
            print(f"      [X] {board.name} failed: {str(e)[:50]}")
            board.is_active = False
            board.save()
            dead_boards.append({"name": board.name, "url": board.url, "error": "Connection Error"})

        time.sleep(1)

    status = "SUCCESS" if not dead_boards else "PARTIAL"
    send_summary_email(status, dead_boards, start_time, total_boards)


if __name__ == "__main__":
    clean_boards()