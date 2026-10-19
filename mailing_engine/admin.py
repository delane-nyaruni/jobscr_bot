from django.contrib import admin
from .models import ApplicationLog

@admin.action(description="Retry selected FAILED applications (resets leads)")
def retry_failed_applications(modeladmin, request, queryset):
    # Only process logs that actually failed
    failed_logs = queryset.filter(status="FAILURE")
    count = 0
    for log in failed_logs:
        lead = log.lead
        # Reset the lead so the mailer picks it up again
        lead.applied = False
        lead.applied_at = None
        lead.save()
        count += 1
        
    modeladmin.message_user(request, f"{count} failed leads have been reset and are ready for the next Mailer run.")

@admin.register(ApplicationLog)
class ApplicationLogAdmin(admin.ModelAdmin):
    list_display = ('lead', 'status', 'sent_at')
    list_filter = ('status', 'sent_at')
    search_fields = ('lead__email_link', 'reason')
    readonly_fields = ('sent_at',)
    
    # Add the custom action to the dropdown
    actions = [retry_failed_applications]