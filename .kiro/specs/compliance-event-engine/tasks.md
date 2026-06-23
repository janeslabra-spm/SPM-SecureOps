# Implementation Plan: Compliance Event Engine

## Overview

Implement the `ComplianceEventEngineImpl` class that receives `DetectionEvent` objects from the `ComplianceEventDispatcher` and orchestrates detection conversion, spatial classification, violation tracking with duration gating, and incident logging. The engine integrates with FastAPI's async lifespan and delegates cooldown suppression to the existing `IncidentLogger`.

All implementation goes in `backend/core/compliance_engine.py`. All tests go in `backend/tests/test_compliance_engine.py`.

## Tasks

- [x] 1. Create ComplianceEngineConfig and ViolationEntry data models
  - [x] 1.1 Create `backend/core/compliance_engine.py` with `ComplianceEngineConfig` frozen dataclass and `ViolationEntry` dataclass
    - Define `ComplianceEngineConfig` with fields: `duration_threshold` (float, default 2.0), `cooldown_seconds` (float, default 10.0), `proximity_pixels` (int, default 80), `screenshots_dir` (Path, default Path("screenshots"))
    - Implement `__post_init__` validation: duration_threshold in (0.0, 300.0], cooldown_seconds in [0.0, 3600.0], proximity_pixels in (0, 2000]
    - Raise `ValueError` with parameter name and violated constraint on invalid values
    - Implement `from_app_config` classmethod that derives config from an `AppConfig` instance
    - Define `ViolationEntry` with `first_seen: float` and `last_candidate: IncidentCandidate`
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.7_

  - [ ]* 1.2 Write property test for configuration validation (Property 12)
    - **Property 12: Configuration Validation**
    - **Validates: Requirements 13.2, 13.3, 13.4, 13.5**
    - Use Hypothesis to generate random (duration_threshold, cooldown_seconds, proximity_pixels) tuples
    - Assert construction succeeds iff all values are in valid ranges
    - Assert ValueError message contains the name of the invalid parameter

- [x] 2. Implement detection result conversion
  - [x] 2.1 Implement `convert_detection_result` pure function in `backend/core/compliance_engine.py`
    - Accept a `DetectionResult` and return `Detection | None`
    - Validate: bbox dict has keys x1, y1, x2, y2; confidence in [0.0, 1.0]; label ≤ 20 characters
    - Round each bbox coordinate to nearest integer using `decimal.ROUND_HALF_UP` rounding
    - Return `None` for invalid results; return `Detection` dataclass for valid results
    - Implement `convert_all_detections(detections: list[DetectionResult]) -> list[Detection]` helper that filters None results
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.2 Write property test for detection conversion round-trip (Property 1)
    - **Property 1: Detection Conversion Round-Trip**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.6**
    - Generate valid DetectionResult objects with float/int bbox values
    - Assert converted Detection bbox tuple matches half-up rounded integers
    - Assert confidence is exactly preserved

  - [ ]* 2.3 Write property test for invalid detection filtering (Property 2)
    - **Property 2: Invalid DetectionResult Filtering**
    - **Validates: Requirements 2.4**
    - Generate mixed lists of valid and invalid DetectionResult objects
    - Assert output length equals count of valid items in input

