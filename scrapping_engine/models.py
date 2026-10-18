from django.db import models

class JobBoard(models.Model):
    """Sites the scraper crawls for job postings."""
    name = models.CharField(max_length=255, default="Unknown Board")
    url = models.URLField(unique=True)
    country = models.CharField(max_length=100, default="Zimbabwe")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.country})"


class CandidateCV(models.Model):
    """Stores CVs as Base64 to survive Render's ephemeral disk."""
    cv_data = models.TextField(blank=True, null=True, help_text="Internal Base64 storage")
    filename = models.CharField(max_length=255, unique=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    target_role = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.full_name} - {self.target_role}"


class IgnoredDomain(models.Model):
    """Email domains excluded from scraped results."""
    domain = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ['domain']

    def __str__(self):
        return self.domain


class JobLead(models.Model):
    """A recruiter/hiring-manager email found on a job posting."""
    cv_used = models.ForeignKey(CandidateCV, on_delete=models.SET_NULL, null=True, blank=True, related_name="job_leads")
    job_board = models.ForeignKey(JobBoard, on_delete=models.CASCADE, related_name="job_leads")
    cv_career = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255, blank=True, default="N/A")
    job_url = models.URLField()
    email_link = models.EmailField()
    job_type = models.CharField(max_length=100, blank=True, default="Remote/Full-time")
    country = models.CharField(max_length=100, default="Zimbabwe")
    found_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    is_reported = models.BooleanField(default=False)

    class Meta:
        unique_together = ("job_url", "email_link")
        indexes = [
            models.Index(fields=["applied"]),
            models.Index(fields=["is_reported"]),
            models.Index(fields=["found_at"]),
            models.Index(fields=["country"]),
        ]
        ordering = ['-found_at']

    def __str__(self):
        return f"{self.email_link} - {self.job_title}"