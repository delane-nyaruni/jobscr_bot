from django.urls import path
from .views import  CurrentUserView

urlpatterns = [
    # Returns the current user's profile data (username, member_level, etc.)
    path('scrapping_engine/', CurrentUserView.as_view(), name='scrapping_engine'),
]