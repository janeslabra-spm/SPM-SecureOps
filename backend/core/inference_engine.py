"""YOLOv8n inference wrapper for the AI Detection Pipeline.

Provides a decoupled inference engine that loads the YOLOv8n model,
filters predictions to target classes, and returns structured raw
detections without crashing on errors.
"""

from __future__ import annotations

import logging
from typing import ClassVar

import numpy as np
from ultralytics import YOLO

from backend.core.pipeline_types import RawDetection

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Wraps YOLOv8n model inference with graceful error handling.

    Loads the model at initialization and provides a single `infer()` method
    that accepts a frame and returns raw detections filtered to target classes.
    """

    TARGET_CLASSES: ClassVar[dict[int, str]] = {
        0: "person",
        67: "cell phone",
        73: "book",
    }

    def __init__(self, model_path: str = "yolov8n.pt", device: str = "auto") -> None:
        """Load the YOLOv8n model from the given path.

        Args:
            model_path: Path to the YOLO model weights file.
            device: Inference device — "auto", "cpu", "cuda", or "mps".
                    When "auto", device selection is deferred to Ultralytics.

        Raises:
            RuntimeError: If the model file is missing or cannot be loaded.
        """
        self._device = device

        try:
            self._model = YOLO(model_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load model from '{model_path}': {exc}"
            ) from exc

    def infer(
        self,
        frame: np.ndarray,
        image_size: int = 640,
        confidence_threshold: float = 0.4,
    ) -> list[RawDetection]:
        """Run YOLOv8n inference on a single frame.

        Args:
            frame: Input image as a NumPy array (BGR, uint8).
            image_size: Longest-edge resize for the model input.
            confidence_threshold: Minimum confidence for detections.

        Returns:
            List of RawDetection objects for the target classes.
            Returns an empty list if inference fails for any reason.
        """
        try:
            predict_kwargs: dict = {
                "conf": confidence_threshold,
                "classes": list(self.TARGET_CLASSES.keys()),
                "imgsz": image_size,
                "verbose": False,
            }

            # When device is "auto", omit device arg so Ultralytics picks the best.
            if self._device != "auto":
                predict_kwargs["device"] = self._device

            results = self._model.predict(frame, **predict_kwargs)

            detections: list[RawDetection] = []

            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None:
                    for box in boxes:
                        class_id = int(box.cls[0].item())
                        confidence = float(box.conf[0].item())
                        xyxy = box.xyxy[0].tolist()
                        bbox_raw = (
                            float(xyxy[0]),
                            float(xyxy[1]),
                            float(xyxy[2]),
                            float(xyxy[3]),
                        )
                        label = self.TARGET_CLASSES.get(class_id, f"class_{class_id}")

                        detections.append(
                            RawDetection(
                                class_id=class_id,
                                label=label,
                                confidence=confidence,
                                bbox_raw=bbox_raw,
                            )
                        )

            return detections

        except Exception as exc:
            logger.error("Inference failed: %s", exc, exc_info=True)
            return []
