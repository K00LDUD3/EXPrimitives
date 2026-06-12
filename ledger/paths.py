from __future__ import annotations

from pathlib import Path

#_: subdirectory names

DIR_CONFIG       = "config"
DIR_LOGS         = "logs"
DIR_METRICS      = "metrics"
DIR_CHECKPOINTS  = "checkpoints"
DIR_ARTIFACTS    = "artifacts"
DIR_TRAJECTORIES = "trajectories"
DIR_SNAPSHOT     = "snapshot"

#_: file names

FILE_EVENTS      = "events.jsonl"
FILE_METRICS     = "metrics.jsonl"
FILE_CONFIG_YAML = "config.yaml"
FILE_CONFIG_JSON = "config.json"
FILE_CONFIG_PY   = "config_snapshot.py"
FILE_METADATA    = "metadata.json"
FILE_NOTES       = "notes.jsonl"
FILE_GIT_HASH    = "git_hash.txt"
FILE_GIT_DIFF    = "git_diff.patch"
FILE_PIP_FREEZE  = "pip_freeze.txt"
FILE_ENTRY       = "entry_script.py"
FILE_CHECKPOINT_LATEST = "latest.pt"

#_: registry

FILE_REGISTRY_DB = "ledger.db"


def config_dir(run_dir: Path) -> Path:
    return run_dir / DIR_CONFIG

def logs_dir(run_dir: Path) -> Path:
    return run_dir / DIR_LOGS

def metrics_dir(run_dir: Path) -> Path:
    return run_dir / DIR_METRICS

def checkpoints_dir(run_dir: Path) -> Path:
    return run_dir / DIR_CHECKPOINTS

def artifacts_dir(run_dir: Path) -> Path:
    return run_dir / DIR_ARTIFACTS

def trajectories_dir(run_dir: Path) -> Path:
    return run_dir / DIR_TRAJECTORIES

def snapshot_dir(run_dir: Path) -> Path:
    return run_dir / DIR_SNAPSHOT

def events_file(run_dir: Path) -> Path:
    return logs_dir(run_dir) / FILE_EVENTS

def metrics_file(run_dir: Path) -> Path:
    return metrics_dir(run_dir) / FILE_METRICS

def config_yaml(run_dir: Path) -> Path:
    return config_dir(run_dir) / FILE_CONFIG_YAML

def config_json(run_dir: Path) -> Path:
    return config_dir(run_dir) / FILE_CONFIG_JSON

def config_py(run_dir: Path) -> Path:
    return config_dir(run_dir) / FILE_CONFIG_PY

def metadata_file(run_dir: Path) -> Path:
    return run_dir / FILE_METADATA

def notes_file(run_dir: Path) -> Path:
    return run_dir / FILE_NOTES

def git_hash_file(run_dir: Path) -> Path:
    return snapshot_dir(run_dir) / FILE_GIT_HASH

def git_diff_file(run_dir: Path) -> Path:
    return snapshot_dir(run_dir) / FILE_GIT_DIFF

def pip_freeze_file(run_dir: Path) -> Path:
    return snapshot_dir(run_dir) / FILE_PIP_FREEZE

def entry_script_file(run_dir: Path) -> Path:
    return snapshot_dir(run_dir) / FILE_ENTRY

def checkpoint_file(run_dir: Path, step: int) -> Path:
    return checkpoints_dir(run_dir) / f"step_{step:010d}.pt"

def checkpoint_latest(run_dir: Path) -> Path:
    return checkpoints_dir(run_dir) / FILE_CHECKPOINT_LATEST

def ensure_run_dirs(run_dir: Path) -> None:
    """Create all standard subdirectories for a new run."""
    for subdir in [
        config_dir(run_dir),
        logs_dir(run_dir),
        metrics_dir(run_dir),
        checkpoints_dir(run_dir),
        artifacts_dir(run_dir),
        trajectories_dir(run_dir),
        snapshot_dir(run_dir),
    ]:
        subdir.mkdir(parents=True, exist_ok=True)
