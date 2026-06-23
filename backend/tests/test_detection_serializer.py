"""Unit tests for DetectionResult serialization and validation.

Tests verify:
- Serialization produces correct JSON structure
- Round-trip (serialize → deserialize) produces identical values
- Confidence values match within 1e-6 tolerance
- Validation rejects invalid inputs
"""

from __future__ import annotations

import json
import math

import pytest

from backend.core.detection_serializer import (
    deserialize_detection,
    deserialize_detection_from_json,
    serialize_detection,
    serialize_detection_to_json,
    validate_detection,
)
from backend.core.pipeline_types import DetectionResult


# --- Fixtures ---


@pytest.fixture
def valid_detection() -> DetectionResult:
    """A valid DetectionResult for person detection."""
    return DetectionResult(
        label="person",
        confidence=0.85,
        bbox={"x1": 10, "y1": 20, "x2": 100, "y2": 200},
        class_id=0,
    )


@pytest.fixture
def cellphone_detection() -> DetectionResult:
    """A valid DetectionResult for cell phone detection."""
    return DetectionResult(
        label="cell phone",
        confidence=0.72,
        bbox={"x1": 50, "y1": 60, "x2": 80, "y2": 90},
        class_id=67,
    )


@pytest.fixture
def book_detection() -> DetectionResult:
    """A valid DetectionResult for book detection."""
    return DetectionResult(
        label="book",
        confidence=0.40,
        bbox={"x1": 0, "y1": 0, "x2": 300, "y2": 400},
        class_id=73,
    )


# --- Serialization Tests ---


