# Cellphone Monitoring System MVP Spec

Local-only compliance monitoring assistant for detecting visible cellphones in a restricted production area.

## Runtime

- Python 3.12 on macOS Sequoia 15.6
- Streamlit local dashboard
- OpenCV video capture
- Ultralytics YOLO object detection
- SQLite incident database at `data/incidents.db`
- Local screenshots in `screenshots/`

## Monitoring Sources

The live monitoring page supports two modes:

- Webcam mode: opens a camera by index, default `0`, using OpenCV AVFoundation capture on macOS.
- Sample video mode: reads a local video file or an uploaded video and can loop it for repeatable demos.

Place an optional default demo video at:

```text
sample_videos/demo.mp4
```

## Detection Rules

YOLO detections are filtered to:

- `person`
- `cell phone`

Incident types:

- `PHONE_ON_TABLE`: phone center is inside the configured table zone.
- `PHONE_HELD_OR_NEAR_PERSON`: phone overlaps with or is close to a person box.

If both rules apply, `PHONE_HELD_OR_NEAR_PERSON` is prioritized.

## Incident Persistence

Each confirmed incident stores:

- incident_id
- timestamp
- incident_type
- confidence
- camera_name
- location
- screenshot_path
- status
- notes

Default review statuses:

- Pending Review
- Confirmed
- False Alarm
