# Requirements Document

## Introduction

The Compliance Event Engine is the downstream processing component that receives `DetectionEvent` objects from the `ComplianceEventDispatcher`. It orchestrates the full compliance workflow: converting raw detection results into typed `Detection` objects for the rules engine, classifying incidents via spatial logic, tracking active violations for duration-based gating, and persisting confirmed incidents through the `IncidentLogger`. The engine integrates with the existing async architecture (FastAPI lifespan, async SQLAlchemy) and runs as a long-lived async service.

## Glossary

- **Compliance_Event_Engine**: The async service that implements the `ComplianceEventEngine` protocol, receiving `DetectionEvent` objects and orchestrating classification, violation tracking, and incident logging.
- **Detection_Event**: An immutable payload containing a timestamp (ISO 8601), camera_id, frame dimensions, and a list of `DetectionResult` objects dispatched from the pipeline.
- **Detection_Result**: A single object detection with label, confidence, bounding box (dict with x1/y1/x2/y2 keys), and class_id.
- **Rules_Engine**: The `classify_incidents` function in `rules.py` that applies spatial logic to produce `IncidentCandidate` objects from a list of `Detection` objects.
- **Incident_Candidate**: A classified potential violation with incident_type, confidence, phone_bbox, and optional person_bbox.
- **Incident_Logger**: The component that applies duration threshold gating, cooldown suppression, and screenshot capture before persisting confirmed incidents.
- **Violation_Tracker**: Internal state within the Compliance_Event_Engine that tracks active violations per camera and incident type for duration-based gating.
- **Desk_Zone**: A rectangular region (stored as percentages in the database) representing the restricted desk area used for zone-based classification.
- **Duration_Threshold**: The minimum time (in seconds) a violation must persist continuously before it qualifies as a confirmed incident.
- **Cooldown_Window**: The time period after logging an incident during which duplicate incidents of the same type are suppressed.
- **Detection**: A normalized detection object with label, confidence, integer pixel bbox tuple, and class_id — the input format expected by the Rules_Engine.

## Requirements

### Requirement 1: Protocol Compliance

**User Story:** As a system architect, I want the Compliance Event Engine to implement the established protocol interface, so that it integrates seamlessly with the existing ComplianceEventDispatcher.

#### Acceptance Criteria

1. THE Compliance_Event_Engine SHALL implement the `ComplianceEventEngine` protocol by providing an async `process_event` method that accepts a Detection_Event parameter and returns None.
2. WHEN the ComplianceEventDispatcher calls `process_event`, THE Compliance_Event_Engine SHALL accept the Detection_Event without blocking the caller beyond 3 seconds.
3. THE Compliance_Event_Engine SHALL be instantiable with a database session factory (an async callable returning an AsyncSession), a screenshot directory path (a string of at most 260 characters), and an AppConfig instance.
4. IF the screenshot directory path provided at instantiation does not exist on the filesystem, THEN THE Compliance_Event_Engine SHALL create the directory (including parent directories) before completing initialization.
5. IF `process_event` encounters an internal processing failure, THEN THE Compliance_Event_Engine SHALL raise an exception to the caller within the 3-second timeout window, allowing the ComplianceEventDispatcher to buffer the event for retry.

### Requirement 2: Detection Result Conversion

**User Story:** As a detection pipeline developer, I want the engine to convert DetectionResult objects into Detection objects, so that the existing rules engine can classify them.

#### Acceptance Criteria

1. WHEN a DetectionEvent is received, THE Compliance_Event_Engine SHALL convert each DetectionResult in the event's detections list into a Detection object by mapping label to label, confidence to confidence, class_id to class_id, and bbox dict keys (x1, y1, x2, y2) to a bbox tuple of (x1, y1, x2, y2) as integers.
2. IF a DetectionResult has bbox values that are not integers, THEN THE Compliance_Event_Engine SHALL round each coordinate to the nearest integer using half-up rounding (e.g., 2.5 rounds to 3) during conversion.
3. THE Compliance_Event_Engine SHALL preserve the confidence value from DetectionResult to Detection without modification, maintaining the original float value in the range 0.0 to 1.0.
4. IF a DetectionResult in the event's detections list fails validation (missing bbox keys x1, y1, x2, or y2, or confidence outside range 0.0 to 1.0, or label exceeding 20 characters), THEN THE Compliance_Event_Engine SHALL skip that DetectionResult and continue converting the remaining items in the list.
5. WHEN a DetectionEvent is received with an empty detections list, THE Compliance_Event_Engine SHALL produce an empty list of Detection objects and pass it to the rules engine without error.
6. FOR each successfully converted Detection, converting it back to dict form with bbox keys (x1, y1, x2, y2) SHALL produce coordinate values equal to the rounded integer values from the original DetectionResult (round-trip equivalence).

