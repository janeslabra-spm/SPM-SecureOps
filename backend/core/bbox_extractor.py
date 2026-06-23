"""Bounding box extraction and normalization for the AI Detection Pipeline.

Converts raw float coordinates from the inference engine into validated,
integer pixel coordinates clamped to frame boundaries.
"""

from __future__ import annotations

import math

from backend.core.pipeline_types import Detection, RawDetection

# Class ID to human-readable label mapping
CLASS_LABELS: dict[int, str] = {
    0: "person",
    67: "cell phone",
    73: "book",
}


class BoundingBoxExtractor:
    """Normalizes and validates raw detection bounding boxes.

    Converts raw float coordinates to integer pixels, swaps inverted
    coordinates, clamps to frame boundaries, and discards invalid
    detections (non-finite values or zero-area boxes).
    """

    @staticmethod
    def extract(
        raw_detections: list[RawDetection],
        frame_width: int,
        frame_height: int,
    ) -> list[Detection]:
        """Extract normalized detections from raw inference output.

        Algorithm:
            1. Discard detections with non-finite coordinate values.
            2. Truncate float coords toward zero using int().
            3. Swap x1/x2 if x1 >= x2; swap y1/y2 if y1 >= y2.
            4. Clamp coordinates to frame boundaries.
            5. Discard zero-area bounding boxes after clamping.
            6. Map class_id to label and produce Detection objects.

        Args:
            raw_detections: List of raw detections from the inference engine.
            frame_width: Width of the source frame in pixels.
            frame_height: Height of the source frame in pixels.

        Returns:
            List of valid Detection objects with normalized coordinates.
        """
        results: list[Detection] = []

        for raw in raw_detections:
            x1_raw, y1_raw, x2_raw, y2_raw = raw.bbox_raw

            # Step 1: Discard non-finite coordinates
            if (
                not math.isfinite(x1_raw)
                or not math.isfinite(y1_raw)
                or not math.isfinite(x2_raw)
                or not math.isfinite(y2_raw)
            ):
                continue

            # Step 2: Truncate float coords toward zero
            x1 = int(x1_raw)
            y1 = int(y1_raw)
            x2 = int(x2_raw)
            y2 = int(y2_raw)

            # Step 3: Swap if coordinates are inverted
            if x1 >= x2:
                x1, x2 = x2, x1
            if y1 >= y2:
                y1, y2 = y2, y1

            # Step 4: Clamp to frame boundaries
            x1 = max(0, min(x1, frame_width - 1))
            x2 = max(0, min(x2, frame_width - 1))
            y1 = max(0, min(y1, frame_height - 1))
            y2 = max(0, min(y2, frame_height - 1))

            # Step 5: Discard zero-area bounding boxes
            if x1 >= x2 or y1 >= y2:
                continue

            # Step 6: Map class_id to label
            label = CLASS_LABELS.get(raw.class_id, raw.label)

            results.append(
                Detection(
                    label=label,
                    confidence=raw.confidence,
                    bbox=(x1, y1, x2, y2),
                    class_id=raw.class_id,
                )
            )

        return results
