import os
import sys
import smtplib
import django
from datetime import timedelta
from email.message import EmailMessage

# Project root is three levels up: scripts/ -> cleaning_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.utils import timezone
from scrapping_engine.models import IgnoredDomain

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465


def _get_env(*names):
    """Returns the first non-empty environment variable from a list."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def send_summary_email(status, removed, kept, details, sender, password, receiver):
    """Sends the blacklist review report via SMTP."""
    now = timezone.now()
    subject = f"Blacklist Review [{status}]: {removed} Removed, {kept} Kept - {now.strftime('%Y-%m-%d')}"

    body = (
        "Blacklist Review Run Report\n"
        "=================================================================\n"
        f"Status:                  {status}\n"
        f"Finished:                {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "\n"
        "Database Snapshot\n"
        "-----------------------------------------------------------------\n"
        f"Domains Reviewed:        {removed + kept}\n"
        f"Domains Removed:         {removed}\n"
        f"Domains Kept:            {kept}\n"
        "\n"
        "Details\n"
        "-----------------------------------------------------------------\n"
        f"{details}\n\n"
        "This is an automated report from Jobscr Behemoth Blacklist Cleaner.\n\n"
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


def review_blacklist():
    print("\n--- STARTING BLACKLIST REVIEW ---")
    start_time = timezone.now()

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver):
        print("  [!] Missing email credentials. Skipping run.")
        return

    # Look for domains added more than 30 days ago
    thirty_days_ago = start_time - timedelta(days=30)
    old_domains = IgnoredDomain.objects.filter(added_at__lte=thirty_days_ago)
    
    print(f"  [*] Found {old_domains.count()} domains older than 30 days.")

    if old_domains.count() == 0:
        print("  [-] No domains are old enough to review yet.")
        return

    removed_count = 0
    kept_count = 0
    detail_lines = []

    # Keywords that indicate a permanent block (do NOT remove)
    permanent_keywords = [
        "invalid", "does not exist", "syntax", "550", "553", "554", "501", 
        "rejected", "spam", "blocked", "banned", "user unknown"
    ]

    for domain in old_domains:
        reason_lower = domain.reason.lower()
        
        # If the reason contains a permanent keyword, keep it
        if any(kw in reason_lower for kw in permanent_keywords):
            print(f"  [-] Keeping permanent blacklist: {domain.domain} ({domain.reason})")
            detail_lines.append(f"[KEPT] {domain.domain:<30} Reason: {domain.reason}")
            kept_count += 1
        else:
            # If it's a temporary failure (e.g., Timeout, Connection Error, 421), remove it
            print(f"  [+] Removing temporary blacklist: {domain.domain} ({domain.reason})")
            detail_lines.append(f"[REMOVED] {domain.domain:<27} Reason: {domain.reason}")
            domain.delete()
            removed_count += 1

    print(f"\n  [*] Review complete. Removed {removed_count}, Kept {kept_count}.")

    status = "SUCCESS" if removed_count >= 0 else "FAILED"
    details_str = "\n".join(detail_lines)

    send_summary_email(
        status=status,
        removed=removed_count,
        kept=kept_count,
        details=details_str,
        sender=sender,
        password=password,
        receiver=receiver
    )


if __name__ == "__main__":
    print("Initializing Blacklist Cleaner...")
    review_blacklist()
    print("\nBlacklist Review complete.")