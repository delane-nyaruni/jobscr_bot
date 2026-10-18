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
RATE_LIMIT_SECONDS = 30
MAX_APPLICATIONS_PER_RUN = 10


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def get_cv_for_lead(lead):
    """Finds the CV that matches this lead's target role."""
    # 1. Try the specific CV used to find this lead
    if lead.cv_used and lead.cv_used.cv_file:
        return lead.cv_used.cv_file.path
        
    # 2. Fallback to any CV that matches the target role
    cv = CandidateCV.objects.filter(target_role=lead.cv_career).first()
    if cv and cv.cv_file:
        return cv.cv_file.path
        
    return None


def compose_application(sender, cv_path, lead, candidate_name):
    """Builds the application email with the matching CV attached."""
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


def send_summary_email(status, stats, details, start_time):
    """Sends the full application run report."""
    print("\n--- GENERATING EMAIL REPORT ---")

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    missing = []
    if not sender:
        missing.append("EMAIL_SENDER or EMAIL_USER")
    if not password:
        missing.append("EMAIL_PASSWORD")
    if not receiver:
        missing.append("EMAIL_RECEIVER or RECEIVER_EMAIL")

    if missing:
        print(f"  [!] Missing secrets: {', '.join(missing)}. Skipping email.")
        return

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Database snapshot
    total_leads = JobLead.objects.count()
    unreported = JobLead.objects.filter(is_reported=False).count()
    pending = JobLead.objects.filter(is_reported=True, applied=False).count()
    applied = JobLead.objects.filter(applied=True).count()
    total_cvs = CandidateCV.objects.count()
    total_logs = ApplicationLog.objects.count()
    success_logs = ApplicationLog.objects.filter(status="SUCCESS").count()
    failure_logs = ApplicationLog.objects.filter(status="FAILURE").count()

    mode = "DRY RUN" if stats['dry_run'] else "LIVE"
    subject = (
        f"Job Application [{status}] ({mode}): "
        f"{stats['sent']} Sent, {stats['failed']} Failed - "
        f"{end_time.strftime('%Y-%m-%d')}"
    )

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
        body += "\nErrors Encountered\n"
        body += "---------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['dry_run']:
        body += (
            "\nNOTE: This was a DRY RUN. No emails were actually sent.\n"
            "Use --live flag to enable real sending.\n"
        )
    elif stats['sent'] > 0:
        body += (
            "\nSuccessful leads have been marked as APPLIED in the database.\n"
            "Failed leads remain eligible for the next run.\n"
        )

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
        print("  [+] Email sent successfully!")
    except Exception as e:
        print(f"  [!] SMTP Error: {e}")


def apply_jobs(live=False):
    start_time = datetime.now()
    print("\n--- STARTING JOB APPLICATION RUN ---")
    mode = "LIVE" if live else "DRY RUN"
    print(f"  [*] Mode: {mode}")
    print(f"  [*] Run started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    stats = {
        "dry_run": not live,
        "queue_total": 0,
        "eligible": 0,
        "processed": 0,
        "sent": 0,
        "failed": 0,
        "no_cv": 0,
        "errors": [],
    }
    details = []

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')

    if not sender or not password:
        print("  [!] Missing EMAIL_SENDER/USER or EMAIL_PASSWORD. Cannot proceed.")
        return

    # Count the full queue so the report shows total vs batch
    queue_qs = JobLead.objects.filter(is_reported=True, applied=False)
    stats['queue_total'] = queue_qs.count()

    leads = list(queue_qs.order_by('found_at')[:MAX_APPLICATIONS_PER_RUN])
    stats['eligible'] = len(leads)

    if not leads:
        print("  [-] No eligible leads to apply to.")
        send_summary_email("NO LEADS", stats, details, start_time)
        return

    print(f"  [*] {stats['queue_total']} leads in queue, processing {stats['eligible']} this run")

    default_cv = CandidateCV.objects.first()
    candidate_name = default_cv.full_name if default_cv else "Candidate"
    print(f"  [*] Candidate name: {candidate_name}")

    for lead in leads:
        stats['processed'] += 1
        print(f"\n    -> Lead: {lead.email_link} ({lead.job_title[:50]})")

        cv_path = get_cv_for_lead(lead)
        if not cv_path:
            print(f"       [!] No CV for role '{lead.cv_career}'. Skipping.")
            ApplicationLog.objects.create(
                lead=lead, status="FAILURE",
                reason=f"CV for role '{lead.cv_career}' not found",
            )
            stats['no_cv'] += 1
            details.append({
                "status": "SKIP",
                "email": lead.email_link,
                "title": lead.job_title,
                "reason": f"No CV for role '{lead.cv_career}'",
            })
            continue

        if not live:
            print(f"       [DRY RUN] Would attach {os.path.basename(cv_path)}")
            details.append({
                "status": "DRY RUN",
                "email": lead.email_link,
                "title": lead.job_title,
                "reason": f"Would attach {os.path.basename(cv_path)}",
            })
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
            stats['sent'] += 1
            print("       [+] Sent successfully")
            details.append({
                "status": "SENT",
                "email": lead.email_link,
                "title": lead.job_title,
                "reason": "",
            })
            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as e:
            print(f"       [!] Failed: {e}")
            ApplicationLog.objects.create(
                lead=lead, status="FAILURE", reason=str(e)[:500],
            )
            stats['failed'] += 1
            stats['errors'].append(f"{lead.email_link}: {str(e)[:100]}")
            details.append({
                "status": "FAILED",
                "email": lead.email_link,
                "title": lead.job_title,
                "reason": str(e)[:100],
            })

    print(
        f"\n  [*] Run complete. "
        f"Sent: {stats['sent']}, Failed: {stats['failed']}, Skipped: {stats['no_cv']}"
    )

    # Determine status
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