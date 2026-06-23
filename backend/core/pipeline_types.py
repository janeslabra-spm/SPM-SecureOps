"""Internal dataclasses and type definitions for the AI Detection Pipeline.

Defines value objects, configuration containers, and custom exceptions used
across pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# --- Custom Exceptions ---


class SourceUnavailableError(Exception):
    """Raised when a video source cannot be opened after all retry attempts."""

    pass


# --- Configuration ---


@dataclass
class FrameCaptureConfig:
    """Configuration for the frame capture service."""

    source_type: Literal["webcam", "cctv", "file"]
    source_id: int | str  # camera index, URL, or file path
    loop: bool = False  # loop video file when it ends
    width: int = 960  # 320–1920
    height: int = 540  # 240–1080
    fps_limit: int = 2  # 1–30
    reconnect_attempts: int = 3
    reconnect_interval: float = 2.0
    connection_timeout: float = 10.0


# --- Immutable Value Objects ---


@dataclass(frozen=True)
class RawDetection:
    """Raw detection output from the inference engine.

    Contains unprocessed float coordinates directly from the model.
    """

    class_id: int
    label: str
    confidence: float
    bbox_raw: tuple[float, float, float, float]  # raw float coords from model


@dataclass(frozen=True)
class Detection:
    """Normalized detection with integer pixel coordinates.

    Produced by the BoundingBoxExtractor after coordinate normalization
    and validation.
    """

    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) normalized integers
    class_id: int


@dataclass(frozen=True)
class DetectionResult:
    """Final detection result structured for JSON serialization.

    Produced by the ConfidenceScorer after threshold filtering and NMS.
    The bbox is a dict for direct JSON serialization.
    """

    label: str
    confidence: float
    bbox: dict  # {"x1": int, "y1": int, "x2": int, "y2": int}
    class_id: int


# --- Mutable State Containers ---


@dataclass
class DetectionEvent:
    """Event payload dispatched to the compliance event engine."""

    timestamp: str  # ISO 8601 with timezone
    camera_id: str  # max 128 chars
    frame_width: int
    frame_height: int
    detections: list[DetectionResult]


@dataclass
class PipelineMetrics:
    """Runtime metrics exposed via the pipeline status endpoint."""

    running: bool = False
    frames_processed: int = 0
    current_fps: float = 0.0
    last_inference_ms: float = 0.0
    error: str | None = None
    per_class_counts: dict[str, int] = field(
        default_factory=lambda: {"person": 0, "cell phone": 0, "book": 0}
    )
