import os
import sys
import time
import imaplib
import smtplib
import django
from datetime import datetime
from email.message import EmailMessage

# Project root is three levels up: scripts/ -> cleaning_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from cleaning_engine.models import CleanupRun, MailCleanupTarget

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

GMAIL_ALL_MAIL = '"[Gmail]/All Mail"'
GMAIL_TRASH = '"[Gmail]/Trash"'


def _get_env(*names):
    """Returns the first non-empty environment variable from a list."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, total_count, detailed_log, sender, password, receiver,
                       targets_count=0, successful_targets=0, failed_targets=0,
                       duration_secs=0, start_time=None):
    """Sends the cleanup summary report via SMTP with rich run details."""
    now = datetime.now()
    subject = (
        f"Cleanup Report [{status}]: {total_count} Deleted - "
        f"{now.strftime('%Y-%m-%d')}"
    )

    body = (
        "Email Cleanup Automation Summary\n"
        "=============================================\n"
        f"Status:              {status}\n"
        f"Started:             {start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A'}\n"
        f"Finished:            {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:            {duration_secs:.1f} seconds\n"
        "\n"
        "Run Statistics\n"
        "---------------------------------------------\n"
        f"Cleanup targets configured: {targets_count}\n"
        f"Targets processed OK:       {successful_targets}\n"
        f"Targets with errors:        {failed_targets}\n"
        f"Total emails deleted:       {total_count}\n"
        "\n"
    )

    if detailed_log:
        body += (
            "Details by Sender\n"
            "---------------------------------------------\n"
            f"{detailed_log}\n\n"
        )
    else:
        body += "No per-sender details to report.\n\n"

    body += (
        "Note: Deleted emails are moved to [Gmail]/Trash and will be\n"
        "permanently removed by Gmail after 30 days.\n\n"
        "This is an automated report from Jobscr Email Cleaner."
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("  [+] Summary email sent successfully.")
    except Exception as e:
        print(f"  [!] SMTP Error sending summary: {e}")


def run_cleanup():
    start_time = datetime.now()
    print("\n--- STARTING MAILBOX CLEANUP ---")
    print(f"  [*] Run started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Load credentials
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver):
        print("  [!] Missing email credentials "
              "(EMAIL_SENDER/USER, EMAIL_PASSWORD, EMAIL_RECEIVER/USER).")
        return

    # 2. Get cleanup targets from the database
    targets = list(MailCleanupTarget.objects.values_list("email", flat=True))
    targets_count = len(targets)

    if targets_count == 0:
        print("  [-] No cleanup targets configured in the database.")
        duration = (datetime.now() - start_time).total_seconds()
        send_summary_email(
            status="NO TARGETS",
            total_count=0,
            detailed_log="No cleanup targets configured in the database.",
            sender=sender, password=password, receiver=receiver,
            targets_count=0, successful_targets=0, failed_targets=0,
            duration_secs=duration, start_time=start_time,
        )
        return

    print(f"  [*] {targets_count} cleanup target(s) loaded from database")

    # 3. Connect to IMAP
    mail = None
    total_deleted = 0
    successful_targets = 0
    failed_targets = 0
    detail_lines = []

    try:
        print(f"  [*] Connecting to {IMAP_SERVER} as {sender}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(sender, password)
        mail.select(GMAIL_ALL_MAIL)
        print("  [+] Connected and selected [Gmail]/All Mail")

        # 4. Process each target independently
        for idx, target in enumerate(targets, start=1):
            print(f"  [*] ({idx}/{targets_count}) Searching for emails from: {target}")
            try:
                status, messages = mail.search(None, f'(FROM "{target}")')

                if status != "OK":
                    print(f"      [!] Search failed with status: {status}")
                    detail_lines.append(f"- {target}: SEARCH FAILED ({status})")
                    failed_targets += 1
                    continue

                if not messages[0]:
                    print(f"      [-] No emails found from {target}")
                    detail_lines.append(f"- {target}: 0 emails")
                    successful_targets += 1
                    continue

                mail_ids = messages[0].split()
                count = len(mail_ids)
                delete_errors = 0

                for m_id in mail_ids:
                    try:
                        mail.copy(m_id, GMAIL_TRASH)
                        mail.store(m_id, "+FLAGS", "\\Deleted")
                    except Exception as e:
                        delete_errors += 1
                        print(f"      [!] Failed to move email {m_id}: {e}")

                moved = count - delete_errors
                total_deleted += moved

                if delete_errors > 0:
                    detail_lines.append(
                        f"- {target}: {moved}/{count} emails deleted "
                        f"({delete_errors} failed)"
                    )
                    failed_targets += 1
                else:
                    detail_lines.append(f"- {target}: {count} emails")
                    successful_targets += 1

                print(f"      [+] Deleted {moved} email(s) from {target}")

            except Exception as e:
                print(f"      [!] Error processing target {target}: {e}")
                detail_lines.append(f"- {target}: ERROR ({str(e)[:100]})")
                failed_targets += 1

        # 5. Finalize IMAP session
        mail.expunge()
        mail.logout()
        print(f"  [+] IMAP session closed.")

    except imaplib.IMAP4.error as e:
        print(f"  [!] IMAP authentication/protocol error: {e}")
        duration = (datetime.now() - start_time).total_seconds()
        send_summary_email(
            status="FAILED",
            total_count=0,
            detailed_log=f"IMAP error: {e}",
            sender=sender, password=password, receiver=receiver,
            targets_count=targets_count, successful_targets=0,
            failed_targets=targets_count,
            duration_secs=duration, start_time=start_time,
        )
        return
    except Exception as e:
        print(f"  [!] Unexpected error: {e}")
        duration = (datetime.now() - start_time).total_seconds()
        send_summary_email(
            status="FAILED",
            total_count=0,
            detailed_log=f"Unexpected error: {e}",
            sender=sender, password=password, receiver=receiver,
            targets_count=targets_count, successful_targets=successful_targets,
            failed_targets=failed_targets + 1,
            duration_secs=duration, start_time=start_time,
        )
        return

    # 6. Compute final status
    if failed_targets == 0:
        final_status = "SUCCESS"
    elif successful_targets > 0:
        final_status = "PARTIAL"
    else:
        final_status = "FAILED"

    duration = (datetime.now() - start_time).total_seconds()
    detail = "\n".join(detail_lines)

    print(f"\n  [*] Run finished in {duration:.1f}s")
    print(f"  [*] Total deleted: {total_deleted}")
    print(f"  [*] Targets OK: {successful_targets}, failed: {failed_targets}")

    # 7. Save to database
    try:
        CleanupRun.objects.create(
            total_deleted=total_deleted,
            detail=detail,
        )
        print("  [+] Cleanup run saved to database.")
    except Exception as e:
        print(f"  [!] Failed to save CleanupRun to database: {e}")

    # 8. Send email report (always)
    send_summary_email(
        status=final_status,
        total_count=total_deleted,
        detailed_log=detail,
        sender=sender, password=password, receiver=receiver,
        targets_count=targets_count,
        successful_targets=successful_targets,
        failed_targets=failed_targets,
        duration_secs=duration,
        start_time=start_time,
    )


if __name__ == "__main__":
    print("Initializing Mailbox Cleanup Engine...")
    run_cleanup()
    print("\nCleanup run complete.")