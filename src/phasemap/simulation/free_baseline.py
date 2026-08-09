"""Vectorized, paired Euler--Maruyama checks for the free baseline.

This module intentionally covers only ``rho=0``.  It keeps fine and coarse
paths coupled by constructing every coarse Wiener increment as the sum of two
fine increments, as required for the contract's discretization comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

import numpy as np
import numpy.typing as npt


OBSERVABLE_NAMES = (
    "mean_position_x",
    "mean_velocity_x",
    "velocity_dot_orientation",
    "position_dot_orientation",
    "mean_squared_speed",
    "mean_position_dot_velocity",
    "mean_squared_displacement",
    "centered_spatial_variance",
)


@dataclass(frozen=True, slots=True)
class FreeEnsembleEstimate:
    """Final-time free-process estimates and trajectory-level standard errors."""

    values: dict[str, float]
    standard_errors: dict[str, float]


@dataclass(frozen=True, slots=True)
class PairedFreeEstimates:
    """Fine/coarse estimates sharing one deterministic Brownian realization."""

    fine: FreeEnsembleEstimate
    coarse: FreeEnsembleEstimate
    paired_standard_errors: dict[str, float]
    fine_positions: npt.NDArray[np.float64]
    coarse_positions: npt.NDArray[np.float64]


def _samples(
    position: npt.NDArray[np.float64],
    velocity: npt.NDArray[np.float64],
    orientation: npt.NDArray[np.float64],
) -> dict[str, npt.NDArray[np.float64]]:
    direction = np.column_stack((np.cos(orientation), np.sin(orientation)))
    centered_position = position - position.mean(axis=0)
    return {
        "mean_position_x": position[:, 0],
        "mean_velocity_x": velocity[:, 0],
        "velocity_dot_orientation": np.sum(velocity * direction, axis=1),
        "position_dot_orientation": np.sum(position * direction, axis=1),
        "mean_squared_speed": np.sum(velocity * velocity, axis=1),
        "mean_position_dot_velocity": np.sum(position * velocity, axis=1),
        "mean_squared_displacement": np.sum(position * position, axis=1),
        "centered_spatial_variance": np.sum(centered_position * centered_position, axis=1),
    }


def _estimate(samples: dict[str, npt.NDArray[np.float64]]) -> FreeEnsembleEstimate:
    return FreeEnsembleEstimate(
        values={name: float(np.mean(value)) for name, value in samples.items()},
        standard_errors={
            name: float(np.std(value, ddof=1) / math.sqrt(value.size))
            for name, value in samples.items()
        },
    )


def covariance_trace_jackknife(
    positions: npt.NDArray[np.float64],
    paired_positions: npt.NDArray[np.float64] | None = None,
) -> tuple[float, float]:
    """Unbiased covariance-trace estimate and delete-one jackknife SE."""
    n = len(positions)
    if n < 3:
        raise ValueError("covariance jackknife needs at least three trajectories")
    def leave_one(values: npt.NDArray[np.float64]) -> tuple[float, npt.NDArray[np.float64]]:
        total, total2 = values.sum(axis=0), float(np.sum(values * values))
        value = (total2 - n * float(np.sum((total / n) ** 2))) / (n - 1)
        omitted = (total2 - np.sum(values * values, axis=1) - (n - 1) * np.sum(((total - values) / (n - 1)) ** 2, axis=1)) / (n - 2)
        return value, omitted
    value, omitted = leave_one(positions)
    if paired_positions is not None:
        other, other_omitted = leave_one(paired_positions)
        value, omitted = value - other, omitted - other_omitted
    return float(value), float(math.sqrt((n - 1) / n * np.sum((omitted - omitted.mean()) ** 2)))


def simulate_free_paired(
    *,
    inertia: float,
    activity: float,
    end_time: float,
    fine_step: float,
    ensemble_size: int,
    seed: int,
) -> PairedFreeEstimates:
    """Simulate coupled free paths at ``fine_step`` and ``2*fine_step``.

    The routine is a fixed-work, non-adaptive calculation.  It uses the same
    pre-step Euler--Maruyama convention as :mod:`integrator` and rejects reset
    parameters by design: it is solely the exact ``rho=0`` baseline route.
    """
    if not all(math.isfinite(value) for value in (inertia, activity, end_time, fine_step)):
        raise ValueError("physical parameters must be finite")
    if inertia <= 0 or activity < 0 or end_time <= 0 or fine_step <= 0:
        raise ValueError("require inertia, end_time, and fine_step > 0 and activity >= 0")
    if ensemble_size < 3:
        raise ValueError("ensemble_size must be at least three")
    steps = round(end_time / fine_step)
    if steps < 2 or steps % 2 or not math.isclose(steps * fine_step, end_time, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("end_time/fine_step must be an even integer")

    rng = np.random.default_rng(seed)
    fine_position = np.zeros((ensemble_size, 2))
    fine_velocity = np.zeros((ensemble_size, 2))
    fine_orientation = np.zeros(ensemble_size)
    coarse_position = np.zeros((ensemble_size, 2))
    coarse_velocity = np.zeros((ensemble_size, 2))
    coarse_orientation = np.zeros(ensemble_size)
    sqrt_fine = math.sqrt(fine_step)

    for step in range(0, steps, 2):
        translational = sqrt_fine * rng.normal(size=(2, ensemble_size, 2))
        rotational = sqrt_fine * rng.normal(size=(2, ensemble_size))
        for offset in range(2):
            direction = np.column_stack((np.cos(fine_orientation), np.sin(fine_orientation)))
            fine_position += fine_velocity * fine_step
            fine_velocity += (-(fine_velocity - activity * direction) * fine_step / inertia
                              + math.sqrt(2.0) * translational[offset] / inertia)
            fine_orientation += math.sqrt(2.0) * rotational[offset]

        coarse_step = 2.0 * fine_step
        direction = np.column_stack((np.cos(coarse_orientation), np.sin(coarse_orientation)))
        coarse_position += coarse_velocity * coarse_step
        coarse_velocity += (-(coarse_velocity - activity * direction) * coarse_step / inertia
                            + math.sqrt(2.0) * (translational[0] + translational[1]) / inertia)
        coarse_orientation += math.sqrt(2.0) * (rotational[0] + rotational[1])

    fine_samples = _samples(fine_position, fine_velocity, fine_orientation)
    coarse_samples = _samples(coarse_position, coarse_velocity, coarse_orientation)
    fine = _estimate(fine_samples)
    coarse = _estimate(coarse_samples)
    fine_cov, fine_cov_se = covariance_trace_jackknife(fine_position)
    coarse_cov, coarse_cov_se = covariance_trace_jackknife(coarse_position)
    paired_cov, paired_cov_se = covariance_trace_jackknife(fine_position, coarse_position)
    fine = replace(fine, values={**fine.values, "centered_spatial_variance": fine_cov}, standard_errors={**fine.standard_errors, "centered_spatial_variance": fine_cov_se})
    coarse = replace(coarse, values={**coarse.values, "centered_spatial_variance": coarse_cov}, standard_errors={**coarse.standard_errors, "centered_spatial_variance": coarse_cov_se})
    paired_standard_errors = {
        name: float(np.std(fine_samples[name] - coarse_samples[name], ddof=1) / math.sqrt(ensemble_size))
        for name in OBSERVABLE_NAMES
    }
    paired_standard_errors["centered_spatial_variance"] = paired_cov_se
    return PairedFreeEstimates(
        fine, coarse, paired_standard_errors, fine_position, coarse_position
    )
