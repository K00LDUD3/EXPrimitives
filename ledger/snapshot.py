from __future__ import annotations

import inspect
import shutil
import subprocess
from pathlib import Path

from .paths import (
    git_hash_file,
    git_diff_file,
    pip_freeze_file,
    entry_script_file,
    snapshot_dir,
)

#_: constants

UNKNOWN_GIT_HASH   = "unknown"
UNKNOWN_PIP_FREEZE = "unavailable"


def capture(run_dir: Path, caller_depth: int = 2) -> None:
    """
    Capture full reproducibility snapshot for a run.

    Records:
    - git commit hash
    - git diff (uncommitted changes)
    - pip freeze output
    - copy of the entry script that created this run

    Args:
        run_dir:      absolute path to the run directory
        caller_depth: stack depth to find the entry script.
                      default 2 reaches the script that called run.snapshot()
                      via manager.create_run(). Increase if call is deeper.
    """
    snapshot_dir(run_dir).mkdir(parents=True, exist_ok=True)

    _capture_git_hash(run_dir)
    _capture_git_diff(run_dir)
    _capture_pip_freeze(run_dir)
    _capture_entry_script(run_dir, caller_depth)


def _capture_git_hash(run_dir: Path) -> None:
    """Write the current git commit hash to snapshot/git_hash.txt."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output = True,
            text           = True,
            check          = True,
        )
        git_hash = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_hash = UNKNOWN_GIT_HASH

    git_hash_file(run_dir).write_text(git_hash, encoding="utf-8")


def _capture_git_diff(run_dir: Path) -> None:
    """Write uncommitted git changes to snapshot/git_diff.patch."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output = True,
            text           = True,
            check          = True,
        )
        diff = result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        diff = ""

    git_diff_file(run_dir).write_text(diff, encoding="utf-8")


def _capture_pip_freeze(run_dir: Path) -> None:
    """Write pip freeze output to snapshot/pip_freeze.txt."""
    try:
        result = subprocess.run(
            ["pip", "freeze"],
            capture_output = True,
            text           = True,
            check          = True,
        )
        freeze = result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        freeze = UNKNOWN_PIP_FREEZE

    pip_freeze_file(run_dir).write_text(freeze, encoding="utf-8")


def _capture_entry_script(run_dir: Path, caller_depth: int) -> None:
    """
    Copy the calling script into snapshot/entry_script.py.
    Uses the call stack to find the entry script automatically.
    Works for .py scripts and .ipynb notebooks.
    """
    stack = inspect.stack()

    if caller_depth >= len(stack):
        return

    caller_file = Path(stack[caller_depth].filename).resolve()

    if not caller_file.exists():
        return

    dest = entry_script_file(run_dir)
    shutil.copy2(str(caller_file), str(dest))


def read_git_hash(run_dir: Path) -> str:
    """Read the snapshotted git hash for a run. Returns UNKNOWN if missing."""
    f = git_hash_file(run_dir)
    return f.read_text(encoding="utf-8").strip() if f.exists() else UNKNOWN_GIT_HASH


def read_pip_freeze(run_dir: Path) -> str:
    """Read the snapshotted pip freeze output for a run."""
    f = pip_freeze_file(run_dir)
    return f.read_text(encoding="utf-8") if f.exists() else UNKNOWN_PIP_FREEZE
