"""Compliance Event Engine — configuration, data models, and implementation."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.config import AppConfig
from backend.core.incident_logger import IncidentLogger, IncidentConfig
from backend.core.pipeline_types import Detection, DetectionEvent, DetectionResult
from backend.core.rules import IncidentCandidate, classify_incidents, table_zone_from_percent
from backend.db.desk_zone import get_desk_zone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComplianceEngineConfig:
    """Immutable configuration for the Compliance Event Engine.

    Fields:
        duration_threshold: Seconds a violation must persist before logging.
        cooldown_seconds: Window for suppressing duplicate incidents.
        proximity_pixels: Max pixel distance for phone-to-person proximity.
        screenshots_dir: Directory for storing incident screenshots.
    """

    duration_threshold: float = 2.0
    cooldown_seconds: float = 10.0
    proximity_pixels: int = 80
    screenshots_dir: Path = Path("screenshots")

    def __post_init__(self) -> None:
        """Validate configuration constraints at construction time."""
        if not (0.0 < self.duration_threshold <= 300.0):
            raise ValueError(
                "duration_threshold must be greater than 0.0 and less than or equal to 300.0"
            )
        if not (0.0 <= self.cooldown_seconds <= 3600.0):
            raise ValueError(
                "cooldown_seconds must be greater than or equal to 0.0 and less than or equal to 3600.0"
            )
        if not (0 < self.proximity_pixels <= 2000):
            raise ValueError(
                "proximity_pixels must be greater than 0 and less than or equal to 2000"
            )

    @classmethod
    def from_app_config(cls, app_config: AppConfig) -> ComplianceEngineConfig:
        """Derive a ComplianceEngineConfig from an existing AppConfig instance."""
        return cls(
            duration_threshold=float(app_config.duration_threshold),
            cooldown_seconds=float(app_config.cooldown_seconds),
            proximity_pixels=app_config.proximity_pixels,
            screenshots_dir=Path(app_config.screenshots_dir),
        )


@dataclass
class ViolationEntry:
    """Tracks an active violation for duration-based gating.

    Fields:
        first_seen: Monotonic timestamp when the violation was first detected.
        last_candidate: The most recent IncidentCandidate for this violation.
    """

    first_seen: float
    last_candidate: IncidentCandidate


# --- Detection Conversion ---

_REQUIRED_BBOX_KEYS = {"x1", "y1", "x2", "y2"}


def _round_half_up(value: float | int) -> int:
    """Round a numeric value to the nearest integer using ROUND_HALF_UP.

    Python's built-in round() uses banker's rounding (ROUND_HALF_EVEN),
    so we use Decimal for true half-up behaviour (2.5 → 3).
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def convert_detection_result(result: DetectionResult) -> Detection | None:
    """Convert a DetectionResult to a Detection, or None if invalid.

    Validation rules:
    - bbox dict must contain keys x1, y1, x2, y2
    - confidence must be in [0.0, 1.0]
    - label must be ≤ 20 characters

    Bbox coordinates are rounded to the nearest integer using half-up rounding.
    Confidence is preserved without modification.
    """
    # Validate label length
    if len(result.label) > 20:
        return None

    # Validate confidence range
    if not (0.0 <= result.confidence <= 1.0):
        return None

    # Validate bbox dict has required keys
    if not isinstance(result.bbox, dict):
        return None
    if not _REQUIRED_BBOX_KEYS.issubset(result.bbox.keys()):
        return None

    # Round bbox coordinates using half-up rounding
    try:
        x1 = _round_half_up(result.bbox["x1"])
        y1 = _round_half_up(result.bbox["y1"])
        x2 = _round_half_up(result.bbox["x2"])
        y2 = _round_half_up(result.bbox["y2"])
    except (TypeError, ValueError, ArithmeticError):
        return None

    return Detection(
        label=result.label,
        confidence=result.confidence,
        bbox=(x1, y1, x2, y2),
        class_id=result.class_id,
    )


def convert_all_detections(detections: list[DetectionResult]) -> list[Detection]:
    """Convert a list of DetectionResults, filtering out invalid ones.

    Applies convert_detection_result to each item and discards None results.
    An empty input list produces an empty output list without error.
    """
    results: list[Detection] = []
    for det in detections:
        converted = convert_detection_result(det)
        if converted is not None:
            results.append(converted)
    return results


# --- Compliance Event Engine Implementation ---


