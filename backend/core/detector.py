from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]
    class_id: int


class YoloDetector:
    """Small wrapper around Ultralytics YOLO for person/cell phone/document detection."""

    TARGET_LABELS = {"person", "cell phone", "book"}

    def __init__(self, model_path: str = "yolov8n.pt", device: str | None = None) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is not installed. Run `pip install -r requirements.txt` first."
            ) from exc

        self.model = YOLO(model_path)
        self.device = None if device in (None, "", "auto") else device
        names = getattr(self.model, "names", {}) or {}
        self.target_class_ids = [
            int(class_id)
            for class_id, label in dict(names).items()
            if str(label) in self.TARGET_LABELS
        ] or None

    def detect(
        self,
        frame,
        confidence_threshold: float = 0.4,
        image_size: int = 640,
    ) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            conf=confidence_threshold,
            imgsz=image_size,
            classes=self.target_class_ids,
            verbose=False,
            device=self.device,
        )
        if not results:
            return []

        names = results[0].names
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return []

        detections: list[Detection] = []
        for box in boxes:
            class_id = int(box.cls[0])
            label = str(names.get(class_id, class_id))
            if label not in self.TARGET_LABELS:
                continue

            x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    label=label,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                    class_id=class_id,
                )
            )

        return detections


def detection_labels(detections: Iterable[Detection]) -> set[str]:
    """Return the set of unique labels from a collection of detections."""
    return {detection.label for detection in detections}
