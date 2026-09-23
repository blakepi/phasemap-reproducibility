"""Streaming, whole-trajectory statistics for the prospective S-074 study."""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


_LINEAR = ("speed", "u_xx", "v_x", "raw_msd", "r_dot_v")


def _array(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


def _window_indices(times: np.ndarray) -> list[np.ndarray]:
    end = float(times[-1])
    return [np.flatnonzero(times >= fraction * end) for fraction in (0.5, 2 / 3, 3 / 4)]


def build_features(paths: Any, times: Any, mode: str) -> tuple[np.ndarray, dict[str, Any]]:
    """Encode independent paths as sufficient features for all fixed windows.

    ``paths`` has shape ``(3, n_times, n_paths, 5)`` with state order
    ``rx, ry, vx, vy, theta``.  The returned layout contains only JSON values.
    """
    values = _array(paths, "paths")
    clock = _array(times, "times")
    if values.ndim != 4 or values.shape[0] != 3 or values.shape[-1] != 5:
        raise ValueError("paths must have shape (3, n_times, n_paths, 5)")
    if clock.ndim != 1 or clock.size != values.shape[1] or clock.size == 0:
        raise ValueError("times must be a nonempty vector matching paths")
    if np.any(np.diff(clock) <= 0):
        raise ValueError("times must be strictly increasing")
    if values.shape[2] < 3:
        raise ValueError("spatial jackknife needs at least three trajectories")
    if mode not in {"localized", "diffusive"}:
        raise ValueError("mode must be localized or diffusive")
    windows = _window_indices(clock)
    active = np.unique(np.concatenate(windows))
    n_paths = values.shape[2]
    columns: list[np.ndarray] = []
    linear: dict[str, list[list[int]]] = {name: [[], [], []] for name in _LINEAR}
    q_index: list[list[int]] = [[], [], []]
    position: list[list[list[int]]] = [[[] for _ in active] for _ in range(3)]

    rx, ry, vx, vy, theta = (values[..., index] for index in range(5))
    samples = {
        "speed": vx * vx + vy * vy,
        "u_xx": np.cos(theta) ** 2,
        "v_x": vx,
        "raw_msd": rx * rx + ry * ry,
        "r_dot_v": rx * vx + ry * vy,
    }
    for level in range(3):
        for window in windows:
            for name in _LINEAR:
                linear[name][level].append(len(columns))
                columns.append(samples[name][level, window].mean(axis=0))
            if mode == "localized":
                weights = np.full(window.size, 1.0 / window.size)
            else:
                centered = clock[window] - clock[window].mean()
                denominator = np.dot(centered, centered)
                weights = np.zeros(window.size) if denominator == 0.0 else centered / denominator
            q_index[level].append(len(columns))
            columns.append(np.einsum("t,tn->n", weights, rx[level, window] ** 2 + ry[level, window] ** 2))
        for local, time_index in enumerate(active):
            for coordinate, data in enumerate((rx, ry)):
                position[level][local].append(len(columns))
                columns.append(data[level, time_index])
    local_index = {int(time): index for index, time in enumerate(active)}
    layout: dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "times": clock.tolist(),
        "windows": [item.tolist() for item in windows],
        "active_times": active.tolist(),
        "linear": linear,
        "q_index": q_index,
        "position": position,
        "position_lookup": {str(key): value for key, value in local_index.items()},
    }
    return np.column_stack(columns), layout


