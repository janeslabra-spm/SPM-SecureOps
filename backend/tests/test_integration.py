"""Backend integration tests for the Security Monitoring System.

Tests the full detection pipeline, database lifecycle, retention end-to-end,
startup sequence, and MJPEG streaming.

Requirements validated: 1.1, 3.2, 4.1, 5.1, 8.5
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.detector import Detection
from backend.core.incident_logger import IncidentConfig, IncidentLogger
from backend.core.rules import (
    DOCUMENT_LEFT_ON_DESK,
    PHONE_NEAR_PERSON,
    PHONE_ON_TABLE,
    IncidentCandidate,
    classify_incidents,
)
from backend.db.models import Base, Incident
from backend.db.queries import (
    delete_expired_incidents,
    get_incident_by_id,
    insert_incident,
    query_incidents,
    update_incident_status,
)
from backend.routers.health import router as health_router, set_detection_engine_active
from backend.routers.stream import router as stream_router
from backend.workers.retention_service import RetentionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory async SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    """Create an async session factory bound to the in-memory database."""
    factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    return factory


@pytest_asyncio.fixture
async def session(session_factory):
    """Create a single async session for test use."""
    async with session_factory() as sess:
        yield sess


@pytest.fixture
def screenshot_dir(tmp_path):
    """Create a temporary screenshot directory."""
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    return screenshots


@pytest.fixture
def fake_frame():
    """Create a fake BGR frame (numpy array) for testing."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 1. Full Detection Pipeline Test
# ---------------------------------------------------------------------------


class TestFullDetectionPipeline:
    """Integration test: frame → detections → classification → incident logging.

    Validates Requirements: 1.1, 3.2
    """

    def test_detection_to_classification_pipeline(self):
        """Mock detector output feeds into classify_incidents correctly."""
        # Simulate detections: a person and a cell phone near each other
        detections = [
            Detection(label="person", confidence=0.92, bbox=(100, 100, 300, 400), class_id=0),
            Detection(label="cell phone", confidence=0.85, bbox=(150, 200, 200, 260), class_id=67),
        ]

        # Desk zone covers center of frame
        table_zone = (50, 50, 500, 450)

        # Classify
        candidates = classify_incidents(detections, table_zone, proximity_pixels=80)

        # The phone overlaps with the person, so should be PHONE_NEAR_PERSON
        assert len(candidates) == 1
        assert candidates[0].incident_type == PHONE_NEAR_PERSON
        assert candidates[0].confidence == 0.85
        assert candidates[0].phone_bbox == (150, 200, 200, 260)
        assert candidates[0].person_bbox == (100, 100, 300, 400)

    def test_phone_on_table_when_no_person_nearby(self):
        """Phone on table with no person nearby classifies as PHONE_ON_TABLE."""
        detections = [
            Detection(label="cell phone", confidence=0.78, bbox=(250, 250, 300, 300), class_id=67),
        ]

        # Desk zone covers the phone center
        table_zone = (200, 200, 400, 400)

        candidates = classify_incidents(detections, table_zone, proximity_pixels=80)

        assert len(candidates) == 1
        assert candidates[0].incident_type == PHONE_ON_TABLE
        assert candidates[0].confidence == 0.78

    def test_document_on_desk_classification(self):
        """Book/document center inside desk zone classifies as DOCUMENT_LEFT_ON_DESK."""
        detections = [
            Detection(label="book", confidence=0.70, bbox=(300, 300, 400, 380), class_id=73),
        ]

        table_zone = (200, 200, 500, 500)

        candidates = classify_incidents(detections, table_zone, proximity_pixels=80)

        assert len(candidates) == 1
        assert candidates[0].incident_type == DOCUMENT_LEFT_ON_DESK

    @pytest.mark.asyncio
    async def test_pipeline_to_incident_logging(self, session_factory, screenshot_dir, fake_frame):
        """Full pipeline: detections → classify → IncidentLogger creates DB record."""
        # Set up IncidentLogger with zero duration threshold for immediate logging
        logger = IncidentLogger(
            db_session_factory=session_factory,
            screenshot_dir=screenshot_dir,
            config=IncidentConfig(duration_threshold=0.0, cooldown_seconds=0.0),
        )

        # Simulate detections and classification
        detections = [
            Detection(label="cell phone", confidence=0.88, bbox=(300, 300, 350, 350), class_id=67),
        ]
        table_zone = (200, 200, 500, 500)
        candidates = classify_incidents(detections, table_zone, proximity_pixels=80)

        assert len(candidates) == 1

        # Log the incident
        with patch("backend.core.incident_logger.cv2.imencode") as mock_imencode:
            mock_imencode.return_value = (True, MagicMock(tobytes=lambda: b"\xff\xd8fake"))
            incident_id = await logger.try_log_incident(
                candidate=candidates[0],
                frame=fake_frame,
                camera_name="Camera 1",
                location="Test Floor",
            )

        assert incident_id is not None

        # Verify the record was created in the database
        async with session_factory() as session:
            incident = await get_incident_by_id(session, incident_id)
            assert incident is not None
            assert incident.incident_type == PHONE_ON_TABLE
            assert incident.confidence == 0.88
            assert incident.camera_name == "Camera 1"
            assert incident.location == "Test Floor"
            assert incident.status == "Pending Review"


