
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('', include("rest_framework.urls")),
    path('admin/', admin.site.urls),
    # path('scrapping_engine/', include('scrapping_engine.urls')),  
   ]