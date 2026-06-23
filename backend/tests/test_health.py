"""Unit tests for the health check endpoint."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.health import (
    HealthResponse,
    _determine_status,
    router,
    set_detection_engine_active,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with the health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestDetermineStatus:
    """Tests for the status determination logic."""

    def test_both_healthy(self):
        assert _determine_status(True, True) == "healthy"

    def test_database_unhealthy_only(self):
        assert _determine_status(False, True) == "degraded"

    def test_detection_engine_unhealthy_only(self):
        assert _determine_status(True, False) == "degraded"

    def test_both_unhealthy(self):
        assert _determine_status(False, False) == "unhealthy"


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_healthy_response(self, mock_db_check, client):
        """When both DB and detection engine are healthy, status is 'healthy'."""
        mock_db_check.return_value = True
        set_detection_engine_active(True)

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] is True
        assert data["detection_engine_active"] is True
        assert data["uptime_seconds"] >= 0

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_degraded_db_down(self, mock_db_check, client):
        """When DB is down but detection engine is active, status is 'degraded'."""
        mock_db_check.return_value = False
        set_detection_engine_active(True)

        response = client.get("/health")
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] is False
        assert data["detection_engine_active"] is True

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_degraded_detection_down(self, mock_db_check, client):
        """When detection engine is down but DB is up, status is 'degraded'."""
        mock_db_check.return_value = True
        set_detection_engine_active(False)

        response = client.get("/health")
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] is True
        assert data["detection_engine_active"] is False

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_unhealthy_both_down(self, mock_db_check, client):
        """When both DB and detection engine are down, status is 'unhealthy'."""
        mock_db_check.return_value = False
        set_detection_engine_active(False)

        response = client.get("/health")
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] is False
        assert data["detection_engine_active"] is False

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_response_includes_uptime(self, mock_db_check, client):
        """Response includes a non-negative uptime_seconds value."""
        mock_db_check.return_value = True
        set_detection_engine_active(True)

        response = client.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    @patch("backend.routers.health.check_db_connection", new_callable=AsyncMock)
    def test_response_model_validation(self, mock_db_check, client):
        """Response conforms to HealthResponse schema."""
        mock_db_check.return_value = True
        set_detection_engine_active(True)

        response = client.get("/health")
        data = response.json()
        # Validate all required fields are present
        health = HealthResponse(**data)
        assert health.status in ("healthy", "degraded", "unhealthy")
        assert isinstance(health.database, bool)
        assert isinstance(health.detection_engine_active, bool)
        assert isinstance(health.uptime_seconds, float)
