"""Kinetic Ledger FastAPI application and lifecycle wiring."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..database.database import check_database_connection, init_db
from ..database.sessions import check_redis_connection
from ..utils.errors import KineticLedgerError, ManualReviewRequiredError, NoveltyRejectionError
from ..utils.logging import setup_logging
from .routers import (
    status as status_router,
    ui,
    sdtvet,
    institutions,
    motion_catalogue,
    motion_catalogue_admin
)

setup_logging("kinetic-ledger-api")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kinetic Ledger Phase-2", description="Trust-minimized motion commerce stack", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(status_router.router, prefix="/status")
# Route modules already declare their own prefixes.
app.include_router(ui.router)
app.include_router(sdtvet.router)
app.include_router(institutions.router)
app.include_router(motion_catalogue.router)
app.include_router(motion_catalogue_admin.router)

# The visualizer HTML loads its bundled Three.js dependencies from `/ui/vendor`.
# Mounting the UI directory makes those assets available while the UI router keeps
# `/` as the application entry point.
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui-assets")

def sync_data_from_r2() -> None:
    """Sync Cloud Run data/configuration from the R2 bucket."""
    skip_env = os.getenv("SKIP_R2_SYNC", os.getenv("SKIP_GCS_SYNC", ""))
    if skip_env.lower() == "true" or not os.getenv("K_SERVICE"):
        return
    try:
        from ..services.r2_storage import sync_directory_from_r2
        sync_directory_from_r2("data/", "/app/data")
        sync_directory_from_r2("config/", "/app/config")
    except Exception as exc:  # pragma: no cover - infrastructure dependent
        logger.warning("Failed to sync data from R2: %s", exc)


_r2_sync_executor = ThreadPoolExecutor(max_workers=1)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize backing services without blocking health checks."""
    try:
        init_db()
        logger.info("PostgreSQL connectivity check %s", "passed" if check_database_connection() else "failed")
    except Exception as exc:
        logger.error("PostgreSQL initialization failed: %s", exc)
    try:
        logger.info("Redis connectivity check %s", "passed" if check_redis_connection() else "failed")
    except Exception as exc:
        logger.error("Redis connectivity check failed: %s", exc)
    asyncio.get_running_loop().run_in_executor(_r2_sync_executor, sync_data_from_r2)


@app.exception_handler(KineticLedgerError)
async def kinetic_ledger_error_handler(request, exc: KineticLedgerError):
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, NoveltyRejectionError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, ManualReviewRequiredError):
        status_code = status.HTTP_202_ACCEPTED
    return JSONResponse(status_code=status_code, content={"error": exc.code, "message": exc.message, "details": exc.details})
