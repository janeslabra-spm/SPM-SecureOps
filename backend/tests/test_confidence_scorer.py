"""Unit tests for the ConfidenceScorer module.

Tests cover threshold filtering, NMS, tie-breaking, ordering,
IoU computation, and threshold validation.
"""

from __future__ import annotations

import logging

import pytest

from backend.core.confidence_scorer import ConfidenceScorer
from backend.core.pipeline_types import Detection, DetectionResult


# --- Helpers ---


def _det(
    label: str = "cell phone",
    confidence: float = 0.8,
    bbox: tuple[int, int, int, int] = (10, 10, 50, 50),
    class_id: int = 67,
) -> Detection:
    """Create a Detection for testing."""
    return Detection(label=label, confidence=confidence, bbox=bbox, class_id=class_id)


# --- Threshold Filtering Tests ---


class TestThresholdFiltering:
    """Tests for confidence threshold filtering behavior."""

    def test_detections_above_threshold_are_kept(self) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        detections = [
            _det(confidence=0.8, bbox=(0, 0, 50, 50)),
            _det(confidence=0.6, bbox=(200, 200, 300, 300)),
        ]
        results = scorer.filter(detections)
        assert len(results) == 2

    def test_detections_below_threshold_are_excluded(self) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        detections = [_det(confidence=0.3), _det(confidence=0.1)]
        results = scorer.filter(detections)
        assert len(results) == 0

    def test_detections_equal_to_threshold_are_retained(self) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        detections = [_det(confidence=0.5)]
        results = scorer.filter(detections)
        assert len(results) == 1
        assert results[0].confidence == 0.5

    def test_empty_input_returns_empty_output(self) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        results = scorer.filter([])
        assert results == []

    def test_default_threshold_is_applied(self) -> None:
        scorer = ConfidenceScorer()
        detections = [_det(confidence=0.39), _det(confidence=0.4)]
        results = scorer.filter(detections)
        assert len(results) == 1
        assert results[0].confidence == 0.4


# --- Threshold Validation Tests ---


class TestThresholdValidation:
    """Tests for confidence threshold validation."""

    def test_valid_threshold_zero(self) -> None:
        scorer = ConfidenceScorer(threshold=0.0)
        assert scorer.threshold == 0.0

    def test_valid_threshold_one(self) -> None:
        scorer = ConfidenceScorer(threshold=1.0)
        assert scorer.threshold == 1.0

    def test_valid_threshold_mid(self) -> None:
        scorer = ConfidenceScorer(threshold=0.7)
        assert scorer.threshold == 0.7

    def test_invalid_threshold_negative_uses_default(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR):
            scorer = ConfidenceScorer(threshold=-0.1)
        assert scorer.threshold == 0.4
        assert "Invalid confidence threshold" in caplog.text

    def test_invalid_threshold_above_one_uses_default(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR):
            scorer = ConfidenceScorer(threshold=1.1)
        assert scorer.threshold == 0.4
        assert "Invalid confidence threshold" in caplog.text

    def test_set_threshold_valid_updates(self) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        scorer.set_threshold(0.7)
        assert scorer.threshold == 0.7

    def test_set_threshold_invalid_reverts_to_default(self, caplog: pytest.LogCaptureFixture) -> None:
        scorer = ConfidenceScorer(threshold=0.5)
        with caplog.at_level(logging.ERROR):
            scorer.set_threshold(2.0)
        assert scorer.threshold == 0.4
        assert "Invalid confidence threshold" in caplog.text


# --- NMS Tests ---


