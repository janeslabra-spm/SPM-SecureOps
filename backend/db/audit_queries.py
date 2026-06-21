"""Async query functions for audit log management.

Provides insert and query operations for the AuditLog model.
"""

import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AuditLog


async def insert_audit_log(
    session: AsyncSession,
    event_type: str,
    description: str,
    actor: str = "system",
    metadata: dict | None = None,
) -> AuditLog:
    """Insert a new audit log entry.

    Args:
        session: The async database session.
        event_type: Category of the event (e.g., 'status_change', 'system_start').
        description: Human-readable description of the event.
        actor: Who or what triggered the event (defaults to 'system').
        metadata: Optional dictionary of additional event data.

    Returns:
        The newly created AuditLog record.
    """
    log_entry = AuditLog(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        description=description,
        actor=actor,
        metadata_json=json.dumps(metadata) if metadata else "{}",
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


async def query_audit_logs(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    event_type: str | None = None,
    actor: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    """Query audit logs with optional filters, ordered by timestamp DESC.

    Args:
        session: The async database session.
        start_date: If provided, only include logs on or after this date.
        end_date: If provided, only include logs on or before this date.
        event_type: If provided, filter by exact event type.
        actor: If provided, filter by actor.
        limit: Maximum number of results (capped at 200).

    Returns:
        List of AuditLog records matching the filters.
    """
    capped_limit = min(limit, 200)
    stmt = select(AuditLog)

    if start_date is not None:
        start_datetime = datetime(start_date.year, start_date.month, start_date.day)
        stmt = stmt.where(AuditLog.timestamp >= start_datetime)

    if end_date is not None:
        end_datetime = datetime(
            end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999
        )
        stmt = stmt.where(AuditLog.timestamp <= end_datetime)

    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)

    if actor is not None:
        stmt = stmt.where(AuditLog.actor == actor)

    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(capped_limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())
