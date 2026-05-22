from .base import BaseConfig
from typing import Callable

"""
# in the user's script
def check_freq_compatibility(cfg):
    errors = []
    if cfg.controller.control_hz <= (1.0 / cfg.system.dt):
        errors.append("controller must run faster than system timestep")
    return errors

anchor.validate(cfg, check_freq_compatibility)
"""

CrossValidator = Callable[[BaseConfig], list[str]]

def validate(cfg: BaseConfig, *cross_validators: CrossValidator) -> None:
    """
    Run the config's own validate() method, then any cross-validators passed in.
    Cross-validators are for rules that span multiple configs.

    Usage — single config:
        anchor.validate(cfg)

    Usage — with cross-config rules:
        anchor.validate(cfg, check_freq_compatibility)
    """
    errors = cfg.validate()

    for fn in cross_validators:
        errors.extend(fn(cfg))

    if errors:
        raise ValueError(
            "Config validation failed:\n" +
            "\n".join(f"  • {e}" for e in errors)
        )
