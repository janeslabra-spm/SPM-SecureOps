"""Tests for desk zone persistence functions."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, DeskZoneConfig
from backend.db.desk_zone import get_desk_zone, upsert_desk_zone


@pytest_asyncio.fixture
async def async_session():
    """Create an in-memory SQLite async session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_desk_zone_creates_default_when_empty(async_session: AsyncSession):
    """get_desk_zone returns a row with default values when no row exists."""
    config = await get_desk_zone(async_session)

    assert config is not None
    assert config.id == 1
    assert config.x1_percent == 20
    assert config.y1_percent == 35
    assert config.x2_percent == 80
    assert config.y2_percent == 75
    assert config.updated_at is not None


@pytest.mark.asyncio
async def test_get_desk_zone_returns_existing_row(async_session: AsyncSession):
    """get_desk_zone returns the existing row without creating a new one."""
    # First call creates the default
    config1 = await get_desk_zone(async_session)
    # Second call returns the same row
    config2 = await get_desk_zone(async_session)

    assert config1.id == config2.id
    assert config1.x1_percent == config2.x1_percent
    assert config1.y1_percent == config2.y1_percent
    assert config1.x2_percent == config2.x2_percent
    assert config1.y2_percent == config2.y2_percent


@pytest.mark.asyncio
async def test_upsert_desk_zone_creates_new_row(async_session: AsyncSession):
    """upsert_desk_zone creates the singleton row when none exists."""
    config = await upsert_desk_zone(async_session, 10, 20, 90, 95)

    assert config.id == 1
    assert config.x1_percent == 10
    assert config.y1_percent == 20
    assert config.x2_percent == 90
    assert config.y2_percent == 95


@pytest.mark.asyncio
async def test_upsert_desk_zone_updates_existing_row(async_session: AsyncSession):
    """upsert_desk_zone updates values on the existing row."""
    # Create initial row
    await upsert_desk_zone(async_session, 10, 20, 90, 95)

    # Update values
    config = await upsert_desk_zone(async_session, 5, 15, 85, 70)

    assert config.id == 1
    assert config.x1_percent == 5
    assert config.y1_percent == 15
    assert config.x2_percent == 85
    assert config.y2_percent == 70


@pytest.mark.asyncio
async def test_upsert_desk_zone_updates_timestamp(async_session: AsyncSession):
    """upsert_desk_zone updates the updated_at timestamp on each save."""
    config1 = await upsert_desk_zone(async_session, 10, 20, 90, 95)
    ts1 = config1.updated_at

    config2 = await upsert_desk_zone(async_session, 30, 40, 60, 50)
    ts2 = config2.updated_at

    assert ts2 >= ts1


@pytest.mark.asyncio
async def test_get_desk_zone_after_upsert(async_session: AsyncSession):
    """get_desk_zone returns the values set by upsert_desk_zone."""
    await upsert_desk_zone(async_session, 15, 25, 75, 65)

    config = await get_desk_zone(async_session)

    assert config.x1_percent == 15
    assert config.y1_percent == 25
    assert config.x2_percent == 75
    assert config.y2_percent == 65
