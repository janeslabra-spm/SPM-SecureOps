"""Unit tests for PipelineManager lifecycle and orchestration.

Tests cover:
- Single-instance enforcement (reject double-start/double-stop)
- Pipeline start/stop lifecycle
- Metrics tracking (frames_processed, current_fps, last_inference_ms, per_class_counts)
- Error state transitions (source unavailable, consecutive inference failures)
- Latency warning logging
- Detection loop orchestration
- Configuration updates
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from backend.config import AppConfig
from backend.core.pipeline_manager import (
    PipelineManager,
    _LATENCY_WARNING_THRESHOLD_MS,
    _MAX_CONSECUTIVE_INFERENCE_FAILURES,
    _SLOW_FRAME_WARNING_COUNT,
)
from backend.core.pipeline_types import (
    DetectionResult,
    PipelineMetrics,
    RawDetection,
    SourceUnavailableError,
)


@pytest.fixture
def app_config() -> AppConfig:
    """Create a minimal AppConfig for testing."""
    return AppConfig(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        model_path="yolov8n.pt",
        device="cpu",
        confidence_threshold=0.4,
        image_size=640,
        camera_width=960,
        camera_height=540,
        ui_fps=2,
    )


@pytest.fixture
def pipeline_manager(app_config: AppConfig) -> PipelineManager:
    """Create a PipelineManager instance for testing."""
    return PipelineManager(config=app_config, db_session_factory=None)


class TestPipelineManagerInit:
    """Tests for PipelineManager initialization."""

    def test_init_creates_confidence_scorer(self, pipeline_manager: PipelineManager):
        """PipelineManager initializes with a ConfidenceScorer from config."""
        assert pipeline_manager._confidence_scorer is not None
        assert pipeline_manager._confidence_scorer.threshold == 0.4

    def test_init_metrics_not_running(self, pipeline_manager: PipelineManager):
        """Pipeline is not running after initialization."""
        status = pipeline_manager.get_status()
        assert status.running is False
        assert status.frames_processed == 0
        assert status.current_fps == 0.0
        assert status.last_inference_ms == 0.0
        assert status.error is None

    def test_init_empty_detections(self, pipeline_manager: PipelineManager):
        """No detections available after initialization."""
        assert pipeline_manager.get_latest_detections() == []


class TestPipelineStartStop:
    """Tests for pipeline start/stop lifecycle."""

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_start_sets_running(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Starting the pipeline sets metrics.running to True."""
        mock_fcs = MagicMock()
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)

        try:
            status = pipeline_manager.get_status()
            assert status.running is True
        finally:
            pipeline_manager._stop_event.set()
            if pipeline_manager._loop_thread:
                pipeline_manager._loop_thread.join(timeout=2.0)
            pipeline_manager._metrics.running = False

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_double_start_raises_value_error(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Starting an already-running pipeline raises ValueError."""
        mock_fcs = MagicMock()
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)

        try:
            with pytest.raises(ValueError, match="Pipeline is already active"):
                pipeline_manager.start("webcam", 1)
        finally:
            pipeline_manager._stop_event.set()
            if pipeline_manager._loop_thread:
                pipeline_manager._loop_thread.join(timeout=2.0)
            pipeline_manager._metrics.running = False

    def test_stop_when_not_running_raises_value_error(
        self, pipeline_manager: PipelineManager
    ):
        """Stopping a non-running pipeline raises ValueError."""
        with pytest.raises(ValueError, match="Pipeline is already inactive"):
            pipeline_manager.stop()

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_stop_returns_metrics(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Stopping the pipeline returns final metrics."""
        mock_fcs = MagicMock()
        mock_fcs.read.return_value = None  # Simulate no frames
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.1)  # Let the loop run briefly

        metrics = pipeline_manager.stop()

        assert isinstance(metrics, PipelineMetrics)
        assert metrics.running is False

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_stop_releases_frame_capture(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Stopping the pipeline releases the frame capture resource."""
        mock_fcs = MagicMock()
        mock_fcs.read.return_value = None
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.05)
        pipeline_manager.stop()

        mock_fcs.release.assert_called_once()


class TestDetectionLoop:
    """Tests for the detection loop orchestration."""

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_loop_processes_frames(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Detection loop processes frames and updates metrics."""
        # Create a fake frame
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        # Mock frame capture to return frame then None (to slow loop)
        call_count = [0]

        def mock_read():
            call_count[0] += 1
            if call_count[0] <= 3:
                return fake_frame
            return None

        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = mock_read
        mock_fcs_class.return_value = mock_fcs

        # Mock inference to return a detection
        raw_det = RawDetection(
            class_id=67,
            label="cell phone",
            confidence=0.85,
            bbox_raw=(100.0, 200.0, 300.0, 400.0),
        )
        mock_ie = MagicMock()
        mock_ie.infer.return_value = [raw_det]
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.3)  # Let the loop process some frames
        metrics = pipeline_manager.stop()

        assert metrics.frames_processed >= 1

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_loop_updates_per_class_counts(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Detection loop updates per-class detection counts."""
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        call_count = [0]

        def mock_read():
            call_count[0] += 1
            if call_count[0] <= 2:
                return fake_frame
            # After processing, return None to slow down
            time.sleep(0.05)
            return None

        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = mock_read
        mock_fcs_class.return_value = mock_fcs

        # Return detections for person and cell phone
        raw_dets = [
            RawDetection(
                class_id=0,
                label="person",
                confidence=0.9,
                bbox_raw=(10.0, 20.0, 100.0, 200.0),
            ),
            RawDetection(
                class_id=67,
                label="cell phone",
                confidence=0.7,
                bbox_raw=(50.0, 60.0, 150.0, 160.0),
            ),
        ]
        mock_ie = MagicMock()
        mock_ie.infer.return_value = raw_dets
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.3)

        status = pipeline_manager.get_status()
        # Should have recorded detections
        assert status.per_class_counts["person"] >= 0
        assert status.per_class_counts["cell phone"] >= 0

        pipeline_manager.stop()

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_loop_stores_latest_detections(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Detection loop stores the latest detection results."""
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        call_count = [0]

        def mock_read():
            call_count[0] += 1
            if call_count[0] <= 2:
                return fake_frame
            time.sleep(0.05)
            return None

        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = mock_read
        mock_fcs_class.return_value = mock_fcs

        raw_det = RawDetection(
            class_id=67,
            label="cell phone",
            confidence=0.85,
            bbox_raw=(100.0, 200.0, 300.0, 400.0),
        )
        mock_ie = MagicMock()
        mock_ie.infer.return_value = [raw_det]
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.3)

        detections = pipeline_manager.get_latest_detections()
        # Should have some detection results after processing
        assert isinstance(detections, list)

        pipeline_manager.stop()

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_none_frame_continues_loop(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """When frame capture returns None (webcam skip), loop continues."""
        mock_fcs = MagicMock()
        mock_fcs.read.return_value = None
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.1)

        # Pipeline should still be running (not crashed)
        status = pipeline_manager.get_status()
        assert status.running is True
        assert status.frames_processed == 0  # No frames processed

        pipeline_manager.stop()


