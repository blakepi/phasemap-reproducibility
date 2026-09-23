"""Independent full-noise exact-clock Euler--Maruyama paths for S-074.

The three returned levels use steps ``step``, ``2 * step`` and ``4 * step``.
They consume the same elementary translational and rotational Wiener
increments.  Coarser accumulators are flushed before every exact reset and at
every requested record time.  The CPU backend is deliberately scalar and is
the deterministic reference for the independent CUDA implementation.

CuPy is imported lazily: CPU qualification remains available on machines
without CUDA.  The CUDA kernel contains its own Philox4x32-10 and Box--Muller
implementation and does not depend on cuRAND headers or fast-math.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any

import numpy as np
import numpy.typing as npt

from phasemap.simulation.protocols import PROTOCOL_REGISTRY, Protocol


FloatArray = npt.NDArray[np.float64]
UInt32Array = npt.NDArray[np.uint32]

_UINT32_MASK = 0xFFFFFFFF
_UINT64_LIMIT = 1 << 64
_INV_2_POW_32 = 2.0**-32
_TWO_PI = 6.283185307179586476925286766559
_SQRT_TWO = 1.414213562373095048801688724210
_BROWNIAN_STREAM = 0x42524F57  # "BROW"
_RESET_STREAM = 0x52534554  # "RSET"
_MAX_SEGMENTS_PER_LAUNCH = 64

_PROTOCOL_INDEX = {protocol: index for index, protocol in enumerate(Protocol)}


def _mulhilo32(a: int, b: int) -> tuple[int, int]:
    product = (a & _UINT32_MASK) * (b & _UINT32_MASK)
    return (product >> 32) & _UINT32_MASK, product & _UINT32_MASK


def _philox4x32_10(
    counter: tuple[int, int, int, int], key: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Return one Random123-compatible Philox4x32-10 block."""

    c0, c1, c2, c3 = (word & _UINT32_MASK for word in counter)
    k0, k1 = (word & _UINT32_MASK for word in key)
    for _ in range(10):
        hi0, lo0 = _mulhilo32(0xD2511F53, c0)
        hi1, lo1 = _mulhilo32(0xCD9E8D57, c2)
        c0, c1, c2, c3 = (
            (hi1 ^ c1 ^ k0) & _UINT32_MASK,
            lo1,
            (hi0 ^ c3 ^ k1) & _UINT32_MASK,
            lo0,
        )
        k0 = (k0 + 0x9E3779B9) & _UINT32_MASK
        k1 = (k1 + 0xBB67AE85) & _UINT32_MASK
    return c0, c1, c2, c3


def _case_key(
    seed: int, M: float, Pe: float, rho: float, protocol: Protocol
) -> tuple[int, int]:
    """Derive a stable stream key unique to a parameter case and protocol."""

    payload = struct.pack(
        "<QdddB", seed, M, Pe, rho, _PROTOCOL_INDEX[protocol]
    )
    digest = hashlib.blake2s(payload, digest_size=8, person=b"PHSM074").digest()
    return struct.unpack("<II", digest)


def _normal_triplet(
    path_index: int,
    draw_index: int,
    key: tuple[int, int],
    stream: int = _BROWNIAN_STREAM,
) -> tuple[float, float, float]:
    """Generate three independent standard normals from one Philox block."""

    if not 0 <= draw_index <= _UINT32_MASK:
        raise RuntimeError("Philox draw counter exhausted")
    words = _philox4x32_10(
        (
            path_index & _UINT32_MASK,
            (path_index >> 32) & _UINT32_MASK,
            draw_index,
            stream,
        ),
        key,
    )
    u0 = (words[0] + 0.5) * _INV_2_POW_32
    u1 = (words[1] + 0.5) * _INV_2_POW_32
    u2 = (words[2] + 0.5) * _INV_2_POW_32
    u3 = (words[3] + 0.5) * _INV_2_POW_32
    radius0 = math.sqrt(-2.0 * math.log(u0))
    radius1 = math.sqrt(-2.0 * math.log(u2))
    angle0 = _TWO_PI * u1
    angle1 = _TWO_PI * u3
    return (
        radius0 * math.cos(angle0),
        radius0 * math.sin(angle0),
        radius1 * math.cos(angle1),
    )


