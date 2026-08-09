"""Independent exact-clock paths for the S-070 trajectory validation.

This module implements the contract SDE directly.  It deliberately imports no
moment operator, formula registry, accepted result artifact, or analytic
reference implementation.  Fine and coarse Euler--Maruyama paths share exact
Poisson reset clocks.  Every coarse Wiener increment is the sum of the
corresponding fine increments, including partial intervals created by reset
events.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np
import numpy.typing as npt

from phasemap.common.model import ModelParams
from phasemap.simulation.protocols import PROTOCOL_REGISTRY, Protocol


FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


def _positive_integer(value: int, name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _finite_positive(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return parsed


def _exact_integer_ratio(numerator: float, denominator: float, name: str) -> int:
    ratio = numerator / denominator
    rounded = round(ratio)
    tolerance = 64.0 * np.finfo(float).eps * max(1.0, abs(ratio))
    if rounded < 1 or not math.isclose(
        ratio, rounded, rel_tol=0.0, abs_tol=tolerance
    ):
        raise ValueError(f"{name} must be a positive integer")
    return int(rounded)


@dataclass(frozen=True, slots=True)
class PairedPathConfig:
    """Fixed-work configuration for a paired fine/coarse ensemble chunk."""

    end_time: float
    fine_step: float
    record_step: float
    ensemble_size: int
    base_seed: int
    case_code: int
    stream_code: int
    max_reset_events_per_trajectory: int = 256
    record_events: bool = False

    def __post_init__(self) -> None:
        end_time = _finite_positive(self.end_time, "end_time")
        fine_step = _finite_positive(self.fine_step, "fine_step")
        record_step = _finite_positive(self.record_step, "record_step")
        _positive_integer(self.ensemble_size, "ensemble_size", minimum=3)
        _positive_integer(
            self.max_reset_events_per_trajectory,
            "max_reset_events_per_trajectory",
        )
        for name in ("base_seed", "case_code", "stream_code"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")

        total_steps = _exact_integer_ratio(
            end_time, fine_step, "end_time/fine_step"
        )
        record_steps = _exact_integer_ratio(
            record_step, fine_step, "record_step/fine_step"
        )
        if total_steps % 2:
            raise ValueError("end_time/fine_step must be even")
        if record_steps % 2:
            raise ValueError(
                "record_step/fine_step must be even so records are coarse boundaries"
            )
        if total_steps % record_steps:
            raise ValueError("end_time/record_step must be an integer")

    @property
    def coarse_step(self) -> float:
        return 2.0 * self.fine_step

    @property
    def total_fine_steps(self) -> int:
        return _exact_integer_ratio(
            self.end_time, self.fine_step, "end_time/fine_step"
        )

    @property
    def record_stride(self) -> int:
        return _exact_integer_ratio(
            self.record_step, self.fine_step, "record_step/fine_step"
        )


@dataclass(frozen=True, slots=True)
class ResetEventLog:
    """Optional exact pre/post event records used by deterministic tests."""

    trajectory_indices: IntArray
    times: FloatArray
    fine_pre_positions: FloatArray
    fine_post_positions: FloatArray
    fine_pre_velocities: FloatArray
    fine_post_velocities: FloatArray
    fine_pre_orientations: FloatArray
    fine_post_orientations: FloatArray
    coarse_pre_positions: FloatArray
    coarse_post_positions: FloatArray
    coarse_pre_velocities: FloatArray
    coarse_post_velocities: FloatArray
    coarse_pre_orientations: FloatArray
    coarse_post_orientations: FloatArray


@dataclass(frozen=True, slots=True)
class PairedPathEnsemble:
    """Recorded paired paths and reset-clock provenance for one chunk."""

    times: FloatArray
    fine_positions: FloatArray
    fine_velocities: FloatArray
    fine_orientations: FloatArray
    coarse_positions: FloatArray
    coarse_velocities: FloatArray
    coarse_orientations: FloatArray
    reset_counts: IntArray
    reset_clock_sha256: str
    event_log: ResetEventLog | None = None

    def array_sha256s(self) -> dict[str, str]:
        """Return canonical little-endian hashes for every recorded path array."""

        arrays = {
            "times": self.times,
            "fine_positions": self.fine_positions,
            "fine_velocities": self.fine_velocities,
            "fine_orientations": self.fine_orientations,
            "coarse_positions": self.coarse_positions,
            "coarse_velocities": self.coarse_velocities,
            "coarse_orientations": self.coarse_orientations,
            "reset_counts": self.reset_counts,
        }
        hashes: dict[str, str] = {}
        for name, values in arrays.items():
            if np.issubdtype(values.dtype, np.integer):
                canonical = np.ascontiguousarray(values, dtype="<i8")
            else:
                canonical = np.ascontiguousarray(values, dtype="<f8")
            hashes[name] = hashlib.sha256(canonical.tobytes()).hexdigest()
        return hashes


def _rng(
    base_seed: int,
    case_code: int,
    stream_code: int,
    component_code: int,
) -> np.random.Generator:
    seed = np.random.SeedSequence(
        [base_seed, case_code, stream_code, component_code]
    )
    return np.random.Generator(np.random.PCG64(seed))


def _strict_exponential(
    rng: np.random.Generator,
    count: int,
    rate: float,
) -> FloatArray:
    """Draw positive exponential waits, repairing only representational zeros."""

    waits = np.asarray(rng.exponential(1.0 / rate, size=count), dtype=float)
    zeros = waits <= 0.0
    while np.any(zeros):
        waits[zeros] = rng.exponential(1.0 / rate, size=int(np.sum(zeros)))
        zeros = waits <= 0.0
    return waits


def _advance(
    position: FloatArray,
    velocity: FloatArray,
    orientation: FloatArray,
    indices: IntArray,
    dt: FloatArray,
    translation: FloatArray,
    rotation: FloatArray,
    *,
    inertia: float,
    activity: float,
) -> None:
    if indices.size == 0:
        return
    old_velocity = velocity[indices].copy()
    old_orientation = orientation[indices].copy()
    direction = np.column_stack(
        (np.cos(old_orientation), np.sin(old_orientation))
    )
    position[indices] += old_velocity * dt[:, None]
    velocity[indices] += (
        -(old_velocity - activity * direction) * (dt[:, None] / inertia)
        + math.sqrt(2.0) * translation / inertia
    )
    orientation[indices] += math.sqrt(2.0) * rotation


def _apply_reset_arrays(
    position: FloatArray,
    velocity: FloatArray,
    orientation: FloatArray,
    indices: IntArray,
    protocol: Protocol,
) -> None:
    reset_map = PROTOCOL_REGISTRY[protocol]
    if reset_map.resets_position:
        position[indices] = 0.0
    if reset_map.resets_velocity:
        velocity[indices] = 0.0
    if reset_map.resets_orientation:
        orientation[indices] = 0.0


def simulate_paired_paths(
    params: ModelParams,
    protocol: Protocol,
    config: PairedPathConfig,
) -> PairedPathEnsemble:
    """Simulate a fixed chunk with exact clocks and paired discretizations.

    The same ``base_seed``, ``case_code``, and ``stream_code`` produce the
    same reset clocks and Wiener increments for every protocol.  This enables
    disclosed common-random-number protocol contrasts.  Distinct stream codes
    create independent streams for the required unpaired confirmations.
    """

    if not isinstance(protocol, Protocol):
        raise TypeError("protocol must be a Protocol")
    count = config.ensemble_size
    mass = float(params.inertia)
    activity = float(params.activity)
    reset_rate = float(params.reset_rate)

    reset_rng = _rng(config.base_seed, config.case_code, config.stream_code, 1)
    translation_rng = _rng(
        config.base_seed, config.case_code, config.stream_code, 2
    )
    rotation_rng = _rng(
        config.base_seed, config.case_code, config.stream_code, 3
    )

    fine_position = np.zeros((count, 2), dtype=float)
    fine_velocity = np.zeros((count, 2), dtype=float)
    fine_orientation = np.zeros(count, dtype=float)
    coarse_position = np.zeros((count, 2), dtype=float)
    coarse_velocity = np.zeros((count, 2), dtype=float)
    coarse_orientation = np.zeros(count, dtype=float)

    pending_dt = np.zeros(count, dtype=float)
    pending_translation = np.zeros((count, 2), dtype=float)
    pending_rotation = np.zeros(count, dtype=float)
    reset_counts = np.zeros(count, dtype=np.int64)
    next_reset = (
        _strict_exponential(reset_rng, count, reset_rate)
        if reset_rate > 0.0
        else np.full(count, math.inf, dtype=float)
    )
    clock_hasher = hashlib.sha256()

    times = np.arange(
        config.total_fine_steps // config.record_stride + 1, dtype=float
    ) * config.record_step
    shape_vector = (times.size, count, 2)
    shape_scalar = (times.size, count)
    fine_positions = np.empty(shape_vector, dtype=float)
    fine_velocities = np.empty(shape_vector, dtype=float)
    fine_orientations = np.empty(shape_scalar, dtype=float)
    coarse_positions = np.empty(shape_vector, dtype=float)
    coarse_velocities = np.empty(shape_vector, dtype=float)
    coarse_orientations = np.empty(shape_scalar, dtype=float)
    fine_positions[0] = fine_position
    fine_velocities[0] = fine_velocity
    fine_orientations[0] = fine_orientation
    coarse_positions[0] = coarse_position
    coarse_velocities[0] = coarse_velocity
    coarse_orientations[0] = coarse_orientation

    event_lists: dict[str, list[FloatArray | IntArray]] | None
    if config.record_events:
        event_lists = {
            "trajectory_indices": [],
            "times": [],
            "fine_pre_positions": [],
            "fine_post_positions": [],
            "fine_pre_velocities": [],
            "fine_post_velocities": [],
            "fine_pre_orientations": [],
            "fine_post_orientations": [],
            "coarse_pre_positions": [],
            "coarse_post_positions": [],
            "coarse_pre_velocities": [],
            "coarse_post_velocities": [],
            "coarse_pre_orientations": [],
            "coarse_post_orientations": [],
        }
    else:
        event_lists = None

    all_indices = np.arange(count, dtype=np.int64)

    def flush(indices: IntArray) -> None:
        if indices.size == 0:
            return
        positive = pending_dt[indices] > 0.0
        active = indices[positive]
        if active.size:
            _advance(
                coarse_position,
                coarse_velocity,
                coarse_orientation,
                active,
                pending_dt[active].copy(),
                pending_translation[active].copy(),
                pending_rotation[active].copy(),
                inertia=mass,
                activity=activity,
            )
        pending_dt[indices] = 0.0
        pending_translation[indices] = 0.0
        pending_rotation[indices] = 0.0

    record_index = 1
    for step_index in range(config.total_fine_steps):
        interval_start = step_index * config.fine_step
        interval_end = (step_index + 1) * config.fine_step
        local_time = np.full(count, interval_start, dtype=float)

        while True:
            unfinished = local_time < interval_end
            if not np.any(unfinished):
                break

            active = np.flatnonzero(unfinished).astype(np.int64, copy=False)
            target = np.minimum(next_reset[active], interval_end)
            event_due = next_reset[active] <= interval_end
            if np.any(
                reset_counts[active[event_due]]
                >= config.max_reset_events_per_trajectory
            ):
                raise RuntimeError(
                    "locked reset-event cap exceeded before completing "
                    "the exact-clock trajectory"
                )
            dt = target - local_time[active]
            if np.any(dt <= 0.0):
                raise RuntimeError("nonpositive exact-clock integration segment")

            translation = (
                translation_rng.normal(size=(active.size, 2))
                * np.sqrt(dt)[:, None]
            )
            rotation = rotation_rng.normal(size=active.size) * np.sqrt(dt)
            _advance(
                fine_position,
                fine_velocity,
                fine_orientation,
                active,
                dt,
                translation,
                rotation,
                inertia=mass,
                activity=activity,
            )
            pending_dt[active] += dt
            pending_translation[active] += translation
            pending_rotation[active] += rotation
            local_time[active] = target

            event_mask = next_reset[active] <= interval_end
            event_indices = active[event_mask]
            if event_indices.size == 0:
                continue

            event_times = next_reset[event_indices].copy()
            local_time[event_indices] = event_times
            flush(event_indices)

            if event_lists is not None:
                event_lists["trajectory_indices"].append(event_indices.copy())
                event_lists["times"].append(event_times)
                event_lists["fine_pre_positions"].append(
                    fine_position[event_indices].copy()
                )
                event_lists["fine_pre_velocities"].append(
                    fine_velocity[event_indices].copy()
                )
                event_lists["fine_pre_orientations"].append(
                    fine_orientation[event_indices].copy()
                )
                event_lists["coarse_pre_positions"].append(
                    coarse_position[event_indices].copy()
                )
                event_lists["coarse_pre_velocities"].append(
                    coarse_velocity[event_indices].copy()
                )
                event_lists["coarse_pre_orientations"].append(
                    coarse_orientation[event_indices].copy()
                )

            _apply_reset_arrays(
                fine_position,
                fine_velocity,
                fine_orientation,
                event_indices,
                protocol,
            )
            _apply_reset_arrays(
                coarse_position,
                coarse_velocity,
                coarse_orientation,
                event_indices,
                protocol,
            )

            if event_lists is not None:
                event_lists["fine_post_positions"].append(
                    fine_position[event_indices].copy()
                )
                event_lists["fine_post_velocities"].append(
                    fine_velocity[event_indices].copy()
                )
                event_lists["fine_post_orientations"].append(
                    fine_orientation[event_indices].copy()
                )
                event_lists["coarse_post_positions"].append(
                    coarse_position[event_indices].copy()
                )
                event_lists["coarse_post_velocities"].append(
                    coarse_velocity[event_indices].copy()
                )
                event_lists["coarse_post_orientations"].append(
                    coarse_orientation[event_indices].copy()
                )

            clock_hasher.update(
                np.ascontiguousarray(event_indices, dtype="<i8").tobytes()
            )
            clock_hasher.update(
                np.ascontiguousarray(event_times, dtype="<f8").tobytes()
            )
            reset_counts[event_indices] += 1
            next_reset[event_indices] = event_times + _strict_exponential(
                reset_rng, event_indices.size, reset_rate
            )

        if (step_index + 1) % 2 == 0:
            flush(all_indices)
        if (step_index + 1) % config.record_stride == 0:
            if np.any(pending_dt != 0.0):
                raise RuntimeError("record boundary contains unflushed coarse noise")
            fine_positions[record_index] = fine_position
            fine_velocities[record_index] = fine_velocity
            fine_orientations[record_index] = fine_orientation
            coarse_positions[record_index] = coarse_position
            coarse_velocities[record_index] = coarse_velocity
            coarse_orientations[record_index] = coarse_orientation
            record_index += 1

    if record_index != times.size:
        raise RuntimeError("record schedule was not filled exactly")
    arrays = (
        fine_positions,
        fine_velocities,
        fine_orientations,
        coarse_positions,
        coarse_velocities,
        coarse_orientations,
    )
    if any(not np.all(np.isfinite(values)) for values in arrays):
        raise FloatingPointError("nonfinite simulated path state")

    event_log: ResetEventLog | None = None
    if event_lists is not None:
        def join(name: str, width: int | None = None) -> FloatArray | IntArray:
            values = event_lists[name]
            if values:
                return np.concatenate(values, axis=0)
            if name == "trajectory_indices":
                return np.empty(0, dtype=np.int64)
            if width is None:
                return np.empty(0, dtype=float)
            return np.empty((0, width), dtype=float)

        event_log = ResetEventLog(
            trajectory_indices=join("trajectory_indices"),  # type: ignore[arg-type]
            times=join("times"),  # type: ignore[arg-type]
            fine_pre_positions=join("fine_pre_positions", 2),  # type: ignore[arg-type]
            fine_post_positions=join("fine_post_positions", 2),  # type: ignore[arg-type]
            fine_pre_velocities=join("fine_pre_velocities", 2),  # type: ignore[arg-type]
            fine_post_velocities=join("fine_post_velocities", 2),  # type: ignore[arg-type]
            fine_pre_orientations=join("fine_pre_orientations"),  # type: ignore[arg-type]
            fine_post_orientations=join("fine_post_orientations"),  # type: ignore[arg-type]
            coarse_pre_positions=join("coarse_pre_positions", 2),  # type: ignore[arg-type]
            coarse_post_positions=join("coarse_post_positions", 2),  # type: ignore[arg-type]
            coarse_pre_velocities=join("coarse_pre_velocities", 2),  # type: ignore[arg-type]
            coarse_post_velocities=join("coarse_post_velocities", 2),  # type: ignore[arg-type]
            coarse_pre_orientations=join("coarse_pre_orientations"),  # type: ignore[arg-type]
            coarse_post_orientations=join("coarse_post_orientations"),  # type: ignore[arg-type]
        )

    return PairedPathEnsemble(
        times=times,
        fine_positions=fine_positions,
        fine_velocities=fine_velocities,
        fine_orientations=fine_orientations,
        coarse_positions=coarse_positions,
        coarse_velocities=coarse_velocities,
        coarse_orientations=coarse_orientations,
        reset_counts=reset_counts,
        reset_clock_sha256=clock_hasher.hexdigest(),
        event_log=event_log,
    )


def mean_and_standard_error(values: npt.ArrayLike) -> tuple[float, float]:
    """Return a finite trajectory mean and ordinary trajectory-level SE."""

    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or sample.size < 2 or not np.all(np.isfinite(sample)):
        raise ValueError("values must be a finite one-dimensional sample of size >= 2")
    return (
        float(sample.mean()),
        float(sample.std(ddof=1) / math.sqrt(sample.size)),
    )


def paired_mean_and_standard_error(
    left: npt.ArrayLike,
    right: npt.ArrayLike,
) -> tuple[float, float]:
    """Return mean(left-right) and its matched trajectory-level SE."""

    left_sample = np.asarray(left, dtype=float)
    right_sample = np.asarray(right, dtype=float)
    if left_sample.shape != right_sample.shape:
        raise ValueError("paired samples must have identical shapes")
    return mean_and_standard_error(left_sample - right_sample)


def covariance_trace_curve(positions: npt.ArrayLike) -> FloatArray:
    """Return the unbiased centered spatial covariance trace at each time."""

    sample = np.asarray(positions, dtype=float)
    if (
        sample.ndim != 3
        or sample.shape[2] != 2
        or sample.shape[1] < 3
        or not np.all(np.isfinite(sample))
    ):
        raise ValueError("positions must be finite with shape (time, N>=3, 2)")
    count = sample.shape[1]
    centered = sample - sample.mean(axis=1, keepdims=True)
    return np.sum(centered * centered, axis=(1, 2)) / (count - 1)


def effective_diffusion(
    times: npt.ArrayLike,
    positions: npt.ArrayLike,
    *,
    window_start_fraction: float,
) -> float:
    """Fit ``Tr Cov(r)/(4t)`` through a late-window covariance slope.

    This function returns only the point estimate.  Contract-conformant
    uncertainty must come from whole-trajectory bootstrap resampling; OLS
    repeated-time standard errors are intentionally not exposed.
    """

    time = np.asarray(times, dtype=float)
    if (
        time.ndim != 1
        or time.size < 3
        or not np.all(np.isfinite(time))
        or np.any(np.diff(time) <= 0.0)
    ):
        raise ValueError("times must be finite and strictly increasing")
    if not math.isfinite(window_start_fraction) or not (
        0.0 < window_start_fraction < 1.0
    ):
        raise ValueError("window_start_fraction must lie strictly between 0 and 1")
    curve = covariance_trace_curve(positions)
    if curve.shape != time.shape:
        raise ValueError("positions time axis must match times")
    mask = time >= window_start_fraction * time[-1]
    if np.count_nonzero(mask) < 3:
        raise ValueError("late window must contain at least three recorded times")
    x = time[mask]
    y = curve[mask]
    centered_x = x - x.mean()
    slope = float(np.dot(centered_x, y - y.mean()) / np.dot(centered_x, centered_x))
    return slope / 4.0


def project_primary_sample_size(
    *,
    pilot_size: int,
    quantile: float,
    pilot_standard_error: float,
    margin: float,
    pilot_discrepancy: float,
    b_window: float,
    b_disc: float,
    compute_cap: int,
) -> int | None:
    """Apply the exact Section 7.6 one-time projection, failing closed."""

    _positive_integer(pilot_size, "pilot_size", minimum=2)
    _positive_integer(compute_cap, "compute_cap", minimum=2)
    values = (
        quantile,
        pilot_standard_error,
        margin,
        pilot_discrepancy,
        b_window,
        b_disc,
    )
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("projection inputs must be finite")
    if (
        quantile <= 0.0
        or pilot_standard_error < 0.0
        or margin <= 0.0
        or b_window < 0.0
        or b_disc < 0.0
    ):
        raise ValueError("projection scales must have valid signs")
    denominator = margin - abs(pilot_discrepancy) - b_window - b_disc
    if denominator <= 0.0:
        return None
    target = math.ceil(
        pilot_size
        * (quantile * pilot_standard_error / denominator) ** 2
    )
    target = max(2, target)
    return target if target <= compute_cap else None


def classify_expanded_interval(
    *,
    lower: float,
    upper: float,
    margin: float,
    b_window: float,
    b_disc: float,
) -> str:
    """Classify a discrepancy interval exactly as Contract Section 7.2."""

    values = (lower, upper, margin, b_window, b_disc)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("classification inputs must be finite")
    if lower > upper:
        raise ValueError("lower interval endpoint exceeds upper endpoint")
    if margin <= 0.0 or b_window < 0.0 or b_disc < 0.0:
        raise ValueError("margin must be positive and envelopes nonnegative")
    expanded_lower = lower - b_window - b_disc
    expanded_upper = upper + b_window + b_disc
    if expanded_lower >= -margin and expanded_upper <= margin:
        return "validated"
    if expanded_lower > margin or expanded_upper < -margin:
        return "contradicted"
    return "unresolved"
