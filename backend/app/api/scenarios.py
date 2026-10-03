from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth import CurrentUser, require_role
from app.scenarios import Scenario, ScenarioRegistry

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios")
async def list_scenarios(
    request: Request, _user: Annotated[CurrentUser, Depends(require_role("viewer"))]
) -> list[Scenario]:
    registry: ScenarioRegistry = request.app.state.scenario_registry
    return registry.all()
