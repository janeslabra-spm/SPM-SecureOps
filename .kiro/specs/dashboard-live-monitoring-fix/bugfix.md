# Bugfix Requirements Document

## Introduction

The Dashboard view (`DashboardView.tsx`) has three interrelated bugs that degrade its usability:

1. The `LiveMonitoringCard` on the dashboard renders `<StreamPreview isActive={true} />` which connects to the backend MJPEG stream endpoint. If the backend pipeline is not running, it shows "Monitoring is not active." Unlike the `LiveMonitoringView`, the dashboard has no `PipelineControls` or `BrowserCamera` fallback, so users cannot activate monitoring from the dashboard.

2. The `EventFeed` component uses a `ScrollArea` with `lg:h-[calc(100%-65px)]` for its scrollable region. When rendered in the Dashboard's grid layout (right column, `xl:col-span-1`), the parent container has no constrained height, so the calc-based height doesn't resolve properly and the feed either overflows its container or fails to scroll.

3. The Dashboard and Live Monitoring views render nearly identical content (same `StreamPreview`, same `EventFeed` with the same data) with only minor layout differences, creating a redundant user experience.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the backend pipeline is not running AND the user views the Dashboard THEN the system displays "Monitoring is not active" in the LiveMonitoringCard with no way to start monitoring or switch to browser camera

1.2 WHEN the user views the Dashboard on a large screen (xl breakpoint) THEN the EventFeed's `lg:h-[calc(100%-65px)]` height does not resolve because the parent grid cell has no fixed/constrained height, causing the feed to overflow or not scroll

1.3 WHEN the user views the Dashboard THEN the system displays essentially the same full-size StreamPreview and EventFeed layout as the Live Monitoring page, providing no differentiated summary or at-a-glance experience

1.4 WHEN the user navigates between Dashboard and Live Monitoring THEN both views show the same stream content and event data with the same component hierarchy, making the two pages redundant

### Expected Behavior (Correct)

2.1 WHEN the backend pipeline is not running AND the user views the Dashboard THEN the system SHALL display a compact live preview that works with the browser camera source (similar to LiveMonitoringView's BrowserCamera fallback) or show a meaningful status with a quick-action to start monitoring

2.2 WHEN the EventFeed is rendered in the Dashboard's grid layout on any screen size THEN the system SHALL constrain the EventFeed container to a fixed or viewport-relative height so the ScrollArea resolves correctly and content is scrollable

2.3 WHEN the user views the Dashboard THEN the system SHALL present a compact, summary-oriented monitoring preview that is visually and functionally distinct from the full Live Monitoring page — showing a smaller preview, key metrics, and quick status rather than a full-size stream

2.4 WHEN the user views the Dashboard THEN the system SHALL differentiate the dashboard's event feed presentation (e.g., fewer items, compact cards, or summary stats) from the full event feed on the Live Monitoring page

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user views the Live Monitoring page THEN the system SHALL CONTINUE TO display the full-size StreamPreview or BrowserCamera with PipelineControls and the complete EventFeed

3.2 WHEN the backend pipeline is running and the user views the Dashboard THEN the system SHALL CONTINUE TO show the live MJPEG stream preview (now in a compact form)

3.3 WHEN events are loaded from the backend THEN the system SHALL CONTINUE TO display events with correct priority badges, status badges, timestamps, and event type icons

3.4 WHEN the user views other dashboard sections (SystemStatusCards, AiAssistant, ComplianceScore, GovernanceBadges, AWS services) THEN the system SHALL CONTINUE TO render them unchanged