def _reset_wait(
    path_index: int, event_index: int, key: tuple[int, int], rho: float
) -> float:
    if rho == 0.0:
        return math.inf
    if not 0 <= event_index <= _UINT32_MASK:
        raise RuntimeError("Philox reset counter exhausted")
    word = _philox4x32_10(
        (
            path_index & _UINT32_MASK,
            (path_index >> 32) & _UINT32_MASK,
            event_index,
            _RESET_STREAM,
        ),
        key,
    )[0]
    return -math.log((word + 0.5) * _INV_2_POW_32) / rho


def _em_step(
    state: npt.ArrayLike,
    *,
    inertia: float,
    activity: float,
    dt: float,
    dw: npt.ArrayLike,
) -> FloatArray:
    """Apply one EM step using only the pre-step velocity and orientation."""

    old = np.asarray(state, dtype=np.float64)
    noise = np.asarray(dw, dtype=np.float64)
    if old.shape != (5,) or noise.shape != (3,):
        raise ValueError("state and dw must have shapes (5,) and (3,)")
    rx, ry, vx, vy, theta = (float(value) for value in old)
    dwx, dwy, dwtheta = (float(value) for value in noise)
    inverse_mass = 1.0 / inertia
    return np.array(
        [
            rx + vx * dt,
            ry + vy * dt,
            vx + (-(vx - activity * math.cos(theta)) * inverse_mass) * dt
            + (_SQRT_TWO * inverse_mass) * dwx,
            vy + (-(vy - activity * math.sin(theta)) * inverse_mass) * dt
            + (_SQRT_TWO * inverse_mass) * dwy,
            theta + _SQRT_TWO * dwtheta,
        ],
        dtype=np.float64,
    )


def _protocol_mask(protocol: Protocol) -> int:
    reset = PROTOCOL_REGISTRY[protocol]
    return (
        int(reset.resets_position)
        | (int(reset.resets_velocity) << 1)
        | (int(reset.resets_orientation) << 2)
    )


def _apply_reset_inplace(states: FloatArray, mask: int) -> None:
    if mask & 1:
        states[:, 0:2] = 0.0
    if mask & 2:
        states[:, 2:4] = 0.0
    if mask & 4:
        states[:, 4] = 0.0


def _simulate_one_cpu(
    *,
    M: float,
    Pe: float,
    rho: float,
    mask: int,
    path_index: int,
    key: tuple[int, int],
    step: float,
    record_times: FloatArray,
) -> FloatArray:
    states = np.zeros((3, 5), dtype=np.float64)
    accum_dt = np.zeros(2, dtype=np.float64)
    accum_dw = np.zeros((2, 3), dtype=np.float64)
    group_count = np.zeros(2, dtype=np.int64)
    output = np.empty((3, record_times.size, 5), dtype=np.float64)
    time = 0.0
    brownian_count = 0
    reset_count = 0
    next_reset = _reset_wait(path_index, 0, key, rho)

    for record_index, target_value in enumerate(record_times):
        target = float(target_value)
        while time < target:
            nominal_boundary = time + step
            if nominal_boundary <= time:
                raise RuntimeError("step is too small to advance physical time")
            reset_due = next_reset <= nominal_boundary and next_reset <= target
            if reset_due:
                boundary = next_reset
            elif target <= nominal_boundary:
                boundary = target
            else:
                boundary = nominal_boundary
            dt = boundary - time
            if dt <= 0.0:
                raise RuntimeError("nonpositive integration segment encountered")

            normals = _normal_triplet(path_index, brownian_count, key)
            if brownian_count == _UINT32_MASK:
                raise RuntimeError("Philox Brownian counter exhausted")
            brownian_count += 1
            sqrt_dt = math.sqrt(dt)
            dw = np.array(
                [sqrt_dt * normals[0], sqrt_dt * normals[1], sqrt_dt * normals[2]],
                dtype=np.float64,
            )
            states[0] = _em_step(
                states[0], inertia=M, activity=Pe, dt=dt, dw=dw
            )

            record_due = boundary == target
            for accumulator, factor in enumerate((2, 4)):
                accum_dt[accumulator] += dt
                accum_dw[accumulator] += dw
                group_count[accumulator] += 1
                if (
                    group_count[accumulator] == factor
                    or reset_due
                    or record_due
                ):
                    states[accumulator + 1] = _em_step(
                        states[accumulator + 1],
                        inertia=M,
                        activity=Pe,
                        dt=float(accum_dt[accumulator]),
                        dw=accum_dw[accumulator],
                    )
                    accum_dt[accumulator] = 0.0
                    accum_dw[accumulator].fill(0.0)
                    group_count[accumulator] = 0

            time = boundary
            if reset_due:
                _apply_reset_inplace(states, mask)
                if reset_count == _UINT32_MASK:
                    raise RuntimeError("Philox reset counter exhausted")
                reset_count += 1
                next_reset = time + _reset_wait(
                    path_index, reset_count, key, rho
                )
        output[:, record_index, :] = states
    return output


