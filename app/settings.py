"""
Django settings for app project.

Generated by 'django-admin startproject' using Django 4.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""

from pathlib import Path
import environ

env = environ.Env(
    GRAVIS_VERSION=(str, "DEV"),
    DEBUG=(bool, False),
    APPLIANCE_NAME=(str, "master"),
    DATA_FOLDER=(str, "/opt/gravis/data"),
    INCOMING_FOLDER=(str, "/opt/gravis/data/incoming"),
    CASES_FOLDER=(str, "/opt/gravis/data/cases"),
    ERROR_FOLDER=(str, "/opt/gravis/data/error"),
    INCOMING_SCAN_INTERVAL=(int, 1),
    DB_BACKEND=(str, "postgres"),   
    DB_USER=(str, "gravis"),
    TEST_FOLDER_PATH = (str, "/tmp")    
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(BASE_DIR / "gravis.env")
environ.Env.read_env(BASE_DIR / "local.env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-r$afdbw+6xgz#af8-e2z=#@kjs2r#$th^m=60v1&almulq5fuh"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")
APPLIANCE_NAME = env("APPLIANCE_NAME")
DATA_FOLDER = env("DATA_FOLDER")
INCOMING_FOLDER = env("INCOMING_FOLDER")
CASES_FOLDER = env("CASES_FOLDER")
ERROR_FOLDER = env("ERROR_FOLDER")
INCOMING_SCAN_INTERVAL = env("INCOMING_SCAN_INTERVAL")
TEST_FOLDER_PATH = env("TEST_FOLDER_PATH")
GRAVIS_VERSION=env("GRAVIS_VERSION")

MEDIA_URL = "media/"
MEDIA_ROOT = DATA_FOLDER
STATIC_URL = "static/"
STATIC_ROOT = "/opt/gravis/staticfiles"

ALLOWED_HOSTS = ["gravis", "127.0.0.1", "localhost"]
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:9090",
    "http://localhost:8001",
    "https://localhost:4443",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:9090",
    "https://127.0.0.1:4443",
    "https://rmrlpdcdap001.nyumc.org"
]
# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "portal",
    "django.contrib.staticfiles",
    "django_rq",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "app.middleware.CrossOriginEmbedderPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases
DB_BACKEND = env("DB_BACKEND")
BACKENDS = {
    "postgres":  {
        "ENGINE": "django.db.backends.postgresql",
        "USER": env("DB_USER"),
        "DBNAME": "gravis",
        "NAME": "gravis"
    },
}
DATABASES = {
    "default": BACKENDS[DB_BACKEND]
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

RQ_SHOW_ADMIN_LINK = True
RQ_QUEUES = {
    "default": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        # 'PASSWORD': 'some-password',
        "DEFAULT_TIMEOUT": 7200,
    },
    # 'high': {
    #     'URL': os.getenv('REDISTOGO_URL', 'redis://localhost:6379/0'), # If you're on Heroku
    #     'DEFAULT_TIMEOUT': 500,
    # },
    # 'low': {
    #     'HOST': 'localhost',
    #     'PORT': 6379,
    #     'DB': 0,
    # }
}
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
