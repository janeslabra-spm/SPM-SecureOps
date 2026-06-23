# Implementation Plan: Security Monitoring System

## Overview

Migration of the Cellphone Monitoring System from a Streamlit monolith to a decoupled FastAPI backend + React TypeScript frontend architecture. The implementation proceeds in layers: project scaffolding → core domain modules → database layer → API endpoints → background workers → frontend → integration wiring. Each task builds incrementally on prior work so there is no orphaned code.

## Tasks

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Create backend project structure and install dependencies
    - Create `backend/` directory with sub-packages: `core/`, `db/`, `workers/`, `routers/`, `schemas/`
    - Create `backend/__init__.py`, `backend/core/__init__.py`, `backend/db/__init__.py`, `backend/workers/__init__.py`, `backend/routers/__init__.py`, `backend/schemas/__init__.py`
    - Create `backend/requirements.txt` with: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, pydantic, pydantic-settings, python-multipart, opencv-python, ultralytics, numpy, hypothesis (dev)
    - Create `backend/config.py` with `AppConfig` dataclass matching the design specification (database_url, model_path, device, thresholds, etc.)
    - _Requirements: 8.1, 8.4_

  - [x] 1.2 Create frontend project structure with Vite + React TypeScript
    - Initialize `frontend/` using Vite with React TypeScript template
    - Install dependencies: react, react-dom, react-router-dom, axios (or fetch wrapper)
    - Set up `tsconfig.json`, `vite.config.ts` with proxy to backend during development
    - Create placeholder `App.tsx` with routing shell (LiveMonitor and IncidentDashboard routes)
    - _Requirements: 7.1_

- [x] 2. Implement core domain modules (backend)
  - [x] 2.1 Migrate and extend the Detection module
    - Create `backend/core/detector.py` with `Detection` dataclass and `YoloDetector` class
    - Add `"book"` to `TARGET_LABELS` (as proxy for paper document detection)
    - Preserve existing detection logic from `src/detector.py`
    - Add `detection_labels()` utility function
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ]* 2.2 Write property test for confidence threshold filtering
    - **Property 1: Confidence Threshold Filtering**
    - Generate random Detection lists with confidence ∈ [0, 1] and random threshold ∈ [0.1, 0.95]
    - Assert all returned detections have confidence >= threshold
    - **Validates: Requirements 1.3, 1.6**

  - [x] 2.3 Migrate and extend the Rule Engine
    - Create `backend/core/rules.py` with `PHONE_ON_TABLE`, `PHONE_NEAR_PERSON`, `DOCUMENT_LEFT_ON_DESK` constants
    - Migrate `IncidentCandidate` dataclass, `classify_incidents()`, `table_zone_from_percent()`, and helper functions
    - Add `DOCUMENT_LEFT_ON_DESK` classification: "book" label center inside desk zone → DOCUMENT_LEFT_ON_DESK
    - Maintain PHONE_NEAR_PERSON priority over PHONE_ON_TABLE for cell phones
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.4 Write property tests for zone-based and proximity-based classification
    - **Property 2: Zone-Based Violation Classification**
    - Generate random bboxes and zones; verify center-in-zone produces correct violation type
    - **Property 3: Proximity-Based Violation Classification**
    - Generate random phone+person bboxes with random proximity; verify PHONE_NEAR_PERSON when overlap or within threshold
    - **Property 4: PHONE_NEAR_PERSON Priority Over PHONE_ON_TABLE**
    - Generate bboxes satisfying both conditions; assert only PHONE_NEAR_PERSON produced
    - **Property 5: Independent Phone Evaluation**
    - Generate 1–10 phone detections; assert at most one violation per phone and total violations ≤ phone count
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6**

  - [x] 2.5 Implement Incident Logger
    - Create `backend/core/incident_logger.py` with `IncidentLogger` class
    - Implement `try_log_incident()` with duration threshold gating and cooldown suppression
    - Implement `_should_suppress()` for cooldown check
    - Implement `_save_screenshot()` with timestamp-to-millisecond + incident_type filename format
    - Handle screenshot write failure gracefully (empty path, error in notes)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 2.6 Write property tests for incident logger
    - **Property 6: Duration Threshold Gating**
    - Generate random detection sequences with timestamps and thresholds; assert no logging before threshold met
    - **Property 7: Cooldown Suppression**
    - Generate random logging attempt sequences; assert suppression within cooldown window
    - **Property 8: Screenshot Filename Format**
    - Generate random incident types and timestamps; verify filename contains millisecond timestamp and incident type
    - **Validates: Requirements 3.1, 3.3, 3.4**

