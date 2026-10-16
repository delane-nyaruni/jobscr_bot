import os
import sys
import csv
import smtplib
from datetime import datetime
from email.message import EmailMessage
import django

# 1. SETUP DJANGO ENVIRONMENT
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.conf import settings
from django.core.management import call_command
from scrapping_engine.models import JobBoard, CandidateCV, JobLead
from scrapping_engine.utils import parse_cv_filename

def sync_cvs_from_folder():
    """Reads media/docs/cv/ and adds new CVs to the database."""
    print("\n--- STEP 1: Syncing CVs ---")
    cv_folder = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv')
    
    if not os.path.exists(cv_folder):
        print(f"Creating CV folder at {cv_folder}")
        os.makedirs(cv_folder)
        return

    found_new = False
    for filename in os.listdir(cv_folder):
        if not filename.lower().endswith('.pdf'):
            continue
            
        if not CandidateCV.objects.filter(filename=filename).exists():
            name, role = parse_cv_filename(filename)
            if name and role:
                CandidateCV.objects.create(filename=filename, full_name=name, target_role=role)
                print(f"  [+] Added CV: {name} - Role: {role}")
                found_new = True
                
    if not found_new:
        print("  [-] No new CVs to add.")

def seed_job_boards():
    """Adds default job boards if the database is empty."""
    print("\n--- STEP 2: Seeding Job Boards ---")
    
    default_boards = [
        {"name": "ZimbaJob", "url": "https://www.zimbajob.com/", "country": "Zimbabwe"},
        {"name": "VacancyMail", "url": "https://vacancymail.co.zw/", "country": "Zimbabwe"},
        {"name": "Classifieds", "url": "https://www.classifieds.co.zw/jobs", "country": "Zimbabwe"},
        {"name": "MyJobboard", "url": "https://example.com/jobs", "country": "Zimbabwe"},
    ]

    for board in default_boards:
        obj, created = JobBoard.objects.get_or_create(
            url=board['url'],
            defaults={'name': board['name'], 'country': board['country']}
        )
        if created:
            print(f"  [+] Added Board: {board['name']}")
        else:
            print(f"  [-] Board already exists: {board['name']}")

def send_session_report(start_time):
    """Fetches leads created during this session, saves to CSV, and emails them."""
    print("\n--- STEP 4: Generating Report & Sending Email ---")
    
    # 1. Fetch leads scraped since the script started
    new_leads = JobLead.objects.filter(found_at__gte=start_time)
    lead_count = new_leads.count()
    
    print(f"  Found {lead_count} new leads in this session.")

    # 2. Setup Email Credentials (Ensure these are in your environment variables)
    SENDER_EMAIL = os.environ.get('EMAIL_SENDER')
    SENDER_PASS = os.environ.get('EMAIL_PASSWORD')
    RECEIVER_EMAIL = os.environ.get('EMAIL_RECEIVER')

    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("  [!] Missing EMAIL_SENDER, EMAIL_PASSWORD, or RECEIVER_EMAIL environment variables. Skipping email.")
        return

    # 3. Generate CSV
    csv_dir = os.path.join(settings.BASE_DIR, 'csv')
    os.makedirs(csv_dir, exist_ok=True)
    csv_filename = f"job_leads_{start_time.strftime('%Y%m%d_%H%M%S')}.csv"
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
    msg['Subject'] = f"JobScr Report: {lead_count} New Leads - {start_time.strftime('%Y-%m-%d')}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg.set_content(
        f"Scraping session completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n"
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
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")

if __name__ == "__main__":
    # Record the exact time the script started
    session_start_time = datetime.now()
    print(f" Initializing Jobscr Engine at {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}...")
    
    # 1. Get CVs
    sync_cvs_from_folder()
    
    # 2. Add Job Boards
    seed_job_boards()
    
    # 3. Trigger the Scraper
    print("\n--- STEP 3: Starting Scraper ---")
    try:
        call_command('scrape_boards')
    except Exception as e:
        print(f"[!] Scraper error: {e}")

    # 4. Send Email Report
    send_session_report(session_start_time)

    print("\n Engine run complete.")