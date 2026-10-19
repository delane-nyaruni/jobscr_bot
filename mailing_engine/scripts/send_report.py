import os
import sys
import csv
import smtplib
from datetime import datetime
from email.message import EmailMessage
import django

# Project root is three levels up: scripts/ -> mailing_engine/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.conf import settings
from scrapping_engine.models import JobLead

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465


def generate_csv(leads, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    filename = f"job_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date Scraped', 'Email Link', 'Job Board',
            'Job Title', 'Role Searched', 'Country'
        ])
        for lead in leads:
            writer.writerow([
                lead.found_at.strftime("%Y-%m-%d %H:%M"),
                lead.email_link,
                lead.job_board.name,
                lead.job_title,
                lead.cv_career,
                lead.country,
            ])
    return filepath, filename


def send_email(sender, password, receiver, subject, body, attachment_path, attachment_name):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)

    with open(attachment_path, 'rb') as f:
        msg.add_attachment(
            f.read(),
            maintype='application',
            subtype='csv',
            filename=attachment_name
        )

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


def send_report():
    print("\n--- STARTING REPORT ENGINE ---")
    sender = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = os.environ.get('RECEIVER_EMAIL')

    if not all([sender, password, receiver]):
        print("  [!] Missing EMAIL_USER, EMAIL_PASSWORD, or RECEIVER_EMAIL.")
        return

    unreported = JobLead.objects.filter(is_reported=False).order_by('found_at')
    count = unreported.count()

    if count == 0:
        print("  [-] No unreported leads to send. Exiting.")
        return

    print(f"  [*] Found {count} unreported leads.")

    csv_dir = os.path.join(settings.BASE_DIR, 'csv')
    filepath, filename = generate_csv(unreported, csv_dir)
    print(f"  [+] CSV generated: {filename}")

    subject = f"JobScr Report: {count} New Leads - {datetime.now().strftime('%Y-%m-%d')}"
    body = (
        f"JobScr Automated Report\n"
        f"---------------------------------------------\n"
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Total new leads: {count}\n\n"
        f"See the attached CSV for details.\n\n"
        f"This is an automated report from GitHub Actions."
    )

    try:
        print("  [*] Sending email...")
        send_email(sender, password, receiver, subject, body, filepath, filename)
        print("  [+] Email sent successfully.")
        updated = unreported.update(is_reported=True)
        print(f"  [+] Marked {updated} leads as reported.")
    except smtplib.SMTPAuthenticationError:
        print("  [!] SMTP Auth failed. Check Gmail App Password.")
    except Exception as e:
        print(f"  [!] Email error: {e}")


if __name__ == "__main__":
    print("Initializing Report Engine...")
    send_report()
    print("\nReport run completed.")