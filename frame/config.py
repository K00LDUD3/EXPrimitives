# frame/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from ..anchor.base import BaseConfig


@dataclass(frozen=True)
class SystemConfig(BaseConfig):
    name: str
    dt: float
    state_dim: int
    control_dim: int
    params: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors = super().validate()
        if self.dt <= 0:
            errors.append(f"dt must be positive, got {self.dt}")
        if self.state_dim < 1:
            errors.append(f"state_dim must be >= 1, got {self.state_dim}")
        return errors


@dataclass(frozen=True)
class ControllerConfig(BaseConfig):
    name: str
    control_hz: float
    action_dim: int

    def validate(self) -> list[str]:
        errors = super().validate()
        if self.control_hz <= 0:
            errors.append(f"control_hz must be positive, got {self.control_hz}")
        return errors
