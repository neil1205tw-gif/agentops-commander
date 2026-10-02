import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings

DB_URL = "postgresql+psycopg://user:s3cret@db:5432/app"


def _settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_ENV", "LOG_LEVEL", "CORS_ORIGINS", "PORT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    settings = _settings()
    assert settings.APP_ENV == "development"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.CORS_ORIGINS == ["http://localhost:5173"]
    assert settings.PORT == 10000


def test_cors_origins_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example, https://b.example ,")
    assert _settings().CORS_ORIGINS == ["http://a.example", "https://b.example"]


def test_cors_origins_rejects_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError):
        _settings()


def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert _settings().LOG_LEVEL == "DEBUG"


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        _settings()


def test_secret_fields_do_not_leak_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    settings = _settings()
    assert "s3cret" not in repr(settings)
    assert "s3cret" not in str(settings)
    assert settings.DATABASE_URL.get_secret_value() == DB_URL


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
