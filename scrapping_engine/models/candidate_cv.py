from django.db import models


class CandidateCV(models.Model):
    """Stores the CVs uploaded by the user. Extracts the target role for scraping."""
    filename = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    target_role = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Candidate CV"
        verbose_name_plural = "Candidate CVs"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.full_name} - {self.target_role}"