def _validate_inputs(
    M: float,
    Pe: float,
    rho: float,
    protocol: Protocol,
    n: int,
    seed: int,
    path_offset: int,
    end_time: float,
    step: float,
    record_times: npt.ArrayLike,
    backend: str,
) -> tuple[float, float, float, Protocol, int, int, int, float, float, FloatArray, str]:
    M = float(M)
    Pe = float(Pe)
    rho = float(rho)
    end_time = float(end_time)
    step = float(step)
    if not math.isfinite(M) or M <= 0.0:
        raise ValueError("M must be finite and > 0")
    if not math.isfinite(Pe) or Pe < 0.0:
        raise ValueError("Pe must be finite and >= 0")
    if not math.isfinite(rho) or rho < 0.0:
        raise ValueError("rho must be finite and >= 0")
    if not isinstance(protocol, Protocol):
        raise TypeError("protocol must be a Protocol")
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n <= 0:
        raise ValueError("n must be a positive integer")
    if (
        isinstance(seed, bool)
        or not isinstance(seed, (int, np.integer))
        or not 0 <= int(seed) < _UINT64_LIMIT
    ):
        raise ValueError("seed must be an integer in [0, 2**64)")
    if (
        isinstance(path_offset, bool)
        or not isinstance(path_offset, (int, np.integer))
        or path_offset < 0
    ):
        raise ValueError("path_offset must be a nonnegative integer")
    if int(path_offset) + int(n) > _UINT64_LIMIT:
        raise ValueError("path_offset + n must not exceed 2**64")
    if not math.isfinite(end_time) or end_time <= 0.0:
        raise ValueError("end_time must be finite and > 0")
    if not math.isfinite(step) or step <= 0.0:
        raise ValueError("step must be finite and > 0")
    records = np.asarray(record_times, dtype=np.float64)
    if records.ndim != 1 or records.size == 0:
        raise ValueError("record_times must be a nonempty one-dimensional array")
    if not np.all(np.isfinite(records)) or records[0] < 0.0:
        raise ValueError("record_times must be finite and nonnegative")
    if records.size > 1 and np.any(np.diff(records) <= 0.0):
        raise ValueError("record_times must be strictly increasing")
    if float(records[-1]) != end_time:
        raise ValueError("record_times must end exactly at end_time")
    if backend not in {"cpu", "gpu"}:
        raise ValueError("backend must be 'cpu' or 'gpu'")
    return (
        M,
        Pe,
        rho,
        protocol,
        int(n),
        int(seed),
        int(path_offset),
        end_time,
        step,
        records.copy(),
        backend,
    )


