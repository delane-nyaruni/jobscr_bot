from django.contrib import admin
from .models import JobBoard, CandidateCV, IgnoredDomain, JobLead


@admin.register(JobBoard)
class JobBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'country', 'is_active')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'url')


@admin.register(CandidateCV)
class CandidateCVAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'target_role', 'filename', 'uploaded_at')
    search_fields = ('full_name', 'target_role')


@admin.register(IgnoredDomain)
class IgnoredDomainAdmin(admin.ModelAdmin):
    list_display = ('domain',)
    search_fields = ('domain',)


@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = ('email_link', 'job_board', 'cv_career', 'job_title', 'found_at', 'is_reported', 'applied')
    list_filter = ('is_reported', 'applied', 'job_board', 'country')
    search_fields = ('email_link', 'job_title', 'cv_career')
    readonly_fields = ('found_at',)