- [x] 3. Checkpoint - Core modules
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement database layer (PostgreSQL + async SQLAlchemy)
  - [x] 4.1 Create SQLAlchemy models and session management
    - Create `backend/db/models.py` with `Incident` and `DeskZoneConfig` ORM models matching the PostgreSQL schema in design
    - Create `backend/db/session.py` with `get_db_session()` async generator, `init_db()` to create tables, and `check_db_connection()` health check
    - Use async SQLAlchemy with asyncpg driver
    - _Requirements: 8.3, 8.5_

  - [x] 4.2 Implement incident query functions
    - Create `backend/db/queries.py` with async functions: `query_incidents()` (filtered, paginated max 100, ordered by timestamp DESC), `get_incident_by_id()`, `update_incident_status()`, `insert_incident()`, `delete_expired_incidents()`
    - Support filters: date range, incident_type, status
    - _Requirements: 6.1, 6.2, 6.4, 6.6_

  - [ ]* 4.3 Write property test for incident query filtering
    - **Property 11: Incident Query Filtering and Ordering**
    - Generate random incident data and filter combinations; assert results match ALL filters, max 100 records, sorted DESC by timestamp
    - **Validates: Requirements 6.1, 6.4**

  - [x] 4.4 Implement desk zone persistence functions
    - Create `backend/db/desk_zone.py` with `get_desk_zone()` and `upsert_desk_zone()` async functions
    - Ensure singleton row pattern (id=1 constraint) with default values on first read
    - _Requirements: 9.1, 9.3, 9.4_

- [x] 5. Implement API routers (FastAPI endpoints)
  - [x] 5.1 Create health check endpoint
    - Create `backend/routers/health.py` with `GET /health` returning `HealthResponse`
    - Check DB connection, detection engine active state, uptime
    - Must respond within 500ms
    - _Requirements: 8.7_

  - [x] 5.2 Create streaming endpoints
    - Create `backend/routers/stream.py` with `GET /stream/video.mjpg` (MJPEG StreamingResponse) and `GET /stream/status` (JSON metrics)
    - Use `multipart/x-mixed-replace; boundary=frame` content type
    - Add `Cache-Control: no-cache` headers
    - Return 503 if monitoring worker is not active
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [x] 5.3 Create incident management endpoints
    - Create `backend/routers/incidents.py` with:
      - `GET /incidents` — filtered list (date range, type, status), max 100, sorted DESC
      - `PATCH /incidents/{incident_id}/status` — update status (validate against allowed values)
      - `GET /incidents/export` — CSV export with required columns
    - Return 404 for non-existent incident_id, 422 for invalid status
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 5.4 Write property tests for API validation
    - **Property 12: Invalid Status Rejection**
    - Generate random strings excluding valid statuses; assert rejection with error response
    - **Property 13: CSV Export Column Completeness**
    - Generate random incident data; verify CSV contains all required columns and values match
    - **Validates: Requirements 6.3, 6.5**

  - [x] 5.5 Create desk zone endpoints
    - Create `backend/routers/zones.py` with `GET /zones/desk` and `PUT /zones/desk`
    - Validate percentage values [0, 100] with Pydantic; reject out-of-range with 422
    - Persist to database before confirming acceptance
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 5.6 Write property test for desk zone validation
    - **Property 14: Desk Zone Validation and Normalization**
    - Generate random four-integer inputs; assert acceptance for [0,100] values and rejection for out-of-range; verify pixel coordinate normalization (x1 ≤ x2, y1 ≤ y2)
    - **Validates: Requirements 9.1, 9.2, 9.5**

