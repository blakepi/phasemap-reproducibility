"""Rao--Blackwellized exact-clock paths for the S-072 replacement study.

Only reset clocks and rotational Brownian paths are sampled.  Conditional on
those paths, the translational linear SDE is integrated in first and second
moments, analytically marginalizing translational Wiener noise.  Three nested
left-point orientation resolutions share clocks and rotational increments so
that first-order Richardson estimates and their residual can be formed from
matched trajectory units.

This module contains no analytic-reference or prior-result imports.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Final

import numpy as np
import numpy.typing as npt

from phasemap.common.model import ModelParams
from phasemap.simulation.protocols import PROTOCOL_REGISTRY, Protocol


FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

RESET_CLOCK_COMPONENT: Final = 1
TRANSLATIONAL_COMPONENT_MARGINALIZED: Final = 2
ROTATIONAL_WIENER_COMPONENT: Final = 3
LEVEL_NAMES: Final = ("finest", "middle", "coarse")
LEVEL_RATIOS: Final = MappingProxyType(
    {"finest": 1, "middle": 2, "coarse": 4}
)


def _positive_integer(value: int, name: str, *, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _integral_ratio(total: float, step: float, name: str) -> int:
    if not math.isfinite(total) or not math.isfinite(step) or step <= 0.0:
        raise ValueError(f"{name} requires finite positive values")
    ratio = total / step
    rounded = round(ratio)
    if not math.isclose(ratio, rounded, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{name} must be integral")
    return int(rounded)


@dataclass(frozen=True)
class TriplePathConfig:
    """Fixed three-level coupled configuration for one bounded stream chunk."""

    end_time: float
    finest_step: float
    record_step: float
    ensemble_size: int
    base_seed: int
    case_code: int
    stream_code: int
    max_reset_events_per_trajectory: int = 256

    def __post_init__(self) -> None:
        _positive_integer(self.ensemble_size, "ensemble_size", minimum=2)
        _positive_integer(self.base_seed, "base_seed", minimum=0)
        _positive_integer(self.case_code, "case_code", minimum=0)
        _positive_integer(self.stream_code, "stream_code", minimum=0)
        _positive_integer(
            self.max_reset_events_per_trajectory,
            "max_reset_events_per_trajectory",
        )
        finest_steps = _integral_ratio(
            self.end_time, self.finest_step, "end_time/finest_step"
        )
        if finest_steps % 4:
            raise ValueError("finest step count must be divisible by four")
        record_stride = _integral_ratio(
            self.record_step, self.finest_step, "record_step/finest_step"
        )
        if record_stride % 4:
            raise ValueError("record stride must align with every level")
        if finest_steps % record_stride:
            raise ValueError("record schedule must divide the end time")

    @property
    def finest_steps(self) -> int:
        return _integral_ratio(
            self.end_time, self.finest_step, "end_time/finest_step"
        )

    @property
    def record_stride(self) -> int:
        return _integral_ratio(
            self.record_step, self.finest_step, "record_step/finest_step"
        )


@dataclass(frozen=True)
class ConditionalLevelRecord:
    """Recorded conditional moments at one numerical resolution."""

    position_means: FloatArray
    velocity_means: FloatArray
    orientations: FloatArray
    position_variance_per_axis: FloatArray
    position_velocity_covariance_per_axis: FloatArray
    velocity_variance_per_axis: FloatArray

    def array_hashes(self) -> dict[str, str]:
        arrays = {
            "position_means": self.position_means,
            "velocity_means": self.velocity_means,
            "orientations": self.orientations,
            "position_variance_per_axis": self.position_variance_per_axis,
            "position_velocity_covariance_per_axis": (
                self.position_velocity_covariance_per_axis
            ),
            "velocity_variance_per_axis": self.velocity_variance_per_axis,
        }
        return {
            name: hashlib.sha256(
                np.ascontiguousarray(values, dtype="<f8").tobytes()
            ).hexdigest()
            for name, values in arrays.items()
        }


@dataclass(frozen=True)
class TripleConditionalEnsemble:
    """Three matched conditional-moment paths and exact-clock metadata."""

    times: FloatArray
    finest: ConditionalLevelRecord
    middle: ConditionalLevelRecord
    coarse: ConditionalLevelRecord
    reset_counts: IntArray
    reset_clock_sha256: str

    def array_hashes(self) -> dict[str, str]:
        hashes = {
            f"{level}_{name}": digest
            for level in LEVEL_NAMES
            for name, digest in getattr(self, level).array_hashes().items()
        }
        hashes["times"] = hashlib.sha256(
            np.ascontiguousarray(self.times, dtype="<f8").tobytes()
        ).hexdigest()
        hashes["reset_counts"] = hashlib.sha256(
            np.ascontiguousarray(self.reset_counts, dtype="<i8").tobytes()
        ).hexdigest()
        return hashes


@dataclass
class _LevelState:
    position: FloatArray
    velocity: FloatArray
    orientation: FloatArray
    c_rr: FloatArray
    c_rv: FloatArray
    c_vv: FloatArray
    pending_dt: FloatArray
    pending_rotation: FloatArray


def seed_tuple(
    base_seed: int, case_code: int, stream_code: int, component_code: int
) -> tuple[int, int, int, int]:
    """Return the complete RNG-domain tuple used by ``SeedSequence``."""

    for value, name in (
        (base_seed, "base_seed"),
        (case_code, "case_code"),
        (stream_code, "stream_code"),
        (component_code, "component_code"),
    ):
        _positive_integer(value, name, minimum=0)
    return (base_seed, case_code, stream_code, component_code)


def _rng(domain: tuple[int, int, int, int]) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(domain)))


def _strict_exponential(
    rng: np.random.Generator, count: int, rate: float
) -> FloatArray:
    """Draw positive waits; redraw only floating-point representations of zero."""

    waits = np.asarray(rng.exponential(1.0 / rate, size=count), dtype=float)
    zeros = waits <= 0.0
    while np.any(zeros):
        waits[zeros] = rng.exponential(1.0 / rate, size=int(np.sum(zeros)))
        zeros = waits <= 0.0
    return waits


def linear_conditional_coefficients(
    dt: npt.ArrayLike, inertia: float
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    """Return exact constant-orientation transition/noise coefficients.

    The returned arrays are ``a, b, q_rr, q_rv, q_vv`` for one Cartesian
    coordinate.  ``a`` and ``b`` define ``v'=a*v+...`` and ``r'=r+b*v+...``.
    """

    duration = np.asarray(dt, dtype=float)
    if (
        duration.ndim != 1
        or not np.all(np.isfinite(duration))
        or np.any(duration <= 0.0)
        or not math.isfinite(inertia)
        or inertia <= 0.0
    ):
        raise ValueError("dt must be a positive finite vector and inertia positive")
    x = duration / inertia
    one_minus_a = -np.expm1(-x)
    one_minus_a2 = -np.expm1(-2.0 * x)
    a = 1.0 - one_minus_a
    b = inertia * one_minus_a
    q_rv = one_minus_a * one_minus_a
    q_vv = one_minus_a2 / inertia
    q_rr = 2.0 * duration - 4.0 * inertia * one_minus_a + inertia * one_minus_a2
    # Avoid cancellation only in an extreme regime not used by the fixed plan.
    tiny = x < 1e-4
    if np.any(tiny):
        xt = x[tiny]
        q_rr[tiny] = inertia * (
            (2.0 / 3.0) * xt**3
            - 0.5 * xt**4
            + (7.0 / 30.0) * xt**5
            - (1.0 / 12.0) * xt**6
        )
    if np.any(q_rr < -1e-14) or np.any(q_rv < 0.0) or np.any(q_vv < 0.0):
        raise FloatingPointError("conditional translational covariance is invalid")
    q_rr = np.maximum(q_rr, 0.0)
    return a, b, q_rr, q_rv, q_vv


def _new_level(count: int) -> _LevelState:
    return _LevelState(
        position=np.zeros((count, 2), dtype=float),
        velocity=np.zeros((count, 2), dtype=float),
        orientation=np.zeros(count, dtype=float),
        c_rr=np.zeros(count, dtype=float),
        c_rv=np.zeros(count, dtype=float),
        c_vv=np.zeros(count, dtype=float),
        pending_dt=np.zeros(count, dtype=float),
        pending_rotation=np.zeros(count, dtype=float),
    )


def _flush_level(
    state: _LevelState,
    indices: IntArray,
    *,
    inertia: float,
    activity: float,
) -> None:
    if indices.size == 0:
        return
    positive = state.pending_dt[indices] > 0.0
    active = indices[positive]
    if active.size:
        dt = state.pending_dt[active].copy()
        dtheta = state.pending_rotation[active].copy()
        a, b, q_rr, q_rv, q_vv = linear_conditional_coefficients(dt, inertia)
        direction = np.column_stack(
            (np.cos(state.orientation[active]), np.sin(state.orientation[active]))
        )
        old_velocity = state.velocity[active].copy()
        old_c_rv = state.c_rv[active].copy()
        old_c_vv = state.c_vv[active].copy()
        state.position[active] += (
            b[:, None] * old_velocity
            + (dt - b)[:, None] * activity * direction
        )
        state.velocity[active] = (
            a[:, None] * old_velocity
            + (1.0 - a)[:, None] * activity * direction
        )
        state.c_rr[active] += (
            2.0 * b * old_c_rv + b * b * old_c_vv + q_rr
        )
        state.c_rv[active] = a * old_c_rv + a * b * old_c_vv + q_rv
        state.c_vv[active] = a * a * old_c_vv + q_vv
        state.orientation[active] += dtheta
    state.pending_dt[indices] = 0.0
    state.pending_rotation[indices] = 0.0


def _apply_conditional_reset(
    state: _LevelState, indices: IntArray, protocol: Protocol
) -> None:
    reset = PROTOCOL_REGISTRY[protocol]
    if reset.resets_position:
        state.position[indices] = 0.0
        state.c_rr[indices] = 0.0
        state.c_rv[indices] = 0.0
    if reset.resets_velocity:
        state.velocity[indices] = 0.0
        state.c_vv[indices] = 0.0
        state.c_rv[indices] = 0.0
    if reset.resets_orientation:
        state.orientation[indices] = 0.0


def _allocate_record(times: FloatArray, count: int) -> dict[str, FloatArray]:
    return {
        "position_means": np.empty((times.size, count, 2), dtype=float),
        "velocity_means": np.empty((times.size, count, 2), dtype=float),
        "orientations": np.empty((times.size, count), dtype=float),
        "position_variance_per_axis": np.empty((times.size, count), dtype=float),
        "position_velocity_covariance_per_axis": np.empty(
            (times.size, count), dtype=float
        ),
        "velocity_variance_per_axis": np.empty((times.size, count), dtype=float),
    }


def _record_state(
    destination: dict[str, FloatArray], index: int, state: _LevelState
) -> None:
    destination["position_means"][index] = state.position
    destination["velocity_means"][index] = state.velocity
    destination["orientations"][index] = state.orientation
    destination["position_variance_per_axis"][index] = state.c_rr
    destination["position_velocity_covariance_per_axis"][index] = state.c_rv
    destination["velocity_variance_per_axis"][index] = state.c_vv


def simulate_conditional_triple_paths(
    params: ModelParams,
    protocol: Protocol,
    config: TriplePathConfig,
) -> TripleConditionalEnsemble:
    """Simulate one fixed chunk without drawing translational Wiener noise."""

    if not isinstance(protocol, Protocol):
        raise TypeError("protocol must be a Protocol")
    mass = float(params.inertia)
    activity = float(params.activity)
    reset_rate = float(params.reset_rate)
    if mass <= 0.0 or reset_rate < 0.0:
        raise ValueError("replacement kernel requires M>0 and rho>=0")

    reset_rng = _rng(
        seed_tuple(
            config.base_seed,
            config.case_code,
            config.stream_code,
            RESET_CLOCK_COMPONENT,
        )
    )
    rotation_rng = _rng(
        seed_tuple(
            config.base_seed,
            config.case_code,
            config.stream_code,
            ROTATIONAL_WIENER_COMPONENT,
        )
    )
    count = config.ensemble_size
    levels = {name: _new_level(count) for name in LEVEL_NAMES}
    next_reset = (
        _strict_exponential(reset_rng, count, reset_rate)
        if reset_rate > 0.0
        else np.full(count, math.inf, dtype=float)
    )
    reset_counts = np.zeros(count, dtype=np.int64)
    clock_hasher = hashlib.sha256()
    all_indices = np.arange(count, dtype=np.int64)
    times = np.arange(
        config.finest_steps // config.record_stride + 1, dtype=float
    ) * config.record_step
    records = {
        name: _allocate_record(times, count) for name in LEVEL_NAMES
    }
    for name in LEVEL_NAMES:
        _record_state(records[name], 0, levels[name])

    record_index = 1
    for step_index in range(config.finest_steps):
        interval_start = step_index * config.finest_step
        interval_end = (step_index + 1) * config.finest_step
        local_time = np.full(count, interval_start, dtype=float)
        while True:
            active = np.flatnonzero(local_time < interval_end).astype(
                np.int64, copy=False
            )
            if active.size == 0:
                break
            target = np.minimum(next_reset[active], interval_end)
            event_due = next_reset[active] <= interval_end
            event_indices = active[event_due]
            if np.any(
                reset_counts[event_indices]
                >= config.max_reset_events_per_trajectory
            ):
                raise RuntimeError("locked reset-event cap exceeded")
            dt = target - local_time[active]
            if np.any(dt <= 0.0):
                raise RuntimeError("nonpositive exact-clock segment")
            dtheta = rotation_rng.normal(size=active.size) * np.sqrt(2.0 * dt)
            for state in levels.values():
                state.pending_dt[active] += dt
                state.pending_rotation[active] += dtheta
            _flush_level(
                levels["finest"], active, inertia=mass, activity=activity
            )
            local_time[active] = target
            if event_indices.size == 0:
                continue
            event_times = next_reset[event_indices].copy()
            for name in ("middle", "coarse"):
                _flush_level(
                    levels[name], event_indices, inertia=mass, activity=activity
                )
            clock_hasher.update(
                np.ascontiguousarray(event_indices, dtype="<i8").tobytes()
            )
            clock_hasher.update(
                np.ascontiguousarray(event_times, dtype="<f8").tobytes()
            )
            for state in levels.values():
                _apply_conditional_reset(state, event_indices, protocol)
            reset_counts[event_indices] += 1
            next_reset[event_indices] = event_times + _strict_exponential(
                reset_rng, event_indices.size, reset_rate
            )

        if (step_index + 1) % LEVEL_RATIOS["middle"] == 0:
            _flush_level(
                levels["middle"], all_indices, inertia=mass, activity=activity
            )
        if (step_index + 1) % LEVEL_RATIOS["coarse"] == 0:
            _flush_level(
                levels["coarse"], all_indices, inertia=mass, activity=activity
            )
        if (step_index + 1) % config.record_stride == 0:
            if any(
                np.any(state.pending_dt != 0.0) for state in levels.values()
            ):
                raise RuntimeError("record boundary contains unflushed state")
            for name in LEVEL_NAMES:
                _record_state(records[name], record_index, levels[name])
            record_index += 1

    if record_index != times.size:
        raise RuntimeError("record schedule was not filled")
    if any(
        not np.all(np.isfinite(array))
        for record in records.values()
        for array in record.values()
    ):
        raise FloatingPointError("nonfinite conditional record")
    if any(
        np.any(record[name] < -1e-12)
        for record in records.values()
        for name in (
            "position_variance_per_axis",
            "velocity_variance_per_axis",
        )
    ):
        raise FloatingPointError("negative conditional variance")

    return TripleConditionalEnsemble(
        times=times,
        finest=ConditionalLevelRecord(**records["finest"]),
        middle=ConditionalLevelRecord(**records["middle"]),
        coarse=ConditionalLevelRecord(**records["coarse"]),
        reset_counts=reset_counts,
        reset_clock_sha256=clock_hasher.hexdigest(),
    )


def conditional_scalar_curves(
    record: ConditionalLevelRecord,
) -> dict[str, FloatArray]:
    """Return conditional expectations for all retained scalar observables."""

    position = np.asarray(record.position_means, dtype=float)
    velocity = np.asarray(record.velocity_means, dtype=float)
    c_rr = np.asarray(record.position_variance_per_axis, dtype=float)
    c_rv = np.asarray(record.position_velocity_covariance_per_axis, dtype=float)
    c_vv = np.asarray(record.velocity_variance_per_axis, dtype=float)
    expected_speed = np.sum(velocity * velocity, axis=2) + 2.0 * c_vv
    expected_raw_msd = np.sum(position * position, axis=2) + 2.0 * c_rr
    expected_r_dot_v = np.sum(position * velocity, axis=2) + 2.0 * c_rv
    return {
        "speed": expected_speed,
        "raw_msd": expected_raw_msd,
        "r_dot_v": expected_r_dot_v,
        "v_x": velocity[:, :, 0],
    }


def conditional_position_features(
    record: ConditionalLevelRecord,
) -> FloatArray:
    """Return sufficient features for unbiased centered covariance bootstrap."""

    position = np.asarray(record.position_means, dtype=float)
    c_trace = 2.0 * np.asarray(record.position_variance_per_axis, dtype=float)
    mean_norm_squared = np.sum(position * position, axis=2)
    return np.stack(
        (
            position[:, :, 0],
            position[:, :, 1],
            mean_norm_squared,
            c_trace,
        ),
        axis=2,
    )


def centered_covariance_curve_from_features(features: npt.ArrayLike) -> FloatArray:
    """Estimate total centered covariance by conditional variance decomposition."""

    values = np.asarray(features, dtype=float)
    if (
        values.ndim != 3
        or values.shape[2] != 4
        or values.shape[1] < 2
        or not np.all(np.isfinite(values))
    ):
        raise ValueError("features must be finite with shape (time,N>=2,4)")
    count = values.shape[1]
    mean = values.mean(axis=1)
    between = (count / (count - 1.0)) * (
        mean[:, 2] - mean[:, 0] * mean[:, 0] - mean[:, 1] * mean[:, 1]
    )
    return mean[:, 3] + between


def richardson_samples(
    finest: npt.ArrayLike,
    middle: npt.ArrayLike,
    coarse: npt.ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    """Return primary and secondary first-order Richardson trajectory units."""

    finest_values = np.asarray(finest, dtype=float)
    middle_values = np.asarray(middle, dtype=float)
    coarse_values = np.asarray(coarse, dtype=float)
    if (
        finest_values.shape != middle_values.shape
        or finest_values.shape != coarse_values.shape
        or not np.all(np.isfinite(finest_values))
        or not np.all(np.isfinite(middle_values))
        or not np.all(np.isfinite(coarse_values))
    ):
        raise ValueError("three finite matched arrays are required")
    return 2.0 * finest_values - middle_values, 2.0 * middle_values - coarse_values
