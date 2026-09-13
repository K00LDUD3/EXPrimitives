# echo/sinks.py
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable
from .event import Event, Level
from .formatter import Formatter
from sys import stdout
from json import dumps as json__dumps


@runtime_checkable
class Sink(Protocol):
    """
    Protocol that all sinks must satisfy.
    A sink receives events and writes them somewhere.

    runtime_checkable means you can do isinstance(obj, Sink) at runtime
    to verify a passed object is a valid sink before registering it.

    Any object with an emit() method and a min_level attribute satisfies
    this protocol — no inheritance required.
    """
    min_level: Level

    def emit(self, event: Event) -> None:
        """
        Receive and handle one event.
        Must never raise — swallow errors internally and warn if needed.
        Called by Logger for every event that passes the level filter.
        """
        ...

    def flush(self) -> None:
        """
        Force any buffered writes to their destination.
        Called by Logger on close or on explicit flush request.
        No-op for sinks that don't buffer.
        """
        ...

    def close(self) -> None:
        """
        Release any held resources (open file handles, connections).
        Called once at end of run. Sink should not be used after close().
        """
        ...

class ConsoleSink(Sink):
    """
    Writes formatted events to stdout.
    Uses Formatter to convert events to strings before printing.

    Args:
        min_level:  only events at or above this level are emitted
        formatter:  Formatter instance used for rendering
                    defaults to Formatter() if not provided
    """

    def __init__(
        self,
        min_level: Level = Level.INFO,
        formatter: Formatter | None = None,
        silent: bool = False,
    ) -> None:
        self.silent: bool = silent
        self.min_level: Level = min_level
        self.formatter: Formatter = formatter if formatter is not None else Formatter()

    def emit(self, event: Event) -> None:
        """
        Format the event and print to stdout.
        Skips events below min_level or silent.
        """
        if (event.level.value < self.min_level.value or self.silent):
            return
        formatted = self.formatter.format(event)
        print(formatted)

    def flush(self) -> None:
        """Flush stdout."""
        stdout.flush()

    def close(self) -> None:
        """No-op — stdout is not owned by this sink."""
        pass


class FileSink(Sink):
    """
    Writes events to a JSONL file (one JSON object per line).
    JSONL is preferred over plain text because it is:
    - trivially parseable line by line
    - grep-friendly
    - directly loadable into pandas / polars for analysis

    Opens the file on construction, closes on close().

    Args:
        path:       absolute path to the output .jsonl file
        min_level:  only events at or above this level are written
        buffer_size: number of events to buffer before flushing to disk
                     0 means flush every event (safe but slow)
    """

    def __init__(
        self,
        path: Path,
        min_level: Level = Level.DEBUG,
        buffer_size: int = 0,
        silent: bool = False,
    ) -> None:
        self.silent = silent
        self.min_level: Level = min_level
        self.path: Path = path  #PATH: extra
        self._buffer: list = []
        self.buffer_size: int = buffer_size
        self._f = open(path, 'w')

    def emit(self, event: Event) -> None:
        """
        Serialize event to JSON and write as one line to the file.
        Respects buffer_size — only flushes when buffer is full.
        Skips events below min_level or silent.
        """
        if event.level.value < self.min_level.value or self.silent:
            return

        serialized = json__dumps(event.to_dict())

        if self.buffer_size == 0:
            self._f.write(serialized + "\n")
            self._f.flush()
        else:
            self._buffer.append(serialized)
            if len(self._buffer) >= self.buffer_size:
                self.flush()

    def flush(self) -> None:
        """Force write any buffered lines to disk."""
        if self._buffer:
            self._f.write("\n".join(self._buffer) + "\n")
            self._f.flush()
            self._buffer.clear()


    def close(self) -> None:
        """Flush remaining buffer and close the file handle."""
        self._f.close()
