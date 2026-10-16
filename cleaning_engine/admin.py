from django.contrib import admin
from .models import MailCleanupTarget, CleanupRun


@admin.register(MailCleanupTarget)
class MailCleanupTargetAdmin(admin.ModelAdmin):
    list_display = ('email', 'reason', 'added_at')
    search_fields = ('email', 'reason')


@admin.register(CleanupRun)
class CleanupRunAdmin(admin.ModelAdmin):
    list_display = ('ran_at', 'total_deleted')
    readonly_fields = ('ran_at', 'total_deleted', 'detail')