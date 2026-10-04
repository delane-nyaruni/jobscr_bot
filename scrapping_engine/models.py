from django.db import models

class JobBoard(models.Model):
    """Sites the scraper crawls for job postings. Replaces leadsDB/job_leads.json['target_boards']."""

    url = models.URLField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.url


class IgnoredDomain(models.Model):
    """Email domains excluded from scraped results. Replaces leadsDB/job_leads.json['ignored_domains']."""

    domain = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.domain


class JobLead(models.Model):
    """A recruiter/hiring-manager email found on a job posting. Replaces csv/job_recipients.csv."""

    email = models.EmailField()
    job_board = models.URLField()
    job_title = models.CharField(max_length=255, blank=True, default="N/A")
    job_type = models.CharField(max_length=100, blank=True, default="N/A")
    found_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("email", "job_board")
        indexes = [models.Index(fields=["applied"])]

    def __str__(self):
        return f"{self.email} ({self.job_board})"


class ApplicationLog(models.Model):
    """Result of one send attempt against a JobLead. Replaces bot_result.csv."""

    STATUS_CHOICES = [("SUCCESS", "Success"), ("FAILURE", "Failure")]

    lead = models.ForeignKey(JobLead, on_delete=models.CASCADE, related_name="application_logs")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    reason = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.email} - {self.status}"


class MailCleanupTarget(models.Model):
    """Sender addresses whose mail should be trashed from the inbox. Replaces csv/dirty_mail.csv."""

    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class CleanupRun(models.Model):
    """One run of the mailbox cleanup command."""

    ran_at = models.DateTimeField(auto_now_add=True)
    total_deleted = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)

    def __str__(self):
        return f"Cleanup {self.ran_at:%Y-%m-%d} - {self.total_deleted} deleted"