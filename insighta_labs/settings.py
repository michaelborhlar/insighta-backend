import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-default-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "profiles",
    "authentication",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "insighta_labs.urls"
WSGI_APPLICATION = "insighta_labs.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-api-version",
    "x-csrftoken",
]

# GitHub OAuth
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
)
GITHUB_WEB_REDIRECT_URI = os.environ.get(
    "GITHUB_WEB_REDIRECT_URI", "http://localhost:3000/auth/callback"
)

# Tokens
ACCESS_TOKEN_EXPIRY_SECONDS = int(os.environ.get("ACCESS_TOKEN_EXPIRY_SECONDS", 180))   # 3 min
REFRESH_TOKEN_EXPIRY_SECONDS = int(os.environ.get("REFRESH_TOKEN_EXPIRY_SECONDS", 300)) # 5 min

# External APIs (Stage 1/2)
GENDERIZE_API_URL = os.environ.get("GENDERIZE_API_URL", "https://api.genderize.io")
AGIFY_API_URL = os.environ.get("AGIFY_API_URL", "https://api.agify.io")
NATIONALIZE_API_URL = os.environ.get("NATIONALIZE_API_URL", "https://api.nationalize.io")

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

# Cache (for rate limiting — in-memory for simple deploys)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Web portal settings (for cookie auth)
WEB_PORTAL_ORIGIN = os.environ.get("WEB_PORTAL_ORIGIN", "http://localhost:3000")
CSRF_COOKIE_HTTPONLY = False  # CSRF token must be readable by JS for header submission
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
