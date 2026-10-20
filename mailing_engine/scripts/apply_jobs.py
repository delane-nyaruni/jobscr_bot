import os
import sys
import time
import smtplib
import django
import base64
import re
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.utils import timezone
from scrapping_engine.models import JobLead, CandidateCV, IgnoredDomain
from mailing_engine.models import ApplicationLog
from utilities.geo_utils import generate_global_map

# Import gear logic from the single source of truth
from utilities.gears_ratio_settings import (
    GEARS,
    match_gear,
    calculate_math,
    find_closest_gear_by_throughput,
)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
MAX_APPLICATIONS_PER_RUN = 30
RATE_LIMIT_SECONDS = 40


def _get_env(*names):
    for name in names:
        value = os.environ.get(name)
        if value: 
            return value
    return None


def check_engine_diagnostics():
    """Reads the YAML file and classifies the engine gear (exact or custom)."""
    print("\n--- BEHEMOTH ENGINE DIAGNOSTICS ---")
    
    available_gears = ", ".join([f"{k} ({v['name']})" for k, v in GEARS.items()])
    print(f"  [*] Available Gears: {available_gears}")
    
    yml_path = os.path.join(BASE_DIR, '.github', 'workflows', 'mailing_robot.yml')
    
    if not os.path.exists(yml_path):
        print("  [!] Could not find mailing_robot.yml. Skipping gear check.")
        return "UNKNOWN (YML Missing)"

    with open(yml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    timeout_match = re.search(r'timeout-minutes:\s*(\d+)', content)
    cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", content)
    if not cron_match:
        cron_match = re.search(r"cron:\s*([^\s]+)", content)

    yaml_timeout = int(timeout_match.group(1)) if timeout_match else 0
    yaml_cron = cron_match.group(1).strip() if cron_match else "Unknown"

    print(f"  [*] Python Settings : Batch={MAX_APPLICATIONS_PER_RUN}, Delay={RATE_LIMIT_SECONDS}s")
    print(f"  [*] YAML Settings   : Timeout={yaml_timeout}m, Cron={yaml_cron}")

    matched_key, matched_gear = match_gear(
        MAX_APPLICATIONS_PER_RUN, RATE_LIMIT_SECONDS, yaml_timeout, yaml_cron
    )
    result = calculate_math(
        MAX_APPLICATIONS_PER_RUN, RATE_LIMIT_SECONDS, yaml_timeout, yaml_cron
    )

    if matched_key:
        print(f"  [OK] ENGINE HEALTHY: Running on GEAR {matched_key} ({matched_gear['name']})")
        status_string = f"GEAR {matched_key} ({matched_gear['name']})"
    else:
        closest_key, closest_gear, delta = find_closest_gear_by_throughput(result['throughput'])
        diff_sign = "+" if delta >= 0 else ""
        print(f"  [~] ENGINE CUSTOM: GEAR {closest_key} ({closest_gear['name']}) - Delta: {diff_sign}{delta:.0f} emails/hr")
        status_string = f"CUSTOM (GEAR {closest_key}, Delta: {diff_sign}{delta:.0f} emails/hr)"

    if result['warnings']:
        print("  [!!!] SAFETY WARNINGS DETECTED:")
        for w in result['warnings']:
            print(f"    [X] {w}")

    print("-----------------------------------\n")
    return status_string


def get_cv_for_lead(lead):
    """Finds the CV from the DB and returns the object."""
    if lead.cv_used and lead.cv_used.cv_data:
        return lead.cv_used
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
            file_data = base64.b64decode(cv_obj.cv_data)
            msg.add_attachment(
                file_data, 
                maintype='application', 
                subtype='pdf', 
                filename=cv_obj.filename
            )
        except Exception as e:
            raise Exception(f"Failed to decode CV attachment: {e}")

    return msg


def send_summary_email(status, stats, details, start_time):
    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = _get_env('EMAIL_RECEIVER', 'RECEIVER_EMAIL')

    if not (sender and password and receiver): 
        print("  [!] Missing email credentials. Skipping report.")
        return

    end_time = timezone.now()
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

    map_text = generate_global_map(html=False)
    map_html = generate_global_map(html=True)

    body = (
        "Job Application Run Report\n"
        "=================================================================\n"
        f"Status:                  {status}\n"
        f"Mode:                    {mode}\n"
        f"Started:                 {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Finished:                {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:                {duration:.1f} seconds\n"
        "\n\n"
        "Database Snapshot\n"
        "-----------------------------------------------------------------\n"
        f"Total Candidate CVs:     {total_cvs}\n"
        f"Total Leads in Database: {total_leads}\n"
        f"Unreported Leads:        {unreported}\n"
        f"Reported, Not Applied:   {pending}\n"
        f"Already Applied:         {applied}\n"
        f"Application Logs (All):  {total_logs}\n"
        f"Successful Sends:        {success_logs}\n"
        f"Failed Sends:            {failure_logs}\n"
        "\n\n"
        "Application Statistics \n"
        "-----------------------------------------------------------------\n"
        f"Active Engine Gear:      {stats.get('gear_status', 'UNKNOWN')}\n"
        f"Batch Limit:             {MAX_APPLICATIONS_PER_RUN} CV Applications/Run\n"
        f"Leads in Queue:          {stats['queue_total']}\n"
        f"Processing This Run:     {stats['eligible']}\n"
        f"Processed:               {stats['processed']}\n"
        f"Emails Sent:             {stats['sent']}\n"
        f"Skipped (No CV):         {stats['no_cv']}\n"
        f"Failed Sends:            {stats['failed']}\n"
        f"Auto-Blacklisted:        {stats['blacklisted']}\n"
        "\n\n"
    )

    body += map_text
    body += f"\nDetails by Lead [{stats['queue_total']}]\n"
    body += "-----------------------------------------------------------------\n"

    if details:
        for d in details:
            body += f"[{d['status']:<7}] {d['email']:<40} {d['title'][:40]}\n"
            if d.get('reason'):
                body += f"           > {d['reason']}\n"
    else:
        body += "(No leads processed this run)\n"

    if stats['errors']:
        body += f"\nErrors Encountered [{len(stats['errors'])}]\n-----------------------------------------------------------------\n"
        for err in stats['errors']:
            body += f"- {err}\n"

    if stats['dry_run']:
        body += "\nNOTE: DRY RUN. No emails were actually sent.\n"
    elif stats['sent'] > 0:
        body += "\nSuccessful leads marked as APPLIED in the Database.\n"

    body += "\nThis is an automated report from Jobscr Behemoth Vacancy Mailer.\n\n\n\nPowered by ninesoftstudio"

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    
    msg.set_content(body)
    html_body = body.replace(map_text, map_html)
    msg.add_alternative(f"<div style='font-family: monospace; white-space: pre-wrap;'>{html_body}</div>", subtype='html')

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("  [+] Summary email sent.")
    except Exception as e:
        print(f"  [!] Failed to send summary email: {e}")


def apply_jobs(live=False):
    # RUN DIAGNOSTICS FIRST AND SAVE THE GEAR STATUS
    gear_status = check_engine_diagnostics()

    start_time = timezone.now()
    stats = {
        "dry_run": not live, 
        "queue_total": 0, 
        "eligible": 0, 
        "processed": 0, 
        "sent": 0, 
        "failed": 0, 
        "no_cv": 0, 
        "blacklisted": 0, 
        "errors": [],
        "gear_status": gear_status
    }
    details = []

    sender = _get_env('EMAIL_SENDER', 'EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')

    if not sender or not password: 
        print("  [!] Missing EMAIL_SENDER / EMAIL_PASSWORD. Exiting.")
        return

    # ============================================================
    # KEY CHANGE: Pick up ALL unapplied leads, NEWEST first
    # Previously: filter(is_reported=True, applied=False).order_by('found_at')
    # ============================================================
    queue_qs = JobLead.objects.filter(applied=False).order_by('-found_at')
    stats['queue_total'] = queue_qs.count()
    leads = list(queue_qs[:MAX_APPLICATIONS_PER_RUN])
    stats['eligible'] = len(leads)

    if not leads:
        print("  [-] No eligible leads to apply to.")
        send_summary_email("NO LEADS", stats, details, start_time)
        return

    print(f"  [*] {stats['queue_total']} leads in queue. Processing {stats['eligible']} this run (newest first).")

    for lead in leads:
        stats['processed'] += 1
        print(f"\n    -> Lead: {lead.email_link} ({lead.job_title[:50]})")
        
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

        try:
            msg = compose_application(sender, cv_obj, lead, candidate_name)
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)

            lead.applied = True
            lead.applied_at = timezone.now()
            lead.is_reported = True   # Auto-mark as reported since we're now processing all leads
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
            error_msg = str(e)
            print(f"       [!] Failed: {error_msg}")
            
            # --- SELF HEALING BLACKLIST LOGIC ---
            if any(code in error_msg for code in ['550', '553', '554', '501', 'invalid address']):
                domain = lead.email_link.split('@')[-1]
                print(f"       [X] Invalid address. Deleting lead and blacklisting domain: {domain}")
                
                IgnoredDomain.objects.get_or_create(
                    domain=domain, 
                    defaults={'reason': f"Invalid email address (SMTP: {error_msg[:50]})"}
                )
                stats['blacklisted'] += 1
                
                lead.delete()

                details.append({
                    "status": "DELETED", 
                    "email": lead.email_link, 
                    "title": lead.job_title, 
                    "reason": f"Invalid address. Domain {domain} blacklisted."
                })
            else:
                ApplicationLog.objects.create(
                    lead=lead, 
                    status="FAILURE", 
                    reason=error_msg[:500]
                )
                stats['failed'] += 1
                stats['errors'].append(f"{lead.email_link}: {error_msg[:100]}")
                details.append({
                    "status": "FAILED",
                    "email": lead.email_link, 
                    "title": lead.job_title, 
                    "reason": error_msg[:100]
                })

    print(f"\n  [*] Run complete. Sent: {stats['sent']}, Failed: {stats['failed']}, Skipped: {stats['no_cv']}, Blacklisted: {stats['blacklisted']}")

    if stats['dry_run']:
        status = "DRY RUN"
    elif stats['eligible'] == 0:
        status = "NO LEADS"
    elif not stats['errors'] and stats['sent'] > 0:
        status = "SUCCESS"
    elif stats['sent'] > 0 or stats['no_cv'] > 0 or stats['blacklisted'] > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"

    send_summary_email(status, stats, details, start_time)


if __name__ == "__main__":
    live = '--live' in sys.argv
    apply_jobs(live=live)