from __future__ import annotations

import math
#from pathlib import Path
from typing import Any, Callable

from exprim.echo.event import Event, EventType, Level
from exprim.gauge.reader import load_events, load_metrics, resolve_paths
from exprim.gauge import metrics as m
from exprim.gauge import scopes as sc
from exprim.gauge.query import Query

# minimum runs needed for population statistics
MIN_POPULATION = 2


def _load_all(sources: list[Any]) -> dict[str, list[Event]]:
    """Load all events for each source keyed by run_id or path string."""
    result = {}
    for source in sources:
        events_path, _ = resolve_paths(source)
        run_id = getattr(source, "run_id", str(events_path))
        result[run_id] = load_events(events_path)
    return result


def _load_all_metrics(sources: list[Any]) -> dict[str, list[Event]]:
    """Load metric events only for each source keyed by run_id or path string."""
    result = {}
    for source in sources:
        _, metrics_path = resolve_paths(source)
        run_id = getattr(source, "run_id", str(metrics_path))
        result[run_id] = load_metrics(metrics_path)
    return result


class CrossQuery:
    """
    Fluent cross-run query interface.
    Applies filters across N runs simultaneously.
    All filter methods return self for chaining.
    Nothing is evaluated until per_run() or aggregate() is called.
    """

    def __init__(self, sources: list[Any]) -> None:
        self._sources = sources
        self._run_events = _load_all(sources)
        self._filters: list[Callable[[Event], bool]] = []

    def level(self, level: Level) -> CrossQuery:
        """Keep only events at or above a given level across all runs."""
        self._filters.append(lambda e: e.level.value >= level.value)
        return self

    def scope(self, scope: str) -> CrossQuery:
        """Keep only events inside a given scope across all runs."""
        def _matches(e: Event) -> bool:
            if e.event_type == EventType.SCOPE:
                return scope in e.payload.get("scope", "")
            return scope in e.module
        self._filters.append(_matches)
        return self

    def module(self, module: str) -> CrossQuery:
        """Keep only events from a given module across all runs."""
        self._filters.append(lambda e: e.module == module)
        return self

    def steps(self, start: int, end: int) -> CrossQuery:
        """Keep only events in a step range across all runs."""
        self._filters.append(
            lambda e: e.step is not None and start <= e.step <= end
        )
        return self

    def contains(self, substring: str) -> CrossQuery:
        """Keep only text events containing a substring across all runs."""
        self._filters.append(
            lambda e: e.event_type == EventType.TEXT and substring in e.message
        )
        return self

    def metric_name(self, name: str) -> CrossQuery:
        """Keep only metric events with a given name across all runs."""
        self._filters.append(
            lambda e: e.event_type == EventType.METRIC and e.payload.get("name") == name
        )
        return self
    
    #_: to define arbitrary callables, use this
    def where(self, condition: Callable[[Event], bool]) -> CrossQuery:
        """Apply an arbitrary filter to events across all runs."""
        self._filters.append(condition)
        return self

    def _apply_filters(self, events: list[Event]) -> list[Event]:
        result = events
        for f in self._filters:
            result = [e for e in result if f(e)]
        return result

    def per_run(self) -> dict[str, list[Event]]:
        """Return filtered events grouped by run_id."""
        return {
            run_id: self._apply_filters(events)
            for run_id, events in self._run_events.items()
        }

    def counts(self) -> dict[str, int]:
        """Return the count of matching events per run."""
        return {run_id: len(events) for run_id, events in self.per_run().items()}

    def find_nth(self, n: int, match: str | None = None, scope: str | None = None, metric: str | None = None, condition: Callable[[float], bool] | None = None) -> dict[str, Event | None]:
        """
        Find the Nth occurrence of a match condition per run.
        match is a substring search on message text.
        scope finds the Nth scope entry.
        metric with condition finds the Nth metric event satisfying the condition.
        Returns dict of run_id to the Nth matching event or None if not found.
        """
        results = {}
        for run_id, events in self._run_events.items():
            q = Query(events)
            if match is not None:
                q = q.contains(match)
            if scope is not None:
                q = q.scope(scope)
            if metric is not None:
                q = q.metric_name(metric)
            if condition is not None:
                q = q.metric_value(condition)
            results[run_id] = q.nth(n)
        return results

    def first_occurrence(self, match: str | None = None, scope: str | None = None) -> dict[str, Event | None]:
        """Return the first occurrence of a match or scope entry per run."""
        return self.find_nth(1, match=match, scope=scope)

    def last_occurrence(self) -> dict[str, list[Event]]:  # match: str | None = None,
        """Return the last matching event per run."""
        result = {}
        for run_id, events in self.per_run().items():
            result[run_id] = events[-1] if events else None
        return result

    def runs_without_match(self, match: str | None = None, scope: str | None = None) -> list[str]:
        """Return run_ids where the condition never occurred."""
        hits = self.find_nth(1, match=match, scope=scope)
        return [run_id for run_id, event in hits.items() if event is None]

    def runs_with_match(self, match: str | None = None, scope: str | None = None) -> list[str]:
        """Return run_ids where the condition occurred at least once."""
        hits = self.find_nth(1, match=match, scope=scope)
        return [run_id for run_id, event in hits.items() if event is not None]


