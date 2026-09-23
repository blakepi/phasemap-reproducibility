import numpy as np
import pytest

from phasemap.common.model import ModelParams, State
from phasemap.simulation.integrator import SimulationConfig, simulate
from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol, apply_reset


def test_no_reset_trajectory_is_seed_reproducible() -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=0.0)
    cfg = SimulationConfig(end_time=0.25, max_step=0.01, seed=42)
    a = simulate(params, Protocol.P, cfg)
    b = simulate(params, Protocol.P, cfg)
    np.testing.assert_allclose(a.times, b.times)
    np.testing.assert_allclose(a.positions, b.positions)
    np.testing.assert_allclose(a.velocities, b.velocities)
    np.testing.assert_allclose(a.orientations, b.orientations)
    assert a.reset_times.size == 0


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_all_protocols_share_the_seeded_simulator_api(protocol: Protocol) -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=8.0)
    cfg = SimulationConfig(end_time=0.25, max_step=0.01, seed=42)

    a = simulate(params, protocol, cfg)
    b = simulate(params, protocol, cfg)

    np.testing.assert_array_equal(a.times, b.times)
    np.testing.assert_array_equal(a.positions, b.positions)
    np.testing.assert_array_equal(a.velocities, b.velocities)
    np.testing.assert_array_equal(a.orientations, b.orientations)
    np.testing.assert_array_equal(a.reset_times, b.reset_times)


def test_exact_clock_splits_and_applies_position_reset() -> None:
    params = ModelParams(inertia=1.0, activity=0.0, reset_rate=20.0)
    cfg = SimulationConfig(end_time=0.5, max_step=0.2, seed=7)
    initial = State(np.array([2.0, -1.0]), np.array([1.0, 0.0]), 0.4)
    tr = simulate(params, Protocol.P, cfg, initial)
    assert tr.reset_times.size > 0
    for reset_time in tr.reset_times:
        indices = np.flatnonzero(np.isclose(tr.times, reset_time, rtol=0.0, atol=1e-14))
        assert indices.size >= 2
        np.testing.assert_allclose(tr.positions[indices[-1]], [0.0, 0.0])


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_reset_records_pre_and_post_state_at_the_same_time(protocol: Protocol) -> None:
    params = ModelParams(inertia=1.0, activity=0.3, reset_rate=20.0)
    cfg = SimulationConfig(end_time=0.5, max_step=0.2, seed=7)
    initial = State(np.array([2.0, -1.0]), np.array([1.0, -0.5]), 0.4)

    tr = simulate(params, protocol, cfg, initial)
    assert tr.reset_times.size > 0
    for reset_time in tr.reset_times:
        indices = np.flatnonzero(
            np.isclose(tr.times, reset_time, rtol=0.0, atol=1e-14)
        )
        assert indices.size == 2

        pre = State(
            tr.positions[indices[0]],
            tr.velocities[indices[0]],
            tr.orientations[indices[0]],
        )
        expected_post = apply_reset(pre, protocol)
        post = State(
            tr.positions[indices[1]],
            tr.velocities[indices[1]],
            tr.orientations[indices[1]],
        )

        np.testing.assert_allclose(
            post.position, expected_post.position, rtol=0.0, atol=1e-12
        )
        np.testing.assert_allclose(
            post.velocity, expected_post.velocity, rtol=0.0, atol=1e-12
        )
        assert post.orientation == pytest.approx(expected_post.orientation, abs=1e-12)
