from django.db import models

class MailCleanupTarget(models.Model):
    """Sender addresses whose mail should be trashed from the inbox."""
    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['email']

    def __str__(self):
        return self.email


class CleanupRun(models.Model):
    """One run of the mailbox cleanup command."""
    ran_at = models.DateTimeField(auto_now_add=True)
    total_deleted = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ['-ran_at']

    def __str__(self):
        return f"Cleanup {self.ran_at:%Y-%m-%d} - {self.total_deleted} deleted"