class ComplianceEventEngineImpl:
    """Compliance Event Engine — processes detection events and manages violation tracking.

    Implements the ComplianceEventEngine protocol. Manages lifecycle (start/stop),
    desk zone caching, violation tracking with duration gating, and incident logging.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        screenshots_dir: str | Path,
        config: AppConfig | ComplianceEngineConfig,
    ) -> None:
        # Derive ComplianceEngineConfig if AppConfig was provided
        if isinstance(config, AppConfig):
            self._config = ComplianceEngineConfig.from_app_config(config)
        else:
            self._config = config

        self._session_factory = session_factory

        # Validate screenshots_dir length (max 260 chars)
        screenshots_path = Path(screenshots_dir)
        if len(str(screenshots_path)) > 260:
            raise ValueError(
                "screenshots_dir path must not exceed 260 characters"
            )

        # Validate that parent directory exists or can be created
        parent = screenshots_path.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ValueError(
                    f"screenshots_dir parent directory does not exist and cannot be created: {parent}"
                ) from exc

        # Create screenshots directory (including parents) if it doesn't exist
        screenshots_path.mkdir(parents=True, exist_ok=True)
        self._screenshots_dir = screenshots_path

        # Create IncidentLogger with appropriate config
        incident_config = IncidentConfig(
            duration_threshold=self._config.duration_threshold,
            cooldown_seconds=self._config.cooldown_seconds,
        )
        self._incident_logger = IncidentLogger(
            db_session_factory=self._session_factory,
            screenshot_dir=self._screenshots_dir,
            config=incident_config,
        )

        # Initialize async lock for shared state protection
        self._lock = asyncio.Lock()

        # Desk zone cache: stores (x1_percent, y1_percent, x2_percent, y2_percent) or None
        self._desk_zone_cache: tuple[int, int, int, int] | None = None

        # Violation tracker: keyed by (camera_id, incident_type) -> ViolationEntry
        self._violation_tracker: dict[tuple[str, str], ViolationEntry] = {}

        # Processing flag: an asyncio.Event that is SET when process_event is running
        self._processing = asyncio.Event()

    async def start(self) -> None:
        """Initialize violation tracker and load desk zone from DB.

        If the database is unavailable, initializes with zone=None and logs a WARNING.
        """
        self._violation_tracker = {}

        # Load desk zone from DB, handle failure gracefully
        try:
            async with self._session_factory() as session:
                zone_config = await get_desk_zone(session)
                self._desk_zone_cache = (
                    zone_config.x1_percent,
                    zone_config.y1_percent,
                    zone_config.x2_percent,
                    zone_config.y2_percent,
                )
        except Exception as exc:
            self._desk_zone_cache = None
            logger.warning(
                "Failed to load desk zone from DB during start: %s. "
                "Operating without zone-based classification.",
                exc,
            )

    async def stop(self) -> None:
        """Clear tracker state, waiting up to 5 seconds for in-progress events."""
        # Wait up to 5 seconds for any in-progress process_event to finish
        if self._processing.is_set():
            try:
                await asyncio.wait_for(self._wait_for_processing_done(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "stop() timed out waiting for in-progress process_event to complete"
                )

        # Clear tracker state
        self._violation_tracker = {}

    async def _wait_for_processing_done(self) -> None:
        """Wait until the processing event is cleared."""
        while self._processing.is_set():
            await asyncio.sleep(0.05)

    async def refresh_desk_zone(self) -> None:
        """Re-read desk zone from DB and update cache.

        Retains previous cached value on failure.
        Raises TimeoutError if the query exceeds 5 seconds.
        """
        try:
            async with self._session_factory() as session:
                zone_config = await asyncio.wait_for(
                    get_desk_zone(session), timeout=5.0
                )
                async with self._lock:
                    self._desk_zone_cache = (
                        zone_config.x1_percent,
                        zone_config.y1_percent,
                        zone_config.x2_percent,
                        zone_config.y2_percent,
                    )
        except asyncio.TimeoutError:
            logger.warning("refresh_desk_zone timed out after 5 seconds")
            raise TimeoutError("refresh_desk_zone query exceeded 5 seconds")
        except Exception as exc:
            logger.warning(
                "Failed to refresh desk zone from DB: %s. Retaining cached value.",
                exc,
            )

    async def process_event(self, event: DetectionEvent) -> None:
        """Process a detection event through the full compliance pipeline.

        Implements the ComplianceEventEngine protocol. Orchestrates:
        1. Event validation (empty detections, invalid dimensions)
        2. Detection conversion (DetectionResult → Detection)
        3. Zone loading and pixel conversion
        4. Incident classification via rules engine
        5. Violation tracking with duration gating
        6. Incident logging for confirmed violations

        Errors are handled per-candidate and at the top level to ensure
        resilience. The _processing flag is set/cleared around all work.
        """
        self._processing.set()
        try:
            # Step 1: Validate event — empty detections list
            if not event.detections:
                logger.debug(
                    "Empty detections list for camera_id=%s at timestamp=%s; skipping.",
                    event.camera_id,
                    event.timestamp,
                )
                return

            # Step 2: Validate frame dimensions
            if event.frame_width <= 0 or event.frame_height <= 0:
                logger.warning(
                    "Invalid frame dimensions (%dx%d) for camera_id=%s; skipping.",
                    event.frame_width,
                    event.frame_height,
                    event.camera_id,
                )
                return

            # Step 3: Convert DetectionResults to Detection objects
            detections = convert_all_detections(event.detections)

            # Step 4: Load cached desk zone and convert to pixel coordinates
            zone_pixels: tuple[int, int, int, int] | None = None
            if self._desk_zone_cache is not None:
                x1_pct, y1_pct, x2_pct, y2_pct = self._desk_zone_cache
                zone_pixels = table_zone_from_percent(
                    event.frame_width,
                    event.frame_height,
                    x1_pct,
                    y1_pct,
                    x2_pct,
                    y2_pct,
                )

            # Step 5: Classify incidents
            candidates = classify_incidents(
                detections, zone_pixels, self._config.proximity_pixels
            )

            # Step 6: If no candidates, clear tracker entries for this camera and return
            if not candidates:
                keys_to_remove = [
                    key
                    for key in self._violation_tracker
                    if key[0] == event.camera_id
                ]
                for key in keys_to_remove:
                    del self._violation_tracker[key]
                return

            # Step 7: Update violation tracker and get entries exceeding threshold
            exceeded = self._update_violation_tracker(event.camera_id, candidates)

            # Step 8: Create placeholder frame for screenshot capture
            frame = np.zeros(
                (event.frame_height, event.frame_width, 3), dtype=np.uint8
            )

            # Step 9: For each violation exceeding duration threshold, invoke IncidentLogger
            for entry in exceeded:
                try:
                    result = await self._incident_logger.try_log_incident(
                        candidate=entry.last_candidate,
                        frame=frame,
                        camera_name=event.camera_id,
                        location=event.camera_id,
                    )

                    # Log success if incident was persisted
                    if result is not None:
                        logger.info(
                            "Incident logged: type=%s, id=%d for camera_id=%s",
                            entry.last_candidate.incident_type,
                            result,
                            event.camera_id,
                        )

                    # Reset first_seen after logging attempt (passed the gate)
                    tracker_key = (event.camera_id, entry.last_candidate.incident_type)
                    if tracker_key in self._violation_tracker:
                        self._violation_tracker[tracker_key].first_seen = time.monotonic()

                except Exception as exc:
                    # Handle exceptions per candidate independently
                    logger.error(
                        "Error logging incident type=%s for camera_id=%s: %s",
                        entry.last_candidate.incident_type,
                        event.camera_id,
                        exc,
                    )
                    continue

        except Exception as exc:
            # Top-level exception handler: log and return without re-raising
            logger.error(
                "Unhandled error in process_event at timestamp=%s, camera_id=%s: %s",
                event.timestamp,
                event.camera_id,
                exc.__class__.__name__,
            )
        finally:
            self._processing.clear()

    def _update_violation_tracker(
        self, camera_id: str, candidates: list[IncidentCandidate]
    ) -> list[ViolationEntry]:
        """Update violation tracker state and return entries exceeding the duration threshold.

        Algorithm:
        1. Get current monotonic time.
        2. Collect unique incident_types from the candidates list.
        3. For each unique incident_type:
           - If (camera_id, incident_type) exists: update last_candidate, keep first_seen.
           - If new: create ViolationEntry with first_seen=now.
           - For duplicates (same incident_type), use the first candidate encountered.
        4. Prune: remove any (camera_id, *) entries whose incident_type is NOT in current types.
        5. Filter entries where (now - first_seen) >= duration_threshold.
        6. Return the filtered list of violations that exceed the threshold.
        """
        now = time.monotonic()

        # Step 2: Collect unique incident_types, preserving first occurrence order
        seen_types: dict[str, IncidentCandidate] = {}
        for candidate in candidates:
            if candidate.incident_type not in seen_types:
                seen_types[candidate.incident_type] = candidate

        current_types = set(seen_types.keys())

        # Step 3: Upsert entries for each unique incident_type
        for incident_type, candidate in seen_types.items():
            key = (camera_id, incident_type)
            if key in self._violation_tracker:
                # Existing entry: retain first_seen, update last_candidate
                self._violation_tracker[key].last_candidate = candidate
            else:
                # New entry: record first_seen as now
                self._violation_tracker[key] = ViolationEntry(
                    first_seen=now,
                    last_candidate=candidate,
                )

        # Step 4: Prune entries for this camera_id whose incident_type is no longer present
        keys_to_remove = [
            key
            for key in self._violation_tracker
            if key[0] == camera_id and key[1] not in current_types
        ]
        for key in keys_to_remove:
            del self._violation_tracker[key]

        # Step 5 & 6: Filter entries exceeding the duration threshold
        threshold = self._config.duration_threshold
        exceeded: list[ViolationEntry] = []
        for key, entry in self._violation_tracker.items():
            if key[0] == camera_id and (now - entry.first_seen) >= threshold:
                exceeded.append(entry)

        return exceeded
