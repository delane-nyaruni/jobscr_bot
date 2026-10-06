# jobs/models.py
from django.db import models

class JobBoard(models.Model):
    """Sites the scraper crawls for job postings. Replaces leadsDB/job_leads.json['target_boards']."""
    name = models.CharField(max_length=255, default="Unknown Board") # Added
    url = models.URLField(unique=True)
    country = models.CharField(max_length=100, default="Zimbabwe") # Added
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.country})"


class CandidateCV(models.Model):
    """Stores the CVs uploaded by the user. Extracts the target role for scraping."""
    filename = models.CharField(max_length=255, unique=True) # e.g., Delane_Nyaruni_Software_Engineer_CV.pdf
    full_name = models.CharField(max_length=255)
    target_role = models.CharField(max_length=255) # e.g., Software Engineer
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.target_role}"


class IgnoredDomain(models.Model):
    """Email domains excluded from scraped results. Replaces leadsDB/job_leads.json['ignored_domains']."""
    domain = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.domain


class JobLead(models.Model):
    """A recruiter/hiring-manager email found on a job posting. Replaces csv/job_recipients.csv."""
    
    # Link to the CV used to find this lead
    cv_used = models.ForeignKey(CandidateCV, on_delete=models.SET_NULL, null=True, blank=True, related_name="job_leads")
    
    # Link to the Job Board
    job_board = models.ForeignKey(JobBoard, on_delete=models.CASCADE, related_name="job_leads")
    
    # The specific role we searched for (extracted from CV)
    cv_career = models.CharField(max_length=255) 
    
    # Details of the specific job posting
    job_title = models.CharField(max_length=255, blank=True, default="N/A")
    job_url = models.URLField() # Added
    email_link = models.EmailField() # Renamed from 'email' as per your request
    job_type = models.CharField(max_length=100, blank=True, default="Remote/Full-time")
    country = models.CharField(max_length=100, default="Zimbabwe")
    
    found_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Prevent scraping the same email from the exact same job posting multiple times
        unique_together = ("job_url", "email_link")
        indexes = [models.Index(fields=["applied"])]

    def __str__(self):
        return f"{self.email_link} - {self.job_title}"


class ApplicationLog(models.Model):
    """Result of one send attempt against a JobLead. Replaces bot_result.csv."""
    STATUS_CHOICES = [("SUCCESS", "Success"), ("FAILURE", "Failure")]

    lead = models.ForeignKey(JobLead, on_delete=models.CASCADE, related_name="application_logs")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    reason = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.email_link} - {self.status}"


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