import os
import sys
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
# Omit DEBUG on the host → production-safe default. Local: DEBUG=True in .env.
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# In development, serve static from finders when DEBUG=True (no collectstatic required).
WHITENOISE_USE_FINDERS = DEBUG

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "config.apps.ConfigConfig",
    "restaurants",
    "bookings",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestIdMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.seated_globals",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

_sqlite_default = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
_database_url = (os.environ.get("DATABASE_URL") or "").strip()

if DEBUG:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL",
            default=_sqlite_default,
        ),
    }
elif _database_url:
    DATABASES = {"default": environ.Env.db_url_config(_database_url)}
else:
    # Production with discrete Railway / Postgres vars (no DATABASE_URL string).
    _db_options = {}
    if env.bool("DATABASE_SSL_REQUIRE", default=True):
        _db_options["sslmode"] = "require"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
            "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
            "OPTIONS": _db_options,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "restaurants:dashboard"
LOGOUT_REDIRECT_URL = "home"

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
if "test" in sys.argv:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "send-reminders": {
        "task": "bookings.tasks.send_reminder_emails",
        "schedule": crontab(hour=10, minute=0),
    },
    "mark-completed": {
        "task": "bookings.tasks.mark_completed_bookings",
        "schedule": crontab(hour=2, minute=0),
    },
}

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_PRICE_LINK = env("STRIPE_PRICE_LINK", default="")
STRIPE_PRICE_WIDGET = env("STRIPE_PRICE_WIDGET", default="")

RESEND_API_KEY = env("RESEND_API_KEY", default="")
FROM_EMAIL = env("FROM_EMAIL", default="bookings@seated.co")
SITE_URL = env("SITE_URL", default="http://localhost:8000")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "seated": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "stderr": {"class": "logging.StreamHandler", "formatter": "seated"},
    },
    "loggers": {
        "seated.request": {"handlers": ["stderr"], "level": "ERROR", "propagate": False},
        "seated.errors": {"handlers": ["stderr"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["stderr"], "level": "ERROR", "propagate": False},
    },
    "root": {"handlers": ["stderr"], "level": "INFO"},
}
