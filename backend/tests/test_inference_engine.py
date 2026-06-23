"""Unit tests for the InferenceEngine class."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# Provide a mock ultralytics module so tests run without the real package.
_mock_ultralytics = MagicMock()
sys.modules.setdefault("ultralytics", _mock_ultralytics)

from backend.core.inference_engine import InferenceEngine  # noqa: E402
from backend.core.pipeline_types import RawDetection  # noqa: E402


class TestInferenceEngineInit:
    """Tests for InferenceEngine initialization."""

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_successful_model_load(self, mock_yolo_cls: MagicMock) -> None:
        """Model loads successfully with a valid path."""
        mock_yolo_cls.return_value = MagicMock()

        engine = InferenceEngine(model_path="yolov8n.pt", device="cpu")

        mock_yolo_cls.assert_called_once_with("yolov8n.pt")
        assert engine._device == "cpu"

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_invalid_model_path_raises_runtime_error(
        self, mock_yolo_cls: MagicMock
    ) -> None:
        """RuntimeError raised when model path is invalid."""
        mock_yolo_cls.side_effect = FileNotFoundError("No such file")

        with pytest.raises(RuntimeError, match="Failed to load model from"):
            InferenceEngine(model_path="/invalid/path.pt")

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_error_message_contains_file_path(
        self, mock_yolo_cls: MagicMock
    ) -> None:
        """RuntimeError message specifies the file path that failed."""
        mock_yolo_cls.side_effect = Exception("corrupt model")

        with pytest.raises(RuntimeError, match="/bad/model.pt"):
            InferenceEngine(model_path="/bad/model.pt")

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_device_auto_stored(self, mock_yolo_cls: MagicMock) -> None:
        """Device 'auto' is stored correctly."""
        mock_yolo_cls.return_value = MagicMock()
        engine = InferenceEngine(device="auto")
        assert engine._device == "auto"

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_device_cuda_stored(self, mock_yolo_cls: MagicMock) -> None:
        """Device 'cuda' is stored correctly."""
        mock_yolo_cls.return_value = MagicMock()
        engine = InferenceEngine(device="cuda")
        assert engine._device == "cuda"

    @patch("backend.core.inference_engine.YOLO", autospec=False)
    def test_device_mps_stored(self, mock_yolo_cls: MagicMock) -> None:
        """Device 'mps' is stored correctly."""
        mock_yolo_cls.return_value = MagicMock()
        engine = InferenceEngine(device="mps")
        assert engine._device == "mps"


class TestInferenceEngineInfer:
    """Tests for InferenceEngine.infer() method."""

    def _make_engine(self, mock_model: MagicMock, device: str = "cpu") -> InferenceEngine:
        """Helper to create an engine with a mocked model."""
        with patch("backend.core.inference_engine.YOLO", return_value=mock_model):
            return InferenceEngine(model_path="yolov8n.pt", device=device)

    def _make_box(self, class_id: int, confidence: float, xyxy: list[float]) -> MagicMock:
        """Helper to create a mocked YOLO box object."""
        box = MagicMock()
        cls_tensor = MagicMock()
        cls_tensor.item.return_value = class_id
        box.cls = [cls_tensor]

        conf_tensor = MagicMock()
        conf_tensor.item.return_value = confidence
        box.conf = [conf_tensor]

        xyxy_tensor = MagicMock()
        xyxy_tensor.tolist.return_value = xyxy
        box.xyxy = [xyxy_tensor]
        return box

    def _make_result(self, boxes: list) -> MagicMock:
        """Helper to create a mocked YOLO result object."""
        result_obj = MagicMock()
        # Use a MagicMock for boxes that supports iteration
        mock_boxes = MagicMock()
        mock_boxes.__iter__ = MagicMock(return_value=iter(boxes))
        mock_boxes.__len__ = MagicMock(return_value=len(boxes))
        mock_boxes.__bool__ = MagicMock(return_value=len(boxes) > 0)
        result_obj.boxes = mock_boxes
        return result_obj

    def test_successful_inference_returns_detections(self) -> None:
        """Successful inference returns list of RawDetection objects."""
        mock_model = MagicMock()
        box = self._make_box(class_id=67, confidence=0.85, xyxy=[100.5, 200.3, 300.7, 400.1])

        result_obj = self._make_result([box])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = engine.infer(frame)

        assert len(detections) == 1
        assert detections[0].class_id == 67
        assert detections[0].label == "cell phone"
        assert detections[0].confidence == 0.85
        assert detections[0].bbox_raw == (100.5, 200.3, 300.7, 400.1)

    def test_inference_returns_raw_detection_type(self) -> None:
        """Each detection is a RawDetection instance."""
        mock_model = MagicMock()
        box = self._make_box(class_id=0, confidence=0.9, xyxy=[10.0, 20.0, 300.0, 400.0])

        result_obj = self._make_result([box])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = engine.infer(frame)

        assert isinstance(detections[0], RawDetection)

    def test_inference_failure_returns_empty_list(self) -> None:
        """Inference exception returns empty list without crashing."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("CUDA out of memory")

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = engine.infer(frame)

        assert detections == []

    def test_no_detections_returns_empty_list(self) -> None:
        """Frame with no detected objects returns empty list."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = engine.infer(frame)

        assert detections == []

    def test_auto_device_omits_device_param(self) -> None:
        """When device is 'auto', device kwarg is not passed to predict."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model, device="auto")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        engine.infer(frame)

        call_kwargs = mock_model.predict.call_args[1]
        assert "device" not in call_kwargs

    def test_explicit_device_passed_to_predict(self) -> None:
        """When device is explicit, it's passed to predict."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model, device="cpu")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        engine.infer(frame)

        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs["device"] == "cpu"

    def test_target_classes_filtered(self) -> None:
        """Predict is called with target class IDs [0, 67, 73]."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        engine.infer(frame)

        call_kwargs = mock_model.predict.call_args[1]
        assert sorted(call_kwargs["classes"]) == [0, 67, 73]

    def test_confidence_threshold_passed(self) -> None:
        """Custom confidence threshold is passed to predict."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        engine.infer(frame, confidence_threshold=0.7)

        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs["conf"] == 0.7

    def test_image_size_passed(self) -> None:
        """Custom image_size is passed to predict."""
        mock_model = MagicMock()
        result_obj = self._make_result([])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        engine.infer(frame, image_size=320)

        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs["imgsz"] == 320

    def test_multiple_detections(self) -> None:
        """Multiple boxes produce multiple RawDetection objects."""
        mock_model = MagicMock()
        box_person = self._make_box(class_id=0, confidence=0.92, xyxy=[50.0, 60.0, 200.0, 400.0])
        box_phone = self._make_box(class_id=67, confidence=0.78, xyxy=[100.0, 150.0, 160.0, 200.0])
        box_book = self._make_box(class_id=73, confidence=0.65, xyxy=[300.0, 100.0, 450.0, 250.0])

        result_obj = self._make_result([box_person, box_phone, box_book])
        mock_model.predict.return_value = [result_obj]

        engine = self._make_engine(mock_model)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = engine.infer(frame)

        assert len(detections) == 3
        assert detections[0].label == "person"
        assert detections[1].label == "cell phone"
        assert detections[2].label == "book"

    def test_label_mapping_for_all_target_classes(self) -> None:
        """All target class IDs map to correct labels."""
        expected = {0: "person", 67: "cell phone", 73: "book"}
        assert InferenceEngine.TARGET_CLASSES == expected
