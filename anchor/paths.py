from __future__ import annotations
from pathlib import Path


_PROJECT_ROOT: Path | None = None


def set_root(path: str | Path) -> None:
    """
    Declare the absolute project root once at the top of any entry script.
    All subsequent anchor.paths calls resolve relative to this.

    Must be an absolute path. Raises if the directory does not exist.

    Usage:
        import anchor
        anchor.paths.set_root("/home/user/projects/myproject")
    """
    global _PROJECT_ROOT
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(f"Project root does not exist: {resolved}")
    _PROJECT_ROOT = resolved


def get_root() -> Path:
    """Return the declared project root. Raises if set_root() was never called."""
    if _PROJECT_ROOT is None:
        raise RuntimeError(
            "Project root has not been set. "
            "Call anchor.paths.set_root('/absolute/path/to/project') "
            "at the top of your entry script."
        )
    return _PROJECT_ROOT


def resolve(path: str | Path) -> Path:
    """
    Accept an absolute path only. Validates existence is NOT required —
    the path may point to a file that will be created.
    Raises if a relative path is passed.

    Usage:
        cfg_path = anchor.paths.resolve("/home/user/projects/myproject/configs/lorenz.yaml")
    """
    p = Path(path)
    if not p.is_absolute():
        raise ValueError(
            f"anchor requires absolute paths. Got relative path: '{path}'\n"
            f"Hint: use anchor.paths.from_root('configs/lorenz.yaml') "
            f"to build absolute paths from your project root."
        )
    return p


def from_root(*parts: str) -> Path:
    """
    Build an absolute path from the declared project root.
    This is the recommended way to construct all paths.

    Usage:
        cfg_path  = anchor.paths.from_root("configs", "lorenz.yaml")
        runs_dir  = anchor.paths.from_root("runs")
    """
    return get_root().joinpath(*parts)


def ensure_dir(path: str | Path) -> Path:
    """
    Resolve path (must be absolute), create directory if it doesn't exist,
    return the Path object.

    Usage:
        log_dir = anchor.paths.ensure_dir(anchor.paths.from_root("runs", "exp_01", "logs"))
    """
    p = resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
