import os
import sys
import imaplib
import smtplib
from datetime import datetime
from email.message import EmailMessage
import django

# Project root is three levels up: scripts/ -> cleaning_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from cleaning_engine.models import MailCleanupTarget, CleanupRun

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

GMAIL_ALL_MAIL = '"[Gmail]/All Mail"'
GMAIL_TRASH = '"[Gmail]/Trash"'


def send_summary(sender, password, receiver, total_deleted, detail):
    subject = f"Cleanup Report: {datetime.now().strftime('%Y-%m-%d')}"
    body = (
        "Email Cleanup Automation Summary\n"
        "---------------------------------------------\n"
        "Status: SUCCESS\n"
        f"Total Deleted: {total_deleted}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Details by sender:\n{detail}\n\n"
        "This is an automated report from GitHub Actions."
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


def clean_mailbox():
    print("\n--- STARTING MAILBOX CLEANUP ---")

    targets = list(MailCleanupTarget.objects.values_list('email', flat=True))
    if not targets:
        print("  [-] No cleanup targets configured.")
        return

    print(f"  [*] {len(targets)} target senders loaded.")

    sender = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = os.environ.get('RECEIVER_EMAIL')

    if not sender or not password:
        print("  [!] Missing EMAIL_USER or EMAIL_PASSWORD.")
        return

    total_deleted = 0
    detail_lines = []

    try:
        print(f"  [*] Connecting to {IMAP_SERVER}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(sender, password)
        mail.select(GMAIL_ALL_MAIL)

        for target in targets:
            print(f"    Searching: {target}")
            status, messages = mail.search(None, f'(FROM "{target}")')
            count = 0

            if status == "OK" and messages[0]:
                mail_ids = messages[0].split()
                count = len(mail_ids)
                for mail_id in mail_ids:
                    mail.copy(mail_id, GMAIL_TRASH)
                    mail.store(mail_id, "+FLAGS", "\\Deleted")
                total_deleted += count

            detail_lines.append(f"- {target}: {count} emails")

        mail.expunge()
        mail.logout()
        print(f"  [+] Cleanup finished. {total_deleted} emails deleted.")
    except imaplib.IMAP4.error as e:
        print(f"  [!] IMAP error: {e}")
        return
    except Exception as e:
        print(f"  [!] Unexpected error: {e}")
        return

    detail = "\n".join(detail_lines)
    CleanupRun.objects.create(total_deleted=total_deleted, detail=detail)
    print("  [+] Cleanup run saved to database.")

    if total_deleted > 0 and receiver:
        try:
            send_summary(sender, password, receiver, total_deleted, detail)
            print("  [+] Summary email sent.")
        except Exception as e:
            print(f"  [!] Failed to send summary: {e}")
    else:
        print("  [-] Nothing deleted. No summary sent.")


if __name__ == "__main__":
    print("Initializing Mailbox Cleanup Engine...")
    clean_mailbox()
    print("\nCleanup run complete.")