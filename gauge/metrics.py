from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from exprim.echo.event import Event, EventType
from exprim.gauge.reader import load_metrics, resolve_paths

# minimum number of points needed for statistical operations
MIN_STAT_POINTS = 2


def extract(events: list[Event], name: str) -> list[tuple[int, float]]:
    """
    Extract a named metric as a list of (step, value) pairs sorted by step.
    Filters to metric events only and skips events with no step or value.
    """
    results = []
    for e in events:
        if e.event_type != EventType.METRIC:
            continue
        if e.payload.get("name") != name:
            continue
        step  = e.step
        value = e.payload.get("value")
        if step is not None and value is not None:
            results.append((step, float(value)))
    return sorted(results, key=lambda x: x[0])


def extract_from_source(source: object | Path, name: str) -> list[tuple[int, float]]:
    """Extract a named metric from a ledger Run or run directory Path."""
    _, metrics_path = resolve_paths(source)
    return extract(load_metrics(metrics_path), name)


def values(series: list[tuple[int, float]]) -> list[float]:
    """Return just the values from a step-value series."""
    return [v for _, v in series]


def steps(series: list[tuple[int, float]]) -> list[int]:
    """Return just the steps from a step-value series."""
    return [s for s, _ in series]


def downsample(series: list[tuple[int, float]], every: int) -> list[tuple[int, float]]:
    """Keep only every Nth point from a series."""
    return series[::every]


def rolling_mean(series: list[tuple[int, float]], window: int) -> list[tuple[int, float]]:
    """Compute rolling mean over a window of points."""
    if len(series) < window:
        return series

    result = []

    for i in range(window - 1, len(series)):
        window_vals = [v for _, v in series[i - window + 1: i + 1]]
        result.append((series[i][0], sum(window_vals) / window))
    return result


def rolling_std(series: list[tuple[int, float]], window: int) -> list[tuple[int, float]]:
    """Compute rolling standard deviation over a window of points."""
    if len(series) < window:
        return []
    result = []
    for i in range(window - 1, len(series)):
        window_vals = [v for _, v in series[i - window + 1: i + 1]]
        mean = sum(window_vals) / window
        variance = sum((v - mean) ** 2 for v in window_vals) / window
        result.append((series[i][0], math.sqrt(variance)))
    return result


def rolling_min(series: list[tuple[int, float]], window: int) -> list[tuple[int, float]]:
    """Compute rolling minimum over a window of points."""
    result = []
    for i in range(window - 1, len(series)):
        window_vals = [v for _, v in series[i - window + 1: i + 1]]
        result.append((series[i][0], min(window_vals)))
    return result


def rolling_max(series: list[tuple[int, float]], window: int) -> list[tuple[int, float]]:
    """Compute rolling maximum over a window of points."""
    result = []
    for i in range(window - 1, len(series)):
        window_vals = [v for _, v in series[i - window + 1: i + 1]]
        result.append((series[i][0], max(window_vals)))
    return result


def ema(series: list[tuple[int, float]], alpha: float = 0.1) -> list[tuple[int, float]]:
    """
    Exponential moving average with smoothing factor alpha.
    alpha closer to 1 means less smoothing, closer to 0 means more smoothing.
    """
    if not series:
        return []
    result = [series[0]]
    for i in range(1, len(series)):
        smoothed = alpha * series[i][1] + (1 - alpha) * result[-1][1]
        result.append((series[i][0], smoothed))
    return result


def mean(series: list[tuple[int, float]]) -> float | None:
    """Mean of all values in a series."""
    vals = values(series)
    return sum(vals) / len(vals) if vals else None


def std(series: list[tuple[int, float]]) -> float | None:
    """Standard deviation of all values in a series."""
    vals = values(series)
    if len(vals) < MIN_STAT_POINTS:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def minimum(series: list[tuple[int, float]]) -> tuple[int, float] | None:
    """Return the (step, value) pair with the minimum value."""
    return min(series, key=lambda x: x[1]) if series else None


def maximum(series: list[tuple[int, float]]) -> tuple[int, float] | None:
    """Return the (step, value) pair with the maximum value."""
    return max(series, key=lambda x: x[1]) if series else None


