"""FastAPI application entrypoint.

Run locally with: uvicorn app.main:app --reload

References:
    - FastAPI application config: https://fastapi.tiangolo.com/tutorial/first-steps/
    - CORS middleware: https://fastapi.tiangolo.com/tutorial/cors/
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import call_sheets, productions

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(productions.router, prefix="/api/v1", tags=["productions"])
app.include_router(call_sheets.router, prefix="/api/v1", tags=["call-sheets"])
app.include_router(call_sheets.public_router, prefix="/api/v1", tags=["call-sheets-public"])


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
