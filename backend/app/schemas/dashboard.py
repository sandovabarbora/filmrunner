import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class DashboardItem(BaseModel):
    kind: Literal["unconfirmed", "unpublished"]
    production_id: uuid.UUID
    production_name: str
    call_sheet_id: uuid.UUID
    shoot_date: date
    day_number: int
    revision_letter: str | None = None
    crew_call: str | None = None
    total: int = 0
    confirmed: int = 0
    not_opened: int = 0


class OnTrackProduction(BaseModel):
    production_id: uuid.UUID
    production_name: str
    next_call_sheet_id: uuid.UUID | None = None
    next_shoot_date: date | None = None
    crew_call: str | None = None


class Dashboard(BaseModel):
    items: list[DashboardItem]
    on_track: list[OnTrackProduction]
