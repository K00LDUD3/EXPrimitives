# EXPrimitives
a bunch of Experiment Primitives (config handler, loggers, experiment handlers, etc) targetting experiment as well as simulation usage.

> For strictly typed documentation across all submodules, see [documentation/documentation.md](https://github.com/K00LDUD3/EXPrimitives/blob/main/documentation/documentation.md).

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
<!--#### `registry` - [TODO]-->


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

### A3. Ledger (Experiment Handler)
```py
ledger/
│
├── __init__.py
├── manager.py
├── run.py
├── artifact.py
├── registry.py
├── snapshot.py
├── paths.py
└── resume.py
```

#### Usage
```python
from pathlib import Path
import torch
import tempfile
import exprim.anchor as anchor
import exprim.ledger as ledger
from exprim.echo.logger import Logger
from exprim.echo.sinks import ConsoleSink, FileSink
from exprim.echo.event import Level


# setup
anchor.paths.set_root(Path(__file__).resolve().parent)
RUNS_DIR = anchor.paths.from_root("runs")


# create experiment manager
manager = ledger.ExperimentManager(runs_dir=RUNS_DIR)


# create experiment manager as context manager closes connection automatically
with ledger.ExperimentManager(runs_dir=RUNS_DIR) as manager:
    pass


# create a run from a config
run = manager.create_run(cfg, name="lorenz_pid", tags=["baseline", "pid"])


# create a run with no tags
run = manager.create_run(cfg, name="lorenz_pid")


# create a run without automatic reproducibility snapshot
run = manager.create_run(cfg, name="lorenz_pid", auto_snapshot=False)


# manually trigger reproducibility snapshot captures git hash git diff pip freeze and entry script
run.snapshot()


# attach echo logger pointed at run log and metric directories
logger = Logger(
    run_id = run.run_id,
    sinks  = [
        ConsoleSink(min_level=Level.INFO),
        FileSink(path=run.logs_path(), min_level=Level.DEBUG),
        FileSink(path=run.metrics_path(), min_level=Level.INFO),
    ]
)
run.attach_logger(logger)


# attach any third party logger satisfying LoggerProtocol
class MyLogger:
    def info(self, message, **kwargs):       print(f"[INFO] {message}")
    def warning(self, message, **kwargs):    print(f"[WARN] {message}")
    def error(self, message, **kwargs):      print(f"[ERR ] {message}")
    def metric(self, name, value, **kwargs): print(f"[METRIC] {name}={value}")
    def close(self):                         pass

run.attach_logger(MyLogger())


# use the attached logger through run.logger
run.logger.info("training started")
run.logger.metric("reward", -12.3, step=100)
run.logger.warning("high gradient norm detected")


# save config to run directory writes yaml json and py formats
run.save_config(cfg)


# load config back as plain dict caller reconstructs into typed config
d = run.load_config()


# save a file artifact copied into run artifacts directory
run.save_artifact(Path("/abs/path/to/phase_portrait.png"))


# save artifact with a custom destination filename
run.save_artifact(Path("/abs/path/to/output.png"), name="phase_portrait_ep10.png")


# save artifact with overwrite allowed
run.save_artifact(Path("/abs/path/to/output.png"), name="phase_portrait.png", overwrite=True)


# list all artifacts saved for this run
artifacts = run.list_artifacts()


# save a pytorch checkpoint ledger is format agnostic serialize first then pass the path
with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
    torch.save(model.state_dict(), f.name)
    run.save_checkpoint(Path(f.name), step=1000)


# save raw bytes checkpoint works with pickle or any serializer
import pickle
raw = pickle.dumps({"weights": [1.0, 2.0, 3.0]})
run.save_checkpoint(raw, step=500)


# save checkpoint with overwrite
run.save_checkpoint(Path(f.name), step=1000, overwrite=True)


# get path to latest checkpoint without loading it
ckpt_path = run.checkpoint_path()


# get path to checkpoint at a specific step
ckpt_path = run.checkpoint_path(step=1000)


# load checkpoint contents with torch
state_dict = torch.load(run.checkpoint_path())


# list all checkpoints as step path pairs sorted ascending
checkpoints = run.list_checkpoints()


# get the step number of the most recent checkpoint
step = run.last_step()


# mark run as successfully completed
run.mark_complete()


# mark run failed with reason string useful in except blocks
try:
    train(run)
    run.mark_complete()
except Exception as e:
    run.mark_failed(reason=str(e))


# add a timestamped note works in scripts repls and notebooks
run.add_note("converged cleanly, good baseline")


# add note and mark failed together in exception handler
try:
    train(run)
except Exception as e:
    run.add_note(f"crashed at step {step}: {e}")
    run.mark_failed(reason=str(e))


# read all notes for a run
notes = run.read_notes()


# add tags to a run duplicates are ignored
run.add_tags(["converged", "production"])


# remove tags from a run missing tags are ignored
run.remove_tags(["debug"])


# get a flat summary dict of run metadata for reporting
summary = run.summary()


# access individual run properties
print(run.run_id)
print(run.name)
print(run.status)
print(run.fingerprint)
print(run.tags)
print(run.created_at)


# get absolute paths to log and metric files
print(run.logs_path())
print(run.metrics_path())


# load a past run by run id
past_run = manager.load_run("lorenz_pid_a3f9c12b_20260608_143201")


# list all runs newest first
all_runs = manager.list_runs()


# list runs filtered by experiment name
runs = manager.list_runs(name="lorenz_pid")


# list runs filtered by a single tag
runs = manager.list_runs(tags=["baseline"])


# list runs containing all specified tags AND filter
runs = manager.list_runs(tags=["lorenz", "converged"])


# list runs by status
runs = manager.list_runs(status="complete")
runs = manager.list_runs(status="failed")
runs = manager.list_runs(status="running")


# list runs within a date range
runs = manager.list_runs(after="2026-06-01", before="2026-06-30")


# combine multiple filters
runs = manager.list_runs(name="lorenz_pid", tags=["baseline"], status="complete")


# find all runs that used an identical config by fingerprint
existing = manager.find_by_fingerprint(cfg.fingerprint())
if existing:
    print(f"already ran this exact config: {existing[0]['run_id']}")


# skip duplicate run before launching an expensive experiment
existing = manager.find_by_fingerprint(cfg.fingerprint())
if not existing:
    run = manager.create_run(cfg, name="lorenz_pid")
else:
    print(f"skipping identical config already run: {existing[0]['run_id']}")


# compare a metric across multiple runs returns list sorted by value ascending
run_ids = [r["run_id"] for r in manager.list_runs(name="lorenz_pid")]
results = manager.compare(run_ids, metric="reward")


# compare metric at a specific step returns closest logged step per run
results = manager.compare(run_ids, metric="reward", step=5000)


# resume a run from latest checkpoint
run, ckpt_path, start_step = manager.resume_run("lorenz_pid_a3f9c12b_20260608_143201")
state_dict = torch.load(ckpt_path)


# resume from a specific checkpoint step
run, ckpt_path, start_step = manager.resume_run(
    "lorenz_pid_a3f9c12b_20260608_143201",
    step=5000,
)


# delete a run and its directory confirm required to prevent accidents
manager.delete_run("lorenz_pid_a3f9c12b_20260608_143201", confirm=True)


# full experiment lifecycle
with ledger.ExperimentManager(runs_dir=RUNS_DIR) as manager:
    run = manager.create_run(cfg, name="lorenz_pid", tags=["baseline"])

    logger = Logger(
        run_id = run.run_id,
        sinks  = [
            ConsoleSink(),
            FileSink(path=run.logs_path(), min_level=Level.DEBUG),
            FileSink(path=run.metrics_path(), min_level=Level.INFO),
        ]
    )
    run.attach_logger(logger)

    try:
        for step in range(10000):
            logger.set_step(step)
            logger.metric("reward", reward, throttle_steps=10)
            logger.metric("control_effort", effort, throttle_steps=10)

            if step % 1000 == 0:
                with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
                    torch.save(model.state_dict(), f.name)
                    run.save_checkpoint(Path(f.name), step=step)

        run.mark_complete()

    except Exception as e:
        run.add_note(f"crashed at step {step}: {e}")
        run.mark_failed(reason=str(e))
        raise

    finally:
        logger.close()
```


## Group B:

### B1. Gauge (Query & Analysis)
Fluent query engine for single and multi-run metric inspection.

### Upcoming Primitives
B1..B3, C1..C4, D1..D3, E1..E2
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

#### 0.0.0 - Add `Anchor`

`Anchor`: **incomplete (`registry.py`) but usable** Made *anchor/validator.py* a stateless validator. Does not store global state of error strings. `registry.py` however will be stateful per run.

#### 0.0.1

`Anchor`: updated *anchor.validate()* to support recursive validation. also included support for saving python dataclasses as a single file self-contained superconfiguration. user can now choose to store/load json/yaml/py.

#### 1.0.0 - Add `Echo`

`Echo`: incomplete (`buffers.py`) but usable. syncronous event stream with *TEXT*, *METRIC* and *SCOPE* event types. *ConsoleSink* and *FileSink* (JSONL) suported. per-sink level filtering, step tracking, logging statistics. **TODO**: `buffers.py` implementation once need arises. 1.0.0-present uses a simple syncronous event buffer.

#### 2.0.0 - Add `Ledger`

`Anchor`: Added *save_json, save_python, save_yaml load_json load_python load_yaml* as top level imports. Can be used directly under anchor. Eg. *anchor.save_python* instead of previously *anchor.serialization.save_python*.

`Ledger`: usable - SQLite backed experiment registry tracking runs by config fingerprint. per-run directory layout with config, logs, metrics, checkpoints, artifacts, and reproducibility snapshot (git hash, git diff, pip freeze, entry script). supports run lifecycle (create, load, resume, delete), tagging, notes, status marking, third-party logger injection via protocol, and basic metric comparison across runs. all paths stored relative - safe to relocate runs directory.

#### 3.0.0 - Add `Gauge` & Documentation
`Gauge`: Fluent query engine for single and multi-run metric inspection.




