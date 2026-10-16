from django.contrib import admin
from .models import ApplicationLog


@admin.register(ApplicationLog)
class ApplicationLogAdmin(admin.ModelAdmin):
    list_display = ('lead', 'status', 'sent_at')
    list_filter = ('status', 'sent_at')
    search_fields = ('lead__email_link', 'reason')
    readonly_fields = ('sent_at',)