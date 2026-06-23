# Requirements Document

## Introduction

Computer vision security monitoring system for detecting information security policy violations in a restricted production workspace. The system uses CCTV/webcam feeds with YOLO object detection to identify prohibited items (cellphones, documents left on desks), automatically logs incidents with evidence screenshots, and enforces a 7-day data retention policy. This is a hackathon MVP focused on proving end-to-end detection, logging, and data lifecycle.

## Glossary

- **Detection_Engine**: The YOLO-based object detection component that processes video frames and returns labeled bounding boxes with confidence scores
- **Rule_Engine**: The component that evaluates spatial relationships between detected objects and configured zones to classify security violations
- **Incident_Logger**: The component responsible for persisting incident records and evidence screenshots to the database
- **Retention_Service**: The component that enforces data lifecycle policies by deleting expired incident records and associated screenshots
- **Dashboard**: The React TypeScript Security Operations Command Center (SOC) frontend application built with React, TypeScript, and Tailwind CSS that provides comprehensive monitoring, incident review, and system health visualization
- **API_Server**: The FastAPI backend that serves detection results, incident data, live video streams, and WebSocket connections to the Dashboard
- **WebSocket_Server**: The WebSocket endpoint hosted by the API_Server that pushes real-time incident events to connected Dashboard clients
- **Desk_Zone**: A configurable rectangular region within the camera frame representing the restricted desk area
- **Bounding_Box**: A rectangle defined by coordinates (x1, y1, x2, y2) that encloses a detected object in a video frame
- **Incident**: A confirmed security policy violation that has been persisted with metadata and evidence
- **Confidence_Score**: A float value between 0.0 and 1.0 representing the detection model's certainty about an identified object
- **SOC_Dashboard**: The Security Operations Command Center interface providing dark-themed, data-dense monitoring views with real-time status cards, live feed, detection feed, and analytics
- **Detection_Feed**: The real-time scrolling list of detection events displayed in the Dashboard right panel, showing timestamps, incident types, and confidence scores
- **Status_Card**: A compact UI card in the Dashboard top bar displaying a single operational metric such as camera count, active violations, model accuracy, or retention policy

## Requirements

### Requirement 1: Object Detection from Video Feed

**User Story:** As a security operator, I want the system to detect people, cellphones, and paper documents in a live camera feed, so that potential policy violations can be identified in real time.

#### Acceptance Criteria

1. WHEN a video frame is received from the camera source, THE Detection_Engine SHALL process the frame and return a list of detected objects, where each object includes a label, a Confidence_Score, and a Bounding_Box defined as (x1, y1, x2, y2) pixel coordinates
2. THE Detection_Engine SHALL detect objects with the labels "person", "cell phone", and "paper document"
3. IF a detected object has a Confidence_Score below the configured threshold (valid range: 0.10 to 0.95, default: 0.40), THEN THE Detection_Engine SHALL exclude that object from the returned results
4. THE Detection_Engine SHALL process each frame and return results within 500ms, measured from frame input to detection output on the deployment machine running the YOLOv8n model
5. WHEN the camera source becomes unavailable, THE Detection_Engine SHALL report the connection failure to the API_Server with an error message that includes the source identifier and the reason for the failure
6. WHEN a video frame contains no objects matching the target labels above the configured confidence threshold, THE Detection_Engine SHALL return an empty list of detections

### Requirement 2: Security Violation Classification

**User Story:** As a security operator, I want the system to automatically classify detected objects into specific violation types based on spatial rules, so that I receive actionable alerts rather than raw detections.

#### Acceptance Criteria

