"""Async compliance event dispatcher with buffered retry semantics.

Dispatches DetectionEvent objects to the ComplianceEventEngine via a
non-blocking asyncio queue. Buffers events when the downstream engine
is unavailable and replays them in chronological order on reconnect.
"""

from __future__ import annotations

import asyncio
import collections
import logging
from typing import ClassVar, Protocol

from backend.core.pipeline_types import DetectionEvent

logger = logging.getLogger(__name__)


class ComplianceEventEngine(Protocol):
    """Protocol for the downstream compliance event engine."""

    async def process_event(self, event: DetectionEvent) -> None: ...


class ComplianceEventDispatcher:
    """Async event dispatcher with buffering and retry.

    Dispatches DetectionEvent objects to a ComplianceEventEngine via a
    non-blocking asyncio.Queue. When the engine is unavailable, events
    are buffered (up to BUFFER_CAPACITY) and retried every RETRY_INTERVAL
    seconds.
    """

    BUFFER_CAPACITY: ClassVar[int] = 100
    RETRY_INTERVAL: ClassVar[float] = 5.0
    DISPATCH_TIMEOUT: ClassVar[float] = 3.0

    def __init__(self, event_engine: ComplianceEventEngine) -> None:
        self._event_engine = event_engine
        self._queue: asyncio.Queue[DetectionEvent] = asyncio.Queue()
        self._buffer: collections.deque[DetectionEvent] = collections.deque(
            maxlen=self.BUFFER_CAPACITY
        )
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False

    async def dispatch(self, event: DetectionEvent) -> None:
        """Enqueue an event for async dispatch.

        Does nothing if the event has an empty detections list.
        """
        if not event.detections:
            return
        self._queue.put_nowait(event)

    async def start(self) -> None:
        """Start the background worker task."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """Stop the background worker task and clean up."""
        self._running = False
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def _worker(self) -> None:
        """Background worker that processes the event queue."""
        try:
            while self._running:
                # If we have buffered events, attempt replay first
                if self._buffer:
                    await self._replay_buffer()

                # Wait for new events from the queue
                try:
                    event = await asyncio.wait_for(
                        self._queue.get(), timeout=self.RETRY_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # No new events; loop back to check buffer/retry
                    continue

                # Try to dispatch the event
                await self._try_dispatch(event)
        except asyncio.CancelledError:
            raise

    async def _try_dispatch(self, event: DetectionEvent) -> None:
        """Attempt to dispatch a single event to the engine.

        On failure, buffer the event for later retry.
        """
        try:
            await asyncio.wait_for(
                self._event_engine.process_event(event),
                timeout=self.DISPATCH_TIMEOUT,
            )
        except Exception:
            self._add_to_buffer(event)

    async def _replay_buffer(self) -> None:
        """Replay buffered events in chronological order.

        Stops replaying on the first failure and resumes normal buffering.
        """
        # Sort buffer by timestamp for chronological replay
        sorted_events = sorted(self._buffer, key=lambda e: e.timestamp)
        self._buffer.clear()

        replayed_count = 0
        for event in sorted_events:
            try:
                await asyncio.wait_for(
                    self._event_engine.process_event(event),
                    timeout=self.DISPATCH_TIMEOUT,
                )
                replayed_count += 1
            except Exception:
                # Re-buffer the failed event and all remaining events
                self._add_to_buffer(event)
                for remaining in sorted_events[replayed_count + 1 :]:
                    self._add_to_buffer(remaining)
                break

        if replayed_count > 0:
            logger.info(
                "Successfully replayed %d buffered event(s)", replayed_count
            )

    def _add_to_buffer(self, event: DetectionEvent) -> None:
        """Add an event to the buffer, discarding oldest if full."""
        if len(self._buffer) >= self.BUFFER_CAPACITY:
            discarded = self._buffer.popleft()
            logger.warning(
                "Event buffer full (capacity=%d). Discarding oldest event "
                "with timestamp=%s",
                self.BUFFER_CAPACITY,
                discarded.timestamp,
            )
        self._buffer.append(event)