def simulate_paths(
    M: float,
    Pe: float,
    rho: float,
    protocol: Protocol,
    *,
    n: int,
    seed: int,
    path_offset: int,
    end_time: float,
    step: float,
    record_times: npt.ArrayLike,
    backend: str = "gpu",
) -> FloatArray:
    """Simulate three coupled exact-clock EM levels.

    Returns:
        A ``float64`` array with shape ``(3, len(record_times), n, 5)``.
        The state axis is ``[r_x, r_y, v_x, v_y, theta]`` and the levels use
        nominal steps ``step``, ``2*step`` and ``4*step`` respectively.
    """

    (
        M,
        Pe,
        rho,
        protocol,
        n,
        seed,
        path_offset,
        _end_time,
        step,
        records,
        backend,
    ) = _validate_inputs(
        M,
        Pe,
        rho,
        protocol,
        n,
        seed,
        path_offset,
        end_time,
        step,
        record_times,
        backend,
    )
    key = _case_key(seed, M, Pe, rho, protocol)
    mask = _protocol_mask(protocol)
    if backend == "gpu":
        return _simulate_gpu(
            M=M,
            Pe=Pe,
            rho=rho,
            mask=mask,
            n=n,
            path_offset=path_offset,
            key=key,
            step=step,
            record_times=records,
        )

    output = np.empty((3, records.size, n, 5), dtype=np.float64)
    for local_path in range(n):
        output[:, :, local_path, :] = _simulate_one_cpu(
            M=M,
            Pe=Pe,
            rho=rho,
            mask=mask,
            path_index=path_offset + local_path,
            key=key,
            step=step,
            record_times=records,
        )
    return output