def final(series: list[tuple[int, float]]) -> tuple[int, float] | None:
    """Return the last (step, value) pair."""
    return series[-1] if series else None


def integral(series: list[tuple[int, float]]) -> float:
    """
    Approximate the area under the metric curve using the trapezoidal rule.
    Useful for computing cumulative reward or total control effort.
    """
    if len(series) < MIN_STAT_POINTS:
        return 0.0
    total = 0.0
    for i in range(1, len(series)):
        dx = series[i][0] - series[i - 1][0]
        dy = (series[i][1] + series[i - 1][1]) / 2.0
        total += dx * dy
    return total


def first_crossing(series: list[tuple[int, float]], threshold: float, direction: str = "above") -> tuple[int, float] | None:
    """
    Find the first point where the metric crosses a threshold.
    direction is either above meaning value goes above threshold
    or below meaning value goes below threshold.
    """
    for step, value in series:
        if direction == "above" and value >= threshold:
            return step, value
        if direction == "below" and value <= threshold:
            return step, value
    return None


def nth_crossing(series: list[tuple[int, float]], threshold: float, n: int, direction: str = "above") -> tuple[int, float] | None:
    """Find the Nth time a metric crosses a threshold in a given direction."""
    count = 0
    for step, value in series:
        crossed = (direction == "above" and value >= threshold) or \
                  (direction == "below" and value <= threshold)
        if crossed:
            count += 1
            if count == n:
                return step, value
    return None


def converged(series: list[tuple[int, float]], tolerance: float, window: int) -> tuple[bool, int | None]:
    """
    Check whether a metric has converged.
    Convergence means the std of the last window points is below tolerance.
    Returns (has_converged, step_of_convergence).
    """
    if len(series) < window:
        return False, None
    for i in range(window - 1, len(series)):
        window_vals = [v for _, v in series[i - window + 1: i + 1]]
        m           = sum(window_vals) / window
        variance    = sum((v - m) ** 2 for v in window_vals) / window
        if math.sqrt(variance) <= tolerance:
            return True, series[i - window + 1][0]
    return False, None


def diverged_after_convergence(series: list[tuple[int, float]], tolerance: float, window: int) -> bool:
    """
    Check whether a metric converged and then diverged again.
    Useful for detecting instability late in training.
    """
    has_converged, convergence_step = converged(series, tolerance, window)
    if not has_converged or convergence_step is None:
        return False
    post = [(s, v) for s, v in series if s > convergence_step]
    if len(post) < window:
        return False
    post_std = std(post)
    return post_std is not None and post_std > tolerance


def spikes(series: list[tuple[int, float]], k: float = 3.0) -> list[tuple[int, float]]:
    """
    Find points that deviate more than k standard deviations from the mean.
    Returns a list of (step, value) pairs identified as spikes.
    """
    m = mean(series)
    s = std(series)
    if m is None or s is None or s == 0:
        return []
    return [(step, value) for step, value in series if abs(value - m) > k * s]


def nans(series: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Find all points where the value is NaN."""
    return [(s, v) for s, v in series if math.isnan(v)]


def infs(series: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Find all points where the value is infinite."""
    return [(s, v) for s, v in series if math.isinf(v)]


def summary(series: list[tuple[int, float]], name: str = "") -> dict:
    """
    Return a summary statistics dict for a metric series.
    Includes mean, std, min, max, final value, total steps, and convergence.
    """
    mn = minimum(series)
    mx = maximum(series)
    fn = final(series)
    has_converged, conv_step = converged(series, tolerance=0.01, window=50)

    return {
        "name":             name,
        "count":            len(series),
        "mean":             mean(series),
        "std":              std(series),
        "min_value":        mn[1] if mn else None,
        "min_step":         mn[0] if mn else None,
        "max_value":        mx[1] if mx else None,
        "max_step":         mx[0] if mx else None,
        "final_value":      fn[1] if fn else None,
        "final_step":       fn[0] if fn else None,
        #"integral":         integral(series),
        "converged":        has_converged,
        "convergence_step": conv_step,
        "n_spikes":         len(spikes(series)),
        "n_nans":           len(nans(series)),
        "n_infs":           len(infs(series)),
    }
