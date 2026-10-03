import uuid

import pytest
from sqlalchemy import Engine, text

from scripts.set_role import main


@pytest.fixture(autouse=True)
def _database_env(migrated_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)


def _insert(engine: Engine, profile_id: uuid.UUID, email: str | None, role: str = "viewer") -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO profiles (id, email, role) VALUES (:id, :email, :role)"),
            {"id": profile_id, "email": email, "role": role},
        )


def _role(engine: Engine, profile_id: uuid.UUID) -> str:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT role FROM profiles WHERE id = :id"), {"id": profile_id}
        ).scalar_one()
    return str(value)


def test_sets_role_by_email_case_insensitively(
    sync_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    profile_id = uuid.uuid4()
    _insert(sync_engine, profile_id, "Someone@Example.test")
    assert main(["someone@example.TEST", "operator"]) == 0
    assert _role(sync_engine, profile_id) == "operator"
    assert "viewer -> operator" in capsys.readouterr().out


def test_sets_role_by_uuid(sync_engine: Engine) -> None:
    profile_id = uuid.uuid4()
    _insert(sync_engine, profile_id, None)
    assert main([str(profile_id), "admin"]) == 0
    assert _role(sync_engine, profile_id) == "admin"


def test_unknown_user_exits_non_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["nobody@example.test", "admin"]) == 1
    assert "user not found" in capsys.readouterr().err
    assert main([str(uuid.uuid4()), "admin"]) == 1


def test_invalid_role_is_rejected() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["someone@example.test", "root"])
    assert excinfo.value.code == 2


def test_missing_database_url_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.chdir("/")  # no .env to pick up
    assert main(["someone@example.test", "admin"]) == 2
    assert "DATABASE_URL is not configured" in capsys.readouterr().err


def test_connection_errors_do_not_print_the_connection_string(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw-secret@127.0.0.1:1/none")
    assert main(["someone@example.test", "admin"]) == 2
    captured = capsys.readouterr()
    assert "pw-secret" not in captured.out + captured.err
    assert "127.0.0.1" not in captured.out + captured.err
    assert "database operation failed" in captured.err
