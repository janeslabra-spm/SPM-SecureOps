from __future__ import annotations

import re
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from src.database import add_incident, init_db, load_incidents, update_status
from src.detector import Detection, YoloDetector
from src.mjpeg_stream import get_monitoring_status, start_monitoring_stream, stop_monitoring_stream
from src.rules import (
    PHONE_HELD_OR_NEAR_PERSON,
    PHONE_ON_TABLE,
    IncidentCandidate,
    classify_incidents,
    table_zone_from_percent,
)


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SAMPLE_VIDEO_DIR = BASE_DIR / "sample_videos"
DB_PATH = DATA_DIR / "incidents.db"

STATUS_OPTIONS = ["Pending Review", "Confirmed", "False Alarm"]
INCIDENT_TYPES = [PHONE_ON_TABLE, PHONE_HELD_OR_NEAR_PERSON]
DETECTOR_CACHE_VERSION = 2


def main() -> None:
    st.set_page_config(page_title="Cellphone Monitoring System", layout="wide")
    init_storage()
    init_state()

    st.title("Cellphone Monitoring System")

    config = sidebar_controls()
    monitoring_tab, incidents_tab = st.tabs(["Live Monitoring", "Incident Dashboard"])

    with monitoring_tab:
        render_monitoring(config)

    with incidents_tab:
        render_dashboard()


def init_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    SAMPLE_VIDEO_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "ultralytics").mkdir(exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(DATA_DIR / "ultralytics"))
    init_db(DB_PATH)


