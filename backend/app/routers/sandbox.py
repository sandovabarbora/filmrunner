from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.ratelimit import SlidingWindow, client_ip
from app.schemas.sandbox import SandboxSession
from app.services.sandbox import create_session, live_session_count, purge_expired

public_router = APIRouter()

# Open to anyone by design: each call writes a small world to the database, so both the rate and the total are bounded.
_per_ip = SlidingWindow(5)
MAX_LIVE_SESSIONS = 200


@public_router.post("/public/sandbox/sessions", response_model=SandboxSession, status_code=status.HTTP_201_CREATED)
def start_session(request: Request, db: Session = Depends(get_db)) -> SandboxSession:
    if not get_settings().sandbox_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    allowed, retry_after = _per_ip.hit(client_ip(request))
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many test sessions", headers={"Retry-After": str(retry_after)})
    purge_expired(db)
    db.commit()
    if live_session_count(db) >= MAX_LIVE_SESSIONS:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The test environment is full; try again later")
    return create_session(db, datetime.now(ZoneInfo("Europe/Prague")).date())