# ---------------------------------------------------------------------------
# 2. Database Lifecycle Test
# ---------------------------------------------------------------------------


class TestDatabaseLifecycle:
    """Integration test: create, query, update incidents in the database.

    Validates Requirements: 3.2, 6.1, 6.2
    """

    @pytest.mark.asyncio
    async def test_insert_and_query_incident(self, session):
        """Insert an incident and query it back."""
        incident = await insert_incident(
            session=session,
            timestamp=datetime(2025, 6, 10, 14, 30, 0),
            incident_type=PHONE_ON_TABLE,
            confidence=0.85,
            camera_name="Camera 1",
            location="Production Floor",
            screenshot_path="/screenshots/test.jpg",
            status="Pending Review",
            notes="",
        )

        assert incident.incident_id is not None
        assert incident.incident_type == PHONE_ON_TABLE

        # Query back
        fetched = await get_incident_by_id(session, incident.incident_id)
        assert fetched is not None
        assert fetched.confidence == 0.85
        assert fetched.camera_name == "Camera 1"

    @pytest.mark.asyncio
    async def test_query_with_filters(self, session):
        """Query incidents with type and status filters."""
        # Insert multiple incidents
        await insert_incident(
            session=session,
            timestamp=datetime(2025, 6, 10, 10, 0, 0),
            incident_type=PHONE_ON_TABLE,
            confidence=0.80,
            camera_name="Camera 1",
            location="Floor A",
        )
        await insert_incident(
            session=session,
            timestamp=datetime(2025, 6, 10, 11, 0, 0),
            incident_type=PHONE_NEAR_PERSON,
            confidence=0.90,
            camera_name="Camera 2",
            location="Floor B",
        )
        await insert_incident(
            session=session,
            timestamp=datetime(2025, 6, 10, 12, 0, 0),
            incident_type=PHONE_ON_TABLE,
            confidence=0.75,
            camera_name="Camera 1",
            location="Floor A",
            status="Confirmed",
        )

        # Filter by type
        phone_table_incidents = await query_incidents(
            session, incident_type=PHONE_ON_TABLE
        )
        assert len(phone_table_incidents) == 2
        assert all(i.incident_type == PHONE_ON_TABLE for i in phone_table_incidents)

        # Filter by status
        confirmed = await query_incidents(session, status="Confirmed")
        assert len(confirmed) == 1
        assert confirmed[0].status == "Confirmed"

    @pytest.mark.asyncio
    async def test_update_incident_status(self, session):
        """Update incident status from Pending Review to Confirmed."""
        incident = await insert_incident(
            session=session,
            timestamp=datetime(2025, 6, 10, 14, 0, 0),
            incident_type=PHONE_NEAR_PERSON,
            confidence=0.92,
            camera_name="Camera 1",
            location="Floor C",
        )

        assert incident.status == "Pending Review"

        updated = await update_incident_status(session, incident.incident_id, "Confirmed")
        assert updated is not None
        assert updated.status == "Confirmed"

        # Verify persistence
        fetched = await get_incident_by_id(session, incident.incident_id)
        assert fetched.status == "Confirmed"

    @pytest.mark.asyncio
    async def test_update_nonexistent_incident_returns_none(self, session):
        """Updating a non-existent incident returns None."""
        result = await update_incident_status(session, 99999, "Confirmed")
        assert result is None

    @pytest.mark.asyncio
    async def test_query_results_sorted_desc_by_timestamp(self, session):
        """Query results are sorted by timestamp in descending order."""
        timestamps = [
            datetime(2025, 6, 10, 8, 0, 0),
            datetime(2025, 6, 10, 12, 0, 0),
            datetime(2025, 6, 10, 10, 0, 0),
        ]

        for ts in timestamps:
            await insert_incident(
                session=session,
                timestamp=ts,
                incident_type=PHONE_ON_TABLE,
                confidence=0.80,
                camera_name="Camera 1",
                location="Floor A",
            )

        results = await query_incidents(session)
        assert len(results) == 3
        # Should be sorted descending: 12:00, 10:00, 08:00
        assert results[0].timestamp == datetime(2025, 6, 10, 12, 0, 0)
        assert results[1].timestamp == datetime(2025, 6, 10, 10, 0, 0)
        assert results[2].timestamp == datetime(2025, 6, 10, 8, 0, 0)


