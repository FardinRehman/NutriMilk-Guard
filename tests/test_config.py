"""
Unit tests for application configuration validation.
"""

import pytest
from config import Config


def test_config_validation_success():
    """Verify default valid configuration passes validation."""
    Config.validate()
    assert Config.EXPECTED_PROJECT_ID in Config.FIREBASE_DATABASE_URL


def test_config_missing_url(monkeypatch):
    """Verify validation raises error if database URL is missing."""
    monkeypatch.setattr(Config, "FIREBASE_DATABASE_URL", "")
    with pytest.raises(ValueError, match="FIREBASE_DATABASE_URL is not configured"):
        Config.validate()


def test_config_invalid_url_scheme(monkeypatch):
    """Verify validation raises error if URL is malformed."""
    monkeypatch.setattr(Config, "FIREBASE_DATABASE_URL", "not-a-valid-url")
    with pytest.raises(ValueError, match="not a valid HTTP/HTTPS URL"):
        Config.validate()


def test_config_mismatched_project(monkeypatch):
    """Verify validation raises error if URL does not belong to expected project."""
    monkeypatch.setattr(
        Config,
        "FIREBASE_DATABASE_URL",
        "https://another-project-default-rtdb.firebaseio.com/"
    )
    monkeypatch.setattr(Config, "FIREBASE_PROJECT_ID", "another-project")
    with pytest.raises(ValueError, match="does not match expected project ID"):
        Config.validate()
