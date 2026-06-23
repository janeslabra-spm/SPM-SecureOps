# Requirements Document

## Introduction

The AI Detection Pipeline is a structured, end-to-end video processing pipeline built on Python FastAPI that captures webcam or CCTV streams, runs YOLOv8n inference to detect persons, cellphones, and paper materials, and forwards detection results to a compliance event engine. This feature formalizes the existing detection logic into a well-defined pipeline with clear stages: frame acquisition, inference, bounding box extraction, confidence scoring, and event dispatch. It extends the current system to support paper material detection and integrates with the compliance event engine for automated policy enforcement.

## Glossary

- **Detection_Pipeline**: The end-to-end FastAPI service responsible for orchestrating frame capture, inference, result extraction, and event dispatch
- **Frame_Capture_Service**: The component that acquires video frames from webcam or CCTV stream sources via OpenCV
- **Inference_Engine**: The component that runs YOLOv8n model prediction on acquired frames and produces raw detection results
- **Bounding_Box_Extractor**: The component that parses inference results into structured bounding box coordinates with associated class labels
- **Confidence_Scorer**: The component that calculates and filters detection confidence scores against configurable thresholds
- **Compliance_Event_Engine**: The downstream service that receives structured detection events and applies policy rules for incident classification
- **Detection_Result**: A structured object containing label, confidence score, and bounding box coordinates for a single detected object
- **Frame**: A single image captured from a video source, represented as a NumPy array
- **CCTV_Stream**: A network-accessible video stream using RTSP or HTTP protocol
- **Paper_Material**: Physical documents, papers, notebooks, or printed material detected using the YOLO "book" class

## Requirements

### Requirement 1: Frame Capture from Video Sources

**User Story:** As a security operator, I want the pipeline to capture frames from webcam or CCTV streams, so that I can monitor restricted areas in real time.

#### Acceptance Criteria

1. WHEN a webcam source is configured, THE Frame_Capture_Service SHALL open the webcam device at the configured camera index (integer 0–10) using OpenCV VideoCapture and set the frame resolution to the configured width (integer 320–1920) and height (integer 240–1080)
2. WHEN a CCTV stream URL is configured, THE Frame_Capture_Service SHALL accept URLs with scheme "rtsp://" or "http://" and connect to the stream using OpenCV VideoCapture within 10 seconds of initialization
3. WHEN a frame is successfully read from a webcam source, THE Frame_Capture_Service SHALL return the frame as a NumPy array with shape (height, width, 3) in BGR color format where height and width match the configured resolution; WHEN a frame is successfully read from a CCTV stream, THE Frame_Capture_Service SHALL return the frame at the stream's native resolution
4. IF the video source fails to open, THEN THE Frame_Capture_Service SHALL raise a connection error with a message indicating the source type and identifier (camera index or stream URL) that could not be opened
5. IF a frame read operation fails on a CCTV stream, THEN THE Frame_Capture_Service SHALL attempt reconnection up to 3 times with a 2-second interval between attempts, and IF all 3 attempts fail, THEN THE Frame_Capture_Service SHALL report a source-unavailable status and stop capture
6. WHILE the pipeline is active, THE Frame_Capture_Service SHALL capture frames at a rate not exceeding the configured frames-per-second limit (integer, 1–30 FPS)
7. WHEN the pipeline receives a stop signal, THE Frame_Capture_Service SHALL release the video capture resource and terminate the capture thread within 5 seconds
8. IF a frame read operation fails on a webcam source, THEN THE Frame_Capture_Service SHALL report a no-frame-available status and retry on the next capture cycle without raising an error

### Requirement 2: YOLOv8n Inference Execution

**User Story:** As a security operator, I want the pipeline to run object detection on each captured frame, so that persons, cellphones, and paper materials are identified automatically.

#### Acceptance Criteria

