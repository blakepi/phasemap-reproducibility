from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from phasemap.simulation.protocols import ALL_PROTOCOLS, PROTOCOL_REGISTRY, Protocol


def _gpu_available() -> bool:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="CUDA path could not be detected", category=UserWarning
            )
            import cupy as cp

        return cp.cuda.runtime.getDeviceCount() > 0
    except Exception:
        return False


GPU_AVAILABLE = _gpu_available()


def test_philox4x32_10_matches_random123_known_answer_vectors() -> None:
    from phasemap.simulation.gpu_trajectories import _philox4x32_10

    assert _philox4x32_10((0, 0, 0, 0), (0, 0)) == (
        0x6627E8D5,
        0xE169C58D,
        0xBC57AC4C,
        0x9B00DBD8,
    )
    assert _philox4x32_10(
        (0xFFFFFFFF,) * 4, (0xFFFFFFFF,) * 2
    ) == (
        0x408F276D,
        0x41C83B0E,
        0xA20BC7C6,
        0x6D5451FD,
    )


@pytest.mark.skipif(not GPU_AVAILABLE, reason="CUDA device with CuPy is required")
def test_gpu_philox_matches_the_same_known_answer_vectors() -> None:
    from phasemap.simulation.gpu_trajectories import _gpu_philox4x32_10

    counters = np.array([[0, 0, 0, 0], [0xFFFFFFFF] * 4], dtype=np.uint32)
    keys = np.array([[0, 0], [0xFFFFFFFF] * 2], dtype=np.uint32)
    got = _gpu_philox4x32_10(counters, keys)
    want = np.array(
        [
            [0x6627E8D5, 0xE169C58D, 0xBC57AC4C, 0x9B00DBD8],
            [0x408F276D, 0x41C83B0E, 0xA20BC7C6, 0x6D5451FD],
        ],
        dtype=np.uint32,
    )
    np.testing.assert_array_equal(got, want)


def test_em_step_uses_old_velocity_and_old_orientation() -> None:
    from phasemap.simulation.gpu_trajectories import _em_step

    state = np.array([1.0, -2.0, 0.5, -0.25, math.pi / 2.0])
    got = _em_step(
        state,
        inertia=2.0,
        activity=3.0,
        dt=0.1,
        dw=np.array([0.2, -0.3, 0.4]),
    )
    want = np.array(
        [
            1.05,
            -2.025,
            0.5 - 0.025 + math.sqrt(2.0) * 0.1,
            -0.25 + 0.1625 - math.sqrt(2.0) * 0.15,
            math.pi / 2.0 + math.sqrt(2.0) * 0.4,
        ]
    )
    np.testing.assert_allclose(got, want, rtol=0.0, atol=2e-15)


@pytest.mark.parametrize(
    ("keyword", "value", "match"),
    [
        ("M", 0.0, "M must be finite and > 0"),
        ("Pe", -1.0, "Pe must be finite and >= 0"),
        ("rho", -1.0, "rho must be finite and >= 0"),
        ("n", 0, "n must be a positive integer"),
        ("seed", -1, "seed must be an integer in"),
        ("path_offset", -1, "path_offset must be a nonnegative integer"),
        ("end_time", 0.0, "end_time must be finite and > 0"),
        ("step", 0.0, "step must be finite and > 0"),
        ("backend", "bogus", "backend must be 'cpu' or 'gpu'"),
    ],
)
def test_invalid_scalar_inputs_fail_closed(
    keyword: str, value: object, match: str
) -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    kwargs: dict[str, object] = {
        "M": 1.0,
        "Pe": 1.0,
        "rho": 1.0,
        "protocol": Protocol.P,
        "n": 2,
        "seed": 3,
        "path_offset": 0,
        "end_time": 0.2,
        "step": 0.01,
        "record_times": [0.0, 0.2],
        "backend": "cpu",
    }
    kwargs[keyword] = value
    with pytest.raises((TypeError, ValueError), match=match):
        simulate_paths(**kwargs)


