"""Pipeline orchestration and lifecycle management for the AI Detection Pipeline.

Manages the frame capture → inference → extraction → scoring → dispatch loop
in a background thread, tracks runtime metrics, and enforces single-instance
pipeline semantics.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.config import AppConfig
from backend.core.bbox_extractor import BoundingBoxExtractor
from backend.core.confidence_scorer import ConfidenceScorer
from backend.core.event_dispatcher import ComplianceEventDispatcher
from backend.core.frame_capture import FrameCaptureService
from backend.core.inference_engine import InferenceEngine
from backend.core.pipeline_types import (
    DetectionEvent,
    DetectionResult,
    FrameCaptureConfig,
    PipelineMetrics,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

# Maximum consecutive inference failures before entering error state
_MAX_CONSECUTIVE_INFERENCE_FAILURES = 3

# Latency threshold for performance warnings (milliseconds)
_LATENCY_WARNING_THRESHOLD_MS = 500.0

# Consecutive slow frames before logging a performance warning
_SLOW_FRAME_WARNING_COUNT = 5


class PipelineManager:
    """Orchestrates the detection pipeline lifecycle and detection loop.

    Manages starting/stopping the pipeline, runs the detection loop in a
    background thread, tracks metrics, and transitions to error state on
    unrecoverable failures.
    """

    def __init__(self, config: AppConfig, db_session_factory=None) -> None:
        """Initialize the pipeline manager.

        Args:
            config: Application configuration with detection parameters.
            db_session_factory: Async session factory for database access
                (used by event dispatcher for persistence).
        """
        self._config = config
        self._db_session_factory = db_session_factory

        # Pipeline components (created on start)
        self._frame_capture: FrameCaptureService | None = None
        self._inference_engine: InferenceEngine | None = None
        self._bbox_extractor = BoundingBoxExtractor()
        self._confidence_scorer = ConfidenceScorer(
            threshold=config.confidence_threshold
        )
        self._event_dispatcher: ComplianceEventDispatcher | None = None

        # Runtime state
        self._metrics = PipelineMetrics()
        self._latest_detections: list[DetectionResult] = []
        self._lock = threading.Lock()

        # Thread management
        self._loop_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Lifecycle tracking
        self._start_time: float | None = None
        self._source_type: str | None = None
        self._source_id: int | str | None = None

        # Runtime config (mutable)
        self._image_size: int = config.image_size
        self._fps_limit: int = config.ui_fps

    def start(self, source_type: str, source_id: int | str) -> None:
        """Start the detection pipeline.

        Creates the frame capture service and inference engine, then starts
        the detection loop in a background thread.

        Args:
            source_type: Either "webcam" or "cctv".
            source_id: Camera index (int) for webcam or URL (str) for CCTV.

        Raises:
            ValueError: If the pipeline is already running.
            SourceUnavailableError: If the video source cannot be opened.
        """
        with self._lock:
            if self._metrics.running:
                raise ValueError("Pipeline is already active")

        # Create frame capture config
        capture_config = FrameCaptureConfig(
            source_type=source_type,  # type: ignore[arg-type]
            source_id=source_id,
            loop=source_type == "file",
            width=self._config.camera_width,
            height=self._config.camera_height,
            fps_limit=self._fps_limit,
        )

        # Create and open frame capture service
        self._frame_capture = FrameCaptureService(capture_config)
        self._frame_capture.open()

        # Create inference engine
        self._inference_engine = InferenceEngine(
            model_path=self._config.model_path,
            device=self._config.device,
        )

        # Store source info
        self._source_type = source_type
        self._source_id = source_id

        # Reset metrics and state
        with self._lock:
            self._metrics = PipelineMetrics(running=True)
            self._latest_detections = []

        # Record start time
        self._start_time = time.monotonic()

        # Start background detection loop
        self._stop_event.clear()
        self._loop_thread = threading.Thread(
            target=self._detection_loop,
            name="pipeline-detection-loop",
            daemon=True,
        )
        self._loop_thread.start()

        logger.info(
            "Pipeline started: source_type=%s, source_id=%s",
            source_type,
            source_id,
        )

    def stop(self) -> PipelineMetrics:
        """Stop the detection pipeline and release resources.

        Returns:
            Final pipeline metrics at the time of stopping.

        Raises:
            ValueError: If the pipeline is not running.
        """
        with self._lock:
            if not self._metrics.running:
                raise ValueError("Pipeline is already inactive")

        # Signal the loop to stop
        self._stop_event.set()

        # Wait for the loop thread to finish
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=5.0)
            self._loop_thread = None

        # Release frame capture
        if self._frame_capture is not None:
            self._frame_capture.release()
            self._frame_capture = None

        # Calculate uptime
        uptime = 0.0
        if self._start_time is not None:
            uptime = time.monotonic() - self._start_time
            self._start_time = None

        # Update metrics
        with self._lock:
            self._metrics.running = False
            metrics_snapshot = PipelineMetrics(
                running=self._metrics.running,
                frames_processed=self._metrics.frames_processed,
                current_fps=self._metrics.current_fps,
                last_inference_ms=self._metrics.last_inference_ms,
                error=self._metrics.error,
                per_class_counts=dict(self._metrics.per_class_counts),
            )

        logger.info(
            "Pipeline stopped: frames_processed=%d, uptime=%.1fs",
            metrics_snapshot.frames_processed,
            uptime,
        )

        return metrics_snapshot

    def get_status(self) -> PipelineMetrics:
        """Return current pipeline metrics.

        Returns:
            Current PipelineMetrics snapshot.
        """
        with self._lock:
            return PipelineMetrics(
                running=self._metrics.running,
                frames_processed=self._metrics.frames_processed,
                current_fps=self._metrics.current_fps,
                last_inference_ms=self._metrics.last_inference_ms,
                error=self._metrics.error,
                per_class_counts=dict(self._metrics.per_class_counts),
            )

    def get_latest_detections(self) -> list[DetectionResult]:
        """Return the most recent detection results.

        Returns:
            List of DetectionResult objects from the last processed frame.
            Empty list if the pipeline is not running or no detections yet.
        """
        with self._lock:
            return list(self._latest_detections)

    def update_config(self, **kwargs) -> dict:
        """Update runtime configuration parameters.

        Supported keys:
            - confidence_threshold: float in [0.0, 1.0]
            - image_size: int in [320, 1280]
            - fps_limit: int in [1, 30]

        Args:
            **kwargs: Configuration parameters to update.

        Returns:
            Dict with current configuration values after update.
        """
        if "confidence_threshold" in kwargs:
            threshold = kwargs["confidence_threshold"]
            self._confidence_scorer.set_threshold(threshold)

        if "image_size" in kwargs:
            self._image_size = kwargs["image_size"]

        if "fps_limit" in kwargs:
            self._fps_limit = kwargs["fps_limit"]

        return {
            "confidence_threshold": self._confidence_scorer.threshold,
            "image_size": self._image_size,
            "fps_limit": self._fps_limit,
        }

    def _detection_loop(self) -> None:
        """Background detection loop running in a separate thread.

        Captures frames, runs inference, extracts bounding boxes, scores
        detections, updates metrics, and dispatches compliance events.
        Uses time-based inference scheduling to maintain smooth operation
        when inference is slow (e.g., CPU-only at 900ms+).
        Exits on stop signal or unrecoverable error.
        """
        consecutive_inference_failures = 0
        consecutive_slow_frames = 0
        fps_tracker_start = time.monotonic()
        fps_frame_count = 0

        # Time-based inference: only run YOLO every N seconds
        # This prevents the loop from stalling at 1 FPS on slow hardware
        inference_interval = 1.0  # seconds between inference runs
        last_inference_time = 0.0  # force first inference immediately
        last_results: list[DetectionResult] = []
        last_inference_ms = 0.0

        while not self._stop_event.is_set():
            try:
                # Step 1: Capture frame
                frame = self._capture_frame()
                if frame is None:
                    # Webcam skip — no frame available, continue loop
                    continue

                now = time.monotonic()
                run_inference = (now - last_inference_time) >= inference_interval

                if run_inference:
                    last_inference_time = now

                    # Step 2: Run inference (measure time)
                    inference_start = time.monotonic()
                    raw_detections = self._inference_engine.infer(
                        frame,
                        image_size=self._image_size,
                        confidence_threshold=self._config.confidence_threshold,
                    )
                    last_inference_ms = (time.monotonic() - inference_start) * 1000.0

                    consecutive_inference_failures = 0

                    # Step 3: Extract bounding boxes
                    frame_height, frame_width = frame.shape[:2]
                    detections = self._bbox_extractor.extract(
                        raw_detections, frame_width, frame_height
                    )

                    # Step 4: Confidence scoring and NMS
                    last_results = self._confidence_scorer.filter(detections)

                    # Step 7: Track latency warnings
                    if last_inference_ms > _LATENCY_WARNING_THRESHOLD_MS:
                        consecutive_slow_frames += 1
                        if consecutive_slow_frames >= _SLOW_FRAME_WARNING_COUNT:
                            logger.warning(
                                "Performance warning: inference latency exceeded "
                                "%.0fms for %d consecutive frames (last=%.1fms)",
                                _LATENCY_WARNING_THRESHOLD_MS,
                                consecutive_slow_frames,
                                last_inference_ms,
                            )
                            consecutive_slow_frames = 0
                    else:
                        consecutive_slow_frames = 0

                    # Step 8: Dispatch compliance event if detections are non-empty
                    if last_results:
                        frame_height, frame_width = frame.shape[:2]
                        self._dispatch_event(last_results, frame_width, frame_height)

                # Step 5: Update metrics (every frame for FPS tracking)
                fps_frame_count += 1
                elapsed_since_fps_reset = time.monotonic() - fps_tracker_start
                if elapsed_since_fps_reset >= 1.0:
                    current_fps = fps_frame_count / elapsed_since_fps_reset
                    fps_tracker_start = time.monotonic()
                    fps_frame_count = 0
                else:
                    current_fps = (
                        fps_frame_count / elapsed_since_fps_reset
                        if elapsed_since_fps_reset > 0
                        else 0.0
                    )

                # Count per-class detections
                per_class_counts = {"person": 0, "cell phone": 0, "book": 0}
                for result in last_results:
                    if result.label in per_class_counts:
                        per_class_counts[result.label] += 1

                with self._lock:
                    self._metrics.frames_processed += 1
                    self._metrics.current_fps = current_fps
                    self._metrics.last_inference_ms = last_inference_ms
                    self._metrics.per_class_counts = per_class_counts
                    self._latest_detections = last_results
                    frame_number = self._metrics.frames_processed

                # Step 6: Log inference cycle at DEBUG
                if run_inference:
                    logger.debug(
                        "Inference cycle: frame=%d, duration=%.1fms, detections=%d",
                        frame_number,
                        last_inference_ms,
                        len(last_results),
                    )

            except SourceUnavailableError as exc:
                # Unrecoverable source failure
                self._enter_error_state(str(exc))
                return

            except Exception as exc:
                # Inference or processing failure
                consecutive_inference_failures += 1
                logger.error(
                    "Detection loop error (attempt %d/%d): %s",
                    consecutive_inference_failures,
                    _MAX_CONSECUTIVE_INFERENCE_FAILURES,
                    exc,
                )

                if consecutive_inference_failures >= _MAX_CONSECUTIVE_INFERENCE_FAILURES:
                    self._enter_error_state(
                        f"Pipeline stopped: {_MAX_CONSECUTIVE_INFERENCE_FAILURES} "
                        f"consecutive inference failures. Last error: {exc}"
                    )
                    return

    def _capture_frame(self):
        """Capture a frame from the video source.

        Returns:
            Frame as numpy array, or None if no frame available (webcam skip).

        Raises:
            SourceUnavailableError: If the source is permanently unavailable.
        """
        if self._frame_capture is None:
            raise SourceUnavailableError("Frame capture service is not initialized")
        return self._frame_capture.read()

    def _dispatch_event(
        self, results: list[DetectionResult], frame_width: int, frame_height: int
    ) -> None:
        """Create and dispatch a detection event.

        Creates a DetectionEvent and dispatches it via the event dispatcher
        if one is available. This is a fire-and-forget operation that does
        not block the detection loop.

        Args:
            results: Detection results to dispatch.
            frame_width: Width of the processed frame.
            frame_height: Height of the processed frame.
        """
        camera_id = f"{self._source_type}:{self._source_id}"
        if len(camera_id) > 128:
            camera_id = camera_id[:128]

        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_id=camera_id,
            frame_width=frame_width,
            frame_height=frame_height,
            detections=results,
        )

        # If event dispatcher is available, dispatch asynchronously
        if self._event_dispatcher is not None:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._event_dispatcher.dispatch(event), loop
                    )
                else:
                    loop.run_until_complete(
                        self._event_dispatcher.dispatch(event)
                    )
            except RuntimeError:
                # No event loop available — log and continue
                logger.debug(
                    "No event loop available for dispatch, skipping event"
                )

    def _enter_error_state(self, error_message: str) -> None:
        """Transition the pipeline to an error state.

        Stops the pipeline loop, releases resources, and updates metrics
        with the error information.

        Args:
            error_message: Description of the error that caused the transition.
        """
        # Calculate uptime
        uptime = 0.0
        if self._start_time is not None:
            uptime = time.monotonic() - self._start_time
            self._start_time = None

        # Release frame capture
        if self._frame_capture is not None:
            try:
                self._frame_capture.release()
            except Exception:
                pass
            self._frame_capture = None

        # Update metrics
        with self._lock:
            self._metrics.running = False
            self._metrics.error = error_message

        logger.error("Pipeline error: %s", error_message)
        logger.info(
            "Pipeline stopped due to error: frames_processed=%d, uptime=%.1fs",
            self._metrics.frames_processed,
            uptime,
        )
