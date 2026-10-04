from django.urls import path
from .views import DeleteUserAccount, RegisterView, ForgotPasswordView, MyTokenObtainPairView, PasswordResetConfirmView, CurrentUserView

urlpatterns = [
    # Matches React: /api/users/user_register/
    path('user_register/', RegisterView.as_view(), name='user_register'),
    
    path('password_reset_confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # Matches React: /api/users/user_forgot/
    path('user_forgot/', ForgotPasswordView.as_view(), name='user_forgot'),
    
    # Matches React Login
    path('user_login/', MyTokenObtainPairView.as_view(), name='user_login'),

    path('delete/', DeleteUserAccount.as_view(), name='delete'),
    
    # Returns the current user's profile data (username, member_level, etc.)
    path('me/', CurrentUserView.as_view(), name='current_user'),
]