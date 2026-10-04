from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
   
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(max_length=254,unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    class Meta:
        # This forces Django to use your specific table name
        db_table = 'auth_user'

    def __str__(self):
        return self.username