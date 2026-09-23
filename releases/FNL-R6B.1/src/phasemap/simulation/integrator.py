"""Reference exact-clock / Euler-Maruyama simulation scaffold.

The Poisson clock is sampled exactly and integration steps are split at reset
times.  The between-jump integrator is intentionally a transparent reference
Euler-Maruyama method, not a publication-grade choice.  G1/G2 work should audit
it against the selected structure-preserving and baseline implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import numpy.typing as npt

from phasemap.common.model import ModelParams, State
from phasemap.simulation.protocols import Protocol, apply_reset


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    end_time: float
    max_step: float
    seed: int = 0
    record_step: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.end_time) or self.end_time <= 0:
            raise ValueError("end_time must be finite and > 0")
        if not math.isfinite(self.max_step) or self.max_step <= 0:
            raise ValueError("max_step must be finite and > 0")
        if self.record_step is not None and (
            not math.isfinite(self.record_step) or self.record_step <= 0
        ):
            raise ValueError("record_step must be finite and > 0 when supplied")


@dataclass(frozen=True, slots=True)
class Trajectory:
    times: npt.NDArray[np.float64]
    positions: npt.NDArray[np.float64]
    velocities: npt.NDArray[np.float64]
    orientations: npt.NDArray[np.float64]
    reset_times: npt.NDArray[np.float64]


def _em_step(
    state: State,
    params: ModelParams,
    dt: float,
    rng: np.random.Generator,
) -> State:
    """One transparent Euler-Maruyama step using pre-step state values."""

    if dt <= 0:
        return state.copy()
    direction = state.propulsion_direction()
    next_position = state.position + state.velocity * dt
    dv_drift = -(state.velocity - params.activity * direction) * (dt / params.inertia)
    dv_noise = (math.sqrt(2.0 * dt) / params.inertia) * rng.normal(size=2)
    next_velocity = state.velocity + dv_drift + dv_noise
    next_orientation = state.orientation + math.sqrt(2.0 * dt) * float(rng.normal())
    return State(next_position, next_velocity, next_orientation)


def simulate(
    params: ModelParams,
    protocol: Protocol,
    config: SimulationConfig,
    initial_state: State | None = None,
) -> Trajectory:
    """Simulate one trajectory with exact exponential reset times.

    The output is recorded after every integration segment and reset.  A later
    production layer may resample to a fixed grid; this low-level representation
    keeps reset-event semantics explicit for testing.
    """

    rng = np.random.default_rng(config.seed)
    state = State.zero() if initial_state is None else initial_state.copy()
    t = 0.0
    next_reset = (
        float(rng.exponential(1.0 / params.reset_rate))
        if params.reset_rate > 0
        else math.inf
    )

    times = [t]
    positions = [state.position.copy()]
    velocities = [state.velocity.copy()]
    orientations = [state.orientation]
    reset_times: list[float] = []

    eps = 32.0 * np.finfo(float).eps * max(1.0, config.end_time)
    while t < config.end_time - eps:
        target = min(t + config.max_step, next_reset, config.end_time)
        dt = target - t
        if dt > eps:
            state = _em_step(state, params, dt, rng)
            t = target
            times.append(t)
            positions.append(state.position.copy())
            velocities.append(state.velocity.copy())
            orientations.append(state.orientation)
        else:
            t = target

        if next_reset <= config.end_time + eps and abs(t - next_reset) <= eps:
            state = apply_reset(state, protocol)
            reset_times.append(t)
            times.append(t)
            positions.append(state.position.copy())
            velocities.append(state.velocity.copy())
            orientations.append(state.orientation)
            next_reset = t + float(rng.exponential(1.0 / params.reset_rate))

    return Trajectory(
        times=np.asarray(times, dtype=float),
        positions=np.asarray(positions, dtype=float),
        velocities=np.asarray(velocities, dtype=float),
        orientations=np.asarray(orientations, dtype=float),
        reset_times=np.asarray(reset_times, dtype=float),
    )