class FeatureAccumulator:
    """Chan-mergeable mean and centered cross-product accumulator."""

    def __init__(self, n: int = 0, mean: Any | None = None, m2: Any | None = None) -> None:
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)):
            raise ValueError("invalid accumulator state")
        self.n = int(n)
        self.mean = np.asarray([] if mean is None else mean, dtype=float)
        self.m2 = np.asarray([] if m2 is None else m2, dtype=float)
        if (
            self.n < 0
            or not np.all(np.isfinite(self.mean))
            or not np.all(np.isfinite(self.m2))
            or (self.n == 0 and (self.mean.size or self.m2.size))
            or (self.n > 0 and (self.mean.ndim != 1 or self.mean.size == 0 or self.m2.shape != (self.mean.size, self.mean.size)))
        ):
            raise ValueError("invalid accumulator state")

    def add(self, features: Any) -> "FeatureAccumulator":
        values = _array(features, "features")
        if values.ndim != 2 or values.shape[0] == 0:
            raise ValueError("features must be a nonempty two-dimensional array")
        count = values.shape[0]
        mean = values.mean(axis=0)
        centered = values - mean
        m2 = centered.T @ centered
        if self.n == 0:
            self.n, self.mean, self.m2 = count, mean, m2
            return self
        if self.mean.size != mean.size:
            raise ValueError("feature width changed during streaming accumulation")
        delta = mean - self.mean
        total = self.n + count
        self.m2 += m2 + np.outer(delta, delta) * (self.n * count / total)
        self.mean += delta * (count / total)
        self.n = total
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "mean": self.mean.tolist(), "m2": self.m2.tolist()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeatureAccumulator":
        if not isinstance(payload, dict):
            raise ValueError("invalid accumulator state")
        try:
            return cls(payload["n"], payload["mean"], payload["m2"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid accumulator state") from error


def _state(stats: dict[str, Any]) -> tuple[int, np.ndarray, np.ndarray]:
    item = FeatureAccumulator.from_dict(stats)
    if item.n < 3:
        raise ValueError("spatial jackknife needs at least three trajectories")
    return item.n, item.mean, item.m2 / (item.n - 1)


def _spatial_coeff(n: int, mean: np.ndarray, layout: dict[str, Any], window: int, levels: np.ndarray) -> tuple[float, np.ndarray]:
    mode = layout["mode"]
    clock = np.asarray(layout["times"], dtype=float)
    window_times = np.asarray(layout["windows"][window], dtype=int)
    if mode == "diffusive" and window_times.size < 2:
        raise ValueError("diffusive windows need at least two record times")
    if mode == "localized":
        weights = np.full(window_times.size, 1.0 / window_times.size)
        factor = 1.0
    else:
        selected = clock[window_times]
        centered = selected - selected.mean()
        weights = centered / np.dot(centered, centered)
        factor = 0.25
    coefficient = np.zeros_like(mean)
    value = 0.0
    lookup = layout["position_lookup"]
    for level, level_weight in enumerate(levels):
        if level_weight == 0:
            continue
        q = int(layout["q_index"][level][window])
        mean_square = mean[q]
        centered_square = 0.0
        for time_index, weight in zip(window_times, weights):
            local = int(lookup[str(int(time_index))])
            x, y = (int(index) for index in layout["position"][level][local])
            centered_square += weight * (mean[x] ** 2 + mean[y] ** 2)
            coefficient[x] += level_weight * factor * n / (n - 2) * (-2.0 * weight * mean[x])
            coefficient[y] += level_weight * factor * n / (n - 2) * (-2.0 * weight * mean[y])
        value += level_weight * factor * n / (n - 1) * (mean_square - centered_square)
        coefficient[q] += level_weight * factor * n / (n - 2)
    return value, coefficient


def _functional(stats: dict[str, Any], layout: dict[str, Any], observable: str, window: int, level_coeffs: Sequence[float]) -> tuple[float, np.ndarray]:
    n, mean, covariance = _state(stats)
    del covariance
    levels = _array(level_coeffs, "level_coeffs")
    if levels.shape != (3,) or not 0 <= window < 3:
        raise ValueError("level_coeffs must have three entries and window must be 0, 1, or 2")
    if observable == "spatial":
        return _spatial_coeff(n, mean, layout, window, levels)
    if observable not in _LINEAR:
        raise ValueError(f"unknown observable {observable!r}")
    coefficient = np.zeros_like(mean)
    for level, weight in enumerate(levels):
        coefficient[int(layout["linear"][observable][level][window])] += weight
    return float(coefficient @ mean), coefficient


def estimate(stats: dict[str, Any], layout: dict[str, Any], observable: str, window: int = 0, level_coeffs: Sequence[float] = (1.0, 0.0, 0.0)) -> dict[str, float]:
    """Return a level/window functional and its paired whole-path SE."""
    n, _, covariance = _state(stats)
    value, coefficient = _functional(stats, layout, observable, window, level_coeffs)
    variance = float(coefficient @ covariance @ coefficient) / n
    return {"value": value, "se": _standard_error(variance, covariance, coefficient, n)}


def paired_difference(stats: dict[str, Any], layout: dict[str, Any], specs: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Combine arbitrary fixed functionals while retaining shared-path covariance."""
    n, _, covariance = _state(stats)
    total_value = 0.0
    total_coeff = np.zeros(covariance.shape[0])
    for spec in specs:
        multiplier = float(spec.get("coefficient", 1.0))
        value, coefficient = _functional(stats, layout, spec["observable"], int(spec.get("window", 0)), spec.get("level_coeffs", (1.0, 0.0, 0.0)))
        total_value += multiplier * value
        total_coeff += multiplier * coefficient
    variance = float(total_coeff @ covariance @ total_coeff) / n
    return {"value": total_value, "se": _standard_error(variance, covariance, total_coeff, n)}


def _value_from_mean(mean: np.ndarray, n: int, layout: dict[str, Any], observable: str, window: int, levels: Sequence[float]) -> float:
    """Evaluate a bootstrap replicate without allocating an ``F x F`` matrix."""
    values = _array(mean, "mean")
    coefficients = _array(levels, "level_coeffs")
    if values.ndim != 1 or coefficients.shape != (3,) or not 0 <= window < 3:
        raise ValueError("invalid bootstrap functional")
    if observable in _LINEAR:
        return float(sum(
            weight * values[int(layout["linear"][observable][level][window])]
            for level, weight in enumerate(coefficients)
        ))
    if observable != "spatial":
        raise ValueError(f"unknown observable {observable!r}")
    mode = layout["mode"]
    clock = np.asarray(layout["times"], dtype=float)
    window_times = np.asarray(layout["windows"][window], dtype=int)
    if mode == "diffusive" and window_times.size < 2:
        raise ValueError("diffusive windows need at least two record times")
    if mode == "localized":
        weights, factor = np.full(window_times.size, 1.0 / window_times.size), 1.0
    else:
        centered = clock[window_times] - clock[window_times].mean()
        weights, factor = centered / np.dot(centered, centered), 0.25
    output, lookup = 0.0, layout["position_lookup"]
    for level, level_weight in enumerate(coefficients):
        if level_weight == 0:
            continue
        q = int(layout["q_index"][level][window])
        centered_square = 0.0
        for time_index, weight in zip(window_times, weights):
            local = int(lookup[str(int(time_index))])
            x, y = (int(index) for index in layout["position"][level][local])
            centered_square += weight * (values[x] ** 2 + values[y] ** 2)
        output += level_weight * factor * n / (n - 1) * (values[q] - centered_square)
    return float(output)


def _standard_error(variance: float, covariance: np.ndarray, coefficient: np.ndarray, n: int) -> float:
    """Allow only floating-point-scale negative quadratic-form roundoff."""
    scale = max(1.0, float(np.max(np.abs(covariance))) * float(np.dot(coefficient, coefficient)) / n)
    if not math.isfinite(variance) or variance < -64.0 * np.finfo(float).eps * scale:
        raise ValueError("negative estimated variance")
    return math.sqrt(max(variance, 0.0))


def bootstrap_se(features: Any, layout: dict[str, Any], observable: str, window: int = 0, level_coeffs: Sequence[float] = (1.0, 0.0, 0.0), reps: int = 1024, seed: int = 0, batch_size: int = 128) -> dict[str, float]:
    """Ordinary multinomial whole-trajectory bootstrap, reduced in batches."""
    values = _array(features, "features")
    if values.ndim != 2 or values.shape[0] < 3 or reps < 4 or reps % 2 or batch_size < 1:
        raise ValueError("need >=3 paths, an even reps >=4, and positive batch_size")
    rng = np.random.default_rng(seed)
    n = values.shape[0]
    samples: list[float] = []
    probabilities = np.full(n, 1.0 / n)
    for start in range(0, reps, batch_size):
        count = min(batch_size, reps - start)
        weights = rng.multinomial(n, probabilities, size=count)
        means = (weights @ values) / n
        samples.extend(_value_from_mean(item, n, layout, observable, window, level_coeffs) for item in means)
    result = np.asarray(samples)
    return {"se": float(result.std(ddof=1)), "first_half_se": float(result[: reps // 2].std(ddof=1)), "second_half_se": float(result[reps // 2 :].std(ddof=1))}


def project_pilot_size(n0: int, standard_errors: Sequence[float], scales: Sequence[float], *, target_fraction: float = 0.01, inflation: float = 1.2, chunk: int = 8192, min_n: int = 1, max_n: int | None = None) -> dict[str, Any]:
    """Project fixed production size from SE alone; never silently cap it."""
    integers = (n0, chunk, min_n) if max_n is None else (n0, chunk, min_n, max_n)
    scalar_values = (target_fraction, inflation)
    if (
        any(isinstance(item, bool) or not isinstance(item, (int, np.integer)) or item < 1 for item in integers)
        or not all(
            not isinstance(item, bool)
            and isinstance(item, (int, float, np.integer, np.floating))
            and math.isfinite(float(item))
            and float(item) > 0
            for item in scalar_values
        )
    ):
        raise ValueError("invalid pilot projection parameters")
    errors, parent_scales = _array(standard_errors, "standard_errors"), _array(scales, "scales")
    if errors.ndim != 1 or errors.size == 0 or errors.shape != parent_scales.shape or np.any(errors < 0) or np.any(parent_scales <= 0):
        raise ValueError("standard errors and positive scales must be matching vectors")
    required = float(inflation) * n0 * float(np.max((errors / (float(target_fraction) * parent_scales)) ** 2))
    if not math.isfinite(required):
        raise ValueError("projection is not finite")
    projected = max(min_n, int(math.ceil(required / chunk) * chunk))
    if max_n is not None and (max_n < min_n or projected > max_n):
        return {"feasible": False, "n": None, "required_n": projected}
    return {"feasible": True, "n": projected, "required_n": projected}
