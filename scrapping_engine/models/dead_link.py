from django.db import models


class DeadLink(models.Model):
    """URLs confirmed dead. Spiders skip these to save time."""
    url = models.URLField(unique=True)
    domain = models.CharField(max_length=255, db_index=True)
    reason = models.CharField(max_length=255, blank=True, help_text="HTTP 404, DNS Error, etc.")
    detected_at = models.DateTimeField(auto_now_add=True)
    last_retry = models.DateTimeField(auto_now=True)
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-detected_at']
        verbose_name = "Dead Link"
        verbose_name_plural = "Dead Links"
        indexes = [models.Index(fields=['domain'])]

    def __str__(self):
        return f"{self.domain} - {self.reason}"