_CUDA_SOURCE = r"""
typedef unsigned int uint32_t;

#define PHILOX_M0 0xD2511F53U
#define PHILOX_M1 0xCD9E8D57U
#define PHILOX_W0 0x9E3779B9U
#define PHILOX_W1 0xBB67AE85U
#define BROWNIAN_STREAM 0x42524F57U
#define RESET_STREAM 0x52534554U
#define INV_2_POW_32 2.3283064365386962890625e-10
#define TWO_PI 6.283185307179586476925286766559
#define SQRT_TWO 1.414213562373095048801688724210
#define MAX_SEGMENTS 64

__device__ __forceinline__ void philox4x32_10(
    uint32_t &c0, uint32_t &c1, uint32_t &c2, uint32_t &c3,
    uint32_t k0, uint32_t k1
) {
    #pragma unroll
    for (int round = 0; round < 10; ++round) {
        uint32_t hi0 = __umulhi(PHILOX_M0, c0);
        uint32_t lo0 = PHILOX_M0 * c0;
        uint32_t hi1 = __umulhi(PHILOX_M1, c2);
        uint32_t lo1 = PHILOX_M1 * c2;
        uint32_t n0 = hi1 ^ c1 ^ k0;
        uint32_t n1 = lo1;
        uint32_t n2 = hi0 ^ c3 ^ k1;
        uint32_t n3 = lo0;
        c0 = n0; c1 = n1; c2 = n2; c3 = n3;
        k0 += PHILOX_W0;
        k1 += PHILOX_W1;
    }
}

__device__ __forceinline__ double uniform_open(uint32_t word) {
    return ((double)word + 0.5) * INV_2_POW_32;
}

__device__ __forceinline__ void normal_triplet(
    unsigned long long path, uint32_t draw, uint32_t key0, uint32_t key1,
    double &z0, double &z1, double &z2
) {
    uint32_t c0 = (uint32_t)path;
    uint32_t c1 = (uint32_t)(path >> 32);
    uint32_t c2 = draw;
    uint32_t c3 = BROWNIAN_STREAM;
    philox4x32_10(c0, c1, c2, c3, key0, key1);
    double u0 = uniform_open(c0);
    double u1 = uniform_open(c1);
    double u2 = uniform_open(c2);
    double u3 = uniform_open(c3);
    double radius0 = sqrt(-2.0 * log(u0));
    double radius1 = sqrt(-2.0 * log(u2));
    double angle0 = TWO_PI * u1;
    double angle1 = TWO_PI * u3;
    z0 = radius0 * cos(angle0);
    z1 = radius0 * sin(angle0);
    z2 = radius1 * cos(angle1);
}

__device__ __forceinline__ double reset_wait(
    unsigned long long path, uint32_t event, uint32_t key0, uint32_t key1,
    double rho
) {
    uint32_t c0 = (uint32_t)path;
    uint32_t c1 = (uint32_t)(path >> 32);
    uint32_t c2 = event;
    uint32_t c3 = RESET_STREAM;
    philox4x32_10(c0, c1, c2, c3, key0, key1);
    return -log(uniform_open(c0)) / rho;
}

__device__ __forceinline__ void em_step(
    double *state, double M, double Pe, double dt,
    double dwx, double dwy, double dwt
) {
    double rx = state[0];
    double ry = state[1];
    double vx = state[2];
    double vy = state[3];
    double theta = state[4];
    double inverse_mass = 1.0 / M;
    state[0] = rx + vx * dt;
    state[1] = ry + vy * dt;
    state[2] = vx + (-(vx - Pe * cos(theta)) * inverse_mass) * dt
                     + (SQRT_TWO * inverse_mass) * dwx;
    state[3] = vy + (-(vy - Pe * sin(theta)) * inverse_mass) * dt
                     + (SQRT_TWO * inverse_mass) * dwy;
    state[4] = theta + SQRT_TWO * dwt;
}

__device__ __forceinline__ void apply_reset(double state[3][5], int mask) {
    #pragma unroll
    for (int level = 0; level < 3; ++level) {
        if (mask & 1) { state[level][0] = 0.0; state[level][1] = 0.0; }
        if (mask & 2) { state[level][2] = 0.0; state[level][3] = 0.0; }
        if (mask & 4) { state[level][4] = 0.0; }
    }
}

extern "C" __global__ void philox_kat(
    const uint32_t *counters, const uint32_t *keys, uint32_t *output, int n
) {
    int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i >= n) return;
    uint32_t c0 = counters[4*i];
    uint32_t c1 = counters[4*i+1];
    uint32_t c2 = counters[4*i+2];
    uint32_t c3 = counters[4*i+3];
    philox4x32_10(c0, c1, c2, c3, keys[2*i], keys[2*i+1]);
    output[4*i] = c0; output[4*i+1] = c1;
    output[4*i+2] = c2; output[4*i+3] = c3;
}

extern "C" __global__ void initialize_paths(
    double *next_reset, double rho, unsigned long long path_offset,
    uint32_t key0, uint32_t key1, int n
) {
    int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i >= n) return;
    unsigned long long path = path_offset + (unsigned long long)i;
    next_reset[i] = rho == 0.0
        ? (1.0 / 0.0) : reset_wait(path, 0U, key0, key1, rho);
}

extern "C" __global__ void advance_paths(
    double *states_global, double *times, double *next_resets,
    uint32_t *brownian_counts, uint32_t *reset_counts,
    double *accum_dt_global, double *accum_dw_global, int *group_global,
    int *status, double target, double step, double M, double Pe, double rho,
    unsigned long long path_offset, uint32_t key0, uint32_t key1,
    int reset_mask, int n
) {
    int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i >= n) return;

    double state[3][5];
    #pragma unroll
    for (int level = 0; level < 3; ++level) {
        #pragma unroll
        for (int component = 0; component < 5; ++component) {
            state[level][component] = states_global[(level*n+i)*5+component];
        }
    }
    double accum_dt[2];
    double accum_dw[2][3];
    int group[2];
    #pragma unroll
    for (int accumulator = 0; accumulator < 2; ++accumulator) {
        accum_dt[accumulator] = accum_dt_global[accumulator*n+i];
        group[accumulator] = group_global[accumulator*n+i];
        #pragma unroll
        for (int component = 0; component < 3; ++component) {
            accum_dw[accumulator][component] =
                accum_dw_global[(accumulator*n+i)*3+component];
        }
    }
    double time = times[i];
    double next_reset = next_resets[i];
    uint32_t brownian_count = brownian_counts[i];
    uint32_t reset_count = reset_counts[i];
    unsigned long long path = path_offset + (unsigned long long)i;
    int local_status = 1;

    for (int segment = 0; segment < MAX_SEGMENTS; ++segment) {
        if (time >= target) { local_status = 0; break; }
        double nominal_boundary = time + step;
        if (nominal_boundary <= time) { local_status = -1; break; }
        bool reset_due = next_reset <= nominal_boundary && next_reset <= target;
        double boundary = reset_due ? next_reset
            : (target <= nominal_boundary ? target : nominal_boundary);
        double dt = boundary - time;
        if (dt <= 0.0) { local_status = -2; break; }

        double z0, z1, z2;
        normal_triplet(path, brownian_count, key0, key1, z0, z1, z2);
        if (brownian_count == 0xffffffffU) { local_status = -3; break; }
        brownian_count += 1U;
        double sqrt_dt = sqrt(dt);
        double dwx = sqrt_dt * z0;
        double dwy = sqrt_dt * z1;
        double dwt = sqrt_dt * z2;
        em_step(state[0], M, Pe, dt, dwx, dwy, dwt);

        bool record_due = boundary == target;
        #pragma unroll
        for (int accumulator = 0; accumulator < 2; ++accumulator) {
            int factor = accumulator == 0 ? 2 : 4;
            accum_dt[accumulator] += dt;
            accum_dw[accumulator][0] += dwx;
            accum_dw[accumulator][1] += dwy;
            accum_dw[accumulator][2] += dwt;
            group[accumulator] += 1;
            if (group[accumulator] == factor || reset_due || record_due) {
                em_step(
                    state[accumulator+1], M, Pe, accum_dt[accumulator],
                    accum_dw[accumulator][0], accum_dw[accumulator][1],
                    accum_dw[accumulator][2]
                );
                accum_dt[accumulator] = 0.0;
                accum_dw[accumulator][0] = 0.0;
                accum_dw[accumulator][1] = 0.0;
                accum_dw[accumulator][2] = 0.0;
                group[accumulator] = 0;
            }
        }

        time = boundary;
        if (reset_due) {
            apply_reset(state, reset_mask);
            if (reset_count == 0xffffffffU) { local_status = -4; break; }
            reset_count += 1U;
            next_reset = time + reset_wait(path, reset_count, key0, key1, rho);
        }
        if (time >= target) { local_status = 0; break; }
    }

    #pragma unroll
    for (int level = 0; level < 3; ++level) {
        #pragma unroll
        for (int component = 0; component < 5; ++component) {
            states_global[(level*n+i)*5+component] = state[level][component];
        }
    }
    #pragma unroll
    for (int accumulator = 0; accumulator < 2; ++accumulator) {
        accum_dt_global[accumulator*n+i] = accum_dt[accumulator];
        group_global[accumulator*n+i] = group[accumulator];
        #pragma unroll
        for (int component = 0; component < 3; ++component) {
            accum_dw_global[(accumulator*n+i)*3+component] =
                accum_dw[accumulator][component];
        }
    }
    times[i] = time;
    next_resets[i] = next_reset;
    brownian_counts[i] = brownian_count;
    reset_counts[i] = reset_count;
    status[i] = local_status;
}
"""


