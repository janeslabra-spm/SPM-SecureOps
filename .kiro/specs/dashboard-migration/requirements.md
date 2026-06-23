# Requirements Document

## Introduction

This document specifies the requirements for migrating the CellphoneMonitoring frontend from the current React 18 / Vite 5 / Tailwind CSS stack to the SPM SecureOps Monitoring Dashboard design. The new frontend adopts Next.js 16 with React 19, shadcn/ui (Radix-based components), and pnpm as the package manager. It implements an 8-view compliance monitoring dashboard connected to the existing FastAPI backend, adding Amazon Bedrock AI assistant integration, AWS service health monitoring, and a structured compliance review workflow.

## Glossary

- **Dashboard_Frontend**: The new Next.js 16 frontend application replacing the current Vite-based React SPA
- **Shell**: The top-level layout component containing the Sidebar, Topbar, and main content area with client-side view switching
- **Sidebar**: The collapsible navigation panel providing access to all 8 views
- **Topbar**: The persistent top bar displaying real-time clock, monitored area, monitoring status indicator, active user count, AWS status pill, notification bell, and user avatar
- **Compliance_Event**: A detection event record containing id, title, detail, timestamp, priority, status, type, reviewer, notes, and zone fields
- **Review_Priority**: An event priority classification with values "Needs Review", "High Review Priority", or "Informational"
- **Event_Status**: A compliance event lifecycle state with values "Pending Review", "Confirmed", "False Positive", "Warning Issued", "Coaching Required", "Escalated", or "Resolved"
- **Backend_API**: The existing FastAPI application providing REST endpoints for incidents, stream, zones, audit, health, and pipeline control
- **AI_Assistant**: The Amazon Bedrock-powered advisory panel providing compliance summaries and risk analysis
- **Glass_Card**: A UI component using glass-morphism styling (backdrop blur, semi-transparent background, subtle border)
- **Monitoring_Zone**: A configurable rectangular area within the camera frame used for detection classification
- **View_Key**: A client-side navigation state identifier for one of the 8 dashboard views: dashboard, live, events, review, analytics, aws, status, settings

## Requirements

### Requirement 1: Project Scaffolding and Build System

**User Story:** As a developer, I want the new frontend to use Next.js 16 with React 19 and pnpm, so that the application uses the target framework and package manager.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL use Next.js 16 as the application framework with React 19 as the UI library
2. THE Dashboard_Frontend SHALL use pnpm as the package manager for dependency installation and script execution
3. THE Dashboard_Frontend SHALL use TypeScript in strict mode for all `.ts` and `.tsx` source files within the application directories, excluding configuration files at the project root
4. THE Dashboard_Frontend SHALL use Tailwind CSS v4 with the @tailwindcss/postcss plugin for styling
5. THE Dashboard_Frontend SHALL include shadcn/ui as the component library providing Avatar, Badge, Button, Card, Chart, DropdownMenu, Input, Progress, ScrollArea, Select, Separator, Table, Tabs, and Tooltip components
6. THE Dashboard_Frontend SHALL include Lucide React for iconography and Recharts for data visualization
7. WHEN a developer runs `pnpm build`, THE Dashboard_Frontend SHALL complete the production build without type errors or compilation failures

### Requirement 2: Application Shell and Navigation

**User Story:** As a compliance operator, I want a persistent shell with sidebar navigation and a status topbar, so that I can navigate between views and see system status at a glance.

#### Acceptance Criteria