1. WHEN a "cell phone" Bounding_Box center point is located inside the configured Desk_Zone, THE Rule_Engine SHALL classify the detection as a PHONE_ON_TABLE violation and include the Confidence_Score and phone Bounding_Box in the violation result
2. WHEN a "cell phone" Bounding_Box overlaps with a "person" Bounding_Box, or WHEN the edge-to-edge distance between a "cell phone" Bounding_Box center and the nearest "person" Bounding_Box is less than or equal to the configured proximity threshold (default: 80 pixels), THE Rule_Engine SHALL classify the detection as a PHONE_NEAR_PERSON violation
3. WHEN a "paper document" Bounding_Box center point is located inside the configured Desk_Zone, THE Rule_Engine SHALL classify the detection as a DOCUMENT_LEFT_ON_DESK violation
4. WHEN a "cell phone" detection satisfies both the PHONE_ON_TABLE and PHONE_NEAR_PERSON rules simultaneously, THE Rule_Engine SHALL prioritize and report only the PHONE_NEAR_PERSON violation
5. WHEN no detected objects satisfy any violation rule, THE Rule_Engine SHALL return an empty list of violations
6. WHEN multiple "cell phone" objects are detected in a single frame, THE Rule_Engine SHALL evaluate each phone independently against all violation rules and return a separate violation entry for each phone that satisfies a rule

### Requirement 3: Incident Logging with Evidence

**User Story:** As a security operator, I want each confirmed violation to be logged with a timestamp, violation type, confidence level, and an evidence screenshot, so that incidents can be reviewed and audited later.

#### Acceptance Criteria

1. WHEN the Rule_Engine confirms a violation that has persisted for longer than the configured duration threshold (configurable between 0.5 and 10.0 seconds, default 2.0 seconds), THE Incident_Logger SHALL create a new incident record in the database within 2 seconds of confirmation
2. THE Incident_Logger SHALL store the following fields for each incident: incident_id (auto-generated unique integer), timestamp (ISO 8601 format "YYYY-MM-DD HH:MM:SS"), incident_type, confidence (decimal value between 0.0 and 1.0), camera_name, location, screenshot_path, status, and notes
3. WHEN an incident is logged, THE Incident_Logger SHALL capture the current annotated video frame as a JPEG screenshot and store it in the configured screenshots directory with a filename containing the timestamp (to millisecond precision) and the incident type to ensure uniqueness
4. IF an incident of the same type has been logged within the configured cooldown period (configurable between 1 and 60 seconds, default 10 seconds), THEN THE Incident_Logger SHALL suppress duplicate logging and discard the candidate until the cooldown expires
5. THE Incident_Logger SHALL assign the default status "Pending Review" to each new incident record
6. IF the screenshot file cannot be written to the configured directory, THEN THE Incident_Logger SHALL still create the incident record in the database with the screenshot_path field set to an empty value and an error indication stored in the notes field

### Requirement 4: Data Retention and Auto-Deletion

**User Story:** As a data compliance officer, I want incident records and screenshots older than 7 days to be automatically deleted, so that the system complies with data minimization policies.

#### Acceptance Criteria

1. THE Retention_Service SHALL delete incident records from the database where the timestamp is older than 7 days (168 hours) from the current server time
2. WHEN an incident record is deleted, THE Retention_Service SHALL also delete the associated screenshot file from the filesystem
3. THE Retention_Service SHALL execute the retention cleanup at least once every 24 hours
4. IF a screenshot file referenced by an incident record does not exist on the filesystem, THEN THE Retention_Service SHALL delete the incident record without raising an error
5. IF a screenshot file cannot be deleted due to a filesystem error, THEN THE Retention_Service SHALL log the failure with the file path and continue processing remaining records without stopping the cleanup execution
6. THE Retention_Service SHALL log the count of deleted records and the count of deleted files after each cleanup execution, including when both counts are zero
7. WHEN the retention cleanup executes, THE Retention_Service SHALL delete any screenshot files in the configured screenshots directory that are not referenced by any existing incident record and are older than 7 days based on file modification time

### Requirement 5: Live Video Streaming and System Status API

**User Story:** As a frontend developer, I want the backend to serve the annotated live video feed, detection status, camera status, system health, and WebSocket connections over HTTP, so that the SOC_Dashboard can display comprehensive monitoring views.

#### Acceptance Criteria

