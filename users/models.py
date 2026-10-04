from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    # Links to the built-in User
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    farm_id = models.CharField(max_length=50, default="DFMS-2026")
    role = models.CharField(max_length=20, choices=[('admin', 'Admin'), ('staff', 'Staff')], default='staff')

    class Meta:
        db_table = 'user_profile' 
        
    def __str__(self):
        return f"{self.user}'s Profile"