1. THE Shell SHALL render the Sidebar, Topbar, and a main content area in a flex layout that fills 100% of the viewport height
2. THE Sidebar SHALL display navigation items for all 8 views: Dashboard, Live Monitoring, Compliance Events, Compliance Review, Analytics, AWS Services, System Status, and Settings
3. THE Sidebar SHALL indicate the currently active view by applying a visually distinct background and a primary-colored icon to the active navigation item, differentiable from inactive items without relying on color alone
4. THE Sidebar SHALL support a collapsed mode (showing icons only, width no greater than 80px) and an expanded mode (showing icons and text labels, width between 200px and 260px), toggled by a collapse button positioned at the bottom of the sidebar
5. WHEN the user clicks a navigation item, THE Shell SHALL render the selected view in the main content area using client-side state without a full page reload
6. WHEN the Shell loads with the root URL path, THE Shell SHALL display the Dashboard view as the default
7. THE Topbar SHALL display a real-time clock in HH:MM:SS format updated every 1 second, the current monitored area name, a "Monitoring Active" status indicator with a repeating pulse animation, an AWS connection status indicator, a notification bell icon, and a user avatar
8. WHILE the Sidebar is in collapsed mode, THE Sidebar SHALL display a tooltip containing the navigation item label when the user hovers over a navigation icon, with the tooltip appearing within 300 milliseconds of hover

### Requirement 3: Dashboard Overview View

**User Story:** As a compliance operator, I want a dashboard overview combining status cards, live monitoring preview, event feed, AI assistant, compliance score, and AWS service health, so that I can assess overall system state from one screen.

#### Acceptance Criteria

1. WHEN the "Dashboard" view is active, THE Shell SHALL display status cards, a live monitoring preview, an event feed, an AI assistant panel, a compliance score widget, AWS service cards, and a data governance section
2. THE Dashboard_Frontend SHALL render status cards showing counts for total events today (all incidents logged since 00:00:00 server local time), pending reviews (incidents with status "Pending Review"), confirmed violations (incidents with status "Confirmed"), and false positives (incidents with status "False Alarm"), each displaying an integer value between 0 and 99,999
3. THE Dashboard_Frontend SHALL display status cards using a glass-morphism card style defined as: a background with opacity between 0.05 and 0.15, a backdrop blur of 8px to 16px, a 1px solid border with opacity between 0.1 and 0.2, and rounded corners of at least 12px
4. THE Dashboard_Frontend SHALL arrange the dashboard in a responsive grid where at viewport widths of 1280px and above the layout uses a 2-column area for live monitoring and supporting widgets alongside a 1-column sidebar for the event feed, and at viewport widths below 1280px the layout stacks all sections into a single column
5. THE Dashboard_Frontend SHALL poll the data source for status card counts and event feed entries at an interval of no more than 10 seconds, updating displayed values within 1 second of receiving a response
6. IF the Dashboard_Frontend fails to load data for any widget on initial render or during a polling cycle, THEN THE Dashboard_Frontend SHALL display an inline loading indicator or error state within that widget area without affecting the rendering of other widgets

### Requirement 4: Live Monitoring View

**User Story:** As a compliance operator, I want to see the live camera feed with AI detection overlays, so that I can observe real-time compliance monitoring activity.

#### Acceptance Criteria

1. WHEN the "Live Monitoring" view is active on a viewport width of 1280px or greater, THE Shell SHALL display the live camera feed in a 2-column area with the detection event feed in a 1-column sidebar
2. THE Dashboard_Frontend SHALL render the MJPEG stream from the Backend_API endpoint GET /stream/video.mjpg in an img element
3. IF the Backend_API stream endpoint GET /stream/video.mjpg returns a 503 status, THEN THE Dashboard_Frontend SHALL display a "Monitoring is not active" placeholder with reduced opacity and hide the scan line overlay
4. THE Dashboard_Frontend SHALL render an animated scan line overlay on the live feed container to indicate active monitoring
5. THE Dashboard_Frontend SHALL poll the GET /stream/status endpoint every 2 seconds and display detection metrics including people count, phone count, and inference time in milliseconds
6. IF the Backend_API GET /stream/status endpoint returns a non-200 response, THEN THE Dashboard_Frontend SHALL display an error indicator in the metrics panel and retain the last successfully received metric values

### Requirement 5: Compliance Events View

**User Story:** As a compliance operator, I want to see incoming compliance events with status cards and an AI advisory panel, so that I can triage new events efficiently.

