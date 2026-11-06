from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import Principal, require_principal
from app.authz import visible_productions
from app.database import get_db
from app.schemas.dashboard import Dashboard
from app.services.dashboard import build_dashboard

router = APIRouter()


@router.get("/me/dashboard", response_model=Dashboard)
def get_dashboard(db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> Dashboard:
    """What needs this person now, across every production they can see. Prague's today, like the crew's link."""
    return build_dashboard(db, visible_productions(db, principal), datetime.now(ZoneInfo("Europe/Prague")).date())
