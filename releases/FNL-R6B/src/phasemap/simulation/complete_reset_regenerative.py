"""Independent regenerative PVTheta simulator used by frozen S-012.

The analytic T-012 implementation is intentionally not imported here.  This
module supplies only the stochastic route, paired fine/coarse coupling, and
trajectory-level estimators required by the preregistered validation plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Callable

import numpy as np

FINE_STEP = 1.0 / 512.0
COARSE_STEP = 1.0 / 256.0
CHUNK_SIZE = 32768


def _array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class PairedTerminalStates:
    """Terminal states from one shared-age, shared-increment coupling."""

    ages: np.ndarray
    fine_position: np.ndarray
    fine_velocity: np.ndarray
    fine_orientation: np.ndarray
    coarse_position: np.ndarray
    coarse_velocity: np.ndarray
    coarse_orientation: np.ndarray

    def array_sha256s(self) -> dict[str, str]:
        """Return canonical little-endian float64 hashes for every raw array."""

        return {
            "ages": _array_sha256(self.ages),
            "fine_position": _array_sha256(self.fine_position),
            "fine_velocity": _array_sha256(self.fine_velocity),
            "fine_orientation": _array_sha256(self.fine_orientation),
            "coarse_position": _array_sha256(self.coarse_position),
            "coarse_velocity": _array_sha256(self.coarse_velocity),
            "coarse_orientation": _array_sha256(self.coarse_orientation),
        }

    def age_sha256(self) -> str:
        """Backward-compatible convenience accessor for the age-stream hash."""

        return self.array_sha256s()["ages"]


def _finite_positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    parsed = float(value)
    invalid = parsed < 0.0 if allow_zero else parsed <= 0.0
    if not math.isfinite(parsed) or invalid:
        relation = ">= 0" if allow_zero else "> 0"
        raise ValueError(f"{name} must be finite and {relation}")
    return parsed


def _rng(base_seed: int, case_code: int, stream_code: int) -> np.random.Generator:
    parts = (base_seed, case_code, stream_code)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in parts):
        raise TypeError("seed and stream codes must be integers")
    seed = np.random.SeedSequence(list(parts))
    return np.random.Generator(np.random.PCG64(seed))


def draw_ages(
    count: int,
    reset_rate: float,
    base_seed: int,
    case_code: int,
) -> np.ndarray:
    """Draw all stationary renewal ages once in trajectory-index order."""

    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    rho = _finite_positive(reset_rate, "reset_rate")
    uniforms = _rng(base_seed, case_code, 1).random(count)
    return -np.log1p(-uniforms) / rho


def simulate_regenerative_paired(
    *,
    inertia: float,
    activity: float,
    reset_rate: float,
    count: int,
    base_seed: int,
    case_code: int,
    chunk_size: int = CHUNK_SIZE,
) -> PairedTerminalStates:
    """Simulate paired fine/coarse free excursions at exponential ages.

    Draw ordering is step-major within each fixed chunk.  Coarse paths consume
    no random variates: each coarse Brownian increment is exactly the sum of
    the one or two matching fine increments.
    """

    mass = _finite_positive(inertia, "inertia")
    peclet = _finite_positive(activity, "activity", allow_zero=True)
    rho = _finite_positive(reset_rate, "reset_rate")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    if not math.isclose(COARSE_STEP, 2.0 * FINE_STEP, rel_tol=0.0, abs_tol=0.0):
        raise RuntimeError("the frozen coarse step must equal two fine steps")

    ages = draw_ages(count, rho, base_seed, case_code)
    fine_position = np.zeros((count, 2), dtype=float)
    fine_velocity = np.zeros((count, 2), dtype=float)
    fine_orientation = np.zeros(count, dtype=float)
    coarse_position = np.zeros((count, 2), dtype=float)
    coarse_velocity = np.zeros((count, 2), dtype=float)
    coarse_orientation = np.zeros(count, dtype=float)
    translational_rng = _rng(base_seed, case_code, 2)
    rotational_rng = _rng(base_seed, case_code, 3)

    for start in range(0, count, chunk_size):
        stop = min(start + chunk_size, count)
        age = ages[start:stop]
        fp = fine_position[start:stop]
        fv = fine_velocity[start:stop]
        ft = fine_orientation[start:stop]
        cp = coarse_position[start:stop]
        cv = coarse_velocity[start:stop]
        ct = coarse_orientation[start:stop]

        maximum_step_index = int(math.ceil(float(age.max()) / FINE_STEP))
        pending_dt = np.zeros(stop - start, dtype=float)
        pending_translation = np.zeros((stop - start, 2), dtype=float)
        pending_rotation = np.zeros(stop - start, dtype=float)

        for step_index in range(maximum_step_index):
            left = step_index * FINE_STEP
            active = np.flatnonzero(age > left)
            if active.size == 0:
                continue

            remaining = age[active] - left
            dt = np.minimum(FINE_STEP, remaining)
            translation = (
                translational_rng.normal(size=(active.size, 2))
                * np.sqrt(dt)[:, None]
            )
            rotation = rotational_rng.normal(size=active.size) * np.sqrt(dt)

            direction = np.column_stack((np.cos(ft[active]), np.sin(ft[active])))
            fp[active] += fv[active] * dt[:, None]
            fv[active] += (
                -(fv[active] - peclet * direction) * (dt[:, None] / mass)
                + math.sqrt(2.0) * translation / mass
            )
            ft[active] += math.sqrt(2.0) * rotation

            pending_dt[active] += dt
            pending_translation[active] += translation
            pending_rotation[active] += rotation

            # Close after each pair.  If the trajectory ends first, close its
            # final singleton whether that interval is short or exactly h.
            terminal = remaining <= FINE_STEP
            close = (step_index % 2 == 1) | terminal
            close_indices = active[close]
            if close_indices.size:
                total_dt = pending_dt[close_indices]
                coarse_direction = np.column_stack(
                    (np.cos(ct[close_indices]), np.sin(ct[close_indices]))
                )
                cp[close_indices] += cv[close_indices] * total_dt[:, None]
                cv[close_indices] += (
                    -(cv[close_indices] - peclet * coarse_direction)
                    * (total_dt[:, None] / mass)
                    + math.sqrt(2.0) * pending_translation[close_indices] / mass
                )
                ct[close_indices] += math.sqrt(2.0) * pending_rotation[close_indices]
                pending_dt[close_indices] = 0.0
                pending_translation[close_indices] = 0.0
                pending_rotation[close_indices] = 0.0

        if (
            np.any(pending_dt != 0.0)
            or np.any(pending_translation != 0.0)
            or np.any(pending_rotation != 0.0)
        ):
            raise RuntimeError("unconsumed coarse coupling accumulator")

    return PairedTerminalStates(
        ages=ages,
        fine_position=fine_position,
        fine_velocity=fine_velocity,
        fine_orientation=fine_orientation,
        coarse_position=coarse_position,
        coarse_velocity=coarse_velocity,
        coarse_orientation=coarse_orientation,
    )


def mean_with_se(values: np.ndarray) -> tuple[float, float]:
    """Return a trajectory mean and its ordinary sample-mean SE."""

    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or sample.size < 2 or not np.all(np.isfinite(sample)):
        raise ValueError("values must be a finite one-dimensional sample of size >= 2")
    estimate = float(sample.mean())
    standard_error = float(sample.std(ddof=1) / math.sqrt(sample.size))
    return estimate, standard_error


def _validate_positions(positions: np.ndarray) -> np.ndarray:
    sample = np.asarray(positions, dtype=float)
    if (
        sample.ndim != 2
        or sample.shape[1] != 2
        or sample.shape[0] < 3
        or not np.all(np.isfinite(sample))
    ):
        raise ValueError("positions must be a finite (N, 2) array with N >= 3")
    return sample


def _jackknife_se(leave_one: np.ndarray) -> float:
    values = np.asarray(leave_one, dtype=float)
    if values.ndim != 1 or values.size < 3 or not np.all(np.isfinite(values)):
        raise ValueError("leave-one estimates must be finite and one-dimensional")
    count = values.size
    variance = (count - 1) / count * np.sum((values - values.mean()) ** 2)
    return float(math.sqrt(float(variance)))


def _covariance_trace_full_and_leave_one(
    positions: np.ndarray,
) -> tuple[float, np.ndarray]:
    sample = _validate_positions(positions)
    count = sample.shape[0]
    total = sample.sum(axis=0)
    squared_norm = np.sum(sample * sample, axis=1)
    total_squared_norm = float(squared_norm.sum())
    estimate = (
        total_squared_norm - float(total @ total) / count
    ) / (count - 1)
    leave_total = total[None, :] - sample
    leave_squared_norm = total_squared_norm - squared_norm
    leave_one = (
        leave_squared_norm
        - np.sum(leave_total * leave_total, axis=1) / (count - 1)
    ) / (count - 2)
    return float(estimate), leave_one


def covariance_trace_with_jackknife(positions: np.ndarray) -> tuple[float, float]:
    """Return unbiased covariance trace and exact O(N) delete-one SE."""

    estimate, leave_one = _covariance_trace_full_and_leave_one(positions)
    return estimate, _jackknife_se(leave_one)


def _kurtosis_full_and_leave_one(
    positions: np.ndarray,
) -> tuple[float, np.ndarray]:
    sample = _validate_positions(positions)
    count = sample.shape[0]
    radial_second = np.sum(sample * sample, axis=1)
    sum_second = float(radial_second.sum())
    sum_fourth = float(np.sum(radial_second * radial_second))
    if sum_second <= 0.0:
        raise ValueError("K is undefined for zero radial second moment")
    estimate = count * sum_fourth / (2.0 * sum_second * sum_second) - 1.0
    leave_second = sum_second - radial_second
    leave_fourth = sum_fourth - radial_second * radial_second
    if np.any(leave_second <= 0.0):
        raise ValueError("leave-one-out K is undefined")
    leave_one = (
        (count - 1) * leave_fourth / (2.0 * leave_second * leave_second) - 1.0
    )
    return float(estimate), leave_one


def kurtosis_with_jackknife(positions: np.ndarray) -> tuple[float, float]:
    """Return raw-radial excess K and exact O(N) delete-one SE."""

    estimate, leave_one = _kurtosis_full_and_leave_one(positions)
    return estimate, _jackknife_se(leave_one)


JackknifeStatistic = Callable[[np.ndarray], tuple[float, float]]


def paired_jackknife(
    fine: np.ndarray,
    coarse: np.ndarray,
    statistic: JackknifeStatistic,
) -> tuple[float, float]:
    """Return a matched fine-minus-coarse statistic and O(N) jackknife SE."""

    fine_sample = _validate_positions(fine)
    coarse_sample = _validate_positions(coarse)
    if fine_sample.shape != coarse_sample.shape:
        raise ValueError("paired fine and coarse arrays must have identical shapes")

    if statistic is covariance_trace_with_jackknife:
        fine_estimate, fine_leave = _covariance_trace_full_and_leave_one(fine_sample)
        coarse_estimate, coarse_leave = _covariance_trace_full_and_leave_one(
            coarse_sample
        )
    elif statistic is kurtosis_with_jackknife:
        fine_estimate, fine_leave = _kurtosis_full_and_leave_one(fine_sample)
        coarse_estimate, coarse_leave = _kurtosis_full_and_leave_one(coarse_sample)
    else:
        raise ValueError(
            "paired_jackknife accepts only covariance_trace_with_jackknife "
            "or kurtosis_with_jackknife"
        )

    leave_difference = fine_leave - coarse_leave
    return fine_estimate - coarse_estimate, _jackknife_se(leave_difference)
