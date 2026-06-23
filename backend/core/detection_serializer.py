"""Serialization and validation utilities for DetectionResult objects.

Provides functions to serialize DetectionResult to JSON-compatible dicts,
deserialize dicts back to DetectionResult, and validate constraint invariants.
"""

from __future__ import annotations

import json
from typing import Any

from backend.core.pipeline_types import DetectionResult

# Validation constants
LABEL_MAX_LENGTH = 20
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0
BBOX_REQUIRED_KEYS = {"x1", "y1", "x2", "y2"}


def serialize_detection(result: DetectionResult) -> dict[str, Any]:
    """Serialize a DetectionResult to a JSON-compatible dictionary.

    Args:
        result: A DetectionResult dataclass instance.

    Returns:
        A dictionary with keys: label, confidence, bbox, class_id.
        The bbox value is a dict with keys x1, y1, x2, y2.
    """
    return {
        "label": result.label,
        "confidence": result.confidence,
        "bbox": {
            "x1": result.bbox["x1"],
            "y1": result.bbox["y1"],
            "x2": result.bbox["x2"],
            "y2": result.bbox["y2"],
        },
        "class_id": result.class_id,
    }


def deserialize_detection(data: dict[str, Any]) -> DetectionResult:
    """Reconstruct a DetectionResult from a dictionary.

    Args:
        data: A dictionary with keys: label, confidence, bbox, class_id.

    Returns:
        A DetectionResult dataclass instance.

    Raises:
        KeyError: If required keys are missing from data or bbox.
        TypeError: If data is not a dict.
    """
    bbox_data = data["bbox"]
    return DetectionResult(
        label=data["label"],
        confidence=float(data["confidence"]),
        bbox={
            "x1": int(bbox_data["x1"]),
            "y1": int(bbox_data["y1"]),
            "x2": int(bbox_data["x2"]),
            "y2": int(bbox_data["y2"]),
        },
        class_id=int(data["class_id"]),
    )


def validate_detection(result: DetectionResult) -> bool:
    """Validate a DetectionResult against structural constraints.

    Checks:
        - label: string with max 20 characters
        - confidence: float in [0.0, 1.0]
        - bbox: dict with keys x1, y1, x2, y2, all non-negative integers
        - class_id: non-negative integer

    Args:
        result: A DetectionResult dataclass instance.

    Returns:
        True if all constraints are satisfied, False otherwise.
    """
    # Validate label
    if not isinstance(result.label, str):
        return False
    if len(result.label) > LABEL_MAX_LENGTH:
        return False

    # Validate confidence
    if not isinstance(result.confidence, (int, float)):
        return False
    if result.confidence < CONFIDENCE_MIN or result.confidence > CONFIDENCE_MAX:
        return False

    # Validate bbox
    if not isinstance(result.bbox, dict):
        return False
    if set(result.bbox.keys()) != BBOX_REQUIRED_KEYS:
        return False
    for key in BBOX_REQUIRED_KEYS:
        value = result.bbox[key]
        if not isinstance(value, int):
            return False
        if value < 0:
            return False

    # Validate class_id
    if not isinstance(result.class_id, int):
        return False
    if result.class_id < 0:
        return False

    return True


def serialize_detection_to_json(result: DetectionResult) -> str:
    """Serialize a DetectionResult to a JSON string.

    Args:
        result: A DetectionResult dataclass instance.

    Returns:
        A JSON string representation.
    """
    return json.dumps(serialize_detection(result))


def deserialize_detection_from_json(json_str: str) -> DetectionResult:
    """Deserialize a DetectionResult from a JSON string.

    Args:
        json_str: A JSON string representing a DetectionResult.

    Returns:
        A DetectionResult dataclass instance.
    """
    data = json.loads(json_str)
    return deserialize_detection(data)