### Requirement 3: Rules Engine Classification

**User Story:** As a compliance officer, I want the engine to apply spatial classification rules to each detection event, so that potential violations are identified automatically.

#### Acceptance Criteria

1. WHEN a Detection_Event contains one or more detections, THE Compliance_Event_Engine SHALL convert each DetectionResult into a Detection object (mapping the bbox dict keys x1, y1, x2, y2 to an integer tuple) and invoke the Rules_Engine `classify_incidents` function with the converted Detection list, the current Desk_Zone (as pixel coordinates or None), and the configured proximity_pixels value.
2. IF no Desk_Zone is configured in the database for the camera identified by the Detection_Event camera_id, THEN THE Compliance_Event_Engine SHALL pass `None` as the table_zone parameter to the Rules_Engine.
3. IF a Desk_Zone is configured for the camera, THEN THE Compliance_Event_Engine SHALL convert the percentage-based zone coordinates (x1_percent, y1_percent, x2_percent, y2_percent) to pixel coordinates by calling `table_zone_from_percent` with the frame_width and frame_height from the Detection_Event.
4. THE Compliance_Event_Engine SHALL use the `proximity_pixels` value from its configuration when invoking the Rules_Engine.
5. IF the Detection_Event frame_width or frame_height is less than or equal to zero, THEN THE Compliance_Event_Engine SHALL skip rules classification for that event and log a warning.

### Requirement 4: Violation Tracking

**User Story:** As a compliance officer, I want the engine to track how long each violation persists, so that transient false detections are filtered out before logging.

#### Acceptance Criteria

1. WHEN the Rules_Engine returns one or more Incident_Candidate objects, THE Violation_Tracker SHALL record a first-seen timestamp (using time.monotonic()) for each new violation keyed by the combination of camera_id and incident_type that does not already exist in the tracking state.
2. WHILE a violation of the same camera_id and incident_type is present in the Rules_Engine output on each consecutive invocation of `process_event`, THE Violation_Tracker SHALL retain the original first-seen timestamp without resetting it.
3. WHEN a previously tracked violation is no longer present in the Rules_Engine output for a given camera_id, THE Violation_Tracker SHALL immediately remove the first-seen record for that camera_id and incident_type combination, so that a subsequent reappearance starts a new tracking period from zero elapsed time.
4. THE Violation_Tracker SHALL maintain independent tracking state per camera_id, so violations on one camera do not affect tracking on another camera.
5. WHEN multiple Incident_Candidate objects of the same incident_type are returned for the same camera_id within a single event, THE Violation_Tracker SHALL track them as a single violation entry for that camera_id and incident_type combination, retaining the earliest first-seen timestamp already recorded.

### Requirement 5: Duration Threshold Gating

**User Story:** As a system operator, I want the engine to only log incidents after a violation persists beyond a configurable duration, so that brief false positives are suppressed.

#### Acceptance Criteria

1. WHEN an Incident_Candidate has been tracked continuously (present in consecutive events for the same camera_id and incident_type) for at least the configured Duration_Threshold seconds, THE Compliance_Event_Engine SHALL forward the candidate to the Incident_Logger for persistence exactly once per continuous violation period.
2. WHEN an Incident_Candidate has been tracked for less than the configured Duration_Threshold seconds, THE Compliance_Event_Engine SHALL suppress logging and continue tracking without invoking the Incident_Logger.
3. THE Compliance_Event_Engine SHALL use the `duration_threshold` value from its configuration, defaulting to 2.0 seconds, and SHALL compute elapsed duration as the difference between the current monotonic timestamp and the first-seen monotonic timestamp for that violation.
4. WHEN the Compliance_Event_Engine has forwarded a violation to the Incident_Logger, THE Compliance_Event_Engine SHALL reset the first-seen timestamp for that camera_id and incident_type combination so that subsequent continuous detections begin a new threshold period.

