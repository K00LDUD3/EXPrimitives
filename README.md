# EXPrimitives
a bunch of Experiment Primitives (config handler, loggers, experiment handlers, etc) targetting experiment as well as simulation usage.

## Group A:

### A1. Anchor (Config Handler)
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

#### Usage
**NOTE**: For `BaseConfig.to_dict()` to capture a variable, it must be type hinted, since the function uses `cls.as_dict()` in its definition.
```py
# assumes: pip install -e /path/to/exprim

from pathlib import Path
from dataclasses import dataclass, field
import exprim.anchor as anchor
from exprim.anchor import BaseConfig


# 1. declare project root

anchor.paths.set_root(Path(__file__).resolve().parent)


# 2. build absolute paths from root

cfg_path  = anchor.paths.from_root("configs", "experiment.yaml")
runs_dir  = anchor.paths.from_root("runs")


# 3. ensure a directory exists

log_dir = anchor.paths.ensure_dir(anchor.paths.from_root("runs", "exp_01", "logs"))


# 4. define flat config

@dataclass(frozen=True)
class SystemConfig(BaseConfig):
    name:        str   = "lorenz"
    dt:          float = 0.01
    state_dim:   int   = 3
    control_dim: int   = 1

    def validate(self) -> list[str]:
        errors = super().validate()
        if self.dt <= 0:
            errors.append(f"SystemConfig: dt must be positive, got {self.dt}")
        if self.state_dim < 1:
            errors.append(f"SystemConfig: state_dim must be >= 1, got {self.state_dim}")
        return errors


# 5. define another flat config

@dataclass(frozen=True)
class ControllerConfig(BaseConfig):
    name:       str   = "pid"
    control_hz: float = 500.0
    action_dim: int   = 1

    def validate(self) -> list[str]:
        errors = super().validate()
        if self.control_hz <= 0:
            errors.append(f"ControllerConfig: control_hz must be positive, got {self.control_hz}")
        return errors


# 6. assemble nested experiment config

@dataclass(frozen=True)
class ExperimentConfig(BaseConfig):
    name:       str              = "lorenz_pid"
    seed:       int              = 42
    system:     SystemConfig     = field(default_factory=SystemConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)

    def validate(self) -> list[str]:
        errors = super().validate()  # automatically recurses into system and controller
        if self.controller.control_hz <= (1.0 / self.system.dt):
            errors.append(
                f"ExperimentConfig: control_hz must exceed 1/dt - "
                f"got {self.controller.control_hz} vs {1.0 / self.system.dt:.2f}"
            )
        if self.controller.action_dim != self.system.control_dim:
            errors.append(
                f"ExperimentConfig: action_dim must match control_dim - "
                f"got {self.controller.action_dim} vs {self.system.control_dim}"
            )
        return errors


# 7. instantiate with all defaults

cfg = ExperimentConfig()


# 8. or instantiate with custom values

cfg = ExperimentConfig(
    name       = "lorenz_pid_fast",
    seed       = 7,
    system     = SystemConfig(dt=0.001, state_dim=3, control_dim=1),
    controller = ControllerConfig(control_hz=1000.0, action_dim=1),
)


# 9. produce a variant without mutating the original

fast_cfg = cfg.replace(seed=99)
assert fast_cfg.seed == 99
assert cfg.seed == 7  # original untouched


# 10. fingerprint - stable hash of config values

print(cfg.fingerprint())         # e.g. "a3f9c12b84e1"
assert cfg.fingerprint() == ExperimentConfig(
    name="lorenz_pid_fast", seed=7,
    system=SystemConfig(dt=0.001, state_dim=3, control_dim=1),
    controller=ControllerConfig(control_hz=1000.0, action_dim=1),
).fingerprint()                  # same values → same fingerprint


# 11. convert to plain dict

d = cfg.to_dict()
# {
#     "name": "lorenz_pid_fast",
#     "seed": 7,
#     "system":     {"name": "lorenz", "dt": 0.001, ...},
#     "controller": {"name": "pid",    "control_hz": 1000.0, ...}
# }


# 12. list field names

print(cfg.field_names())         # ["name", "seed", "system", "controller"]


# 13. validate - raises ValueError listing all errors at once

anchor.validate(cfg)


# 14. validate with cross-config rules

def check_device_compatibility(cfg):
    errors = []
    if not hasattr(cfg, "device"):
        return errors
    if cfg.device == "mps" and cfg.system.dt < 0.001:
        errors.append("MPS backend unstable at dt < 0.001")
    return errors

anchor.validate(cfg, check_device_compatibility)


# 15. save to yaml

anchor.save_yaml(cfg, anchor.paths.from_root("configs", "experiment.yaml"))


# 16. load from yaml - returns plain dict

d = anchor.load_yaml(anchor.paths.from_root("configs", "experiment.yaml"))


# 17. save to json

anchor.save_json(cfg, anchor.paths.from_root("configs", "experiment.json"))


# 18. load from json - returns plain dict

d = anchor.load_json(anchor.paths.from_root("configs", "experiment.json"))


# 19. full round-trip yaml - save then reconstruct

anchor.save_yaml(cfg, anchor.paths.from_root("configs", "experiment.yaml"))
d           = anchor.load_yaml(anchor.paths.from_root("configs", "experiment.yaml"))
cfg_reloaded = ExperimentConfig(
    **{**d, 
       "system":     SystemConfig(**d["system"]),
       "controller": ControllerConfig(**d["controller"]),
    }
)
assert cfg_reloaded == cfg


# 20. save self-contained python snapshot
anchor.save_python(cfg, anchor.paths.from_root("configs", "experiment_snapshot.py"))


# 21. load from python snapshot - returns plain dict

d = anchor.load_python(anchor.paths.from_root("configs", "experiment_snapshot.py"))


# 22. load from file - auto-detects yaml or json by extension

cfg = anchor.load(
    path = anchor.paths.from_root("configs", "experiment.yaml"),
    cls  = ExperimentConfig,
)


# 23. load with field overrides

cfg = anchor.load(
    path      = anchor.paths.from_root("configs", "experiment.yaml"),
    cls       = ExperimentConfig,
    overrides = {"seed": 99},
)


# 24. load and skip validation - test use only

cfg = anchor.load(
    path            = anchor.paths.from_root("configs", "experiment.yaml"),
    cls             = ExperimentConfig,
    skip_validation = True,
)


# 25. use fingerprint to create unique run directory

run_dir = anchor.paths.ensure_dir(
    anchor.paths.from_root("runs", cfg.fingerprint())
)
anchor.save_yaml(cfg,    run_dir / "config.yaml")
anchor.save_python(cfg,  run_dir / "config_snapshot.py")


# 26. resolve and validate an absolute path without creating it

p = anchor.paths.resolve("/home/tanush/Repos/Prime-Fundamentum/configs/experiment.yaml")


# 27. get the declared project root

root = anchor.paths.get_root()


# 28. dataclass equality - field-by-field, inherited from frozen dataclass

cfg_a = ExperimentConfig(seed=42)
cfg_b = ExperimentConfig(seed=42)
cfg_c = ExperimentConfig(seed=99)
assert cfg_a == cfg_b
assert cfg_a != cfg_c


# 29. configs are hashable - usable as dict keys or in sets

seen = {cfg_a, cfg_b, cfg_c}
assert len(seen) == 2          # cfg_a and cfg_b are equal → deduplicated


# 30. pretty repr - multiline, readable for debugging

print(cfg)
# ExperimentConfig(
#   name='lorenz_pid_fast',
#   seed=7,
#   system=SystemConfig(
#     name='lorenz',
#     dt=0.001,
#     ...
#   ),
#   controller=ControllerConfig(...)
# )
```
##### `base`
##### `serialization`
##### `validation`
##### `loaders`
<!--#### `registry` - [TODO]-->
##### `paths`


