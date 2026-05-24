from pathlib import Path
from .base import BaseConfig

from dataclasses import fields as dc_fields
from json import dump as json__dump, load as json__load
from yaml import load as yaml__load, safe_load as yaml__safe_load, dump as yaml__dump, Loader as yaml__Loader
from typing import Any

from warnings import warn


"""
One thing to notice:
load_yaml and load_json now return dict, not BaseConfig.
This is deliberate. Serialization's job is to read bytes off
disk and give you a plain dict.
It has no idea which subclass to reconstruct.
Only the caller knows that.
So reconstruction is the caller's responsibility:
"""


def save_yaml(cfg: BaseConfig, path: Path) -> None:
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    data = cfg.to_dict()
    with open(path, "w", encoding="utf-8") as f:
        yaml__dump(data, f, default_flow_style=False, sort_keys=False)


def load_yaml(path: Path, safe: bool = True) -> dict:
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        if safe:
            data = yaml__safe_load(f)
        else:

            warn("Using normal yaml.load(). Pass safe=True to use yaml.safe_load()", UserWarning, stacklevel=2)
            data = yaml__load(f, Loader=yaml__Loader)
    return data


def save_json(cfg: BaseConfig, path: Path) -> None:
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    data = cfg.to_dict()
    with open(path, "w", encoding="utf-8") as f:
        json__dump(data, f, indent=4)


def load_json(path: Path) -> dict:
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        data = json__load(f)
    return data

# anchor/serialization.py — add these two functions


def save_python(cfg: BaseConfig, path: Path) -> None:
    """
    Save a self-contained Python snapshot of the config as a
    nested dataclass definition with all values baked in as defaults.

    Fully reconstructible via load_python() — no registry, no YAML
    parser, no imports from your codebase required.

    Advantages over YAML/JSON:
    - types visible alongside values
    - lists, dicts, tuples render as Python literals
    - directly executable
    - hierarchy immediately readable as nested class definitions

    Use this as your primary human-facing config format.
    Use save_yaml / save_json for machine-to-machine exchange
    or if you need a format readable by non-Python tools.
    """
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    if not path.suffix == ".py":
        raise TypeError(f"anchor requires python extension. Got: '{path}'")

    lines = [
        "# Auto-generated snapshot by anchor.serialization.save_python()",
        "# Do not edit — for inspection only.",
        "# For programmatic reconstruction use config.yaml.",
        "",
        "from __future__ import annotations",
        "from dataclasses import dataclass",
        "",
        "",
    ]

    lines.extend(_render_dataclass(cfg, indent=0))

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _render_dataclass(cfg: BaseConfig, indent: int) -> list[str]:
    """
    Recursively render a BaseConfig as a nested dataclass definition.
    Nested BaseConfig fields are rendered as inner dataclass definitions
    before the parent's own fields.
    """

    pad = "    " * indent
    padmore = "    " * (indent + 1)
    cls = type(cfg)
    lines = []

    # opening decorator and class definition
    lines.append(f"{pad}@dataclass(frozen=True)")
    lines.append(f"{pad}class {cls.__name__}:")
    lines.append("")

    # first pass — render nested BaseConfig fields as inner classes
    for f in dc_fields(cfg):
        value = getattr(cfg, f.name)
        if isinstance(value, BaseConfig):
            nested_lines = _render_dataclass(value, indent + 1)
            lines.extend(nested_lines)
            lines.append("")

    # second pass — render all fields with their types and baked-in defaults
    for f in dc_fields(cfg):
        value = getattr(cfg, f.name)
        type_str = _type_name(value)

        if isinstance(value, BaseConfig):
            # reference the inner class by name, default is inner class call
            inner_cls = type(value).__name__
            lines.append(f"{padmore}{f.name}: {inner_cls} = {inner_cls}()")
        else:
            lines.append(f"{padmore}{f.name}: {type_str} = {value!r}")

    return lines


def _type_name(value: Any) -> str:
    """Return a clean type name string for a given value."""
    type_map = {
        int:   "int",
        float: "float",
        str:   "str",
        bool:  "bool",
    }
    return type_map.get(type(value), type(value).__name__)


def load_python(path: Path) -> dict:
    """
    Load a Python snapshot back as a plain dict.

    Executes the snapshot file in an isolated namespace and calls
    to_dict() on the resulting config object.

    The snapshot must define a single dataclass and instantiate it
    as a variable named 'cfg' — which save_python() does not do yet.
    This is a read-back utility for inspection only.

    Note: uses exec() — only load files you generated yourself.
    """
    if not path.is_absolute():
        raise ValueError(f"anchor requires absolute paths. Got: '{path}'")
    if not path.suffix == ".py":
        raise TypeError(f"anchor requires python extension. Got: '{path}'")

    namespace: dict[str, Any] = {}
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), namespace)

    if "cfg" not in namespace:
        raise ValueError(
            f"Python snapshot must define a variable named 'cfg'. "
            f"Found: {list(namespace.keys())}"
        )

    return namespace["cfg"].to_dict()
