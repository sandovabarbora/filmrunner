"""FastAPI application entrypoint.

Run locally with: uvicorn app.main:app --reload

References:
    - FastAPI application config: https://fastapi.tiangolo.com/tutorial/first-steps/
    - CORS middleware: https://fastapi.tiangolo.com/tutorial/cors/
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.bodylimit import BodyLimitMiddleware
from app.ratelimit import RateLimitMiddleware

from app.config import get_settings
from app.database import engine
from app.request_log import RequestLogMiddleware
from app.routers import call_sheets, dashboard, productions, push, sandbox

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# They log full request URLs, which carry addresses and push endpoints.
for _noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
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
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    per_ip=settings.public_rate_limit_per_ip,
    per_token=settings.public_rate_limit_per_token,
    per_ip_photos=settings.public_rate_limit_per_ip_photos,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last = outermost, so a 429 and a CORS preflight are logged as well.
app.add_middleware(RequestLogMiddleware)

app.include_router(productions.router, prefix="/api/v1", tags=["productions"])
app.include_router(productions.public_router, prefix="/api/v1", tags=["contacts-public"])
app.include_router(call_sheets.router, prefix="/api/v1", tags=["call-sheets"])
app.include_router(call_sheets.public_router, prefix="/api/v1", tags=["call-sheets-public"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(sandbox.public_router, prefix="/api/v1", tags=["sandbox"])
app.include_router(push.router, prefix="/api/v1", tags=["push"])


READY_TIMEOUT_SECONDS = 2.5
# One worker: when the database hangs, probes cannot pile onto the request threads or take more than one pooled connection.
_ready_probe = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readyz")


def _ops_body() -> dict[str, str]:
    body = {"status": "ok", "environment": settings.environment}
    # FR-109: omitted (not null) when the image was built without the build-arg,
    # so a staleness check can tell "predates commit reporting" apart from "unknown sha".
    if settings.git_sha:
        body["git_sha"] = settings.git_sha
    return body


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    return _ops_body()


def _select_one() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@app.get("/readyz", tags=["ops"], responses={503: {"description": "The database did not answer in time"}})
async def readyz() -> JSONResponse:
    # A hung server enforces no statement_timeout, so the deadline has to be on this side.
    probe = asyncio.get_running_loop().run_in_executor(_ready_probe, _select_one)
    try:
        await asyncio.wait_for(probe, READY_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - whatever the failure, the answer is the same and carries no detail
        logger.warning("Readiness probe failed: %s", exc.__class__.__name__)
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse(_ops_body())