# ---------------------------------------------------------------------------
# 3. Retention End-to-End Test
# ---------------------------------------------------------------------------


class TestRetentionEndToEnd:
    """Integration test: insert expired records, run cleanup, verify deletion.

    Validates Requirements: 4.1
    """

    @pytest.mark.asyncio
    async def test_expired_records_deleted_recent_preserved(
        self, session_factory, screenshot_dir
    ):
        """Records older than 7 days are deleted; recent ones preserved."""
        now = datetime.now()
        old_timestamp = now - timedelta(days=10)
        recent_timestamp = now - timedelta(days=2)

        async with session_factory() as session:
            # Insert an old incident
            old_incident = await insert_incident(
                session=session,
                timestamp=old_timestamp,
                incident_type=PHONE_ON_TABLE,
                confidence=0.80,
                camera_name="Camera 1",
                location="Floor A",
                screenshot_path=str(screenshot_dir / "old_screenshot.jpg"),
            )
            # Insert a recent incident
            recent_incident = await insert_incident(
                session=session,
                timestamp=recent_timestamp,
                incident_type=PHONE_NEAR_PERSON,
                confidence=0.90,
                camera_name="Camera 2",
                location="Floor B",
                screenshot_path=str(screenshot_dir / "recent_screenshot.jpg"),
            )

        # Create fake screenshot files
        old_screenshot = screenshot_dir / "old_screenshot.jpg"
        old_screenshot.write_text("old image data")
        recent_screenshot = screenshot_dir / "recent_screenshot.jpg"
        recent_screenshot.write_text("recent image data")

        # Run retention cleanup
        service = RetentionService(
            db_session_factory=session_factory,
            screenshot_dir=screenshot_dir,
        )
        result = await service.run_cleanup()

        # Verify old record deleted, recent preserved
        assert result.deleted_records == 1
        assert result.deleted_files == 1

        # Old screenshot should be removed
        assert not old_screenshot.exists()
        # Recent screenshot should still exist
        assert recent_screenshot.exists()

        # Verify in DB
        async with session_factory() as session:
            old_fetched = await get_incident_by_id(session, old_incident.incident_id)
            assert old_fetched is None

            recent_fetched = await get_incident_by_id(session, recent_incident.incident_id)
            assert recent_fetched is not None

    @pytest.mark.asyncio
    async def test_orphan_screenshots_deleted(self, session_factory, screenshot_dir):
        """Orphan screenshot files (unreferenced, older than 7 days) are deleted."""
        # Create an orphan file with an old modification time
        orphan_file = screenshot_dir / "orphan_old.jpg"
        orphan_file.write_text("orphan data")
        # Set modification time to 10 days ago
        old_mtime = time.time() - (10 * 24 * 3600)
        os.utime(orphan_file, (old_mtime, old_mtime))

        # Create a recent orphan file (should be preserved)
        recent_orphan = screenshot_dir / "orphan_recent.jpg"
        recent_orphan.write_text("recent orphan data")

        # Run retention cleanup
        service = RetentionService(
            db_session_factory=session_factory,
            screenshot_dir=screenshot_dir,
        )
        result = await service.run_cleanup()

        # Old orphan should be deleted
        assert not orphan_file.exists()
        assert result.orphan_files_deleted == 1

        # Recent orphan should be preserved
        assert recent_orphan.exists()

    @pytest.mark.asyncio
    async def test_missing_screenshot_file_handled_gracefully(
        self, session_factory, screenshot_dir
    ):
        """Cleanup handles missing screenshot files without raising errors."""
        old_timestamp = datetime.now() - timedelta(days=10)

        async with session_factory() as session:
            await insert_incident(
                session=session,
                timestamp=old_timestamp,
                incident_type=PHONE_ON_TABLE,
                confidence=0.75,
                camera_name="Camera 1",
                location="Floor A",
                screenshot_path=str(screenshot_dir / "nonexistent.jpg"),
            )

        service = RetentionService(
            db_session_factory=session_factory,
            screenshot_dir=screenshot_dir,
        )
        result = await service.run_cleanup()

        # Record should still be deleted even though file doesn't exist
        assert result.deleted_records == 1
        assert result.deleted_files == 0
        assert result.errors == []


# ---------------------------------------------------------------------------
# 4. Startup Sequence Test
# ---------------------------------------------------------------------------


