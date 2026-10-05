"""
Replaces email_auto_bot.py.

Sends the CV to every JobLead not yet marked applied, logs each attempt
as an ApplicationLog row instead of bot_result.csv, then emails a short
summary instead of attaching the CSV log.

Run with: python manage.py send_applications
"""
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from leads.models import ApplicationLog, JobLead

CV_PATH = Path(settings.BASE_DIR) / "static" / "cv" / "Delane_Nyaruni_ICT_Specialist_CV.pdf"
APPLICATION_SUBJECT = "Job Application - Experienced ICT Specialist"
APPLICATION_BODY = (
    "Dear Hiring Manager,\n\n"
    "Please find attached my CV... "
    "Portfolio: https://delane-nyaruni.github.io"
)


class Command(BaseCommand):
    help = "Email the CV to every job lead that hasn't been applied to yet."

    def handle(self, *args, **options):
        pending = JobLead.objects.filter(applied=False)
        if not pending.exists():
            self.stdout.write("No new leads to email.")
            return

        sent_count = 0
        for lead in pending:
            msg = EmailMessage(subject=APPLICATION_SUBJECT, body=APPLICATION_BODY, to=[lead.email])
            if CV_PATH.exists():
                msg.attach_file(str(CV_PATH))

            try:
                msg.send()
                ApplicationLog.objects.create(lead=lead, status="SUCCESS", reason="Sent")
                lead.applied = True
                lead.applied_at = timezone.now()
                lead.save(update_fields=["applied", "applied_at"])
                sent_count += 1
            except Exception as exc:
                ApplicationLog.objects.create(lead=lead, status="FAILURE", reason=str(exc))

        self._send_admin_summary(sent_count)

    def _send_admin_summary(self, sent_count):
        receiver = getattr(settings, "RECEIVER_EMAIL", None)
        if not receiver:
            return
        subject = f"Bot Log: {sent_count} Applications Sent Successfully"
        body = f"Automation process completed. Successfully applied to {sent_count} companies today."
        EmailMessage(subject, body, to=[receiver]).send(fail_silently=True)