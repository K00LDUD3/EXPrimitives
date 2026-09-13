# anchor/loaders.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseConfig
from .serialization import load_yaml, load_json
from .validation import validate


def load(
    path: str | Path,
    cls: type[BaseConfig],
    *,
    overrides: dict[str, Any] | None = None,
    resolver=None,
    skip_validation: bool = False,
) -> BaseConfig:
    """
    Primary entry point for loading a config from disk.

    Handles the full pipeline:
        disk → plain dict → typed config → overrides → validation

    Args:
        path:            Absolute path to a .yaml or .json config file.
        cls:             The config class to reconstruct into.
        overrides:       Optional dict of field overrides applied after
                         loading. Uses cfg.replace() — never mutates.
        resolver:        Optional resolver function for nested config
                         reconstruction. Pass anchor.registry.reconstruct
                         once the registry exists. Leave None for flat configs.
        skip_validation: If True, bypass validate(). Use only in tests.

    Returns:
        A frozen, validated BaseConfig instance.

    Usage — flat config:
        cfg = anchor.load(path, SystemConfig)

    Usage — nested config:
        cfg = anchor.load(path, ExperimentConfig, resolver=anchor.registry.reconstruct)

    Usage — with overrides:
        cfg = anchor.load(path, SystemConfig, overrides={"dt": 0.001, "seed": 99})
    """
    p = Path(path)

    if not p.is_absolute():
        raise ValueError(
            f"anchor requires absolute paths. Got: '{path}'\n"
            f"Hint: use anchor.paths.from_root(...) to construct absolute paths."
        )

    suffix = p.suffix.lower()
    if suffix in (".yaml", ".yml"):
        d = load_yaml(p)
    elif suffix == ".json":
        d = load_json(p)
    else:
        raise ValueError(
            f"Unsupported config file format: '{suffix}'. "
            f"Expected .yaml, .yml, or .json."
        )

    cfg = cls.from_dict(d, resolver=resolver)

    if overrides:
        cfg = cfg.replace(**overrides)

    if not skip_validation:
        validate(cfg)

    return cfg