#### Acceptance Criteria

1. WHEN the "Compliance Events" view is activated, THE Shell SHALL display a 2-column grid layout with the left column (approximately 2/3 width) containing status cards and an event feed, and the right column (approximately 1/3 width) containing the AI assistant panel
2. WHEN the "Compliance Events" view is activated, THE Dashboard_Frontend SHALL fetch up to 100 compliance events from the Backend_API endpoint GET /incidents, sorted by timestamp descending, and map each incident record to the Compliance_Event display model
3. THE Dashboard_Frontend SHALL display each event in the event feed showing its id, detail (the incident_type formatted with underscores replaced by spaces), timestamp (formatted as locale date-time string), priority badge, status badge, and zone (the camera_name value)
4. THE Dashboard_Frontend SHALL derive the priority badge from the incident confidence value: "High Review Priority" (red) when confidence is greater than or equal to 0.85, "Needs Review" (amber) when confidence is greater than or equal to 0.50 and less than 0.85, and "Informational" (blue) when confidence is less than 0.50
5. THE Dashboard_Frontend SHALL color-code status badges using semantic tokens: yellow for "Pending Review", green for "Confirmed", and gray for "False Alarm"
6. IF the GET /incidents request fails or returns a non-2xx response, THEN THE Dashboard_Frontend SHALL display an error message indicating the events could not be loaded, and SHALL provide a retry mechanism allowing the operator to re-fetch without navigating away
7. WHEN the AI assistant panel is displayed, THE Dashboard_Frontend SHALL show an advisory area that presents contextual guidance relevant to the currently visible compliance events, rendered as a read-only text panel within the right column of the grid

### Requirement 6: Compliance Review View

**User Story:** As a compliance supervisor, I want a searchable and filterable table of events with workflow actions, so that I can review, assign, and resolve compliance events.

#### Acceptance Criteria

1. WHEN the "Compliance Review" view is active, THE Shell SHALL display a data table with all compliance events supporting search, priority filtering, and status filtering
2. THE Dashboard_Frontend SHALL provide a text search input that performs case-insensitive substring matching on event id, detail, zone, or reviewer fields, filtering the table rows in real-time as the user types
3. THE Dashboard_Frontend SHALL provide dropdown selects for filtering by Review_Priority and Event_Status
4. THE Dashboard_Frontend SHALL display table columns for Event ID, Detail, Zone, Priority, Status, Reviewer, and Actions
5. WHEN the user clicks "Assign Reviewer" on an event, THE Dashboard_Frontend SHALL present a reviewer selection and call the Backend_API to update the event
6. WHEN the user clicks "Mark Confirmed", "Mark False Positive", or "Escalate" on an event, THE Dashboard_Frontend SHALL call PATCH /incidents/{incident_id}/status with the corresponding status value and update the row's status badge immediately upon a successful response
7. THE Dashboard_Frontend SHALL provide a CSV export button that triggers a download from the Backend_API endpoint GET /incidents/export with current filter parameters applied

### Requirement 7: Analytics View

**User Story:** As a compliance manager, I want visual analytics showing event trends and distribution, so that I can identify patterns and measure compliance performance.

#### Acceptance Criteria

1. WHEN the "Analytics" view is active, THE Shell SHALL display a bar chart of daily events, a pie chart of event categories, and a line chart of weekly review trends
2. THE Dashboard_Frontend SHALL render the bar chart using Recharts showing events per day for the current calendar week (Monday through Sunday)
3. THE Dashboard_Frontend SHALL render the pie chart using Recharts showing distribution across Mobile Device Detection, Printed Material Detection, and False Positive Event categories for the past 7 days
4. THE Dashboard_Frontend SHALL render the line chart using Recharts showing total reviews (all events that transitioned out of "Pending Review") and confirmed counts (events marked "Confirmed") over the past 7 days
5. THE Dashboard_Frontend SHALL display a compliance score widget showing the percentage of reviewed incidents out of total incidents in the past 7 days, and an AI assistant panel below the charts
6. IF the analytics data endpoints return empty data sets, THEN THE Dashboard_Frontend SHALL display an empty state message within each chart panel indicating no data is available for the selected period

