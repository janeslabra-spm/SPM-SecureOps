"""Desk zone configuration persistence functions.

Implements a singleton row pattern (id=1) for the desk zone configuration,
ensuring exactly one row exists with configurable percentage-based boundaries.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import DeskZoneConfig


def _utcnow_naive() -> datetime:
    """Return current UTC time as a timezone-naive datetime.

    The database column is TIMESTAMP WITHOUT TIME ZONE, so we must
    not pass timezone-aware values to asyncpg.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_desk_zone(session: AsyncSession) -> DeskZoneConfig:
    """Get the current desk zone config. Creates default row if none exists.

    Default values: x1=20, y1=35, x2=80, y2=75

    Args:
        session: An active async database session.

    Returns:
        The singleton DeskZoneConfig row.
    """
    result = await session.execute(
        select(DeskZoneConfig).where(DeskZoneConfig.id == 1)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = DeskZoneConfig(
            id=1,
            x1_percent=20,
            y1_percent=35,
            x2_percent=80,
            y2_percent=75,
            updated_at=_utcnow_naive(),
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)

    return config


async def upsert_desk_zone(
    session: AsyncSession,
    x1_percent: int,
    y1_percent: int,
    x2_percent: int,
    y2_percent: int,
) -> DeskZoneConfig:
    """Create or update the desk zone configuration (singleton row, id=1).

    Updates the updated_at timestamp on save.

    Args:
        session: An active async database session.
        x1_percent: Left boundary as percentage (0-100).
        y1_percent: Top boundary as percentage (0-100).
        x2_percent: Right boundary as percentage (0-100).
        y2_percent: Bottom boundary as percentage (0-100).

    Returns:
        The updated DeskZoneConfig row.
    """
    result = await session.execute(
        select(DeskZoneConfig).where(DeskZoneConfig.id == 1)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = DeskZoneConfig(
            id=1,
            x1_percent=x1_percent,
            y1_percent=y1_percent,
            x2_percent=x2_percent,
            y2_percent=y2_percent,
            updated_at=_utcnow_naive(),
        )
        session.add(config)
    else:
        config.x1_percent = x1_percent
        config.y1_percent = y1_percent
        config.x2_percent = x2_percent
        config.y2_percent = y2_percent
        config.updated_at = _utcnow_naive()

    await session.commit()
    await session.refresh(config)
    return config