### Requirement 6: Incident Logging Integration

**User Story:** As a compliance officer, I want confirmed violations to be persisted with evidence, so that I can review incidents after the fact.

#### Acceptance Criteria

1. WHEN the Compliance_Event_Engine processes an Incident_Candidate from its rule evaluation, THE Compliance_Event_Engine SHALL invoke the Incident_Logger's `try_log_incident` method with the Incident_Candidate, the current video frame as a numpy array for screenshot capture, the camera_id from the Detection_Event as camera_name, and the camera_id string used directly as the location parameter.
2. WHEN the Incident_Logger returns an integer incident_id (greater than 0), THE Compliance_Event_Engine SHALL log the successful persistence at INFO level including the incident_type and incident_id.
3. WHEN the Incident_Logger returns None (indicating either cooldown suppression or duration threshold not yet met), THE Compliance_Event_Engine SHALL continue processing the next candidate without error and without logging at ERROR or WARNING level.
4. IF the Incident_Logger raises an exception during `try_log_incident`, THEN THE Compliance_Event_Engine SHALL log the error at ERROR level including the incident_type and exception message, and SHALL continue processing remaining Incident_Candidates in the current evaluation batch without halting.
5. WHEN the Compliance_Event_Engine has multiple Incident_Candidates from a single Detection_Event, THE Compliance_Event_Engine SHALL invoke `try_log_incident` for each candidate independently, so that a failure or suppression for one candidate does not prevent processing of subsequent candidates.

### Requirement 7: Cooldown Suppression Delegation

**User Story:** As a system operator, I want duplicate incident suppression handled consistently, so that the same violation is not logged repeatedly within a short window.

#### Acceptance Criteria

1. THE Compliance_Event_Engine SHALL delegate cooldown suppression logic entirely to the Incident_Logger by not maintaining any cooldown timestamps, suppression counters, or duplicate-detection state of its own.
2. THE Compliance_Event_Engine SHALL pass the configured `cooldown_seconds` value from its configuration when constructing the Incident_Logger's IncidentConfig.
3. WHEN the Incident_Logger receives a candidate incident whose `incident_type` matches a previously logged incident, AND the elapsed time since that incident_type was last logged is less than `cooldown_seconds`, THEN THE Incident_Logger SHALL suppress the duplicate by returning None and not persisting a database record.
4. WHEN the Incident_Logger receives a candidate incident whose `incident_type` has not been logged before, OR the elapsed time since that incident_type was last logged is greater than or equal to `cooldown_seconds`, THEN THE Incident_Logger SHALL allow the incident to proceed through the logging pipeline.

### Requirement 8: Empty Event Handling

**User Story:** As a pipeline developer, I want the engine to handle edge cases gracefully, so that empty or minimal events do not cause errors.

#### Acceptance Criteria

1. WHEN a Detection_Event contains an empty detections list, THE Compliance_Event_Engine SHALL return without invoking the Rules_Engine or Incident_Logger and SHALL log the early return at DEBUG level including the camera_id and timestamp.
2. WHEN a Detection_Event contains detections but the Rules_Engine returns zero Incident_Candidate objects, THE Compliance_Event_Engine SHALL remove all violation tracking entries for the Detection_Event's camera_id and return without invoking the Incident_Logger.
3. WHEN a Detection_Event contains detections and the Rules_Engine returns Incident_Candidate objects that do not include a previously tracked violation type for that camera_id, THE Compliance_Event_Engine SHALL remove the tracking entry for that specific camera_id and incident_type combination while retaining tracking entries for violations still present.

### Requirement 9: Async Lifecycle Management

**User Story:** As a backend developer, I want the engine to integrate with FastAPI's async lifespan, so that resources are properly initialized and cleaned up.

#### Acceptance Criteria

1. THE Compliance_Event_Engine SHALL provide an async `start` method that initializes the Violation_Tracker as an empty dict and loads the current Desk_Zone configuration from the database, caching it for use during event processing.
2. THE Compliance_Event_Engine SHALL provide an async `stop` method that clears all violation tracking state and releases held resources.
3. WHEN `stop` is called, THE Compliance_Event_Engine SHALL wait up to 5 seconds for any in-progress `process_event` invocation to complete before clearing state.
4. IF the database is unavailable when `start` is called, THEN THE Compliance_Event_Engine SHALL initialize with Desk_Zone set to None and log the failure at WARNING level, allowing the engine to operate without zone-based classification until a successful `refresh_desk_zone` call.