### Requirement 8: AWS Services View

**User Story:** As a system administrator, I want to see AWS service health, system component status, and data governance controls, so that I can monitor infrastructure health.

#### Acceptance Criteria

1. WHEN the "AWS Services" view is active, THE Shell SHALL display AWS service health cards, a system status panel showing component health indicators, and a data governance section
2. WHEN the "AWS Services" view is active, THE Dashboard_Frontend SHALL display service cards for EC2, S3, Amazon Bedrock, and CloudWatch, where each card shows the service name, role description, region identifier, and an uptime percentage value between 0% and 100%
3. THE Dashboard_Frontend SHALL display each AWS service card with the Glass_Card style and a status indicator showing either "Operational" with a green visual cue or "Degraded" with an amber visual cue
4. WHEN the "AWS Services" view becomes active, THE Dashboard_Frontend SHALL fetch system health data from the Backend_API endpoint GET /health and map the response fields to component health indicators: "status" field mapped to overall system health, "database" field (boolean) mapped to Database showing "Online" or "Offline", "detection_engine_active" field (boolean) mapped to AI Engine showing "Online" or "Offline", and "uptime_seconds" field mapped to a server uptime display
5. WHILE the "AWS Services" view is active, THE Dashboard_Frontend SHALL re-fetch data from the GET /health endpoint every 30 seconds to refresh the system status panel indicators

### Requirement 9: System Status View

**User Story:** As a system administrator, I want a component health view with progress bars, so that I can quickly identify degraded subsystems.

#### Acceptance Criteria

1. WHEN the "System Status" view is active, THE Shell SHALL display status cards and component health progress bars for each of the six monitored components: Camera, AI Engine, Backend, Database, AWS, and Retention
2. THE Dashboard_Frontend SHALL display health progress bars representing a value from 0% to 100% for Camera, AI Engine, Backend, Database, AWS, and Retention components
3. THE Dashboard_Frontend SHALL color each progress bar green when the component health value is above 90%, amber when the value is between 70% and 90% inclusive, and red when the value is below 70%
4. THE Dashboard_Frontend SHALL derive Camera health as 100% when the GET /stream/status endpoint returns HTTP 200, and 0% when it returns HTTP 503 or fails to respond within 5 seconds
5. THE Dashboard_Frontend SHALL derive AI Engine health as 100% when the GET /stream/status endpoint returns HTTP 200 and the fps field is greater than 0, and 0% otherwise
6. THE Dashboard_Frontend SHALL derive Backend health as 100% when the GET /health endpoint returns HTTP 200, and 0% when it fails to respond within 5 seconds
7. THE Dashboard_Frontend SHALL derive Database health as 100% when the GET /health endpoint returns HTTP 200 and the database field is true, and 0% when the database field is false or the endpoint is unreachable
8. IF the GET /stream/status or GET /health endpoint is unreachable or returns an error, THEN THE Dashboard_Frontend SHALL display the affected component's progress bar at 0% colored red and show a label indicating the component is unreachable
9. THE Dashboard_Frontend SHALL poll the GET /health and GET /stream/status endpoints every 30 seconds to refresh the component health values

### Requirement 10: Settings View

**User Story:** As a compliance operator, I want to configure monitored area boundaries, monitoring preferences, and view governance controls, so that I can adjust system behavior.

#### Acceptance Criteria

