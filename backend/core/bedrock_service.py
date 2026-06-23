"""AWS Bedrock integration service using Amazon Nova Lite for compliance analysis.

Cost-optimization strategies:
- Concise system prompts to minimize input tokens
- In-memory LRU cache with TTL to avoid duplicate calls
- Capped max_tokens to prevent runaway responses
- Batch event summarization (one call per request, not per event)
- Graceful degradation when credentials are missing
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BedrockConfig:
    """Configuration for the Bedrock AI service.

    Fields:
        enabled: Whether the AI service is active (requires valid credentials).
        region: AWS region for Bedrock endpoint.
        model_id: Bedrock model identifier (Nova Lite).
        max_tokens: Maximum output tokens per response (cost control).
        temperature: Sampling temperature for generation.
        cache_ttl_seconds: How long to cache identical requests.
        cache_max_size: Maximum number of cached responses.
    """

    enabled: bool = False
    region: str = "us-east-1"
    model_id: str = "us.amazon.nova-lite-v1:0"
    max_tokens: int = 300
    temperature: float = 0.3
    cache_ttl_seconds: int = 120
    cache_max_size: int = 64


@dataclass
class _CacheEntry:
    """Internal cache entry with timestamp."""

    response: dict[str, Any]
    created_at: float


class BedrockComplianceService:
    """Handles AI-powered compliance analysis via Amazon Bedrock Nova Lite.

    Provides structured incident summarization, risk assessment, and
    pattern detection. Implements in-memory caching to reduce redundant
    API calls and control costs.
    """

    _SYSTEM_PROMPT = (
        "You are a concise security compliance analyst. "
        "Given cellphone detection events in a restricted workspace, respond ONLY with valid JSON:\n"
        '{"summary":"<1-2 sentence overview>","riskLevel":"<Low|Medium|High|Critical>",'
        '"activeViolations":{"PHONE_ON_TABLE":<count>,"PHONE_HELD_OR_NEAR_PERSON":<count>},'
        '"patterns":"<1 sentence pattern observation>"}\n'
        "Rules: riskLevel is Critical if >=5 events or any confidence>0.9, "
        "High if >=3 events, Medium if >=2, Low otherwise."
    )

    def __init__(self, config: BedrockConfig) -> None:
        self._config = config
        self._client: Any | None = None
        self._cache: dict[str, _CacheEntry] = {}

        if config.enabled:
            try:
                import boto3

                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=config.region,
                )
                logger.info(
                    "Bedrock compliance service initialized (model=%s, region=%s)",
                    config.model_id,
                    config.region,
                )
            except Exception as exc:
                logger.warning("Failed to initialize Bedrock client: %s", exc)
                self._client = None

    @property
    def available(self) -> bool:
        """Whether the service is ready to make Bedrock calls."""
        return self._client is not None

    async def analyze_events(
        self,
        events: list[dict[str, Any]],
        view_context: str = "dashboard",
    ) -> dict[str, Any]:
        """Analyze compliance events and return structured summary.

        Args:
            events: List of detection events with id, type, confidence, timestamp.
            view_context: UI context for tailoring the response.

        Returns:
            Dict with summary, riskLevel, activeViolations, patterns.
            Falls back to rule-based response if Bedrock is unavailable.
        """
        if not self.available:
            return self._fallback_analysis(events)

        # Build cache key from event data
        cache_key = self._compute_cache_key(events, view_context)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Build the user prompt — minimal tokens
        user_prompt = self._build_user_prompt(events, view_context)

        try:
            response = await self._invoke_model(user_prompt)
            self._put_cache(cache_key, response)
            return response
        except Exception as exc:
            logger.warning("Bedrock invocation failed, using fallback: %s", exc)
            return self._fallback_analysis(events)

    async def _invoke_model(self, user_prompt: str) -> dict[str, Any]:
        """Call Bedrock Nova Lite with the Converse API.

        Uses the Converse API for cross-model compatibility and cleaner interface.
        Runs the synchronous boto3 call in a thread to avoid blocking the event loop.
        """
        import asyncio

        def _call() -> dict[str, Any]:
            response = self._client.converse(
                modelId=self._config.model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ],
                system=[{"text": self._SYSTEM_PROMPT}],
                inferenceConfig={
                    "maxTokens": self._config.max_tokens,
                    "temperature": self._config.temperature,
                },
            )

            # Extract text from response
            output_message = response["output"]["message"]
            text_content = output_message["content"][0]["text"]

            # Parse JSON response
            parsed = json.loads(text_content)
            return self._validate_response(parsed)

        return await asyncio.get_event_loop().run_in_executor(None, _call)

    def _build_user_prompt(self, events: list[dict[str, Any]], view_context: str) -> str:
        """Build a token-efficient user prompt from events."""
        # Compact event representation to minimize input tokens
        compact_events = []
        for e in events[:20]:  # Cap at 20 events to control input size
            compact_events.append(
                f"{e.get('type','unknown')}|conf:{e.get('confidence',0):.2f}|{e.get('timestamp','')}"
            )

        return f"Context:{view_context}\nEvents({len(events)}):\n" + "\n".join(compact_events)

    def _compute_cache_key(self, events: list[dict[str, Any]], view_context: str) -> str:
        """Generate a deterministic cache key for the request."""
        # Use sorted event IDs + types for deduplication
        key_data = json.dumps(
            {
                "ctx": view_context,
                "events": sorted(
                    [{"id": e.get("id"), "type": e.get("type")} for e in events],
                    key=lambda x: x.get("id", 0),
                ),
            },
            sort_keys=True,
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached(self, key: str) -> dict[str, Any] | None:
        """Return cached response if still within TTL."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.created_at > self._config.cache_ttl_seconds:
            del self._cache[key]
            return None
        return entry.response

    def _put_cache(self, key: str, response: dict[str, Any]) -> None:
        """Store a response in cache, evicting oldest if at capacity."""
        if len(self._cache) >= self._config.cache_max_size:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]
        self._cache[key] = _CacheEntry(response=response, created_at=time.time())

    def _validate_response(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Ensure the parsed response matches expected schema."""
        valid_risk_levels = {"Low", "Medium", "High", "Critical"}
        risk = parsed.get("riskLevel", "Medium")
        if risk not in valid_risk_levels:
            risk = "Medium"

        return {
            "summary": str(parsed.get("summary", "Analysis unavailable.")),
            "riskLevel": risk,
            "activeViolations": parsed.get("activeViolations", {}),
            "patterns": str(parsed.get("patterns", "No patterns identified.")),
        }

    def _fallback_analysis(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Rule-based fallback when Bedrock is unavailable.

        Provides deterministic analysis without incurring API costs.
        """
        if not events:
            return {
                "summary": "No compliance events to analyze.",
                "riskLevel": "Low",
                "activeViolations": {},
                "patterns": "No activity detected.",
            }

        # Count violations by type
        violations: dict[str, int] = {}
        max_confidence = 0.0
        for e in events:
            event_type = e.get("type", "unknown")
            violations[event_type] = violations.get(event_type, 0) + 1
            conf = e.get("confidence", 0.0)
            if conf > max_confidence:
                max_confidence = conf

        total = len(events)

        # Determine risk level using same rules as the prompt
        if total >= 5 or max_confidence > 0.9:
            risk_level = "Critical"
        elif total >= 3:
            risk_level = "High"
        elif total >= 2:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        summary = (
            f"{total} compliance event(s) detected. "
            f"Highest confidence: {max_confidence:.0%}."
        )

        # Simple pattern detection
        dominant_type = max(violations, key=violations.get) if violations else "none"
        patterns = f"Primary violation type: {dominant_type} ({violations.get(dominant_type, 0)} occurrences)."

        return {
            "summary": summary,
            "riskLevel": risk_level,
            "activeViolations": violations,
            "patterns": patterns,
        }
