import pytest

from tests.db_support import database_url_for, require_test_database_url


def test_require_returns_url_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://u:p@h:5432/postgres")
    assert require_test_database_url() == "postgresql+psycopg://u:p@h:5432/postgres"


def test_require_skips_locally_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(pytest.skip.Exception, match="TEST_DATABASE_URL"):
        require_test_database_url()


def test_require_fails_in_ci_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="TEST_DATABASE_URL"):
        require_test_database_url()


def test_database_url_for_replaces_database_and_keeps_password() -> None:
    url = database_url_for("postgresql+psycopg://u:p%40ss@h:5432/postgres", "other")
    assert url == "postgresql+psycopg://u:p%40ss@h:5432/other"
