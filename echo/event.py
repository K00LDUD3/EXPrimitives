# echo/event.py
from __future__ import annotations
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Any
from time import time


class Level(IntEnum):
    """
    Log levels in ascending order of severity.
    Used by sinks to filter events below a minimum level.
    """
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


MAX_LEVEL_LEN = 0
for level in Level:
    length = len(level.name)
    if length > MAX_LEVEL_LEN:
        MAX_LEVEL_LEN = length


class EventType(Enum):
    """
    Distinguishes the nature of the event.
    Sinks can route based on this — metrics go to metric sink,
    text goes to console/file sink.
    """
    TEXT = "text"     # human-readable log line
    METRIC = "metric"   # numeric observation — step, value, name
    SCOPE = "scope"    # context entry/exit marker


@dataclass(frozen=True)
class Event:
    """
    The atomic unit of Echo. Every logger call produces one Event.
    Immutable once created — sinks receive it, never modify it.

    Fields:
        timestamp:   Unix timestamp at moment of creation (float, seconds)
        level:       severity level
        event_type:  TEXT, METRIC, or SCOPE
        message:     human-readable description (empty string for pure metrics)
        payload:     arbitrary structured data attached to this event
                     for TEXT events: empty dict
                     for METRIC events: {"name": str, "value": float, "step": int}
                     for SCOPE events: {"scope": str, "action": "enter" | "exit"}
        run_id:      identifier of the current run — attached by Logger, not caller
        module:      dotted module path of the emitting subsystem e.g. "frame.lorenz"
        tags:        tuple of arbitrary string labels for filtering
        step:        global simulation/training step at time of emission
    """
    timestamp:  float
    level:      Level
    event_type: EventType
    message:    str
    payload:    dict[str, Any]
    run_id:     str = ""
    module:     str = ""
    tags:       tuple[str, ...] = ()
    step:       int | None = None

    def is_metric(self) -> bool:
        """Return True if this event carries a numeric metric observation."""
        return (self.event_type == EventType.METRIC)

    def is_text(self) -> bool:
        """Return True if this event is a human-readable log line."""
        return (self.event_type == EventType.TEXT)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize this event to a plain dict.
        Level and EventType become their string values.
        Used by FileSink to write JSONL lines.
        """
        ...

    @classmethod
    def now(
        cls,
        level:      Level,
        event_type: EventType,
        message:    str,
        payload:    dict[str, Any],
        run_id:     str = "",
        module:     str = "",
        tags:       tuple[str, ...] = (),
        step:       int | None = None,
    ) -> Event:
        """
        Construct an Event with timestamp set to the current time.
        This is the primary constructor — never set timestamp manually.

        Usage:
            event = Event.now(Level.INFO, EventType.TEXT, "step complete", {})
        """
        return cls(
            timestamp=time(),
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
            run_id=run_id,
            module=module,
            tags=tags,
            step=step
        )
