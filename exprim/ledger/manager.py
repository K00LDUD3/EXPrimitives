from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths as p
from .registry import Registry, STATUS_RUNNING
from .run import Run
from .resume import get_resume_state, resume_note

#_: constants

RUN_ID_PREFIX  = "run"
RUN_ID_SEPARATOR = "_"
METADATA_VERSION = "1.0"


class ExperimentManager:
    """
    Primary API entry point for Ledger.

    Manages the full lifecycle of experiment runs:
    - creating runs
    - loading past runs
    - querying the registry
    - comparing runs
    - resuming from checkpoints
    - deleting runs

    All paths are relative internally — safe to move the runs directory.

    Usage:
        manager = ExperimentManager(runs_dir=Path("/abs/path/to/runs"))
        run     = manager.create_run(cfg, name="lorenz_pid", tags=["baseline"])
    """

    def __init__(self, runs_dir: Path) -> None:
        if not runs_dir.is_absolute():
            raise ValueError(
                f"runs_dir must be an absolute path. Got: '{runs_dir}'"
            )
        self._runs_dir = runs_dir
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._registry = Registry(runs_dir)

    #_: run creation

    def create_run(
        self,
        cfg:             Any,
        name:            str | None       = None,
        tags:            list[str] | None = None,
        auto_snapshot:   bool             = True,
    ) -> Run:
        """
        Create a new experiment run.

        Responsibilities:
        - generates a unique run_id from config fingerprint + timestamp
        - creates all run subdirectories
        - persists config in yaml / json / py formats
        - captures reproducibility snapshot (git, pip, entry script)
        - registers run in SQLite registry

        Args:
            cfg:           BaseConfig subclass instance
            name:          experiment name. defaults to cfg.name if present.
            tags:          list of string labels
            auto_snapshot: if True, capture git/pip/entry script snapshot

        Returns:
            Run object ready to use
        """
        exp_name    = name or getattr(cfg, "name", "experiment")
        fingerprint = cfg.fingerprint()
        run_id      = _make_run_id(exp_name, fingerprint)
        run_dir     = self._runs_dir / exp_name / run_id

        # create directory structure
        p.ensure_run_dirs(run_dir)

        # build metadata
        now      = datetime.now().isoformat(sep=" ", timespec="seconds")
        metadata = {
            "version":     METADATA_VERSION,
            "run_id":      run_id,
            "name":        exp_name,
            "fingerprint": fingerprint,
            "status":      STATUS_RUNNING,
            "created_at":  now,
            "updated_at":  now,
            "tags":        tags or [],
            "failure_reason": None,
        }

        # write metadata.json
        with open(p.metadata_file(run_dir), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)

        # register in SQLite
        self._registry.register(
            run_id        = run_id,
            name          = exp_name,
            relative_path = str(Path(exp_name) / run_id),
            fingerprint   = fingerprint,
            tags          = tags or [],
        )

        run = Run(
            run_id   = run_id,
            run_dir  = run_dir,
            metadata = metadata,
            registry = self._registry,
        )

        # persist config
        run.save_config(cfg)

        # reproducibility snapshot — caller_depth=3 reaches the user's script
        if auto_snapshot:
            run.snapshot(caller_depth=3)

        return run

    #_: loading

    def load_run(self, run_id: str) -> Run:
        """
        Load a past run by run_id.

        Args:
            run_id: the run identifier e.g. "lorenz_pid_a3f9c12b_20260608_143201"

        Raises:
            KeyError if run_id not found in registry
            FileNotFoundError if run directory is missing
        """
        record = self._registry.get(run_id)
        if record is None:
            raise KeyError(f"Run not found in registry: '{run_id}'")

        run_dir = self._runs_dir / record["relative_path"]
        if not run_dir.exists():
            raise FileNotFoundError(
                f"Run directory missing: '{run_dir}'. "
                f"The runs directory may have been moved or the run deleted."
            )

        meta_file = p.metadata_file(run_dir)
        with open(meta_file, encoding="utf-8") as f:
            metadata = json.load(f)

        return Run(
            run_id   = run_id,
            run_dir  = run_dir,
            metadata = metadata,
            registry = self._registry,
        )

    #_: querying

    def list_runs(
        self,
        name:   str | None       = None,
        tags:   list[str] | None = None,
        status: str | None       = None,
        after:  str | None       = None,
        before: str | None       = None,
    ) -> list[dict[str, Any]]:
        """
        Query runs with optional filters.

        Args:
            name:   exact experiment name
            tags:   list of tags — returns runs containing ALL specified tags
            status: "running" | "complete" | "failed"
            after:  ISO date string e.g. "2026-01-01"
            before: ISO date string e.g. "2026-06-01"

        Returns:
            list of run record dicts, newest first
        """
        return self._registry.list_runs(
            name   = name,
            tags   = tags,
            status = status,
            after  = after,
            before = before,
        )

    def find_by_fingerprint(self, fingerprint: str) -> list[dict[str, Any]]:
        """
        Find all runs that used an identical config (same fingerprint).
        Useful for deduplication before launching expensive runs.

        Usage:
            existing = manager.find_by_fingerprint(cfg.fingerprint())
            if existing:
                print(f"already ran this config: {existing[0]['run_id']}")
        """
        return self._registry.find_by_fingerprint(fingerprint)

    #_: comparison

    def compare(
        self,
        run_ids:    list[str],
        metric:     str,
        step:       int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compare a named metric across multiple runs.

        Reads each run's metrics.jsonl and extracts the metric value.
        If step is provided, finds the closest logged step.
        If step is None, returns the final logged value.

        Returns list of dicts:
            [
                {
                    "run_id":      ...,
                    "name":        ...,
                    "fingerprint": ...,
                    "tags":        [...],
                    "step":        ...,
                    "value":       ...,
                },
                ...
            ]
        """
        results = []
        for run_id in run_ids:
            record = self._registry.get(run_id)
            if record is None:
                continue

            run_dir = self._runs_dir / record["relative_path"]
            value, found_step = _extract_metric(run_dir, metric, step)

            results.append({
                "run_id":      run_id,
                "name":        record["name"],
                "fingerprint": record["fingerprint"],
                "tags":        record["tags"],
                "step":        found_step,
                "value":       value,
            })

        return sorted(results, key=lambda r: (r["value"] is None, r["value"]))

    #_: resume

    def resume_run(self, run_id: str, step: int | None = None) -> tuple[Run, Path, int]:
        """
        Resume an interrupted run from a checkpoint.

        Args:
            run_id: run to resume
            step:   specific checkpoint step. None = latest.

        Returns:
            (run, checkpoint_path, step) tuple

        Usage:
            run, ckpt_path, start_step = manager.resume_run("run_abc123")
            state_dict = torch.load(ckpt_path)
            # continue training from start_step
        """
        run            = self.load_run(run_id)
        ckpt_path, resolved_step = get_resume_state(run.run_dir, step)
        run.add_note(resume_note(resolved_step))
        return run, ckpt_path, resolved_step

    #_: deletion

    def delete_run(self, run_id: str, confirm: bool = False) -> None:
        """
        Delete a run's directory and registry entry.

        Args:
            confirm: must be True to proceed — prevents accidental deletion

        Raises:
            RuntimeError if confirm is False
        """
        if not confirm:
            raise RuntimeError(
                f"Pass confirm=True to delete run '{run_id}'. "
                f"This operation is irreversible."
            )

        record = self._registry.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: '{run_id}'")

        run_dir = self._runs_dir / record["relative_path"]

        import shutil
        if run_dir.exists():
            shutil.rmtree(str(run_dir))

        self._registry.delete(run_id)

    #_: lifecycle

    def close(self) -> None:
        """Close the registry database connection."""
        self._registry.close()

    def __enter__(self) -> ExperimentManager:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


#_: helpers

def _make_run_id(name: str, fingerprint: str) -> str:
    """
    Generate a unique run ID.
    Format: {name}_{fingerprint_short}_{timestamp}
    e.g.  : lorenz_pid_a3f9c12b_20260608_143201
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}{RUN_ID_SEPARATOR}{fingerprint[:8]}{RUN_ID_SEPARATOR}{timestamp}"


def _extract_metric(
    run_dir: Path,
    metric:  str,
    step:    int | None,
) -> tuple[float | None, int | None]:
    """
    Read metrics.jsonl for a run and extract a named metric.
    Returns (value, step) or (None, None) if not found.
    """
    metrics_file = p.metrics_file(run_dir)
    if not metrics_file.exists():
        return None, None

    candidates: list[tuple[int, float]] = []

    with open(metrics_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                payload = event.get("payload", {})
                if payload.get("name") == metric:
                    event_step  = event.get("step") or 0
                    event_value = payload.get("value")
                    if event_value is not None:
                        candidates.append((event_step, event_value))
            except (json.JSONDecodeError, KeyError):
                continue

    if not candidates:
        return None, None

    if step is None:
        # return final value
        return candidates[-1][1], candidates[-1][0]

    # return value at closest step
    closest = min(candidates, key=lambda c: abs(c[0] - step))
    return closest[1], closest[0]
