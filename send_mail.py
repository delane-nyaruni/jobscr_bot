import os
import csv
import smtplib
from datetime import datetime
from email.message import EmailMessage
import django

# 1. SETUP DJANGO ENVIRONMENT
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.conf import settings
from scrapping_engine.models import JobLead

def send_report():
    """Fetches unreported leads, saves to CSV, and emails them."""
    print("\n--- STEP 1: Generating Report & Sending Email ---")
    
    # 1. Fetch leads that have NOT been emailed yet
    new_leads = JobLead.objects.filter(is_reported=False)
    lead_count = new_leads.count()
    
    print(f"  Found {lead_count} unreported leads.")

    if lead_count == 0:
        print("  [-] No new leads to report. Exiting.")
        return

    # 2. Setup Email Credentials
    SENDER_EMAIL = os.environ.get('EMAIL_USER')
    SENDER_PASS = os.environ.get('EMAIL_PASSWORD')
    RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL')

    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("  [!] Missing EMAIL_USER, EMAIL_PASSWORD, or RECEIVER_EMAIL environment variables. Skipping email.")
        return

    # 3. Generate CSV
    csv_dir = os.path.join(settings.BASE_DIR, 'csv')
    os.makedirs(csv_dir, exist_ok=True)
    csv_filename = f"job_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(csv_dir, csv_filename)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date Scraped', 'Email Link', 'Job Board', 'Job Title', 'Role Searched', 'Country'])
        for lead in new_leads:
            writer.writerow([
                lead.found_at.strftime("%Y-%m-%d %H:%M"),
                lead.email_link,
                lead.job_board.name,
                lead.job_title,
                lead.cv_career,
                lead.country
            ])

    # 4. Construct and Send Email
    msg = EmailMessage()
    msg['Subject'] = f"JobScr Report: {lead_count} New Leads - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg.set_content(
        f"Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n"
        f"Total new leads found: {lead_count}\n\n"
        f"Please find the attached CSV file for details."
    )

    with open(filepath, 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='csv', filename=csv_filename)

    try:
        print("  [*] Connecting to SMTP server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)
        print("  [+] Email sent successfully!")
        
        # 5. MARK LEADS AS REPORTED SO WE DON'T SEND THEM AGAIN
        new_leads.update(is_reported=True)
        print("  [+] Marked leads as reported in the database.")
        
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")

if __name__ == "__main__":
    print("Initializing Jobscr Report Engine...")
    send_report()
    print("\nReporting run complete.")