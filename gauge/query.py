from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from exprim.echo.event import Event, Level, EventType
from exprim.gauge.reader import load_events, resolve_paths

# sentinel for unset numeric bounds
UNSET = object()


class Query:
    """
    Fluent query interface for filtering and searching events from a single run.
    All filter methods return self so calls can be chained.
    Nothing is evaluated until collect() is called.

    Usage:
        results = gauge.query(run).scope("train_epoch").level(Level.WARNING).collect()
    """

    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self._filters: list[Callable[[Event], bool]] = []

    @classmethod
    def from_source(cls, source: Any) -> Query:
        """Build a Query from a ledger Run object or a Path to a run directory."""
        events_path, _ = resolve_paths(source)
        return cls(load_events(events_path))

    @classmethod
    def from_path(cls, path: Path) -> Query:
        """Build a Query directly from a JSONL file path."""
        return cls(load_events(path))

    def level(self, level: Level) -> Query:
        """Keep only events at or above a given level."""
        self._filters.append(lambda e: e.level.value >= level.value)
        return self

    def exact_level(self, level: Level) -> Query:
        """Keep only events at exactly a given level."""
        self._filters.append(lambda e: e.level == level)
        return self

    def event_type(self, event_type: EventType) -> Query:
        """Keep only events of a given type."""
        self._filters.append(lambda e: e.event_type == event_type)
        return self

    def steps(self, start: int, end: int) -> Query:
        """Keep only events whose step falls within start and end inclusive."""
        self._filters.append(
            lambda e: e.step is not None and start <= e.step <= end
        )
        return self

    def step_from(self, start: int) -> Query:
        """Keep only events at or after a given step."""
        self._filters.append(lambda e: e.step is not None and e.step >= start)
        return self

    def step_until(self, end: int) -> Query:
        """Keep only events at or before a given step."""
        self._filters.append(lambda e: e.step is not None and e.step <= end)
        return self

    def time_range(self, start: float, end: float) -> Query:
        """Keep only events whose timestamp falls within start and end."""
        self._filters.append(lambda e: start <= e.timestamp <= end)
        return self

    def module(self, module: str) -> Query:
        """Keep only events from an exact module name."""
        self._filters.append(lambda e: e.module == module)
        return self

    def module_startswith(self, prefix: str) -> Query:
        """Keep only events whose module starts with a given prefix."""
        self._filters.append(lambda e: e.module.startswith(prefix))
        return self

    def scope(self, scope: str) -> Query:
        """
        Keep only events emitted inside a given scope.
        Matches events whose module contains the scope string,
        and SCOPE marker events whose payload scope matches.
        """
        def _matches(e: Event) -> bool:
            if e.event_type == EventType.SCOPE:
                return scope in e.payload.get("scope", "")
            return scope in e.module
        self._filters.append(_matches)
        return self

    def tag(self, tag: str) -> Query:
        """Keep only events that carry a given tag."""
        self._filters.append(lambda e: tag in e.tags)
        return self

    def tags_any(self, tags: list[str]) -> Query:
        """Keep only events that carry at least one of the given tags."""
        self._filters.append(lambda e: any(t in e.tags for t in tags))
        return self

    def tags_all(self, tags: list[str]) -> Query:
        """Keep only events that carry all of the given tags."""
        self._filters.append(lambda e: all(t in e.tags for t in tags))
        return self

    def metric_name(self, name: str) -> Query:
        """Keep only metric events with a given name."""
        self._filters.append(
            lambda e: e.event_type == EventType.METRIC and e.payload.get("name") == name
        )
        return self

    def metric_value(self, condition: Callable[[float], bool]) -> Query:
        """
        Keep only metric events where the value satisfies a condition.

        Usage:
            .metric_value(lambda v: v > -5)
            .metric_value(lambda v: 0 < v < 1)
        """
        def _check(e: Event) -> bool:
            if e.event_type != EventType.METRIC:
                return False
            v = e.payload.get("value")
            return v is not None and condition(v)
        self._filters.append(_check)
        return self

    def contains(self, substring: str) -> Query:
        """Keep only text events whose message contains a substring."""
        self._filters.append(
            lambda e: e.event_type == EventType.TEXT and substring in e.message
        )
        return self

    def matches(self, pattern: str) -> Query:
        """Keep only text events whose message matches a regex pattern."""
        compiled = re.compile(pattern)
        self._filters.append(
            lambda e: e.event_type == EventType.TEXT and bool(compiled.search(e.message))
        )
        return self

    def fuzzy(self, keyword: str, threshold: float = 0.6) -> Query:
        """
        Keep only text events whose message approximately matches a keyword.
        Uses character overlap ratio as the similarity measure.
        threshold of 0.6 means 60 percent character overlap required.
        """
        keyword_lower = keyword.lower()

        def _fuzzy_match(message: str) -> bool:
            message_lower = message.lower()
            if keyword_lower in message_lower:
                return True
            common = sum(c in message_lower for c in keyword_lower)
            ratio  = common / max(len(keyword_lower), 1)
            return ratio >= threshold

        self._filters.append(
            lambda e: e.event_type == EventType.TEXT and _fuzzy_match(e.message)
        )
        return self

    def where(self, condition: Callable[[Event], bool]) -> Query:
        """Apply an arbitrary filter function to each event."""
        self._filters.append(condition)
        return self

    def not_module(self, module: str) -> Query:
        """Exclude events from a given module."""
        self._filters.append(lambda e: e.module != module)
        return self

    def not_scope(self, scope: str) -> Query:
        """Exclude events emitted inside a given scope."""
        self._filters.append(lambda e: scope not in e.module)
        return self

    def collect(self) -> list[Event]:
        """Evaluate all filters and return the matching events."""
        result = self._events
        for f in self._filters:
            result = [e for e in result if f(e)]
        return result

    def first(self) -> Event | None:
        """Return the first matching event or None."""
        results = self.collect()
        return results[0] if results else None

    def last(self) -> Event | None:
        """Return the last matching event or None."""
        results = self.collect()
        return results[-1] if results else None

    def nth(self, n: int) -> Event | None:
        """
        Return the Nth matching event (1-indexed) or None.
        nth(1) is equivalent to first().
        """
        results = self.collect()
        if n < 1 or n > len(results):
            return None
        return results[n - 1]

    def count(self) -> int:
        """Return the number of matching events."""
        return len(self.collect())

    def context(self, event: Event, before: int = 5, after: int = 5) -> list[Event]:
        """
        Return the N events before and after a given event in the unfiltered stream.
        Useful for understanding what happened around a warning or error.
        """
        try:
            idx = self._events.index(event)
        except ValueError:
            return []
        start = max(0, idx - before)
        end   = min(len(self._events), idx + after + 1)
        return self._events[start:end]

    def surrounding(self, n: int, before: int = 5, after: int = 5) -> list[Event]:
        """Return context around the Nth matching event."""
        event = self.nth(n)
        if event is None:
            return []
        return self.context(event, before, after)
