from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import cv2

from src.database import add_incident
from src.detector import Detection, YoloDetector
from src.rules import IncidentCandidate, classify_incidents, table_zone_from_percent


_worker_lock = threading.Lock()
_worker: "MonitoringWorker | None" = None
_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_server_port: int | None = None


class MonitoringWorker:
    def __init__(self, config: dict[str, Any], db_path: Path, screenshot_dir: Path) -> None:
        self.config = dict(config)
        self.db_path = db_path
        self.screenshot_dir = screenshot_dir
        self.stop_event = threading.Event()
        self.frame_condition = threading.Condition()
        self.latest_jpeg: bytes | None = None
        self.frame_id = 0
        self.active_since: dict[str, float] = {}
        self.last_logged: dict[str, float] = {}
        self.thread = threading.Thread(target=self._run, name="monitoring-worker", daemon=True)
        self.status: dict[str, Any] = {
            "message": "Starting monitoring...",
            "people": 0,
            "phones": 0,
            "active_rule_matches": 0,
            "logged_this_frame": 0,
            "inference_ms": 0.0,
            "fps": 0.0,
            "last_incident_id": None,
            "last_screenshot_path": "",
        }

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        with self.frame_condition:
            self.frame_condition.notify_all()
        self.thread.join(timeout=2)

    def snapshot(self) -> bytes | None:
        with self.frame_condition:
            return self.latest_jpeg

    def status_snapshot(self) -> dict[str, Any]:
        with self.frame_condition:
            return dict(self.status)

    def wait_for_frame(self, last_frame_id: int, timeout: float = 2.0) -> tuple[int, bytes | None]:
        with self.frame_condition:
            self.frame_condition.wait_for(
                lambda: self.frame_id != last_frame_id or self.stop_event.is_set(),
                timeout=timeout,
            )
            return self.frame_id, self.latest_jpeg

    def _run(self) -> None:
        capture = self._open_capture()
        if capture is None or not capture.isOpened():
            self._set_status(message=f"Could not open {self.config['source_mode'].lower()} source.")
            return

        try:
            detector = YoloDetector(
                model_path=self.config["model_path"],
                device=self.config["device"],
            )
        except Exception as exc:
            self._set_status(message=f"YOLO model failed to load: {exc}")
            capture.release()
            return

        target_interval = 1 / max(int(self.config["ui_fps"]), 1)
        last_loop_started = time.perf_counter()

        try:
            while not self.stop_event.is_set():
                loop_started = time.perf_counter()
                ok, frame = capture.read()
                if not ok and self.config["source_mode"] == "Sample video" and self.config["loop_video"]:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = capture.read()

                if not ok or frame is None:
                    self._set_status(message="No frame was available from the selected source.")
                    time.sleep(0.2)
                    continue

                inference_started = time.perf_counter()
                try:
                    detections = detector.detect(
                        frame,
                        confidence_threshold=self.config["confidence_threshold"],
                        image_size=self.config["image_size"],
                    )
                except Exception as exc:
                    self._set_status(message=f"YOLO inference failed: {exc}")
                    break
                inference_ms = (time.perf_counter() - inference_started) * 1000

                height, width = frame.shape[:2]
                table_zone = table_zone_from_percent(width, height, *self.config["table_percents"])
                candidates = classify_incidents(detections, table_zone, self.config["proximity_pixels"])
                annotated = _draw_overlays(frame, detections, candidates, table_zone)
                confirmed = self._update_incident_timers(candidates, annotated)

                ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok:
                    elapsed = max(time.perf_counter() - last_loop_started, 0.001)
                    last_loop_started = time.perf_counter()
                    self._publish_frame(
                        encoded.tobytes(),
                        {
                            "people": sum(1 for detection in detections if detection.label == "person"),
                            "phones": sum(1 for detection in detections if detection.label == "cell phone"),
                            "active_rule_matches": len(candidates),
                            "logged_this_frame": len(confirmed),
                            "inference_ms": inference_ms,
                            "fps": 1 / elapsed,
                        },
                    )

                sleep_for = target_interval - (time.perf_counter() - loop_started)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            capture.release()

    def _open_capture(self):
        if self.config["source_mode"] == "Webcam":
            capture = cv2.VideoCapture(self.config["camera_index"], cv2.CAP_AVFOUNDATION)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["camera_width"])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["camera_height"])
        else:
            video_path = Path(self.config["sample_video_path"]).expanduser()
            capture = cv2.VideoCapture(str(video_path))

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _update_incident_timers(self, candidates: list[IncidentCandidate], frame) -> list[int]:
        now = time.time()
        active_types = {candidate.incident_type for candidate in candidates}

        for incident_type in list(self.active_since.keys()):
            if incident_type not in active_types:
                self.active_since.pop(incident_type, None)

        confirmed_ids: list[int] = []
        for incident_type in active_types:
            self.active_since.setdefault(incident_type, now)
            elapsed = now - self.active_since[incident_type]
            last_logged = self.last_logged.get(incident_type, 0)
            if elapsed < self.config["duration_threshold"] or now - last_logged < self.config["cooldown_seconds"]:
                continue

            strongest = max(
                (candidate for candidate in candidates if candidate.incident_type == incident_type),
                key=lambda candidate: candidate.confidence,
            )
            incident_id = self._save_incident(strongest, frame)
            self.last_logged[incident_type] = now
            self.active_since[incident_type] = now
            self._set_status(
                message=(
                    f"Incident #{incident_id} logged: {incident_type} "
                    f"({strongest.confidence:.2f} confidence)."
                ),
                last_incident_id=incident_id,
            )
            confirmed_ids.append(incident_id)

        return confirmed_ids

    def _save_incident(self, candidate: IncidentCandidate, frame) -> int:
        timestamp = datetime.now().replace(microsecond=0)
        timestamp_for_filename = datetime.now()
        filename = f"incident_{timestamp_for_filename:%Y%m%d_%H%M%S_%f}_{candidate.incident_type}.jpg"
        screenshot_path = self.screenshot_dir / filename
        cv2.imwrite(str(screenshot_path), frame)
        incident_id = add_incident(
            db_path=self.db_path,
            timestamp=timestamp.isoformat(sep=" "),
            incident_type=candidate.incident_type,
            confidence=candidate.confidence,
            camera_name=self.config["camera_name"],
            location=self.config["location"],
            screenshot_path=str(screenshot_path),
        )
        self._set_status(last_screenshot_path=str(screenshot_path))
        return incident_id

    def _publish_frame(self, jpeg: bytes, status_update: dict[str, Any]) -> None:
        with self.frame_condition:
            self.latest_jpeg = jpeg
            self.frame_id += 1
            self.status.update(status_update)
            self.frame_condition.notify_all()

    def _set_status(self, **updates: Any) -> None:
        with self.frame_condition:
            self.status.update(updates)
            self.frame_condition.notify_all()