_RAW_MODULE: Any | None = None


def _cupy() -> Any:
    try:
        import cupy as cp
    except Exception as exc:  # pragma: no cover - exercised on CPU-only hosts
        raise RuntimeError("backend='gpu' requires CuPy with a working CUDA device") from exc
    try:
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("no CUDA devices were detected")
    except Exception as exc:
        raise RuntimeError("backend='gpu' requires a working CUDA device") from exc
    return cp


def _raw_module(cp: Any) -> Any:
    global _RAW_MODULE
    if _RAW_MODULE is None:
        _RAW_MODULE = cp.RawModule(
            code=_CUDA_SOURCE,
            options=("--std=c++11", "--fmad=false"),
            name_expressions=("philox_kat", "initialize_paths", "advance_paths"),
        )
    return _RAW_MODULE


def _gpu_philox4x32_10(counters: npt.ArrayLike, keys: npt.ArrayLike) -> UInt32Array:
    """Run Philox blocks through the CUDA implementation for qualification."""

    counter_array = np.asarray(counters, dtype=np.uint32)
    key_array = np.asarray(keys, dtype=np.uint32)
    if counter_array.ndim != 2 or counter_array.shape[1] != 4:
        raise ValueError("counters must have shape (n, 4)")
    if key_array.shape != (counter_array.shape[0], 2):
        raise ValueError("keys must have shape (n, 2)")
    cp = _cupy()
    module = _raw_module(cp)
    kernel = module.get_function("philox_kat")
    d_counters = cp.asarray(np.ascontiguousarray(counter_array))
    d_keys = cp.asarray(np.ascontiguousarray(key_array))
    d_output = cp.empty_like(d_counters)
    threads = 128
    blocks = (counter_array.shape[0] + threads - 1) // threads
    kernel(
        (blocks,),
        (threads,),
        (d_counters, d_keys, d_output, np.int32(counter_array.shape[0])),
    )
    return cp.asnumpy(d_output)


