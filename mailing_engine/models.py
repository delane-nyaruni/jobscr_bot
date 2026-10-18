from django.db import models
from scrapping_engine.models import JobLead

class ApplicationLog(models.Model):
    """Result of one send attempt against a JobLead."""
    STATUS_CHOICES = [("SUCCESS", "Success"), ("FAILURE", "Failure")]

    lead = models.ForeignKey(JobLead, on_delete=models.CASCADE, related_name="application_logs")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    reason = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.lead.email_link} - {self.status}"