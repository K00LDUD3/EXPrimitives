```
anchor/
├── base.py           # BaseConfig, frozen, fingerprint, replace
├── types.py          # Device, Precision, LogLevel, Seed, Hz — shared primitives
├── serialization.py  # save/load YAML/JSON — works on any BaseConfig
├── validation.py     # validation runner infrastructure, not the rules themselves
├── loaders.py        # load(path, overrides) — generic
├── registry.py       # string → class mapping
├── paths.py
└── __init__.py
```

> Example Usage

Each Axes carries its own config file

```
frame/
└── config.py    # SystemConfig(BaseConfig)

guide/
└── config.py    # ControllerConfig(BaseConfig)

echo/
└── config.py    # LoggingConfig(BaseConfig)

ledger/
└── config.py    # RunConfig(BaseConfig)
```

which can be put together in a main file such as
```python
from anchor import BaseConfig
from frame.config import SystemConfig
from guide.config import ControllerConfig

@dataclass(frozen=True)
class MyExperimentConfig(BaseConfig):
    system:     SystemConfig
    controller: ControllerConfig
    seed:       int = 42
```

> `__init__.py`

```py
from anchor.base          import BaseConfig
from anchor.types         import Device, Precision, LogLevel, Seed, Hz, Seconds
from anchor.loaders       import load
from anchor.serialization import save_yaml, load_yaml, save_json, to_dict, from_dict
from anchor.validation    import validate
from anchor.registry      import register, lookup
from anchor import paths

__all__ = [
    "BaseConfig",
    "Device", "Precision", "LogLevel", "Seed", "Hz", "Seconds",
    "load", "save_yaml", "load_yaml", "save_json", "to_dict", "from_dict",
    "validate",
    "register", "lookup",
]
```
Anchor enforces absolute paths everywhere.
No relative paths are accepted at any API boundary.
Use anchor.paths.set_root() once per entry script.
Use anchor.paths.from_root() to construct all subsequent paths.

> `Types.py`

```python
from enum import Enum, auto

class Device(str, Enum):
    CPU  = "cpu"
    CUDA = "cuda"
    MPS  = "mps"

class Precision(str, Enum):
    FP32 = "float32"
    FP16 = "float16"
    BF16 = "bfloat16"

class LogLevel(str, Enum):
    DEBUG   = "DEBUG"
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"

# Type aliases
Seed    = int
RunID   = str
Hz      = float   # frequency in Hertz
Seconds = float
```

> `Base.py`
```python
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field, asdict, replace
from typing import Any

@dataclass(frozen=True)   # immutable by default
class BaseConfig:
    """
    Root mixin for all config objects.
    Frozen: once constructed, values cannot be mutated.
    All subclasses inherit hash, equality, serialization.
    """

    def to_dict(self) -> dict[str, Any]:
        """Recursively convert to plain dict (enum values become strings)."""
        ...

    def fingerprint(self) -> str:
        """SHA256 of the canonical dict representation.
        Two configs with identical values produce identical fingerprints.
        Used by Ledger for deduplication and reproducibility checks."""
        ...

    def replace(self, **kwargs) -> BaseConfig:
        """Return a new config with fields overridden. Never mutates."""
        return replace(self, **kwargs)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BaseConfig:
        """Reconstruct from plain dict. Handles nested configs and enums."""
        ...
```

- frozen=True — configs are value objects. Nothing mutates them after construction.
- replace() — the only way to produce a variant. Returns a new object.
- fingerprint() — Ledger uses this to detect if you're re-running an identical config.

> `path.py` 

Used to help with establishing root directories in files with simple function calls

```py
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
    ...

def get_root() -> Path:
    """Return the declared project root. Raises if set_root() was never called."""
     "at the top of your entry script."
    ...


def resolve(path: str | Path) -> Path:
    """
    Accept an absolute path only. Validates existence is NOT required —
    the path may point to a file that will be created.
    Raises if a relative path is passed.

    Usage:
        cfg_path = anchor.paths.resolve("/home/user/projects/myproject/configs/lorenz.yaml")
    """
    ...


def from_root(*parts: str) -> Path:
    """
    Build an absolute path from the declared project root.
    This is the recommended way to construct all paths.

    Usage:
        cfg_path  = anchor.paths.from_root("configs", "lorenz.yaml")
        runs_dir  = anchor.paths.from_root("runs")
    """
    ...

def ensure_dir(path: str | Path) -> Path:
    """
    Resolve path (must be absolute), create directory if it doesn't exist,
    return the Path object.

    Usage:
        log_dir = anchor.paths.ensure_dir(anchor.paths.from_root("runs", "exp_01", "logs"))
    """
    ...
```

which can be used in main like

```py
import anchor

anchor.paths.set_root("/home/user/projects/lorenz_study")

cfg = anchor.load(anchor.paths.from_root("configs", "lorenz_pid.yaml"))
```
