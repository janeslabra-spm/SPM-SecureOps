"""Desk zone configuration API endpoints.

Provides GET and PUT endpoints for managing the desk zone boundaries
used by the Rule Engine for violation classification.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.desk_zone import get_desk_zone, upsert_desk_zone
from backend.db.session import get_db_session

router = APIRouter(prefix="/zones", tags=["zones"])


class DeskZoneConfig(BaseModel):
    """Pydantic schema for desk zone configuration.

    All values are integer percentages relative to the camera frame dimensions.
    Each value must be in the range [0, 100] inclusive.
    """

    x1_percent: int = Field(ge=0, le=100, default=20)
    y1_percent: int = Field(ge=0, le=100, default=35)
    x2_percent: int = Field(ge=0, le=100, default=80)
    y2_percent: int = Field(ge=0, le=100, default=75)


@router.get("/desk", response_model=DeskZoneConfig)
async def get_desk_zone_config(
    session: AsyncSession = Depends(get_db_session),
) -> DeskZoneConfig:
    """Return the current desk zone configuration.

    If no configuration has been set, returns the default values
    (x1=20, y1=35, x2=80, y2=75).
    """
    config = await get_desk_zone(session)
    return DeskZoneConfig(
        x1_percent=config.x1_percent,
        y1_percent=config.y1_percent,
        x2_percent=config.x2_percent,
        y2_percent=config.y2_percent,
    )


@router.put("/desk", response_model=DeskZoneConfig)
async def update_desk_zone_config(
    body: DeskZoneConfig,
    session: AsyncSession = Depends(get_db_session),
) -> DeskZoneConfig:
    """Update the desk zone configuration.

    Validates that all percentage values are within [0, 100].
    Persists to the database before confirming acceptance.
    Returns 422 if any value is out of range.
    """
    config = await upsert_desk_zone(
        session,
        x1_percent=body.x1_percent,
        y1_percent=body.y1_percent,
        x2_percent=body.x2_percent,
        y2_percent=body.y2_percent,
    )
    return DeskZoneConfig(
        x1_percent=config.x1_percent,
        y1_percent=config.y1_percent,
        x2_percent=config.x2_percent,
        y2_percent=config.y2_percent,
    )
