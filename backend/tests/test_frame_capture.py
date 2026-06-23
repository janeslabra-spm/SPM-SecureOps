"""Unit tests for FrameCaptureService."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.core.frame_capture import FrameCaptureService
from backend.core.pipeline_types import FrameCaptureConfig, SourceUnavailableError


# --- Fixtures ---


def _webcam_config(**overrides) -> FrameCaptureConfig:
    defaults = {
        "source_type": "webcam",
        "source_id": 0,
        "width": 960,
        "height": 540,
        "fps_limit": 30,
        "reconnect_attempts": 3,
        "reconnect_interval": 0.01,
        "connection_timeout": 10.0,
    }
    defaults.update(overrides)
    return FrameCaptureConfig(**defaults)


def _cctv_config(**overrides) -> FrameCaptureConfig:
    defaults = {
        "source_type": "cctv",
        "source_id": "rtsp://192.168.1.100:554/stream",
        "width": 960,
        "height": 540,
        "fps_limit": 30,
        "reconnect_attempts": 3,
        "reconnect_interval": 0.01,
        "connection_timeout": 10.0,
    }
    defaults.update(overrides)
    return FrameCaptureConfig(**defaults)


# --- URL Validation Tests ---


class TestCCTVUrlValidation:
    """Tests for CCTV URL scheme validation."""

    def test_rtsp_url_accepted(self):
        config = _cctv_config(source_id="rtsp://camera.local/stream")
        service = FrameCaptureService(config)
        # Should not raise ValueError on URL validation
        service._validate_cctv_url(str(config.source_id))

    def test_http_url_accepted(self):
        config = _cctv_config(source_id="http://camera.local/video")
        service = FrameCaptureService(config)
        service._validate_cctv_url(str(config.source_id))

    def test_https_url_rejected(self):
        config = _cctv_config(source_id="https://camera.local/stream")
        service = FrameCaptureService(config)
        with pytest.raises(ValueError, match="Invalid CCTV URL scheme"):
            service._validate_cctv_url(str(config.source_id))

    def test_ftp_url_rejected(self):
        config = _cctv_config(source_id="ftp://camera.local/stream")
        service = FrameCaptureService(config)
        with pytest.raises(ValueError, match="Invalid CCTV URL scheme"):
            service._validate_cctv_url(str(config.source_id))

    def test_no_scheme_url_rejected(self):
        config = _cctv_config(source_id="camera.local/stream")
        service = FrameCaptureService(config)
        with pytest.raises(ValueError, match="Invalid CCTV URL scheme"):
            service._validate_cctv_url(str(config.source_id))

    def test_empty_string_rejected(self):
        config = _cctv_config(source_id="")
        service = FrameCaptureService(config)
        with pytest.raises(ValueError, match="Invalid CCTV URL scheme"):
            service._validate_cctv_url(str(config.source_id))


# --- Open Tests ---


class TestWebcamOpen:
    """Tests for webcam source opening."""

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_webcam_success(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()

        mock_vc_class.assert_called_once_with(0)
        mock_cap.set.assert_any_call(3, 960)  # CAP_PROP_FRAME_WIDTH = 3
        mock_cap.set.assert_any_call(4, 540)  # CAP_PROP_FRAME_HEIGHT = 4
        assert service.is_open is True

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_webcam_failure_raises_error(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)

        with pytest.raises(SourceUnavailableError) as exc_info:
            service.open()

        assert "webcam" in str(exc_info.value)
        assert "0" in str(exc_info.value)

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_webcam_error_contains_source_type_and_id(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_class.return_value = mock_cap

        config = _webcam_config(source_id=5)
        service = FrameCaptureService(config)

        with pytest.raises(SourceUnavailableError) as exc_info:
            service.open()

        error_msg = str(exc_info.value)
        assert "webcam" in error_msg
        assert "5" in error_msg


class TestCCTVOpen:
    """Tests for CCTV source opening."""

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_success_first_attempt(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _cctv_config()
        service = FrameCaptureService(config)
        service.open()

        mock_vc_class.assert_called_once_with("rtsp://192.168.1.100:554/stream")
        assert service.is_open is True

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_invalid_scheme_raises_value_error(self, mock_vc_class):
        config = _cctv_config(source_id="ftp://invalid.com/stream")
        service = FrameCaptureService(config)

        with pytest.raises(ValueError, match="Invalid CCTV URL scheme"):
            service.open()

    @patch("backend.core.frame_capture.time.sleep")
    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_retries_on_failure(self, mock_vc_class, mock_sleep):
        # Fail twice, succeed on third attempt
        mock_caps = []
        for opened in [False, False, True]:
            cap = MagicMock()
            cap.isOpened.return_value = opened
            mock_caps.append(cap)
        mock_vc_class.side_effect = mock_caps

        config = _cctv_config(reconnect_interval=0.01)
        service = FrameCaptureService(config)
        service.open()

        assert mock_vc_class.call_count == 3
        assert service.is_open is True

    @patch("backend.core.frame_capture.time.sleep")
    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_all_attempts_fail_raises_error(self, mock_vc_class, mock_sleep):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_class.return_value = mock_cap

        config = _cctv_config(reconnect_attempts=3, reconnect_interval=0.01)
        service = FrameCaptureService(config)

        with pytest.raises(SourceUnavailableError) as exc_info:
            service.open()

        error_msg = str(exc_info.value)
        assert "cctv" in error_msg
        assert "rtsp://192.168.1.100:554/stream" in error_msg

    @patch("backend.core.frame_capture.time.sleep")
    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_waits_between_attempts(self, mock_vc_class, mock_sleep):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_class.return_value = mock_cap

        config = _cctv_config(reconnect_attempts=3, reconnect_interval=2.0)
        service = FrameCaptureService(config)

        with pytest.raises(SourceUnavailableError):
            service.open()

        # Should sleep between attempts (not after the last one)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2.0)

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_cctv_http_url_accepted(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _cctv_config(source_id="http://camera.local:8080/video")
        service = FrameCaptureService(config)
        service.open()

        assert service.is_open is True


# --- Read Tests ---


class TestRead:
    """Tests for frame reading with rate limiting."""

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_read_returns_frame(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_vc_class.return_value = mock_cap

        config = _webcam_config(fps_limit=30)
        service = FrameCaptureService(config)
        service.open()

        result = service.read()
        assert result is not None
        assert result.shape == (540, 960, 3)

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_read_webcam_failure_returns_none(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()

        result = service.read()
        assert result is None

    @patch("backend.core.frame_capture.time.sleep")
    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_read_cctv_failure_triggers_reconnection(self, mock_vc_class, mock_sleep):
        # First cap: opens successfully, then read fails
        mock_cap_1 = MagicMock()
        mock_cap_1.isOpened.return_value = True
        mock_cap_1.read.return_value = (False, None)

        # Second cap (after reconnection): opens successfully, read succeeds
        mock_cap_2 = MagicMock()
        mock_cap_2.isOpened.return_value = True
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        mock_cap_2.read.return_value = (True, frame)

        mock_vc_class.side_effect = [mock_cap_1, mock_cap_2]

        config = _cctv_config(reconnect_interval=0.01)
        service = FrameCaptureService(config)
        service.open()

        result = service.read()
        assert result is not None

    def test_read_when_not_open_raises_error(self):
        config = _webcam_config()
        service = FrameCaptureService(config)

        with pytest.raises(SourceUnavailableError):
            service.read()

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_read_rate_limiting(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_vc_class.return_value = mock_cap

        config = _webcam_config(fps_limit=10)  # 100ms interval
        service = FrameCaptureService(config)
        service.open()

        # First read should be immediate
        service.read()
        t_start = time.monotonic()

        # Second read should be delayed by ~100ms
        service.read()
        elapsed = time.monotonic() - t_start

        # Allow some tolerance but ensure rate limiting is applied
        assert elapsed >= 0.09  # At least ~90ms (allowing for timing jitter)


# --- Release Tests ---


class TestRelease:
    """Tests for resource cleanup."""

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_release_closes_capture(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()
        assert service.is_open is True

        service.release()
        mock_cap.release.assert_called_once()
        assert service.is_open is False

    def test_release_when_not_open(self):
        config = _webcam_config()
        service = FrameCaptureService(config)

        # Should not raise
        service.release()
        assert service.is_open is False

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_release_within_5_seconds(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()

        start = time.monotonic()
        service.release()
        duration = time.monotonic() - start

        assert duration < 5.0


# --- is_open Property Tests ---


class TestIsOpen:
    """Tests for the is_open property."""

    def test_initially_closed(self):
        config = _webcam_config()
        service = FrameCaptureService(config)
        assert service.is_open is False

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_open_after_success(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()
        assert service.is_open is True

    @patch("backend.core.frame_capture.cv2.VideoCapture")
    def test_closed_after_release(self, mock_vc_class):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        config = _webcam_config()
        service = FrameCaptureService(config)
        service.open()
        service.release()
        assert service.is_open is False
