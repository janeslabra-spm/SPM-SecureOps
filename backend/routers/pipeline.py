"""REST API endpoints for the AI Detection Pipeline.

Provides endpoints to start, stop, configure, and query the detection
pipeline including real-time status, latest detections, and runtime
configuration updates.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.pipeline_manager import PipelineManager
from backend.core.pipeline_types import SourceUnavailableError
from backend.db.audit_queries import insert_audit_log
from backend.db.session import get_session_factory
from backend.schemas.pipeline import (
    DetectionResultSchema,
    ErrorResponse,
    PipelineConfigResponse,
    PipelineConfigUpdate,
    PipelineStartRequest,
    PipelineStartResponse,
    PipelineStatusResponse,
    PipelineStopResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


async def _audit_log(event_type: str, description: str) -> None:
    """Fire-and-forget audit log insertion.

    Failures are logged but never propagate to the caller.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await insert_audit_log(
                session, event_type=event_type, description=description
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit log insert failed (%s): %s", event_type, exc)


def _get_pipeline_manager(request: Request) -> PipelineManager:
    """Retrieve the PipelineManager from application state."""
    return request.app.state.pipeline_manager


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(request: Request) -> PipelineStatusResponse:
    """Return current pipeline running state, metrics, and error info."""
    manager = _get_pipeline_manager(request)
    metrics = manager.get_status()
    return PipelineStatusResponse(
        running=metrics.running,
        frames_processed=metrics.frames_processed,
        current_fps=metrics.current_fps,
        last_inference_ms=metrics.last_inference_ms,
        error=metrics.error,
        per_class_counts=metrics.per_class_counts,
    )


@router.post(
    "/start",
    response_model=PipelineStartResponse,
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def start_pipeline(
    request: Request, body: PipelineStartRequest
) -> PipelineStartResponse:
    """Start the detection pipeline with the specified source.

    Returns 200 on success, 409 if already running, 503 if source
    unavailable, 422 on validation errors (handled by Pydantic).
    """
    manager = _get_pipeline_manager(request)

    try:
        manager.start(source_type=body.source_type, source_id=body.source_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SourceUnavailableError as exc:
        await _audit_log(
            "pipeline_error",
            f"Pipeline start failed: source unavailable ({body.source_type}:{body.source_id})",
        )
        raise HTTPException(status_code=503, detail=str(exc))

    await _audit_log(
        "pipeline_start",
        f"Pipeline started with source {body.source_type}:{body.source_id}",
    )

    return PipelineStartResponse(
        running=True,
        source_type=body.source_type,
        source_id=body.source_id,
    )


@router.post(
    "/stop",
    response_model=PipelineStopResponse,
    responses={409: {"model": ErrorResponse}},
)
async def stop_pipeline(request: Request) -> PipelineStopResponse:
    """Stop the detection pipeline and release resources.

    Returns 200 on success, 409 if already inactive.
    """
    manager = _get_pipeline_manager(request)

    try:
        metrics = manager.stop()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await _audit_log(
        "pipeline_stop",
        f"Pipeline stopped — total frames processed: {metrics.frames_processed}",
    )

    return PipelineStopResponse(
        running=False,
        frames_processed=metrics.frames_processed,
    )


@router.get("/detections", response_model=list[DetectionResultSchema])
async def get_detections(request: Request) -> list[dict]:
    """Return latest detection results.

    Returns an empty array if the pipeline is not running or no
    detections have been recorded yet.
    """
    manager = _get_pipeline_manager(request)
    detections = manager.get_latest_detections()

    return [
        {
            "label": d.label,
            "confidence": d.confidence,
            "bbox": d.bbox,
            "class_id": d.class_id,
        }
        for d in detections
    ]


@router.put(
    "/config",
    response_model=PipelineConfigResponse,
    responses={422: {"model": ErrorResponse}},
)
async def update_pipeline_config(
    request: Request, body: PipelineConfigUpdate
) -> PipelineConfigResponse:
    """Update runtime pipeline configuration.

    Accepts partial updates for confidence_threshold, image_size, and
    fps_limit. Pydantic validation automatically returns 422 for
    out-of-range values.
    """
    manager = _get_pipeline_manager(request)

    # Only pass fields that were explicitly provided
    update_kwargs = {}
    if body.confidence_threshold is not None:
        update_kwargs["confidence_threshold"] = body.confidence_threshold
    if body.image_size is not None:
        update_kwargs["image_size"] = body.image_size
    if body.fps_limit is not None:
        update_kwargs["fps_limit"] = body.fps_limit

    current_config = manager.update_config(**update_kwargs)

    return PipelineConfigResponse(
        confidence_threshold=current_config["confidence_threshold"],
        image_size=current_config["image_size"],
        fps_limit=current_config["fps_limit"],
    )
