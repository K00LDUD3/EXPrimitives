from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .paths import artifacts_dir, checkpoints_dir, checkpoint_file, checkpoint_latest

#_: constants

CHECKPOINT_SUFFIX = ".pt"
OVERWRITE_ERROR   = (
    "Artifact already exists at '{path}'. "
    "Pass overwrite=True to replace it."
)


class ArtifactStore:
    """
    Manages artifact and checkpoint storage for a single run.
    All paths are derived from run_dir — no absolute path storage.

    Artifacts: arbitrary files (plots, CSVs, numpy arrays, etc.)
    Checkpoints: versioned binary state (PyTorch state dicts, etc.)
    """

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    #_: artifacts

    def save_artifact(
        self,
        source:    Path,
        name:      str | None = None,
        overwrite: bool       = False,
    ) -> Path:
        """
        Copy a file into the run's artifacts/ directory.

        Args:
            source:    absolute path to the source file
            name:      destination filename. defaults to source filename.
            overwrite: if False, raises if artifact already exists

        Returns:
            absolute path to the saved artifact
        """
        dest_name = name or source.name
        dest      = artifacts_dir(self._run_dir) / dest_name

        if dest.exists() and not overwrite:
            raise FileExistsError(OVERWRITE_ERROR.format(path=dest))

        artifacts_dir(self._run_dir).mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(dest))
        return dest

    def list_artifacts(self) -> list[Path]:
        """Return list of all artifact paths for this run."""
        d = artifacts_dir(self._run_dir)
        if not d.exists():
            return []
        return sorted(d.iterdir())

    #_: checkpoints

    def save_checkpoint(
        self,
        state:     Any,
        step:      int,
        overwrite: bool = False,
    ) -> Path:
        """
        Save a checkpoint to checkpoints/step_NNNNNNNNNN.pt
        and update the latest.pt symlink.

        Ledger is checkpoint-format agnostic — it writes bytes.
        The caller serializes (torch.save, pickle, etc.) and passes bytes,
        or passes a path to an already-serialized file.

        If state is a Path: treated as an already-serialized file to copy.
        If state is bytes:  written directly.

        Args:
            state:     Path to serialized file, or raw bytes
            step:      training/simulation step number
            overwrite: if False, raises if checkpoint at this step exists

        Returns:
            absolute path to the saved checkpoint
        """
        dest = checkpoint_file(self._run_dir, step)
        checkpoints_dir(self._run_dir).mkdir(parents=True, exist_ok=True)

        if dest.exists() and not overwrite:
            raise FileExistsError(OVERWRITE_ERROR.format(path=dest))

        if isinstance(state, Path):
            shutil.copy2(str(state), str(dest))
        elif isinstance(state, bytes):
            dest.write_bytes(state)
        else:
            raise TypeError(
                f"state must be Path or bytes, got {type(state).__name__}. "
                f"Serialize your object first (e.g. use torch.save to a temp file)."
            )

        _update_latest_symlink(self._run_dir, dest)
        return dest

    def checkpoint_path(self, step: int | None = None) -> Path:
        """
        Return the path to a checkpoint without loading it.

        Args:
            step: specific step. if None, returns latest.pt path.

        Raises:
            FileNotFoundError if the checkpoint does not exist.
        """
        if step is None:
            path = checkpoint_latest(self._run_dir)
        else:
            path = checkpoint_file(self._run_dir, step)

        if not path.exists():
            raise FileNotFoundError(f"No checkpoint found at: {path}")

        return path

    def list_checkpoints(self) -> list[tuple[int, Path]]:
        """
        Return all checkpoints as (step, path) pairs, sorted by step ascending.
        Excludes the latest.pt symlink.
        """
        d = checkpoints_dir(self._run_dir)
        if not d.exists():
            return []

        results = []
        for f in sorted(d.iterdir()):
            if f.suffix == CHECKPOINT_SUFFIX and f.stem.startswith("step_"):
                try:
                    step = int(f.stem.replace("step_", ""))
                    results.append((step, f))
                except ValueError:
                    continue

        return results

    def last_step(self) -> int | None:
        """Return the step number of the most recent checkpoint, or None."""
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None
        return checkpoints[-1][0]


#_: helpers

def _update_latest_symlink(run_dir: Path, target: Path) -> None:
    """Update the latest.pt symlink to point to target."""
    latest = checkpoint_latest(run_dir)
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    try:
        latest.symlink_to(target.name)
    except (OSError, NotImplementedError):
        # symlinks unavailable (some Windows configs) — copy instead
        shutil.copy2(str(target), str(latest))