1. WHEN the "Settings" view is active, THE Shell SHALL display a monitored area configuration section, a monitoring preferences section with toggles, and a data governance section showing retention period, auto-delete status, and compliance standard
2. WHEN the Settings view loads, THE Dashboard_Frontend SHALL call GET /zones/desk on the Backend_API and display editable integer percentage fields for x1, y1, x2, and y2, each accepting values from 0 to 100 inclusive
3. WHEN the user saves zone configuration, THE Dashboard_Frontend SHALL call PUT /zones/desk with the updated values and display a visible success confirmation message for at least 3 seconds
4. IF the Backend_API returns a 422 validation error on zone save, THEN THE Dashboard_Frontend SHALL display the validation error message to the user in place of the success confirmation
5. WHEN the Settings view is active, THE Dashboard_Frontend SHALL display toggles for Auto Detection enable/disable and Alert Notifications enable/disable, persisting each toggle state in local browser storage
6. IF the Backend_API is unreachable when saving zone configuration, THEN THE Dashboard_Frontend SHALL display an error message indicating the network failure and retain the user's unsaved field values

### Requirement 11: AI Compliance Assistant Integration

**User Story:** As a compliance operator, I want an AI-powered advisory panel providing event summaries and risk analysis, so that I can make informed review decisions.

#### Acceptance Criteria

1. THE AI_Assistant panel SHALL display a compliance summary generated from the most recent compliance events, including a count of active violations by type, a risk assessment level (Low, Medium, High, Critical), and a plain-language explanation of detected patterns
2. THE Dashboard_Frontend SHALL send compliance event context to a backend proxy endpoint at POST /api/ai/summary, and the backend proxy SHALL forward the request to Amazon Bedrock and return the generated advisory text within 15 seconds
3. WHEN new compliance events arrive, THE AI_Assistant SHALL request an updated summary no more frequently than once every 30 seconds (debounced), discarding intermediate event arrivals within that window
4. WHILE the AI_Assistant is awaiting a response from the backend proxy, THE AI_Assistant SHALL display a loading indicator with a skeleton placeholder in the panel area
5. IF the backend proxy does not return a response within 15 seconds or returns an HTTP error status (4xx or 5xx), THEN THE AI_Assistant SHALL display an error state message indicating the advisory service is temporarily unavailable and SHALL offer a manual retry button
6. THE Dashboard_Frontend SHALL render AI_Assistant responses in a scrollable card with a maximum height of 400 pixels, displaying markdown-formatted text truncated to 2000 characters with a visual indicator if the response was truncated
7. WHEN the operator navigates away from the current view and returns, THE AI_Assistant SHALL display the last successfully received summary until a new summary is requested

### Requirement 12: Dark Theme and Design System

**User Story:** As a compliance operator, I want a dark-themed interface with consistent semantic colors and glass-morphism styling, so that the dashboard is comfortable for extended monitoring sessions.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL implement a dark theme as the default color scheme using CSS custom properties for all color tokens, with a background color in the range of hsl(220-240, 10-20%, 8-14%) and foreground text color providing at least 4.5:1 contrast ratio
2. THE Dashboard_Frontend SHALL define semantic color tokens for success (hsl green in the 120-160 hue range), warning (hsl amber in the 35-50 hue range), danger (hsl red in the 0-10 hue range), and info (hsl blue in the 200-230 hue range), used consistently across status indicators and badges
3. THE Dashboard_Frontend SHALL implement the Glass_Card utility class providing backdrop-filter blur of 8px to 16px, a background with alpha between 0.03 and 0.12, and a 1px solid border with alpha between 0.08 and 0.20 on card components
4. THE Dashboard_Frontend SHALL implement pulse dot animations using CSS keyframes with a repeating scale or opacity animation cycle of 1.5 to 2.5 seconds for live status indicators and the "Monitoring Active" topbar indicator
5. THE Dashboard_Frontend SHALL use the shadcn/ui design tokens and component variants as the foundation for all interactive elements, with consistent border-radius, focus rings, and transition durations matching the shadcn defaults

### Requirement 13: Backend API Integration Layer

