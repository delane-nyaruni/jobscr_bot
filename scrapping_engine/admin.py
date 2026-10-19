import os
import base64
from django import forms
from django.contrib import admin
from .models import JobBoard, CandidateCV, IgnoredDomain, JobLead, DeadLink
from utilities.cv_utils import parse_cv_filename


# ==========================================
# 1. JOB BOARD BULK ACTIONS
# ==========================================
@admin.action(description="Activate selected job boards")
def activate_boards(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"{updated} job boards successfully activated.")

@admin.action(description="Deactivate selected job boards")
def deactivate_boards(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} job boards successfully deactivated.")


# ==========================================
# 2. JOB LEAD BULK ACTIONS
# ==========================================
@admin.action(description="Mark leads for Mailer")
def mark_as_reported(modeladmin, request, queryset):
    updated = queryset.update(is_reported=True)
    modeladmin.message_user(request, f"{updated} leads successfully marked as REPORTED.")

@admin.action(description="Mark leads as APPLIED")
def mark_as_applied(modeladmin, request, queryset):
    updated = queryset.update(applied=True)
    modeladmin.message_user(request, f"{updated} leads successfully marked as APPLIED.")

@admin.action(description="Reset leads to UNREPORTED")
def reset_to_unreported(modeladmin, request, queryset):
    updated = queryset.update(is_reported=False, applied=False)
    modeladmin.message_user(request, f"{updated} leads reset to UNREPORTED and UNAPPLIED.")


# ==========================================
# 3. CUSTOM CV UPLOAD FORM
# ==========================================
class CandidateCVForm(forms.ModelForm):
    cv_upload = forms.FileField(
        required=True, 
        help_text="Upload a PDF (e.g., Delane_Nyaruni_Software_Engineer_CV.pdf)"
    )

    class Meta:
        model = CandidateCV
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_file = self.cleaned_data.get('cv_upload')

        if uploaded_file:
            file_content = uploaded_file.read()
            instance.cv_data = base64.b64encode(file_content).decode('utf-8')
            filename = os.path.basename(uploaded_file.name)
            instance.filename = filename
            name, role = parse_cv_filename(filename)
            instance.full_name = name if name else "Unknown Name"
            instance.target_role = role if role else "Unknown Role"

        if commit:
            instance.save()
        return instance


# ==========================================
# 4. REGISTER ADMINS
# ==========================================
@admin.register(CandidateCV)
class CandidateCVAdmin(admin.ModelAdmin):
    form = CandidateCVForm
    list_display = ('full_name', 'target_role', 'filename', 'uploaded_at')
    exclude = ('cv_data',)
    readonly_fields = ('filename', 'full_name', 'target_role')

    def get_fields(self, request, obj=None):
        if not obj:
            return ('cv_upload',)
        return ('filename', 'full_name', 'target_role', 'uploaded_at')


@admin.register(JobBoard)
class JobBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'country', 'is_active')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'url')
    actions = [activate_boards, deactivate_boards]


@admin.register(IgnoredDomain)
class IgnoredDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'reason', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('domain', 'reason')
    readonly_fields = ('added_at',)


@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = ('email_link', 'job_board', 'cv_career', 'job_title', 'found_at', 'is_reported', 'applied')
    list_filter = ('is_reported', 'applied', 'job_board', 'country')
    search_fields = ('email_link', 'job_title', 'cv_career')
    readonly_fields = ('found_at',)
    actions = [mark_as_reported, mark_as_applied, reset_to_unreported]


# ==========================================
# 5. DEAD LINK ADMIN
# ==========================================
@admin.register(DeadLink)
class DeadLinkAdmin(admin.ModelAdmin):
    list_display = ('domain', 'reason', 'detected_at', 'last_retry', 'retry_count')
    list_filter = ('detected_at',)
    search_fields = ('domain', 'url', 'reason')
    readonly_fields = ('detected_at', 'last_retry', 'retry_count')