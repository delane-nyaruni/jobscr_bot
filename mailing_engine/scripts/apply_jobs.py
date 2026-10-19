import os
import sys
import time
import smtplib
import django
import base64
from datetime import datetime
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobLead, CandidateCV
from mailing_engine.models import ApplicationLog
from utilities.geo_utils import generate_global_map

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
RATE_LIMIT_SECONDS = 30
MAX_APPLICATIONS_PER_RUN = 10


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value: 
            return value
    return None


def get_cv_for_lead(lead):
    """Finds the CV from the DB and returns the object."""
    # 1. Try the specific CV linked to this lead
    if lead.cv_used and lead.cv_used.cv_data:
        return lead.cv_used
        
    # 2. Fallback to any CV that matches the target role and has data
    cv = CandidateCV.objects.filter(target_role=lead.cv_career).exclude(cv_data__isnull=True).exclude(cv_data="").first()
    return cv


def compose_application(sender, cv_obj, lead, candidate_name):
    """Builds the application email with the Base64 CV attached."""
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

    if cv_obj and cv_obj.cv_data:
        try:
            # Decode the Base64 string back into a PDF file
            file_data = base64.b64decode(cv_obj.cv_data)
            msg.add_attachment(
                file_data, 
                maintype='application', 
                subtype='pdf', 
                filename=cv_obj.filename
            )
        except Exception as e:
            # Raise error so the main loop catches it and logs a FAILURE
            raise Exception(f"Failed to decode CV attachment: {e}")

    return msg


def send_summary_email(status, stats, details, start_time):
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver): 
        print("  [!] Missing email credentials. Skipping report.")
        return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    total_leads = JobLead.objects.count()
    unreported = JobLead.objects.filter(is_reported=False).count()
    pending = JobLead.objects.filter(is_reported=True, applied=False).count()
    applied = JobLead.objects.filter(applied=True).count()
    total_cvs = CandidateCV.objects.count()
    total_logs = ApplicationLog.objects.count()
    success_logs = ApplicationLog.objects.filter(status="SUCCESS").count()
    failure_logs = ApplicationLog.objects.filter(status="FAILURE").count()

    mode = "DRY RUN" if stats['dry_run'] else "LIVE"
    subject = f"Job Application [{status}] ({mode}): {stats['sent']} Sent, {stats['failed']} Failed - {end_time.strftime('%Y-%m-%d')}"

    body = (
        "Job Application Run Report\n"
        "=================================================================\n"
        f"Status:              {status}\n"
        f"Mode:                {mode}\n"
        f"Started:             {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:            {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:            {duration:.1f} seconds\n"
        "\n"
        "Database Snapshot\n"
        "---------------------------------------------\n"
        f"Candidate CVs:           {total_cvs}\n"
        f"Total leads in DB:       {total_leads}\n"
        f"Unreported leads:        {unreported}\n"
        f"Reported, not applied:   {pending}\n"
        f"Already applied:         {applied}\n"
        f"Application logs (all):  {total_logs}\n"
        f"  Successful sends:      {success_logs}\n"
        f"  Failed sends:          {failure_logs}\n"
        "\n"
        "Application Statistics (this run)\n"
        "---------------------------------------------\n"
        f"Batch limit:             {MAX_APPLICATIONS_PER_RUN}\n"
        f"Leads in queue:          {stats['queue_total']}\n"
        f"Processing this run:     {stats['eligible']}\n"
        f"Processed:               {stats['processed']}\n"
        f"Emails sent:             {stats['sent']}\n"
        f"Skipped (no CV):         {stats['no_cv']}\n"
        f"Failed sends:            {stats['failed']}\n"
        "\n"
        "Details by Lead\n"
        "---------------------------------------------\n"
    )

    if details:
        for d in details:
            body += f"[{d['status']:<7}] {d['email']:<40} {d['title'][:40]}\n"
            if d.get('reason'):
                body += f"           > {d['reason']}\n"
    else:
        body += "(no leads processed this run)\n"

    if stats['errors']:
        body += "\nErrors Encountered\n---------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['dry_run']:
        body += "\nNOTE: DRY RUN. No emails were actually sent.\n"
    elif stats['sent'] > 0:
        body += "\nSuccessful leads marked as APPLIED in the DB.\n"

    body += generate_global_map()
    body += "\nThis is an automated report from Jobscr Behemoth Vacancy Mailer."

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("  [+] Summary email sent.")
    except Exception as e:
        print(f"  [!] Failed to send summary email: {e}")