**User Story:** As a developer, I want a typed API client layer mapping backend endpoints to frontend data models, so that all views consume consistent, type-safe data.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL provide a typed API client module using Axios that exports typed functions for each Backend_API endpoint, where each function specifies request parameters and return types as TypeScript interfaces
2. THE Dashboard_Frontend SHALL map the GET /incidents response to the Compliance_Event TypeScript type, translating the backend field `incident_type` to a frontend `eventType` field and the backend `status` field (values: "Pending Review", "Confirmed", "False Alarm") to a typed Event_Status union type
3. THE Dashboard_Frontend SHALL map the GET /health response to a typed HealthStatus interface containing fields: status (union of "healthy" | "degraded" | "unhealthy"), database (boolean), detection_engine_active (boolean), and uptime_seconds (number)
4. THE Dashboard_Frontend SHALL map the GET /stream/status response to a typed StreamMetrics interface containing fields: people (number), phones (number), active_rule_matches (number), logged_this_frame (number), inference_ms (number), fps (number), and message (string)
5. IF the Backend_API returns a network error or the request exceeds a 10-second timeout, THEN THE Dashboard_Frontend SHALL display a connection error indicator in the Topbar and render affected views with their last successfully fetched data or an empty state placeholder if no prior data exists
6. THE Dashboard_Frontend SHALL configure the API base URL through an environment variable NEXT_PUBLIC_API_URL, defaulting to http://localhost:8000 when the variable is not set
7. IF the Backend_API returns an HTTP 503 status on the GET /stream/status endpoint, THEN THE Dashboard_Frontend SHALL indicate that monitoring is inactive in the stream-dependent views rather than displaying an error

### Requirement 14: Data Governance Display

**User Story:** As a compliance officer, I want to see active data governance controls listed in the dashboard, so that I can verify compliance policies are enforced.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL display a data governance section containing exactly 9 governance control badges, each rendered as a distinct, visible badge element with a text label
2. THE Dashboard_Frontend SHALL display the following governance control labels: "Human Review Required", "No Facial Recognition", "No Biometric Identification", "No Continuous Video Recording", "Only Event Evidence Stored", "Local Processing Supported", "Automatic 7 Day Evidence Retention", "Authorized Access Required", and "Audit Logging Enabled"
3. THE Dashboard_Frontend SHALL render all governance control badges within a single Glass_Card container that uses a flex-wrap layout, allowing badges to flow onto additional rows when the container width is insufficient to display all badges in a single row
4. THE Dashboard_Frontend SHALL display all 9 governance control badges as always-visible static indicators without requiring data from the Backend_API, representing the system's built-in privacy-by-design policies

### Requirement 15: Responsive Layout and Accessibility

**User Story:** As a compliance operator, I want the dashboard to work on different screen sizes and be keyboard accessible, so that I can use it on various devices and with assistive technologies.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL implement responsive grid layouts that collapse from multi-column to single-column when the viewport width is narrower than 1280px, where multi-column layouts include the status cards row (4 columns to 2 columns at 640px, to 1 column below 640px) and the main content area (2-column to 1-column below 1280px)
2. IF the viewport width is narrower than 768px, THEN THE Sidebar SHALL be hidden by default and a menu toggle button with an aria-label of "Open navigation menu" SHALL be displayed in the Topbar
3. THE Dashboard_Frontend SHALL support sequential keyboard navigation via the Tab key for all interactive elements in the following order: sidebar navigation items, topbar action buttons, then page content in DOM order, with a visible focus indicator (minimum 2px outline with at least 3:1 contrast ratio against adjacent colors) on the currently focused element
4. THE Dashboard_Frontend SHALL provide ARIA labels on all icon-only buttons (including notification bell, menu toggle, and camera status actions), aria-label attributes on status indicators describing their current state, and aria-live="polite" annotations on the event feed and stream status regions that update without page reload
5. THE Dashboard_Frontend SHALL maintain a minimum touch target size of 44x44 CSS pixels for all interactive elements when the viewport width is 1024px or narrower
6. WHEN the menu toggle button in the Topbar is activated via click or keyboard (Enter or Space key), THE Sidebar SHALL toggle between visible and hidden states, and the toggle button aria-expanded attribute SHALL reflect the current visibility state
