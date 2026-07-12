from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from exprim.echo.event import Event

ENCODING = "utf-8"


def events_to_jsonl(events: list[Event], path: Path) -> None:
    """Export a list of events to a JSONL file."""
    if not path.is_absolute():
        raise ValueError(f"export requires absolute paths. Got: {path}")
    with open(path, "w", encoding=ENCODING) as f:
        for e in events:
            f.write(json.dumps(e.to_dict()) + "\n")


def series_to_csv(series: list[tuple[int, float]], path: Path, name: str = "value") -> None:
    """
    Export a metric time series to a CSV file with columns step and value.
    name is used as the column header for the value column.
    """
    if not path.is_absolute():
        raise ValueError(f"export requires absolute paths. got: {path}")

    with open(path, "w", newline="", encoding=ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(["step", name])
        writer.writerows(series)


def multi_series_to_csv(series_dict: dict[str, list[tuple[int, float]]], path: Path) -> None:
    """
    Export multiple metric series to a single CSV file.
    Columns are step and one column per metric name.
    All series are aligned to the union of all steps.
    Missing values are left empty.
    """
    if not path.is_absolute():
        raise ValueError(f"export requires absolute paths. Got: {path}")

    all_steps = sorted(set(s for series in series_dict.values() for s, _ in series))
    lookup: dict[str, dict[int, float]] = {
        name: {s: v for s, v in series}
        for name, series in series_dict.items()
    }

    names = sorted(series_dict.keys())

    with open(path, "w", newline="", encoding=ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(["step"] + names)
        for step in all_steps:
            row = [step] + [lookup[name].get(step, "") for name in names]
            writer.writerow(row)



def table_to_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """
    Export a list of dicts (such as from report.cross_run_table) to CSV.
    Column order follows the key order of the first row.
    """
    if not path.is_absolute():
        raise ValueError(f"export requires absolute paths. Got: {path}")
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding=ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def summary_to_json(summary: dict, path: Path) -> None:
    """Export a summary dict to a JSON file with readable indentation."""
    if not path.is_absolute():
        raise ValueError(f"export requires absolute paths. Got: {path}")
    with open(path, "w", encoding=ENCODING) as f:
        json.dump(summary, f, indent=4, default=str)
