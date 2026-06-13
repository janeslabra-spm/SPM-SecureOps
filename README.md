# Cellphone Monitoring System

Local-only Streamlit MVP for detecting visible cellphones from a webcam or sample video.

## Setup

Use Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit.

## Demo Modes

The sidebar has two video sources:

- `Webcam`: opens the configured camera index, default `0`.
- `Sample video`: uses an uploaded video or a local file path.

For a stable hackathon demo, place a video at:

```text
sample_videos/demo.mp4
```

Then choose `Sample video` in the sidebar and click `Start Monitoring`.

## Smooth Preview Settings

For a stable demo on a MacBook, start with:

- `UI frame rate`: `2`
- `Inference image size`: `480`
- `Camera width`: `960`
- `Camera height`: `540`

The app shows the live feed through a local MJPEG preview stream, so the browser keeps one stable video element instead of repainting a Streamlit image for every frame. Lower the UI frame rate if the laptop gets warm; raise the inference image size if phone boxes are too loose.

## Notes For macOS Sequoia

- The first webcam run may trigger a camera permission prompt.
- If webcam access is unstable, switch to `Sample video`.
- The default model is `yolov8n.pt`. Ultralytics may download it on first use if it is not already present.
- Use `cpu` if `mps` inference is not available or behaves inconsistently.

## Local Data

- Incidents are stored in `data/incidents.db`.
- Screenshots are stored in `screenshots/`.
- Uploaded sample videos are stored in `data/`.
- No cloud storage, paid APIs, face recognition, or external notification services are used.
