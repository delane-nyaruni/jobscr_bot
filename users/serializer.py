from django.contrib.auth.models import User
from rest_framework import serializers
from django.db import transaction
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UserProfile

class UserRegisterSerializer(serializers.ModelSerializer):
    # Field for the profile role, defaults to staff
    role = serializers.CharField(write_only=True, required=False, default='staff')

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def create(self, validated_data):
        # Extract role before creating the user
        role = validated_data.pop('role', 'staff')
        
        with transaction.atomic():
            # Create User with hashed password
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password']
            )
            
            # Automatically create the UserProfile
            UserProfile.objects.create(
                user=user,
                role=role,
                farm_id="DFMS-2026"
            )
            
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add the custom 'role' to the JWT token for React routing
        try:
            token['role'] = user.userprofile.role
        except UserProfile.DoesNotExist:
            token['role'] = 'staff'
        return token