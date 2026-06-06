# echo/buffer.py
from __future__ import annotations
import threading
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sinks import Sink
from .event import Event


class EventBuffer:
    """
    A thread-safe buffer that decouples event emission from sink writes.

    At high simulation frequencies (500Hz+), synchronous sink writes
    (especially file I/O) will bottleneck the simulation loop.
    EventBuffer accepts events instantly onto an in-memory queue and
    drains them to sinks on a background thread.

    Usage:
        buffer = EventBuffer(sinks=[console_sink, file_sink], maxsize=10000)
        buffer.start()
        buffer.put(event)    # non-blocking, returns immediately
        buffer.stop()        # drains remaining events then shuts down

    Args:
        sinks:    list of sinks to drain events into
        maxsize:  maximum number of events held in memory before
                  put() blocks. Prevents unbounded memory growth.
                  Default 10000 is safe for most simulation workloads.
    """

    def __init__(
        self,
        sinks: list[Sink],
        maxsize: int = 10000,
    ) -> None:
        ...

    def start(self) -> None:
        """
        Start the background drain thread.
        Must be called before put().
        Raises RuntimeError if called more than once.
        """
        ...

    def put(self, event: Event) -> None:
        """
        Add an event to the buffer.
        Non-blocking if buffer is below maxsize.
        Blocks if buffer is full — applies natural backpressure
        rather than silently dropping events.
        """
        ...

    def stop(self) -> None:
        """
        Signal the drain thread to stop after emptying the buffer.
        Blocks until all buffered events have been written to sinks.
        Calls flush() and close() on all sinks after draining.
        """
        ...

    def _drain_loop(self) -> None:
        """
        Internal method run on the background thread.
        Continuously pulls events from the queue and emits to all sinks.
        Exits cleanly when stop() is called and queue is empty.
        Never call this directly.
        """
        ...

    def stats(self) -> dict[str, int]:
        """
        Return current buffer statistics.

        Returns:
            {
                "queued":   number of events currently in buffer,
                "emitted":  total events successfully written to sinks,
                "dropped":  total events dropped due to sink errors
            }
        """
        ...