- [x] 6. Checkpoint - API layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement background workers
  - [x] 7.1 Implement Detection Worker
    - Create `backend/workers/detection_worker.py` with `DetectionWorker` class
    - Migrate logic from `MonitoringWorker` in `src/mjpeg_stream.py` to use async DB session factory and new `IncidentLogger`
    - Implement `start()`, `stop()`, `get_latest_frame()`, `get_status()`, `wait_for_frame()`
    - Frame annotation with bounding boxes, confidence scores, labels, violation indicators, desk zone overlay
    - _Requirements: 1.1, 1.4, 5.4, 8.5_

  - [x] 7.2 Implement Retention Service
    - Create `backend/workers/retention_service.py` with `RetentionService` class
    - Implement `run_cleanup()`: delete incidents older than 7 days, delete associated screenshot files, delete orphan screenshots older than 7 days
    - Schedule cleanup every 24 hours using asyncio task
    - Log deleted record count and file count (including zeros)
    - Handle missing files gracefully, handle permission errors without stopping
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 7.3 Write property tests for retention service
    - **Property 9: Retention Cleanup Deletes Expired Records and Screenshots**
    - Generate random incident sets with timestamps ±14 days; assert records >7 days deleted, ≤7 days preserved
    - **Property 10: Orphan Screenshot Cleanup**
    - Generate random file sets (some referenced, some not) with random ages; assert unreferenced files >7 days deleted, referenced or recent files preserved
    - **Validates: Requirements 4.1, 4.2, 4.7**

- [x] 8. Wire FastAPI application entry point
  - [x] 8.1 Create main FastAPI application with startup/shutdown
    - Create `backend/app.py` with FastAPI instance
    - Register all routers (health, stream, incidents, zones)
    - Configure CORS middleware with configurable origins
    - On startup: call `init_db()`, start `DetectionWorker`, start `RetentionService`
    - On shutdown: stop `DetectionWorker`, stop `RetentionService`
    - If DB connection fails on startup, terminate with exit code 1 and log error
    - Serve OpenAPI docs at `/docs`
    - _Requirements: 8.1, 8.2, 8.4, 8.5, 8.6_