class _StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/viewer.html"):
            self._serve_viewer()
        elif self.path.startswith("/video.mjpg"):
            self._serve_mjpeg()
        elif self.path.startswith("/status.json"):
            self._serve_status()
        elif self.path.startswith("/snapshot.jpg"):
            self._serve_snapshot()
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _serve_viewer(self) -> None:
        body = b"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {
      margin: 0;
      padding: 0;
      background: #0e1117;
      overflow: hidden;
    }
    .video-shell {
      width: 100vw;
      min-height: 520px;
      background: #0e1117;
      display: flex;
      align-items: flex-start;
      justify-content: center;
    }
    img {
      width: 100%;
      height: auto;
      display: block;
      border-radius: 6px;
      background: #0e1117;
    }
  </style>
</head>
<body>
  <div class="video-shell">
    <img src="/video.mjpg" alt="Live monitoring feed">
  </div>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_mjpeg(self) -> None:
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        last_frame_id = -1
        while True:
            worker = get_worker()
            if worker is None or worker.stop_event.is_set():
                break

            last_frame_id, jpeg = worker.wait_for_frame(last_frame_id)
            if jpeg is None:
                continue

            try:
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                break

    def _serve_snapshot(self) -> None:
        worker = get_worker()
        jpeg = worker.snapshot() if worker else None
        if jpeg is None:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(jpeg)))
        self.end_headers()
        self.wfile.write(jpeg)

    def _serve_status(self) -> None:
        worker = get_worker()
        body = json.dumps(worker.status_snapshot() if worker else {"message": "Monitoring is stopped."}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_monitoring_stream(config: dict[str, Any], db_path: Path, screenshot_dir: Path) -> int:
    global _worker
    port = ensure_stream_server()
    with _worker_lock:
        if _worker is not None:
            _worker.stop()
        _worker = MonitoringWorker(config, db_path, screenshot_dir)
        _worker.start()
    return port


def stop_monitoring_stream() -> None:
    global _worker
    with _worker_lock:
        if _worker is not None:
            _worker.stop()
            _worker = None


def get_worker() -> MonitoringWorker | None:
    with _worker_lock:
        return _worker


def get_monitoring_status() -> dict[str, Any]:
    worker = get_worker()
    if worker is None:
        return {"message": "Monitoring is stopped."}
    return worker.status_snapshot()


def ensure_stream_server() -> int:
    global _server, _server_thread, _server_port
    if _server is not None and _server_port is not None:
        return _server_port

    port = _find_free_port(8765, 8799)
    _server = ThreadingHTTPServer(("127.0.0.1", port), _StreamHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, name="mjpeg-server", daemon=True)
    _server_thread.start()
    _server_port = port
    return port


def _find_free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free local port between {start} and {end}.")


def _draw_overlays(
    frame,
    detections: list[Detection],
    candidates: list[IncidentCandidate],
    table_zone: tuple[int, int, int, int],
):
    tx1, ty1, tx2, ty2 = table_zone
    cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), (255, 200, 0), 2)
    cv2.putText(frame, "TABLE ZONE", (tx1, max(ty1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

    candidate_bboxes = {candidate.phone_bbox: candidate.incident_type for candidate in candidates}
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        if detection.label == "person":
            color = (60, 180, 255)
        elif detection.bbox in candidate_bboxes:
            color = (0, 0, 255)
        else:
            color = (0, 220, 80)

        label = f"{detection.label} {detection.confidence:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(y1 - 8, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    for candidate in candidates:
        x1, _, _, y2 = candidate.phone_bbox
        cv2.putText(frame, candidate.incident_type, (x1, y2 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    return frame
