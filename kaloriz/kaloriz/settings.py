
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv; load_dotenv()

# Load .env dari ROOT PROJECT (selevel manage.py)
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-0*g@$i%3!o4c58$w9$a(g@=vnb)qr5x5w@5@yp@_js1-n3ax)y'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']  # Allow all hosts for development/testing

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]


# Application definition

INSTALLED_APPS = [
    "jazzmin",  # Must be before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "catalog",
    "shipping",
    "payment",
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

ROOT_URLCONF = 'kaloriz.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # <— kita pakai /templates
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "core.context_processors.cart_context",
        ]},
    },
]

WSGI_APPLICATION = 'kaloriz.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Makassar"  # atau "Asia/Jakarta"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]   # <— CSS/JS/Images kamu
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
# For development: emails will be printed to console


# =========================
# EMAIL (SMTP) CONFIG
# =========================
# =========================
# EMAIL (SMTP) CONFIG
# =========================
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')          # wajib terisi
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')  # wajib terisi (App Password TANPA spasi)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
SERVER_EMAIL = DEFAULT_FROM_EMAIL


# Midtrans configuration
MIDTRANS_IS_PRODUCTION = os.getenv('MIDTRANS_IS_PRODUCTION', 'False') == 'True'
MIDTRANS_SERVER_KEY = os.getenv('MIDTRANS_SERVER_KEY', '')
MIDTRANS_CLIENT_KEY = os.getenv('MIDTRANS_CLIENT_KEY', '')
MIDTRANS_PAYMENT_METHOD_SLUG = os.getenv('MIDTRANS_PAYMENT_METHOD_SLUG', 'midtrans').strip().lower()

# DOKU configuration
DOKU_IS_PRODUCTION = os.getenv('DOKU_IS_PRODUCTION', 'False') == 'True'
DOKU_CLIENT_ID = os.getenv('DOKU_CLIENT_ID', '')
DOKU_SECRET_KEY = os.getenv('DOKU_SECRET_KEY', '')
DOKU_MERCHANT_CODE = os.getenv('DOKU_MERCHANT_CODE', '')
DOKU_PAYMENT_METHOD_SLUG = os.getenv('DOKU_PAYMENT_METHOD_SLUG', 'doku').strip().lower()
DOKU_SANDBOX_BASE_URL = os.getenv('DOKU_SANDBOX_BASE_URL', 'https://api-sandbox.doku.com')
DOKU_PRODUCTION_BASE_URL = os.getenv('DOKU_PRODUCTION_BASE_URL', 'https://api.doku.com')


# Jazzmin settings
JAZZMIN_SETTINGS = {
    "site_title": "Kaloriz Admin",
    "site_header": "Kaloriz",
    "site_brand": "Kaloriz E-Commerce",
    "site_logo": None,
    "welcome_sign": "Selamat Datang di Kaloriz Admin",
    "copyright": "Kaloriz",
    "search_model": ["auth.User", "catalog.Product", "core.Order"],

    # Icons
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "catalog.Category": "fas fa-tags",
        "catalog.Product": "fas fa-box",
        "catalog.Testimonial": "fas fa-star",
        "core.Cart": "fas fa-shopping-cart",
        "core.Order": "fas fa-receipt",
        "core.UserProfile": "fas fa-user-circle",
        "core.Watchlist": "fas fa-heart",
    },

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["auth", "catalog", "core"],

    # UI Customization
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# ============================================
# SHIPPING CONFIGURATION
# ============================================

# Flat rate shipping untuk Makassar
# Tarif pengiriman berdasarkan kecamatan (diatur di District model)
SHIPPING_ENABLED = True
DEFAULT_SHIPPING_CITY = "Makassar"
DEFAULT_SHIPPING_PROVINCE = "Sulawesi Selatan"
