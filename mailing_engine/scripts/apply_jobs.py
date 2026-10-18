import os
import sys
import time
import smtplib
import django
from datetime import datetime
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.conf import settings
from scrapping_engine.models import JobLead, CandidateCV
from mailing_engine.models import ApplicationLog

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
RATE_LIMIT_SECONDS = 30   # Wait 30s between sends to avoid spam flags
MAX_APPLICATIONS_PER_RUN = 10


def get_cv_for_lead(lead):
    """Finds the CV that matches this lead's target role."""
    if lead.cv_used:
        path = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv', lead.cv_used.filename)
        if os.path.exists(path):
            return path
    cv = CandidateCV.objects.filter(target_role=lead.cv_career).first()
    if cv:
        path = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv', cv.filename)
        if os.path.exists(path):
            return path
    return None


def compose_application(sender, cv_path, lead, candidate_name):
    """Builds the application email."""
    msg = EmailMessage()
    msg['Subject'] = f"Application for {lead.job_title} - {candidate_name}"
    msg['From'] = sender
    msg['To'] = lead.email_link
    
    body = f"""Dear Hiring Manager,

I am writing to express my interest in the {lead.job_title} role.

I have attached my CV for your review. I am available to discuss 
how my experience aligns with the requirements of this position.

Best regards,
{candidate_name}
"""
    msg.set_content(body)
    
    if cv_path and os.path.exists(cv_path):
        with open(cv_path, 'rb') as f:
            msg.add_attachment(
                f.read(),
                maintype='application',
                subtype='pdf',
                filename=os.path.basename(cv_path),
            )
    
    return msg


def apply_jobs(live=False):
    print("\n--- STARTING JOB APPLICATION RUN ---")
    if not live:
        print("  [*] DRY RUN MODE (pass --live to actually send)")
    
    sender = os.environ.get('EMAIL_SENDER') or os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    if not sender or not password:
        print("  [!] Missing EMAIL_SENDER / EMAIL_PASSWORD.")
        return
    
    # Only apply to leads we've already told the user about
    leads = JobLead.objects.filter(
        is_reported=True,
        applied=False,
    ).order_by('found_at')[:MAX_APPLICATIONS_PER_RUN]
    
    if not leads.exists():
        print("  [-] No eligible leads to apply to.")
        return
    
    print(f"  [*] {leads.count()} leads eligible for application")
    
    # Get candidate name from the first CV (adjust if you have multiple)
    default_cv = CandidateCV.objects.first()
    candidate_name = default_cv.full_name if default_cv else "Candidate"
    
    sent = 0
    failed = 0
    
    for lead in leads:
        cv_path = get_cv_for_lead(lead)
        if not cv_path:
            print(f"    [!] No CV found for role '{lead.cv_career}'. Skipping.")
            ApplicationLog.objects.create(
                lead=lead, status="FAILURE",
                reason=f"CV for role '{lead.cv_career}' not found",
            )
            failed += 1
            continue
        
        print(f"    -> Applying to {lead.email_link} ({lead.job_title[:50]})")
        
        if not live:
            print(f"       [DRY RUN] Would send {os.path.basename(cv_path)}")
            continue
        
        try:
            msg = compose_application(sender, cv_path, lead, candidate_name)
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)
            
            lead.applied = True
            lead.applied_at = datetime.now()
            lead.save()
            ApplicationLog.objects.create(lead=lead, status="SUCCESS", reason="")
            sent += 1
            print(f"       [+] Sent successfully")
            time.sleep(RATE_LIMIT_SECONDS)
        except Exception as e:
            print(f"       [!] Failed: {e}")
            ApplicationLog.objects.create(
                lead=lead, status="FAILURE", reason=str(e)[:500],
            )
            failed += 1
    
    print(f"\n  [*] Complete. Sent: {sent}, Failed: {failed}")


if __name__ == "__main__":
    live = '--live' in sys.argv
    apply_jobs(live=live)