1. THE API_Server SHALL expose an MJPEG stream endpoint that delivers annotated JPEG frames using the `multipart/x-mixed-replace` content type with a `frame` boundary delimiter
2. THE API_Server SHALL expose a status endpoint that returns a JSON object containing the fields: people count (integer), phone count (integer), active rule match count (integer), logged-this-frame count (integer), inference latency in milliseconds (number), and frames per second (number)
3. WHEN a client connects to the MJPEG stream endpoint, THE API_Server SHALL continuously send annotated frames at the configured UI frame rate (default 2 fps, configurable between 1–6 fps) until the client disconnects or the monitoring worker stops
4. THE API_Server SHALL overlay Bounding_Boxes with confidence scores, object labels (person, cell phone), violation-type text indicators on flagged objects, and the Desk_Zone boundary rectangle on each streamed frame
5. IF no camera source is active or the monitoring worker is not running, THEN THE API_Server SHALL return an HTTP 503 Service Unavailable error response with a JSON body containing a message indicating the unavailability reason
6. THE API_Server SHALL include `Cache-Control: no-cache` headers on both the MJPEG stream and status endpoint responses to prevent stale data delivery to the Dashboard
7. THE API_Server SHALL expose a GET /api/cameras endpoint that returns a JSON array of camera objects, each containing the camera name (string) and status (string: "online" or "offline")
8. THE API_Server SHALL expose a GET /api/status endpoint that returns a JSON object containing the fields: ai_engine (string: "online" or "offline"), database (string: "connected" or "disconnected"), and websocket (string: "active" or "inactive")
9. THE API_Server SHALL expose a WebSocket endpoint at the path /ws/incidents that accepts client connections and maintains a persistent bidirectional channel for pushing real-time incident events
10. IF the monitoring worker is not active when the status endpoint is called, THEN THE API_Server SHALL return a status response with all count fields set to zero and the fps field set to zero

### Requirement 6: Incident Management API

**User Story:** As a security operator, I want to view, filter, and update the status of logged incidents through the Dashboard, so that I can review and triage violations.

#### Acceptance Criteria

1. THE API_Server SHALL expose an endpoint that returns incident records filtered by date range, incident type, and review status, returning a maximum of 100 records per response
2. WHEN an incident status update request is received with a valid incident_id and new status value, THE API_Server SHALL update the incident record in the database and return the updated record
3. IF an incident status update request contains a status value other than "Pending Review", "Confirmed", or "False Alarm", THEN THE API_Server SHALL reject the request with an error response indicating the invalid status value
4. THE API_Server SHALL return incident records sorted by timestamp in descending order
5. THE API_Server SHALL expose an endpoint to export filtered incident records as a CSV file containing the columns: incident_id, timestamp, incident_type, confidence, camera_name, location, status, and notes
6. IF an incident status update request references an incident_id that does not exist in the database, THEN THE API_Server SHALL return an error response indicating that the incident was not found

### Requirement 7: Security Operations Command Center Dashboard

**User Story:** As a security operator, I want a professional dark-themed Security Operations Command Center (SOC) dashboard with live CCTV feeds, real-time detection alerts, system health indicators, and analytics, so that I can monitor the entire security posture from a single screen.

#### Acceptance Criteria