def init_state() -> None:
    defaults = {
        "monitoring": False,
        "capture": None,
        "capture_key": None,
        "active_since": {},
        "last_logged": {},
        "last_preview_at": 0.0,
        "last_inference_ms": 0.0,
        "last_detections": [],
        "last_candidates": [],
        "last_confirmed": [],
        "last_annotated_frame": None,
        "stream_port": None,
        "stream_config_key": None,
        "last_message": "No confirmed incident in this session.",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def sidebar_controls() -> dict:
    st.sidebar.header("Monitoring")

    source_mode = st.sidebar.radio("Video source", ["Webcam", "Sample video"])
    camera_index = 0
    sample_video_path = ""
    loop_video = True

    if source_mode == "Webcam":
        camera_index = st.sidebar.number_input("Camera index", min_value=0, max_value=10, value=0)
        camera_width = st.sidebar.selectbox("Camera width", [640, 960, 1280, 1920], index=1)
        camera_height = st.sidebar.selectbox("Camera height", [360, 540, 720, 1080], index=1)
    else:
        camera_width = 0
        camera_height = 0
        uploaded_file = st.sidebar.file_uploader("Sample video upload", type=["mp4", "mov", "m4v", "avi"])
        default_sample = SAMPLE_VIDEO_DIR / "demo.mp4"
        sample_video_path = st.sidebar.text_input("Local sample video path", value=str(default_sample))
        loop_video = st.sidebar.checkbox("Loop sample video", value=True)

        if uploaded_file is not None:
            sample_video_path = save_uploaded_video(uploaded_file)
            st.sidebar.caption(f"Using uploaded file: {Path(sample_video_path).name}")

    model_path = st.sidebar.text_input("YOLO model path", value="yolov8n.pt")
    device = st.sidebar.selectbox("Inference device", ["auto", "cpu", "mps"], index=0)
    ui_fps = st.sidebar.slider("UI frame rate", 1, 6, 2)
    image_size = st.sidebar.selectbox("Inference image size", [320, 480, 640, 960], index=1)
    confidence_threshold = st.sidebar.slider("Confidence threshold", 0.10, 0.95, 0.40, 0.05)
    duration_threshold = st.sidebar.slider("Detection duration threshold (seconds)", 0.5, 10.0, 2.0, 0.5)
    cooldown_seconds = st.sidebar.slider("Incident cooldown (seconds)", 1, 60, 10)
    proximity_pixels = st.sidebar.slider("Phone/person proximity (pixels)", 20, 250, 80, 10)

    st.sidebar.header("Table Zone")
    table_x1 = st.sidebar.slider("table_x1_percent", 0, 100, 20)
    table_y1 = st.sidebar.slider("table_y1_percent", 0, 100, 35)
    table_x2 = st.sidebar.slider("table_x2_percent", 0, 100, 80)
    table_y2 = st.sidebar.slider("table_y2_percent", 0, 100, 75)

    st.sidebar.header("Incident Defaults")
    camera_name = st.sidebar.text_input("Camera name", value="Demo Webcam 1")
    location = st.sidebar.text_input("Location", value="Production Table Demo")

    return {
        "source_mode": source_mode,
        "camera_index": int(camera_index),
        "camera_width": int(camera_width),
        "camera_height": int(camera_height),
        "sample_video_path": sample_video_path,
        "loop_video": loop_video,
        "model_path": model_path,
        "device": device,
        "ui_fps": ui_fps,
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "duration_threshold": duration_threshold,
        "cooldown_seconds": cooldown_seconds,
        "proximity_pixels": proximity_pixels,
        "table_percents": (table_x1, table_y1, table_x2, table_y2),
        "camera_name": camera_name,
        "location": location,
    }


def save_uploaded_video(uploaded_file) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", uploaded_file.name)
    output_path = DATA_DIR / f"uploaded_{safe_name}"

    if (
        st.session_state.get("uploaded_video_name") != uploaded_file.name
        or st.session_state.get("uploaded_video_size") != uploaded_file.size
    ):
        output_path.write_bytes(uploaded_file.getbuffer())
        st.session_state.uploaded_video_name = uploaded_file.name
        st.session_state.uploaded_video_size = uploaded_file.size
        st.session_state.uploaded_video_path = str(output_path)

    return st.session_state.get("uploaded_video_path", str(output_path))


def render_monitoring(config: dict) -> None:
    controls_left, controls_right = st.columns(2)
    with controls_left:
        if st.button("Start Monitoring", type="primary", width="stretch"):
            st.session_state.monitoring = True
            st.session_state.active_since = {}
            st.session_state.stream_config_key = monitoring_config_key(config)
            st.session_state.stream_port = start_monitoring_stream(config, DB_PATH, SCREENSHOT_DIR)
    with controls_right:
        if st.button("Stop Monitoring", width="stretch"):
            stop_capture()

    if not st.session_state.monitoring:
        show_idle_preview()
        return

    config_key = monitoring_config_key(config)
    if st.session_state.stream_port is None or st.session_state.stream_config_key != config_key:
        st.session_state.stream_config_key = config_key
        st.session_state.stream_port = start_monitoring_stream(config, DB_PATH, SCREENSHOT_DIR)

    render_mjpeg_view(st.session_state.stream_port)
    render_stream_status()


def monitoring_config_key(config: dict) -> tuple:
    return (
        config["source_mode"],
        config["camera_index"],
        config["camera_width"],
        config["camera_height"],
        config["sample_video_path"],
        config["loop_video"],
        config["model_path"],
        config["device"],
        config["ui_fps"],
        config["image_size"],
        config["confidence_threshold"],
        config["duration_threshold"],
        config["cooldown_seconds"],
        config["proximity_pixels"],
        config["table_percents"],
        config["camera_name"],
        config["location"],
    )


def render_mjpeg_view(port: int) -> None:
    st.iframe(f"http://127.0.0.1:{port}/viewer.html", width="stretch", height=760)


@st.fragment(run_every=1)
def render_stream_status() -> None:
    status = get_monitoring_status()
    st.info(status.get("message", "Monitoring is running."))
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("People", int(status.get("people", 0)))
    col2.metric("Phones", int(status.get("phones", 0)))
    col3.metric("Active rule matches", int(status.get("active_rule_matches", 0)))
    col4.metric("Logged last frame", int(status.get("logged_this_frame", 0)))
    col5.metric("Inference", f"{float(status.get('inference_ms', 0)):.0f} ms")


@st.fragment(run_every=0.25)
def render_live_frame(config: dict) -> None:
    st.info(st.session_state.last_message)
    video_slot = st.empty()
    metrics = st.empty()

    if not st.session_state.monitoring:
        show_idle_preview()
        return

    now = time.time()
    min_interval = 1 / max(int(config["ui_fps"]), 1)
    if now - st.session_state.last_preview_at < min_interval:
        show_cached_frame(video_slot, metrics)
        return

    source_key, source_value = source_from_config(config)
    if source_key is None:
        st.warning("Choose a sample video file or switch to webcam mode.")
        st.session_state.monitoring = False
        return

    capture = get_capture(source_key, source_value, config)
    if capture is None or not capture.isOpened():
        st.error(f"Could not open {config['source_mode'].lower()} source: {source_value}")
        stop_capture()
        return

    ok, frame = capture.read()
    if not ok and config["source_mode"] == "Sample video" and config["loop_video"]:
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = capture.read()

    if not ok or frame is None:
        st.warning("No frame was available from the selected source.")
        stop_capture()
        return

    detector = load_detector(config["model_path"], config["device"], DETECTOR_CACHE_VERSION)
    try:
        inference_started = time.perf_counter()
        detections = detector.detect(
            frame,
            confidence_threshold=config["confidence_threshold"],
            image_size=config["image_size"],
        )
        st.session_state.last_inference_ms = (time.perf_counter() - inference_started) * 1000
    except Exception as exc:
        st.error(f"YOLO inference failed: {exc}")
        stop_capture()
        return

    height, width = frame.shape[:2]
    table_zone = table_zone_from_percent(width, height, *config["table_percents"])
    candidates = classify_incidents(detections, table_zone, config["proximity_pixels"])
    annotated = draw_overlays(frame.copy(), detections, candidates, table_zone)
    confirmed = update_incident_timers(candidates, annotated, config)

    st.session_state.last_preview_at = now
    st.session_state.last_detections = detections
    st.session_state.last_candidates = candidates
    st.session_state.last_confirmed = confirmed
    st.session_state.last_annotated_frame = annotated

    video_slot.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), channels="RGB", width="stretch")
    metrics_frame(metrics, detections, candidates, confirmed)


