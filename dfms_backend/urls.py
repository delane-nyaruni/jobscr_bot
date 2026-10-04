
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('', include("rest_framework.urls")),
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    # path('api/mail/', include('mail.urls')),  
    path('api/users/me/', include('users.urls')),  
   ]