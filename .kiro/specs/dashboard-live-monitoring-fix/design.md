# Dashboard Live Monitoring Fix — Bugfix Design

## Overview

The Dashboard view (`DashboardView.tsx`) has three interrelated bugs that degrade its usability: (1) the `LiveMonitoringCard` renders a `StreamPreview` that shows "Monitoring is not active" when the backend pipeline is off, with no fallback or controls to activate monitoring; (2) the `EventFeed` uses a CSS `calc()` height that doesn't resolve within the dashboard's unconstrained grid cell, causing overflow/scroll failures; (3) the dashboard and Live Monitoring views render nearly identical full-size stream previews and event feeds, creating a redundant user experience.

The fix refactors `LiveMonitoringCard` into a compact, summary-oriented widget with browser camera fallback capability and a quick-start action, constrains the `EventFeed` height via a fixed/viewport-relative value within the dashboard grid, and differentiates the dashboard's monitoring presentation from the full Live Monitoring page.

## Glossary

- **Bug_Condition (C)**: The set of conditions where the dashboard monitoring card is either non-functional (pipeline off, no fallback), has broken scroll layout, or is visually redundant with the Live Monitoring page
- **Property (P)**: The desired behavior — dashboard provides a compact, functional monitoring preview with proper scroll and differentiated UX
- **Preservation**: The Live Monitoring page, event data rendering, and all other dashboard sections remain unchanged
- **LiveMonitoringCard**: The inline component in `DashboardView.tsx` that displays the live stream preview
- **StreamPreview**: Widget in `components/widgets/StreamPreview.tsx` that renders the MJPEG `<img>` element
- **BrowserCamera**: Widget in `components/widgets/BrowserCamera.tsx` that uses `getUserMedia` with backend detection
- **EventFeed**: Widget in `components/widgets/EventFeed.tsx` with a `ScrollArea` for displaying compliance events
- **PipelineControls**: Widget in `components/widgets/PipelineControls.tsx` that manages source selection and pipeline start/stop

## Bug Details

### Bug Condition

The bug manifests across three related scenarios in `DashboardView.tsx`:

1. The `LiveMonitoringCard` always renders `<StreamPreview isActive={true} />` which connects to the MJPEG endpoint. If the backend pipeline is not running, the stream returns a 503, triggering the `handleError` callback and showing "Monitoring is not active" — with no way to start the pipeline or fall back to browser camera.

2. The `EventFeed` component uses `lg:h-[calc(100%-65px)]` for its `ScrollArea`. In the dashboard grid layout (`xl:grid-cols-3`), the parent `xl:col-span-1` grid cell has no explicit height constraint, so `100%` resolves to `auto` and the `calc()` produces no meaningful bound, causing the content to overflow or not scroll.

3. The `LiveMonitoringCard` renders an identical full-aspect-ratio `StreamPreview` and the `EventFeed` shows the same data with the same card layout as the Live Monitoring page — no visual or functional differentiation.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type DashboardRenderContext
  OUTPUT: boolean
  
  RETURN (
    (input.pipelineRunning == false AND input.view == "dashboard"
     AND input.component == "LiveMonitoringCard"
     AND NOT hasFallbackOrQuickAction(input))
    OR
    (input.view == "dashboard" AND input.component == "EventFeed"
     AND input.parentHeightConstrained == false
     AND input.screenWidth >= BREAKPOINT_XL)
    OR
    (input.view == "dashboard" AND input.component == "LiveMonitoringCard"
     AND isVisuallyIdenticalTo(input, "LiveMonitoringView"))
  )
