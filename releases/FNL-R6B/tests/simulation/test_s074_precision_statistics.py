"""Behavioral tests for independent-trajectory S-074 reductions."""

from __future__ import annotations

import numpy as np
import pytest

from phasemap.simulation.precision_statistics import (
    FeatureAccumulator,
    bootstrap_se,
    build_features,
    estimate,
    paired_difference,
    project_pilot_size,
)


def _paths(times: np.ndarray, positions: np.ndarray, velocities: np.ndarray | None = None) -> np.ndarray:
    """Make level/path states from (time, path, coordinate) fixtures."""
    n_times, n_paths, _ = positions.shape
    result = np.zeros((3, n_times, n_paths, 5), dtype=float)
    result[:, :, :, :2] = positions
    if velocities is not None:
        result[:, :, :, 2:4] = velocities
    return result


def _literal_spatial(paths: np.ndarray, times: np.ndarray, mode: str, window: int, levels: tuple[float, float, float]) -> float:
    """Direct whole-array functional used only to validate sufficient features."""
    end = times[-1]
    index = np.flatnonzero(times >= (0.5, 2 / 3, 3 / 4)[window] * end)
    if mode == "localized":
        weights, factor = np.full(index.size, 1.0 / index.size), 1.0
    else:
        centered = times[index] - times[index].mean()
        weights, factor = centered / (centered @ centered), 0.25
    value = 0.0
    for level, coefficient in enumerate(levels):
        points = paths[level, index, :, :2]
        variance = np.sum((points - points.mean(axis=1, keepdims=True)) ** 2, axis=(1, 2)) / (points.shape[1] - 1)
        value += coefficient * factor * (weights @ variance)
    return float(value)


def _literal_specs(paths: np.ndarray, times: np.ndarray, specs: list[dict[str, object]]) -> float:
    return sum(
        float(spec.get("coefficient", 1.0))
        * _literal_spatial(paths, times, "localized", int(spec.get("window", 0)), tuple(spec["level_coeffs"]))
        for spec in specs
    )


def test_spatial_fixture_matches_literal_delete_one_jackknife() -> None:
    # Wrong centering/deletion algebra changes the hand-derived value or SE.
    times = np.array([1.0])
    position = np.array([[[-1.0, 0.0], [0.0, 0.0], [1.0, 0.0]]])
    features, layout = build_features(_paths(times, position), times, "localized")
    stats = FeatureAccumulator().add(features).to_dict()
    result = estimate(stats, layout, "spatial")
    deleted = np.array([0.5, 2.0, 0.5])  # literal recomputed two-path variances
    literal_se = np.sqrt((2.0 / 3.0) * np.sum((deleted - deleted.mean()) ** 2))
    assert result["value"] == pytest.approx(1.0)
    assert result["se"] == pytest.approx(literal_se)


def test_diffusive_fixture_uses_intercept_slope_and_jackknife() -> None:
    # Treating origin regression as an intercept fit changes D=1/4 and its SE.
    times = np.array([1.0, 2.0, 3.0])
    coordinate = np.sqrt(times)[:, None] * np.array([[-1.0, 0.0, 1.0]])
    position = np.stack((coordinate, np.zeros_like(coordinate)), axis=-1)
    features, layout = build_features(_paths(times, position), times, "diffusive")
    result = estimate(FeatureAccumulator().add(features).to_dict(), layout, "spatial")
    assert result["value"] == pytest.approx(0.25)
    assert result["se"] == pytest.approx(0.25)


