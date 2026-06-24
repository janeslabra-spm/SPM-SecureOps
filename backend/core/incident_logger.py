"""Incident Logger for persisting security violation incidents.

Handles duration threshold gating, cooldown suppression, screenshot capture,
and graceful failure handling for screenshot writes.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.rules import IncidentCandidate
from backend.db.queries import insert_incident


logger = logging.getLogger(__name__)


@dataclass
class IncidentConfig:
    """Configuration for the Incident Logger thresholds."""

    duration_threshold: float = 2.0  # seconds a violation must persist before logging
    cooldown_seconds: float = 10.0  # seconds to suppress duplicate logging after an incident


class IncidentLogger:
    """Logs confirmed security violations with evidence screenshots.

    Implements duration threshold gating (only logs after a violation persists
    beyond a configurable time), cooldown suppression (prevents duplicate logging
    within a configurable window), and resilient screenshot capture.
    """

    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        screenshot_dir: Path,
        config: IncidentConfig,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._screenshot_dir = screenshot_dir
        self._config = config

        # Tracks when each incident type was first seen (for duration gating)
        self._first_seen: dict[str, float] = {}

        # Tracks when each incident type was last logged (for cooldown suppression)
        self._last_logged: dict[str, float] = {}

    async def try_log_incident(
        self,
        candidate: IncidentCandidate,
        frame: np.ndarray,
        camera_name: str,
        location: str,
    ) -> int | None:
        """Attempt to log an incident, applying duration threshold and cooldown.

        Returns the incident_id if successfully logged, or None if suppressed
        or threshold not yet met.
        """
        incident_type = candidate.incident_type
        now = time.monotonic()

        # Duration threshold gating: track how long the violation has been seen
        if incident_type not in self._first_seen:
            self._first_seen[incident_type] = now

        elapsed = now - self._first_seen[incident_type]
        if elapsed < self._config.duration_threshold:
            # Violation hasn't persisted long enough yet
            return None

        # Cooldown suppression: check if we recently logged this type
        if self._should_suppress(incident_type):
            return None

        # Save screenshot (handles failures gracefully)
        screenshot_path = self._save_screenshot(frame, incident_type)

        # Build notes field
        notes = ""
        if screenshot_path == "":
            notes = "Screenshot capture failed"

        # Persist the incident to the database
        timestamp = datetime.now(tz=timezone.utc)

        async with self._db_session_factory() as session:
            incident = await insert_incident(
                session=session,
                timestamp=timestamp,
                incident_type=incident_type,
                confidence=candidate.confidence,
                camera_name=camera_name,
                location=location,
                screenshot_path=screenshot_path,
                status="Pending Review",
                notes=notes,
            )

        # Update cooldown tracking
        self._last_logged[incident_type] = now

        # Reset first_seen so the next occurrence starts fresh
        self._first_seen.pop(incident_type, None)

        logger.info(
            "Incident logged: type=%s, id=%d, confidence=%.2f, screenshot=%s",
            incident_type,
            incident.incident_id,
            candidate.confidence,
            screenshot_path or "(none)",
        )

        return incident.incident_id

    def _should_suppress(self, incident_type: str) -> bool:
        """Check if an incident type is within the cooldown window.

        Returns True if a recent incident of this type was logged within
        the cooldown period, meaning the current detection should be suppressed.
        """
        if incident_type not in self._last_logged:
            return False

        elapsed = time.monotonic() - self._last_logged[incident_type]
        return elapsed < self._config.cooldown_seconds

    def _save_screenshot(self, frame: np.ndarray, incident_type: str) -> str:
        """Save a screenshot of the current frame as JPEG.

        Filename format: incident_YYYYMMDD_HHMMSSfff_{incident_type}.jpg
        where fff is milliseconds.

        Returns the file path string on success, or empty string on failure.
        """
        try:
            now = datetime.now()
            # Format timestamp with millisecond precision
            timestamp_str = now.strftime("%Y%m%d_%H%M%S") + f"{now.microsecond // 1000:03d}"
            filename = f"incident_{timestamp_str}_{incident_type}.jpg"
            filepath = self._screenshot_dir / filename

            # Ensure the screenshots directory exists
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)

            # Encode frame as JPEG
            success, buffer = cv2.imencode(".jpg", frame)
            if not success:
                logger.error("cv2.imencode failed for incident type: %s", incident_type)
                return ""

            # Write to file
            filepath.write_bytes(buffer.tobytes())
            return str(filepath)

        except Exception as exc:
            logger.error(
                "Failed to save screenshot for incident type %s: %s",
                incident_type,
                exc,
            )
            return ""

    def reset_tracking(self, incident_type: str) -> None:
        """Reset the first-seen timestamp for an incident type.

        Call this when a violation is no longer detected to reset the
        duration threshold tracking.
        """
        self._first_seen.pop(incident_type, None)