### Requirement 10: Desk Zone Refresh

**User Story:** As a system operator, I want the engine to pick up desk zone changes without requiring a restart, so that zone configuration updates take effect promptly.

#### Acceptance Criteria

1. THE Compliance_Event_Engine SHALL provide an async `refresh_desk_zone` method that re-reads the Desk_Zone configuration from the database and updates the cached value.
2. WHEN the `refresh_desk_zone` method is called, THE Compliance_Event_Engine SHALL use the updated Desk_Zone for all subsequent event processing within 1 second of the refresh completing.
3. IF the database query for Desk_Zone fails during refresh, THEN THE Compliance_Event_Engine SHALL retain the previously cached value and log the error at WARNING level including the exception message.
4. THE `refresh_desk_zone` method SHALL complete within 5 seconds; if the database query exceeds this timeout, the method SHALL raise a TimeoutError after logging at WARNING level.

### Requirement 11: Event Processing Idempotency

**User Story:** As a pipeline developer, I want the engine to handle duplicate events safely, so that replayed buffered events do not produce duplicate incidents.

#### Acceptance Criteria

1. WHEN the same Detection_Event (identical timestamp, camera_id, and detections) is processed multiple times (replay scenario from the ComplianceEventDispatcher buffer), THE Compliance_Event_Engine SHALL rely on the Incident_Logger's cooldown suppression to prevent duplicate incident records.
2. THE Compliance_Event_Engine SHALL process each event based solely on its content and the current violation tracking state, without maintaining a history of previously processed event timestamps.
3. WHEN replayed events arrive within the cooldown window of a previously logged incident of the same type, THE Incident_Logger SHALL return None for those candidates, and THE Compliance_Event_Engine SHALL treat that as normal suppression without logging an error.

### Requirement 12: Error Resilience

**User Story:** As a system operator, I want the engine to remain operational when individual event processing fails, so that one bad event does not halt the monitoring system.

#### Acceptance Criteria

1. IF an unhandled exception occurs during `process_event`, THEN THE Compliance_Event_Engine SHALL log the exception at ERROR level with the event timestamp, camera_id, and exception class name, and return without re-raising the exception.
2. IF the database is temporarily unavailable during incident logging, THEN THE Compliance_Event_Engine SHALL log the error at ERROR level including the exception message, and continue processing subsequent events without halting.
3. THE Compliance_Event_Engine SHALL maintain valid internal state (violation tracking dict unchanged from its pre-event state) when individual event processing encounters an unrecoverable error before violation tracking updates are applied.
4. IF an exception occurs after violation tracking has been partially updated within a single `process_event` call, THEN THE Compliance_Event_Engine SHALL retain the partial updates (committed tracking changes are not rolled back) and log the partial-processing state at WARNING level.

### Requirement 13: Configuration

**User Story:** As a system operator, I want the engine's behavior to be configurable, so that thresholds can be tuned per deployment.

#### Acceptance Criteria

1. THE Compliance_Event_Engine SHALL accept configuration for: duration_threshold (float, default 2.0), cooldown_seconds (float, default 10.0), proximity_pixels (int, default 80), and screenshots_dir (Path).
2. THE Compliance_Event_Engine SHALL validate that duration_threshold is greater than 0.0 and less than or equal to 300.0.
3. THE Compliance_Event_Engine SHALL validate that cooldown_seconds is greater than or equal to 0.0 and less than or equal to 3600.0.
4. THE Compliance_Event_Engine SHALL validate that proximity_pixels is greater than 0 and less than or equal to 2000.
5. IF any configuration value is invalid, THEN THE Compliance_Event_Engine SHALL raise a ValueError at construction time with a message that identifies the invalid parameter name and states the violated constraint.
6. IF screenshots_dir is provided, THEN THE Compliance_Event_Engine SHALL validate that the parent directory of screenshots_dir exists or can be created, and SHALL raise a ValueError at construction time if the parent directory does not exist and cannot be created.
7. THE Compliance_Event_Engine SHALL support construction either from an explicit ComplianceEngineConfig dataclass or by deriving values from an existing AppConfig instance.
