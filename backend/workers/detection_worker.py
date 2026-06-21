"""Detection Worker — background thread for video processing.

Migrated from MonitoringWorker in src/mjpeg_stream.py to use async DB session
factory, the new IncidentLogger, and the backend core modules (YoloDetector,
classify_incidents, table_zone_from_percent).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import AppConfig
from backend.core.detector import Detection, YoloDetector
from backend.core.incident_logger import IncidentConfig, IncidentLogger
from backend.core.rules import IncidentCandidate, classify_incidents, table_zone_from_percent
from backend.db.desk_zone import get_desk_zone

logger = logging.getLogger(__name__)


class DetectionWorker:
    """Threaded video processing loop (migrated from MonitoringWorker).

    Captures frames from a webcam or sample video, runs YOLO inference,
    classifies violations via the rule engine, logs incidents via the
    IncidentLogger, annotates frames with bounding boxes and overlays,
    and publishes JPEG frames for the MJPEG streaming endpoint.
    """

    def __init__(
        self,
        config: AppConfig,
        db_session_factory: async_sessionmaker,  # kept for API compatibility, not used directly
        screenshot_dir: Path,
    ) -> None:
        self._config = config
        self._screenshot_dir = screenshot_dir

        # Threading primitives
        self._stop_event = threading.Event()
        self._frame_condition = threading.Condition()

        # Published frame state
        self._latest_jpeg: bytes | None = None
        self._frame_id: int = 0

        # IncidentLogger is created inside the worker thread after its own
        # event loop is running, so its DB connections belong to that loop.
        self._incident_logger: IncidentLogger | None = None

        # Status metrics
        self._status: dict[str, Any] = {
            "message": "Starting monitoring...",
            "people": 0,
            "phones": 0,
            "active_rule_matches": 0,
            "logged_this_frame": 0,
            "inference_ms": 0.0,
            "fps": 0.0,
        }

        # Worker thread and its own event loop.
        # The engine/session factory are created on this loop to avoid
        # asyncpg "Future attached to a different loop" errors.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker_session_factory: async_sessionmaker | None = None
        self._thread = threading.Thread(
            target=self._run, name="detection-worker", daemon=True
        )

        # Public attribute used by the stream router to check worker state
        self.is_running: bool = False

    def start(self) -> None:
        """Start the detection worker background thread."""
        self.is_running = True
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop and wait for thread to join."""
        self._stop_event.set()
        with self._frame_condition:
            self._frame_condition.notify_all()
        self._thread.join(timeout=5)
        self.is_running = False

    def _run_async(self, coro):
        """Run a coroutine on the worker's own event loop."""
        if self._loop is None:
            raise RuntimeError("Worker event loop not yet initialized.")
        return self._loop.run_until_complete(coro)

    def get_latest_frame(self) -> bytes | None:
        """Return the most recently published annotated JPEG frame."""
        with self._frame_condition:
            return self._latest_jpeg

    def get_status(self) -> dict[str, Any]:
        """Return a copy of the current detection metrics."""
        with self._frame_condition:
            return dict(self._status)

    def wait_for_frame(
        self, last_frame_id: int, timeout: float = 2.0
    ) -> tuple[int, bytes | None]:
        """Block until a new frame is available or timeout expires.

        Args:
            last_frame_id: The frame ID the caller last received.
            timeout: Maximum seconds to wait.

        Returns:
            Tuple of (current_frame_id, jpeg_bytes_or_None).
        """
        with self._frame_condition:
            self._frame_condition.wait_for(
                lambda: self._frame_id != last_frame_id or self._stop_event.is_set(),
                timeout=timeout,
            )
            return self._frame_id, self._latest_jpeg

    # ------------------------------------------------------------------
    # Internal: main processing loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main detection loop running in background thread."""
        # Create a dedicated event loop for this thread.
        # The engine and session factory are also created here so all asyncpg
        # connections belong to this loop — preventing cross-loop errors.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Build a worker-local engine and session factory on this loop
        worker_engine = create_async_engine(
            self._config.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self._worker_session_factory = async_sessionmaker(
            bind=worker_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # IncidentLogger uses the worker-local session factory
        self._incident_logger = IncidentLogger(
            db_session_factory=self._worker_session_factory,
            screenshot_dir=self._screenshot_dir,
            config=IncidentConfig(
                duration_threshold=self._config.duration_threshold,
                cooldown_seconds=self._config.cooldown_seconds,
            ),
        )

        capture = self._open_capture()
        if capture is None or not capture.isOpened():
            self._set_status(
                message=f"Could not open {self._config.source_mode} source."
            )
            self.is_running = False
            return

        try:
            detector = YoloDetector(
                model_path=self._config.model_path,
                device=self._config.device,
            )
        except Exception as exc:
            self._set_status(message=f"YOLO model failed to load: {exc}")
            capture.release()
            self.is_running = False
            return

        target_interval = 1.0 / max(self._config.ui_fps, 1)
        last_loop_started = time.perf_counter()

        # Desk zone percentages (loaded from config defaults; refreshed from DB periodically)
        zone_percents = (
            self._config.desk_zone_x1,
            self._config.desk_zone_y1,
            self._config.desk_zone_x2,
            self._config.desk_zone_y2,
        )
        zone_refresh_interval = 30.0  # refresh desk zone from DB every 30s
        last_zone_refresh = 0.0

        try:
            while not self._stop_event.is_set():
                loop_started = time.perf_counter()

                # Periodically refresh desk zone config from DB
                if time.perf_counter() - last_zone_refresh > zone_refresh_interval:
                    zone_percents = self._fetch_desk_zone(zone_percents)
                    last_zone_refresh = time.perf_counter()

                # Read frame
                ok, frame = capture.read()
                if (
                    not ok
                    and self._config.source_mode == "sample_video"
                    and self._config.loop_video
                ):
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = capture.read()

                if not ok or frame is None:
                    self._set_status(
                        message="No frame was available from the selected source."
                    )
                    time.sleep(0.2)
                    continue

                # Run YOLO inference
                inference_started = time.perf_counter()
                try:
                    detections = detector.detect(
                        frame,
                        confidence_threshold=self._config.confidence_threshold,
                        image_size=self._config.image_size,
                    )
                except Exception as exc:
                    self._set_status(message=f"YOLO inference failed: {exc}")
                    break
                inference_ms = (time.perf_counter() - inference_started) * 1000

                # Compute table zone in pixels
                height, width = frame.shape[:2]
                table_zone = table_zone_from_percent(
                    width, height, *zone_percents
                )

                # Classify violations
                candidates = classify_incidents(
                    detections, table_zone, self._config.proximity_pixels
                )

                # Annotate frame with overlays
                annotated = _draw_overlays(frame, detections, candidates, table_zone)

                # Log incidents (async logger called from thread)
                logged_count = self._process_incidents(candidates, annotated)

                # Encode frame as JPEG
                ok, encoded = cv2.imencode(
                    ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
                )
                if ok:
                    elapsed = max(time.perf_counter() - last_loop_started, 0.001)
                    last_loop_started = time.perf_counter()
                    self._publish_frame(
                        encoded.tobytes(),
                        {
                            "people": sum(
                                1 for d in detections if d.label == "person"
                            ),
                            "phones": sum(
                                1 for d in detections if d.label == "cell phone"
                            ),
                            "active_rule_matches": len(candidates),
                            "logged_this_frame": logged_count,
                            "inference_ms": round(inference_ms, 1),
                            "fps": round(1.0 / elapsed, 1),
                        },
                    )

                # Rate-limit the loop
                sleep_for = target_interval - (time.perf_counter() - loop_started)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            capture.release()
            self.is_running = False
            # Dispose the worker-local engine and close the loop
            if self._worker_session_factory is not None and self._loop is not None:
                try:
                    self._loop.run_until_complete(worker_engine.dispose())
                except Exception:
                    pass
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    def _open_capture(self):
        """Open a video capture source based on configuration."""
        if self._config.source_mode == "webcam":
            capture = cv2.VideoCapture(self._config.camera_index)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.camera_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.camera_height)
        else:
            video_path = Path(self._config.sample_video_path).expanduser()
            capture = cv2.VideoCapture(str(video_path))

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _fetch_desk_zone(
        self, fallback: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int]:
        """Fetch desk zone percentages from the database.

        Runs the async DB query synchronously from the worker thread.
        Falls back to the provided defaults if the fetch fails.
        """
        try:
            zone_config = self._run_async(self._get_desk_zone_from_db())
            return (
                zone_config.x1_percent,
                zone_config.y1_percent,
                zone_config.x2_percent,
                zone_config.y2_percent,
            )
        except Exception as exc:
            logger.debug("Failed to refresh desk zone from DB: %s", exc)
            return fallback

    async def _get_desk_zone_from_db(self):
        """Async helper to fetch desk zone config using the worker-local session factory."""
        async with self._worker_session_factory() as session:
            return await get_desk_zone(session)

    def _process_incidents(
        self, candidates: list[IncidentCandidate], frame: np.ndarray
    ) -> int:
        """Process incident candidates through the IncidentLogger.

        Calls the async try_log_incident from the synchronous worker thread
        using the worker's own event loop. Also resets tracking for incident
        types no longer detected.

        Returns the count of incidents actually logged this frame.
        """
        active_types = {c.incident_type for c in candidates}

        # Reset tracking for types that are no longer active
        for incident_type in list(self._incident_logger._first_seen.keys()):
            if incident_type not in active_types:
                self._incident_logger.reset_tracking(incident_type)

        logged_count = 0
        for candidate in candidates:
            try:
                incident_id = self._run_async(
                    self._incident_logger.try_log_incident(
                        candidate=candidate,
                        frame=frame,
                        camera_name="Camera 1",
                        location="Production Floor",
                    )
                )
                if incident_id is not None:
                    logged_count += 1
                    self._set_status(
                        message=(
                            f"Incident #{incident_id} logged: "
                            f"{candidate.incident_type} "
                            f"({candidate.confidence:.2f} confidence)."
                        )
                    )
            except Exception as exc:
                logger.error(
                    "Failed to log incident %s: %s",
                    candidate.incident_type,
                    exc,
                )

        return logged_count

    def _publish_frame(self, jpeg: bytes, status_update: dict[str, Any]) -> None:
        """Publish a new annotated JPEG frame and update status metrics."""
        with self._frame_condition:
            self._latest_jpeg = jpeg
            self._frame_id += 1
            self._status.update(status_update)
            self._frame_condition.notify_all()

    def _set_status(self, **updates: Any) -> None:
        """Update status fields and notify waiting consumers."""
        with self._frame_condition:
            self._status.update(updates)
            self._frame_condition.notify_all()


# --------------------------------------------------------------------------
# Frame annotation helpers
# --------------------------------------------------------------------------


def _draw_overlays(
    frame: np.ndarray,
    detections: list[Detection],
    candidates: list[IncidentCandidate],
    table_zone: tuple[int, int, int, int],
) -> np.ndarray:
    """Draw bounding boxes, labels, violation indicators, and desk zone overlay.

    Annotation rules:
    - Desk zone: cyan-ish rectangle with "DESK ZONE" label
    - Person detections: blue-orange bounding box
    - Phone with violation: red bounding box
    - Phone without violation: green bounding box
    - Document with violation: red bounding box
    - Violation type text displayed below flagged objects
    - Labels include confidence scores
    """
    # Draw desk zone overlay (cyan-ish color)
    tx1, ty1, tx2, ty2 = table_zone
    overlay_color = (200, 200, 0)  # cyan-ish in BGR
    cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), overlay_color, 2)
    cv2.putText(
        frame,
        "DESK ZONE",
        (tx1, max(ty1 - 8, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        overlay_color,
        2,
    )

    # Build a lookup of bboxes that have violations
    candidate_bboxes: dict[tuple[int, int, int, int], str] = {
        candidate.phone_bbox: candidate.incident_type for candidate in candidates
    }

    # Draw bounding boxes for each detection
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox

        if detection.label == "person":
            # Person: blue-orange color
            color = (60, 180, 255)  # BGR for blue-orange
        elif detection.bbox in candidate_bboxes:
            # Phone/document with active violation: red
            color = (0, 0, 255)  # BGR for red
        else:
            # Phone/document without violation: green
            color = (0, 220, 80)  # BGR for green

        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Draw label with confidence score
        label = f"{detection.label} {detection.confidence:.2f}"
        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 8, 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

    # Draw violation type text on flagged objects
    for candidate in candidates:
        x1, _, _, y2 = candidate.phone_bbox
        cv2.putText(
            frame,
            candidate.incident_type,
            (x1, y2 + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
        )

    return frame
