"""
Django settings for backend project.

Generated by 'django-admin startproject' using Django 4.2.9.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from datetime import timedelta
import os
from pathlib import Path

from django.utils import timezone
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ["DEBUG"] == "True"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "manage.inethicloud.net",
    "manage.inethilocal.net",
    "manage-backend.inethilocal.net",
    "manage-backend.inethicloud.net",
] + os.environ.get("ALLOWED_HOSTS", "").split(",")

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://manage.inethilocal.net",
    "https://manage.inethicloud.net",
    "https://manage-backend.inethilocal.net",
    "https://manage-backend.inethicloud.net",
]

# CORS settings for development. For production, consider specifying CORS_ALLOWED_ORIGINS.
CORS_ALLOW_ALL_ORIGINS = DEBUG  # For development

CORS_ALLOW_CREDENTIALS = True
# Application definition
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_keycloak",
    "revproxy",
    "accounts",
    "monitoring",
    "metrics",
    "payments",
    "wallet",
    "sync",
    "radius"
]
# Keycloak config
AUTHENTICATION_BACKENDS = ["django_keycloak.backends.KeycloakAuthorizationCodeBackend"]
LOGIN_URL = "keycloak_login"
KEYCLOAK_CLIENTS = {
    "DEFAULT": {
        "URL": os.environ["KEYCLOAK_URL"],
        "REALM": os.environ["KEYCLOAK_REALM"],
        "CLIENT_ID": os.environ["KEYCLOAK_CLIENT_ID"],
        "CLIENT_SECRET": os.environ["KEYCLOAK_CLIENT_SECRET"],
    },
    "API": {
        "URL": os.environ["KEYCLOAK_URL"],
        "REALM": os.environ["KEYCLOAK_REALM"],
        "CLIENT_ID": os.environ["DRF_KEYCLOAK_CLIENT_ID"],
        "CLIENT_SECRET": None,  # DRF client is public
    },
}
# Radiusdesk config
RD_DB_NAME = "rd"
RD_DB_USER = "rd"
RD_DB_PASSWORD = "rd"
RD_DB_HOST = "127.0.0.1"
RD_DB_PORT = "3306"
RD_URL = os.environ["RADIUSDESK_URL"]
RD_CONFIG_URL = f"{RD_URL}/cake4/rd_cake/nodes/get-config-for-node.json"
RD_REPORT_URL = f"{RD_URL}/cake4/rd_cake/node-reports/submit_report.json"
RD_ACTIONS_URL = f"{RD_URL}/cake4/rd_cake/node-actions/get_actions_for.json"
# UNIFI config
UNIFI_DB_NAME = "ace"
UNIFI_DB_USER = ""
UNIFI_DB_PASSWORD = ""
UNIFI_DB_HOST = "localhost"
UNIFI_DB_PORT = "27117"
UNIFI_URL = os.environ["UNIFI_URL"]
UNIFI_INFORM_URL = f"{UNIFI_URL}/inform"

DEVICE_CHECKS = [
    {
        "title": "CPU Usage",
        "key": "cpu",
        "func": lambda v: v < 80,
        "feedback": {
            None: "No CPU usage recorded",
            False: "CPU usage is high",
            True: "CPU usage falls in an acceptable range",
        },
    },
    {
        "title": "Memory Usage",
        "key": "mem",
        "func": lambda v: v < 70,
        "feedback": {
            None: "No memory usage recorded",
            False: "Memory usage is high",
            True: "Memory usage falls in an acceptable range",
        },
    },
    {
        "title": "Recently Contacted",
        "key": "last_ping",
        "func": lambda v: timezone.now() - v < timedelta(minutes=20),
        "feedback": {
            None: "Device has never been pinged",
            False: "Device has not been pinged recently",
            True: "Device has been pinged recently",
        },
    },
    {
        "title": "Active",
        "key": "last_contact",
        "func": lambda v: timezone.now() - v < timedelta(minutes=5),
        "feedback": {
            None: "Device has not contacted the server",
            False: "Device has not been contacted the server recently",
            True: "Device is active",
        },
    },
    {
        "title": "Reachable",
        "key": "reachable",
        "func": bool,
        "feedback": {
            None: "Device has not been contacted yet",
            False: "Device is unreachable",
            True: "Device is reachable",
        },
    },
    {
        "title": "RTT",
        "key": "rtt",
        "func": lambda v: v < 40,
        "feedback": {
            None: "No RTT data",
            False: "Took too long to return a response",
            True: "Response time is acceptable",
        },
    },
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "django_keycloak.authentication.KeycloakDRFAuthentication",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

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

ASGI_APPLICATION = "backend.asgi.application"
WSGI_APPLICATION = "backend.wsgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # 'ENGINE': 'django.db.backends.mysql',
            # 'NAME': 'manage',
            # 'USER': 'inethi',
            # 'PASSWORD': 'iNethi2023#',
            # 'HOST': 'inethi-manage-mysql',
            # 'PORT': '3306',
        },
        "metrics_db": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "metrics.sqlite3",
        },
        "radius_db": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": RD_DB_NAME,
            "USER": RD_DB_USER,
            "PASSWORD": RD_DB_PASSWORD,
            "HOST": RD_DB_HOST,
            "PORT": RD_DB_PORT
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "manage",
            "USER": "inethi",
            "PASSWORD": "iNethi2023#",
            #'HOST': '127.0.0.1', # this works when running python locally
            "HOST": "inethi-manage-mysql",
            "PORT": "3306",
        }
    }

DATABASE_ROUTERS = ["backend.routers.MetricsRouter"]

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Johannesburg"

USE_I18N = True

USE_TZ = True
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery config
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:6379/0"
# Celery TIME_ZONE should be equal to django TIME_ZONE
# In order to schedule run_iperf3_checks on the correct time intervals
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False

# Channels config
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"redis://{REDIS_HOST}/1"],
        },
    },
}

CELERY_BEAT_SCHEDULE = {
    "ping_schedule": {
        "task": "metrics.tasks.run_pings",
        # Executes ping every 5 min
        "schedule": timedelta(minutes=5),
    },
    "sync_schedule": {
        "task": "sync.tasks.sync_dbs",
        # Executes db sync every hour
        "schedule": timedelta(minutes=60),
    },
    "alerts_schedule": {
        "task": "sync.tasks.generate_alerts",
        # Executes alert generation every 10 mins
        "schedule": timedelta(minutes=10),
    },
    "aggregate_hourly": {
        "task": "metrics.tasks.aggregate_all_hourly_metrics",
        "schedule": timedelta(hours=1),
    },
    "aggregate_daily": {
        "task": "metrics.tasks.aggregate_all_daily_metrics",
        "schedule": timedelta(days=1),
    },
    "aggregate_monthly": {
        "task": "metrics.tasks.aggregate_all_monthly_metrics",
        "schedule": timedelta(days=30),
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "report": {
            "format": "{asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console_info": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stdout",  # Use standard output rather than standard error
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": "django_errors.log",
            "formatter": "verbose",
        },
        "reports_file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "reports.log",
            "formatter": "report",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console_info", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console_info", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "general": {
            "handlers": ["console_info", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "reports": {
            "handlers": ["reports_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
