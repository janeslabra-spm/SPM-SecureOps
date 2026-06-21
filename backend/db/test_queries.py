"""Unit tests for backend.db.queries module.

Uses an in-memory async SQLite database for isolated testing.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.db.models import Base, Incident
from backend.db.queries import (
    query_incidents,
    get_incident_by_id,
    update_incident_status,
    insert_incident,
    delete_expired_incidents,
)


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


@pytest_asyncio.fixture
async def populated_session(async_session: AsyncSession):
    """Session pre-populated with sample incidents."""
    now = datetime.now()
    incidents = [
        Incident(
            timestamp=now - timedelta(hours=i),
            incident_type="PHONE_ON_TABLE" if i % 2 == 0 else "PHONE_NEAR_PERSON",
            confidence=0.8 + (i * 0.01),
            camera_name="cam_1",
            location="Office A",
            screenshot_path=f"/screenshots/inc_{i}.jpg",
            status="Pending Review" if i % 3 != 0 else "Confirmed",
            notes="",
        )
        for i in range(10)
    ]
    async_session.add_all(incidents)
    await async_session.commit()
    return async_session


class TestInsertIncident:
    @pytest.mark.asyncio
    async def test_insert_returns_incident_with_id(self, async_session: AsyncSession):
        result = await insert_incident(
            session=async_session,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            incident_type="PHONE_ON_TABLE",
            confidence=0.85,
            camera_name="cam_1",
            location="Office A",
        )
        assert result.incident_id is not None
        assert result.incident_type == "PHONE_ON_TABLE"
        assert result.confidence == 0.85
        assert result.status == "Pending Review"
        assert result.notes == ""

    @pytest.mark.asyncio
    async def test_insert_with_custom_status_and_notes(self, async_session: AsyncSession):
        result = await insert_incident(
            session=async_session,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            incident_type="PHONE_NEAR_PERSON",
            confidence=0.92,
            camera_name="cam_2",
            location="Lab B",
            status="Confirmed",
            notes="Caught on camera clearly",
        )
        assert result.status == "Confirmed"
        assert result.notes == "Caught on camera clearly"


class TestGetIncidentById:
    @pytest.mark.asyncio
    async def test_returns_incident_when_exists(self, async_session: AsyncSession):
        inserted = await insert_incident(
            session=async_session,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            incident_type="PHONE_ON_TABLE",
            confidence=0.85,
            camera_name="cam_1",
            location="Office A",
        )
        found = await get_incident_by_id(async_session, inserted.incident_id)
        assert found is not None
        assert found.incident_id == inserted.incident_id

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(self, async_session: AsyncSession):
        result = await get_incident_by_id(async_session, 9999)
        assert result is None


class TestUpdateIncidentStatus:
    @pytest.mark.asyncio
    async def test_updates_status_successfully(self, async_session: AsyncSession):
        inserted = await insert_incident(
            session=async_session,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            incident_type="PHONE_ON_TABLE",
            confidence=0.85,
            camera_name="cam_1",
            location="Office A",
        )
        updated = await update_incident_status(
            async_session, inserted.incident_id, "Confirmed"
        )
        assert updated is not None
        assert updated.status == "Confirmed"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_id(self, async_session: AsyncSession):
        result = await update_incident_status(async_session, 9999, "Confirmed")
        assert result is None


class TestQueryIncidents:
    @pytest.mark.asyncio
    async def test_returns_all_when_no_filters(self, populated_session: AsyncSession):
        results = await query_incidents(populated_session)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_ordered_by_timestamp_desc(self, populated_session: AsyncSession):
        results = await query_incidents(populated_session)
        for i in range(len(results) - 1):
            assert results[i].timestamp >= results[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_filter_by_incident_type(self, populated_session: AsyncSession):
        results = await query_incidents(
            populated_session, incident_type="PHONE_ON_TABLE"
        )
        assert all(r.incident_type == "PHONE_ON_TABLE" for r in results)
        assert len(results) == 5  # indices 0, 2, 4, 6, 8

    @pytest.mark.asyncio
    async def test_filter_by_status(self, populated_session: AsyncSession):
        results = await query_incidents(populated_session, status="Confirmed")
        assert all(r.status == "Confirmed" for r in results)

    @pytest.mark.asyncio
    async def test_max_limit_enforced(self, async_session: AsyncSession):
        # Insert 150 records
        now = datetime.now()
        for i in range(150):
            async_session.add(
                Incident(
                    timestamp=now - timedelta(minutes=i),
                    incident_type="PHONE_ON_TABLE",
                    confidence=0.8,
                    camera_name="cam_1",
                    location="Office",
                    screenshot_path="",
                    status="Pending Review",
                    notes="",
                )
            )
        await async_session.commit()

        results = await query_incidents(async_session)
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_limit_capped_at_100(self, async_session: AsyncSession):
        """Even if user passes limit > 100, result is capped at 100."""
        now = datetime.now()
        for i in range(110):
            async_session.add(
                Incident(
                    timestamp=now - timedelta(minutes=i),
                    incident_type="PHONE_ON_TABLE",
                    confidence=0.8,
                    camera_name="cam_1",
                    location="Office",
                    screenshot_path="",
                    status="Pending Review",
                    notes="",
                )
            )
        await async_session.commit()

        results = await query_incidents(async_session, limit=200)
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, async_session: AsyncSession):
        """Filter by start_date and end_date."""
        from datetime import date

        # Insert incidents across multiple days
        async_session.add(
            Incident(
                timestamp=datetime(2024, 3, 10, 12, 0, 0),
                incident_type="PHONE_ON_TABLE",
                confidence=0.8,
                camera_name="cam_1",
                location="Office",
                screenshot_path="",
                status="Pending Review",
                notes="",
            )
        )
        async_session.add(
            Incident(
                timestamp=datetime(2024, 3, 12, 14, 0, 0),
                incident_type="PHONE_NEAR_PERSON",
                confidence=0.9,
                camera_name="cam_1",
                location="Office",
                screenshot_path="",
                status="Pending Review",
                notes="",
            )
        )
        async_session.add(
            Incident(
                timestamp=datetime(2024, 3, 15, 8, 0, 0),
                incident_type="PHONE_ON_TABLE",
                confidence=0.7,
                camera_name="cam_1",
                location="Office",
                screenshot_path="",
                status="Confirmed",
                notes="",
            )
        )
        await async_session.commit()

        # Query for incidents between March 11 and March 13
        results = await query_incidents(
            async_session, start_date=date(2024, 3, 11), end_date=date(2024, 3, 13)
        )
        assert len(results) == 1
        assert results[0].incident_type == "PHONE_NEAR_PERSON"


class TestDeleteExpiredIncidents:
    @pytest.mark.asyncio
    async def test_deletes_expired_records(self, async_session: AsyncSession):
        now = datetime.now()
        # Insert one recent and one expired incident
        async_session.add(
            Incident(
                timestamp=now - timedelta(days=1),
                incident_type="PHONE_ON_TABLE",
                confidence=0.8,
                camera_name="cam_1",
                location="Office",
                screenshot_path="/screenshots/recent.jpg",
                status="Pending Review",
                notes="",
            )
        )
        async_session.add(
            Incident(
                timestamp=now - timedelta(days=10),
                incident_type="PHONE_NEAR_PERSON",
                confidence=0.9,
                camera_name="cam_1",
                location="Office",
                screenshot_path="/screenshots/old.jpg",
                status="Confirmed",
                notes="",
            )
        )
        await async_session.commit()

        deleted = await delete_expired_incidents(async_session, retention_days=7)
        assert len(deleted) == 1
        assert deleted[0].screenshot_path == "/screenshots/old.jpg"

        # Verify only recent remains
        remaining = await query_incidents(async_session)
        assert len(remaining) == 1
        assert remaining[0].screenshot_path == "/screenshots/recent.jpg"

    @pytest.mark.asyncio
    async def test_returns_empty_when_nothing_expired(self, async_session: AsyncSession):
        now = datetime.now()
        async_session.add(
            Incident(
                timestamp=now - timedelta(days=2),
                incident_type="PHONE_ON_TABLE",
                confidence=0.8,
                camera_name="cam_1",
                location="Office",
                screenshot_path="/screenshots/recent.jpg",
                status="Pending Review",
                notes="",
            )
        )
        await async_session.commit()

        deleted = await delete_expired_incidents(async_session, retention_days=7)
        assert len(deleted) == 0
