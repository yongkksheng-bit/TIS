import pytest
from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    """Config should load database URL from DATABASE_URL env var."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/test")
    settings = Settings()
    assert "test" in settings.DATABASE_URL


def test_settings_default_database_url():
    """Config should have a sensible default for DATABASE_URL."""
    settings = Settings()
    assert "postgresql" in settings.DATABASE_URL
    assert "tis" in settings.DATABASE_URL


def test_settings_redis_url_default():
    """Config should have a default REDIS_URL."""
    settings = Settings()
    assert "redis://" in settings.REDIS_URL


def test_settings_minio_defaults():
    """Config should have MinIO defaults."""
    settings = Settings()
    assert settings.MINIO_ENDPOINT == "localhost:9000"
    assert settings.MINIO_ACCESS_KEY == "minioadmin"
    assert settings.MINIO_SECRET_KEY == "minioadmin"


def test_settings_deepseek_api_key_optional():
    """DEEPSEEK_API_KEY should be optional (None by default)."""
    settings = Settings()
    assert settings.DEEPSEEK_API_KEY is None