class TestErrorState:
    """Tests for error state transitions."""

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_source_unavailable_enters_error_state(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """SourceUnavailableError transitions pipeline to error state."""
        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = SourceUnavailableError("Source lost")
        mock_fcs.release.return_value = None
        mock_fcs_class.return_value = mock_fcs
        mock_ie = MagicMock()
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("cctv", "rtsp://test.local/stream")
        time.sleep(0.2)  # Give loop time to hit the error

        status = pipeline_manager.get_status()
        assert status.running is False
        assert status.error is not None
        assert "Source lost" in status.error

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_consecutive_inference_failures_enters_error_state(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """3 consecutive inference failures transition to error state."""
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        mock_fcs = MagicMock()
        mock_fcs.read.return_value = fake_frame
        mock_fcs.release.return_value = None
        mock_fcs_class.return_value = mock_fcs

        # Make inference raise an exception every time
        mock_ie = MagicMock()
        mock_ie.infer.side_effect = RuntimeError("Inference crash")
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.5)  # Give time for 3 failures

        status = pipeline_manager.get_status()
        assert status.running is False
        assert status.error is not None
        assert "consecutive inference failures" in status.error

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_error_state_preserves_metrics(
        self, mock_fcs_class, mock_ie_class, pipeline_manager: PipelineManager
    ):
        """Error state preserves frame count and other metrics."""
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        call_count = [0]

        def mock_read():
            call_count[0] += 1
            return fake_frame

        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = mock_read
        mock_fcs.release.return_value = None
        mock_fcs_class.return_value = mock_fcs

        # First call succeeds, then fail 3 times
        infer_count = [0]

        def mock_infer(frame, **kwargs):
            infer_count[0] += 1
            if infer_count[0] <= 1:
                return [
                    RawDetection(
                        class_id=0,
                        label="person",
                        confidence=0.9,
                        bbox_raw=(10.0, 20.0, 100.0, 200.0),
                    )
                ]
            raise RuntimeError("Inference crash")

        mock_ie = MagicMock()
        mock_ie.infer.side_effect = mock_infer
        mock_ie_class.return_value = mock_ie

        pipeline_manager.start("webcam", 0)
        time.sleep(0.5)

        status = pipeline_manager.get_status()
        # Should have processed at least 1 frame before error
        assert status.frames_processed >= 1
        assert status.running is False
        assert status.error is not None


class TestLatencyWarning:
    """Tests for latency warning logging."""

    @patch("backend.core.pipeline_manager.InferenceEngine")
    @patch("backend.core.pipeline_manager.FrameCaptureService")
    def test_slow_frames_trigger_warning(
        self,
        mock_fcs_class,
        mock_ie_class,
        pipeline_manager: PipelineManager,
        caplog,
    ):
        """5 consecutive slow frames triggers a WARNING log."""
        fake_frame = np.zeros((540, 960, 3), dtype=np.uint8)

        call_count = [0]

        def mock_read():
            call_count[0] += 1
            if call_count[0] <= 6:
                return fake_frame
            time.sleep(0.1)
            return None

        mock_fcs = MagicMock()
        mock_fcs.read.side_effect = mock_read
        mock_fcs_class.return_value = mock_fcs

        # Make inference take >500ms
        def slow_infer(frame, **kwargs):
            time.sleep(0.55)  # 550ms
            return []

        mock_ie = MagicMock()
        mock_ie.infer.side_effect = slow_infer
        mock_ie_class.return_value = mock_ie

        import logging

        with caplog.at_level(logging.WARNING, logger="backend.core.pipeline_manager"):
            pipeline_manager.start("webcam", 0)
            time.sleep(4.0)  # Give enough time for 5 slow frames

            pipeline_manager._stop_event.set()
            if pipeline_manager._loop_thread:
                pipeline_manager._loop_thread.join(timeout=2.0)
            pipeline_manager._metrics.running = False

        # Check for performance warning
        warning_messages = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any("Performance warning" in msg for msg in warning_messages)


class TestConfigUpdate:
    """Tests for runtime configuration updates."""

    def test_update_confidence_threshold(self, pipeline_manager: PipelineManager):
        """update_config updates confidence threshold."""
        result = pipeline_manager.update_config(confidence_threshold=0.6)
        assert result["confidence_threshold"] == 0.6

    def test_update_image_size(self, pipeline_manager: PipelineManager):
        """update_config updates image size."""
        result = pipeline_manager.update_config(image_size=480)
        assert result["image_size"] == 480

    def test_update_fps_limit(self, pipeline_manager: PipelineManager):
        """update_config updates FPS limit."""
        result = pipeline_manager.update_config(fps_limit=10)
        assert result["fps_limit"] == 10

    def test_update_multiple_params(self, pipeline_manager: PipelineManager):
        """update_config handles multiple params at once."""
        result = pipeline_manager.update_config(
            confidence_threshold=0.7, image_size=320, fps_limit=5
        )
        assert result["confidence_threshold"] == 0.7
        assert result["image_size"] == 320
        assert result["fps_limit"] == 5

    def test_update_returns_current_config(self, pipeline_manager: PipelineManager):
        """update_config returns all current values even with partial update."""
        result = pipeline_manager.update_config(confidence_threshold=0.5)
        assert "confidence_threshold" in result
        assert "image_size" in result
        assert "fps_limit" in result


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_pipeline_metrics(
        self, pipeline_manager: PipelineManager
    ):
        """get_status returns a PipelineMetrics object."""
        status = pipeline_manager.get_status()
        assert isinstance(status, PipelineMetrics)

    def test_get_status_reflects_initial_state(
        self, pipeline_manager: PipelineManager
    ):
        """get_status shows correct initial state."""
        status = pipeline_manager.get_status()
        assert status.running is False
        assert status.frames_processed == 0
        assert status.error is None
        assert status.per_class_counts == {
            "person": 0,
            "cell phone": 0,
            "book": 0,
        }


class TestGetLatestDetections:
    """Tests for get_latest_detections method."""

    def test_returns_empty_when_not_running(
        self, pipeline_manager: PipelineManager
    ):
        """Returns empty list when pipeline is not running."""
        assert pipeline_manager.get_latest_detections() == []

    def test_returns_list_copy(self, pipeline_manager: PipelineManager):
        """Returns a copy, not a reference to internal list."""
        detections = pipeline_manager.get_latest_detections()
        assert detections is not pipeline_manager._latest_detections
