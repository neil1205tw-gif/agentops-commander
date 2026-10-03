from pydantic import BaseModel, ConfigDict, Field


class ScenarioAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)
    source: str = Field(min_length=1)
    # Minutes relative to incident creation; negative values are in the past.
    fired_at_offset_minutes: int
    symptoms: list[str] = Field(min_length=1)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    default_title: str = Field(min_length=1)
    affected_services: list[str] = Field(min_length=1)
    alert: ScenarioAlert