def test_linear_means_and_streaming_merge_match_whole_paths() -> None:
    times = np.array([1.0])
    position = np.zeros((1, 3, 2))
    velocity = np.array([[[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]])
    features, layout = build_features(_paths(times, position, velocity), times, "localized")
    whole = FeatureAccumulator().add(features).to_dict()
    accumulator = FeatureAccumulator().add(features[:1])
    streamed = accumulator.add(features[1:]).to_dict()
    restored = FeatureAccumulator.from_dict(streamed).to_dict()
    result = estimate(restored, layout, "speed")
    assert whole["n"] == restored["n"]
    assert np.allclose(whole["mean"], restored["mean"])
    assert np.allclose(whole["m2"], restored["m2"])
    assert result["value"] == pytest.approx(14.0 / 3.0)
    assert result["se"] == pytest.approx(7.0 / 3.0)


def test_paired_level_contrast_preserves_common_path_covariance() -> None:
    times = np.array([1.0])
    position = np.zeros((1, 4, 2))
    velocity = np.array([[[1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [4.0, 0.0]]])
    paths = _paths(times, position, velocity)
    paths[1, :, :, 2:4] = paths[0, :, :, 2:4]
    features, layout = build_features(paths, times, "localized")
    stats = FeatureAccumulator().add(features).to_dict()
    result = estimate(stats, layout, "speed", level_coeffs=(1.0, -1.0, 0.0))
    assert result["value"] == pytest.approx(0.0)
    assert result["se"] == pytest.approx(0.0)
    assert paired_difference(stats, layout, [{"observable": "speed", "level_coeffs": (1, -1, 0)}])["se"] == pytest.approx(0.0)


def test_bootstrap_and_pilot_projection_are_explicit() -> None:
    rng = np.random.default_rng(4)
    times = np.array([1.0])
    position = np.zeros((1, 64, 2))
    velocity = np.stack((rng.normal(size=(1, 64)), np.zeros((1, 64))), axis=-1)
    features, layout = build_features(_paths(times, position, velocity), times, "localized")
    outcome = bootstrap_se(features, layout, "speed", reps=400, seed=5)
    analytic = estimate(FeatureAccumulator().add(features).to_dict(), layout, "speed")["se"]
    assert outcome["se"] == pytest.approx(analytic, rel=0.2)
    assert outcome["first_half_se"] > 0 and outcome["second_half_se"] > 0
    assert project_pilot_size(100, [0.2], [1.0], target_fraction=0.1, inflation=1.2, chunk=64, min_n=64, max_n=512)["n"] == 512
    capped = project_pilot_size(100, [5.0], [1.0], target_fraction=0.01, inflation=1.2, chunk=64, min_n=64, max_n=512)
    assert capped["feasible"] is False and capped["n"] is None


def test_invalid_shapes_and_small_spatial_sample_fail_closed() -> None:
    with pytest.raises(ValueError, match="shape"):
        build_features(np.zeros((2, 1, 3, 5)), np.array([1.0]), "localized")
    with pytest.raises(ValueError, match="at least three"):
        build_features(np.zeros((3, 1, 2, 5)), np.array([1.0]), "localized")


def test_random_time_dependent_spatial_jackknife_matches_literal_deletions() -> None:
    # Losing time-dependent ensemble centering changes this direct deletion result.
    rng = np.random.default_rng(72)
    times = np.array([1.0, 2.0, 3.0, 4.0])
    paths = _paths(times, rng.normal(size=(4, 6, 2)))
    features, layout = build_features(paths, times, "localized")
    stats = FeatureAccumulator().add(features).to_dict()
    observed = estimate(stats, layout, "spatial", window=1)
    deleted = np.array([_literal_spatial(np.delete(paths, item, axis=2), times, "localized", 1, (1, 0, 0)) for item in range(6)])
    assert observed["value"] == pytest.approx(_literal_spatial(paths, times, "localized", 1, (1, 0, 0)))
    assert observed["se"] == pytest.approx(np.sqrt(5 / 6 * np.sum((deleted - deleted.mean()) ** 2)))


def test_paired_quadratic_level_window_contrast_matches_literal_deletions() -> None:
    # Independent-error summing loses the common-path covariance in this contrast.
    rng = np.random.default_rng(73)
    times = np.array([1.0, 2.0, 3.0, 4.0])
    paths = _paths(times, rng.normal(size=(4, 7, 2)))
    paths[1, :, :, :2] = paths[0, :, :, :2] + 0.25 * rng.normal(size=(4, 7, 2))
    features, layout = build_features(paths, times, "localized")
    stats = FeatureAccumulator().add(features).to_dict()
    specs: list[dict[str, object]] = [
        {"observable": "spatial", "window": 0, "level_coeffs": (1, -1, 0)},
        {"observable": "spatial", "window": 1, "level_coeffs": (1, 0, -1), "coefficient": -0.35},
    ]
    observed = paired_difference(stats, layout, specs)
    deleted = np.array([_literal_specs(np.delete(paths, item, axis=2), times, specs) for item in range(7)])
    assert observed["value"] == pytest.approx(_literal_specs(paths, times, specs))
    assert observed["se"] == pytest.approx(np.sqrt(6 / 7 * np.sum((deleted - deleted.mean()) ** 2)))


def test_spatial_bootstrap_matches_literal_whole_path_resampling() -> None:
    # Resampling feature rows as independent time points would not match this literal route.
    rng = np.random.default_rng(74)
    times = np.array([1.0, 2.0, 3.0, 4.0])
    paths = _paths(times, rng.normal(size=(4, 5, 2)))
    features, layout = build_features(paths, times, "localized")
    observed = bootstrap_se(features, layout, "spatial", window=0, reps=24, seed=75, batch_size=7)
    bootstrap_rng = np.random.default_rng(75)
    weights = bootstrap_rng.multinomial(5, np.full(5, 0.2), size=24)
    literal = np.array([_literal_spatial(np.repeat(paths, row, axis=2), times, "localized", 0, (1, 0, 0)) for row in weights])
    assert observed["se"] == pytest.approx(literal.std(ddof=1))
    assert observed["first_half_se"] == pytest.approx(literal[:12].std(ddof=1))
    assert observed["second_half_se"] == pytest.approx(literal[12:].std(ddof=1))


def test_malformed_serialized_state_negative_variance_and_projection_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="invalid accumulator"):
        FeatureAccumulator.from_dict({"n": 3, "mean": [np.nan], "m2": [[0.0]]})
    features, layout = build_features(np.zeros((3, 1, 3, 5)), np.array([1.0]), "localized")
    bad_state = FeatureAccumulator().add(features).to_dict()
    bad_state["m2"] = (-np.eye(features.shape[1])).tolist()
    with pytest.raises(ValueError, match="negative estimated variance"):
        estimate(bad_state, layout, "speed")
    bad_state["m2"] = (-1e-20 * np.eye(features.shape[1])).tolist()
    assert estimate(bad_state, layout, "speed")["se"] == 0.0
    with pytest.raises(ValueError, match="projection"):
        project_pilot_size(100, [1.0], [1.0], chunk=1.5)
    with pytest.raises(ValueError, match="projection"):
        project_pilot_size(100, [1.0], [1.0], target_fraction="0.01")