1. WHEN a valid frame (a non-null NumPy array with dtype uint8, height > 0, width > 0, and 3 color channels) is received, THE Inference_Engine SHALL run YOLOv8n prediction filtered to the target classes: person (class 0), cell phone (class 67), and book (class 73), using the configured confidence threshold (default 0.40)
2. THE Inference_Engine SHALL load the YOLOv8n model from the configured model path (default "yolov8n.pt") at initialization before processing any frames
3. WHEN inference completes, THE Inference_Engine SHALL return a list of Detection objects each containing: label (string), confidence (float between 0.0 and 1.0), bounding box (x1, y1, x2, y2 as integer pixel coordinates), and class_id (integer)
4. THE Inference_Engine SHALL execute inference using the configured device parameter, accepting the values "auto", "cpu", or a device-specific string (e.g., "cuda", "mps"), where "auto" defers device selection to the Ultralytics library
5. THE Inference_Engine SHALL pass input frames to the model at the configured image size (default 640 pixels, representing the longest-edge resize used by Ultralytics) before inference
6. IF the model file is missing or corrupt at initialization, THEN THE Inference_Engine SHALL raise a RuntimeError with a message specifying the file path that could not be loaded
7. IF inference fails on a frame due to a runtime exception, THEN THE Inference_Engine SHALL log the error including the exception message at ERROR level, return an empty list of Detection objects, and preserve the pipeline running state without crashing

### Requirement 3: Bounding Box Extraction

**User Story:** As a system integrator, I want structured bounding box data extracted from inference results, so that downstream components can process detection locations.

#### Acceptance Criteria

1. WHEN inference results are available, THE Bounding_Box_Extractor SHALL extract bounding box coordinates in (x1, y1, x2, y2) pixel format for each detection and include the corresponding Confidence_Score (float between 0.0 and 1.0) in the output
2. WHEN extracting bounding boxes, THE Bounding_Box_Extractor SHALL map each bounding box to the corresponding class label (person, cell phone, or book)
3. THE Bounding_Box_Extractor SHALL normalize each bounding box by applying the following operations in order: first truncate coordinate values to integers toward zero, then swap coordinates if x1 >= x2 or y1 >= y2 to restore correct order, then clamp all coordinate values to the frame boundaries (0 to frame_width-1 for x values, 0 to frame_height-1 for y values)
4. WHEN no detections are present in the inference results, THE Bounding_Box_Extractor SHALL return an empty list
5. IF a detection in the inference results contains non-finite coordinate values (NaN or infinity), THEN THE Bounding_Box_Extractor SHALL discard that detection from the output and continue processing the remaining detections
6. IF after normalization a bounding box has zero area (x1 equals x2 or y1 equals y2), THEN THE Bounding_Box_Extractor SHALL discard that detection from the output

### Requirement 4: Confidence Score Calculation and Filtering

**User Story:** As a security operator, I want detection results filtered by confidence threshold, so that only reliable detections trigger compliance events.

#### Acceptance Criteria

1. THE Confidence_Scorer SHALL associate each Detection_Result with the confidence score produced by the YOLOv8n model for that detection, represented as a float with at least 4 decimal places of precision
2. WHEN a confidence threshold is configured, THE Confidence_Scorer SHALL exclude detections with confidence scores strictly below the threshold (scores equal to the threshold are retained)
3. THE Confidence_Scorer SHALL accept confidence threshold values between 0.0 and 1.0 inclusive
4. IF a confidence threshold value outside the range 0.0 to 1.0 is provided, THEN THE Confidence_Scorer SHALL reject the value, return an error indication describing the valid range, and apply the default threshold of 0.4
5. WHEN multiple detections of the same class overlap with Intersection over Union greater than or equal to 0.5, THE Confidence_Scorer SHALL retain only the detection with the highest confidence score (Non-Maximum Suppression); IF two overlapping detections of the same class have identical confidence scores, THEN THE Confidence_Scorer SHALL retain the detection with the larger bounding box area
6. IF no confidence threshold has been explicitly configured, THEN THE Confidence_Scorer SHALL apply the default threshold of 0.4

### Requirement 5: Detection Result Structuring

**User Story:** As a system integrator, I want detection results in a consistent structured format, so that they can be consumed by the compliance event engine and API clients.

#### Acceptance Criteria

