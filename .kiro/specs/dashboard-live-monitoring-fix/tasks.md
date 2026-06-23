# Implementation Plan

## Overview

Fix three interrelated bugs in `DashboardView.tsx`: (1) LiveMonitoringCard has no fallback when pipeline is off, (2) EventFeed uses broken `calc()` height in the dashboard grid, (3) dashboard and Live Monitoring views are visually redundant. The fix adds pipeline status awareness, browser camera fallback, compact preview mode, explicit height constraints, and visual differentiation.

## Tasks

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Dashboard Monitoring Card Non-Functional States
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the three interrelated bugs exist
  - **Scoped PBT Approach**: Use fast-check to generate combinations of pipeline states (running/stopped) and screen widths (≥ xl breakpoint) to demonstrate:
    - When `pipelineRunning == false`: LiveMonitoringCard has no fallback action (no browser camera, no "Start Monitoring" button)
    - When rendered in dashboard grid at xl+ widths: EventFeed ScrollArea height is unconstrained (resolves to content height, not a fixed/viewport-relative value)
    - LiveMonitoringCard preview dimensions and EventFeed item count are identical to LiveMonitoringView (no compact differentiation)
  - Test file: `frontend/__tests__/dashboard-live-monitoring-bug.test.tsx`
  - Setup: Mock `apiClient.getPipelineStatus()` to return stopped state, render `DashboardView` with msw mocking
  - Assert: A browser camera element OR a "Start Monitoring" button exists in LiveMonitoringCard (from Bug Condition in design: `hasFallbackOrQuickAction(input)` must be true)
  - Assert: EventFeed container has a resolved height ≤ viewport maximum (from Bug Condition: `parentHeightConstrained == true`)
  - Assert: Dashboard preview is compact and distinct from LiveMonitoringView (from Bug Condition: `NOT isVisuallyIdenticalTo(input, "LiveMonitoringView")`)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bugs exist)
  - Document counterexamples found (e.g., "LiveMonitoringCard renders only StreamPreview with no fallback when pipeline is off", "EventFeed height resolves to auto/content height", "Dashboard and Live Monitoring views have identical preview dimensions")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Live Monitoring Page and Other Dashboard Sections Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - **Step 1 - Observe**: Render `LiveMonitoringView` on UNFIXED code and record:
    - Full-size StreamPreview/BrowserCamera is present with aspect-video class
    - PipelineControls component is rendered with source selection
    - EventFeed renders complete list with full card layout (priority badges, status badges, timestamps, icons)
  - **Step 2 - Observe**: Render `DashboardView` on UNFIXED code and record:
    - SystemStatusCards, AiAssistant, ComplianceScore, GovernanceBadges, AwsServicesSection all render correctly
  - **Step 3 - Write property-based tests** using fast-check:
    - Generate random `ComplianceEvent[]` arrays with arbitrary priorities, statuses, timestamps, and event types
    - For all generated event arrays: assert LiveMonitoringView renders events with correct priority badges, status badges, timestamps, and icons
    - For all generated pipeline status combinations: assert LiveMonitoringView renders full-size StreamPreview or BrowserCamera with PipelineControls
    - Assert other dashboard widgets (SystemStatusCards, AiAssistant, ComplianceScore, GovernanceBadges) render unchanged
  - Test file: `frontend/__tests__/dashboard-live-monitoring-preservation.test.tsx`
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Fix for dashboard live monitoring card non-functional states, broken EventFeed height, and visual redundancy

  - [ ] 3.1 Add pipeline status awareness to LiveMonitoringCard
    - Import and use pipeline status hook/polling in `DashboardView.tsx` `LiveMonitoringCard` section
    - Conditionally render based on `pipelineRunning` state
    - When pipeline is running: render compact `StreamPreview` (not full aspect-video)
    - When pipeline is stopped: render `BrowserCamera` fallback OR "Start Monitoring" quick-action button
    - _Bug_Condition: isBugCondition(input) where input.pipelineRunning == false AND NOT hasFallbackOrQuickAction(input)_
    - _Expected_Behavior: Dashboard provides actionable monitoring UI regardless of pipeline state_
    - _Preservation: LiveMonitoringView continues to use its own full-size StreamPreview/BrowserCamera/PipelineControls_
    - _Requirements: 2.1, 3.1, 3.2_

  - [ ] 3.2 Make LiveMonitoringCard compact and visually distinct
    - Replace full `aspect-video` StreamPreview with a compact preview container (e.g., `max-h-[200px]` or `h-48`)
    - Add summary metrics below preview (detection count, pipeline status indicator, last event time)
    - Add "View Full Monitoring →" navigation link in card header linking to Live Monitoring page
    - Ensure the compact card is visually distinct from the full-page LiveMonitoringView presentation
    - _Bug_Condition: isBugCondition(input) where isVisuallyIdenticalTo(input, "LiveMonitoringView")_
    - _Expected_Behavior: Dashboard shows compact summary card, not a duplicate of the full monitoring page_
    - _Preservation: LiveMonitoringView retains its full-size layout unchanged_
    - _Requirements: 2.3, 2.4, 3.1_

  - [ ] 3.3 Fix EventFeed height with explicit constraints
    - In `EventFeed.tsx`: replace `lg:h-[calc(100%-65px)]` with a strategy that works in unconstrained grid parents
    - Option A: Accept a `maxHeight` or `compact` prop and apply `max-h-[400px]` or `max-h-[60vh]` when in dashboard context
    - Option B: Use `flex-1 min-h-0` pattern on the parent container so ScrollArea fills available flex space
    - Option C: Default to `h-[420px]` and remove the broken `lg:h-[calc(100%-65px)]`
    - Ensure ScrollArea scrolls content correctly at xl breakpoint in the dashboard grid
    - _Bug_Condition: isBugCondition(input) where input.parentHeightConstrained == false AND input.screenWidth >= BREAKPOINT_XL_
    - _Expected_Behavior: EventFeed has resolved, constrained height enabling scroll_
    - _Preservation: EventFeed on LiveMonitoringView continues to work as before_
    - _Requirements: 2.2, 3.1_

  - [ ] 3.4 Add compact mode to EventFeed for dashboard context
    - Add `compact` prop to `EventFeed` component
    - When `compact=true`: limit displayed items (5-8 max), use condensed card layout, show summary count
    - Pass `compact={true}` from `DashboardView` and `compact={false}` (or omit) from `LiveMonitoringView`
    - Ensure event data rendering (badges, timestamps, icons) remains correct in both modes
    - _Bug_Condition: Dashboard EventFeed is visually identical to Live Monitoring EventFeed_
    - _Expected_Behavior: Dashboard shows fewer items with condensed presentation_
    - _Preservation: LiveMonitoringView EventFeed renders full list with full cards unchanged_
    - _Requirements: 2.4, 3.1, 3.3_

  - [ ] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Dashboard Monitoring Card Provides Functional Preview
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (actionable monitoring, constrained height, compact differentiation)
    - When this test passes, it confirms the expected behavior is satisfied for all bug conditions
    - Run bug condition exploration test from step 1: `frontend/__tests__/dashboard-live-monitoring-bug.test.tsx`
    - **EXPECTED OUTCOME**: Test PASSES (confirms all three bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Live Monitoring Page and Other Dashboard Sections Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2: `frontend/__tests__/dashboard-live-monitoring-preservation.test.tsx`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions to LiveMonitoringView, event rendering, or other dashboard widgets)
    - Confirm all property-based tests still pass after fix (no regressions)

