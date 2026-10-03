from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Local development only. Never used when APP_ENV=production.
_DEFAULT_DEV_AUTH_SECRET = "dev-only-secret-for-local-development-do-not-use-in-production"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    DATABASE_URL: SecretStr
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    PORT: int = 10000
    SUPABASE_URL: str = ""
    JWT_ISSUER: str = ""
    JWT_AUDIENCE: str = "authenticated"
    # Signs and verifies dev JWTs. Empty means: use the built-in default in development / test,
    # and ignore it in production (dev tokens are not accepted there).
    DEV_AUTH_SECRET: SecretStr = SecretStr("")
    DEV_JWT_TTL_SECONDS: int = 28800

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must not contain a wildcard origin")
        return value

    @model_validator(mode="after")
    def _check_auth_settings(self) -> Self:
        self.SUPABASE_URL = self.SUPABASE_URL.strip().rstrip("/")
        self.JWT_ISSUER = self.JWT_ISSUER.strip()
        if self.APP_ENV == "production":
            for name in ("SUPABASE_URL", "JWT_ISSUER"):
                if not getattr(self, name):
                    raise ValueError(f"{name} is required when APP_ENV=production")
            self.DEV_AUTH_SECRET = SecretStr("")
        elif not self.DEV_AUTH_SECRET.get_secret_value():
            self.DEV_AUTH_SECRET = SecretStr(_DEFAULT_DEV_AUTH_SECRET)
        return self

    @property
    def dev_auth_enabled(self) -> bool:
        return self.APP_ENV in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
