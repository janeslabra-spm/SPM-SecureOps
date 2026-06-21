"""Streaming endpoints for live MJPEG video feed and detection status metrics."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/stream", tags=["stream"])


class StreamStatus(BaseModel):
    """Real-time detection metrics returned by the status endpoint."""

    people: int
    phones: int
    active_rule_matches: int
    logged_this_frame: int
    inference_ms: float
    fps: float
    message: str = ""


def _get_detection_worker(request: Request):
    """Retrieve the detection worker from app state.

    Returns None if no worker is available or it is not running.
    """
    worker = getattr(request.app.state, "detection_worker", None)
    return worker


def _worker_is_active(worker) -> bool:
    """Check if the detection worker exists and is currently running."""
    if worker is None:
        return False
    # Support workers that expose an `is_running` attribute or method
    is_running = getattr(worker, "is_running", None)
    if callable(is_running):
        return is_running()
    if isinstance(is_running, bool):
        return is_running
    # Fallback: if worker exists but has no is_running indicator,
    # check for a running attribute (threading.Thread style)
    running = getattr(worker, "running", None)
    if isinstance(running, bool):
        return running
    # If we can't determine status, assume not active
    return False


async def _mjpeg_frame_generator(worker) -> AsyncGenerator[bytes, None]:
    """Yield MJPEG frames from the detection worker as multipart chunks."""
    last_frame_id = 0
    while True:
        # Use wait_for_frame if available for efficient frame delivery
        wait_fn = getattr(worker, "wait_for_frame", None)
        if wait_fn is not None:
            # Run the blocking wait_for_frame in a thread to avoid blocking
            # the uvicorn event loop (which would prevent other API requests)
            frame_id, jpeg_bytes = await asyncio.to_thread(
                wait_fn, last_frame_id, 2.0
            )
            if jpeg_bytes is None:
                # Check if worker is still active
                if not _worker_is_active(worker):
                    break
                await asyncio.sleep(0.1)
                continue
            last_frame_id = frame_id
        else:
            # Fallback: use get_latest_frame
            get_frame = getattr(worker, "get_latest_frame", None)
            if get_frame is None:
                break
            jpeg_bytes = get_frame()
            if jpeg_bytes is None:
                if not _worker_is_active(worker):
                    break
                await asyncio.sleep(0.5)
                continue

        # Format as MJPEG multipart frame
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg_bytes
            + b"\r\n"
        )

        # Small yield to allow other coroutines to run
        await asyncio.sleep(0)


@router.get("/video.mjpg")
async def stream_video(request: Request):
    """Stream annotated MJPEG video frames from the detection worker.

    Returns a multipart/x-mixed-replace stream of JPEG frames.
    Returns 503 if no detection worker is active.
    """
    worker = _get_detection_worker(request)

    if not _worker_is_active(worker):
        return JSONResponse(
            status_code=503,
            content={"detail": "Monitoring is not active"},
            headers={"Cache-Control": "no-cache"},
        )

    return StreamingResponse(
        _mjpeg_frame_generator(worker),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/status")
async def stream_status(request: Request):
    """Return current detection metrics as JSON.

    Returns 503 if no detection worker is active.
    """
    worker = _get_detection_worker(request)

    if not _worker_is_active(worker):
        return JSONResponse(
            status_code=503,
            content={"detail": "Monitoring is not active"},
            headers={"Cache-Control": "no-cache"},
        )

    # Get status from worker
    get_status = getattr(worker, "get_status", None)
    if get_status is not None:
        status_data = get_status()
        # If worker returns a StreamStatus model, use it directly
        if isinstance(status_data, StreamStatus):
            return JSONResponse(
                content=status_data.model_dump(),
                headers={"Cache-Control": "no-cache"},
            )
        # If it returns a dict, map to StreamStatus fields
        if isinstance(status_data, dict):
            status = StreamStatus(
                people=status_data.get("people", 0),
                phones=status_data.get("phones", 0),
                active_rule_matches=status_data.get("active_rule_matches", 0),
                logged_this_frame=status_data.get("logged_this_frame", 0),
                inference_ms=status_data.get("inference_ms", 0.0),
                fps=status_data.get("fps", 0.0),
                message=status_data.get("message", ""),
            )
            return JSONResponse(
                content=status.model_dump(),
                headers={"Cache-Control": "no-cache"},
            )

    # Fallback: return empty status
    status = StreamStatus(
        people=0,
        phones=0,
        active_rule_matches=0,
        logged_this_frame=0,
        inference_ms=0.0,
        fps=0.0,
        message="Worker status unavailable",
    )
    return JSONResponse(
        content=status.model_dump(),
        headers={"Cache-Control": "no-cache"},
    )