### A2. Echo (Log Utils)
```py
echo/
├── event.py
├── logger.py
├── sinks.py
├── formatter.py
└── buffer.py
```

#### Usage
```py
from pathlib import Path
from exprim.echo.logger import Logger
from exprim.echo.sinks import ConsoleSink, FileSink
from exprim.echo.event import Level

# setup
console = ConsoleSink(min_level=Level.INFO)
file = FileSink(
    path = Path(".../../*.json"),
    min_level = Level.DEBUG,
    buffer_size = 50
)

## default console logger
default_logger = Logger(
    run_id = "exp_default",
    module = "main",
    sinks = [],
    min_level = Level.DEBUG
)

## sink logger
logger = Logger(
    run_id = "exp_01",
    module = "main",
    sinks = [console, file, ...],
    min_level = Level.DEBUG
)

# for text logging:
logger.info("experiment started")
logger.debug("this only goes to file, console is INFO+")
logger.warning("learning rate is very high", tags=("training", "hyperparams"))
logger.error("nan detected in loss")

# loops
for step in range(1000):
    logger.set_step(step)

    logger.metric("reward", -12.3)
    logger.metric("control_effort", 0.4)

    # throttled - only emits (writes to sinks) every 10 steps, not every step
    logger.metric("loss", 0.041, throttle_steps=10)

# heirarchicals
frame_log = logger.child("frame.lorenz")
guide_log = logger.child("guide.pid")

frame_log.info("system reset")          # [frame.lorenz] system reset
guide_log.info("control signal: 0.42") # [guide.pid] control signal: 0.42

# scoping
with logger.scope("train_epoch"):
    logger.info("epoch 1 started")

    with logger.scope("forward_pass"):
        logger.debug("computing derivatives")
        logger.metric("loss", 0.031)

    with logger.scope("backward_pass"):
        logger.debug("gradients computed")
        logger.metric("grad_norm", 1.42)

    logger.info("epoch 1 complete")


# silent mode
silent_logger = Logger(...,silent=True) # NOTE: silent=True overrides all sinks and silences them too 
silent_logger.info("this produces zero I/O")
silent_sink = ConsoleSink(...,silent=True)


# logging statistics
print(logger.stats())
# {"DEBUG": 4, "INFO": 6, "WARNING": 1, "ERROR": 1, "metric": 2103, "dropped": 890}

# cleanup
logger.close()
```
### Upcoming Primitives
A3, B1..B3, C1..C4, D1..D3, E1..E2
<!--
Tentative ordering:
### A3. A3 Ledger (Experiment Handler)
## A4. B1 Frame
## A5. B2 Guide
## A6. B3 Augment
## A7. C1 Gauge
## A8. C2 Probe
## A9. C4 Vault
## A10.C3 Canvas
## A11.D1 Oracle
## A12.D2 Stride
## A13.D3 Fence
## A14.E1 Torch
## A15.E2 Port

A: base layering group
B: modelling and control group
C: analysis group
D: runtime & extension group
E: externals
-->

### Changelog
#### 0.0.1
`Anchor`: **incomplete (`registry.py`) but usable** Made `anchor/validator.py` a stateless validator. Does not store global state of error strings. `registry.py` however will be stateful per run.

#### 0.0.2
`Anchor`: updated `anchor.validate()` to support recursive validation. also included support for saving python dataclasses as a single file self-contained superconfiguration. user can now choose to store/load json/yaml/py. 

#### 0.0.3
`Echo`: incomplete (`buffers.py`) but usable. syncronous event stream with `TEXT`, `METRIC` and `SCOPE` event types. `ConsoleSink` and `FileSink` (JSONL) suported. per-sink level filtering, step tracking, logging statistics. **TODO**: `buffers.py` implementation once need arises. 0.0.3 uses a simple syncronous event buffer.


