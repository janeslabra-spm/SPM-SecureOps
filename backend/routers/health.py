"""Health check endpoint for the Security Monitoring System.

Provides a GET /health endpoint that reports server status, database
connectivity, and detection engine active state.
"""

import time

from fastapi import APIRouter
from pydantic import BaseModel

from backend.db.session import check_db_connection

router = APIRouter()

# Module-level start time for uptime calculation
_start_time: float = time.time()


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str  # "healthy" | "degraded" | "unhealthy"
    database: bool  # DB connection alive
    detection_engine_active: bool  # Worker thread running
    uptime_seconds: float


def _determine_status(database_ok: bool, detection_engine_ok: bool) -> str:
    """Determine overall system status based on component health.

    - Both healthy → "healthy"
    - One unhealthy → "degraded"
    - Both unhealthy → "unhealthy"
    """
    if database_ok and detection_engine_ok:
        return "healthy"
    elif not database_ok and not detection_engine_ok:
        return "unhealthy"
    else:
        return "degraded"


async def _is_detection_engine_active() -> bool:
    """Check if the detection engine worker is running.

    This checks the app state for the detection worker instance.
    If not yet wired up (e.g., during testing), defaults to False.
    """
    # This will be replaced by app state injection when the main app is wired.
    # For now, we accept it as a module-level flag that can be set externally.
    return _detection_engine_active


# Module-level flag for detection engine status.
# Will be updated by the main app when the detection worker starts/stops.
_detection_engine_active: bool = False


def set_detection_engine_active(active: bool) -> None:
    """Set the detection engine active state.

    Called by the main application when the detection worker starts or stops.
    """
    global _detection_engine_active
    _detection_engine_active = active


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns server status, database connectivity, detection engine state,
    and uptime. Designed to respond within 500ms.
    """
    database_ok = await check_db_connection()
    detection_engine_ok = _detection_engine_active
    status = _determine_status(database_ok, detection_engine_ok)
    uptime = time.time() - _start_time

    return HealthResponse(
        status=status,
        database=database_ok,
        detection_engine_active=detection_engine_ok,
        uptime_seconds=round(uptime, 2),
    )
