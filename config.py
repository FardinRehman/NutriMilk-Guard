"""
Configuration module for Nutri Milk Guard.
Loads environment variables, validates Firebase configuration, and sets application defaults.
"""

import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

# Ensure non-existent TLS CA certificate bundle environment variables on Windows do not crash requests/urllib
for env_var in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
    val = os.environ.get(env_var)
    if val and not os.path.exists(val):
        del os.environ[env_var]

# Load .env file from project root
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "nutri-milk-guard-default-vtu-project-key-2026")
    
    # Expected Firebase project ID
    EXPECTED_PROJECT_ID = "milk-monitoring-4cb97"
    
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", EXPECTED_PROJECT_ID).strip()
    FIREBASE_DATABASE_URL = os.getenv(
        "FIREBASE_DATABASE_URL",
        "https://milk-monitoring-4cb97-default-rtdb.asia-southeast1.firebasedatabase.app/"
    ).strip()
    
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        os.path.join(basedir, "secrets", "serviceAccountKey.json")
    )
    
    # Primary Firebase Realtime Database path where the ESP32 pushes updates
    DEFAULT_DB_PATH = os.getenv("DEFAULT_DB_PATH", "milk_monitor/current").strip().strip("/")
    
    # Background sync & live update intervals
    UPDATE_POLL_INTERVAL = float(os.getenv("UPDATE_POLL_INTERVAL", "3.0"))
    STALE_DATA_TIMEOUT = int(os.getenv("STALE_DATA_TIMEOUT", "45"))
    
    # Local persistent storage for application settings & in-memory ring buffer limits
    INSTANCE_DIR = os.path.join(basedir, "instance")
    SETTINGS_FILE = os.path.join(INSTANCE_DIR, "settings.json")
    HISTORY_CACHE_FILE = os.path.join(INSTANCE_DIR, "session_history.json")
    MAX_HISTORY_POINTS = 500
    
    # Server configuration
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))

    @classmethod
    def validate(cls):
        """
        Validate critical Firebase configuration.
        Fails fast if URL is completely missing or does not match the project.
        """
        if not cls.FIREBASE_DATABASE_URL:
            raise ValueError(
                "CRITICAL: FIREBASE_DATABASE_URL is not configured. "
                "Please configure FIREBASE_DATABASE_URL in .env or environment variables."
            )
        
        parsed = urlparse(cls.FIREBASE_DATABASE_URL)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(
                f"CRITICAL: FIREBASE_DATABASE_URL '{cls.FIREBASE_DATABASE_URL}' is not a valid HTTP/HTTPS URL."
            )
        
        # Validate that the database URL belongs to the intended project
        netloc = parsed.netloc.lower()
        if cls.EXPECTED_PROJECT_ID not in netloc:
            raise ValueError(
                f"CRITICAL: Configured database URL '{cls.FIREBASE_DATABASE_URL}' does not match "
                f"expected project ID '{cls.EXPECTED_PROJECT_ID}'."
            )


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    FIREBASE_DATABASE_URL = "https://milk-monitoring-4cb97-default-rtdb.asia-southeast1.firebasedatabase.app/"
    UPDATE_POLL_INTERVAL = 0.5
    STALE_DATA_TIMEOUT = 10


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
