"""Core dimensionless PHASEMAP model data structures.

Between reset events the candidate scientific contract uses

    d r = v dt
    M d v = -(v - Pe u(theta)) dt + sqrt(2) dW_t
    d theta = sqrt(2) dW_r,

where u(theta)=(cos(theta), sin(theta)).  This module stores parameters and
states only; the contract remains authoritative until G1 is approved.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import numpy.typing as npt

FloatVector = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class ModelParams:
    """Dimensionless model parameters.

    Attributes:
        inertia: Positive inertial parameter M.
        activity: Nonnegative propulsion strength Pe.
        reset_rate: Nonnegative Poisson reset rate rho.
    """

    inertia: float
    activity: float
    reset_rate: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.inertia) or self.inertia <= 0:
            raise ValueError("inertia must be finite and > 0")
        if not math.isfinite(self.activity) or self.activity < 0:
            raise ValueError("activity must be finite and >= 0")
        if not math.isfinite(self.reset_rate) or self.reset_rate < 0:
            raise ValueError("reset_rate must be finite and >= 0")


@dataclass(slots=True)
class State:
    """One particle state in two dimensions."""

    position: FloatVector
    velocity: FloatVector
    orientation: float

    def __post_init__(self) -> None:
        self.position = _vec2(self.position, "position")
        self.velocity = _vec2(self.velocity, "velocity")
        if not math.isfinite(float(self.orientation)):
            raise ValueError("orientation must be finite")
        self.orientation = float(self.orientation)

    @classmethod
    def zero(cls) -> "State":
        return cls(np.zeros(2, dtype=float), np.zeros(2, dtype=float), 0.0)

    def copy(self) -> "State":
        return State(self.position.copy(), self.velocity.copy(), self.orientation)

    def propulsion_direction(self) -> FloatVector:
        return np.array(
            [math.cos(self.orientation), math.sin(self.orientation)], dtype=float
        )


def _vec2(value: npt.ArrayLike, name: str) -> FloatVector:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (2,):
        raise ValueError(f"{name} must have shape (2,), got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr.copy()
