from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from . import paths as p
from .artifact import ArtifactStore
from .snapshot import capture, read_git_hash

# constants
STATUS_RUNNING  = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED   = "failed"

METADATA_VERSION = "1.0"


#NOTE: logger protocol for external logger. Echo satisfies this protocol.

@runtime_checkable
class LoggerProtocol(Protocol):
    """
    Minimal protocol a logger must satisfy to be used with Ledger.
    Echo's Logger satisfies this. Any other logger with these methods works too.
    """
    def info(self, message: str, **kwargs: Any) -> None: ...
    def warning(self, message: str, **kwargs: Any) -> None: ...
    def error(self, message: str, **kwargs: Any) -> None: ...
    def metric(self, name: str, value: float, **kwargs: Any) -> None: ...
    def close(self) -> None: ...


class Run:
    """
    Central interaction point for a single experiment run.

    Manages:
    - config persistence
    - artifact and checkpoint storage
    - notes
    - metadata (status, step, timestamps)
    - reproducibility snapshot
    - logger attachment

    Never instantiate directly — use ExperimentManager.create_run()
    or ExperimentManager.load_run().
    """

    def __init__(
        self,
        run_id:   str,
        run_dir:  Path,
        metadata: dict[str, Any],
        registry: Any,              #_: Registry - typed loosely to avoid circular import
    ) -> None:
        self.run_id   = run_id
        self.run_dir  = run_dir
        self._meta    = metadata
        self._registry = registry
        self._artifacts = ArtifactStore(run_dir)
        self._logger: LoggerProtocol | None = None

    # properties
    
    @property
    def name(self) -> str:
        return self._meta["name"]

    @property
    def status(self) -> str:
        return self._meta["status"]

    @property
    def fingerprint(self) -> str:
        return self._meta["fingerprint"]

    @property
    def tags(self) -> list[str]:
        return list(self._meta.get("tags", []))

    @property
    def created_at(self) -> str:
        return self._meta["created_at"]

    #NOTE: config actions

    def save_config(self, cfg: Any) -> None:
        """
        Persist the experiment config in all three formats.
        Requires anchor. cfg must be a BaseConfig subclass.
        """
        from .. import anchor as anchor

        p.config_dir(self.run_dir).mkdir(parents=True, exist_ok=True)
        #PERF: Add save and load to __init__ of ANCHOR
        anchor.serialization.save_yaml(cfg, p.config_yaml(self.run_dir))
        anchor.serialization.save_json(cfg, p.config_json(self.run_dir))
        anchor.serialization.save_python(cfg, p.config_py(self.run_dir))

    def load_config(self) -> dict[str, Any]:
        """
        Load the saved config as a plain dict.
        Caller reconstructs into typed config using their config class.
        """
        from .. import anchor as anchor
        return anchor.loaders.load_yaml(p.config_yaml(self.run_dir))

    #_: logger

    def attach_logger(self, logger: LoggerProtocol) -> LoggerProtocol:
        """
        Attach any logger satisfying LoggerProtocol to this run.
        Returns the logger for convenience.

        For Echo users — create your logger with a FileSink pointed at
        self.logs_path() and self.metrics_path(), then attach here.

        Usage:
            from echo.logger import Logger
            from echo.sinks import ConsoleSink, FileSink
            from echo.event import Level

            logger = Logger(
                run_id = run.run_id,
                sinks  = [
                    ConsoleSink(),
                    FileSink(path=run.logs_path(),    min_level=Level.DEBUG),
                    FileSink(path=run.metrics_path(), min_level=Level.INFO),
                ]
            )
            run.attach_logger(logger)
        """
        if not isinstance(logger, LoggerProtocol):
            raise TypeError(
                f"logger must satisfy LoggerProtocol "
                f"(info, warning, error, metric, close). Got: {type(logger)}"
            )
        self._logger = logger
        return logger

    @property
    def logger(self) -> LoggerProtocol:
        """Return the attached logger. Raises if none attached."""
        if self._logger is None:
            raise RuntimeError(
                f"No logger attached to run '{self.run_id}'. "
                f"Call run.attach_logger(logger) first."
            )
        return self._logger

    #_: convenience paths

    def logs_path(self) -> Path:
        """Absolute path to the events JSONL file for this run."""
        return p.events_file(self.run_dir)

    def metrics_path(self) -> Path:
        """Absolute path to the metrics JSONL file for this run."""
        return p.metrics_file(self.run_dir)

    #_: artifacts and checkpoints

    def save_artifact(self, source: Path, name: str | None = None, overwrite: bool = False) -> Path:
        """Copy a file into this run's artifacts/ directory."""
        return self._artifacts.save_artifact(source, name, overwrite)

    def save_checkpoint(self, state: Any, step: int, overwrite: bool = False) -> Path:
        """
        Save a checkpoint for this run.
        state must be Path (already serialized file) or bytes.

        For PyTorch:
            import tempfile, torch
            with tempfile.NamedTemporaryFile(suffix='.pt', delete=False) as f:
                torch.save(state_dict, f.name)
                run.save_checkpoint(Path(f.name), step=step)
        """
        dest = self._artifacts.save_checkpoint(state, step, overwrite)
        self._update_metadata(final_step=step)
        return dest

    def checkpoint_path(self, step: int | None = None) -> Path:
        """Return path to a checkpoint. step=None returns latest."""
        return self._artifacts.checkpoint_path(step)

    def list_checkpoints(self) -> list[tuple[int, Path]]:
        """Return all (step, path) checkpoint pairs sorted ascending."""
        return self._artifacts.list_checkpoints()

    def last_step(self) -> int | None:
        """Return step number of most recent checkpoint."""
        return self._artifacts.last_step()

    def list_artifacts(self) -> list[Path]:
        """Return list of all artifact paths."""
        return self._artifacts.list_artifacts()

    #_: notes

    def add_note(self, text: str) -> None:
        """
        Append a timestamped note to this run's notes.jsonl.
        Works in scripts, REPLs, or notebooks — any session.
        Useful in try/except blocks for failure annotation.

        Usage:
            run.add_note("converged well, use as baseline")
            # or in exception handler:
            run.add_note(f"diverged at step {step}: {e}")
        """
        note = {
            "timestamp": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "text":      text,
        }
        with open(p.notes_file(self.run_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(note) + "\n")
        self._registry.increment_notes(self.run_id)

    def read_notes(self) -> list[dict[str, str]]:
        """Return all notes for this run as list of {timestamp, text} dicts."""
        f = p.notes_file(self.run_dir)
        if not f.exists():
            return []
        return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]

    #_: tags

    def add_tags(self, tags: list[str]) -> None:
        """Add tags to this run. Duplicates are ignored."""
        current = set(self.tags)
        current.update(tags)
        updated = sorted(current)
        self._meta["tags"] = updated
        self._registry.update_tags(self.run_id, updated)

    def remove_tags(self, tags: list[str]) -> None:
        """Remove tags from this run. Missing tags are ignored."""
        current = set(self.tags)
        current.difference_update(tags)
        updated = sorted(current)
        self._meta["tags"] = updated
        self._registry.update_tags(self.run_id, updated)

    #_: status

    def mark_complete(self) -> None:
        """Mark this run as successfully completed."""
        self._meta["status"] = STATUS_COMPLETE
        self._registry.update_status(
            self.run_id,
            STATUS_COMPLETE,
            final_step=self.last_step(),
        )
        self._update_metadata(status=STATUS_COMPLETE)
        if self._logger:
            self._logger.info("run marked complete")

    def mark_failed(self, reason: str = "") -> None:
        """
        Mark this run as failed with an optional reason string.
        Use in except blocks:
            except Exception as e:
                run.mark_failed(reason=str(e))
        """
        self._meta["status"] = STATUS_FAILED
        self._registry.update_status(
            self.run_id,
            STATUS_FAILED,
            failure_reason=reason,
            final_step=self.last_step(),
        )
        self._update_metadata(status=STATUS_FAILED, failure_reason=reason)
        if self._logger:
            self._logger.error(f"run failed: {reason}")

    #_: snapshot

    def snapshot(self, caller_depth: int = 2) -> None:
        """
        Capture full reproducibility snapshot:
        - git commit hash
        - git diff (uncommitted changes)
        - pip freeze
        - copy of the calling entry script

        Called automatically by ExperimentManager.create_run().
        Can be called manually if needed.
        """
        #FIX: ledger.snapshot.CAPTURE
        capture(self.run_dir, caller_depth=caller_depth + 1)


    #_: summary

    def summary(self) -> dict[str, Any]:
        """
        Return a flat dict of run metadata for reporting or comparison.

        Returns:
            {
                "run_id":          ...,
                "name":            ...,
                "status":          ...,
                "created_at":      ...,
                "tags":            [...],
                "fingerprint":     ...,
                "final_step":      ...,
                "notes_count":     ...,
                "git_hash":        ...,
            }
        """
        return {
            "run_id":      self.run_id,
            "name":        self.name,
            "status":      self.status,
            "created_at":  self.created_at,
            "tags":        self.tags,
            "fingerprint": self.fingerprint,
            "final_step":  self.last_step(),
            "notes_count": len(self.read_notes()),
            "git_hash":    read_git_hash(self.run_dir),
        }

    #_: internal

    def _update_metadata(self, **kwargs: Any) -> None:
        """Write updated metadata fields to metadata.json."""
        self._meta.update(kwargs)
        self._meta["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
        meta_file = p.metadata_file(self.run_dir)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, indent=4)
