from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializer import UserRegisterSerializer, MyTokenObtainPairSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .models import UserProfile

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        try:
            # Decode the user ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            # Check if the token is valid for this specific user
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({'Status': 'Success'}, status=status.HTTP_200_OK)
            else:
                return Response({'Status': 'Error', 'Message': 'Invalid Token'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'Status': 'Error', 'Message': 'Invalid User'}, status=status.HTTP_400_BAD_REQUEST)
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': 'Success'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def user_register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    # 1. Check if Username exists
    if User.objects.filter(username=username).exists():
        return Response({'username': ['This username is already taken.']}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Check if Email exists (This fixes your "Email not working" issue)
    if User.objects.filter(email=email).exists():
        return Response({'email': ['This email is already registered.']}, status=status.HTTP_400_BAD_REQUEST)

    # 3. Create User
    try:
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        return Response({'message': 'User created successfully'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            # Security tokens for the reset link
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Replace localhost with your production domain later
            reset_link = f"http://localhost:8000/api/users/user_forgot/{uid}/{token}/"
            
            send_mail(
                'DFMS Password Reset',
                f'Please use the following link to reset your password: {reset_link}',
                'lusnerdelane@gmail.com',
                [email],
                fail_silently=False,
            )
            return Response({'Status': 'Success'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            # We return Success even if email doesn't exist for security (anti-enumeration)
            # but your React logic can handle it as needed.
            return Response({'Status': 'Success'}, status=status.HTTP_200_OK)

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    
class DeleteUserAccount(APIView):
    # This ensures only the logged-in user can delete their own account
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete() # This triggers the MySQL 'DELETE' command automatically
        return Response({"message": "Account deleted"}, status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    """
    Returns the logged-in user's profile info for pages like ManageUserAccount.
    Requires a valid JWT in the Authorization header (same auth as DeleteUserAccount).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # get_or_create in case a user (e.g. one made via createsuperuser) has no
        # UserProfile row yet — avoids a 500 from UserProfile.DoesNotExist
        profile, _ = UserProfile.objects.get_or_create(user=user)

        member_level = 'Admin' if user.is_superuser else profile.get_role_display()

        return Response({
            'username': user.username,
            'email': user.email,
            'is_superuser': user.is_superuser,
            'member_level': member_level,
            'farm_id': profile.farm_id,
        }, status=status.HTTP_200_OK)