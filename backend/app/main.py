"""FastAPI application entrypoint.

Run locally with: uvicorn app.main:app --reload

References:
    - FastAPI application config: https://fastapi.tiangolo.com/tutorial/first-steps/
    - CORS middleware: https://fastapi.tiangolo.com/tutorial/cors/
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ratelimit import RateLimitMiddleware

from app.config import get_settings
from app.routers import call_sheets, productions, push

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FilmRunner — Call Sheets",
    description="Skeleton API for the call-sheet slice of FilmRunner. See DESIGN.md.",
    version="0.1.0",
)

# The PWA is served from another origin (GitHub Pages in production, the
# Vite dev server locally), so CORS is required. Origins come from
# FILMRUNNER_CORS_ORIGINS; "*" is the local-dev default.
# FR-51: the abuse guard sits inside CORS (added first = innermost), so a 429 still carries CORS headers
# and the browser can show the message instead of a blocked request.
app.add_middleware(RateLimitMiddleware, per_ip=settings.public_rate_limit_per_ip, per_token=settings.public_rate_limit_per_token)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(productions.router, prefix="/api/v1", tags=["productions"])
app.include_router(productions.public_router, prefix="/api/v1", tags=["contacts-public"])
app.include_router(call_sheets.router, prefix="/api/v1", tags=["call-sheets"])
app.include_router(call_sheets.public_router, prefix="/api/v1", tags=["call-sheets-public"])
app.include_router(push.router, prefix="/api/v1", tags=["push"])


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    body = {"status": "ok", "environment": settings.environment}
    # FR-109: omitted (not null) when the image was built without the build-arg,
    # so a staleness check can tell "predates commit reporting" apart from "unknown sha".
    if settings.git_sha:
        body["git_sha"] = settings.git_sha
    return body
