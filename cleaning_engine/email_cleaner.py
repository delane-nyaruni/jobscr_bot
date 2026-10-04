
import imaplib

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from leads.models import CleanupRun, MailCleanupTarget

IMAP_SERVER = "imap.gmail.com"


class Command(BaseCommand):
    help = "Delete inbox mail from addresses flagged in MailCleanupTarget."

    def handle(self, *args, **options):
        targets = list(MailCleanupTarget.objects.values_list("email", flat=True))
        if not targets:
            self.stdout.write("No cleanup targets configured.")
            return

        email_user = getattr(settings, "EMAIL_HOST_USER", None)
        email_password = getattr(settings, "EMAIL_HOST_PASSWORD", None)
        if not email_user or not email_password:
            self.stderr.write("Mailbox credentials missing (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD).")
            return

        total_deleted = 0
        detail_lines = []

        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(email_user, email_password)
            mail.select('"[Gmail]/All Mail"')

            for target in targets:
                status, messages = mail.search(None, f'(FROM "{target}")')
                count = 0
                if status == "OK" and messages[0]:
                    mail_ids = messages[0].split()
                    count = len(mail_ids)
                    for m_id in mail_ids:
                        mail.copy(m_id, '"[Gmail]/Trash"')
                        mail.store(m_id, "+FLAGS", "\\Deleted")
                    total_deleted += count
                detail_lines.append(f"- {target}: {count} emails")

            mail.expunge()
            mail.logout()
        except Exception as exc:
            self.stderr.write(f"Cleanup failed: {exc}")
            return

        detail = "\n".join(detail_lines)
        CleanupRun.objects.create(total_deleted=total_deleted, detail=detail)

        if total_deleted > 0:
            self._send_summary(total_deleted, detail)
        else:
            self.stdout.write("Nothing deleted. No report sent.")

    def _send_summary(self, total_count, detailed_log):
        receiver = getattr(settings, "RECEIVER_EMAIL", None)
        if not receiver:
            return
        subject = f"Cleanup Report: {timezone.now():%Y-%m-%d}"
        body = (
            "Email Cleanup Automation Summary\n"
            "---------------------------------------------\n"
            f"Status: SUCCESS\n"
            f"Total Deleted: {total_count}\n"
            f"Date: {timezone.now():%Y-%m-%d %H:%M:%S}\n\n"
            f"Details by sender:\n{detailed_log}\n\n"
            "This is an automated report from GitHub Actions."
        )
        EmailMessage(subject, body, to=[receiver]).send(fail_silently=True)