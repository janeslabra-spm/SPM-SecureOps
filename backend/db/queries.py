"""Async query functions for incident management.

Provides CRUD operations and filtered queries for the Incident model
using async SQLAlchemy sessions.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Incident


async def query_incidents(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    incident_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[Incident]:
    """Query incidents with optional filters, max 100 results, ordered by timestamp DESC.

    Args:
        session: The async database session.
        start_date: If provided, only include incidents on or after this date.
        end_date: If provided, only include incidents on or before this date (inclusive, end of day).
        incident_type: If provided, filter by exact incident type match.
        status: If provided, filter by exact status match.
        limit: Maximum number of results to return (capped at 100).

    Returns:
        List of Incident records matching the filters, ordered by timestamp DESC.
    """
    # Enforce maximum of 100 records
    capped_limit = min(limit, 100)

    stmt = select(Incident)

    # Apply filters
    if start_date is not None:
        start_datetime = datetime(start_date.year, start_date.month, start_date.day)
        stmt = stmt.where(Incident.timestamp >= start_datetime)

    if end_date is not None:
        # Include the entire end date (up to end of day)
        end_datetime = datetime(
            end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999
        )
        stmt = stmt.where(Incident.timestamp <= end_datetime)

    if incident_type is not None:
        stmt = stmt.where(Incident.incident_type == incident_type)

    if status is not None:
        stmt = stmt.where(Incident.status == status)

    # Always order by timestamp descending
    stmt = stmt.order_by(Incident.timestamp.desc())

    # Apply limit
    stmt = stmt.limit(capped_limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_incident_by_id(
    session: AsyncSession, incident_id: int
) -> Incident | None:
    """Get a single incident by ID, or None if not found.

    Args:
        session: The async database session.
        incident_id: The unique identifier of the incident.

    Returns:
        The Incident record if found, or None.
    """
    stmt = select(Incident).where(Incident.incident_id == incident_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_incident_status(
    session: AsyncSession, incident_id: int, new_status: str
) -> Incident | None:
    """Update incident status. Returns updated incident or None if not found.

    Args:
        session: The async database session.
        incident_id: The unique identifier of the incident to update.
        new_status: The new status value (should be one of the valid statuses).

    Returns:
        The updated Incident record, or None if the incident was not found.
    """
    incident = await get_incident_by_id(session, incident_id)
    if incident is None:
        return None

    incident.status = new_status
    await session.commit()
    await session.refresh(incident)
    return incident


async def insert_incident(
    session: AsyncSession,
    timestamp: datetime,
    incident_type: str,
    confidence: float,
    camera_name: str,
    location: str,
    screenshot_path: str = "",
    status: str = "Pending Review",
    notes: str = "",
) -> Incident:
    """Insert a new incident record and return it.

    Args:
        session: The async database session.
        timestamp: When the incident occurred.
        incident_type: Type of violation detected.
        confidence: Detection confidence score (0.0 to 1.0).
        camera_name: Name/identifier of the camera source.
        location: Description of where the incident occurred.
        screenshot_path: Path to the evidence screenshot file.
        status: Initial review status (defaults to "Pending Review").
        notes: Additional notes or error information.

    Returns:
        The newly created Incident record with auto-generated incident_id.
    """
    incident = Incident(
        timestamp=timestamp,
        incident_type=incident_type,
        confidence=confidence,
        camera_name=camera_name,
        location=location,
        screenshot_path=screenshot_path,
        status=status,
        notes=notes,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


async def delete_expired_incidents(
    session: AsyncSession, retention_days: int = 7
) -> list[Incident]:
    """Delete and return incidents older than retention_days.

    Finds all incidents with timestamps older than the retention period,
    collects them for caller to handle screenshot cleanup, then deletes
    the records from the database.

    Args:
        session: The async database session.
        retention_days: Number of days to retain records (default 7).

    Returns:
        List of deleted Incident records (for screenshot cleanup by the caller).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    # For naive datetime comparison, use a naive cutoff as well
    cutoff_naive = cutoff.replace(tzinfo=None)

    # First, fetch the expired incidents so we can return them
    select_stmt = (
        select(Incident)
        .where(Incident.timestamp < cutoff_naive)
        .order_by(Incident.timestamp.desc())
    )
    result = await session.execute(select_stmt)
    expired_incidents = list(result.scalars().all())

    if expired_incidents:
        # Delete the expired records
        expired_ids = [inc.incident_id for inc in expired_incidents]
        delete_stmt = delete(Incident).where(Incident.incident_id.in_(expired_ids))
        await session.execute(delete_stmt)
        await session.commit()

    return expired_incidents
