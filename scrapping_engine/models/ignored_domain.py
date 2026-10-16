from django.db import models


class IgnoredDomain(models.Model):
    """Email domains excluded from scraped results."""
    domain = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Ignored Domain"
        verbose_name_plural = "Ignored Domains"
        ordering = ['domain']

    def __str__(self):
        return self.domain