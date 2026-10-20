import os
import sys
import time
import imaplib
import smtplib
import django
from datetime import datetime
from email.message import EmailMessage
from django.db.models import Sum

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from cleaning_engine.models import CleanupRun, MailCleanupTarget
from mailing_engine.models import ApplicationLog

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

GMAIL_ALL_MAIL = '"[Gmail]/All Mail"'
GMAIL_TRASH = '"[Gmail]/Trash"'


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, total_count, detailed_log, sender, password, receiver,
                       manual_targets=0, auto_targets=0, successful_targets=0, failed_targets=0,
                       duration_secs=0, start_time=None):
    now = datetime.now()
    subject = f"Cleanup Report [{status}]: {total_count} Deleted - {now.strftime('%Y-%m-%d')}"

    total_runs = CleanupRun.objects.count()
    total_ever = CleanupRun.objects.aggregate(total=Sum('total_deleted'))['total'] or 0
    total_targets = manual_targets + auto_targets

    body = (
        "Email Cleanup Run Report\n"
        "=================================================================\n"
        f"Status:                  {status}\n"
        f"Started:                 {start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A'}\n"
        f"Finished:                {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:                {duration_secs:.1f} seconds\n"
        "\n\n"
        "Database Snapshot\n"
        "-----------------------------------------------------------------\n"
        f"Manual Cleanup Targets:  {manual_targets}\n"
        f"Auto-Tracked (Applied):  {auto_targets}\n"
        f"Total Cleanup Targets:   {total_targets}\n"
        f"Total Cleanup Runs:      {total_runs}\n"
        f"Total Deleted (All):     {total_ever}\n"
        "\n\n"
        "Cleanup Statistics\n"
        "-----------------------------------------------------------------\n"
        f"Targets Processed OK:    {successful_targets}\n"
        f"Targets With Errors:     {failed_targets}\n"
        f"Emails Deleted:          {total_count}\n"
        "\n\n"
    )

    body += f"\nDetails by System [{total_targets}]\n"
    body += "-----------------------------------------------------------------\n"
    
    if detailed_log:
        body += f"{detailed_log}\n\n"
    else:
        body += "No per-sender details to report.\n\n"

    body += (
        "Note: Deleted emails are moved to [Gmail]/Trash and will be\n"
        "permanently removed by Gmail after 30 days.\n\n"
        "This is an automated report from Jobscr Behemoth Mail Cleaner.\n\n\n\n"
        "Powered by ninesoftstudio"
    )

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
        print(f"  [!] SMTP Error sending summary: {e}")


def run_cleanup():
    start_time = datetime.now()
    print("\n--- STARTING MAILBOX CLEANUP ---")
    print(f"  [*] Run started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver):
        print("  [!] Missing email credentials (EMAIL_SENDER/USER, EMAIL_PASSWORD, EMAIL_RECEIVER/USER).")
        return

    # ==========================================================
    # 1. Get manual targets (MailCleanupTarget)
    # ==========================================================
    manual_targets = list(MailCleanupTarget.objects.values_list("email", flat=True))
    manual_count = len(manual_targets)
    print(f"  [*] {manual_count} manual cleanup target(s) loaded")

    # ==========================================================
    # 2. Get auto-targets from ApplicationLog (emails we've sent to)
    # ==========================================================
    auto_targets = list(
        ApplicationLog.objects
        .filter(status="SUCCESS", lead__isnull=False)
        .values_list("lead__email_link", flat=True)
        .distinct()
    )
    auto_count = len(auto_targets)
    print(f"  [*] {auto_count} auto-tracked addresses from successful applications")

    # ==========================================================
    # 3. Combine and dedupe
    # ==========================================================
    targets_set = set(manual_targets) | set(auto_targets)
    targets = list(targets_set)
    total_targets = len(targets)
    print(f"  [*] {total_targets} total unique cleanup target(s) after deduplication")

    if total_targets == 0:
        print("  [-] No cleanup targets configured (neither manual nor auto-tracked).")
        duration = (datetime.now() - start_time).total_seconds()
        send_summary_email(
            status="NO TARGETS",
            total_count=0,
            detailed_log="No cleanup targets configured in the database (manual or auto-tracked).",
            sender=sender, password=password, receiver=receiver,
            manual_targets=0, auto_targets=0, successful_targets=0, failed_targets=0,
            duration_secs=duration, start_time=start_time,
        )
        return

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

        for idx, target in enumerate(targets, start=1):
            # Determine the source for reporting
            if target in manual_targets and target in auto_targets:
                source = "MANUAL+AUTO"
            elif target in manual_targets:
                source = "MANUAL"
            else:
                source = "AUTO-APPLIED"

            print(f"  [*] ({idx}/{total_targets}) [{source}] Searching for emails from: {target}")
            try:
                status, messages = mail.search(None, f'(FROM "{target}")')

                if status != "OK":
                    print(f"      [!] Search failed with status: {status}")
                    detail_lines.append(f"- [{source}] {target}: SEARCH FAILED ({status})")
                    failed_targets += 1
                    continue

                if not messages[0]:
                    print(f"      [-] No emails found from {target}")
                    detail_lines.append(f"- [{source}] {target}: 0 emails")
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
                        f"- [{source}] {target}: {moved}/{count} emails deleted ({delete_errors} failed)"
                    )
                    failed_targets += 1
                else:
                    detail_lines.append(f"- [{source}] {target}: {count} emails")
                    successful_targets += 1

                print(f"      [+] Deleted {moved} email(s) from {target}")

            except Exception as e:
                print(f"      [!] Error processing target {target}: {e}")
                detail_lines.append(f"- [{source}] {target}: ERROR ({str(e)[:100]})")
                failed_targets += 1

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
            manual_targets=manual_count, auto_targets=auto_count,
            successful_targets=0, failed_targets=total_targets,
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
            manual_targets=manual_count, auto_targets=auto_count,
            successful_targets=successful_targets, failed_targets=failed_targets + 1,
            duration_secs=duration, start_time=start_time,
        )
        return

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

    try:
        CleanupRun.objects.create(
            total_deleted=total_deleted,
            detail=detail,
        )
        print("  [+] Cleanup run saved to database.")
    except Exception as e:
        print(f"  [!] Failed to save CleanupRun to database: {e}")

    send_summary_email(
        status=final_status,
        total_count=total_deleted,
        detailed_log=detail,
        sender=sender, password=password, receiver=receiver,
        manual_targets=manual_count,
        auto_targets=auto_count,
        successful_targets=successful_targets,
        failed_targets=failed_targets,
        duration_secs=duration,
        start_time=start_time,
    )


if __name__ == "__main__":
    print("Initializing Mailbox Cleanup Engine...")
    run_cleanup()
    print("\nCleanup run complete.")