"""
Django settings for the Accounts service (V1).

Separation of responsibilities:
- config/  = project-level wiring (settings, root URL conf, WSGI/ASGI).
- accounts/ = application code (views, URLs, middleware, later models/serializers).

At this stage (V1.1-V1.3) we implement only the structure, /health and the
gateway headers. The ORM model and migrations are deliberately postponed
until V1.4, after studying the professor's ORM lesson.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Demo-only defaults. Real secrets must come from the environment.
SECRET_KEY = os.getenv("ACCOUNTS_SECRET_KEY", "django-insecure-accounts-dev-only")
DEBUG = os.getenv("ACCOUNTS_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("ACCOUNTS_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
]

# This middleware runs first so its response phase always executes, even
# when a downstream view raises an exception.
MIDDLEWARE = [
    "accounts.middleware.GatewayHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# PostgreSQL 16 is the relational store for Accounts and Payments (Master Plan).
# The placeholder SQLite database used in V1.1-V1.3 is gone: V1.4 introduces
# the Account model and real migrations following the professor's ORM lesson.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "accounts"),
        "USER": os.getenv("POSTGRES_USER", "accounts"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "accounts_dev"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5433"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# Fault-injection knobs (C1 /fail, /slow, /flaky). Tests override them with
# Django's override_settings so the suite stays fast and deterministic.
ACCOUNTS_SLOW_SECONDS = float(os.getenv("ACCOUNTS_SLOW_SECONDS", "2"))
ACCOUNTS_FLAKY_FAILURE_RATE = float(os.getenv("ACCOUNTS_FLAKY_FAILURE_RATE", "0.5"))

# Structured console logs are captured by Docker and by our tests. The
# gateway middleware puts request_id / consumer / served_by into the message.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "gateway": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "gateway",
        },
    },
    "loggers": {
        "accounts.gateway": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
