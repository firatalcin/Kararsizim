"""
Django settings for the Kararsizim project.

All environment-specific values come from environment variables.
Locally, manage.py loads them from a .env file via python-dotenv.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"
ON_VERCEL = bool(os.environ.get("VERCEL"))

# Fail closed: a missing DJANGO_DEBUG means production. Local development sets
# DJANGO_DEBUG=True in .env (see .env.example); the test runner needs no setup.
DEBUG = env_bool("DJANGO_DEBUG", RUNNING_TESTS)
if DEBUG and ON_VERCEL:
    raise ImproperlyConfigured("DJANGO_DEBUG must not be True on Vercel.")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is False "
            "(for local development set DJANGO_DEBUG=True in .env)."
        )
    SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-production"

# No wildcard default: set the exact production host(s). Use ".vercel.app" only for preview deployments.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "polls",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Without DATABASE_URL we fall back to local SQLite.

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0,
    )
}

# Tests always run on local SQLite: they must not create a test database on
# Supabase, whose pooler is not meant for that.
if len(sys.argv) > 1 and sys.argv[1] == "test":
    DATABASES["default"] = dj_database_url.parse(f"sqlite:///{BASE_DIR / 'db.sqlite3'}")

if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Supabase transaction pooler: no server-side cursors, no prepared statements.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    options = DATABASES["default"].setdefault("OPTIONS", {})
    # "require" encrypts but does not verify the server; use "verify-full" with the CA
    # certificate downloaded from the Supabase dashboard (DJANGO_DB_SSLROOTCERT) to also verify it.
    options["sslmode"] = os.environ.get("DJANGO_DB_SSLMODE", "require")
    if os.environ.get("DJANGO_DB_SSLROOTCERT"):
        options["sslrootcert"] = os.environ["DJANGO_DB_SSLROOTCERT"]
    options["prepare_threshold"] = None


# Authentication

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"


# E-mail: password reset and address verification switch on once an SMTP server is configured
# (EMAIL_HOST). Locally, DJANGO_EMAIL_ENABLED=True prints the mails to the console instead.

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "webmaster@localhost"
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

EMAIL_FEATURES_ENABLED = env_bool("DJANGO_EMAIL_ENABLED", bool(EMAIL_HOST))
if EMAIL_FEATURES_ENABLED and not EMAIL_HOST and not DEBUG:
    raise ImproperlyConfigured("DJANGO_EMAIL_ENABLED needs EMAIL_HOST (an SMTP server) outside local development.")

PASSWORD_RESET_TIMEOUT = 60 * 60  # reset links stay valid for an hour

# Shown on the privacy page as the address to write to about personal data (optional).
CONTACT_EMAIL = os.environ.get("DJANGO_CONTACT_EMAIL", "")


# Rate limiting (core.throttle): {scope: (max requests, window in seconds)}.
# Off in tests (they hammer the same endpoints); throttle tests switch it on explicitly.

THROTTLE_ENABLED = env_bool("DJANGO_THROTTLE", not RUNNING_TESTS)
THROTTLE_LIMITS = {
    "login": (10, 15 * 60),  # per IP
    "login-email": (5, 15 * 60),  # per account, so a botnet cannot spread guesses over many IPs
    "admin-login": (10, 15 * 60),
    "register": (5, 60 * 60),
    "poll-create": (20, 60 * 60),  # per member (a few of these may be validation retries)
    "vote": (60, 10 * 60),  # per member or IP
    "vote-poll": (20, 60 * 60),  # per member or IP and poll
    "password-reset": (5, 60 * 60),
    "password-reset-email": (3, 60 * 60),
    "verify-mail": (3, 60 * 60),
    "account-delete": (5, 60 * 60),
}
# Vercel overwrites X-Forwarded-For with the real client address, so it can be trusted there;
# everywhere else only REMOTE_ADDR is trusted unless DJANGO_CLIENT_IP_HEADER says otherwise.
CLIENT_IP_HEADER = os.environ.get("DJANGO_CLIENT_IP_HEADER") or (
    "HTTP_X_FORWARDED_FOR" if ON_VERCEL else "REMOTE_ADDR"
)


# Internationalization

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}


# Messages are stored in cookies (Vercel's filesystem is not persistent).

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"


# Production security

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = True
    # Short HSTS by default: browsers remember it, so only raise it (a year, + subdomains/preload)
    # through the environment once the production domain is final.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
