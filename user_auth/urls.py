from django.urls import path
from .views import  CurrentUserView

urlpatterns = [
    # Returns the current user's profile data (username, member_level, etc.)
    path('me/', CurrentUserView.as_view(), name='current_user'),
]