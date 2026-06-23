"""Frame capture service for webcam, CCTV, and file video sources.

Provides rate-limited frame acquisition with automatic reconnection
for CCTV streams and graceful error handling for webcam devices.
"""

from __future__ import annotations

import logging
import time
import threading
from urllib.parse import urlparse

import cv2
import numpy as np
import requests

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
        For file sources, opens a local video file with optional looping.

        Raises:
            ValueError: If CCTV URL scheme is not rtsp:// or http://.
            SourceUnavailableError: If the source cannot be opened.
        """
        if self._config.source_type == "file":
            self._open_file()
        elif self._config.source_type == "cctv":
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
        if not self._is_open:
            raise SourceUnavailableError(
                f"Cannot read from {self._config.source_type} source "
                f"'{self._config.source_id}': source is not open"
            )

        # Rate limiting: wait until frame interval has elapsed
        self._wait_for_frame_interval()

        # HTTP MJPEG mode (ngrok/HTTPS streams)
        if self._capture is None and hasattr(self, "_http_frame_lock"):
            with self._http_frame_lock:
                frame = self._http_frame
            if frame is not None:
                self._last_read_time = time.monotonic()
                return frame.copy()
            # No frame yet — might still be buffering
            return None

        if self._capture is None:
            raise SourceUnavailableError(
                f"Cannot read from {self._config.source_type} source "
                f"'{self._config.source_id}': no capture available"
            )

        ret, frame = self._capture.read()

        if ret and frame is not None:
            self._last_read_time = time.monotonic()
            return frame

        # Handle read failure based on source type
        if self._config.source_type == "file":
            # Video file ended — loop if configured
            if self._config.loop:
                self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._capture.read()
                if ret and frame is not None:
                    self._last_read_time = time.monotonic()
                    return frame
            raise SourceUnavailableError(
                f"Video file '{self._config.source_id}' ended"
            )
        elif self._config.source_type == "webcam":
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

        Releases the OpenCV VideoCapture object and/or HTTP stream,
        and marks the service as closed.
        """
        self._release_http_stream()
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
            ValueError: If the URL scheme is not rtsp://, http://, or https://.
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("rtsp", "http", "https"):
            raise ValueError(
                f"Invalid CCTV URL scheme '{parsed.scheme}': "
                f"must be 'rtsp://', 'http://', or 'https://'. Got: {url}"
            )

    def _open_file(self) -> None:
        """Open a local video file for playback.

        Raises:
            SourceUnavailableError: If the file cannot be opened.
        """
        file_path = str(self._config.source_id)
        cap = cv2.VideoCapture(file_path)

        if not cap.isOpened():
            cap.release()
            raise SourceUnavailableError(
                f"Cannot open file source '{file_path}': "
                f"file not found or unsupported format"
            )

        self._capture = cap
        self._is_open = True
        logger.info(
            "Opened file source '%s' (loop=%s)",
            file_path,
            self._config.loop,
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

        For HTTPS URLs (e.g., ngrok), uses a requests-based MJPEG reader
        that bypasses browser warnings. For RTSP/HTTP, uses OpenCV directly.

        Raises:
            SourceUnavailableError: If all connection attempts fail.
        """
        url = str(self._config.source_id)
        parsed = urlparse(url)

        # For HTTPS (ngrok) or URLs with ngrok in the domain, use HTTP reader
        if parsed.scheme == "https" or "ngrok" in url:
            self._open_http_mjpeg(url)
            return

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

    def _open_http_mjpeg(self, url: str) -> None:
        """Open an MJPEG stream over HTTP/HTTPS using requests.

        This handles ngrok's browser warning by sending the
        ngrok-skip-browser-warning header. Frames are decoded from the
        multipart MJPEG response in a background thread.
        """
        headers = {
            "ngrok-skip-browser-warning": "true",
            "User-Agent": "SecureOps-Pipeline/1.0",
        }

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
            response.raise_for_status()
        except Exception as exc:
            raise SourceUnavailableError(
                f"Cannot open HTTP stream '{url}': {exc}"
            )

        self._http_response = response
        self._http_frame: np.ndarray | None = None
        self._http_frame_lock = threading.Lock()
        self._http_stop = threading.Event()
        self._http_thread = threading.Thread(
            target=self._http_mjpeg_reader,
            args=(response,),
            daemon=True,
            name="mjpeg-http-reader",
        )
        self._http_thread.start()
        self._is_open = True
        self._capture = None  # Not using OpenCV capture for this mode
        logger.info("Opened HTTP MJPEG source '%s' (ngrok-compatible)", url)

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
        self._release_http_stream()
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._is_open = False

        # Re-open with retry logic
        self._open_cctv()

    def _http_mjpeg_reader(self, response) -> None:
        """Background thread that reads MJPEG frames from an HTTP response.

        Parses the multipart MJPEG stream and decodes JPEG frames into
        numpy arrays, storing the latest frame for the read() method.
        """
        buf = b""
        for chunk in response.iter_content(chunk_size=4096):
            if self._http_stop.is_set():
                break
            buf += chunk
            # Look for JPEG frame boundaries
            start = buf.find(b"\xff\xd8")  # JPEG start
            end = buf.find(b"\xff\xd9")    # JPEG end
            if start != -1 and end != -1 and end > start:
                jpg_data = buf[start:end + 2]
                buf = buf[end + 2:]
                # Decode JPEG to numpy array
                frame = cv2.imdecode(
                    np.frombuffer(jpg_data, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if frame is not None:
                    with self._http_frame_lock:
                        self._http_frame = frame

        logger.info("HTTP MJPEG reader thread exiting")

    def _release_http_stream(self) -> None:
        """Stop the HTTP MJPEG reader thread and close the connection."""
        if hasattr(self, "_http_stop"):
            self._http_stop.set()
        if hasattr(self, "_http_thread") and self._http_thread is not None:
            self._http_thread.join(timeout=3.0)
            self._http_thread = None
        if hasattr(self, "_http_response") and self._http_response is not None:
            try:
                self._http_response.close()
            except Exception:
                pass
            self._http_response = None

    def _wait_for_frame_interval(self) -> None:
        """Block until the configured frame interval has elapsed."""
        if self._last_read_time == 0.0:
            return

        elapsed = time.monotonic() - self._last_read_time
        remaining = self._frame_interval - elapsed

        if remaining > 0:
            time.sleep(remaining)
