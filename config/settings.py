from pathlib import Path
import os

import dj_database_url
from decouple import Csv, config


# =========================================================
# CHEMINS ET ENVIRONNEMENT
# =========================================================

os.environ["PGCLIENTENCODING"] = "UTF8"

BASE_DIR = Path(__file__).resolve().parent.parent

RENDER_EXTERNAL_HOSTNAME = os.environ.get(
    "RENDER_EXTERNAL_HOSTNAME",
    "",
)


# =========================================================
# SÉCURITÉ
# =========================================================

# La clé doit exister dans le fichier .env en local
# et dans Environment sur Render.
SECRET_KEY = config("SECRET_KEY")

# Local : DEBUG=True dans .env
# Render : DEBUG=False dans Environment
DEBUG = config(
    "DEBUG",
    default=False,
    cast=bool,
)

ALLOWED_HOSTS = [
    host
    for host in config(
        "ALLOWED_HOSTS",
        default="127.0.0.1,localhost",
        cast=Csv(),
    )
    if host
]

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in config(
        "CSRF_TRUSTED_ORIGINS",
        default="",
        cast=Csv(),
    )
    if origin
]

# Render fournit automatiquement son nom de domaine.
if RENDER_EXTERNAL_HOSTNAME:
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(
            RENDER_EXTERNAL_HOSTNAME
        )

    render_origin = (
        f"https://{RENDER_EXTERNAL_HOSTNAME}"
    )

    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(
            render_origin
        )


# =========================================================
# APPLICATIONS
# =========================================================

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


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Doit rester juste après SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URLS, TEMPLATES ET SERVEUR
# =========================================================

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
                (
                    "django.template.context_processors."
                    "debug"
                ),
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth."
                    "context_processors.auth"
                ),
                (
                    "django.contrib.messages."
                    "context_processors.messages"
                ),

                # Cloche des alertes de stock.
                (
                    "catalog.context_processors."
                    "stock_notifications"
                ),

                # Informations de la société.
                (
                    "configuration.context_processors."
                    "company_settings"
                ),
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# =========================================================
# BASE DE DONNÉES
# =========================================================

# En production, Render fournira DATABASE_URL.
# En local, Django utilisera les variables DB_* du .env.
DATABASE_URL = config(
    "DATABASE_URL",
    default="",
)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.postgresql"
            ),
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


# =========================================================
# VALIDATION DES MOTS DE PASSE
# =========================================================

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


# =========================================================
# LANGUE ET HEURE
# =========================================================

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Africa/Bamako"

USE_I18N = True

USE_TZ = True


# =========================================================
# FICHIERS STATIQUES ET MÉDIAS
# =========================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# =========================================================
# SÉCURITÉ HTTPS EN PRODUCTION
# =========================================================

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"


# =========================================================
# DJANGO
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"