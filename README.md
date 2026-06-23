# SPM SecureOps — Cellphone Monitoring System

Real-time computer vision security monitoring system that detects visible cellphones in restricted production areas using a webcam or sample video feed. Built with a FastAPI backend and React frontend.

## Architecture

```
┌──────────────────┐       REST / MJPEG       ┌──────────────────┐
│  React Frontend  │ ◄──────────────────────► │  FastAPI Backend  │
│  (Next.js + TS)  │                           │  (Uvicorn)        │
└──────────────────┘                           └────────┬─────────┘
                                                        │
                              ┌──────────────────────────┼──────────────────┐
                              │                          │                   │
                    ┌─────────▼────────┐   ┌────────────▼───┐   ┌──────────▼──────────┐
                    │ DetectionWorker   │   │ RetentionService│   │ PipelineManager     │
                    │ (YOLO inference)  │   │ (data cleanup)  │   │ (start/stop/config) │
                    └──────────────────┘   └────────────────┘   └─────────────────────┘
                              │
                    ┌─────────▼────────┐
                    │   PostgreSQL      │
                    │   (async via      │
                    │    SQLAlchemy)    │
                    └──────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg |
| Frontend | React 19, TypeScript ~5.8, Next.js 15, Tailwind CSS v4, shadcn/ui, Recharts, Axios |
| Package Manager | pnpm (frontend) |
| Detection | YOLO11 Nano (`yolo11n.pt`) via Ultralytics, OpenCV |
| Database | PostgreSQL |
| Testing | pytest, Hypothesis (property-based); Vitest, fast-check (frontend) |

## Prerequisites

- Python 3.12+
- Node.js (LTS)
- pnpm (`npm install -g pnpm`)
- PostgreSQL running locally (or accessible via connection string)

## Getting Started

### 1. Clone and configure environment

```bash
cd CellphoneMonitoring
cp .env.example .env  # or create .env manually
```

Required environment variables in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/security_monitoring
CORS_ORIGINS=http://localhost:3000
```

The frontend uses an optional `BACKEND_URL` environment variable (default: `http://backend:8000`) to configure Next.js rewrites that proxy `/api/*`, `/health`, `/incidents/*`, `/zones/*`, `/stream/*`, and `/screenshots/*` requests to the backend. For local development without Docker, set `BACKEND_URL=http://localhost:8000` in the frontend's `.env.local`.

### 2. Backend setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Database setup

Create the PostgreSQL database:

```sql
CREATE DATABASE security_monitoring;
```

Tables are created automatically on first startup via SQLAlchemy.

### 4. Run the backend

```bash
uvicorn backend.app:app --reload
```

The API will be available at `http://localhost:8000`. On first run, Ultralytics will download the `yolo11n.pt` model.

### 5. Frontend setup

```bash
cd frontend
pnpm install
pnpm dev
```

The frontend will be available at `http://localhost:3000`. API requests are proxied to the backend via Next.js rewrites (configured in `next.config.ts`). For local dev, create `frontend/.env.local`:

```env
BACKEND_URL=http://localhost:8000
```

In Docker Compose the default (`http://backend:8000`) resolves to the backend service automatically.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health check |
| GET | `/stream/video` | MJPEG live video stream |
| GET | `/api/incidents` | List incidents (with filtering) |
| POST | `/api/incidents` | Create incident |
| PATCH | `/api/incidents/{id}` | Update incident status/notes |
| GET | `/api/zones` | Get desk zone configuration |
| PUT | `/api/zones` | Update desk zone |
| GET | `/api/audit` | Audit trail logs |
| GET | `/api/pipeline/status` | Pipeline running state and metrics |
| POST | `/api/pipeline/start` | Start detection pipeline (source_type: "webcam", "cctv", or "file") |
| POST | `/api/pipeline/stop` | Stop detection pipeline |
| GET | `/api/pipeline/detections` | Latest detection results |
| PUT | `/api/pipeline/config` | Update runtime pipeline config |
| POST | `/api/browser-camera/detect` | Detect objects in a browser-uploaded JPEG frame |

## Detection Rules

YOLO detections are filtered to two classes: `person` and `cell phone`.

Incident types:

- **PHONE_ON_TABLE** — phone center is inside the configured desk zone
- **PHONE_NEAR_PERSON** — phone overlaps or is within proximity threshold of a person bounding box
- **DOCUMENT_LEFT_ON_DESK** — book/document center is inside the configured desk zone

If both rules apply, `PHONE_NEAR_PERSON` takes priority over `PHONE_ON_TABLE` for the same phone.

## Configuration