@pytest.mark.parametrize(
    "record_times",
    [[], [[0.0, 0.2]], [0.0, math.nan, 0.2], [-0.1, 0.2], [0.0, 0.1, 0.1, 0.2], [0.0, 0.1]],
)
def test_invalid_record_grids_fail_closed(record_times: object) -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    with pytest.raises(ValueError, match="record_times"):
        simulate_paths(
            1.0,
            1.0,
            1.0,
            Protocol.P,
            n=2,
            seed=3,
            path_offset=0,
            end_time=0.2,
            step=0.01,
            record_times=record_times,
            backend="cpu",
        )


def test_cpu_paths_are_reproducible_and_path_offset_batch_invariant() -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    kwargs = dict(
        M=0.8,
        Pe=1.4,
        rho=3.0,
        protocol=Protocol.P_THETA,
        seed=0x123456789ABCDEF0,
        end_time=0.19,
        step=0.017,
        record_times=[0.0, 0.07, 0.19],
        backend="cpu",
    )
    whole = simulate_paths(n=5, path_offset=11, **kwargs)
    repeated = simulate_paths(n=5, path_offset=11, **kwargs)
    batched = np.concatenate(
        [
            simulate_paths(n=2, path_offset=11, **kwargs),
            simulate_paths(n=3, path_offset=13, **kwargs),
        ],
        axis=2,
    )
    assert whole.shape == (3, 3, 5, 5)
    assert whole.dtype == np.float64
    np.testing.assert_array_equal(whole, repeated)
    np.testing.assert_array_equal(whole, batched)
    np.testing.assert_array_equal(whole[:, 0], 0.0)


def test_parameter_cases_and_protocols_have_distinct_random_streams() -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    common = dict(
        M=0.9,
        Pe=1.1,
        rho=0.0,
        n=2,
        seed=99,
        path_offset=0,
        end_time=0.04,
        step=0.04,
        record_times=[0.04],
        backend="cpu",
    )
    p = simulate_paths(protocol=Protocol.P, **common)
    v = simulate_paths(protocol=Protocol.V, **common)
    changed_case = simulate_paths(protocol=Protocol.P, **(common | {"Pe": 1.2}))
    assert not np.array_equal(p, v)
    assert not np.array_equal(p, changed_case)


def _first_reset_time(
    M: float, Pe: float, rho: float, protocol: Protocol, seed: int
) -> float:
    from phasemap.simulation.gpu_trajectories import (
        _RESET_STREAM,
        _case_key,
        _philox4x32_10,
    )

    key = _case_key(seed, M, Pe, rho, protocol)
    word = _philox4x32_10((0, 0, 0, _RESET_STREAM), key)[0]
    uniform = (word + 0.5) * (2.0**-32)
    return -math.log(uniform) / rho


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_exact_first_reset_is_applied_before_a_coincident_record(
    protocol: Protocol,
) -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    M, Pe, rho, seed = 0.8, 1.2, 8.0, 0
    reset_time = _first_reset_time(M, Pe, rho, protocol, seed)
    got = simulate_paths(
        M,
        Pe,
        rho,
        protocol,
        n=1,
        seed=seed,
        path_offset=0,
        end_time=reset_time,
        step=1.0,
        record_times=[reset_time],
        backend="cpu",
    )
    reset_map = PROTOCOL_REGISTRY[protocol]
    for level in range(3):
        state = got[level, 0, 0]
        if reset_map.resets_position:
            np.testing.assert_array_equal(state[0:2], 0.0)
        if reset_map.resets_velocity:
            np.testing.assert_array_equal(state[2:4], 0.0)
        if reset_map.resets_orientation:
            assert state[4] == 0.0
    np.testing.assert_allclose(got[0], got[1], rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(got[0], got[2], rtol=0.0, atol=1e-15)


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_reset_maps_preserve_every_unlisted_component(protocol: Protocol) -> None:
    from phasemap.simulation.gpu_trajectories import (
        _apply_reset_inplace,
        _protocol_mask,
    )

    states = np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [6.0, 7.0, 8.0, 9.0, 10.0],
            [11.0, 12.0, 13.0, 14.0, 15.0],
        ]
    )
    before = states.copy()
    _apply_reset_inplace(states, _protocol_mask(protocol))
    reset_map = PROTOCOL_REGISTRY[protocol]
    expected = before.copy()
    if reset_map.resets_position:
        expected[:, 0:2] = 0.0
    if reset_map.resets_velocity:
        expected[:, 2:4] = 0.0
    if reset_map.resets_orientation:
        expected[:, 4] = 0.0
    np.testing.assert_array_equal(states, expected)


