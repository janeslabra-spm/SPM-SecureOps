"""Unit tests for ComplianceEventDispatcher.

Tests cover:
- Non-blocking dispatch (≤5ms overhead)
- Empty detection guard (no dispatch on empty list)
- Buffering when downstream unavailable
- Buffer capacity (FIFO eviction at 100)
- Retry and replay in chronological order
- Replay stops on mid-stream failure
- start() and stop() lifecycle
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from backend.core.event_dispatcher import ComplianceEventDispatcher
from backend.core.pipeline_types import DetectionEvent, DetectionResult


def _make_event(
    timestamp: str = "2024-01-15T10:30:00+00:00",
    camera_id: str = "cam-01",
    detections: list[DetectionResult] | None = None,
) -> DetectionEvent:
    """Helper to create a DetectionEvent with defaults."""
    if detections is None:
        detections = [
            DetectionResult(
                label="cell phone",
                confidence=0.85,
                bbox={"x1": 10, "y1": 20, "x2": 50, "y2": 60},
                class_id=67,
            )
        ]
    return DetectionEvent(
        timestamp=timestamp,
        camera_id=camera_id,
        frame_width=960,
        frame_height=540,
        detections=detections,
    )


@pytest.fixture
def mock_engine():
    """Create a mock compliance event engine."""
    engine = AsyncMock()
    engine.process_event = AsyncMock()
    return engine


@pytest.fixture
def dispatcher(mock_engine):
    """Create a ComplianceEventDispatcher with a mock engine."""
    return ComplianceEventDispatcher(mock_engine)


class TestDispatchBasic:
    """Tests for basic dispatch behavior."""

    @pytest.mark.asyncio
    async def test_dispatch_does_not_enqueue_empty_detections(
        self, dispatcher, mock_engine
    ):
        """Events with empty detections should not be enqueued."""
        event = _make_event(detections=[])
        await dispatcher.dispatch(event)
        assert dispatcher._queue.empty()

    @pytest.mark.asyncio
    async def test_dispatch_enqueues_event_with_detections(self, dispatcher):
        """Events with detections should be placed on the queue."""
        event = _make_event()
        await dispatcher.dispatch(event)
        assert not dispatcher._queue.empty()
        queued = dispatcher._queue.get_nowait()
        assert queued is event

    @pytest.mark.asyncio
    async def test_dispatch_is_non_blocking(self, dispatcher):
        """dispatch() should complete within 5ms."""
        event = _make_event()
        start = time.perf_counter()
        await dispatcher.dispatch(event)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5.0


class TestWorkerDispatch:
    """Tests for the background worker dispatching events."""

    @pytest.mark.asyncio
    async def test_worker_dispatches_to_engine(self, dispatcher, mock_engine):
        """Worker should forward events to the event engine."""
        event = _make_event()
        await dispatcher.start()
        await dispatcher.dispatch(event)
        # Give worker time to process
        await asyncio.sleep(0.1)
        await dispatcher.stop()

        mock_engine.process_event.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_worker_buffers_on_engine_failure(
        self, dispatcher, mock_engine
    ):
        """When engine raises, event should be buffered."""
        mock_engine.process_event.side_effect = ConnectionError("unavailable")
        event = _make_event()

        await dispatcher.start()
        await dispatcher.dispatch(event)
        await asyncio.sleep(0.1)
        await dispatcher.stop()

        assert len(dispatcher._buffer) == 1
        assert dispatcher._buffer[0] is event


class TestBuffering:
    """Tests for event buffer capacity and FIFO eviction."""

    @pytest.mark.asyncio
    async def test_buffer_capacity_is_100(self, dispatcher, mock_engine):
        """Buffer should hold a maximum of 100 events."""
        mock_engine.process_event.side_effect = ConnectionError("down")

        await dispatcher.start()
        # Dispatch 100 events
        for i in range(100):
            event = _make_event(timestamp=f"2024-01-15T10:{i:02d}:00+00:00")
            await dispatcher.dispatch(event)

        await asyncio.sleep(0.5)
        await dispatcher.stop()

        assert len(dispatcher._buffer) == 100

    @pytest.mark.asyncio
    async def test_buffer_overflow_discards_oldest(
        self, dispatcher, mock_engine
    ):
        """When buffer is full, oldest event should be discarded."""
        mock_engine.process_event.side_effect = ConnectionError("down")

        await dispatcher.start()
        # Fill buffer with 100 events
        for i in range(100):
            event = _make_event(timestamp=f"2024-01-15T10:{i:02d}:00+00:00")
            await dispatcher.dispatch(event)

        await asyncio.sleep(0.5)

        # Add one more to trigger overflow
        overflow_event = _make_event(timestamp="2024-01-15T11:00:00+00:00")
        await dispatcher.dispatch(overflow_event)
        await asyncio.sleep(0.2)
        await dispatcher.stop()

        assert len(dispatcher._buffer) == 100
        # The oldest event (10:00:00) should have been discarded
        timestamps = [e.timestamp for e in dispatcher._buffer]
        assert "2024-01-15T10:00:00+00:00" not in timestamps
        assert "2024-01-15T11:00:00+00:00" in timestamps


class TestReplay:
    """Tests for buffer replay on reconnect."""

    @pytest.mark.asyncio
    async def test_replay_in_chronological_order(self, mock_engine):
        """Buffered events should be replayed in timestamp-ascending order."""
        call_order: list[str] = []

        # Use a short retry interval for fast testing
        dispatcher = ComplianceEventDispatcher(mock_engine)
        dispatcher.RETRY_INTERVAL = 0.3

        # Always fail initially
        mock_engine.process_event.side_effect = ConnectionError("down")

        await dispatcher.start()

        # Dispatch 3 events out of timestamp order
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:03:00+00:00")
        )
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:01:00+00:00")
        )
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:02:00+00:00")
        )

        # Wait for all events to be attempted and buffered
        await asyncio.sleep(0.5)
        assert len(dispatcher._buffer) == 3

        # Now switch engine to succeed and track call order
        async def track_calls(event: DetectionEvent) -> None:
            call_order.append(event.timestamp)

        mock_engine.process_event.side_effect = track_calls

        # Wait for retry cycle to trigger replay
        await asyncio.sleep(1.0)
        await dispatcher.stop()

        # Verify chronological order
        assert call_order == [
            "2024-01-15T10:01:00+00:00",
            "2024-01-15T10:02:00+00:00",
            "2024-01-15T10:03:00+00:00",
        ]

    @pytest.mark.asyncio
    async def test_replay_stops_on_mid_stream_failure(self, mock_engine):
        """If replay fails mid-stream, remaining events stay buffered."""
        # Use a short retry interval for fast testing
        dispatcher = ComplianceEventDispatcher(mock_engine)
        dispatcher.RETRY_INTERVAL = 0.3

        # Always fail initially
        mock_engine.process_event.side_effect = ConnectionError("down")

        await dispatcher.start()

        # Dispatch 3 events
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:01:00+00:00")
        )
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:02:00+00:00")
        )
        await dispatcher.dispatch(
            _make_event(timestamp="2024-01-15T10:03:00+00:00")
        )

        # Wait for all events to be attempted and buffered
        await asyncio.sleep(0.5)
        assert len(dispatcher._buffer) == 3

        # Now make replay succeed for first event but always fail after
        replay_call_count = 0

        async def succeed_first_only(event: DetectionEvent) -> None:
            nonlocal replay_call_count
            replay_call_count += 1
            if replay_call_count >= 2:
                raise ConnectionError("mid-replay failure")

        mock_engine.process_event.side_effect = succeed_first_only

        # Wait for retry cycle to trigger replay
        await asyncio.sleep(0.5)
        await dispatcher.stop()

        # One event replayed successfully, two remain buffered
        # (the one that failed + the remaining one)
        assert len(dispatcher._buffer) == 2


class TestLifecycle:
    """Tests for start() and stop() lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_creates_worker_task(self, dispatcher):
        """start() should create a background worker task."""
        await dispatcher.start()
        assert dispatcher._worker_task is not None
        assert not dispatcher._worker_task.done()
        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_worker_task(self, dispatcher):
        """stop() should cancel the background task."""
        await dispatcher.start()
        task = dispatcher._worker_task
        await dispatcher.stop()
        assert task.cancelled() or task.done()
        assert dispatcher._worker_task is None

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self, dispatcher):
        """Calling start() twice should not create a second worker."""
        await dispatcher.start()
        first_task = dispatcher._worker_task
        await dispatcher.start()
        assert dispatcher._worker_task is first_task
        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, dispatcher):
        """Calling stop() without start() should not raise."""
        await dispatcher.stop()  # Should not raise
