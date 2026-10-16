from django.db import models


class JobBoard(models.Model):
    """Sites the scraper crawls for job postings."""
    name = models.CharField(max_length=255, default="Unknown Board")
    url = models.URLField(unique=True)
    country = models.CharField(max_length=100, default="Zimbabwe")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Job Board"
        verbose_name_plural = "Job Boards"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.country})"