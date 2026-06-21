"""Tests for the streaming endpoints (GET /stream/video.mjpg and GET /stream/status)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.stream import router, StreamStatus


def _create_app(detection_worker=None) -> FastAPI:
    """Create a test FastAPI app with the stream router and optional worker."""
    app = FastAPI()
    app.include_router(router)
    app.state.detection_worker = detection_worker
    return app


class FakeWorker:
    """Fake detection worker for testing active state."""

    def __init__(self, running: bool = True, status: dict | None = None, frame: bytes | None = None):
        self.is_running = running
        self._status = status or {
            "people": 3,
            "phones": 1,
            "active_rule_matches": 1,
            "logged_this_frame": 0,
            "inference_ms": 42.5,
            "fps": 2.0,
            "message": "",
        }
        self._frame = frame or b"\xff\xd8\xff\xe0fake_jpeg_data"
        self._frame_id = 1

    def get_status(self) -> dict:
        return self._status

    def get_latest_frame(self) -> bytes | None:
        return self._frame

    def wait_for_frame(self, last_frame_id: int, timeout: float = 2.0) -> tuple[int, bytes | None]:
        if last_frame_id >= self._frame_id:
            return (last_frame_id, None)
        return (self._frame_id, self._frame)


class TestStreamStatus:
    """Tests for GET /stream/status endpoint."""

    def test_status_returns_503_when_no_worker(self):
        """Should return 503 when no detection worker is set."""
        app = _create_app(detection_worker=None)
        client = TestClient(app)

        response = client.get("/stream/status")

        assert response.status_code == 503
        assert response.json() == {"detail": "Monitoring is not active"}
        assert response.headers["cache-control"] == "no-cache"

    def test_status_returns_503_when_worker_not_running(self):
        """Should return 503 when worker exists but is not running."""
        worker = FakeWorker(running=False)
        app = _create_app(detection_worker=worker)
        client = TestClient(app)

        response = client.get("/stream/status")

        assert response.status_code == 503
        assert response.json() == {"detail": "Monitoring is not active"}
        assert response.headers["cache-control"] == "no-cache"

    def test_status_returns_metrics_when_worker_active(self):
        """Should return JSON metrics when worker is active."""
        worker = FakeWorker(running=True)
        app = _create_app(detection_worker=worker)
        client = TestClient(app)

        response = client.get("/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert data["people"] == 3
        assert data["phones"] == 1
        assert data["active_rule_matches"] == 1
        assert data["logged_this_frame"] == 0
        assert data["inference_ms"] == 42.5
        assert data["fps"] == 2.0
        assert data["message"] == ""
        assert response.headers["cache-control"] == "no-cache"

    def test_status_returns_stream_status_model(self):
        """Should handle worker returning a StreamStatus model directly."""
        status_model = StreamStatus(
            people=5,
            phones=2,
            active_rule_matches=2,
            logged_this_frame=1,
            inference_ms=35.0,
            fps=3.0,
            message="active",
        )

        class ModelWorker:
            is_running = True

            def get_status(self):
                return status_model

        app = _create_app(detection_worker=ModelWorker())
        client = TestClient(app)

        response = client.get("/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert data["people"] == 5
        assert data["phones"] == 2
        assert data["message"] == "active"


class TestStreamVideo:
    """Tests for GET /stream/video.mjpg endpoint."""

    def test_video_returns_503_when_no_worker(self):
        """Should return 503 when no detection worker is set."""
        app = _create_app(detection_worker=None)
        client = TestClient(app)

        response = client.get("/stream/video.mjpg")

        assert response.status_code == 503
        assert response.json() == {"detail": "Monitoring is not active"}
        assert response.headers["cache-control"] == "no-cache"

    def test_video_returns_503_when_worker_not_running(self):
        """Should return 503 when worker exists but is not running."""
        worker = FakeWorker(running=False)
        app = _create_app(detection_worker=worker)
        client = TestClient(app)

        response = client.get("/stream/video.mjpg")

        assert response.status_code == 503
        assert response.json() == {"detail": "Monitoring is not active"}
        assert response.headers["cache-control"] == "no-cache"

    def test_video_returns_mjpeg_stream_when_active(self):
        """Should return multipart MJPEG stream with correct content type."""
        fake_jpeg = b"\xff\xd8\xff\xe0test_frame_data"

        class SingleFrameWorker:
            """Worker that delivers one frame then stops."""
            is_running = True
            _delivered = False

            def wait_for_frame(self, last_frame_id: int, timeout: float = 2.0):
                if not self._delivered:
                    self._delivered = True
                    return (1, fake_jpeg)
                # Stop after first frame
                self.is_running = False
                return (last_frame_id, None)

        worker = SingleFrameWorker()
        app = _create_app(detection_worker=worker)
        client = TestClient(app)

        with client.stream("GET", "/stream/video.mjpg") as response:
            assert response.status_code == 200
            assert "multipart/x-mixed-replace" in response.headers["content-type"]
            assert "boundary=frame" in response.headers["content-type"]
            assert response.headers["cache-control"] == "no-cache"

            # Read the streamed content
            content = response.read()
            assert b"--frame\r\n" in content
            assert b"Content-Type: image/jpeg\r\n\r\n" in content
            assert fake_jpeg in content
