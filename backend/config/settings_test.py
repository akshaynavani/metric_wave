"""Settings for the pytest suite: no external Postgres/Redis required."""
import os

from .settings import *  # noqa: F401,F403

SECRET_KEY = "test-secret"
DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("TEST_SQLITE_PATH", ":memory:"),
    }
}

# CI can opt into the real backing services by setting USE_REAL_SERVICES=1.
if os.environ.get("USE_REAL_SERVICES") == "1":
    import dj_database_url

    DATABASES = {"default": dj_database_url.config()}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
INGEST_MAX_BATCH = 5
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