def source_from_config(config: dict) -> tuple[str, int | str] | tuple[None, None]:
    if config["source_mode"] == "Webcam":
        return (
            f"webcam:{config['camera_index']}:{config['camera_width']}x{config['camera_height']}",
            config["camera_index"],
        )

    path = Path(config["sample_video_path"]).expanduser()
    if not path.exists() or not path.is_file():
        return None, None
    return f"sample:{path.resolve()}", str(path)


def get_capture(source_key: str, source_value: int | str, config: dict):
    capture = st.session_state.capture
    if capture is not None and st.session_state.capture_key == source_key and capture.isOpened():
        return capture

    release_capture()
    if isinstance(source_value, int):
        capture = cv2.VideoCapture(source_value, cv2.CAP_AVFOUNDATION)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config["camera_width"])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config["camera_height"])
    else:
        capture = cv2.VideoCapture(source_value)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    st.session_state.capture = capture
    st.session_state.capture_key = source_key
    return capture


def release_capture() -> None:
    capture = st.session_state.get("capture")
    if capture is not None:
        capture.release()
    st.session_state.capture = None
    st.session_state.capture_key = None


def stop_capture() -> None:
    st.session_state.monitoring = False
    st.session_state.active_since = {}
    st.session_state.stream_port = None
    st.session_state.stream_config_key = None
    stop_monitoring_stream()
    release_capture()


@st.cache_resource(show_spinner="Loading YOLO model...")
def load_detector(model_path: str, device: str, cache_version: int) -> YoloDetector:
    _ = cache_version
    return YoloDetector(model_path=model_path, device=device)


def update_incident_timers(
    candidates: list[IncidentCandidate],
    frame,
    config: dict,
) -> list[int]:
    now = time.time()
    active_types = {candidate.incident_type for candidate in candidates}

    for incident_type in list(st.session_state.active_since.keys()):
        if incident_type not in active_types:
            st.session_state.active_since.pop(incident_type, None)

    confirmed_ids: list[int] = []
    for incident_type in active_types:
        st.session_state.active_since.setdefault(incident_type, now)
        elapsed = now - st.session_state.active_since[incident_type]
        last_logged = st.session_state.last_logged.get(incident_type, 0)
        if elapsed < config["duration_threshold"] or now - last_logged < config["cooldown_seconds"]:
            continue

        strongest = max(
            (candidate for candidate in candidates if candidate.incident_type == incident_type),
            key=lambda candidate: candidate.confidence,
        )
        incident_id = save_incident(strongest, frame, config)
        st.session_state.last_logged[incident_type] = now
        st.session_state.active_since[incident_type] = now
        st.session_state.last_message = (
            f"Incident #{incident_id} logged: {incident_type} "
            f"({strongest.confidence:.2f} confidence)."
        )
        confirmed_ids.append(incident_id)

    return confirmed_ids


def save_incident(candidate: IncidentCandidate, frame, config: dict) -> int:
    timestamp = datetime.now().replace(microsecond=0)
    timestamp_for_filename = datetime.now()
    filename = f"incident_{timestamp_for_filename:%Y%m%d_%H%M%S_%f}_{candidate.incident_type}.jpg"
    screenshot_path = SCREENSHOT_DIR / filename
    cv2.imwrite(str(screenshot_path), frame)

    return add_incident(
        db_path=DB_PATH,
        timestamp=timestamp.isoformat(sep=" "),
        incident_type=candidate.incident_type,
        confidence=candidate.confidence,
        camera_name=config["camera_name"],
        location=config["location"],
        screenshot_path=str(screenshot_path),
    )


