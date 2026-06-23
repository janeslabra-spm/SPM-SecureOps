# Implementation Plan: Dashboard Migration

## Overview

Migrate the CellphoneMonitoring frontend from React 18 / Vite 5 / react-router-dom to Next.js 16 / React 19 with shadcn/ui, pnpm, and an 8-view compliance monitoring dashboard. The migration is a full rewrite of the `frontend/` directory, implementing client-side view switching within a single-page Shell layout consuming the existing FastAPI backend unchanged.

## Tasks

- [x] 1. Scaffold Next.js 16 project with pnpm and core dependencies
  - [x] 1.1 Initialize Next.js 16 project with pnpm and TypeScript strict mode
    - Remove existing `frontend/` contents and initialize a new Next.js 16 project using pnpm
    - Configure `tsconfig.json` with strict mode enabled
    - Configure `next.config.ts` for the project
    - Set up `postcss.config.mjs` with `@tailwindcss/postcss` plugin
    - Create `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Install and configure shadcn/ui, Lucide React, Recharts, and Axios
    - Install shadcn/ui and generate components: Avatar, Badge, Button, Card, Chart, DropdownMenu, Input, Progress, ScrollArea, Select, Separator, Table, Tabs, Tooltip
    - Install Lucide React for icons, Recharts for charts, and Axios for HTTP
    - Verify `pnpm build` completes without errors
    - _Requirements: 1.5, 1.6, 1.7_

  - [x] 1.3 Set up dark theme CSS custom properties and glass-morphism utilities
    - Create `app/globals.css` with dark theme tokens (background hsl 220-240, 10-20%, 8-14%)
    - Define semantic color tokens: success (green 120-160), warning (amber 35-50), danger (red 0-10), info (blue 200-230)
    - Implement `.glass-card` utility class with backdrop-filter blur 8-16px, background alpha 0.03-0.12, border alpha 0.08-0.20
    - Implement pulse dot keyframe animation (1.5-2.5s cycle) for status indicators
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 1.4 Set up Vitest, testing-library, fast-check, and msw for testing
    - Install vitest, @testing-library/react, @testing-library/jest-dom, jsdom, fast-check, and msw
    - Create `vitest.config.ts` and `setup-tests.ts` with jsdom environment
    - Create test directory structure: `__tests__/properties/`, `__tests__/unit/`, `__tests__/integration/`
    - _Requirements: 1.7_

- [x] 2. Implement TypeScript types, API client, and custom hooks
  - [x] 2.1 Create TypeScript interfaces and constants
    - Create `lib/types.ts` with all interfaces: ComplianceEvent, ReviewPriority, EventStatus, HealthStatus, StreamMetrics, DeskZoneConfig, AiSummaryRequest, AiSummaryResponse, IncidentQueryParams, AwsServiceCard
    - Create `lib/constants.ts` with ViewKey type/enum, polling intervals, and theme tokens
    - Create `lib/utils.ts` with `cn()` helper and formatting utilities
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 2.2 Implement typed Axios API client module
    - Create `lib/api-client.ts` with the ApiClient class
    - Implement all endpoint methods: getIncidents, updateIncidentStatus, exportIncidentsCsv, getHealth, getStreamStatus, getStreamUrl, getDeskZone, updateDeskZone, getAiSummary
    - Configure base URL from `NEXT_PUBLIC_API_URL` environment variable with localhost:8000 fallback
    - Set 10-second timeout on all requests
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 2.3 Implement incident mapping function with priority derivation
    - Create mapping function to transform backend incident response to ComplianceEvent
    - Implement priority derivation: confidence >= 0.85 → "High Review Priority", >= 0.50 → "Needs Review", < 0.50 → "Informational"
    - Map status "False Alarm" → "False Positive", preserve others
    - Map incident_type to detail (replace underscores with spaces), title (capitalize), and eventType (raw)
    - _Requirements: 5.4, 13.2_

  - [ ]* 2.4 Write property test for incident mapping (Property 3)
    - **Property 3: Incident mapping with priority derivation**
    - Generate random incident objects with confidence in [0,1], verify priority derivation thresholds and status mapping
    - **Validates: Requirements 5.4, 13.2**

  - [x] 2.5 Implement custom hooks: usePolling, useViewState, useClock, useApiClient
    - Create `hooks/usePolling.ts` — generic interval polling with cleanup, enabled flag, and error callback
    - Create `hooks/useViewState.ts` — active view state management returning ViewKey and setter
    - Create `hooks/useClock.ts` — real-time HH:MM:SS clock updated every second
    - Create `hooks/useApiClient.ts` — API client instance accessor
    - _Requirements: 2.5, 2.7, 3.5, 4.5_

  - [ ]* 2.6 Write property test for debounce behavior (Property 8)
    - **Property 8: AI summary debounce**
    - Generate random event arrival timestamps within 30-second windows, verify at most one request per window
    - **Validates: Requirements 11.3**

- [x] 3. Implement Shell layout: Sidebar, Topbar, and view switching
  - [x] 3.1 Implement Shell component with client-side view switching
    - Create `components/shell/Shell.tsx` managing active ViewKey, sidebar collapse, and mobile visibility
    - Render Sidebar, Topbar, and main content area in a flex layout filling 100vh
    - Default to "dashboard" view on root URL
    - _Requirements: 2.1, 2.5, 2.6_

  - [x] 3.2 Implement Sidebar with collapsible navigation for 8 views
    - Create `components/shell/Sidebar.tsx` with all 8 nav items (Dashboard, Live Monitoring, Compliance Events, Compliance Review, Analytics, AWS Services, System Status, Settings)
    - Implement collapsed mode (icons only, ≤80px) and expanded mode (icons + labels, 200-260px)
    - Apply active styling (distinct background + primary icon) to current view
    - Add tooltip on hover in collapsed mode (within 300ms)
    - Hide sidebar below 768px with menu toggle in Topbar
    - _Requirements: 2.2, 2.3, 2.4, 2.8, 15.2, 15.6_

  - [x] 3.3 Implement Topbar with clock, status indicators, and responsive toggle
    - Create `components/shell/Topbar.tsx` displaying real-time clock (HH:MM:SS), monitored area name, "Monitoring Active" pulse indicator, AWS status pill, notification bell, user avatar
    - Implement menu toggle button with aria-label and aria-expanded for mobile
    - _Requirements: 2.7, 15.2, 15.4, 15.6_

  - [ ]* 3.4 Write property test for navigation state consistency (Property 1)
    - **Property 1: Navigation state consistency**
    - For arbitrary ViewKey values, verify exactly one nav item has active styling and clicking updates state
    - **Validates: Requirements 2.3, 2.5**

  - [ ]* 3.5 Write unit tests for Shell, Sidebar, and Topbar
    - Test collapsed/expanded modes, view switching, responsive behavior, ARIA attributes
    - Test keyboard navigation and focus indicators
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 15.3, 15.4_

- [x] 4. Checkpoint - Ensure shell and core infrastructure pass tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Dashboard Overview view and widgets
  - [x] 5.1 Implement StatusCard widget with glass-morphism styling
    - Create `components/widgets/StatusCard.tsx` with title, value, icon, and trend props
    - Apply Glass_Card styling (backdrop blur, semi-transparent background, border)
    - _Requirements: 3.2, 3.3, 12.3_

  - [x] 5.2 Implement EventFeed widget
    - Create `components/widgets/EventFeed.tsx` showing scrollable event list
    - Display id, formatted detail, timestamp, priority badge, status badge, and zone for each event
    - Add aria-live="polite" for dynamic updates
    - _Requirements: 5.3, 15.4_

  - [x] 5.3 Implement ComplianceScore widget
    - Create `components/widgets/ComplianceScore.tsx` showing percentage of reviewed incidents
    - Calculate: (non-pending count / total) * 100, display 0 when total is 0
    - _Requirements: 7.5_

  - [ ]* 5.4 Write property test for status card count derivation (Property 2)
    - **Property 2: Status card count derivation**
    - Generate random incident arrays with varying statuses, verify count calculations match expectations
    - **Validates: Requirements 3.2**

  - [ ]* 5.5 Write property test for compliance score calculation (Property 6)
    - **Property 6: Compliance score calculation**
    - Generate random incident arrays, verify score = (non-pending / total) * 100, 0 when empty
    - **Validates: Requirements 7.5**

  - [x] 5.6 Implement DashboardView with responsive grid layout
    - Create `components/views/DashboardView.tsx` combining StatusCards, StreamPreview, EventFeed, AiAssistant, ComplianceScore, AWS cards, and GovernanceBadges
    - Implement responsive grid: 2-column + sidebar at ≥1280px, single column below
    - Poll status cards and event feed at ≤10 second intervals
    - Show independent error/loading states per widget
    - _Requirements: 3.1, 3.4, 3.5, 3.6_

- [x] 6. Implement Live Monitoring and Compliance Events views
  - [x] 6.1 Implement StreamPreview widget with MJPEG display and scan line overlay
    - Create `components/widgets/StreamPreview.tsx` rendering MJPEG stream from `/stream/video.mjpg`
    - Implement animated scan line overlay for active monitoring indication
    - Show "Monitoring is not active" placeholder on 503 with reduced opacity, hide scan line
    - _Requirements: 4.2, 4.3, 4.4, 13.7_

  - [x] 6.2 Implement LiveMonitoringView with detection metrics
    - Create `components/views/LiveMonitoringView.tsx` with 2-column layout (feed + event sidebar) at ≥1280px
    - Poll GET /stream/status every 2 seconds for people count, phone count, inference_ms
    - Show error indicator in metrics panel on non-200 response, retain last data
    - _Requirements: 4.1, 4.5, 4.6_

  - [x] 6.3 Implement AiAssistant widget with debounce and truncation
    - Create `components/widgets/AiAssistant.tsx` calling POST /api/ai/summary
    - Debounce requests to at most once per 30 seconds
    - Show loading skeleton while awaiting response
    - Truncate response at 2000 characters with visual indicator
    - Display error state with retry button on timeout (15s) or HTTP error
    - Render in scrollable card with max-height 400px
    - Preserve last summary when navigating away and returning
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 6.4 Write property test for AI response truncation (Property 9)
    - **Property 9: AI response truncation**
    - Generate random strings of varying lengths, verify truncation at 2000 chars with indicator
    - **Validates: Requirements 11.6**

  - [x] 6.5 Implement ComplianceEventsView with status cards and AI panel
    - Create `components/views/ComplianceEventsView.tsx` with 2-column grid (2/3 events + 1/3 AI panel)
    - Fetch up to 100 events from GET /incidents sorted by timestamp descending
    - Display priority badges (red/amber/blue) and status badges (yellow/green/gray)
    - Show error state with retry mechanism on fetch failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 6.6 Write property test for event rendering completeness (Property 4)
    - **Property 4: Event rendering completeness**
    - Generate random ComplianceEvent objects, verify all fields rendered in feed items
    - **Validates: Requirements 5.3**

- [x] 7. Implement Compliance Review and Analytics views
  - [x] 7.1 Implement ComplianceReviewView with searchable table and workflow actions
    - Create `components/views/ComplianceReviewView.tsx` with data table, search input, priority/status dropdown filters
    - Implement case-insensitive substring search across id, detail, zone, reviewer fields
    - Display columns: Event ID, Detail, Zone, Priority, Status, Reviewer, Actions
    - Implement actions: Assign Reviewer, Mark Confirmed, Mark False Positive, Escalate (calling PATCH /incidents/{id}/status)
    - Update row status badge immediately on successful response
    - Implement CSV export button triggering GET /incidents/export with current filters
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.2 Write property test for text search filtering (Property 5)
    - **Property 5: Text search filtering**
    - Generate random ComplianceEvent arrays and search strings, verify filtered results contain exactly the matching events
    - **Validates: Requirements 6.2**

  - [x] 7.3 Implement AnalyticsView with charts and compliance score
    - Create `components/views/AnalyticsView.tsx` with bar chart (daily events, current week), pie chart (event categories, past 7 days), and line chart (weekly review trends)
    - Use Recharts for all chart rendering
    - Display compliance score widget and AI assistant panel below charts
    - Show empty state messages when data sets are empty
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 8. Checkpoint - Ensure views and widgets pass tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement AWS Services, System Status, and Settings views
  - [x] 9.1 Implement HealthProgressBar widget with color-coded thresholds
    - Create `components/widgets/HealthProgressBar.tsx` with label, value (0-100), and status props
    - Color: green > 90%, amber 70-90%, red < 70%
    - Show "unreachable" label when component is at 0%
    - _Requirements: 9.2, 9.3_

  - [x] 9.2 Implement component health derivation logic
    - Create health derivation utilities: Camera (stream 200 = 100%, else 0%), AI Engine (stream 200 + fps > 0 = 100%, else 0%), Backend (health 200 = 100%, else 0%), Database (health 200 + database true = 100%, else 0%), AWS (static 99.9%), Retention (health status !== "unhealthy" = 100%, else 0%)
    - _Requirements: 9.4, 9.5, 9.6, 9.7, 9.8_

  - [ ]* 9.3 Write property test for component health derivation and color coding (Property 7)
    - **Property 7: Component health derivation and color coding**
    - Generate random API responses (200/503) and fps values, verify health derivation and color thresholds
    - **Validates: Requirements 8.4, 9.3, 9.4, 9.5, 9.6, 9.7**

  - [x] 9.4 Implement AwsServicesView with service cards and system health panel
    - Create `components/views/AwsServicesView.tsx` with Glass_Card service cards for EC2, S3, Amazon Bedrock, CloudWatch
    - Display name, role, region, uptime percentage, and "Operational"/"Degraded" status
    - Fetch GET /health and map to component indicators (system health, database, AI engine, uptime)
    - Poll every 30 seconds
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.5 Implement SystemStatusView with progress bars for 6 components
    - Create `components/views/SystemStatusView.tsx` with HealthProgressBar for each of 6 components
    - Poll GET /health and GET /stream/status every 30 seconds
    - Apply color-coded thresholds and show unreachable state on errors
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

  - [x] 9.6 Implement SettingsView with zone config, toggles, and governance display
    - Create `components/views/SettingsView.tsx` with zone configuration (GET/PUT /zones/desk), monitoring toggles (localStorage persistence), and data governance section
    - Display editable percentage fields (0-100) for x1, y1, x2, y2
    - Show success confirmation for 3+ seconds on save, show 422 validation errors
    - Show network error on unreachable backend, retain unsaved values
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 10. Implement Data Governance badges and remaining widgets
  - [x] 10.1 Implement GovernanceBadges widget with 9 static badges
    - Create `components/widgets/GovernanceBadges.tsx` with all 9 governance control labels
    - Render in a Glass_Card container with flex-wrap layout
    - Display as always-visible static indicators (no backend dependency)
    - Labels: "Human Review Required", "No Facial Recognition", "No Biometric Identification", "No Continuous Video Recording", "Only Event Evidence Stored", "Local Processing Supported", "Automatic 7 Day Evidence Retention", "Authorized Access Required", "Audit Logging Enabled"
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 11. Implement error handling and accessibility
  - [x] 11.1 Implement global error handling and connection status in Topbar
    - Add connection error indicator to Topbar on network timeout or API unreachability
    - Implement widget-level error isolation (failure in one widget doesn't cascade)
    - Retain last fetched data on error, show empty state on first-load failure
    - Implement retry buttons on one-shot request failures
    - _Requirements: 13.5, 13.7, 3.6_

  - [x] 11.2 Implement responsive layout breakpoints and accessibility attributes
    - Ensure status cards: 4 columns → 2 at 640px → 1 below 640px
    - Ensure main content: 2-column → 1-column below 1280px
    - Add ARIA labels on all icon-only buttons (notification bell, menu toggle, camera actions)
    - Add aria-label on status indicators, aria-live="polite" on event feed and stream status
    - Ensure minimum 44x44px touch targets at ≤1024px viewport
    - Ensure visible focus indicators (2px outline, 3:1 contrast) on all interactive elements
    - Ensure sequential Tab navigation: sidebar → topbar → page content
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [ ]* 11.3 Write integration tests for API client and polling lifecycle
    - Test API client with mocked Axios responses for all endpoints
    - Test polling hook start/stop/cleanup lifecycle
    - Test error handling flows (503, 422, network timeout)
    - _Requirements: 13.1, 13.5, 13.7_

- [x] 12. Final checkpoint - Verify build and all tests pass
  - Ensure `pnpm build` completes without errors
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design specifies TypeScript throughout — all code uses strict TypeScript
- The backend remains unchanged; only a POST /api/ai/summary proxy endpoint is added
- shadcn/ui components are generated into `components/ui/` and customized via CSS tokens
- All polling intervals follow the design: 2s (stream), 10s (dashboard), 30s (health/AWS)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.5"] },
    { "id": 4, "tasks": ["2.4", "2.6", "3.1"] },
    { "id": 5, "tasks": ["3.2", "3.3"] },
    { "id": 6, "tasks": ["3.4", "3.5"] },
    { "id": 7, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 8, "tasks": ["5.4", "5.5", "5.6", "6.1"] },
    { "id": 9, "tasks": ["6.2", "6.3", "6.5"] },
    { "id": 10, "tasks": ["6.4", "6.6", "7.1"] },
    { "id": 11, "tasks": ["7.2", "7.3"] },
    { "id": 12, "tasks": ["9.1", "9.2"] },
    { "id": 13, "tasks": ["9.3", "9.4", "9.5", "9.6"] },
    { "id": 14, "tasks": ["10.1"] },
    { "id": 15, "tasks": ["11.1", "11.2"] },
    { "id": 16, "tasks": ["11.3"] }
  ]
}
```
