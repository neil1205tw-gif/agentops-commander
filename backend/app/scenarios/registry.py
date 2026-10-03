from collections.abc import Iterable
from pathlib import Path

from app.scenarios.models import Scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCENARIO_KEYS = frozenset({"cpu_spike_after_deploy", "db_pool_exhaustion", "duplicate_alert_storm"})


class ScenarioRegistry:
    def __init__(self, scenarios: Iterable[Scenario]) -> None:
        self._scenarios: dict[str, Scenario] = {}
        for scenario in scenarios:
            if scenario.key in self._scenarios:
                raise ValueError(f"Duplicate scenario key: {scenario.key}")
            self._scenarios[scenario.key] = scenario

    @classmethod
    def from_directory(cls, directory: Path | None = None) -> "ScenarioRegistry":
        """Load every *.json fixture; any invalid file raises (so the app fails at startup)."""
        scenarios: list[Scenario] = []
        for path in sorted((directory or FIXTURES_DIR).glob("*.json")):
            scenario = Scenario.model_validate_json(path.read_text(encoding="utf-8"))
            if scenario.key != path.stem:
                raise ValueError(f"Scenario key '{scenario.key}' does not match file {path.name}")
            scenarios.append(scenario)
        return cls(scenarios)

    def get(self, key: str) -> Scenario | None:
        return self._scenarios.get(key)

    def all(self) -> list[Scenario]:
        return list(self._scenarios.values())

    def service_names(self) -> set[str]:
        return {service for s in self._scenarios.values() for service in s.affected_services}


def load_registry(directory: Path | None = None) -> ScenarioRegistry:
    """Load the registry and require exactly the fixed set of scenario keys."""
    registry = ScenarioRegistry.from_directory(directory)
    loaded = {scenario.key for scenario in registry.all()}
    if loaded != SCENARIO_KEYS:
        raise ValueError(f"Scenario fixtures must be exactly: {', '.join(sorted(SCENARIO_KEYS))}")
    return registry
