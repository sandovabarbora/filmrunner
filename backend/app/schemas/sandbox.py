import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SandboxPersona(BaseModel):
    key: str
    kind: Literal["editor", "link"]
    # An editor persona signs in with this token; a link persona opens this sheet, the way a real crew member does.
    token: str | None = None
    call_sheet_id: uuid.UUID | None = None
    personal_token: str | None = None


class SandboxSession(BaseModel):
    expires_at: datetime
    personas: list[SandboxPersona]