All tunable parameters are defined in `backend/config.py` (`AppConfig` dataclass):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_path` | `yolo11n.pt` | YOLO model file |
| `device` | `auto` | Inference device (`auto`, `cpu`, `mps`) |
| `confidence_threshold` | `0.40` | Minimum detection confidence |
| `image_size` | `640` | Inference input resolution |
| `camera_index` | `0` | Webcam device index |
| `camera_width` | `960` | Capture width |
| `camera_height` | `540` | Capture height |
| `duration_threshold` | `0.5s` | Seconds before logging incident |
| `cooldown_seconds` | `5` | Duplicate suppression window |
| `proximity_pixels` | `80` | Phone-to-person proximity |
| `ui_fps` | `12` | MJPEG stream frame rate |
| `retention_days` | `7` | Days before old data cleanup |

## Frontend Views

The frontend uses client-side view switching within a single Shell layout (no page transitions):

| View | Description |
|------|-------------|
| Dashboard | Overview with status cards, live monitoring card (Browser/MJPEG toggle), event feed, AI assistant, governance badges |
| Live Monitoring | Full-size MJPEG feed with real-time detection metrics, pipeline controls |
| Compliance Events | Event list with priority badges, AI assistant panel |
| Compliance Review | Searchable incident table with workflow actions and CSV export |
| Analytics | Charts (daily events, category breakdown, review trends) |
| System Status | Component health progress bars (Camera, AI, Backend, DB, AWS, Retention) |
| Settings | Desk zone config, monitoring toggles, data governance |

### Pipeline Controls Widget

The `PipelineControls` widget provides in-dashboard start/stop controls for the detection pipeline with four source presets (defaults to Browser Camera):

| Preset | Source Type | Default source_id |
|--------|------------|-------------------|
| Browser Camera (default) | browser | Browser webcam via `/api/browser-camera/detect` |
| Demo Video | `file` | `/app/backend/demo.mp4` |
| Live Camera (RTSP/HTTP) | `cctv` | User-provided URL |
| Custom File | `file` | User-provided path |

The widget polls `/api/pipeline/status` every 3 seconds and displays live metrics (FPS, frames processed, inference latency, detection count) while the pipeline is running. When "Browser Camera" is selected, the pipeline start/stop buttons are hidden since detection is handled per-frame via the browser camera endpoint.

**Auto-start behavior:** Selecting "Demo Video" starts the pipeline only if the backend stream is not already active. If the detection worker is already running on mount (e.g., auto-started via the `DEMO_VIDEO_PATH` environment variable), the widget detects the active stream and switches the active preset to "Demo Video" automatically. Switching back to "Browser Camera" no longer stops the backend pipeline — it only switches the frontend view to browser camera mode.

## Browser Camera Detection

The system supports using the user's browser webcam as a video source via the `/api/browser-camera/detect` endpoint. The browser captures frames using `getUserMedia` + canvas, encodes them as JPEG, and POSTs them to the backend for YOLO inference.

| Field | Description |
|-------|-------------|
| Request | `POST /api/browser-camera/detect` with `multipart/form-data` containing a JPEG `frame` |
| Response | JSON with `detections` (array of label, confidence, bbox, class_id), `inference_ms`, `frame_width`, `frame_height` |
| Error | 422 if non-image content type, empty payload, or undecodable image |

The endpoint lazily initializes a shared `InferenceEngine` on first request and reuses it for subsequent calls. Detection results are also dispatched to the Compliance Event Engine for automated incident classification (same as the pipeline path).

## Video Source Types

The pipeline supports three source types via POST `/api/pipeline/start`:

| Source Type | `source_id` | Description |
|-------------|-------------|-------------|
| `webcam` | Integer 0–10 | Local webcam device index |
| `cctv` | `rtsp://` or `http://` URL | Network CCTV stream |
| `file` | File path string | Local video file (e.g., MP4, AVI) with optional looping |

When using `"file"` source type, the pipeline reads from a local video file. If `loop` is enabled in the frame capture config, the video restarts from the beginning when it reaches the end — useful for demo/testing with sample footage.

## Background Services

- **DetectionWorker** — captures frames from webcam/video, runs YOLO inference, applies rules, logs incidents with screenshots
- **RetentionService** — periodically cleans incidents and screenshots older than `retention_days`
- **PipelineManager** — provides start/stop/config control over the detection pipeline via REST API

## Project Structure

```
CellphoneMonitoring/
├── .env                        # Environment variables
├── backend/                    # FastAPI backend
│   ├── app.py                  # Entry point — lifespan, CORS, routers
│   ├── config.py               # AppConfig dataclass
│   ├── core/                   # Detection engine, rules, pipeline
│   ├── db/                     # Async SQLAlchemy models, queries, session
│   ├── routers/                # API route modules
│   ├── schemas/                # Pydantic request/response schemas
│   ├── workers/                # Background services
│   └── tests/                  # pytest + hypothesis tests
├── frontend/                   # Next.js frontend (React 19 + shadcn/ui)
│   ├── app/                    # Next.js App Router pages and layouts
│   ├── components/             # UI components (shell, views, widgets, ui)
│   ├── hooks/                  # Custom React hooks (polling, websocket)
│   ├── lib/                    # API client, types, constants, utilities
│   ├── __tests__/              # Vitest + fast-check tests
│   └── package.json
├── data/                       # Runtime data (gitignored)
│   └── ultralytics/            # YOLO config/cache
└── screenshots/                # Captured incident frames (gitignored)
```

## Running Tests

```bash
# Backend tests
pytest backend/tests/ -v

# Frontend tests
cd frontend && pnpm test

# Frontend lint
cd frontend && pnpm lint
```

## Local Data

- Incidents are stored in PostgreSQL
- Screenshots are saved to `screenshots/`
- YOLO model cache lives in `data/ultralytics/`
- No cloud services, paid APIs, face recognition, or external notifications

## Deployment

See the AWS stack steering rules for Docker and EC2 deployment guidance. The system supports containerized deployment via Docker Compose with services for the API, frontend (Nginx), and PostgreSQL.
