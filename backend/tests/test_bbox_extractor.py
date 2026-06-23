"""Unit tests for BoundingBoxExtractor."""

from __future__ import annotations

import math

import pytest

from backend.core.bbox_extractor import BoundingBoxExtractor
from backend.core.pipeline_types import Detection, RawDetection


class TestBoundingBoxExtractor:
    """Tests for BoundingBoxExtractor.extract()."""

    def test_basic_extraction(self) -> None:
        """Normal detection is correctly extracted."""
        raw = RawDetection(
            class_id=67,
            label="cell phone",
            confidence=0.85,
            bbox_raw=(100.7, 200.3, 300.9, 400.1),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 1
        det = results[0]
        assert det.label == "cell phone"
        assert det.confidence == 0.85
        assert det.bbox == (100, 200, 300, 400)
        assert det.class_id == 67

    def test_truncation_toward_zero(self) -> None:
        """Float coords are truncated toward zero (not rounded)."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(10.9, 20.9, 30.1, 40.1),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].bbox == (10, 20, 30, 40)

    def test_negative_coords_truncation(self) -> None:
        """Negative float coords truncate toward zero (toward positive)."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(-5.7, -3.2, 100.0, 200.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        # int(-5.7) = -5, int(-3.2) = -3, then clamped to 0
        assert results[0].bbox[0] == 0
        assert results[0].bbox[1] == 0

    def test_swap_inverted_x_coords(self) -> None:
        """Swaps x1/x2 when x1 >= x2."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(300.0, 100.0, 100.0, 400.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].bbox[0] < results[0].bbox[2]  # x1 < x2

    def test_swap_inverted_y_coords(self) -> None:
        """Swaps y1/y2 when y1 >= y2."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(100.0, 400.0, 300.0, 100.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].bbox[1] < results[0].bbox[3]  # y1 < y2

    def test_clamp_to_frame_boundaries(self) -> None:
        """Coordinates are clamped to [0, frame_dim-1]."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(-10.0, -20.0, 700.0, 500.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        x1, y1, x2, y2 = results[0].bbox
        assert x1 == 0
        assert y1 == 0
        assert x2 == 639  # frame_width - 1
        assert y2 == 479  # frame_height - 1

    def test_discard_nan_coords(self) -> None:
        """Detections with NaN coordinates are discarded."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(float("nan"), 100.0, 300.0, 400.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 0

    def test_discard_inf_coords(self) -> None:
        """Detections with infinity coordinates are discarded."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(100.0, float("inf"), 300.0, 400.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 0

    def test_discard_negative_inf_coords(self) -> None:
        """Detections with -infinity coordinates are discarded."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(100.0, 200.0, float("-inf"), 400.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 0

    def test_discard_zero_area_after_clamp(self) -> None:
        """Zero-area boxes after clamping are discarded."""
        # Both x coords clamp to the same value (frame_width - 1)
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(700.0, 100.0, 800.0, 200.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 0

    def test_discard_zero_area_equal_coords(self) -> None:
        """Boxes where x1 == x2 or y1 == y2 after processing are discarded."""
        # After truncation: x1=100, x2=100 → swap doesn't help (equal) → zero area
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(100.0, 200.0, 100.9, 400.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 0

    def test_class_label_mapping_person(self) -> None:
        """Class 0 maps to 'person'."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(10.0, 20.0, 100.0, 200.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].label == "person"

    def test_class_label_mapping_cell_phone(self) -> None:
        """Class 67 maps to 'cell phone'."""
        raw = RawDetection(
            class_id=67,
            label="cell phone",
            confidence=0.8,
            bbox_raw=(10.0, 20.0, 100.0, 200.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].label == "cell phone"

    def test_class_label_mapping_book(self) -> None:
        """Class 73 maps to 'book'."""
        raw = RawDetection(
            class_id=73,
            label="book",
            confidence=0.7,
            bbox_raw=(10.0, 20.0, 100.0, 200.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert results[0].label == "book"

    def test_empty_input_returns_empty(self) -> None:
        """Empty raw detections list returns empty results."""
        results = BoundingBoxExtractor.extract([], frame_width=640, frame_height=480)

        assert results == []

    def test_multiple_detections(self) -> None:
        """Multiple valid detections are all extracted."""
        raws = [
            RawDetection(class_id=0, label="person", confidence=0.9, bbox_raw=(10.0, 20.0, 100.0, 200.0)),
            RawDetection(class_id=67, label="cell phone", confidence=0.8, bbox_raw=(50.0, 60.0, 150.0, 250.0)),
            RawDetection(class_id=73, label="book", confidence=0.7, bbox_raw=(200.0, 300.0, 400.0, 450.0)),
        ]
        results = BoundingBoxExtractor.extract(raws, frame_width=640, frame_height=480)

        assert len(results) == 3
        assert results[0].label == "person"
        assert results[1].label == "cell phone"
        assert results[2].label == "book"

    def test_mixed_valid_and_invalid(self) -> None:
        """Valid detections are kept while invalid ones are discarded."""
        raws = [
            RawDetection(class_id=0, label="person", confidence=0.9, bbox_raw=(10.0, 20.0, 100.0, 200.0)),
            RawDetection(class_id=67, label="cell phone", confidence=0.8, bbox_raw=(float("nan"), 60.0, 150.0, 250.0)),
            RawDetection(class_id=73, label="book", confidence=0.7, bbox_raw=(200.0, 300.0, 400.0, 450.0)),
        ]
        results = BoundingBoxExtractor.extract(raws, frame_width=640, frame_height=480)

        assert len(results) == 2
        assert results[0].label == "person"
        assert results[1].label == "book"

    def test_boundary_coords_exactly_at_frame_edge(self) -> None:
        """Coords exactly at frame boundaries are valid."""
        raw = RawDetection(
            class_id=0,
            label="person",
            confidence=0.9,
            bbox_raw=(0.0, 0.0, 639.0, 479.0),
        )
        results = BoundingBoxExtractor.extract([raw], frame_width=640, frame_height=480)

        assert len(results) == 1
        assert results[0].bbox == (0, 0, 639, 479)
