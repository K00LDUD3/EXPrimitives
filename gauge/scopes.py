from __future__ import annotations

from pathlib import Path
from exprim.echo.event import Event, EventType
from exprim.gauge.reader import load_events, resolve_paths

# action strings used in scope event payloads
SCOPE_ENTER = "enter"
SCOPE_EXIT  = "exit"


def all_scope_names(events: list[Event]) -> list[str]:
    """Return a sorted list of all unique scope names present in the event stream."""
    names = set()
    for e in events:
        if e.event_type == EventType.SCOPE:
            scope = e.payload.get("scope", "")
            if scope:
                names.add(scope)
    return sorted(names)


def scope_entries(events: list[Event], scope: str) -> list[Event]:
    """Return all entry events for a given scope name."""
    return [
        e for e in events
        if e.event_type == EventType.SCOPE
        and e.payload.get("scope") == scope
        and e.payload.get("action") == SCOPE_ENTER
    ]


def scope_exits(events: list[Event], scope: str) -> list[Event]:
    """Return all exit events for a given scope name."""
    return [
        e for e in events
        if e.event_type == EventType.SCOPE
        and e.payload.get("scope") == scope
        and e.payload.get("action") == SCOPE_EXIT
    ]


def nth_entry(events: list[Event], scope: str, n: int) -> Event | None:
    """
    Return the Nth entry event for a given scope (1-indexed).
    Returns None if the scope was entered fewer than N times.
    """
    entries = scope_entries(events, scope)
    if n < 1 or n > len(entries):
        return None
    return entries[n - 1]


def entry_count(events: list[Event], scope: str) -> int:
    """Return how many times a scope was entered."""
    return len(scope_entries(events, scope))


def scope_durations(events: list[Event], scope: str) -> list[float]:
    """
    Return a list of durations in seconds for each complete entry-exit pair
    of a given scope. Incomplete pairs (entered but never exited) are ignored.
    """
    entries = scope_entries(events, scope)
    exits   = scope_exits(events, scope)
    pairs   = min(len(entries), len(exits))
    return [
        exits[i].timestamp - entries[i].timestamp
        for i in range(pairs)
    ]


def mean_duration(events: list[Event], scope: str) -> float | None:
    """Return the mean duration in seconds for a scope across all its executions."""
    durations = scope_durations(events, scope)
    if not durations:
        return None
    return sum(durations) / len(durations)


def total_duration(events: list[Event], scope: str) -> float:
    """Return total cumulative time spent inside a scope across all executions."""
    return sum(scope_durations(events, scope))


def slowest_execution(events: list[Event], scope: str) -> float | None:
    """Return the duration of the slowest single execution of a scope."""
    durations = scope_durations(events, scope)
    return max(durations) if durations else None


def fastest_execution(events: list[Event], scope: str) -> float | None:
    """Return the duration of the fastest single execution of a scope."""
    durations = scope_durations(events, scope)
    return min(durations) if durations else None


def events_inside_scope(events: list[Event], scope: str) -> list[Event]:
    """
    Return all non-scope events emitted while inside a given scope.
    Uses module field matching since events carry their scope context there.
    """
    return [
        e for e in events
        if e.event_type != EventType.SCOPE and scope in e.module
    ]


def errors_inside_scope(events: list[Event], scope: str) -> list[Event]:
    """Return all error events emitted inside a given scope."""
    from exprim.echo.event import Level
    return [
        e for e in events_inside_scope(events, scope)
        if e.level == Level.ERROR
    ]


def warnings_inside_scope(events: list[Event], scope: str) -> list[Event]:
    """Return all warning events emitted inside a given scope."""
    from exprim.echo.event import Level
    return [
        e for e in events_inside_scope(events, scope)
        if e.level == Level.WARNING
    ]


def scope_had_errors(events: list[Event], scope: str) -> bool:
    """Return True if any errors were logged inside a given scope."""
    return len(errors_inside_scope(events, scope)) > 0


def timing_report(events: list[Event]) -> list[dict]:
    """
    Build a timing report for all scopes in the event stream.
    Returns a list of dicts sorted by total duration descending.
    Each entry contains scope name, entry count, mean duration,
    total duration, slowest execution, and whether any errors occurred.
    """
    names = all_scope_names(events)
    report = []
    for name in names:
        durations = scope_durations(events, name)
        if not durations:
            continue
        report.append({
            "scope":            name,
            "entry_count":      entry_count(events, name),
            "mean_duration_s":  sum(durations) / len(durations),
            "total_duration_s": sum(durations),
            "slowest_s":        max(durations),
            "fastest_s":        min(durations),
            "had_errors":       scope_had_errors(events, name),
        })
    return sorted(report, key=lambda r: r["total_duration_s"], reverse=True)


def call_tree(events: list[Event]) -> dict:
    """
    Build a nested call tree from scope events.
    Each node is a dict with keys: name, entries, children.
    children is a dict of child scope name to child node.
    Nesting is inferred from the scope path separator " > ".
    """
    names = all_scope_names(events)
    tree: dict = {}

    for name in names:
        parts  = [p.strip() for p in name.split(">")]
        node   = tree
        for part in parts:
            if part not in node:
                node[part] = {
                    "name":     part,
                    "entries":  entry_count(events, name),
                    "children": {},
                }
            node = node[part]["children"]

    return tree
