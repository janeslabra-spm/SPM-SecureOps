"""Audit log API endpoints.

Provides endpoints for listing and querying system audit logs.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.audit_queries import query_audit_logs
from backend.db.session import get_db_session


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry."""

    log_id: int
    timestamp: datetime
    event_type: str
    description: str
    actor: str
    metadata_json: str


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    event_type: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditLogResponse]:
    """Return a filtered list of audit logs, max 200, sorted by timestamp DESC.

    Query parameters:
    - start_date: Only include logs on or after this date.
    - end_date: Only include logs on or before this date.
    - event_type: Filter by event type (e.g., status_change, system_start, detection).
    - actor: Filter by actor (e.g., system, user).
    """
    logs = await query_audit_logs(
        session=session,
        start_date=start_date,
        end_date=end_date,
        event_type=event_type,
        actor=actor,
    )
    return [
        AuditLogResponse(
            log_id=log.log_id,
            timestamp=log.timestamp,
            event_type=log.event_type,
            description=log.description,
            actor=log.actor,
            metadata_json=log.metadata_json,
        )
        for log in logs
    ]