END FUNCTION
```

### Examples

- **No fallback**: User opens Dashboard, pipeline is stopped → sees "Monitoring is not active" with no button to start or camera button. Expected: see a quick-action "Start Monitoring" button or auto-activate browser camera preview.
- **Scroll overflow**: User opens Dashboard on 1440px+ screen → EventFeed in right column shows all 20 events overflowing beyond the visible card area without a working scrollbar. Expected: EventFeed constrains to a viewport-relative height and scrolls.
- **Redundant UX**: User views Dashboard's LiveMonitoringCard → sees the same full 16:9 aspect-video stream and identical EventFeed cards as the Live Monitoring page. Expected: a compact preview (smaller aspect ratio) with summary stats, visually distinct from the full-page version.
- **Edge case**: Pipeline starts while user is on Dashboard → StreamPreview loads successfully, compact preview shows live feed. Expected: transition to live state is smooth.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The Live Monitoring page (`LiveMonitoringView.tsx`) must continue to display the full-size `StreamPreview` or `BrowserCamera` with `PipelineControls` and the complete `EventFeed`
- When the backend pipeline IS running and the user views the Dashboard, the live MJPEG stream preview must still render (now in compact form)
- Events loaded from the backend must continue to display with correct priority badges, status badges, timestamps, and event type icons
- Other dashboard sections (`SystemStatusCards`, `AiAssistant`, `ComplianceScore`, `GovernanceBadges`, `AwsServicesSection`) must render unchanged
- Mouse/keyboard interactions on all non-affected components must continue to work

**Scope:**
All inputs/interactions that do NOT involve the dashboard's `LiveMonitoringCard` layout, the dashboard's `EventFeed` height, or the dashboard-vs-LiveMonitoring differentiation should be completely unaffected. This includes:
- The Live Monitoring page functionality
- Event data fetching and mapping
- All other dashboard widgets
- Backend API endpoints and responses

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **No Fallback or Controls in LiveMonitoringCard**: The `LiveMonitoringCard` component in `DashboardView.tsx` unconditionally renders `<StreamPreview isActive={true} />` without any awareness of pipeline status. Unlike `LiveMonitoringView` which has `PipelineControls` and conditionally renders `BrowserCamera`, the dashboard card has no mechanism to detect that the stream is unavailable and offer an alternative.

2. **Unconstrained Parent Height for EventFeed**: The `EventFeed`'s `ScrollArea` uses `lg:h-[calc(100%-65px)]` — this depends on the parent having a resolved height. In the dashboard grid (`xl:grid-cols-3`), the right column (`xl:col-span-1`) is sized by content, not by an explicit height. CSS `calc(100% - 65px)` where `100%` refers to an auto-height parent produces no bound, so the `ScrollArea` grows with its content instead of scrolling.

3. **Copy-paste Architecture**: The `LiveMonitoringCard` was likely created by copying the card structure from `LiveMonitoringView` without redesigning it for a dashboard summary context. The same `StreamPreview` with `aspect-video` and the same `EventFeed` with full cards are used, resulting in identical visual output.

4. **No Compact Variant Props**: Neither `StreamPreview` nor `EventFeed` expose a "compact" or "summary" mode that would allow the dashboard to render a differentiated view.

## Correctness Properties

Property 1: Bug Condition - Dashboard Monitoring Card Provides Functional Preview

_For any_ dashboard render where the backend pipeline is not running, the fixed `LiveMonitoringCard` SHALL either automatically use the browser camera as a fallback source or display a clear quick-action button to start monitoring, ensuring the user is never left with an inert "Monitoring is not active" state with no recourse.

**Validates: Requirements 2.1**

Property 2: Bug Condition - EventFeed Height Resolves in Dashboard Grid

_For any_ screen width at or above the `xl` breakpoint where the `EventFeed` is rendered in the dashboard's grid right column, the fixed `EventFeed` container SHALL have a resolved, constrained height (fixed or viewport-relative) that enables the `ScrollArea` to scroll its content rather than overflowing.

**Validates: Requirements 2.2**

Property 3: Bug Condition - Dashboard Monitoring Card Is Visually Distinct

_For any_ dashboard render, the fixed `LiveMonitoringCard` SHALL present a compact, summary-oriented view that is visually and functionally distinct from the full Live Monitoring page — using a smaller preview, summary metrics, and fewer event items.

**Validates: Requirements 2.3, 2.4**

Property 4: Preservation - Live Monitoring Page Unchanged

_For any_ render of the `LiveMonitoringView`, the fixed code SHALL produce exactly the same behavior as the original code, preserving the full-size `StreamPreview`/`BrowserCamera`, `PipelineControls`, and complete `EventFeed`.

**Validates: Requirements 3.1, 3.2, 3.3**

Property 5: Preservation - Other Dashboard Sections Unchanged

_For any_ render of dashboard sections other than `LiveMonitoringCard` and the dashboard `EventFeed` height, the fixed code SHALL produce exactly the same behavior as the original code, preserving `SystemStatusCards`, `AiAssistant`, `ComplianceScore`, `GovernanceBadges`, and `AwsServicesSection`.

**Validates: Requirements 3.4**

## Fix Implementation

### Changes Required

**File**: `frontend/components/views/DashboardView.tsx`

**Component**: `LiveMonitoringCard` (inline component) and `EventFeed` usage

**Specific Changes**:

1. **Add Pipeline Status Awareness**: Import and use `apiClient.getPipelineStatus()` (or a polling hook) within `LiveMonitoringCard` to determine if the pipeline is running.

2. **Browser Camera Fallback**: When the pipeline is not running, render a compact `BrowserCamera` component instead of the inert `StreamPreview`. Alternatively, render a clear "Start Monitoring" quick-action button that either navigates to the Live Monitoring page or directly starts the pipeline with the browser camera preset.

3. **Compact Preview Layout**: Replace the full `aspect-video` `StreamPreview` with a smaller preview container (e.g., `aspect-[16/9] max-h-[200px]` or a fixed height like `h-48`) and add summary metrics (detection count, pipeline FPS, last event time) below the preview. This differentiates the dashboard card from the full-page view.

4. **Fix EventFeed Height**: Replace the `lg:h-[calc(100%-65px)]` in the dashboard context with a fixed or viewport-relative height. Options:
   - Pass a `height` prop to `EventFeed` and apply `h-[400px]` or `max-h-[60vh]` when in dashboard context
   - Constrain the parent grid cell with an explicit `max-h-*` or `h-*` class
   - Use a new `compact` prop on `EventFeed` that applies a fixed height internally

5. **Differentiate EventFeed Content**: Add a `compact` mode to `EventFeed` (or pass reduced `maxItems` like 5-8) and show condensed event cards or just summary statistics (count by priority, last event time) instead of the full card layout.

6. **Add Quick-Action Navigation**: Include a "View Full Monitoring →" link/button in the compact card header that navigates to the Live Monitoring view, clarifying the relationship between the two pages.

**File**: `frontend/components/widgets/EventFeed.tsx`

**Specific Changes**:

7. **Fix ScrollArea Height Resolution**: Replace the dual `h-[420px] ... lg:h-[calc(100%-65px)]` with a single strategy that works in both standalone and grid contexts. Options:
   - Accept a `maxHeight` prop: `<ScrollArea style={{ maxHeight }} ...>` 
   - Use `flex-1 min-h-0` pattern on the parent so the ScrollArea fills available flex space
   - Default to `h-[420px]` and remove the broken `lg:h-[calc(100%-65px)]`

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write component tests that render `DashboardView` and `EventFeed` in specific conditions and assert the expected DOM structure, scroll behavior, and visual differentiation. Run these tests on the UNFIXED code to observe failures.

**Test Cases**:
1. **No Fallback Test**: Render `DashboardView` with mocked pipeline status as "stopped" → assert that a browser camera element OR a "Start Monitoring" button exists (will fail on unfixed code)
2. **EventFeed Overflow Test**: Render `EventFeed` inside a grid container matching the dashboard layout at xl breakpoint → assert that the ScrollArea has a resolved computed height ≤ viewport height (will fail on unfixed code)
3. **Visual Differentiation Test**: Render both `DashboardView` and `LiveMonitoringView` → compare the preview dimensions and event item count — assert they are different (will fail on unfixed code)
4. **Stream Error Handling Test**: Render `LiveMonitoringCard` and simulate stream error → assert fallback UI is actionable (will fail on unfixed code)

**Expected Counterexamples**:
- `LiveMonitoringCard` renders only `<StreamPreview>` with no fallback elements when pipeline is off
- `EventFeed` ScrollArea height resolves to content height rather than a fixed value
- Dashboard and Live Monitoring views produce DOM trees with same StreamPreview dimensions
- Possible causes: missing pipeline status check, unconstrained grid parent, copy-paste architecture

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := renderDashboard_fixed(input)
  ASSERT hasActionableMonitoring(result)    // Property 1
  ASSERT scrollAreaHeightResolved(result)   // Property 2
  ASSERT isCompactAndDistinct(result)       // Property 3
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT renderLiveMonitoringView_original(input) = renderLiveMonitoringView_fixed(input)
  ASSERT renderOtherDashboardWidgets_original(input) = renderOtherDashboardWidgets_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many combinations of event arrays, pipeline states, and screen sizes
- It catches edge cases where the fix might inadvertently affect the Live Monitoring page
- It provides strong guarantees that event rendering (badges, timestamps, icons) is unchanged

**Test Plan**: Observe behavior on UNFIXED code first for the Live Monitoring page and other dashboard widgets, then write property-based tests capturing that behavior continues after the fix.

**Test Cases**:
1. **Live Monitoring Page Preservation**: Verify that `LiveMonitoringView` renders identically before and after the fix — same `StreamPreview`/`BrowserCamera`, same `PipelineControls`, same `EventFeed`
2. **Event Rendering Preservation**: For any array of `ComplianceEvent[]`, verify that event cards render with correct priority badges, status badges, timestamps, and icons in both views
3. **Other Dashboard Widgets Preservation**: Verify `SystemStatusCards`, `AiAssistant`, `ComplianceScore`, `GovernanceBadges` render identically
4. **Pipeline Running Preservation**: When pipeline IS running, verify the dashboard still shows a live stream (compact but functional)

### Unit Tests

- Test `LiveMonitoringCard` renders browser camera fallback when pipeline is stopped
- Test `LiveMonitoringCard` renders compact stream preview when pipeline is running
- Test `LiveMonitoringCard` shows "Start Monitoring" quick-action when no source is active
- Test `EventFeed` with explicit height prop renders a constrained ScrollArea
- Test `EventFeed` compact mode renders fewer items with condensed layout
- Test navigation link/button exists in compact monitoring card

### Property-Based Tests

- Generate random `ComplianceEvent[]` arrays and verify `EventFeed` renders correctly in compact vs full mode (correct item count, correct badge mapping)
- Generate random pipeline status combinations and verify `LiveMonitoringCard` always provides an actionable UI (never shows inert "not active" without a call-to-action)
- Generate random screen width values and verify `EventFeed` height is always ≤ a maximum bound in the dashboard grid context

### Integration Tests

- Test full Dashboard page with pipeline stopped → verify user can activate monitoring from dashboard
- Test full Dashboard page with pipeline running → verify compact live preview is visible and functional
- Test navigating between Dashboard and Live Monitoring → verify each page shows its own distinct presentation
- Test EventFeed scrolling with 20+ events in the dashboard grid → verify scroll works at xl breakpoint