class TestNonMaximumSuppression:
    """Tests for per-class Non-Maximum Suppression."""

    def test_non_overlapping_detections_both_kept(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [
            _det(confidence=0.9, bbox=(0, 0, 50, 50)),
            _det(confidence=0.8, bbox=(200, 200, 300, 300)),
        ]
        results = scorer.filter(detections)
        assert len(results) == 2

    def test_overlapping_same_class_lower_confidence_suppressed(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        # Two overlapping cell phone detections
        detections = [
            _det(confidence=0.9, bbox=(0, 0, 100, 100)),
            _det(confidence=0.7, bbox=(10, 10, 110, 110)),
        ]
        results = scorer.filter(detections)
        assert len(results) == 1
        assert results[0].confidence == 0.9

    def test_overlapping_different_classes_both_kept(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        # Person and cell phone overlap — NMS is per-class
        detections = [
            _det(label="person", confidence=0.9, bbox=(0, 0, 100, 100), class_id=0),
            _det(label="cell phone", confidence=0.8, bbox=(10, 10, 110, 110), class_id=67),
        ]
        results = scorer.filter(detections)
        assert len(results) == 2

    def test_tie_breaking_keeps_larger_area(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        # Same confidence, same class, overlapping with IoU >= 0.5
        # Small box: (0,0)-(80,80) area = 6400
        # Large box: (0,0)-(100,100) area = 10000
        # Intersection: (0,0)-(80,80) = 6400
        # Union: 6400 + 10000 - 6400 = 10000
        # IoU: 6400/10000 = 0.64 >= 0.5 → NMS fires
        small_box = _det(confidence=0.8, bbox=(0, 0, 80, 80))  # area 6400
        large_box = _det(confidence=0.8, bbox=(0, 0, 100, 100))  # area 10000
        detections = [small_box, large_box]
        results = scorer.filter(detections)
        assert len(results) == 1
        # Larger area wins the tie
        assert results[0].bbox == {"x1": 0, "y1": 0, "x2": 100, "y2": 100}

    def test_nms_iou_below_threshold_both_kept(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        # Slight overlap but IoU < 0.5
        detections = [
            _det(confidence=0.9, bbox=(0, 0, 100, 100)),
            _det(confidence=0.8, bbox=(80, 80, 200, 200)),
        ]
        results = scorer.filter(detections)
        assert len(results) == 2

    def test_nms_iou_exactly_at_threshold_suppresses(self) -> None:
        """IoU >= 0.5 triggers suppression."""
        scorer = ConfidenceScorer(threshold=0.3)
        # Create two boxes with exactly 0.5 IoU
        # Box A: (0,0)-(100,100) area=10000
        # Box B overlaps so that IoU = intersection / union = 0.5
        # If B = (0,0)-(100,200), intersection = 10000, union = 10000 + 20000 - 10000 = 20000, IoU = 0.5
        detections = [
            _det(confidence=0.9, bbox=(0, 0, 100, 100)),
            _det(confidence=0.7, bbox=(0, 0, 100, 200)),
        ]
        results = scorer.filter(detections)
        assert len(results) == 1
        assert results[0].confidence == 0.9


# --- Ordering Tests ---


class TestResultOrdering:
    """Tests for result ordering."""

    def test_sorted_descending_by_confidence(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [
            _det(confidence=0.5, bbox=(0, 0, 10, 10)),
            _det(confidence=0.9, bbox=(200, 200, 300, 300)),
            _det(confidence=0.7, bbox=(400, 400, 500, 500)),
        ]
        results = scorer.filter(detections)
        confidences = [r.confidence for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_ties_broken_by_ascending_class_id(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [
            _det(label="cell phone", confidence=0.8, bbox=(200, 200, 300, 300), class_id=67),
            _det(label="person", confidence=0.8, bbox=(0, 0, 10, 10), class_id=0),
            _det(label="book", confidence=0.8, bbox=(400, 400, 500, 500), class_id=73),
        ]
        results = scorer.filter(detections)
        class_ids = [r.class_id for r in results]
        assert class_ids == [0, 67, 73]


# --- DetectionResult Format Tests ---


class TestDetectionResultFormat:
    """Tests for DetectionResult output structure."""

    def test_bbox_is_dict_with_correct_keys(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [_det(bbox=(10, 20, 30, 40))]
        results = scorer.filter(detections)
        assert results[0].bbox == {"x1": 10, "y1": 20, "x2": 30, "y2": 40}

    def test_label_and_class_id_preserved(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [_det(label="person", class_id=0, confidence=0.9)]
        results = scorer.filter(detections)
        assert results[0].label == "person"
        assert results[0].class_id == 0

    def test_confidence_preserved(self) -> None:
        scorer = ConfidenceScorer(threshold=0.3)
        detections = [_det(confidence=0.8765)]
        results = scorer.filter(detections)
        assert results[0].confidence == 0.8765


# --- compute_iou Tests ---


class TestComputeIou:
    """Tests for the compute_iou static method."""

    def test_identical_boxes_iou_is_one(self) -> None:
        box = (0, 0, 100, 100)
        assert ConfidenceScorer.compute_iou(box, box) == 1.0

    def test_non_overlapping_boxes_iou_is_zero(self) -> None:
        box_a = (0, 0, 50, 50)
        box_b = (100, 100, 200, 200)
        assert ConfidenceScorer.compute_iou(box_a, box_b) == 0.0

    def test_partial_overlap(self) -> None:
        # Box A: (0,0)-(100,100) area=10000
        # Box B: (50,50)-(150,150) area=10000
        # Intersection: (50,50)-(100,100) = 50*50 = 2500
        # Union: 10000 + 10000 - 2500 = 17500
        # IoU: 2500 / 17500 ≈ 0.1429
        iou = ConfidenceScorer.compute_iou((0, 0, 100, 100), (50, 50, 150, 150))
        assert abs(iou - 2500 / 17500) < 1e-6

    def test_one_box_inside_another(self) -> None:
        # Inner: (25,25)-(75,75) area=2500
        # Outer: (0,0)-(100,100) area=10000
        # Intersection: 2500
        # Union: 10000 + 2500 - 2500 = 10000
        # IoU: 2500/10000 = 0.25
        iou = ConfidenceScorer.compute_iou((0, 0, 100, 100), (25, 25, 75, 75))
        assert abs(iou - 0.25) < 1e-6

    def test_zero_area_boxes_returns_zero(self) -> None:
        # Both boxes have zero area (line)
        assert ConfidenceScorer.compute_iou((0, 0, 0, 0), (0, 0, 0, 0)) == 0.0

    def test_touching_boxes_no_overlap(self) -> None:
        # Adjacent boxes sharing an edge
        box_a = (0, 0, 50, 50)
        box_b = (50, 0, 100, 50)
        assert ConfidenceScorer.compute_iou(box_a, box_b) == 0.0
