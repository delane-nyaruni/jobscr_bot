import os
from pathlib import Path
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.mysql.features import DatabaseFeatures
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent



# We create a dummy function that does nothing
def ignore_version_check(__self__):
    pass

# We replace Django's internal version check with our dummy function
BaseDatabaseWrapper.check_database_version_supported = ignore_version_check


# 1. Skip the version check (The code we already added)
def skip_check(__self__):
    pass
BaseDatabaseWrapper.check_database_version_supported = skip_check

# # 2. Disable the "RETURNING" feature that is breaking MariaDB 10.4
def patched_can_return_rows(__self__):
    return False

DatabaseFeatures.can_return_columns_from_insert = property(lambda self: False)
DatabaseFeatures.can_return_rows_from_bulk_insert = property(lambda self: False)


SECRET_KEY = '!8&$#b_&!5wp$#(621b-(#0sy*b4t@q6s+8+qnc!#t_17md-m_'

# <-- 4. Fetch DEBUG from .env. (os.getenv returns a string, so we check if it equals 'True') -->
DEBUG = False


# Application definition

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api',
    'rest_framework_simplejwt',
    'users',
    # 'mail',
    'rest_framework',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.environ.get("EMAIL_USER")
# EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_PASSWORD")
# DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
# RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dfms_backend.urls'

TEMPLATES: list[dict[str, str | bool | list | dict]] = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]




WSGI_APPLICATION = 'dfms_backend.wsgi.application'

# CLOUD  DB CONN

# mysql

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'defaultdb',
        'USER': 'avnadmin',
        'PASSWORD': 'os.environ.get('MYSQL_DB_PASSWORD')',
        'HOST': 'mysql-3ed8e01d-delaneoncodes-6fbe.b.aivencloud.com',
        'PORT': '12904',  
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# postgresdb

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'defaultdb',        
#         'USER': 'avnadmin',    
#         'PASSWORD': '', 
#         'HOST': 'pg-142e1b4-delaneoncodes-6fbe.k.aivencloud.com',
#         'PORT': '12904',        
#     }
# }

# <-- Local DB Connection-->
# postgresdb

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'dfms',       
#         'USER': 'postgres',    
#         'PASSWORD': 'root', 
#         'HOST': 'localhost',
#         'PORT': '5432',        
#     }
# }


# mysqldb

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'jobscr',
#         'USER': 'root',
#         'PASSWORD': '',
#         'HOST': 'localhost',
#         'PORT': 3306,
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
        
#     }
# }


# Password validation
# Use JWT for authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}
SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('JWT',), #  'Bearer' to 'JWT'
}
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# production ready settings
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# 2. Configure Static Files for Production
STATIC_URL = '/static/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# 3. Enable compression and caching (optional but recommended)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.100.12:54114",
    "http://192.168.43.12:54114",
    "https://mdfms.netlify.app",
    "http://localhost:54114",
    "http://192.168.245.128:54114",
]

CORS_ALLOW_ALL_ORIGINS = True
ALLOWED_HOSTS = [
                  '*',
                'https://dfms-backend-t05z.onrender.com',
                 '127.0.0.1',
                 'localhost',
                 '192.168.100.12',
                 '0.0.0.0',
                 '192.168.43.12',
                 ' http://localhost:54114',
                 ]