- [x] 9. Implement React TypeScript SOC Dashboard frontend
  - [x] 9.1 Set up frontend project structure, services, and hooks
    - Install additional dependencies: recharts, tailwindcss, @tailwindcss/vite, react-router-dom, axios
    - Configure Tailwind CSS with dark mode SOC color scheme (slate-900+ backgrounds, neon green #00FF88 accents)
    - Create `frontend/src/services/api.ts` — Axios HTTP client with base URL config for all REST API calls
    - Create `frontend/src/services/websocket.ts` — WebSocket connection manager with connect, reconnect (5-second retry), JSON message parsing for /ws/incidents
    - Create `frontend/src/hooks/useWebSocket.ts` — Custom hook exposing connection state and incoming messages
    - Create `frontend/src/hooks/usePolling.ts` — Custom hook accepting interval parameter (ms) for periodic data fetching
    - Remove `frontend/src/components/LiveMonitor.css` (no component-specific CSS, use Tailwind only)
    - _Requirements: 7.1, 11.1, 11.3, 11.4, 11.7_

  - [x] 9.2 Implement Sidebar and page layout with React Router
    - Create `frontend/src/components/Sidebar.tsx` — Persistent dark-themed left sidebar with menu items: Camera, Dashboard, Live Monitoring, Incident Review, Audit Logs, Security Policies, Settings
    - Create `frontend/src/pages/dashboard.tsx` — Main SOC overview page (placeholder for now, wired in 9.3)
    - Create `frontend/src/pages/incidents.tsx` — Incident Review page (placeholder, wired in 9.5)
    - Create `frontend/src/pages/cameras.tsx` — Camera management view (placeholder)
    - Create `frontend/src/pages/audit.tsx` — Audit logs view (placeholder)
    - Create `frontend/src/pages/settings.tsx` — System settings (placeholder)
    - Update `frontend/src/App.tsx` with React Router: root "/" redirects to "/dashboard", Sidebar visible on all pages, 404 fallback page with link to /dashboard
    - _Requirements: 7.2, 11.1, 11.2, 11.5, 11.6_

  - [x] 9.3 Implement SOC Dashboard main page (dashboard.tsx)
    - Create `frontend/src/components/StatusCard.tsx` — Compact metric card for top bar
    - Implement top status bar with four StatusCards: "Cameras Online", "Active Violations", "Model Status" (avg confidence last 60s), "Data Retention Policy" (7 Days)
    - Create `frontend/src/components/CameraPanel.tsx` — Live MJPEG feed via `<img>` tag pointing to `/stream/video.mjpg`, minimum 60% viewport width, show "Feed Disconnected" overlay if no frame within 10 seconds
    - Create `frontend/src/components/DetectionFeed.tsx` — Right-side scrolling list, max 50 entries (FIFO), each entry shows timestamp + incident type + confidence, ordered most recent first
    - Create `frontend/src/components/AnalyticsGraph.tsx` — Recharts-based incidents-per-hour bar/line chart for current day
    - Wire dashboard.tsx to compose StatusCards + CameraPanel + DetectionFeed + AnalyticsGraph
    - Create `frontend/src/components/SecurityStatus.tsx` — System health panel showing Backend/Database/AI Engine with green/red indicators
    - Poll GET /api/status every 10 seconds to refresh SecurityStatus panel
    - Create Data Governance footer: "Retention Policy: 7 Days", "Auto Delete: Enabled", "ISO 27001" compliance badge
    - _Requirements: 7.1, 7.3, 7.4, 7.5, 7.6, 7.9, 7.10, 7.11, 7.12_

  - [x] 9.4 Implement WebSocket alerts and AlertBanner
    - Create `frontend/src/components/AlertBanner.tsx` — Dismissible notification banner showing incident type + confidence, visible ≥5 seconds or until dismissed
    - Connect useWebSocket hook to /ws/incidents endpoint
    - When new_incident event received: append to DetectionFeed, increment Active Violations StatusCard, display AlertBanner
    - If WebSocket connection lost: display "Connection Lost" in SecurityStatus panel, auto-reconnect every 5 seconds
    - _Requirements: 7.13, 10.5, 10.6_

  - [x] 9.5 Implement Incident Review page (incidents.tsx)
    - Implement paginated data table with columns: time, incident type, confidence, status — max 20 rows/page with prev/next navigation
    - Add filter controls: date range picker, incident type dropdown, status dropdown — AND logic combining all active filters
    - Implement status update per incident row via PATCH /incidents/{id}/status with dropdown (Pending Review, Confirmed, False Alarm)
    - Create `frontend/src/components/IncidentExport.tsx` — CSV export button triggering download from GET /incidents/export with active filters as query params
    - _Requirements: 7.7, 7.8, 6.5_

- [x] 10. Checkpoint - Full stack integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Integration tests and final wiring
  - [x] 11.1 Write backend integration tests
    - Test full detection pipeline: frame → detections → classification → incident logging
    - Test database lifecycle: create, query, update incidents across PostgreSQL
    - Test retention end-to-end: insert expired records, run cleanup, verify deletion
    - Test startup sequence: DB init, worker start, retention scheduler start
    - Test MJPEG streaming: connect, receive frames, verify multipart format
    - _Requirements: 1.1, 3.2, 4.1, 5.1, 8.5_

  - [ ]* 11.2 Write frontend unit tests
    - Test LiveMonitor renders MJPEG img and metrics
    - Test IncidentDashboard renders filter controls and incident table
    - Test AlertNotification shows and auto-dismisses
    - Test error states (feed disconnected, API unreachable)
    - _Requirements: 7.1, 7.2, 7.5, 7.7_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- The backend uses Python (FastAPI + async SQLAlchemy + asyncpg) and the frontend uses React TypeScript (Vite)
- Core detection and rule modules are migrated from existing `src/` code with minimal changes (adding "book" detection and DOCUMENT_LEFT_ON_DESK rule)
- The existing `app.py`, `src/` directory remain untouched during migration — the new code lives in `backend/` and `frontend/`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "4.2", "4.4"] },
    { "id": 3, "tasks": ["2.4", "2.5", "4.3"] },
    { "id": 4, "tasks": ["2.6", "5.1", "5.2", "5.3", "5.5"] },
    { "id": 5, "tasks": ["5.4", "5.6", "7.1", "7.2"] },
    { "id": 6, "tasks": ["7.3", "8.1"] },
    { "id": 7, "tasks": ["9.1"] },
    { "id": 8, "tasks": ["9.2"] },
    { "id": 9, "tasks": ["9.3", "9.5"] },
    { "id": 10, "tasks": ["9.4"] },
    { "id": 11, "tasks": ["10", "11.1", "11.2"] },
    { "id": 12, "tasks": ["12"] }
  ]
}
```
