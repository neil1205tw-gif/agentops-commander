import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.scenarios import SCENARIO_KEYS, Scenario, ScenarioRegistry, load_registry
from app.scenarios.registry import FIXTURES_DIR
from tests.helpers import make_settings


def _write_fixtures(directory: Path) -> None:
    for path in FIXTURES_DIR.glob("*.json"):
        (directory / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def test_registry_loads_the_three_scenarios() -> None:
    registry = load_registry()
    assert {s.key for s in registry.all()} == SCENARIO_KEYS
    assert registry.service_names() == {"checkout-api", "student-portal-api", "notification-worker"}


def test_get_by_key() -> None:
    registry = load_registry()
    scenario = registry.get("db_pool_exhaustion")
    assert scenario is not None
    assert scenario.affected_services == ["student-portal-api"]
    assert scenario.alert.symptoms
    assert registry.get("unknown") is None


def test_each_scenario_names_its_service() -> None:
    registry = load_registry()
    expected = {
        "cpu_spike_after_deploy": "checkout-api",
        "db_pool_exhaustion": "student-portal-api",
        "duplicate_alert_storm": "notification-worker",
    }
    for key, service in expected.items():
        scenario = registry.get(key)
        assert scenario is not None
        assert scenario.affected_services == [service]


def test_invalid_json_fails(tmp_path: Path) -> None:
    _write_fixtures(tmp_path)
    (tmp_path / "db_pool_exhaustion.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_registry(tmp_path)


def test_missing_field_fails(tmp_path: Path) -> None:
    _write_fixtures(tmp_path)
    path = tmp_path / "cpu_spike_after_deploy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["alert"]["summary"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_registry(tmp_path)


def test_unknown_field_fails(tmp_path: Path) -> None:
    _write_fixtures(tmp_path)
    path = tmp_path / "cpu_spike_after_deploy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metrics"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_registry(tmp_path)


def test_key_must_match_file_name(tmp_path: Path) -> None:
    _write_fixtures(tmp_path)
    (tmp_path / "db_pool_exhaustion.json").rename(tmp_path / "other.json")
    with pytest.raises(ValueError, match="does not match"):
        load_registry(tmp_path)


def test_missing_scenario_fails(tmp_path: Path) -> None:
    _write_fixtures(tmp_path)
    (tmp_path / "duplicate_alert_storm.json").unlink()
    with pytest.raises(ValueError, match="must be exactly"):
        load_registry(tmp_path)


def test_duplicate_keys_fail() -> None:
    scenario = load_registry().all()[0]
    with pytest.raises(ValueError, match="Duplicate"):
        ScenarioRegistry([scenario, scenario])


def test_scenario_model_rejects_empty_services() -> None:
    data = load_registry().all()[0].model_dump()
    data["affected_services"] = []
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_app_does_not_start_with_a_broken_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_fixtures(tmp_path)
    (tmp_path / "cpu_spike_after_deploy.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.scenarios.registry.FIXTURES_DIR", tmp_path)
    settings = make_settings(DATABASE_URL="postgresql+psycopg://x:y@127.0.0.1:1/none")
    with pytest.raises(ValidationError):
        create_app(settings)
