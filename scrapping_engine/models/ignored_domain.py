from django.db import models


class IgnoredDomain(models.Model):
    """Email domains or boards excluded from scraped results."""
    domain = models.CharField(max_length=255, unique=True)
    reason = models.CharField(max_length=255, blank=True, help_text="Why was this domain blacklisted?")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ignored Domain"
        verbose_name_plural = "Ignored Domains"
        ordering = ['domain']

    def __str__(self):
        return f"{self.domain} ({self.reason})" if self.reason else self.domain