class CrossMetrics:
    """
    Population-level metric analysis across N runs.
    Accepts a list of ledger Run objects or Paths.
    """

    def __init__(self, sources: list[Any], name: str) -> None:
        self._sources = sources
        self._name    = name
        self._series: dict[str, list[tuple[int, float]]] = {}
        for source in sources:
            _, metrics_path = resolve_paths(source)
            run_id = getattr(source, "run_id", str(metrics_path))
            self._series[run_id] = m.extract(load_metrics(metrics_path), name)

    def per_run(self) -> dict[str, list[tuple[int, float]]]:
        """Return the full metric series for each run."""
        return dict(self._series)

    def final_values(self) -> dict[str, float | None]:
        """Return the final metric value for each run."""
        return {
            run_id: (series[-1][1] if series else None)
            for run_id, series in self._series.items()
        }

    def mean_across_runs(self) -> float | None:
        """Mean of final values across all runs."""
        finals = [v for v in self.final_values().values() if v is not None]
        return sum(finals) / len(finals) if finals else None

    def std_across_runs(self) -> float | None:
        """Standard deviation of final values across all runs."""
        finals = [v for v in self.final_values().values() if v is not None]
        if len(finals) < MIN_POPULATION:
            return None
        mu = sum(finals) / len(finals)
        return math.sqrt(sum((v - mu) ** 2 for v in finals) / len(finals))

    def min_across_runs(self) -> tuple[str, float] | None:
        """Return (run_id, value) of the run with the lowest final value."""
        finals = {k: v for k, v in self.final_values().items() if v is not None}
        if not finals:
            return None
        best = min(finals, key=lambda k: finals[k])
        return best, finals[best]

    def max_across_runs(self) -> tuple[str, float] | None:
        """Return (run_id, value) of the run with the highest final value."""
        finals = {k: v for k, v in self.final_values().items() if v is not None}
        if not finals:
            return None
        best = max(finals, key=lambda k: finals[k])
        return best, finals[best]

    def percentiles(self, qs: list[float]) -> dict[float, float]:
        """
        Compute percentiles of final values across runs.
        qs is a list of percentile values between 0 and 100.
        Returns dict of percentile to value.
        """
        finals = sorted(v for v in self.final_values().values() if v is not None)
        if not finals:
            return {q: 0.0 for q in qs}
        result = {}
        for q in qs:
            idx = (q / 100.0) * (len(finals) - 1)
            lo  = int(idx)
            hi  = min(lo + 1, len(finals) - 1)
            result[q] = finals[lo] + (idx - lo) * (finals[hi] - finals[lo])
        return result

    def coefficient_of_variation(self) -> float | None:
        """
        Coefficient of variation across runs.
        Std divided by mean. Measures consistency across runs.
        A lower value means runs are more consistent with each other.
        """
        mu = self.mean_across_runs()
        s  = self.std_across_runs()
        if mu is None or s is None or mu == 0:
            return None
        return s / abs(mu)

    def rank_by_final(self, ascending: bool = True) -> list[tuple[str, float]]:
        """
        Rank runs by their final metric value.
        Returns list of (run_id, value) sorted ascending by default.
        """
        finals = [(k, v) for k, v in self.final_values().items() if v is not None]
        return sorted(finals, key=lambda x: x[1], reverse=not ascending)

    def rank_by_best(self, ascending: bool = True) -> list[tuple[str, float]]:
        """
        Rank runs by their best metric value ever achieved.
        Best means minimum if ascending, maximum if descending.
        """
        results = []
        for run_id, series in self._series.items():
            if not series:
                continue
            best = min(series, key=lambda x: x[1]) if ascending else max(series, key=lambda x: x[1])
            results.append((run_id, best[1]))
        return sorted(results, key=lambda x: x[1], reverse=not ascending)

    def convergence_per_run(self, tolerance: float = 0.01, window: int = 50) -> dict[str, dict]:
        """
        Check convergence for each run.
        Returns dict of run_id to convergence result dict containing
        converged bool, convergence_step, and diverged_after_convergence bool.
        """
        results = {}
        for run_id, series in self._series.items():
            has_converged, conv_step = m.converged(series, tolerance, window)
            diverged = m.diverged_after_convergence(series, tolerance, window)
            results[run_id] = {
                "converged": has_converged,
                "convergence_step": conv_step,
                "diverged_after_convergence": diverged,
            }
        return results

    def fastest_convergence(self, tolerance: float = 0.01, window: int = 50) -> tuple[str, int] | None:
        """Return (run_id, step) of the run that converged earliest."""
        conv = self.convergence_per_run(tolerance, window)
        candidates = [
            (run_id, r["convergence_step"])
            for run_id, r in conv.items()
            if r["converged"] and r["convergence_step"] is not None
        ]
        return min(candidates, key=lambda x: x[1]) if candidates else None

    def slowest_convergence(self, tolerance: float = 0.01, window: int = 50) -> tuple[str, int] | None:
        """Return (run_id, step) of the run that converged latest."""
        conv = self.convergence_per_run(tolerance, window)
        candidates = [
            (run_id, r["convergence_step"])
            for run_id, r in conv.items()
            if r["converged"] and r["convergence_step"] is not None
        ]
        return max(candidates, key=lambda x: x[1]) if candidates else None

    def outliers(self, k: float = 2.0) -> list[str]:
        """
        Return run_ids whose final value deviates more than k standard deviations
        from the ensemble mean. These are statistical outlier runs.
        """
        mu = self.mean_across_runs()
        s  = self.std_across_runs()
        if mu is None or s is None or s == 0:
            return []
        finals = self.final_values()
        return [
            run_id for run_id, v in finals.items()
            if v is not None and abs(v - mu) > k * s
        ]

    def first_crossing_per_run(self, threshold: float, direction: str = "above") -> dict[str, tuple[int, float] | None]:
        """Return the first threshold crossing (step, value) per run."""
        return {
            run_id: m.first_crossing(series, threshold, direction)
            for run_id, series in self._series.items()
        }

    def nth_crossing_per_run(self, threshold: float, n: int, direction: str = "above") -> dict[str, tuple[int, float] | None]:
        """Return the Nth threshold crossing per run."""
        return {
            run_id: m.nth_crossing(series, threshold, n, direction)
            for run_id, series in self._series.items()
        }

    def envelope(self) -> dict[str, list[tuple[int, float]]]:
        """
        Compute the ensemble envelope across runs aligned by step.
        Returns dict with keys mean, upper (mean+std), lower (mean-std)
        each as a list of (step, value) pairs.
        All series are aligned to the common steps present in all runs.
        """
        all_steps = sorted(
            set(s for series in self._series.values() for s, _ in series)
        )
        mean_curve  = []
        upper_curve = []
        lower_curve = []

        for step in all_steps:
            vals = []
            for series in self._series.values():
                point = next(((s, v) for s, v in series if s == step), None)
                if point:
                    vals.append(point[1])
            if len(vals) < MIN_POPULATION:
                continue
            mu = sum(vals) / len(vals)
            s  = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
            mean_curve.append((step, mu))
            upper_curve.append((step, mu + s))
            lower_curve.append((step, mu - s))

        return {"mean": mean_curve, "upper": upper_curve, "lower": lower_curve}

    def summary(self, percentile_intervals = [5,25,50,75,95]) -> dict:
        """
        Return a population-level summary of this metric across all runs.
        """
        pcts = self.percentiles(percentile_intervals)
        conv = self.convergence_per_run()
        n_converged = sum(1 for r in conv.values() if r["converged"])
        best = self.rank_by_final(ascending=True)
        
        #res = {}
        res = {
            "metric": self._name,
            "n_runs": len(self._series),
            "mean": self.mean_across_runs(),
            "std": self.std_across_runs(),
            "cv": self.coefficient_of_variation(),
           # "p5": pcts.get(5),
           # "p25":pcts.get(25),
           # "p50":                   pcts.get(50),
           # "p75":                   pcts.get(75),
           # "p95":                   pcts.get(95),
            "n_converged": n_converged,
            "best_run": best[0][0] if best else None,
            "best_value": best[0][1] if best else None,
            "outlier_run_ids": self.outliers(),
        }

        res.update({f"p{i}": k for i, k in enumerate(pcts)})
        return res