def apply_jobs(live=False):
    start_time = datetime.now()
    stats = {"dry_run": not live, "queue_total": 0, "eligible": 0, "processed": 0, "sent": 0, "failed": 0, "no_cv": 0, "errors": []}
    details = []

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')

    if not sender or not password: 
        print("  [!] Missing EMAIL_SENDER / EMAIL_PASSWORD. Exiting.")
        return

    # 1. Get leads that have been reported but not applied to yet
    queue_qs = JobLead.objects.filter(is_reported=True, applied=False)
    stats['queue_total'] = queue_qs.count()
    leads = list(queue_qs.order_by('found_at')[:MAX_APPLICATIONS_PER_RUN])
    stats['eligible'] = len(leads)

    if not leads:
        print("  [-] No eligible leads to apply to.")
        send_summary_email("NO LEADS", stats, details, start_time)
        return

    print(f"  [*] {stats['queue_total']} leads in queue. Processing {stats['eligible']} this run.")

    for lead in leads:
        stats['processed'] += 1
        print(f"\n    -> Lead: {lead.email_link} ({lead.job_title[:50]})")
        
        # 2. Find the CV
        cv_obj = get_cv_for_lead(lead)
        
        if not cv_obj:
            print(f"       [!] No CV found for role '{lead.cv_career}'. Skipping.")
            ApplicationLog.objects.create(
                lead=lead, 
                status="FAILURE", 
                reason=f"CV for role '{lead.cv_career}' not found"
            )
            stats['no_cv'] += 1
            details.append({
                "status": "SKIP", 
                "email": lead.email_link, 
                "title": lead.job_title, 
                "reason": f"No CV for role '{lead.cv_career}'"
            })
            continue

        # 3. Get the name dynamically from the specific CV being used
        candidate_name = cv_obj.full_name if cv_obj.full_name else "Candidate"

        if not live:
            print(f"       [DRY RUN] Would attach {cv_obj.filename} for {candidate_name}")
            details.append({
                "status": "DRY RUN", 
                "email": lead.email_link, 
                "title": lead.job_title, 
                "reason": f"Would attach {cv_obj.filename}"
            })
            continue

        # 4. Send the Email
        try:
            msg = compose_application(sender, cv_obj, lead, candidate_name)
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)

            # 5. Mark as applied and log success
            lead.applied = True
            lead.applied_at = datetime.now()
            lead.save()
            ApplicationLog.objects.create(lead=lead, status="SUCCESS", reason="")
            stats['sent'] += 1
            print(f"       [+] Sent successfully.")
            details.append({
                "status": "SENT", 
                "email": lead.email_link, 
                "title": lead.job_title, 
                "reason": ""
            })
            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as e:
            print(f"       [!] Failed: {e}")
            ApplicationLog.objects.create(
                lead=lead, 
                status="FAILURE", 
                reason=str(e)[:500]
            )
            stats['failed'] += 1
            stats['errors'].append(f"{lead.email_link}: {str(e)[:100]}")
            details.append({
                "status": "FAILED", 
                "email": lead.email_link, 
                "title": lead.job_title, 
                "reason": str(e)[:100]
            })

    print(f"\n  [*] Run complete. Sent: {stats['sent']}, Failed: {stats['failed']}, Skipped: {stats['no_cv']}")

    # 6. Determine Status and Send Report
    if stats['dry_run']:
        status = "DRY RUN"
    elif stats['eligible'] == 0:
        status = "NO LEADS"
    elif not stats['errors'] and stats['sent'] > 0:
        status = "SUCCESS"
    elif stats['sent'] > 0 or stats['no_cv'] > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"

    send_summary_email(status, stats, details, start_time)


if __name__ == "__main__":
    live = '--live' in sys.argv
    apply_jobs(live=live)