def test_rho_zero_has_no_resets_and_record_flushes_all_levels() -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    got = simulate_paths(
        1.3,
        0.7,
        0.0,
        Protocol.PV_THETA,
        n=4,
        seed=7,
        path_offset=2,
        end_time=0.013,
        step=0.02,
        record_times=[0.013],
        backend="cpu",
    )
    assert np.all(np.isfinite(got))
    np.testing.assert_array_equal(got[0], got[1])
    np.testing.assert_array_equal(got[0], got[2])
    assert np.any(got != 0.0)


def test_counter_random_laws_have_expected_engineering_statistics() -> None:
    from phasemap.simulation.gpu_trajectories import (
        _BROWNIAN_STREAM,
        _RESET_STREAM,
        _normal_triplet,
        _philox4x32_10,
    )

    key = (0x13579BDF, 0x2468ACE0)
    count = 30_000
    normals = np.empty((count, 3), dtype=np.float64)
    waits = np.empty(count, dtype=np.float64)
    rho = 2.5
    for index in range(count):
        normals[index] = _normal_triplet(17, index, key, _BROWNIAN_STREAM)
        word = _philox4x32_10((17, 0, index, _RESET_STREAM), key)[0]
        waits[index] = -math.log((word + 0.5) * (2.0**-32)) / rho

    assert np.max(np.abs(normals.mean(axis=0))) < 0.025
    assert np.max(np.abs(normals.var(axis=0) - 1.0)) < 0.04
    correlations = np.corrcoef(normals, rowvar=False)
    assert np.max(np.abs(correlations - np.eye(3))) < 0.025
    assert abs(waits.mean() - 1.0 / rho) < 0.008


@pytest.mark.skipif(not GPU_AVAILABLE, reason="CUDA device with CuPy is required")
@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_gpu_matches_independent_scalar_cpu_paths(protocol: Protocol) -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    kwargs = dict(
        M=0.73,
        Pe=1.31,
        rho=18.0,
        protocol=protocol,
        n=4,
        seed=0xCAFEBABE,
        path_offset=21,
        end_time=0.23,
        step=0.017,
        record_times=[0.0, 0.031, 0.11, 0.23],
    )
    cpu = simulate_paths(**kwargs, backend="cpu")
    gpu = simulate_paths(**kwargs, backend="gpu")
    np.testing.assert_allclose(gpu, cpu, rtol=2e-13, atol=2e-13)


@pytest.mark.skipif(not GPU_AVAILABLE, reason="CUDA device with CuPy is required")
def test_gpu_path_offset_batches_are_identical_to_one_launch() -> None:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    kwargs = dict(
        M=1.1,
        Pe=0.8,
        rho=4.0,
        protocol=Protocol.V_THETA,
        seed=888,
        end_time=0.2,
        step=0.01,
        record_times=[0.05, 0.2],
        backend="gpu",
    )
    whole = simulate_paths(n=7, path_offset=100, **kwargs)
    chunks = np.concatenate(
        [
            simulate_paths(n=3, path_offset=100, **kwargs),
            simulate_paths(n=4, path_offset=103, **kwargs),
        ],
        axis=2,
    )
    np.testing.assert_array_equal(whole, chunks)