class CrossScopes:
    """Population-level scope analysis across N runs."""

    def __init__(self, sources: list[Any]) -> None:
        self._run_events = _load_all(sources)

    def entry_counts(self, scope: str) -> dict[str, int]:
        """Return how many times a scope was entered per run."""
        return {
            run_id: sc.entry_count(events, scope)
            for run_id, events in self._run_events.items()
        }

    def mean_entry_count(self, scope: str) -> float | None:
        """Mean number of times a scope was entered across runs."""
        counts = list(self.entry_counts(scope).values())
        return sum(counts) / len(counts) if counts else None

    def mean_duration(self, scope: str) -> float | None:
        """Mean duration of a scope averaged across all runs and executions."""
        all_durations = []
        for events in self._run_events.values():
            all_durations.extend(sc.scope_durations(events, scope))
        if not all_durations:
            return None
        return sum(all_durations) / len(all_durations)

    def slowest_run(self, scope: str) -> tuple[str, float] | None:
        """Return (run_id, total_duration) of the run that spent the most time in a scope."""
        totals = {
            run_id: sc.total_duration(events, scope)
            for run_id, events in self._run_events.items()
        }
        if not totals:
            return None
        worst = max(totals, key=lambda k: totals[k])
        return worst, totals[worst]

    def nth_entry_per_run(self, scope: str, n: int) -> dict[str, Event | None]:
        """Return the Nth scope entry event per run."""
        return {
            run_id: sc.nth_entry(events, scope, n)
            for run_id, events in self._run_events.items()
        }

    def runs_with_errors_in_scope(self, scope: str) -> list[str]:
        """Return run_ids where errors were logged inside a given scope."""
        return [
            run_id for run_id, events in self._run_events.items()
            if sc.scope_had_errors(events, scope)
        ]

    def runs_never_entered_scope(self, scope: str) -> list[str]:
        """Return run_ids where a scope was never entered."""
        return [
            run_id for run_id, count in self.entry_counts(scope).items()
            if count == 0
        ]

    def runs_entered_more_than(self, scope: str, n: int) -> list[str]:
        """Return run_ids where a scope was entered more than N times."""
        return [
            run_id for run_id, count in self.entry_counts(scope).items()
            if count > n
        ]

    def timing_report(self, scope: str) -> dict:
        """Population timing summary for a scope across all runs."""
        all_durations = []
        for events in self._run_events.values():
            all_durations.extend(sc.scope_durations(events, scope))
        if not all_durations:
            return {"scope": scope, "n_runs": len(self._run_events)}
        mu = sum(all_durations) / len(all_durations)
        s  = math.sqrt(sum((d - mu) ** 2 for d in all_durations) / len(all_durations))
        return {
            "scope": scope,
            "n_runs": len(self._run_events),
            "mean_duration_s": mu,
            "std_duration_s": s,
            "min_duration_s": min(all_durations),
            "max_duration_s": max(all_durations),
            "total_executions": len(all_durations),
            "runs_with_errors": len(self.runs_with_errors_in_scope(scope)),
        }
