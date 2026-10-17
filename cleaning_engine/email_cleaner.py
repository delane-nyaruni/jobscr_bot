import os
import imaplib
import smtplib
from datetime import datetime
from email.message import EmailMessage
import django

# 1. SETUP DJANGO ENVIRONMENT
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import CleanupRun, MailCleanupTarget

IMAP_SERVER = "imap.gmail.com"

def send_summary_email(total_count, detailed_log, sender_email, sender_pass, receiver_email):
    """Sends the cleanup summary report via SMTP."""
    subject = f"Cleanup Report: {datetime.now().strftime('%Y-%m-%d')}"
    body = (
        "Email Cleanup Automation Summary\n"
        "---------------------------------------------\n"
        "Status: SUCCESS\n"
        f"Total Deleted: {total_count}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Details by sender:\n{detailed_log}\n\n"
        "This is an automated report from Jobscr Email Cleaner."
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_pass)
            smtp.send_message(msg)
        print("  [+] Summary email sent successfully.")
    except Exception as e:
        print(f"  [!] SMTP Error sending summary: {e}")


def run_cleanup():
    print("\n--- STARTING MAILBOX CLEANUP ---")
    
    # 1. Get targets from the database
    targets = list(MailCleanupTarget.objects.values_list("email", flat=True))
    if not targets:
        print("  [-] No cleanup targets configured in the database.")
        return

    # 2. Load credentials
    email_user = os.environ.get("EMAIL_USER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not email_user or not email_password:
        print("  [!] Missing EMAIL_USER or EMAIL_PASSWORD environment variables.")
        return

    total_deleted = 0
    detail_lines = []

    # 3. Connect and clean
    try:
        print(f"  [*] Connecting to {IMAP_SERVER} as {email_user}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email_user, email_password)
        mail.select('"[Gmail]/All Mail"')

        for target in targets:
            print(f"  [*] Searching for emails from: {target}")
            status, messages = mail.search(None, f'(FROM "{target}")')
            count = 0
            if status == "OK" and messages[0]:
                mail_ids = messages[0].split()
                count = len(mail_ids)
                for m_id in mail_ids:
                    mail.copy(m_id, '"[Gmail]/Trash"')
                    mail.store(m_id, "+FLAGS", "\\Deleted")
                total_deleted += count
            detail_lines.append(f"- {target}: {count} emails")

        mail.expunge()
        mail.logout()
        print(f"  [+] Successfully deleted {total_deleted} emails.")

    except Exception as exc:
        print(f"  [!] IMAP Cleanup failed: {exc}")
        return

    # 4. Save run to database
    detail = "\n".join(detail_lines)
    CleanupRun.objects.create(total_deleted=total_deleted, detail=detail)
    print("  [+] Cleanup run saved to database.")

    # 5. Send report if anything was deleted
    if total_deleted > 0 and receiver_email:
        send_summary_email(total_deleted, detail, email_user, email_password, receiver_email)
    elif total_deleted == 0:
        print("  [-] Nothing deleted. No report sent.")


if __name__ == "__main__":
    print("Initializing Mailbox Cleanup Engine...")
    run_cleanup()
    print("\n Cleanup run complete.")