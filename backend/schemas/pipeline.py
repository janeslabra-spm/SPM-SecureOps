"""Pydantic request/response schemas for the AI Detection Pipeline API.

Defines all models used by the /api/pipeline/* endpoints including
start/stop requests, status responses, configuration updates, and
detection result schemas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Bounding box coordinates in pixel format (top-left to bottom-right)."""

    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(ge=0)
    y2: int = Field(ge=0)


class DetectionResultSchema(BaseModel):
    """A single detection result with label, confidence, bbox, and class ID."""

    label: str = Field(max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    class_id: int = Field(ge=0)


class PipelineStartRequest(BaseModel):
    """Request body for POST /api/pipeline/start."""

    source_type: Literal["webcam", "cctv"]
    source_id: int | str

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: int | str, info) -> int | str:
        """Validate source_id based on source_type.

        Webcam: integer 0–10
        CCTV: string starting with rtsp:// or http://
        """
        if info.data.get("source_type") == "webcam":
            if not isinstance(v, int) or v < 0 or v > 10:
                raise ValueError("Webcam source_id must be integer 0–10")
        elif info.data.get("source_type") == "cctv":
            if not isinstance(v, str) or not (
                v.startswith("rtsp://") or v.startswith("http://")
            ):
                raise ValueError("CCTV source_id must be rtsp:// or http:// URL")
        return v


class PipelineStartResponse(BaseModel):
    """Response body for successful POST /api/pipeline/start."""

    running: bool
    source_type: str
    source_id: int | str


class PipelineStopResponse(BaseModel):
    """Response body for successful POST /api/pipeline/stop."""

    running: bool
    frames_processed: int


class PipelineStatusResponse(BaseModel):
    """Response body for GET /api/pipeline/status."""

    running: bool
    frames_processed: int
    current_fps: float
    last_inference_ms: float
    error: str | None
    per_class_counts: dict[str, int] = Field(default_factory=dict)


class PipelineConfigUpdate(BaseModel):
    """Request body for PUT /api/pipeline/config.

    All fields are optional; only provided fields are updated.
    """

    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    image_size: int | None = Field(default=None, ge=320, le=1280)
    fps_limit: int | None = Field(default=None, ge=1, le=30)


class PipelineConfigResponse(BaseModel):
    """Response body for PUT /api/pipeline/config (current config after update)."""

    confidence_threshold: float
    image_size: int
    fps_limit: int


class ErrorResponse(BaseModel):
    """Standard error response body for 4xx/5xx responses."""

    error: str
