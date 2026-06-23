"""Unit tests for the RetentionService.

Tests core cleanup logic including expired record deletion,
screenshot file deletion, orphan file cleanup, and error handling.
"""

import asyncio
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.workers.retention_service import RetentionResult, RetentionService


@pytest.fixture
def screenshot_dir(tmp_path):
    """Create a temporary screenshot directory."""
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    return screenshots


@pytest.fixture
def mock_session_factory():
    """Create a mock async session factory."""
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


class TestRetentionResult:
    """Tests for RetentionResult dataclass."""

    def test_defaults(self):
        result = RetentionResult()
        assert result.deleted_records == 0
        assert result.deleted_files == 0
        assert result.orphan_files_deleted == 0
        assert result.errors == []

    def test_custom_values(self):
        result = RetentionResult(
            deleted_records=5,
            deleted_files=3,
            orphan_files_deleted=2,
            errors=["err1"],
        )
        assert result.deleted_records == 5
        assert result.deleted_files == 3
        assert result.orphan_files_deleted == 2
        assert result.errors == ["err1"]


class TestRetentionServiceInit:
    """Tests for RetentionService initialization."""

    def test_default_interval(self, mock_session_factory, screenshot_dir):
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)
        assert service.RETENTION_DAYS == 7
        assert service._interval_hours == 24

    def test_custom_interval(self, mock_session_factory, screenshot_dir):
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir, interval_hours=12)
        assert service._interval_hours == 12


class TestDeleteScreenshotFile:
    """Tests for _delete_screenshot_file logic."""

    def test_missing_file_skipped_gracefully(self, mock_session_factory, screenshot_dir):
        """Requirement 4.4: missing files should be skipped without error."""
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)
        result = RetentionResult()

        service._delete_screenshot_file("nonexistent.jpg", result)

        assert result.deleted_files == 0
        assert result.errors == []

    def test_existing_file_deleted(self, mock_session_factory, screenshot_dir):
        """Screenshot file should be deleted and counted."""
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)
        result = RetentionResult()

        # Create a test file
        test_file = screenshot_dir / "test_screenshot.jpg"
        test_file.write_text("test data")

        service._delete_screenshot_file(str(test_file), result)

        assert result.deleted_files == 1
        assert not test_file.exists()

    def test_relative_path_resolved(self, mock_session_factory, screenshot_dir):
        """Relative paths should be resolved against screenshot_dir."""
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)
        result = RetentionResult()

        # Create a test file in the screenshot directory
        test_file = screenshot_dir / "relative_test.jpg"
        test_file.write_text("test data")

        service._delete_screenshot_file("relative_test.jpg", result)

        assert result.deleted_files == 1
        assert not test_file.exists()

    def test_permission_error_logged_and_continues(
        self, mock_session_factory, screenshot_dir
    ):
        """Requirement 4.5: permission errors logged, processing continues."""
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)
        result = RetentionResult()

        # Create a test file
        test_file = screenshot_dir / "locked_file.jpg"
        test_file.write_text("test data")

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            service._delete_screenshot_file(str(test_file), result)

        assert result.deleted_files == 0
        assert len(result.errors) == 1
        assert "Permission denied" in result.errors[0]


class TestStartStop:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, mock_session_factory, screenshot_dir):
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)

        # Patch run_cleanup to prevent actual execution
        with patch.object(service, "run_cleanup", new_callable=AsyncMock):
            await service.start()
            assert service._task is not None
            assert not service._task.done()

            await service.stop()
            assert service._task is None

    @pytest.mark.asyncio
    async def test_stop_without_start(self, mock_session_factory, screenshot_dir):
        """Stop should work even if never started."""
        factory, _ = mock_session_factory
        service = RetentionService(factory, screenshot_dir)

        await service.stop()  # Should not raise
        assert service._task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