- [ ] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `cd frontend && pnpm test -- --run`
  - Ensure both property-based test files pass:
    - `frontend/__tests__/dashboard-live-monitoring-bug.test.tsx` (bug condition → expected behavior)
    - `frontend/__tests__/dashboard-live-monitoring-preservation.test.tsx` (preservation)
  - Verify no TypeScript errors: `cd frontend && pnpm tsc --noEmit`
  - Verify no lint errors: `cd frontend && pnpm lint`
  - Ensure all tests pass, ask the user if questions arise.

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1", "2"],
      "description": "Write exploration and preservation tests on UNFIXED code (independent, can run in parallel)"
    },
    {
      "wave": 2,
      "tasks": ["3.1", "3.3"],
      "description": "Implement pipeline status awareness and fix EventFeed height (independent implementation tasks)"
    },
    {
      "wave": 3,
      "tasks": ["3.2", "3.4"],
      "description": "Make LiveMonitoringCard compact (depends on 3.1) and add EventFeed compact mode (depends on 3.3)"
    },
    {
      "wave": 4,
      "tasks": ["3.5", "3.6"],
      "description": "Verify exploration test passes and preservation tests still pass after fix"
    },
    {
      "wave": 5,
      "tasks": ["4"],
      "description": "Final checkpoint - run full test suite, type checking, and linting"
    }
  ]
}
```

## Notes

- Tasks 1 and 2 are independent and can be written in parallel (both run on UNFIXED code)
- Tasks 3.1-3.4 are the implementation phase; 3.1 and 3.3 can proceed in parallel after tests are written
- Task 3.2 depends on 3.1 (compact preview needs pipeline awareness first)
- Task 3.4 depends on 3.3 (compact mode needs the height fix infrastructure)
- The test files use Vitest + fast-check for property-based testing and msw for API mocking
- All component tests should use `@testing-library/react` for rendering and assertions
