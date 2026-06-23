"""Confidence scoring, threshold filtering, and Non-Maximum Suppression.

Filters detections by confidence threshold, applies per-class NMS to
remove overlapping duplicates, and produces JSON-serializable results
sorted by confidence descending.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from backend.core.pipeline_types import Detection, DetectionResult

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Filters detections by confidence and applies Non-Maximum Suppression.

    Attributes:
        DEFAULT_THRESHOLD: The default confidence threshold (0.4).
        NMS_IOU_THRESHOLD: The IoU threshold for NMS suppression (0.5).
    """

    DEFAULT_THRESHOLD: ClassVar[float] = 0.4
    NMS_IOU_THRESHOLD: ClassVar[float] = 0.5

    def __init__(self, threshold: float = 0.4) -> None:
        """Initialize the scorer with a confidence threshold.

        Args:
            threshold: Confidence threshold in [0.0, 1.0]. If invalid,
                logs an error and uses the default threshold of 0.4.
        """
        if not (0.0 <= threshold <= 1.0):
            logger.error(
                "Invalid confidence threshold %.4f; must be in [0.0, 1.0]. "
                "Using default threshold %.1f.",
                threshold,
                self.DEFAULT_THRESHOLD,
            )
            self._threshold = self.DEFAULT_THRESHOLD
        else:
            self._threshold = threshold

    @property
    def threshold(self) -> float:
        """Current confidence threshold."""
        return self._threshold

    def set_threshold(self, threshold: float) -> None:
        """Update the confidence threshold.

        Args:
            threshold: New threshold value. Must be in [0.0, 1.0].
                If invalid, logs an error and keeps current threshold
                at the default value of 0.4.
        """
        if not (0.0 <= threshold <= 1.0):
            logger.error(
                "Invalid confidence threshold %.4f; must be in [0.0, 1.0]. "
                "Keeping default threshold %.1f.",
                threshold,
                self.DEFAULT_THRESHOLD,
            )
            self._threshold = self.DEFAULT_THRESHOLD
        else:
            self._threshold = threshold

    def filter(self, detections: list[Detection]) -> list[DetectionResult]:
        """Filter detections by threshold and apply per-class NMS.

        Algorithm:
            1. Keep only detections with confidence >= self._threshold.
            2. Group by class_id.
            3. For each class, apply greedy NMS:
               - Sort by confidence descending (ties: larger area first).
               - For each detection, suppress if IoU >= 0.5 with any
                 already-kept detection.
            4. Collect all kept detections from all classes.
            5. Sort descending by confidence; ties broken by ascending class_id.
            6. Convert each Detection to DetectionResult (bbox tuple → dict).

        Args:
            detections: List of Detection objects from the BoundingBoxExtractor.

        Returns:
            Sorted list of DetectionResult objects ready for JSON serialization.
        """
        # Step 1: Threshold filtering
        above_threshold = [
            d for d in detections if d.confidence >= self._threshold
        ]

        # Step 2: Group by class_id
        groups: dict[int, list[Detection]] = {}
        for det in above_threshold:
            groups.setdefault(det.class_id, []).append(det)

        # Step 3: Per-class NMS
        kept: list[Detection] = []
        for class_id, class_detections in groups.items():
            # Sort by confidence descending; ties broken by larger area first
            class_detections.sort(
                key=lambda d: (
                    -d.confidence,
                    -(self._bbox_area(d.bbox)),
                ),
            )
            kept_for_class: list[Detection] = []
            for det in class_detections:
                suppressed = False
                for kept_det in kept_for_class:
                    iou = self.compute_iou(det.bbox, kept_det.bbox)
                    if iou >= self.NMS_IOU_THRESHOLD:
                        suppressed = True
                        break
                if not suppressed:
                    kept_for_class.append(det)
            kept.extend(kept_for_class)

        # Step 5: Sort results descending by confidence, ties by ascending class_id
        kept.sort(key=lambda d: (-d.confidence, d.class_id))

        # Step 6: Convert to DetectionResult with bbox as dict
        results: list[DetectionResult] = []
        for det in kept:
            x1, y1, x2, y2 = det.bbox
            results.append(
                DetectionResult(
                    label=det.label,
                    confidence=det.confidence,
                    bbox={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    class_id=det.class_id,
                )
            )

        return results

    @staticmethod
    def compute_iou(
        box_a: tuple[int, int, int, int],
        box_b: tuple[int, int, int, int],
    ) -> float:
        """Compute Intersection over Union (IoU) for two bounding boxes.

        Args:
            box_a: First bounding box as (x1, y1, x2, y2).
            box_b: Second bounding box as (x1, y1, x2, y2).

        Returns:
            IoU value in [0.0, 1.0]. Returns 0.0 if union area is zero.
        """
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        # Intersection coordinates
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        # Intersection area (zero if no overlap)
        inter_width = max(0, inter_x2 - inter_x1)
        inter_height = max(0, inter_y2 - inter_y1)
        intersection = inter_width * inter_height

        # Union area
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - intersection

        if union == 0:
            return 0.0

        return intersection / union

    @staticmethod
    def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
        """Calculate the area of a bounding box.

        Args:
            bbox: Bounding box as (x1, y1, x2, y2).

        Returns:
            Area in pixels squared.
        """
        x1, y1, x2, y2 = bbox
        return (x2 - x1) * (y2 - y1)
