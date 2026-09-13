from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact import ArtifactStore

#_: constants

RESUME_NOTE = "run resumed from checkpoint at step {step}"


def get_resume_state(
    run_dir:    Path,
    step:       int | None = None,
) -> tuple[Path, int]:
    """
    Locate the checkpoint to resume from.

    Args:
        run_dir: absolute path to the run directory
        step:    specific step to resume from.
                 if None, resumes from the latest checkpoint.

    Returns:
        (checkpoint_path, step) tuple

    Raises:
        FileNotFoundError if no checkpoint exists
    """
    store = ArtifactStore(run_dir)
    path  = store.checkpoint_path(step)

    if step is None:
        resolved_step = store.last_step()
        if resolved_step is None:
            raise FileNotFoundError(
                f"No checkpoints found in run directory: {run_dir}"
            )
    else:
        resolved_step = step

    return path, resolved_step


def resume_note(step: int) -> str:
    """Return a formatted note string for logging on resume."""
    return RESUME_NOTE.format(step=step)
