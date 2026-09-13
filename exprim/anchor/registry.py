# registry.py
from .base import BaseConfig

_CONFIG_REGISTRY: dict[str, type] = {}
_IMPL_REGISTRY:   dict[str, type] = {}


def register_config(name: str, cls: type) -> None:
    _CONFIG_REGISTRY[name] = cls


def register_impl(name: str, cls: type) -> None:
    _IMPL_REGISTRY[name] = cls


def lookup_config(name: str) -> type:
    if name not in _CONFIG_REGISTRY:
        raise KeyError(
            f"No config registered under '{name}'. "
            f"Available: {list(_CONFIG_REGISTRY)}"
        )
    return _CONFIG_REGISTRY[name]


def lookup_impl(name: str) -> type:
    if name not in _IMPL_REGISTRY:
        raise KeyError(
            f"No impl registered under '{name}'. "
            f"Available: {list(_IMPL_REGISTRY)}"
        )
    return _IMPL_REGISTRY[name]


def reconstruct(d: dict) -> "BaseConfig":
    cls = lookup_config(d["name"])
    return cls.from_dict(d, resolver=reconstruct)
