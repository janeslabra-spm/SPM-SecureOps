"""Incident management API endpoints.

Provides endpoints for listing, filtering, updating status, and exporting
incident records.
"""

import csv
import io
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.queries import get_incident_by_id, query_incidents, update_incident_status
from backend.db.audit_queries import insert_audit_log
from backend.db.session import get_db_session


# --- Pydantic Schemas ---


class StatusUpdateRequest(BaseModel):
    """Request body for updating an incident's review status."""

    status: Literal[
        "Pending Review",
        "Confirmed",
        "False Positive",
        "False Alarm",
        "Warning Issued",
        "Coaching Required",
        "Escalated",
        "Resolved",
    ]


class IncidentResponse(BaseModel):
    """Response schema for a single incident record."""

    incident_id: int
    timestamp: datetime
    incident_type: str
    confidence: float
    camera_name: str
    location: str
    screenshot_path: str
    status: str
    notes: str


# --- Router ---

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    incident_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[IncidentResponse]:
    """Return a filtered list of incidents, max 100, sorted by timestamp DESC.

    Query parameters:
    - start_date: Only include incidents on or after this date.
    - end_date: Only include incidents on or before this date (inclusive).
    - incident_type: Filter by exact incident type.
    - status: Filter by exact review status.
    """
    incidents = await query_incidents(
        session=session,
        start_date=start_date,
        end_date=end_date,
        incident_type=incident_type,
        status=status,
    )
    return [
        IncidentResponse(
            incident_id=inc.incident_id,
            timestamp=inc.timestamp,
            incident_type=inc.incident_type,
            confidence=inc.confidence,
            camera_name=inc.camera_name,
            location=inc.location,
            screenshot_path=inc.screenshot_path,
            status=inc.status,
            notes=inc.notes,
        )
        for inc in incidents
    ]


@router.get("/export")
async def export_incidents_csv(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    incident_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Export filtered incidents as a CSV file.

    The CSV contains the columns: incident_id, timestamp, incident_type,
    confidence, camera_name, location, status, notes.

    Applies the same filters as GET /incidents.
    """
    incidents = await query_incidents(
        session=session,
        start_date=start_date,
        end_date=end_date,
        incident_type=incident_type,
        status=status,
    )

    # Build CSV content in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header row
    columns = [
        "incident_id",
        "timestamp",
        "incident_type",
        "confidence",
        "camera_name",
        "location",
        "status",
        "notes",
    ]
    writer.writerow(columns)

    # Write data rows
    for inc in incidents:
        writer.writerow([
            inc.incident_id,
            inc.timestamp.isoformat() if inc.timestamp else "",
            inc.incident_type,
            inc.confidence,
            inc.camera_name,
            inc.location,
            inc.status,
            inc.notes,
        ])

    # Reset stream position for reading
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidents_export.csv"},
    )


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
async def update_status(
    incident_id: int,
    body: StatusUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> IncidentResponse:
    """Update the review status of an incident.

    Returns the updated incident record. Raises 404 if the incident_id
    does not exist. Invalid status values are rejected with 422 by Pydantic
    validation on the request body.
    """
    # Check if incident exists first
    incident = await get_incident_by_id(session, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=404, detail=f"Incident {incident_id} not found"
        )

    updated = await update_incident_status(session, incident_id, body.status)

    # Log the status change to audit trail
    await insert_audit_log(
        session=session,
        event_type="status_change",
        description=f"Incident #{incident_id} status changed from '{incident.status}' to '{body.status}'",
        actor="user",
        metadata={"incident_id": incident_id, "old_status": incident.status, "new_status": body.status},
    )

    return IncidentResponse(
        incident_id=updated.incident_id,
        timestamp=updated.timestamp,
        incident_type=updated.incident_type,
        confidence=updated.confidence,
        camera_name=updated.camera_name,
        location=updated.location,
        screenshot_path=updated.screenshot_path,
        status=updated.status,
        notes=updated.notes,
    )
