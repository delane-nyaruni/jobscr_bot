from django.db import models
from .candidate_cv import CandidateCV
from .job_board import JobBoard


class JobLead(models.Model):
    """A recruiter/hiring-manager email found on a job posting."""

    cv_used = models.ForeignKey(
        CandidateCV,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_leads"
    )
    job_board = models.ForeignKey(
        JobBoard,
        on_delete=models.CASCADE,
        related_name="job_leads"
    )
    cv_career = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255, blank=True, default="N/A")
    job_url = models.URLField()
    email_link = models.EmailField()
    job_type = models.CharField(max_length=100, blank=True, default="Remote/Full-time")
    country = models.CharField(max_length=100, default="Zimbabwe")

    found_at = models.DateTimeField(auto_now_add=True)
    is_reported = models.BooleanField(default=False)
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Job Lead"
        verbose_name_plural = "Job Leads"
        unique_together = ("job_url", "email_link")
        indexes = [
            models.Index(fields=["applied"]),
            models.Index(fields=["is_reported"]),
            models.Index(fields=["found_at"]),
        ]
        ordering = ['-found_at']

    def __str__(self):
        return f"{self.email_link} - {self.job_title}"