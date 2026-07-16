from pathlib import Path
import os

from decouple import Csv, config


os.environ["PGCLIENTENCODING"] = "UTF8"


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-stock-single-dev-key-change-me",
)

DEBUG = config(
    "DEBUG",
    default=True,
    cast=bool,
)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost",
    cast=Csv(),
)


INSTALLED_APPS = [
    # Applications Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Applications externes
    "widget_tweaks",

    # Applications du projet
    "accounts",
    "core",
    "catalog",
    "inventory",
    "customers",
    "sales",
    "payments",
    "expenses",
    "cashbox",
    "documents",
    "reports",
    "purchases.apps.PurchasesConfig",
    "configuration.apps.ConfigurationConfig",
]


MIDDLEWARE = [
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
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                (
                    "django.contrib.auth."
                    "context_processors.auth"
                ),
                (
                    "django.contrib.messages."
                    "context_processors.messages"
                ),

                # Informations de la société disponibles
                # automatiquement dans les templates.
                (
                    "configuration.context_processors."
                    "company_settings"
                ),
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config(
            "DB_NAME",
            default="stock_single_db",
        ),
        "USER": config(
            "DB_USER",
            default="stock_single_user",
        ),
        "PASSWORD": config(
            "DB_PASSWORD",
            default="12345",
        ),
        "HOST": config(
            "DB_HOST",
            default="localhost",
        ),
        "PORT": config(
            "DB_PORT",
            default="5432",
        ),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Africa/Bamako"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "dashboard"

LOGOUT_REDIRECT_URL = "login"