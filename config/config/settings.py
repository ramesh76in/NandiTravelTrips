"""
Django settings for Nandi Travel Trips project.
"""
import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BASE_DIR.parent

# Add workspace root to sys.path to allow clean imports from backend package
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Load .env file automatically if present
env_path = WORKSPACE_ROOT / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if '#' in val and not (val.startswith('"') or val.startswith("'")):
                    val = val.split('#')[0].strip()
                val = val.strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-eyn^$21k*fzkmis&^b$1r%-c#mik(b=rd0teo4u(nlt2g)9+$a'
)

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,*').split(',')

# GDS & Flight Aggregator Configuration
GDS_PROVIDER = os.environ.get('GDS_PROVIDER', 'auto').strip().lower()

# Travelport TripServices / Universal API Settings
TRAVELPORT_USERNAME = os.environ.get('TRAVELPORT_USERNAME', '').strip()
TRAVELPORT_PASSWORD = os.environ.get('TRAVELPORT_PASSWORD', '').strip()
TRAVELPORT_TARGET_BRANCH = os.environ.get('TRAVELPORT_TARGET_BRANCH', '').strip()
TRAVELPORT_ENV = os.environ.get('TRAVELPORT_ENV', 'test').strip()

# Amadeus API Configuration
AMADEUS_CLIENT_ID = os.environ.get('AMADEUS_CLIENT_ID', '').strip()
AMADEUS_CLIENT_SECRET = os.environ.get('AMADEUS_CLIENT_SECRET', '').strip()
AMADEUS_ENV = os.environ.get('AMADEUS_ENV', 'test').strip()

# Travelopro Flight API Configuration (documented AeroVE5 API)
TRAVELOPRO_USER_ID = os.environ.get('TRAVELOPRO_USER_ID', '').strip()
TRAVELOPRO_USER_PASSWORD = os.environ.get('TRAVELOPRO_USER_PASSWORD', '').strip()
TRAVELOPRO_ACCESS = os.environ.get('TRAVELOPRO_ACCESS', 'Test').strip()
TRAVELOPRO_IP_MODE = os.environ.get('TRAVELOPRO_IP_MODE', 'manual').strip().lower()
TRAVELOPRO_IP_ADDRESS = os.environ.get('TRAVELOPRO_IP_ADDRESS', '').strip()
TRAVELOPRO_BASE_URL = os.environ.get('TRAVELOPRO_BASE_URL', 'https://travelnext.works/api/aeroVE5').strip().rstrip('/')
TRAVELOPRO_TIMEOUT = int(os.environ.get('TRAVELOPRO_TIMEOUT', '30'))
TRAVELOPRO_ENV = os.environ.get('TRAVELOPRO_ENV', 'test').strip()

LOG_DIR = WORKSPACE_ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'detailed': {'format': '{asctime} | {levelname} | {name} | {message}', 'style': '{'}},
    'handlers': {
        'travelopro_file': {'class': 'logging.FileHandler', 'filename': str(LOG_DIR / 'travelopro_api.log'), 'formatter': 'detailed', 'encoding': 'utf-8'},
        'nandi_file': {'class': 'logging.FileHandler', 'filename': str(LOG_DIR / 'nandi_flights.log'), 'formatter': 'detailed', 'encoding': 'utf-8'},
    },
    'loggers': {
        'travelopro.api': {'handlers': ['travelopro_file'], 'level': 'INFO', 'propagate': False},
        'nandi.flight': {'handlers': ['nandi_file'], 'level': 'INFO', 'propagate': False},
    },
}

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Flight-search cache. FileBasedCache keeps live search offers out of the
# Django session/database and works locally without requiring Redis.
FLIGHT_SEARCH_CACHE_TTL = int(os.environ.get('FLIGHT_SEARCH_CACHE_TTL', '120'))
FLIGHT_SEARCH_LOCK_TTL = int(os.environ.get('FLIGHT_SEARCH_LOCK_TTL', '300'))
TRAVELOPRO_MULTIPLE_BRANDED_FARES = os.environ.get('TRAVELOPRO_MULTIPLE_BRANDED_FARES', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(WORKSPACE_ROOT / '.django_cache'),
        'TIMEOUT': FLIGHT_SEARCH_CACHE_TTL,
        'OPTIONS': {'MAX_ENTRIES': 2000},
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
