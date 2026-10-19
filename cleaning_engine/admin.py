from django.contrib import admin
from .models import MailCleanupTarget, CleanupRun


@admin.register(MailCleanupTarget)
class MailCleanupTargetAdmin(admin.ModelAdmin):
    list_display = ('email', 'reason', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('email', 'reason')
    readonly_fields = ('added_at',)


@admin.register(CleanupRun)
class CleanupRunAdmin(admin.ModelAdmin):
    list_display = ('ran_at', 'total_deleted')
    list_filter = ('ran_at',)
    date_hierarchy = 'ran_at'
    readonly_fields = ('ran_at', 'total_deleted', 'detail')