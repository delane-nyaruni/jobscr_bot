from django.urls import path
from .views import  CurrentUserView

urlpatterns = [
    path('scrapping_engine/', CurrentUserView.as_view(), name='scrapping_engine'),
]