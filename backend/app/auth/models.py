import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["viewer", "operator", "admin"]

# admin ⊃ operator ⊃ viewer
ROLE_LEVELS: dict[str, int] = {"viewer": 0, "operator": 1, "admin": 2}


class CurrentUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    email: str | None
    display_name: str | None
    role: Role
