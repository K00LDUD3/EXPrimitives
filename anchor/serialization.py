from pathlib import Path
from .base import BaseConfig

from json import dump as json__dump, load as json__load
from yaml import load as yaml__load, safe_load as yaml__safe_load, dump as yaml__dump, Loader as yaml__Loader

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