- [x] 3. Implement violation tracker logic
  - [x] 3.1 Implement `_update_violation_tracker` method on `ComplianceEventEngineImpl`
    - Accept camera_id and list of IncidentCandidate objects
    - Upsert entries: for new (camera_id, incident_type) pairs, record `time.monotonic()` as first_seen
    - For existing pairs, retain original first_seen timestamp, update last_candidate
    - Deduplicate: multiple candidates of same incident_type for same camera_id → single entry with earliest first_seen
    - Prune: remove entries for incident_types no longer present for this camera_id
    - Return list of ViolationEntry objects that exceed the duration threshold
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_

  - [ ]* 3.2 Write property test for violation tracker timestamp invariant (Property 4)
    - **Property 4: Violation Tracker Timestamp Invariant**
    - **Validates: Requirements 4.1, 4.2**
    - Generate sequences of events containing the same (camera_id, incident_type)
    - Assert first_seen timestamp is set on first occurrence and never modified on subsequent calls

  - [ ]* 3.3 Write property test for violation tracker pruning (Property 5)
    - **Property 5: Violation Tracker Pruning**
    - **Validates: Requirements 4.3, 8.2, 8.3**
    - Generate random prior tracker state and random current classification results
    - Assert post-update tracked types for a camera exactly equal the current result types

  - [ ]* 3.4 Write property test for camera independence (Property 6)
    - **Property 6: Camera Independence**
    - **Validates: Requirements 4.4**
    - Generate two distinct camera_ids and random mutations for one
    - Assert the other camera's tracker entries remain unchanged

  - [ ]* 3.5 Write property test for same-type deduplication (Property 7)
    - **Property 7: Same-Type Deduplication Within Single Event**
    - **Validates: Requirements 4.5**
    - Generate events with multiple IncidentCandidates of same incident_type
    - Assert exactly one tracking entry per (camera_id, incident_type) with earliest first_seen

  - [ ]* 3.6 Write property test for duration threshold gate (Property 8)
    - **Property 8: Duration Threshold Gate**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - Generate random (first_seen, current_time, threshold) triples
    - Assert gate allows logging iff (current_time - first_seen) >= threshold

  - [ ]* 3.7 Write property test for first-seen reset after logging (Property 9)
    - **Property 9: First-Seen Reset After Logging**
    - **Validates: Requirements 5.4**
    - Assert that after a violation passes the gate and is forwarded, first_seen is reset to current time

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement ComplianceEventEngineImpl class
  - [x] 5.1 Implement constructor and lifecycle methods (`__init__`, `start`, `stop`, `refresh_desk_zone`)
    - Constructor accepts `session_factory`, `screenshots_dir` (str | Path, max 260 chars), and `config` (AppConfig | ComplianceEngineConfig)
    - If config is AppConfig, derive ComplianceEngineConfig via `from_app_config`
    - Create screenshots directory (including parents) if it doesn't exist
    - Validate screenshots_dir parent exists or can be created; raise ValueError otherwise
    - `start()`: initialize violation tracker as empty dict, load desk zone from DB (cache it), handle DB failure gracefully (zone = None, log WARNING)
    - `stop()`: wait up to 5 seconds for in-progress process_event, then clear tracker state
    - `refresh_desk_zone()`: re-read desk zone from DB, update cache; retain previous on failure; raise TimeoutError if query exceeds 5 seconds
    - Use `asyncio.Lock` to protect concurrent access to shared state
    - _Requirements: 1.3, 1.4, 9.1, 9.2, 9.3, 9.4, 10.1, 10.2, 10.3, 10.4, 13.6_

  - [x] 5.2 Implement `process_event` method — main event processing pipeline
    - Validate event: if detections list is empty, log DEBUG and return early
    - Validate frame dimensions: if width or height ≤ 0, log WARNING and return early
    - Convert DetectionResults to Detection objects via `convert_all_detections`
    - Load cached desk zone; convert percentage to pixel coords via `table_zone_from_percent` if zone exists for camera_id
    - Invoke `classify_incidents` with converted detections, zone, and proximity_pixels
    - If no candidates returned, clear all tracker entries for this camera_id and return
    - Update violation tracker; prune expired entries
    - For each violation exceeding duration threshold: invoke `IncidentLogger.try_log_incident` independently with candidate, frame (numpy array from event or placeholder), camera_id, and camera_id as location
    - Reset first_seen for logged violations
    - Handle exceptions per candidate independently (log ERROR, continue to next)
    - Wrap entire method in top-level try/except: log ERROR with timestamp, camera_id, exception class; return without re-raising
    - Ensure protocol compliance: method signature matches `ComplianceEventEngine` protocol
    - _Requirements: 1.1, 1.2, 1.5, 2.1, 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 8.1, 8.2, 8.3, 11.1, 11.2, 11.3, 12.1, 12.2, 12.3, 12.4_

  - [ ]* 5.3 Write property test for independent candidate processing (Property 10)
    - **Property 10: Independent Candidate Processing**
    - **Validates: Requirements 6.5**
    - Generate N ≥ 2 candidates with random failures injected via mock
    - Assert try_log_incident is called for each candidate regardless of prior failures

  - [ ]* 5.4 Write property test for state preservation on pre-tracking failure (Property 11)
    - **Property 11: State Preservation on Pre-Tracking Failure**
    - **Validates: Requirements 12.3**
    - Inject exceptions before tracker updates are applied
    - Assert violation tracker dict is unchanged from pre-event state

- [x] 6. Implement zone loading and conversion integration
  - [x] 6.1 Implement desk zone loading from database in `ComplianceEventEngineImpl`
    - Query desk zone for the camera_id from the database using existing `backend/db/desk_zone.py` helpers
    - Cache the result as percentage-based coordinates
    - Convert to pixel coordinates using `table_zone_from_percent(frame_width, frame_height, ...)` at event processing time
    - Pass `None` to classify_incidents when no zone is configured for the camera
    - _Requirements: 3.2, 3.3, 10.1, 10.2, 10.3_

  - [ ]* 6.2 Write property test for zone percentage-to-pixel conversion (Property 3)
    - **Property 3: Zone Percentage-to-Pixel Conversion**
    - **Validates: Requirements 3.3**
    - Generate random positive frame dimensions (1–4000) and zone percentages (0–100)
    - Assert engine produces pixel coordinates identical to `table_zone_from_percent` output

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Wire engine into FastAPI lifespan and integration testing
  - [x] 8.1 Register `ComplianceEventEngineImpl` in FastAPI lifespan in `backend/app.py`
    - Instantiate engine with session factory, screenshots_dir from config, and AppConfig
    - Call `engine.start()` during lifespan startup
    - Call `engine.stop()` during lifespan shutdown
    - Pass engine instance to `ComplianceEventDispatcher` constructor
    - _Requirements: 1.1, 9.1, 9.2_

  - [ ]* 8.2 Write integration tests for end-to-end event processing flow
    - Test: DetectionEvent → conversion → classification → tracking → logging with mocked DB
    - Test: empty event early return (Req 8.1)
    - Test: start() with DB failure initializes zone=None (Req 9.4)
    - Test: stop() graceful shutdown with concurrent event (Req 9.3)
    - Test: refresh_desk_zone updates cache and handles failure (Req 10.1, 10.3)
    - Test: IncidentLogger None return continues without error (Req 6.3)
    - Test: AppConfig → ComplianceEngineConfig derivation (Req 13.7)
    - _Requirements: 1.1, 6.3, 8.1, 9.1, 9.3, 9.4, 10.1, 10.3, 13.7_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit/integration tests validate specific examples and edge cases
- All implementation uses Python 3.12 with async/await, type hints, and dataclasses
- The engine file is `backend/core/compliance_engine.py`; tests are in `backend/tests/test_compliance_engine.py`
- Uses `hypothesis` library (already in requirements.txt) with `@settings(max_examples=100)`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["5.2", "6.1"] },
    { "id": 6, "tasks": ["5.3", "5.4", "6.2"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["8.2"] }
  ]
}
```
