"""Frame capture service for webcam and CCTV video sources.

Provides rate-limited frame acquisition with automatic reconnection
for CCTV streams and graceful error handling for webcam devices.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import cv2
import numpy as np

from backend.core.pipeline_types import FrameCaptureConfig, SourceUnavailableError

logger = logging.getLogger(__name__)


class FrameCaptureService:
    """Captures frames from webcam or CCTV sources with rate limiting.

    Supports:
    - Webcam devices via integer camera index
    - CCTV streams via RTSP or HTTP URLs
    - Automatic reconnection for CCTV failures
    - FPS rate limiting via time-based throttling
    """

    def __init__(self, config: FrameCaptureConfig) -> None:
        self._config = config
        self._capture: cv2.VideoCapture | None = None
        self._is_open: bool = False
        self._last_read_time: float = 0.0
        self._frame_interval: float = 1.0 / config.fps_limit

    @property
    def is_open(self) -> bool:
        """Whether the capture source is currently open and available."""
        return self._is_open

    def open(self) -> None:
        """Open the configured video source.

        For webcam sources, opens by integer index and sets resolution.
        For CCTV sources, validates URL scheme and connects via OpenCV.

        Raises:
            ValueError: If CCTV URL scheme is not rtsp:// or http://.
            SourceUnavailableError: If the source cannot be opened.
        """
        if self._config.source_type == "cctv":
            self._validate_cctv_url(str(self._config.source_id))
            self._open_cctv()
        else:
            self._open_webcam()

    def read(self) -> np.ndarray | None:
        """Read a frame from the video source with FPS rate limiting.

        Blocks until the configured frame interval has elapsed since the
        last successful read. For webcam sources, returns None on read
        failure. For CCTV sources, triggers reconnection on read failure.

        Returns:
            Frame as a NumPy array (BGR), or None if frame unavailable
            (webcam only).

        Raises:
            SourceUnavailableError: If CCTV reconnection is exhausted.
        """
        if not self._is_open or self._capture is None:
            raise SourceUnavailableError(
                f"Cannot read from {self._config.source_type} source "
                f"'{self._config.source_id}': source is not open"
            )

        # Rate limiting: wait until frame interval has elapsed
        self._wait_for_frame_interval()

        ret, frame = self._capture.read()

        if ret and frame is not None:
            self._last_read_time = time.monotonic()
            return frame

        # Handle read failure based on source type
        if self._config.source_type == "webcam":
            logger.debug(
                "Frame read failed for webcam source %s, skipping frame",
                self._config.source_id,
            )
            return None
        else:
            # CCTV: attempt reconnection
            logger.warning(
                "Frame read failed for CCTV source '%s', attempting reconnection",
                self._config.source_id,
            )
            self._reconnect_cctv()
            # After successful reconnection, try reading again
            ret, frame = self._capture.read()
            if ret and frame is not None:
                self._last_read_time = time.monotonic()
                return frame
            # If still failing after reconnection, raise
            raise SourceUnavailableError(
                f"Cannot read from {self._config.source_type} source "
                f"'{self._config.source_id}': read failed after reconnection"
            )

    def release(self) -> None:
        """Release the video capture resource.

        Releases the OpenCV VideoCapture object and marks the service
        as closed. Completes within 5 seconds.
        """
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._is_open = False
        logger.info(
            "Released %s source '%s'",
            self._config.source_type,
            self._config.source_id,
        )

    def _validate_cctv_url(self, url: str) -> None:
        """Validate that a CCTV URL uses an accepted scheme.

        Raises:
            ValueError: If the URL scheme is not rtsp:// or http://.
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("rtsp", "http"):
            raise ValueError(
                f"Invalid CCTV URL scheme '{parsed.scheme}': "
                f"must be 'rtsp://' or 'http://'. Got: {url}"
            )

    def _open_webcam(self) -> None:
        """Open a webcam device by integer index and set resolution.

        Raises:
            SourceUnavailableError: If the webcam cannot be opened.
        """
        source_id = int(self._config.source_id)
        cap = cv2.VideoCapture(source_id)

        if not cap.isOpened():
            cap.release()
            raise SourceUnavailableError(
                f"Cannot open {self._config.source_type} source "
                f"'{self._config.source_id}': webcam device not found"
            )

        # Set configured resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)

        self._capture = cap
        self._is_open = True
        logger.info(
            "Opened webcam source %s at %dx%d",
            source_id,
            self._config.width,
            self._config.height,
        )

    def _open_cctv(self) -> None:
        """Open a CCTV stream via URL with reconnection support.

        Attempts to connect up to reconnect_attempts times with
        reconnect_interval delay between attempts.

        Raises:
            SourceUnavailableError: If all connection attempts fail.
        """
        url = str(self._config.source_id)

        for attempt in range(1, self._config.reconnect_attempts + 1):
            cap = cv2.VideoCapture(url)

            if cap.isOpened():
                self._capture = cap
                self._is_open = True
                logger.info("Opened CCTV source '%s' on attempt %d", url, attempt)
                return

            cap.release()
            logger.warning(
                "CCTV connection attempt %d/%d failed for '%s'",
                attempt,
                self._config.reconnect_attempts,
                url,
            )

            if attempt < self._config.reconnect_attempts:
                time.sleep(self._config.reconnect_interval)

        raise SourceUnavailableError(
            f"Cannot open {self._config.source_type} source "
            f"'{self._config.source_id}': all {self._config.reconnect_attempts} "
            f"connection attempts failed"
        )

    def _reconnect_cctv(self) -> None:
        """Attempt to reconnect to a CCTV stream.

        Releases the current capture and attempts to re-open the source.

        Raises:
            SourceUnavailableError: If reconnection fails after all attempts.
        """
        logger.info(
            "Starting reconnection sequence for CCTV source '%s'",
            self._config.source_id,
        )

        # Release current capture
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._is_open = False

        # Re-open with retry logic
        self._open_cctv()

    def _wait_for_frame_interval(self) -> None:
        """Block until the configured frame interval has elapsed."""
        if self._last_read_time == 0.0:
            return

        elapsed = time.monotonic() - self._last_read_time
        remaining = self._frame_interval - elapsed

        if remaining > 0:
            time.sleep(remaining)
