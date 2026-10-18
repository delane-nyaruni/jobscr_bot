import os
import base64
from django import forms
from django.contrib import admin
from .models import JobBoard, CandidateCV, IgnoredDomain, JobLead
from utilities.cv_utils import parse_cv_filename

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