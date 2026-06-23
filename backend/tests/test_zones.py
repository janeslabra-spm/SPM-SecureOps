"""Unit tests for the desk zone configuration endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.db.session import get_db_session
from backend.routers.zones import DeskZoneConfig, router


async def _override_db_session():
    """Mock DB session dependency for tests."""
    yield MagicMock()


@pytest.fixture
def app():
    """Create a test FastAPI app with the zones router and mocked DB session."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_session] = _override_db_session
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


def _make_mock_config(x1=20, y1=35, x2=80, y2=75):
    """Create a mock DeskZoneConfig ORM object."""
    config = MagicMock()
    config.x1_percent = x1
    config.y1_percent = y1
    config.x2_percent = x2
    config.y2_percent = y2
    return config


class TestDeskZoneConfigSchema:
    """Tests for DeskZoneConfig Pydantic validation."""

    def test_valid_defaults(self):
        config = DeskZoneConfig()
        assert config.x1_percent == 20
        assert config.y1_percent == 35
        assert config.x2_percent == 80
        assert config.y2_percent == 75

    def test_valid_custom_values(self):
        config = DeskZoneConfig(
            x1_percent=0, y1_percent=0, x2_percent=100, y2_percent=100
        )
        assert config.x1_percent == 0
        assert config.y1_percent == 0
        assert config.x2_percent == 100
        assert config.y2_percent == 100

    def test_boundary_zero(self):
        config = DeskZoneConfig(
            x1_percent=0, y1_percent=0, x2_percent=0, y2_percent=0
        )
        assert config.x1_percent == 0

    def test_boundary_hundred(self):
        config = DeskZoneConfig(
            x1_percent=100, y1_percent=100, x2_percent=100, y2_percent=100
        )
        assert config.x1_percent == 100

    def test_rejects_negative_x1(self):
        with pytest.raises(Exception):
            DeskZoneConfig(x1_percent=-1, y1_percent=35, x2_percent=80, y2_percent=75)

    def test_rejects_over_100_x2(self):
        with pytest.raises(Exception):
            DeskZoneConfig(x1_percent=20, y1_percent=35, x2_percent=101, y2_percent=75)

    def test_rejects_negative_y1(self):
        with pytest.raises(Exception):
            DeskZoneConfig(x1_percent=20, y1_percent=-5, x2_percent=80, y2_percent=75)

    def test_rejects_over_100_y2(self):
        with pytest.raises(Exception):
            DeskZoneConfig(x1_percent=20, y1_percent=35, x2_percent=80, y2_percent=200)


class TestGetDeskZoneEndpoint:
    """Tests for GET /zones/desk."""

    @patch("backend.routers.zones.get_desk_zone", new_callable=AsyncMock)
    def test_returns_current_config(self, mock_get_zone, client):
        """GET /zones/desk returns the current desk zone configuration."""
        mock_get_zone.return_value = _make_mock_config(10, 20, 90, 95)

        response = client.get("/zones/desk")
        assert response.status_code == 200
        data = response.json()
        assert data["x1_percent"] == 10
        assert data["y1_percent"] == 20
        assert data["x2_percent"] == 90
        assert data["y2_percent"] == 95

    @patch("backend.routers.zones.get_desk_zone", new_callable=AsyncMock)
    def test_returns_defaults_when_no_config(self, mock_get_zone, client):
        """GET /zones/desk returns defaults if no custom config exists."""
        mock_get_zone.return_value = _make_mock_config()  # default values

        response = client.get("/zones/desk")
        assert response.status_code == 200
        data = response.json()
        assert data["x1_percent"] == 20
        assert data["y1_percent"] == 35
        assert data["x2_percent"] == 80
        assert data["y2_percent"] == 75


class TestPutDeskZoneEndpoint:
    """Tests for PUT /zones/desk."""

    @patch("backend.routers.zones.upsert_desk_zone", new_callable=AsyncMock)
    def test_updates_config_successfully(self, mock_upsert, client):
        """PUT /zones/desk persists and returns updated config."""
        mock_upsert.return_value = _make_mock_config(15, 25, 85, 90)

        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 15,
                "y1_percent": 25,
                "x2_percent": 85,
                "y2_percent": 90,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["x1_percent"] == 15
        assert data["y1_percent"] == 25
        assert data["x2_percent"] == 85
        assert data["y2_percent"] == 90

    def test_rejects_x1_below_zero(self, client):
        """PUT /zones/desk returns 422 for x1_percent < 0."""
        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": -1,
                "y1_percent": 35,
                "x2_percent": 80,
                "y2_percent": 75,
            },
        )
        assert response.status_code == 422

    def test_rejects_x2_above_100(self, client):
        """PUT /zones/desk returns 422 for x2_percent > 100."""
        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 20,
                "y1_percent": 35,
                "x2_percent": 101,
                "y2_percent": 75,
            },
        )
        assert response.status_code == 422

    def test_rejects_y1_below_zero(self, client):
        """PUT /zones/desk returns 422 for y1_percent < 0."""
        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 20,
                "y1_percent": -10,
                "x2_percent": 80,
                "y2_percent": 75,
            },
        )
        assert response.status_code == 422

    def test_rejects_y2_above_100(self, client):
        """PUT /zones/desk returns 422 for y2_percent > 100."""
        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 20,
                "y1_percent": 35,
                "x2_percent": 80,
                "y2_percent": 150,
            },
        )
        assert response.status_code == 422

    @patch("backend.routers.zones.upsert_desk_zone", new_callable=AsyncMock)
    def test_accepts_boundary_values_zero(self, mock_upsert, client):
        """PUT /zones/desk accepts all zeros (valid boundary)."""
        mock_upsert.return_value = _make_mock_config(0, 0, 0, 0)

        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 0,
                "y1_percent": 0,
                "x2_percent": 0,
                "y2_percent": 0,
            },
        )
        assert response.status_code == 200

    @patch("backend.routers.zones.upsert_desk_zone", new_callable=AsyncMock)
    def test_accepts_boundary_values_hundred(self, mock_upsert, client):
        """PUT /zones/desk accepts all 100s (valid boundary)."""
        mock_upsert.return_value = _make_mock_config(100, 100, 100, 100)

        response = client.put(
            "/zones/desk",
            json={
                "x1_percent": 100,
                "y1_percent": 100,
                "x2_percent": 100,
                "y2_percent": 100,
            },
        )
        assert response.status_code == 200