def _simulate_gpu(
    *,
    M: float,
    Pe: float,
    rho: float,
    mask: int,
    n: int,
    path_offset: int,
    key: tuple[int, int],
    step: float,
    record_times: FloatArray,
) -> FloatArray:
    cp = _cupy()
    module = _raw_module(cp)
    initialize = module.get_function("initialize_paths")
    advance = module.get_function("advance_paths")
    states = cp.zeros((3, n, 5), dtype=cp.float64)
    times = cp.zeros(n, dtype=cp.float64)
    next_resets = cp.empty(n, dtype=cp.float64)
    brownian_counts = cp.zeros(n, dtype=cp.uint32)
    reset_counts = cp.zeros(n, dtype=cp.uint32)
    accum_dt = cp.zeros((2, n), dtype=cp.float64)
    accum_dw = cp.zeros((2, n, 3), dtype=cp.float64)
    group_count = cp.zeros((2, n), dtype=cp.int32)
    status = cp.zeros(n, dtype=cp.int32)
    output = cp.empty((3, record_times.size, n, 5), dtype=cp.float64)
    threads = 128
    blocks = (n + threads - 1) // threads
    initialize(
        (blocks,),
        (threads,),
        (
            next_resets,
            np.float64(rho),
            np.uint64(path_offset),
            np.uint32(key[0]),
            np.uint32(key[1]),
            np.int32(n),
        ),
    )

    for record_index, target in enumerate(record_times):
        while True:
            advance(
                (blocks,),
                (threads,),
                (
                    states,
                    times,
                    next_resets,
                    brownian_counts,
                    reset_counts,
                    accum_dt,
                    accum_dw,
                    group_count,
                    status,
                    np.float64(target),
                    np.float64(step),
                    np.float64(M),
                    np.float64(Pe),
                    np.float64(rho),
                    np.uint64(path_offset),
                    np.uint32(key[0]),
                    np.uint32(key[1]),
                    np.int32(mask),
                    np.int32(n),
                ),
            )
            minimum = int(cp.min(status).item())
            if minimum < 0:
                messages = {
                    -1: "step is too small to advance physical time",
                    -2: "nonpositive integration segment encountered",
                    -3: "Philox Brownian counter exhausted",
                    -4: "Philox reset counter exhausted",
                }
                raise RuntimeError(messages.get(minimum, "CUDA trajectory kernel failed"))
            if int(cp.max(status).item()) == 0:
                break
        output[:, record_index, :, :] = states
    return cp.asnumpy(output)


__all__ = ["simulate_paths"]