def draw_overlays(
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
        x1, y1, _, y2 = candidate.phone_bbox
        cv2.putText(frame, candidate.incident_type, (x1, y2 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    return frame


def metrics_frame(
    placeholder,
    detections: list[Detection],
    candidates: list[IncidentCandidate],
    confirmed_ids: list[int],
) -> None:
    people = sum(1 for detection in detections if detection.label == "person")
    phones = sum(1 for detection in detections if detection.label == "cell phone")
    with placeholder.container():
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("People", people)
        col2.metric("Phones", phones)
        col3.metric("Active rule matches", len(candidates))
        col4.metric("Logged this frame", len(confirmed_ids))
        col5.metric("Inference", f"{st.session_state.last_inference_ms:.0f} ms")


def show_idle_preview() -> None:
    st.caption("Monitoring is stopped.")
    if st.session_state.last_annotated_frame is not None:
        st.image(
            cv2.cvtColor(st.session_state.last_annotated_frame, cv2.COLOR_BGR2RGB),
            channels="RGB",
            width="stretch",
        )


def show_cached_frame(video_slot, metrics) -> None:
    cached_frame = st.session_state.last_annotated_frame
    if cached_frame is None:
        video_slot.caption("Preparing camera preview...")
        return

    video_slot.image(cv2.cvtColor(cached_frame, cv2.COLOR_BGR2RGB), channels="RGB", width="stretch")
    metrics_frame(
        metrics,
        st.session_state.last_detections,
        st.session_state.last_candidates,
        st.session_state.last_confirmed,
    )


def render_dashboard() -> None:
    today = date.today()
    start_default = today - timedelta(days=7)

    filter_cols = st.columns([1, 1, 1, 1, 1])
    start_date = filter_cols[0].date_input("Start date", value=start_default)
    end_date = filter_cols[1].date_input("End date", value=today)
    incident_type = filter_cols[2].selectbox("Incident type", ["All", *INCIDENT_TYPES])
    status = filter_cols[3].selectbox("Status", ["All", *STATUS_OPTIONS])
    if filter_cols[4].button("Refresh", width="stretch"):
        st.rerun()

    render_dashboard_results(
        start_date.isoformat(),
        end_date.isoformat(),
        incident_type,
        status,
    )


@st.fragment(run_every=2)
def render_dashboard_results(
    start_date: str,
    end_date: str,
    incident_type: str,
    status: str,
) -> None:
    df = load_incidents(
        DB_PATH,
        start_date=start_date,
        end_date=end_date,
        incident_type=incident_type,
        status=status,
    )

    render_summary(df)
    render_incident_table(df)
    render_status_editor(df)
    render_export(df)


def render_summary(df: pd.DataFrame) -> None:
    now = pd.Timestamp.now()
    if df.empty:
        today_count = 0
        week_count = 0
        by_type = pd.Series(dtype="int64")
    else:
        timestamps = pd.to_datetime(df["timestamp"])
        today_count = int((timestamps.dt.date == now.date()).sum())
        week_start = now.normalize() - pd.Timedelta(days=now.weekday())
        week_count = int((timestamps >= week_start).sum())
        by_type = df["incident_type"].value_counts()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total incidents today", today_count)
    col2.metric("Total incidents this week", week_count)
    col3.metric("Filtered incidents", len(df))

    if not by_type.empty:
        st.bar_chart(by_type)


def render_incident_table(df: pd.DataFrame) -> None:
    st.subheader("Recent Incidents")
    if df.empty:
        st.caption("No incidents match the selected filters.")
        return

    display_columns = {
        "timestamp": "Timestamp",
        "incident_type": "Incident Type",
        "confidence": "Confidence",
        "camera_name": "Camera",
        "location": "Location",
        "status": "Status",
        "screenshot_path": "Screenshot Path",
    }
    st.dataframe(
        df[list(display_columns.keys())].rename(columns=display_columns).head(100),
        width="stretch",
        hide_index=True,
    )

    recent = df.iloc[0]
    screenshot_path = Path(str(recent["screenshot_path"]))
    if screenshot_path.exists():
        st.image(
            screenshot_path.read_bytes(),
            caption=f"Latest screenshot: incident #{recent['incident_id']}",
            width="stretch",
        )
    else:
        st.warning(f"Screenshot file not found: {screenshot_path}")


def render_status_editor(df: pd.DataFrame) -> None:
    st.subheader("Review Status")
    if df.empty:
        return

    incident_ids = df["incident_id"].astype(int).tolist()
    selected_id = st.selectbox("Incident ID", incident_ids)
    current_status = str(df.loc[df["incident_id"] == selected_id, "status"].iloc[0])
    new_status = st.selectbox(
        "New status",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
    )

    if st.button("Update Status"):
        update_status(DB_PATH, int(selected_id), new_status)
        st.success(f"Incident #{selected_id} updated to {new_status}.")
        st.rerun()


def render_export(df: pd.DataFrame) -> None:
    export_columns = [
        "incident_id",
        "timestamp",
        "incident_type",
        "confidence",
        "camera_name",
        "location",
        "screenshot_path",
        "status",
        "notes",
    ]
    csv_bytes = df.reindex(columns=export_columns).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export CSV",
        data=csv_bytes,
        file_name="cellphone_monitoring_incidents_export.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
