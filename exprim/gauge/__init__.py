from exprim.gauge.query import Query
from exprim.gauge.cross import CrossQuery, CrossMetrics, CrossScopes
from exprim.gauge import reader
from exprim.gauge import metrics
from exprim.gauge import scopes
from exprim.gauge import cross
from exprim.gauge import report
from exprim.gauge import export
from typing import Any


def query(source: Any) -> Query:
    """
    Start a fluent query on a single run.
    source can be a ledger Run object or a Path to a run directory.

    Usage:
        gauge.query(run).scope("train").level(Level.WARNING).collect()
    """
    return Query.from_source(source)


def cross(sources: list[Any]) -> CrossQuery:
    """
    Start a fluent cross-run query across N runs.
    sources is a list of ledger Run objects or Paths.

    Usage:
        gauge.cross(runs).scope("train").contains("nan").per_run()
    """
    return CrossQuery(sources)


def metric(source: Any, name: str) -> CrossMetrics:
    """
    Start a single-run metric analysis wrapped in CrossMetrics for a single source.
    Convenience wrapper so the same API works for one or many runs.
    """
    return CrossMetrics([source], name)


def cross_metric(sources: list[Any], name: str) -> CrossMetrics:
    """
    Start a population-level metric analysis across N runs.

    Usage:
        gauge.cross_metric(runs, "reward").outliers(k=2.0)
    """
    return CrossMetrics(sources, name)


def cross_scopes(sources: list[Any]) -> CrossScopes:
    """
    Start a population-level scope analysis across N runs.

    Usage:
        gauge.cross_scopes(runs).timing_report("train_epoch")
    """
    return CrossScopes(sources)


__all__ = [
    "query",
    "cross",
    "metric",
    "cross_metric",
    "cross_scopes",
    "Query",
    "CrossQuery",
    "CrossMetrics",
    "CrossScopes",
    "reader",
    "metrics",
    "scopes",
    "report",
    "export",
]
