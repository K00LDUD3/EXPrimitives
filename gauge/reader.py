from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

from exprim.echo.event import Event, Level, EventType

# default encoding for all file reads
ENCODING = "utf-8"


def load_events(path: Path) -> list[Event]:
    """Load all events from a JSONL file into memory as a list."""
    return list(stream_events(path))


def stream_events(path: Path) -> Generator[Event, None, None]:
    """
    Lazily read events from a JSONL file one at a time.
    Use this for large files where loading everything into memory is not practical.
    """
    if not path.exists():
        return
    with open(path, encoding=ENCODING) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield _event_from_dict(json.loads(line))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue


def load_metrics(path: Path) -> list[Event]:
    """Load only metric events from a JSONL file."""
    return [e for e in load_events(path) if e.event_type == EventType.METRIC]


def load_text(path: Path) -> list[Event]:
    """Load only text events from a JSONL file."""
    return [e for e in load_events(path) if e.event_type == EventType.TEXT]


def load_scopes(path: Path) -> list[Event]:
    """Load only scope marker events from a JSONL file."""
    return [e for e in load_events(path) if e.event_type == EventType.SCOPE]


def load_warnings(path: Path) -> list[Event]:
    """Load all WARNING level events."""
    return [e for e in load_events(path) if e.level == Level.WARNING]


def load_errors(path: Path) -> list[Event]:
    """Load all ERROR level events."""
    return [e for e in load_events(path) if e.level == Level.ERROR]


def tail_events(path: Path, n: int = 100) -> list[Event]:
    """Return the last N events from a JSONL file."""
    return load_events(path)[-n:]


def resolve_paths(source: Path | object) -> tuple[Path, Path]:
    """
    Given either a ledger Run object or a directory Path, return
    the (events_path, metrics_path) tuple for that run.
    Gauge accepts both so it works with or without Ledger.
    """
    if isinstance(source, Path):
        from exprim.ledger.paths import events_file, metrics_file
        return events_file(source), metrics_file(source)
    else:
        return source.logs_path(), source.metrics_path()


def _event_from_dict(d: dict) -> Event:
    """Reconstruct an Event from a plain dict read from JSONL."""
    return Event(
        timestamp  = d["timestamp"],
        level      = Level[d["level"].strip()],
        event_type = EventType(d["event_type"]),
        message    = d.get("message", ""),
        payload    = d.get("payload", {}),
        run_id     = d.get("run_id", ""),
        module     = d.get("module", ""),
        tags       = tuple(d.get("tags", [])),
        step       = d.get("step"),
    )
