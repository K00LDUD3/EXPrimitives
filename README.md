# Prime-Fundamentum
An orthogonal set of python tools to be used in synergy to accelerate development under the broad umbrella of simulation. 

Below are Axes which can be used independently or together as building blocks.

## 1. Anchor
A config system. 

Goal: Every experiment must be reproducable from a `config.yaml` source file. Source directory structure 

```text
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

### Files 
#### `base.py`
#### `serialization.py`
#### `validation.py`
#### `loaders.py`
#### `registry.py`

### Changelog 
#### V 1.0.1

> `Anchor` can be **used but is incomplete** Made `anchor/validator.py` a stateless validator. Does not store global state of error strings. 

> **TODO: TEST `anchor` with and without loaders.py** 


## 2. Echo
```text

```
## 3. Ledger
## 4. Frame
## 5. Guide
## 6. Augment
## 7. Gauge
## 8. Probe
## 9. Vault
## 10. Canvas
## 11. Oracle
## 12. Stride
## 13. Fence
## 14. Torch
## 15. Port
