from __future__ import annotations
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, asdict, replace, fields
from typing import Any, Callable

Resolver = Callable[[dict], "BaseConfig"]


@dataclass(frozen=True)   # immutable by default
class BaseConfig:
    """
    Root mixin for all config objects.
    Frozen: once constructed, values cannot be mutated.
    All subclasses inherit hash, equality, serialization.
    """
    
    def to_dict(self) -> dict[str, Any]:
        """Recursively convert to plain dict (enum values become strings)."""
        return _to_dict_recursive(asdict(self))

    def fingerprint(self) -> str:
        """SHA256 of the canonical dict representation.
        Two configs with identical values produce identical fingerprints.
        Used by Ledger for deduplication and reproducibility checks."""

        canonical = json.dumps(self.to_dict(), sort_keys=True)
        full_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return full_hash[:12]

    def replace(self, **kwargs) -> BaseConfig:
        """Return a new config with fields overridden. Never mutates."""
        return replace(self, **kwargs)

    @classmethod
    def from_dict(cls, d: dict, resolver: Resolver | None = None) -> BaseConfig:
        """
        Reconstruct from plain dict.
        
        resolver: if provided, any nested dict with a 'name' field
        is passed to resolver() instead of being left as a raw dict.
        This breaks the circular dependency — BaseConfig never imports
        the registry, but can still reconstruct nested configs.

        Usage without nesting:
            cfg = SystemConfig.from_dict(d)

        Usage with nesting (called by registry):
            cfg = ExperimentConfig.from_dict(d, resolver=anchor.registry.reconstruct)
        """
        resolved = {}
        for k, v in d.items():
            if isinstance(v, dict) and "name" in v and resolver is not None:
                resolved[k] = resolver(v)
            else:
                resolved[k] = v
        return cls(**resolved)

    def validate(self) -> list[str]:
        """
        Override in subclasses to return a list of error strings.
        Empty list means valid.
        Call super().validate() when overriding to chain parent checks.
        """
        return []
    def field_names(self) -> list[str]:
        return [f.name for f in fields(self)]

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        field_strs = [
            f"  {f.name}={getattr(self, f.name)!r}"
            for f in fields(self)
        ]
        return f"{cls_name}(\n" + ",\n".join(field_strs) + "\n)"


def _to_dict_recursive(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, dict):
        temp = {}
        for key, value in obj.items():
            temp[key] = _to_dict_recursive(value)
        return temp

    if isinstance(obj, (list, tuple)):
        return [_to_dict_recursive(val) for val in obj]

    return obj