1. THE Dashboard SHALL be built with React, TypeScript, and Tailwind CSS using a dark mode design language with a dark gray/black background (slate-900 or darker) and neon green (#00FF88) accent highlights for active states, alerts, and key indicators
2. THE Dashboard SHALL display a persistent left sidebar navigation containing the following menu items: Camera, Dashboard, Live Monitoring, Incident Review, Audit Logs, Security Policies, and Settings
3. THE Dashboard SHALL display a top status bar containing four Status_Cards: "Cameras Online" (showing count of online cameras), "Active Violations" (showing count of unresolved incidents), "Model Status" (showing detection accuracy percentage based on the average Confidence_Score of inferences received within the last 60 seconds), and "Data Retention Policy" (showing the configured retention period in days)
4. THE Dashboard SHALL display a main center panel containing the live MJPEG camera feed rendered at a large size (minimum 60% of the viewport width), with Bounding_Box overlays and Desk_Zone boundaries visible on the video feed
5. THE Dashboard SHALL display a right-side panel containing the Detection_Feed, which shows a scrolling list of the most recent 50 detection events where each entry includes a timestamp, incident type, and Confidence_Score, ordered by most recent first, discarding the oldest entry when the limit is exceeded
6. THE Dashboard SHALL display an analytics section below the main camera panel containing an "Incidents Per Hour" line or bar chart rendered using the Recharts library, showing incident counts aggregated by hour for the current day
7. THE Dashboard SHALL provide an Incident Review page displaying a paginated data table with columns: time, incident type, confidence, and status, where each row represents a logged incident, displaying a maximum of 20 rows per page with navigation controls to move between pages
8. THE Dashboard SHALL provide filter controls on the Incident Review page for filtering incidents by date range, incident type, and review status, where all active filters are combined using AND logic so that only records matching every active filter are displayed
9. THE Dashboard SHALL display a Data Governance footer section showing three indicators: "Retention Policy" (displaying "7 Days" as the configured period), "Auto Delete" (displaying "Enabled" status), and "ISO 27001" (displaying a compliance indicator badge)
10. THE Dashboard SHALL display a System Status panel showing health indicators for three backend services: "Backend" (API_Server health), "Database" (PostgreSQL connection state), and "AI Engine" (Detection_Engine active state), where each indicator shows "Online" or "Offline" with a corresponding green or red visual indicator
11. THE Dashboard SHALL poll the GET /api/status endpoint every 10 seconds to refresh the System Status panel indicators
12. IF the MJPEG video feed fails to deliver a frame within 10 seconds of the last received frame or fails to load on initial connection within 10 seconds, THEN THE Dashboard SHALL display an error message indicating the feed is disconnected in place of the video area, styled consistently with the dark theme
13. WHEN a new incident event is received via WebSocket, THE Dashboard SHALL append the event to the Detection_Feed panel within 1 second of receipt and display an alert banner notification that remains visible for at least 5 seconds or until the operator dismisses the notification

### Requirement 8: Backend Architecture (FastAPI Migration)

**User Story:** As a developer, I want the backend to be a FastAPI application serving REST endpoints and the MJPEG stream, so that the system uses a production-grade API framework decoupled from the frontend.

#### Acceptance Criteria

1. THE API_Server SHALL be implemented using the FastAPI framework with Python, replacing the existing Streamlit application
2. THE API_Server SHALL serve all detection, incident, and streaming functionality through REST endpoints documented via auto-generated OpenAPI specification accessible at the /docs path
3. THE API_Server SHALL use PostgreSQL as the primary database for incident storage
4. THE API_Server SHALL support configurable CORS allowed origins to permit the React TypeScript Dashboard to communicate from a separate origin during development
5. WHEN the API_Server starts, THE API_Server SHALL initialize the database schema, begin the Detection_Engine processing loop as a background task, and begin the Retention_Service background task
6. IF the API_Server cannot connect to the PostgreSQL database during startup, THEN THE API_Server SHALL terminate with exit code 1 and log an error message indicating the connection failure
7. THE API_Server SHALL expose a health-check endpoint that returns the server status, database connectivity state, and Detection_Engine active state, responding within 500ms

### Requirement 9: Desk Zone Configuration

**User Story:** As a security operator, I want to configure the restricted desk zone boundaries, so that the system can correctly determine which objects are inside the monitored area.

#### Acceptance Criteria

1. THE API_Server SHALL accept Desk_Zone configuration as four integer percentage values (x1_percent, y1_percent, x2_percent, y2_percent) each within the range 0 to 100 inclusive, relative to the frame dimensions
2. WHEN a Desk_Zone configuration is provided, THE Rule_Engine SHALL convert the percentage values to pixel coordinates based on the frame dimensions at the time of each detection frame, normalizing coordinates such that the top-left corner is (min(x1, x2), min(y1, y2)) and the bottom-right corner is (max(x1, x2), max(y1, y2))
3. THE API_Server SHALL persist the Desk_Zone configuration before confirming acceptance to the caller, so that it survives application restarts
4. WHEN no Desk_Zone configuration has been set, THE API_Server SHALL use default values of x1=20%, y1=35%, x2=80%, y2=75%
5. IF any provided percentage value is outside the range 0 to 100 inclusive, THEN THE API_Server SHALL reject the configuration request and return an error message indicating the invalid value and the acceptable range of 0 to 100

### Requirement 10: WebSocket Real-Time Incident Alerts

**User Story:** As a security operator, I want to receive instant push notifications of new incidents via WebSocket, so that the Dashboard updates in real time without polling delays.

#### Acceptance Criteria

1. THE WebSocket_Server SHALL accept client connections at the endpoint ws://localhost:8000/ws/incidents and maintain an open connection for each connected Dashboard client, supporting at least 10 simultaneous client connections
2. WHEN the Incident_Logger successfully persists a new incident record, THE WebSocket_Server SHALL broadcast an event message to all connected clients within 1 second of persistence, containing the fields: incident_id, timestamp, incident_type, confidence, camera_name, and status
3. THE WebSocket_Server SHALL serialize each incident event as a JSON object with a "type" field set to "new_incident" and a "data" field containing the incident details specified in criterion 2
4. IF a WebSocket client disconnects unexpectedly or a send to a specific client fails, THEN THE WebSocket_Server SHALL remove that client from the active connections list and continue broadcasting to remaining connected clients without interruption
5. WHEN the Dashboard receives a WebSocket incident event, THE Dashboard SHALL append the incident to the Detection_Feed panel, increment the "Active Violations" Status_Card count, and display an AlertBanner notification showing the incident type and confidence that remains visible for at least 5 seconds or until the operator dismisses it
6. IF the WebSocket connection is lost, THEN THE Dashboard SHALL attempt to reconnect every 5 seconds indefinitely and display a "Connection Lost" indicator in the System Status panel until reconnection succeeds
7. IF no clients are connected when the Incident_Logger persists a new incident record, THEN THE WebSocket_Server SHALL discard the event message without queuing or raising an error

### Requirement 11: Frontend Page Architecture and Component Structure

**User Story:** As a frontend developer, I want the Dashboard to follow a structured page and component architecture using React Router, so that the codebase is organized and maintainable for the SOC Dashboard features.

#### Acceptance Criteria

1. THE Dashboard SHALL organize pages into the following route-mapped files within a `pages/` directory: dashboard.tsx mapped to the route path "/dashboard" (main SOC overview), incidents.tsx mapped to "/incidents" (Incident Review page), cameras.tsx mapped to "/cameras" (camera management view), audit.tsx mapped to "/audit" (audit logs view), and settings.tsx mapped to "/settings" (system settings view)
2. THE Dashboard SHALL implement the following reusable components within a `components/` directory: Sidebar (persistent navigation visible on all pages), CameraPanel (live MJPEG feed with bounding box overlay), IncidentCard (single incident display with incident type, confidence score, and timestamp), DetectionFeed (scrolling real-time event list displaying a maximum of 50 entries), AnalyticsGraph (Recharts-based incidents-per-hour chart), SecurityStatus (system health indicators panel), and AlertBanner (dismissible notification banner for new incidents that can be closed by user click)
3. THE Dashboard SHALL implement a services layer within a `services/` directory containing: api.ts (HTTP client using Axios for all REST API calls to the API_Server) and websocket.ts (WebSocket connection manager handling connect, reconnect with 5-second retry interval, and JSON message parsing for the /ws/incidents endpoint)
4. THE Dashboard SHALL implement a `hooks/` directory containing custom React hooks for shared stateful logic including a hook for WebSocket subscription management that exposes connection state and incoming messages, and a hook for periodic polling that accepts an interval parameter in milliseconds
5. THE Dashboard SHALL use React Router for client-side navigation between pages, where the Sidebar menu items link to their corresponding page routes, and the root path "/" redirects to "/dashboard"
6. IF a user navigates to a route path that does not match any defined page route, THEN THE Dashboard SHALL render a fallback page indicating the requested page was not found, with a navigation link back to "/dashboard"
7. THE Dashboard SHALL use Tailwind CSS utility classes for all styling, applying the dark mode SOC color scheme (slate-900 or darker backgrounds with neon green accent highlights) consistently across all pages and components without any component-specific CSS files
