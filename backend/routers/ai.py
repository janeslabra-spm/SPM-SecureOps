"""AI Compliance Assistant API endpoints.

Provides the endpoint consumed by the frontend AiAssistant component
for generating compliance analysis via Amazon Bedrock Nova Lite.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


# --- Pydantic Schemas ---


class AiEventInput(BaseModel):
    """Single event within an AI summary request."""

    id: int
    type: str
    confidence: float
    timestamp: str


class AiSummaryRequest(BaseModel):
    """Request body for AI compliance analysis."""

    events: list[AiEventInput] = Field(default_factory=list, max_length=50)
    viewContext: str = "dashboard"


class AiSummaryResponse(BaseModel):
    """Structured response from the AI compliance analysis."""

    summary: str
    riskLevel: str = Field(pattern=r"^(Low|Medium|High|Critical)$")
    activeViolations: dict[str, int] = Field(default_factory=dict)
    patterns: str


# --- Router ---

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/summary", response_model=AiSummaryResponse)
async def get_ai_summary(body: AiSummaryRequest, request: Request) -> AiSummaryResponse:
    """Generate an AI-powered compliance summary for the given events.

    If Bedrock is available, uses Nova Lite for analysis.
    Otherwise, falls back to a deterministic rule-based response.
    """
    bedrock_service = request.app.state.bedrock_service

    events_data: list[dict[str, Any]] = [
        {
            "id": e.id,
            "type": e.type,
            "confidence": e.confidence,
            "timestamp": e.timestamp,
        }
        for e in body.events
    ]

    result = await bedrock_service.analyze_events(
        events=events_data,
        view_context=body.viewContext,
    )

    return AiSummaryResponse(**result)


@router.get("/status")
async def get_ai_status(request: Request) -> dict[str, Any]:
    """Check whether the AI service is available and its configuration."""
    bedrock_service = request.app.state.bedrock_service
    return {
        "available": bedrock_service.available,
        "model": bedrock_service._config.model_id if bedrock_service.available else None,
        "region": bedrock_service._config.region if bedrock_service.available else None,
    }