class TestStartupSequence:
    """Integration test: startup sequence with health check and router registration.

    Validates Requirements: 8.5
    """

    def test_health_endpoint_returns_200(self):
        """Health endpoint responds with 200 and expected structure."""
        app = FastAPI()
        app.include_router(health_router)

        with patch("backend.routers.health.check_db_connection", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = True
            set_detection_engine_active(True)

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] is True
            assert data["detection_engine_active"] is True
            assert "uptime_seconds" in data

    def test_all_routers_registered(self):
        """All required routers are registered and accessible."""
        from backend.routers.incidents import router as incidents_router
        from backend.routers.zones import router as zones_router

        app = FastAPI()
        app.include_router(health_router)
        app.include_router(stream_router)
        app.include_router(incidents_router)
        app.include_router(zones_router)

        # Collect all route paths
        routes = [route.path for route in app.routes]

        # Verify key endpoints are registered
        assert "/health" in routes
        assert "/stream/video.mjpg" in routes
        assert "/stream/status" in routes
        assert "/incidents" in routes or "/incidents/" in routes
        assert "/zones/desk" in routes or "/zones/desk/" in routes

    def test_health_endpoint_degraded_when_db_unavailable(self):
        """Health reports degraded when DB is unavailable."""
        app = FastAPI()
        app.include_router(health_router)

        with patch("backend.routers.health.check_db_connection", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = False
            set_detection_engine_active(True)

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] is False


# ---------------------------------------------------------------------------
# 5. MJPEG Streaming Test
# ---------------------------------------------------------------------------


class TestMJPEGStreaming:
    """Integration test: MJPEG streaming endpoint delivers frames in multipart format.

    Validates Requirements: 5.1
    """

    def test_stream_returns_503_when_no_worker(self):
        """Streaming returns 503 when detection worker is not available."""
        app = FastAPI()
        app.include_router(stream_router)
        app.state.detection_worker = None

        client = TestClient(app)
        response = client.get("/stream/video.mjpg")

        assert response.status_code == 503
        assert response.json() == {"detail": "Monitoring is not active"}
        assert response.headers["cache-control"] == "no-cache"

    def test_stream_delivers_mjpeg_frames(self):
        """Streaming endpoint delivers JPEG frames in multipart format."""
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake JPEG header + data

        class SingleFrameWorker:
            """Worker that delivers one frame then stops."""

            is_running = True
            _delivered = False

            def wait_for_frame(self, last_frame_id: int, timeout: float = 2.0):
                if not self._delivered:
                    self._delivered = True
                    return (1, fake_jpeg)
                self.is_running = False
                return (last_frame_id, None)

        app = FastAPI()
        app.include_router(stream_router)
        app.state.detection_worker = SingleFrameWorker()

        client = TestClient(app)

        with client.stream("GET", "/stream/video.mjpg") as response:
            assert response.status_code == 200
            content_type = response.headers["content-type"]
            assert "multipart/x-mixed-replace" in content_type
            assert "boundary=frame" in content_type
            assert response.headers["cache-control"] == "no-cache"

            # Read the streamed content
            content = response.read()
            # Verify multipart format
            assert b"--frame\r\n" in content
            assert b"Content-Type: image/jpeg\r\n\r\n" in content
            assert fake_jpeg in content

    def test_stream_status_returns_metrics(self):
        """Status endpoint returns correct metrics from worker."""

        class MetricsWorker:
            is_running = True

            def get_status(self):
                return {
                    "people": 2,
                    "phones": 1,
                    "active_rule_matches": 1,
                    "logged_this_frame": 0,
                    "inference_ms": 35.5,
                    "fps": 2.5,
                    "message": "",
                }

        app = FastAPI()
        app.include_router(stream_router)
        app.state.detection_worker = MetricsWorker()

        client = TestClient(app)
        response = client.get("/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert data["people"] == 2
        assert data["phones"] == 1
        assert data["active_rule_matches"] == 1
        assert data["inference_ms"] == 35.5
        assert data["fps"] == 2.5
        assert response.headers["cache-control"] == "no-cache"

    def test_stream_multiple_frames(self):
        """Streaming endpoint delivers multiple frames sequentially."""
        frame1 = b"\xff\xd8\xff\xe0frame_one_data"
        frame2 = b"\xff\xd8\xff\xe0frame_two_data"

        class MultiFrameWorker:
            """Worker that delivers two frames then stops."""

            is_running = True
            _frame_count = 0

            def wait_for_frame(self, last_frame_id: int, timeout: float = 2.0):
                self._frame_count += 1
                if self._frame_count == 1:
                    return (1, frame1)
                elif self._frame_count == 2:
                    return (2, frame2)
                self.is_running = False
                return (last_frame_id, None)

        app = FastAPI()
        app.include_router(stream_router)
        app.state.detection_worker = MultiFrameWorker()

        client = TestClient(app)

        with client.stream("GET", "/stream/video.mjpg") as response:
            assert response.status_code == 200
            content = response.read()
            # Both frames should be present in the multipart stream
            assert frame1 in content
            assert frame2 in content
            # Each frame should be preceded by the boundary
            assert content.count(b"--frame\r\n") >= 2