class TestSerializeDetection:
    """Tests for serialize_detection function."""

    def test_produces_correct_keys(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert set(result.keys()) == {"label", "confidence", "bbox", "class_id"}

    def test_bbox_is_dict_with_correct_keys(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert isinstance(result["bbox"], dict)
        assert set(result["bbox"].keys()) == {"x1", "y1", "x2", "y2"}

    def test_preserves_label(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert result["label"] == "person"

    def test_preserves_confidence(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert result["confidence"] == 0.85

    def test_preserves_bbox_values(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert result["bbox"]["x1"] == 10
        assert result["bbox"]["y1"] == 20
        assert result["bbox"]["x2"] == 100
        assert result["bbox"]["y2"] == 200

    def test_preserves_class_id(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        assert result["class_id"] == 0

    def test_cellphone_detection(self, cellphone_detection: DetectionResult) -> None:
        result = serialize_detection(cellphone_detection)
        assert result["label"] == "cell phone"
        assert result["class_id"] == 67
        assert result["confidence"] == 0.72

    def test_book_detection(self, book_detection: DetectionResult) -> None:
        result = serialize_detection(book_detection)
        assert result["label"] == "book"
        assert result["class_id"] == 73

    def test_is_json_serializable(self, valid_detection: DetectionResult) -> None:
        result = serialize_detection(valid_detection)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed == result

    def test_confidence_at_boundary_zero(self) -> None:
        detection = DetectionResult(
            label="person", confidence=0.0, bbox={"x1": 0, "y1": 0, "x2": 1, "y2": 1}, class_id=0
        )
        result = serialize_detection(detection)
        assert result["confidence"] == 0.0

    def test_confidence_at_boundary_one(self) -> None:
        detection = DetectionResult(
            label="person", confidence=1.0, bbox={"x1": 0, "y1": 0, "x2": 1, "y2": 1}, class_id=0
        )
        result = serialize_detection(detection)
        assert result["confidence"] == 1.0


# --- Deserialization Tests ---


class TestDeserializeDetection:
    """Tests for deserialize_detection function."""

    def test_reconstructs_from_dict(self, valid_detection: DetectionResult) -> None:
        data = {
            "label": "person",
            "confidence": 0.85,
            "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 200},
            "class_id": 0,
        }
        result = deserialize_detection(data)
        assert result.label == "person"
        assert result.confidence == 0.85
        assert result.bbox == {"x1": 10, "y1": 20, "x2": 100, "y2": 200}
        assert result.class_id == 0

    def test_missing_key_raises_key_error(self) -> None:
        data = {"label": "person", "confidence": 0.85, "class_id": 0}
        with pytest.raises(KeyError):
            deserialize_detection(data)

    def test_missing_bbox_key_raises_key_error(self) -> None:
        data = {
            "label": "person",
            "confidence": 0.85,
            "bbox": {"x1": 10, "y1": 20, "x2": 100},  # missing y2
            "class_id": 0,
        }
        with pytest.raises(KeyError):
            deserialize_detection(data)

    def test_coerces_confidence_to_float(self) -> None:
        data = {
            "label": "person",
            "confidence": 1,  # integer
            "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 200},
            "class_id": 0,
        }
        result = deserialize_detection(data)
        assert isinstance(result.confidence, float)
        assert result.confidence == 1.0

    def test_coerces_bbox_values_to_int(self) -> None:
        data = {
            "label": "person",
            "confidence": 0.5,
            "bbox": {"x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 200.0},
            "class_id": 0,
        }
        result = deserialize_detection(data)
        for val in result.bbox.values():
            assert isinstance(val, int)


# --- Round-Trip Tests ---


class TestRoundTrip:
    """Tests for serialize → deserialize round-trip identity."""

    def test_round_trip_person(self, valid_detection: DetectionResult) -> None:
        serialized = serialize_detection(valid_detection)
        deserialized = deserialize_detection(serialized)
        assert deserialized.label == valid_detection.label
        assert deserialized.class_id == valid_detection.class_id
        assert deserialized.bbox == valid_detection.bbox
        assert abs(deserialized.confidence - valid_detection.confidence) < 1e-6

    def test_round_trip_cellphone(self, cellphone_detection: DetectionResult) -> None:
        serialized = serialize_detection(cellphone_detection)
        deserialized = deserialize_detection(serialized)
        assert deserialized.label == cellphone_detection.label
        assert deserialized.class_id == cellphone_detection.class_id
        assert deserialized.bbox == cellphone_detection.bbox
        assert abs(deserialized.confidence - cellphone_detection.confidence) < 1e-6

    def test_round_trip_book(self, book_detection: DetectionResult) -> None:
        serialized = serialize_detection(book_detection)
        deserialized = deserialize_detection(serialized)
        assert deserialized.label == book_detection.label
        assert deserialized.class_id == book_detection.class_id
        assert deserialized.bbox == book_detection.bbox
        assert abs(deserialized.confidence - book_detection.confidence) < 1e-6

    def test_json_string_round_trip(self, valid_detection: DetectionResult) -> None:
        json_str = serialize_detection_to_json(valid_detection)
        deserialized = deserialize_detection_from_json(json_str)
        assert deserialized.label == valid_detection.label
        assert deserialized.class_id == valid_detection.class_id
        assert deserialized.bbox == valid_detection.bbox
        assert abs(deserialized.confidence - valid_detection.confidence) < 1e-6

    def test_round_trip_confidence_precision(self) -> None:
        """Verify confidence with many decimal places survives round-trip within 1e-6."""
        detection = DetectionResult(
            label="person",
            confidence=0.123456789,
            bbox={"x1": 5, "y1": 10, "x2": 50, "y2": 100},
            class_id=0,
        )
        json_str = serialize_detection_to_json(detection)
        deserialized = deserialize_detection_from_json(json_str)
        assert abs(deserialized.confidence - detection.confidence) < 1e-6

    def test_round_trip_boundary_confidence_zero(self) -> None:
        detection = DetectionResult(
            label="book", confidence=0.0, bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10}, class_id=73
        )
        serialized = serialize_detection(detection)
        deserialized = deserialize_detection(serialized)
        assert abs(deserialized.confidence - 0.0) < 1e-6

    def test_round_trip_boundary_confidence_one(self) -> None:
        detection = DetectionResult(
            label="cell phone", confidence=1.0, bbox={"x1": 0, "y1": 0, "x2": 5, "y2": 5}, class_id=67
        )
        serialized = serialize_detection(detection)
        deserialized = deserialize_detection(serialized)
        assert abs(deserialized.confidence - 1.0) < 1e-6


# --- Validation Tests ---


class TestValidateDetection:
    """Tests for validate_detection function."""

    def test_valid_person_detection(self, valid_detection: DetectionResult) -> None:
        assert validate_detection(valid_detection) is True

    def test_valid_cellphone_detection(self, cellphone_detection: DetectionResult) -> None:
        assert validate_detection(cellphone_detection) is True

    def test_valid_book_detection(self, book_detection: DetectionResult) -> None:
        assert validate_detection(book_detection) is True

    def test_label_at_max_length(self) -> None:
        detection = DetectionResult(
            label="a" * 20,
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is True

    def test_rejects_label_exceeding_max_length(self) -> None:
        detection = DetectionResult(
            label="a" * 21,
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_confidence_below_zero(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=-0.01,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_confidence_above_one(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=1.01,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_accepts_confidence_at_zero(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.0,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is True

    def test_accepts_confidence_at_one(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=1.0,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is True

    def test_rejects_negative_bbox_value(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": -1, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_negative_bbox_y1(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": -5, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_float_bbox_value(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10.5, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_negative_class_id(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=-1,
        )
        assert validate_detection(detection) is False

    def test_rejects_missing_bbox_key(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10},  # missing y2
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_rejects_extra_bbox_key(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10, "z": 5},
            class_id=0,
        )
        assert validate_detection(detection) is False

    def test_accepts_zero_bbox_values(self) -> None:
        detection = DetectionResult(
            label="person",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 0, "y2": 0},
            class_id=0,
        )
        assert validate_detection(detection) is True

    def test_accepts_empty_label(self) -> None:
        detection = DetectionResult(
            label="",
            confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
            class_id=0,
        )
        assert validate_detection(detection) is True
