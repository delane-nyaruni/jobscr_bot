import os
from django.contrib import admin
from .models import JobBoard, CandidateCV, IgnoredDomain, JobLead
from utilities.cv_utils import parse_cv_filename


@admin.register(JobBoard)
class JobBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'country', 'is_active')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'url')


@admin.register(CandidateCV)
class CandidateCVAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'target_role', 'filename', 'uploaded_at')
    search_fields = ('full_name', 'target_role')
    
    # Make these read-only so you don't have to type them manually.
    # The system will fill them automatically when you upload the file.
    readonly_fields = ('filename', 'full_name', 'target_role')

    def save_model(self, request, obj, form, change):
        """Automatically parse the filename when a CV is uploaded."""
        if obj.cv_file:
            base_name = os.path.basename(obj.cv_file.name)
            
            # Extract the name and role from the file (e.g., Delane_Nyaruni_Software_Engineer_CV.pdf)
            if not obj.filename or 'cv_file' in form.changed_data:
                name, role = parse_cv_filename(base_name)
                
                obj.filename = base_name
                obj.full_name = name if name else "Unknown Name"
                obj.target_role = role if role else "Unknown Role"
                    
        super().save_model(request, obj, form, change)


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