1. THE Detection_Pipeline SHALL produce each Detection_Result as a structured object containing: label (string, maximum 20 characters), confidence (float in the range 0.0 to 1.0 inclusive), bounding box (a JSON object with keys "x1", "y1", "x2", "y2" each holding a non-negative integer in pixel coordinates where (x1, y1) is the top-left corner and (x2, y2) is the bottom-right corner), and class_id (non-negative integer)
2. WHEN constructing a Detection_Result, THE Detection_Pipeline SHALL use the human-readable label: "person" for class 0, "cell phone" for class 67, and "book" for class 73
3. THE Detection_Pipeline SHALL return detection results as a list ordered by descending confidence score; IF two Detection_Results have identical confidence scores, THEN THE Detection_Pipeline SHALL order them by class_id ascending as a tiebreaker
4. WHEN a frame contains no objects matching the target classes, THE Detection_Pipeline SHALL return an empty list
5. THE Detection_Pipeline SHALL produce Detection_Result objects where serializing to JSON then deserializing back produces a Detection_Result with identical label, class_id, bounding box integer values, and confidence value matching the original to within 1e-6 absolute tolerance

### Requirement 6: Compliance Event Dispatch

**User Story:** As a compliance officer, I want detection results forwarded to the compliance event engine, so that policy violations are automatically classified and recorded.

#### Acceptance Criteria

1. WHEN one or more Detection_Results are produced for a frame, THE Detection_Pipeline SHALL dispatch the detection results to the Compliance_Event_Engine within 100 milliseconds of result production
2. WHEN dispatching to the Compliance_Event_Engine, THE Detection_Pipeline SHALL include: timestamp (ISO 8601 format with timezone), camera identifier (string, maximum 128 characters), frame dimensions (width and height in pixels as integers), and the list of Detection_Results
3. THE Detection_Pipeline SHALL dispatch events asynchronously using a non-blocking queue, ensuring the dispatch operation does not add more than 5 milliseconds of latency to the frame processing loop
4. IF the Compliance_Event_Engine is unavailable (connection refused or timeout exceeding 3 seconds), THEN THE Detection_Pipeline SHALL buffer up to 100 unsent events in a FIFO queue and retry dispatch every 5 seconds until a retry succeeds, where success is defined as receiving a response from the Compliance_Event_Engine within the 3-second timeout
5. IF the event buffer reaches capacity of 100 events, THEN THE Detection_Pipeline SHALL discard the oldest buffered event and log a warning at WARNING level with the discarded event timestamp
6. WHEN a retry dispatch to the Compliance_Event_Engine succeeds after a period of unavailability, THE Detection_Pipeline SHALL dispatch all remaining buffered events in chronological order, stopping replay and resuming normal buffering if a dispatch failure occurs mid-replay, and SHALL log an INFO message indicating the count of successfully replayed events
7. WHEN no Detection_Results are produced for a frame (empty detection list), THE Detection_Pipeline SHALL NOT dispatch an event to the Compliance_Event_Engine for that frame

### Requirement 7: Pipeline API Endpoints

**User Story:** As a frontend developer, I want REST API endpoints to control and query the detection pipeline, so that I can build monitoring dashboards.

#### Acceptance Criteria

1. THE Detection_Pipeline SHALL expose a GET endpoint at /api/pipeline/status that returns a JSON object with: running (boolean), frames_processed (integer), current_fps (float), last_inference_ms (float), and error (string or null)
2. THE Detection_Pipeline SHALL expose a POST endpoint at /api/pipeline/start that accepts a JSON body with source_type ("webcam" or "cctv") and source_id (integer camera index or string URL), returning HTTP 200 with a JSON body containing: running (boolean, true), source_type (string), and source_id (string or integer)
3. THE Detection_Pipeline SHALL expose a POST endpoint at /api/pipeline/stop that halts the detection pipeline and releases video resources, returning HTTP 200 with a JSON body containing: running (boolean, false) and frames_processed (integer, total count at time of stop)
4. THE Detection_Pipeline SHALL expose a GET endpoint at /api/pipeline/detections that returns the most recent Detection_Results for the last processed frame as a JSON array
5. WHEN a start request is received while the pipeline is already running, THE Detection_Pipeline SHALL return HTTP 409 Conflict with a JSON body containing an error message indicating the pipeline is already active
6. WHEN a stop request is received while the pipeline is not running, THE Detection_Pipeline SHALL return HTTP 409 Conflict with a JSON body containing an error message indicating the pipeline is already inactive
7. THE Detection_Pipeline SHALL expose a PUT endpoint at /api/pipeline/config that accepts a JSON body with optional fields: confidence_threshold (float 0.0–1.0), image_size (integer 320–1280), and fps_limit (integer 1–30), returning HTTP 200 with updated configuration
8. WHEN the /api/pipeline/detections endpoint is called while the pipeline is not running, THE Detection_Pipeline SHALL return HTTP 200 with an empty JSON array
9. WHEN the /api/pipeline/start endpoint receives an invalid source_type or missing source_id, THE Detection_Pipeline SHALL return HTTP 422 with a validation error message
10. IF the /api/pipeline/config endpoint receives a value outside its valid range for any field, THE Detection_Pipeline SHALL return HTTP 422 with a JSON body describing which fields failed validation
11. IF the video source cannot be opened during a start request (connection refused, device not found, or stream unreachable), THE Detection_Pipeline SHALL return HTTP 503 Service Unavailable with a JSON body containing an error message describing the source failure

