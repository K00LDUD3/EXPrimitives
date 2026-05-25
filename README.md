# Prime-Fundamentum
Below are Axes which can be used independently or together as building blocks.

## A1. Anchor (Config System)

Goal: Every experiment must be reproducable from a single source file. Source directory structure.

Rest of the submodules will use Anchor(A1) to store prebuilt configs (tentative). 
```text
anchor/
├── base.py          
├── types.py         
├── serialization.py 
├── validation.py    
├── loaders.py       
├── registry.py      
└── paths.py          
```

### Files 
#### `base.py`
#### `serialization.py`
#### `validation.py`
#### `loaders.py`
#### `registry.py` - [TODO]
#### `paths.py`

### Changelog 
#### 0.0.1 (21-05-2026)

> `Anchor`: **incomplete (`registry.py`) but usable** Made `anchor/validator.py` a stateless validator. Does not store global state of error strings. `registry.py` however will be stateful per run.

#### 0.0.2 (24-05-2026)

> `Anchor`: updated `anchor.validate()` to support recursive validation. also included support for saving python dataclasses as a single file self-contained superconfiguration. user can now choose to store/load json/yaml/py. 

## A2. Echo
```py
echo/
├── event.py          # Event dataclass + Level enum
├── logger.py         # Logger class - primary API, tee to sinks, scope context
├── sinks.py          # Sink protocol + ConsoleSink + FileSink
├── formatter.py      # event -> human-readable string
└── buffer.py         # buffered write queue for high-frequency logging, async support
```
## A3. Ledger (Experiment Handler)
## A4. Frame
## A5. Guide
## A6. Augment
## A7. Gauge
## A8. Probe
## A9. Vault
## A10. Canvas
## A11. Oracle
## A12. Stride
## A13. Fence
## A14. Torch
## A15. Port
