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


def _clean_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    for key in (
        "APP_ENV",
        "SUPABASE_URL",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
        "DEV_AUTH_SECRET",
        "DEV_JWT_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_dev_auth_defaults_outside_production(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", app_env)
    settings = _settings()
    assert settings.dev_auth_enabled is True
    assert len(settings.DEV_AUTH_SECRET.get_secret_value()) >= 32
    assert settings.JWT_AUDIENCE == "authenticated"
    assert settings.DEV_JWT_TTL_SECONDS == 28800
    assert settings.SUPABASE_URL == ""


def test_blank_dev_auth_secret_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("DEV_AUTH_SECRET", "")
    assert len(_settings().DEV_AUTH_SECRET.get_secret_value()) >= 32


def test_explicit_dev_auth_secret_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("DEV_AUTH_SECRET", "my-own-secret-" + "x" * 30)
    assert _settings().DEV_AUTH_SECRET.get_secret_value() == "my-own-secret-" + "x" * 30


def test_production_requires_supabase_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError) as missing_both:
        _settings()
    assert "SUPABASE_URL is required" in str(missing_both.value)
    monkeypatch.setenv("SUPABASE_URL", "https://p.example.test")
    with pytest.raises(ValidationError) as missing_issuer:
        _settings()
    assert "JWT_ISSUER is required" in str(missing_issuer.value)
    monkeypatch.setenv("JWT_ISSUER", "   ")
    with pytest.raises(ValidationError):
        _settings()
    assert "s3cret" not in str(missing_issuer.value)


def test_production_disables_dev_auth_and_ignores_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SUPABASE_URL", "https://p.example.test/")
    monkeypatch.setenv("JWT_ISSUER", "https://p.example.test/auth/v1")
    monkeypatch.setenv("DEV_AUTH_SECRET", "should-not-be-used-" + "x" * 20)
    settings = _settings()
    assert settings.dev_auth_enabled is False
    assert settings.DEV_AUTH_SECRET.get_secret_value() == ""
    assert settings.SUPABASE_URL == "https://p.example.test"


def test_dev_auth_secret_does_not_leak_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    secret = _settings().DEV_AUTH_SECRET.get_secret_value()
    assert secret not in repr(_settings())


def test_validation_errors_do_not_echo_input_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_auth_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError) as excinfo:
        _settings()
    assert "s3cret" not in str(excinfo.value)
    assert "input_value" not in str(excinfo.value)
