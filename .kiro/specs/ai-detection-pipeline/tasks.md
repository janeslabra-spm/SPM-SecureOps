# Implementation Plan: AI Detection Pipeline

## Overview

This plan implements the AI Detection Pipeline by decomposing the existing monolithic `DetectionWorker` into discrete, testable pipeline stages with typed interfaces, REST API control endpoints, and compliance event dispatch. Each task builds incrementally, starting with data models and interfaces, then core components, then wiring and integration.

## Tasks

- [x] 1. Define data models, schemas, and core interfaces
  - [x] 1.1 Create Pydantic schemas for the pipeline API
    - Create `backend/schemas/pipeline.py` with all request/response models: `BoundingBox`, `DetectionResultSchema`, `PipelineStartRequest`, `PipelineStartResponse`, `PipelineStopResponse`, `PipelineStatusResponse`, `PipelineConfigUpdate`, `PipelineConfigResponse`, `ErrorResponse`
    - Include field validators for source_id (webcam integer 0–10, CCTV rtsp:// or http:// URL)
    - Include field constraints: confidence_threshold [0.0, 1.0], image_size [320, 1280], fps_limit [1, 30]
    - _Requirements: 5.1, 7.1, 7.2, 7.3, 7.7, 7.9, 7.10_

  - [x] 1.2 Create internal dataclasses and type definitions
    - Create `backend/core/pipeline_types.py` with: `FrameCaptureConfig`, `RawDetection`, `Detection`, `DetectionResult`, `DetectionEvent`, `PipelineMetrics`
    - Define custom exceptions: `SourceUnavailableError`
    - Use frozen dataclasses for immutable value objects
    - _Requirements: 1.4, 2.3, 3.1, 5.1, 6.2_

- [x] 2. Implement FrameCaptureService
  - [x] 2.1 Implement frame capture with webcam and CCTV support
    - Create `backend/core/frame_capture.py` with `FrameCaptureService` class
    - Implement `open()` with webcam (integer index) and CCTV (RTSP/HTTP URL) source handling
    - Implement URL scheme validation for CCTV sources (rtsp:// or http://)
    - Implement `read()` with FPS rate limiting using time-based throttling
    - Implement `release()` for resource cleanup within 5 seconds
    - Implement reconnection logic: 3 attempts, 2-second interval for CCTV failures
    - Raise `SourceUnavailableError` with source_type and source_id in message on permanent failure
    - Handle single-frame read failures: skip and retry for webcam, trigger reconnection for CCTV
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 2.2 Write property tests for FrameCaptureService
    - **Property 1: CCTV URL Scheme Validation** — generate arbitrary strings and verify acceptance iff starts with "rtsp://" or "http://"
    - **Property 2: Source Error Identity** — verify error messages contain source_type and source_id substrings
    - **Property 3: Frame Rate Limiting** — verify interval between reads ≥ 1/fps_limit
    - **Validates: Requirements 1.2, 1.4, 1.6**

- [x] 3. Implement InferenceEngine
  - [x] 3.1 Implement YOLOv8n inference wrapper
    - Create `backend/core/inference_engine.py` with `InferenceEngine` class
    - Load YOLOv8n model at init; raise `RuntimeError` if model path invalid
    - Filter inference to target classes: person (0), cell phone (67), book (73)
    - Accept device parameter ("auto", "cpu", "cuda", "mps") and image_size config
    - Return empty list on inference failure (log error, don't crash)
    - Return `list[RawDetection]` with class_id, label, confidence, bbox_raw
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 8.1_

- [x] 4. Implement BoundingBoxExtractor
  - [x] 4.1 Implement bounding box normalization and validation
    - Create `backend/core/bbox_extractor.py` with `BoundingBoxExtractor` class
    - Implement `extract()` static method: convert raw float coords to integer pixels (truncate toward zero)
    - Swap coordinates if x1 >= x2 or y1 >= y2
    - Clamp to frame boundaries: [0, frame_width-1] for x, [0, frame_height-1] for y
    - Discard detections with non-finite values (NaN, inf)
    - Discard zero-area bounding boxes after normalization
    - Map class_ids to labels: 0→"person", 67→"cell phone", 73→"book"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 4.2 Write property tests for BoundingBoxExtractor
    - **Property 4: Bounding Box Normalization Invariants** — generate random float coords and frame dims, verify 0 ≤ x1 < x2 ≤ frame_width-1, 0 ≤ y1 < y2 ≤ frame_height-1, area > 0; verify non-finite coords are discarded
    - **Property 5: Class Label Mapping** — generate class_ids from {0, 67, 73}, verify correct label assignment
    - **Validates: Requirements 3.2, 3.3, 3.5, 3.6, 5.2, 8.2**

- [x] 5. Implement ConfidenceScorer
  - [x] 5.1 Implement confidence filtering and Non-Maximum Suppression
    - Create `backend/core/confidence_scorer.py` with `ConfidenceScorer` class
    - Implement threshold filtering (scores equal to threshold are retained)
    - Validate threshold in [0.0, 1.0]; reject invalid with error, apply default 0.4
    - Implement per-class NMS with IoU ≥ 0.5 threshold; retain highest confidence
    - Implement tie-breaking: identical confidence → keep larger bounding box area
    - Sort results descending by confidence; ties broken by ascending class_id
    - Produce `DetectionResult` with bbox as dict for JSON serialization
    - Implement `compute_iou()` static method
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.3_

  - [ ]* 5.2 Write property tests for ConfidenceScorer
    - **Property 6: Confidence Threshold Filtering** — generate random detection lists and thresholds, verify all outputs ≥ threshold and confidence preserved
    - **Property 7: Threshold Range Validation** — generate arbitrary floats, verify only [0.0, 1.0] accepted; invalid values result in default 0.4
    - **Property 8: Non-Maximum Suppression Correctness** — generate overlapping same-class pairs with IoU ≥ 0.5, verify only highest confidence retained; ties broken by area
    - **Property 9: Detection Result Ordering** — generate random detection lists, verify descending confidence with class_id tiebreaker
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 5.3, 8.5**

- [x] 6. Checkpoint - Core pipeline components
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement ComplianceEventDispatcher
  - [x] 7.1 Implement async event dispatch with buffering and retry
    - Create `backend/core/event_dispatcher.py` with `ComplianceEventDispatcher` class
    - Implement non-blocking async dispatch via asyncio.Queue (≤5ms overhead)
    - Buffer up to 100 events when downstream unavailable (FIFO)
    - Retry every 5 seconds; replay buffered events in chronological order on reconnect
    - Discard oldest event and log WARNING when buffer full
    - Do NOT dispatch when detection list is empty
    - Implement `start()` and `stop()` lifecycle methods
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.2 Write property tests for ComplianceEventDispatcher
    - **Property 12: Event Buffer Capacity and FIFO Eviction** — generate sequences of N events, verify buffer ≤ 100 and oldest evicted first
    - **Property 13: Buffer Replay Chronological Order** — generate buffered event sets, verify replay in ascending timestamp order
    - **Property 14: No Dispatch on Empty Detections** — generate frames with empty detection lists, verify no event enqueued
    - **Validates: Requirements 6.4, 6.5, 6.6, 6.7**

- [x] 8. Implement PipelineManager
  - [x] 8.1 Implement pipeline orchestration and lifecycle management
    - Create `backend/core/pipeline_manager.py` with `PipelineManager` class
    - Orchestrate the frame capture → inference → extraction → scoring → dispatch loop
    - Manage pipeline lifecycle: start/stop/error state transitions
    - Enforce single-instance (reject double-start/double-stop)
    - Track metrics: frames_processed, current_fps, last_inference_ms, per_class_counts
    - Transition to error state on unrecoverable failures (source permanently unavailable, 3 consecutive inference failures)
    - Log start/stop/error at INFO; inference cycles at DEBUG
    - Log performance warning at WARNING if latency > 500ms for 5 consecutive frames
    - _Requirements: 7.5, 7.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [x] 9. Implement Pipeline API Router
  - [x] 9.1 Create REST API endpoints for pipeline control
    - Create `backend/routers/pipeline.py` with FastAPI APIRouter
    - Implement GET `/api/pipeline/status` — return running state, metrics, error
    - Implement POST `/api/pipeline/start` — accept source_type and source_id, return 200/409/422/503
    - Implement POST `/api/pipeline/stop` — halt pipeline, release resources, return 200/409
    - Implement GET `/api/pipeline/detections` — return latest detection results (empty array if not running)
    - Implement PUT `/api/pipeline/config` — update confidence_threshold, image_size, fps_limit with validation
    - Register router in `backend/app.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11_

  - [ ]* 9.2 Write unit tests for pipeline API endpoints
    - Test all 409 Conflict scenarios (start while running, stop while not running)
    - Test 422 validation errors (invalid source_type, missing source_id, out-of-range config)
    - Test 503 Service Unavailable when source cannot be opened
    - Test valid start/stop/config/status/detections flows
    - Test detections endpoint returns empty array when pipeline not running
    - _Requirements: 7.1–7.11_

- [x] 10. Implement paper material detection and zone classification
  - [x] 10.1 Integrate paper detection into compliance event engine
    - Update compliance event engine (or create integration in `backend/core/rules.py`) to handle "book" detections
    - Implement center-point calculation: center_x = (x1 + x2) / 2, center_y = (y1 + y2) / 2
    - Classify as DOCUMENT_LEFT_ON_DESK when center point is inside configured Desk_Zone boundaries
    - Skip classification and log WARNING when no Desk_Zone is configured
    - Do not classify as violation when center point is outside Desk_Zone
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 10.2 Write property tests for paper material zone classification
    - **Property 15: Center-in-Zone Classification** — generate random bboxes and zones, verify classification iff center is inside zone boundaries
    - **Validates: Requirements 8.3, 8.4**

- [x] 11. Implement JSON serialization and detection result structuring
  - [x] 11.1 Implement DetectionResult serialization and validation
    - Ensure `DetectionResult` objects serialize to JSON with correct structure (label, confidence, bbox dict, class_id)
    - Validate round-trip: serialize → deserialize produces identical values (confidence within 1e-6)
    - Ensure label max length 20, confidence [0.0, 1.0], bbox non-negative integers
    - _Requirements: 5.1, 5.2, 5.4, 5.5_

  - [ ]* 11.2 Write property tests for JSON round-trip
    - **Property 10: JSON Serialization Round-Trip** — generate random DetectionResult objects, verify serialize/deserialize identity with confidence tolerance 1e-6
    - **Validates: Requirements 5.5**

- [x] 12. Implement pipeline config validation
  - [x] 12.1 Implement runtime configuration update validation
    - Ensure PUT `/api/pipeline/config` rejects out-of-range values with descriptive 422 errors
    - Validate confidence_threshold [0.0, 1.0], image_size [320, 1280], fps_limit [1, 30]
    - Apply valid partial updates (only provided fields updated)
    - _Requirements: 7.7, 7.10_

  - [ ]* 12.2 Write property tests for pipeline config validation
    - **Property 16: Pipeline Config Validation Rejects Out-of-Range** — generate random config values, verify rejection iff outside valid ranges with error identifying invalid fields
    - **Validates: Requirements 7.10**

- [x] 13. Checkpoint - Full pipeline integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Wire components together and integration tests
  - [x] 14.1 Wire pipeline into FastAPI application
    - Register pipeline router in `backend/app.py`
    - Initialize `PipelineManager` in FastAPI lifespan with `AppConfig` and db session factory
    - Connect `ComplianceEventDispatcher` to existing compliance event engine
    - Ensure pipeline starts/stops cleanly with application lifecycle
    - Add audit log entries on pipeline start/stop/error events
    - _Requirements: 6.1, 7.1, 9.2, 9.7_

  - [ ]* 14.2 Write integration tests for end-to-end pipeline flow
    - Test frame capture → inference → extraction → scoring → dispatch with mocked YOLO model
    - Test API lifecycle: start → status → detections → config update → stop
    - Test database persistence: incidents via compliance engine, audit logs on start/stop
    - _Requirements: 6.1, 6.2, 7.1–7.8, 9.2_

- [x] 15. Final checkpoint - Complete pipeline verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases using pytest
- All pipeline components use Python type hints and dataclasses per project conventions
- The pipeline integrates with existing `backend/core/rules.py` and `backend/db/` modules
- Test files: `backend/tests/test_pipeline_properties.py` (property tests), `backend/tests/test_pipeline_unit.py` (unit tests), `backend/tests/test_pipeline_integration.py` (integration tests)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "4.2", "5.1"] },
    { "id": 3, "tasks": ["5.2", "7.1"] },
    { "id": 4, "tasks": ["7.2", "8.1"] },
    { "id": 5, "tasks": ["9.1", "10.1", "11.1"] },
    { "id": 6, "tasks": ["9.2", "10.2", "11.2", "12.1"] },
    { "id": 7, "tasks": ["12.2", "14.1"] },
    { "id": 8, "tasks": ["14.2"] }
  ]
}
```
