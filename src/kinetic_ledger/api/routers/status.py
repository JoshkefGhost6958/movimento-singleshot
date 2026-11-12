from fastapi import APIRouter

from ...database.database import check_database_connection
from ...database.sessions import check_redis_connection

router = APIRouter(
    #prefix="/status",
    tags=["status"],
)

@router.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "kinetic-ledger-api",
        "version": "2.0.0",
    }


@router.get("/ready")
def ready():
    """
    Startup probe endpoint for Cloud Run.
    Performs database and Redis connectivity checks.
    Returns 200 when the application is ready to receive traffic.
    """
    db_ok = check_database_connection()
    redis_ok = check_redis_connection()

    return {
        "status": "ready" if (db_ok and redis_ok) else "degraded",
        "service": "kinetic-ledger-api",
        "checks": {
            "database": "ok" if db_ok else "failed",
            "redis": "ok" if redis_ok else "failed",
        },
    }


@router.get("/traffic")
def traffic():
    """
    Readiness probe endpoint for Cloud Run.
    Returns 200 when the application can handle traffic.
    """
    return {"status": "accepting_traffic", "service": "kinetic-ledger-api"}


@router.get("/restart")
def restart():
    """
    Liveness probe endpoint for Cloud Run.
    Returns 200 to indicate the application is alive.
    """
    return {"status": "alive", "service": "kinetic-ledger-api"}