### Requirement 8: Paper Material Detection

**User Story:** As a security operator, I want the pipeline to detect paper materials on desks, so that unauthorized document exposure is flagged as a compliance violation.

#### Acceptance Criteria

1. THE Inference_Engine SHALL include YOLO class 73 (book) in the filtered target classes alongside "person" and "cell phone" for paper material detection
2. WHEN a book class detection is present in a frame, THE Detection_Pipeline SHALL label the detection as "book" to represent paper material and include the Confidence_Score and Bounding_Box in the detection results
3. WHEN a "book" detection is evaluated by the Compliance_Event_Engine and its Bounding_Box center point (calculated as center_x = (x1 + x2) / 2, center_y = (y1 + y2) / 2) is located inside the configured Desk_Zone boundaries, THE Compliance_Event_Engine SHALL classify the detection as a DOCUMENT_LEFT_ON_DESK violation
4. IF a "book" detection's Bounding_Box center point is located outside the configured Desk_Zone, THEN THE Compliance_Event_Engine SHALL not classify it as a violation
5. THE Detection_Pipeline SHALL apply the same configurable confidence threshold (valid range: 0.0 to 1.0, default: 0.4) to paper material detections as to person and cell phone detections
6. IF no Desk_Zone is configured when the Compliance_Event_Engine evaluates a "book" detection, THEN THE Compliance_Event_Engine SHALL skip the DOCUMENT_LEFT_ON_DESK classification for that detection and log a WARNING indicating no Desk_Zone is defined

### Requirement 9: Pipeline Health and Observability

**User Story:** As a DevOps engineer, I want pipeline health metrics and logging, so that I can monitor system performance and diagnose issues in production.

#### Acceptance Criteria

1. THE Detection_Pipeline SHALL log each inference cycle duration in milliseconds at DEBUG level, including the frame sequence number and count of detections produced in that cycle
2. THE Detection_Pipeline SHALL log pipeline start, stop, and error events at INFO level
3. IF inference latency exceeds 500 milliseconds for 5 consecutive frames, THEN THE Detection_Pipeline SHALL log a performance warning at WARNING level and reset the consecutive-frame counter to zero once a subsequent frame completes in 500 milliseconds or less
4. THE Detection_Pipeline SHALL expose the following metrics via the /api/pipeline/status endpoint: current inference latency in milliseconds, total frames processed since pipeline start, and per-class detection counts (person, cell phone, book) for the most recent frame, returning a JSON response within 200 milliseconds
5. WHEN the pipeline encounters an unrecoverable error (video source permanently unavailable after all reconnection attempts exhausted, or model failing to produce inference results on 3 consecutive frames), THEN THE Detection_Pipeline SHALL transition to a stopped state, log the error at ERROR level including the error category and descriptive message, and update the status endpoint to reflect the error condition with the error field populated
6. WHILE the Detection_Pipeline is in a stopped or error state, THE Detection_Pipeline SHALL continue to serve the /api/pipeline/status endpoint with the last known metrics and current pipeline state
7. WHEN the Detection_Pipeline transitions from running to stopped or error state, THE Detection_Pipeline SHALL log an INFO message indicating the total frames processed and the total uptime duration in seconds since the pipeline was last started
