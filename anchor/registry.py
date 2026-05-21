from anchor.base import BaseConfig

_CONFIG_REGISTRY: dict[str, type] = {}

def register(name: str):
    def decorator(cls):
        _CONFIG_REGISTRY[name] = cls
        return cls
    return decorator

def lookup(name: str) -> type:
    if name not in _CONFIG_REGISTRY:
        raise KeyError(f"No config registered under '{name}'. Available: {list(_CONFIG_REGISTRY)}")
    return _CONFIG_REGISTRY[name]

def reconstruct(d: dict) -> BaseConfig:
    cls = lookup(d["name"])
    return cls.from_dict(d, resolver=reconstruct)  # passes itself as resolver
