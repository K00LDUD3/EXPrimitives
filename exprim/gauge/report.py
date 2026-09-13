from __future__ import annotations

from typing import Any

from exprim.gauge.reader import load_events, load_metrics, resolve_paths
from exprim.gauge import metrics as m
from exprim.gauge import scopes as sc
from exprim.gauge.query import Query
from exprim.echo.event import Level


def run_summary(source: Any, metric_names: list[str] | None = None) -> dict:
    """
    Full summary report for a single run.
    Includes metric summaries, scope timing, warning count, error count.
    If metric_names is None, all metrics found in the file are summarised.
    """
    events_path, metrics_path = resolve_paths(source)
    events  = load_events(events_path)
    mevents = load_metrics(metrics_path)

    if metric_names is None:
        metric_names = list({
            e.payload.get("name") for e in mevents
            if e.payload.get("name")
        })

    metric_summaries = {
        name: m.summary(m.extract(mevents, name), name=name)
        for name in metric_names
    }

    return {
        "run_id":          getattr(source, "run_id", str(events_path)),
        "total_events":    len(events),
        "warning_count":   len(Query(events).exact_level(Level.WARNING).collect()),
        "error_count":     len(Query(events).exact_level(Level.ERROR).collect()),
        "scope_timing":    sc.timing_report(events),
        "metrics":         metric_summaries,
    }


def error_report(source: Any) -> list[dict]:
    """
    Return all errors for a run with their step, module, message, and timestamp.
    Sorted by step ascending.
    """
    events_path, _ = resolve_paths(source)
    events  = load_events(events_path)
    errors  = Query(events).exact_level(Level.ERROR).collect()
    return [
        {
            "step":      e.step,
            "timestamp": e.timestamp,
            "module":    e.module,
            "message":   e.message,
            "tags":      list(e.tags),
        }
        for e in errors
    ]


def warning_report(source: Any) -> list[dict]:
    """
    Return all warnings for a run grouped by module.
    Returns list of dicts with module name and list of warning messages.
    """
    events_path, _ = resolve_paths(source)
    events   = load_events(events_path)
    warnings = Query(events).exact_level(Level.WARNING).collect()
    grouped: dict[str, list[str]] = {}
    for e in warnings:
        grouped.setdefault(e.module, []).append(e.message)
    return [
        {"module": module, "count": len(messages), "messages": messages}
        for module, messages in sorted(grouped.items())
    ]


def convergence_report(source: Any, metrics: list[str], tolerance: float = 0.01, window: int = 50) -> list[dict]:
    """
    Report convergence status for a set of metrics in a single run.
    Returns list of dicts with metric name, converged bool, convergence step,
    and whether the metric diverged after initially converging.
    """
    _, metrics_path = resolve_paths(source)
    mevents = load_metrics(metrics_path)
    results = []
    for name in metrics:
        series = m.extract(mevents, name)
        has_converged, conv_step = m.converged(series, tolerance, window)
        diverged = m.diverged_after_convergence(series, tolerance, window)
        results.append({
            "metric":                     name,
            "converged":                  has_converged,
            "convergence_step":           conv_step,
            "diverged_after_convergence": diverged,
        })
    return results


def cross_run_table(sources: list[Any], metric_names: list[str]) -> list[dict]:
    """
    Build a comparison table across N runs.
    Each row is one run. Columns are final values of each requested metric
    plus run metadata.
    Sorted by the first metric ascending.
    """
    from exprim.gauge.cross import CrossMetrics
    rows = []
    run_ids = [getattr(s, "run_id", str(s)) for s in sources]

    metric_data: dict[str, dict[str, float | None]] = {}
    for name in metric_names:
        cx = CrossMetrics(sources, name)
        metric_data[name] = cx.final_values()

    for run_id in run_ids:
        row: dict[str, Any] = {"run_id": run_id}
        for name in metric_names:
            row[name] = metric_data[name].get(run_id)
        rows.append(row)

    if rows and metric_names:
        rows.sort(key=lambda r: (r[metric_names[0]] is None, r[metric_names[0]]))

    return rows


def population_summary(sources: list[Any], metric_names: list[str], tolerance: float = 0.01, window: int = 50) -> dict:
    """
    Full population-level summary across N runs for a set of metrics.
    Includes ensemble statistics, convergence summary, and outlier detection.
    """
    from exprim.gauge.cross import CrossMetrics, CrossScopes, CrossQuery

    all_events = {}
    for source in sources:
        events_path, _ = resolve_paths(source)
        run_id = getattr(source, "run_id", str(events_path))
        all_events[run_id] = load_events(events_path)

    all_scope_names_set: set[str] = set()
    for events in all_events.values():
        all_scope_names_set.update(sc.all_scope_names(events))

    metric_summaries = {}
    for name in metric_names:
        cx = CrossMetrics(sources, name)
        metric_summaries[name] = cx.summary()

    n_runs      = len(sources)
    total_errors = {
        run_id: len(Query(events).exact_level(Level.ERROR).collect())
        for run_id, events in all_events.items()
    }

    return {
        "n_runs":            n_runs,
        "metrics":           metric_summaries,
        "runs_with_errors":  [rid for rid, count in total_errors.items() if count > 0],
        "runs_clean":        [rid for rid, count in total_errors.items() if count == 0],
        "scopes_seen":       sorted(all_scope_names_set),
    }
