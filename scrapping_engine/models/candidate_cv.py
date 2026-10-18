from django.db import models

class CandidateCV(models.Model):
    """Stores the CVs uploaded by the user. Extracts the target role for scraping."""
    
    # The actual file upload field
    cv_file = models.FileField(
        upload_to='docs/cv/', 
        help_text="Upload your CV. Format: Name_Surname_Role_CV.pdf"
    )
    
    # These will be auto-filled by the admin panel
    filename = models.CharField(max_length=255, unique=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    target_role = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.target_role}"