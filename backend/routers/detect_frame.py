"""REST endpoint for browser-based camera frame detection.

Accepts JPEG frames uploaded from the browser (via getUserMedia + canvas),
runs YOLO inference, and returns detection results. Also dispatches
detection events to the compliance engine for incident classification.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field

from backend.core.inference_engine import InferenceEngine
from backend.core.bbox_extractor import BoundingBoxExtractor
from backend.core.confidence_scorer import ConfidenceScorer
from backend.core.pipeline_types import DetectionEvent, DetectionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browser-camera", tags=["browser-camera"])


class BoundingBoxResponse(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class FrameDetectionResult(BaseModel):
    label: str
    confidence: float
    bbox: BoundingBoxResponse
    class_id: int


class DetectFrameResponse(BaseModel):
    """Response for a single frame detection request."""

    detections: list[FrameDetectionResult]
    inference_ms: float
    frame_width: int
    frame_height: int


def _get_inference_engine(request: Request) -> InferenceEngine:
    """Get or create the shared inference engine from app state."""
    engine = getattr(request.app.state, "browser_inference_engine", None)
    if engine is None:
        from backend.config import AppConfig
        import os

        config = AppConfig(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/security_monitoring",
            )
        )
        engine = InferenceEngine(
            model_path=config.model_path,
            device=config.device,
        )
        request.app.state.browser_inference_engine = engine
    return engine


@router.post("/detect", response_model=DetectFrameResponse)
async def detect_frame(request: Request, frame: UploadFile = File(...)) -> DetectFrameResponse:
    """Accept a JPEG frame from the browser and run YOLO inference.

    The browser captures frames from getUserMedia, encodes them as JPEG
    via a canvas element, and POSTs them here. Returns bounding boxes
    and classification results.

    Args:
        frame: JPEG image file uploaded from the browser.

    Returns:
        Detection results with bounding boxes, labels, and timing info.
    """
    # Validate content type
    content_type = frame.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=422,
            detail=f"Expected image file, got: {content_type}",
        )

    # Read the image bytes
    image_bytes = await frame.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=422, detail="Empty frame received")

    # Decode JPEG to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=422, detail="Failed to decode image")

    frame_height, frame_width = img.shape[:2]

    # Get inference engine
    engine = _get_inference_engine(request)

    # Get config for thresholds
    from backend.config import AppConfig
    import os

    config = AppConfig(
        database_url=os.environ.get("DATABASE_URL", "")
    )

    # Run inference
    inference_start = time.monotonic()
    raw_detections = engine.infer(
        img,
        image_size=config.image_size,
        confidence_threshold=config.confidence_threshold,
    )
    inference_ms = (time.monotonic() - inference_start) * 1000.0

    # Extract bounding boxes
    bbox_extractor = BoundingBoxExtractor()
    detections = bbox_extractor.extract(raw_detections, frame_width, frame_height)

    # Score and filter
    scorer = ConfidenceScorer(threshold=config.confidence_threshold)
    results = scorer.filter(detections)

    # Build response
    detection_results = [
        FrameDetectionResult(
            label=r.label,
            confidence=round(r.confidence, 3),
            bbox=BoundingBoxResponse(**r.bbox),
            class_id=r.class_id,
        )
        for r in results
    ]

    # Dispatch detection event to compliance engine for incident classification
    dispatcher = getattr(request.app.state, "compliance_dispatcher", None)
    if dispatcher is not None and results:
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_id="browser-camera",
            frame_width=frame_width,
            frame_height=frame_height,
            detections=[
                DetectionResult(
                    label=r.label,
                    confidence=r.confidence,
                    bbox=r.bbox,
                    class_id=r.class_id,
                )
                for r in results
            ],
        )
        try:
            await dispatcher.dispatch(event)
        except Exception as exc:
            logger.warning("Failed to dispatch browser detection event: %s", exc)

    return DetectFrameResponse(
        detections=detection_results,
        inference_ms=round(inference_ms, 1),
        frame_width=frame_width,
        frame_height=frame_height,
    )
