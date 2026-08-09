"""Independent 28-state Ito/jump operator for the frozen S-021 plan.

This module is deliberately numerical and self-contained.  It uses only
``mpmath`` plus the Python standard library, performs no file access, and does
not import the PHASEMAP package or a symbolic-algebra implementation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

import mpmath as mp


BASIS_NAMES: tuple[str, ...] = (
    "one",
    "r_x",
    "r_y",
    "v_x",
    "v_y",
    "u_x",
    "u_y",
    "rr_xx",
    "rr_xy",
    "rr_yy",
    "vv_xx",
    "vv_xy",
    "vv_yy",
    "rv_xx",
    "rv_xy",
    "rv_yx",
    "rv_yy",
    "ru_xx",
    "ru_xy",
    "ru_yx",
    "ru_yy",
    "vu_xx",
    "vu_xy",
    "vu_yx",
    "vu_yy",
    "uu_xx",
    "uu_xy",
    "uu_yy",
)
"""Exact basis order locked by the S-021 preregistration."""

INDEX: Mapping[str, int] = MappingProxyType(
    {name: index for index, name in enumerate(BASIS_NAMES)}
)

PROTOCOL_FLAGS: Mapping[str, tuple[int, int, int]] = MappingProxyType(
    {
        "P": (1, 0, 0),
        "V": (0, 1, 0),
        "Theta": (0, 0, 1),
        "PV": (1, 1, 0),
        "PTheta": (1, 0, 1),
        "VTheta": (0, 1, 1),
        "PVTheta": (1, 1, 1),
    }
)
POSITION_PROTOCOLS: tuple[str, ...] = ("P", "PV", "PTheta", "PVTheta")
TRANSPORT_PROTOCOLS: tuple[str, ...] = ("V", "Theta", "VTheta")

R_INDICES: tuple[int, ...] = (7, 8, 9)
S_INDICES: tuple[int, ...] = (10, 11, 12)
C_INDICES: tuple[int, ...] = (13, 14, 15, 16)
Q_INDICES: tuple[int, ...] = (17, 18, 19, 20)
W_INDICES: tuple[int, ...] = (21, 22, 23, 24)
U_INDICES: tuple[int, ...] = (25, 26, 27)
INTERNAL_INDICES: tuple[int, ...] = (
    0,
    3,
    4,
    5,
    6,
    10,
    11,
    12,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
)
INTERNAL_NONCONSTANT_INDICES: tuple[int, ...] = INTERNAL_INDICES[1:]
FIRST_MOMENT_INTERNAL_INDICES: tuple[int, ...] = (3, 4, 5, 6)
SYMMETRY_ZERO_NAMES: tuple[str, ...] = (
    "r_y",
    "v_y",
    "u_y",
    "rr_xy",
    "vv_xy",
    "rv_xy",
    "rv_yx",
    "ru_xy",
    "ru_yx",
    "vu_xy",
    "vu_yx",
    "uu_xy",
)

FORMULA_FIELDS: tuple[str, ...] = (
    "r_bar",
    "v_bar",
    "u_bar",
    "R",
    "S",
    "C",
    "Q",
    "W",
    "U",
    "Cov_r",
    "D",
    "b",
    "C_centered",
    "Q_centered",
    "Sigma_v",
    "Sigma_u",
    "K",
    "raw_rr_quadratic",
    "raw_rr_linear",
    "raw_ru_linear",
    "raw_rv_linear",
    "D_eff",
    "raw_MSD",
    "speed",
    "r_dot_v",
    "centered_variance",
)

_RATIONAL_PATTERN = re.compile(r"[+-]?\d+(?:/[+-]?\d+)?\Z")


def parse_rational(value: str) -> mp.mpf:
    """Parse a decimal-free integer or rational in the active mp context."""

    if not isinstance(value, str) or _RATIONAL_PATTERN.fullmatch(value) is None:
        raise ValueError(f"not an exact decimal-free rational: {value!r}")
    if "/" in value:
        numerator_text, denominator_text = value.split("/", 1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)
        if denominator == 0:
            raise ZeroDivisionError("rational denominator is zero")
        return mp.mpf(numerator) / mp.mpf(denominator)
    return mp.mpf(int(value))


def _exact_number(value: Any, label: str) -> mp.mpf:
    if isinstance(value, str):
        result = parse_rational(value)
    elif isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{label} must not use binary floating point")
    elif isinstance(value, int):
        result = mp.mpf(value)
    elif isinstance(value, mp.mpf):
        result = value
    else:
        raise TypeError(f"{label} must be an exact rational string or mpf")
    if not mp.isfinite(result):
        raise ValueError(f"{label} is nonfinite")
    return result


def _sparse_terms(*pairs: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    return tuple((column, coefficient) for column, coefficient in pairs if coefficient)


def _reset_image_terms(
    position_reset: int,
    velocity_reset: int,
    orientation_reset: int,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """List the pullback image of every one of the 28 basis functions."""

    p = position_reset
    v = velocity_reset
    h = orientation_reset
    kp = 1 - p
    kv = 1 - v
    kh = 1 - h
    return (
        _sparse_terms((0, 1)),  # one
        _sparse_terms((1, kp)),  # r_x
        _sparse_terms((2, kp)),  # r_y
        _sparse_terms((3, kv)),  # v_x
        _sparse_terms((4, kv)),  # v_y
        _sparse_terms((5, kh), (0, h)),  # u_x
        _sparse_terms((6, kh)),  # u_y
        _sparse_terms((7, kp)),  # rr_xx
        _sparse_terms((8, kp)),  # rr_xy
        _sparse_terms((9, kp)),  # rr_yy
        _sparse_terms((10, kv)),  # vv_xx
        _sparse_terms((11, kv)),  # vv_xy
        _sparse_terms((12, kv)),  # vv_yy
        _sparse_terms((13, kp * kv)),  # rv_xx
        _sparse_terms((14, kp * kv)),  # rv_xy
        _sparse_terms((15, kp * kv)),  # rv_yx
        _sparse_terms((16, kp * kv)),  # rv_yy
        _sparse_terms((17, kp * kh), (1, kp * h)),  # ru_xx
        _sparse_terms((18, kp * kh)),  # ru_xy
        _sparse_terms((19, kp * kh), (2, kp * h)),  # ru_yx
        _sparse_terms((20, kp * kh)),  # ru_yy
        _sparse_terms((21, kv * kh), (3, kv * h)),  # vu_xx
        _sparse_terms((22, kv * kh)),  # vu_xy
        _sparse_terms((23, kv * kh), (4, kv * h)),  # vu_yx
        _sparse_terms((24, kv * kh)),  # vu_yy
        _sparse_terms((25, kh), (0, h)),  # uu_xx
        _sparse_terms((26, kh)),  # uu_xy
        _sparse_terms((27, kh)),  # uu_yy
    )


RESET_IMAGE_TERMS: Mapping[
    str, tuple[tuple[tuple[int, int], ...], ...]
] = MappingProxyType(
    {
        protocol: _reset_image_terms(*flags)
        for protocol, flags in PROTOCOL_FLAGS.items()
    }
)


def reset_pullback(protocol: str) -> mp.matrix:
    """Return the explicitly enumerated 28-by-28 reset pullback matrix."""

    try:
        images = RESET_IMAGE_TERMS[protocol]
    except KeyError as exc:
        raise ValueError(f"unknown reset protocol: {protocol!r}") from exc
    matrix = mp.zeros(len(BASIS_NAMES), len(BASIS_NAMES))
    for row, terms in enumerate(images):
        for column, coefficient in terms:
            matrix[row, column] = coefficient
    return matrix


def build_ito_operator(inertia: Any, activity: Any) -> mp.matrix:
    """Hand-code the locked between-reset Ito stencil."""

    M = _exact_number(inertia, "inertia")
    Pe = _exact_number(activity, "activity")
    if M <= 0:
        raise ValueError("inertia must be positive")
    if Pe < 0:
        raise ValueError("activity must be nonnegative")

    A = mp.zeros(28, 28)
    inverse_M = 1 / M

    A[1, 3] = 1
    A[2, 4] = 1

    A[3, 3] = -inverse_M
    A[3, 5] = Pe * inverse_M
    A[4, 4] = -inverse_M
    A[4, 6] = Pe * inverse_M

    A[5, 5] = -1
    A[6, 6] = -1

    A[7, 13] = 2
    A[8, 14] = 1
    A[8, 15] = 1
    A[9, 16] = 2

    A[10, 0] = 2 * inverse_M**2
    A[10, 10] = -2 * inverse_M
    A[10, 21] = 2 * Pe * inverse_M
    A[11, 11] = -2 * inverse_M
    A[11, 22] = Pe * inverse_M
    A[11, 23] = Pe * inverse_M
    A[12, 0] = 2 * inverse_M**2
    A[12, 12] = -2 * inverse_M
    A[12, 24] = 2 * Pe * inverse_M

    A[13, 10] = 1
    A[13, 13] = -inverse_M
    A[13, 17] = Pe * inverse_M
    A[14, 11] = 1
    A[14, 14] = -inverse_M
    A[14, 18] = Pe * inverse_M
    A[15, 11] = 1
    A[15, 15] = -inverse_M
    A[15, 19] = Pe * inverse_M
    A[16, 12] = 1
    A[16, 16] = -inverse_M
    A[16, 20] = Pe * inverse_M

    A[17, 17] = -1
    A[17, 21] = 1
    A[18, 18] = -1
    A[18, 22] = 1
    A[19, 19] = -1
    A[19, 23] = 1
    A[20, 20] = -1
    A[20, 24] = 1

    velocity_orientation_decay = -(1 + inverse_M)
    A[21, 21] = velocity_orientation_decay
    A[21, 25] = Pe * inverse_M
    A[22, 22] = velocity_orientation_decay
    A[22, 26] = Pe * inverse_M
    A[23, 23] = velocity_orientation_decay
    A[23, 26] = Pe * inverse_M
    A[24, 24] = velocity_orientation_decay
    A[24, 27] = Pe * inverse_M

    A[25, 0] = 2
    A[25, 25] = -4
    A[26, 26] = -4
    A[27, 0] = 2
    A[27, 27] = -4
    assert_finite_matrix(A, "Ito operator")
    return A


def build_operator(
    protocol: str,
    inertia: Any,
    activity: Any,
    reset_rate: Any,
) -> mp.matrix:
    """Return ``A0 + rho*(J-I)`` for one locked reset map."""

    rho = _exact_number(reset_rate, "reset rate")
    if rho < 0:
        raise ValueError("reset rate must be nonnegative")
    A0 = build_ito_operator(inertia, activity)
    identity = mp.eye(len(BASIS_NAMES))
    A = A0 + rho * (reset_pullback(protocol) - identity)
    assert_finite_matrix(A, "Ito/jump operator")
    return A


def initial_state() -> mp.matrix:
    """Return the locked default state ``r=v=0, theta=0``."""

    state = mp.zeros(len(BASIS_NAMES), 1)
    state[INDEX["one"]] = 1
    state[INDEX["u_x"]] = 1
    state[INDEX["uu_xx"]] = 1
    return state


def slow_rate(
    protocol: str,
    inertia: Any,
    reset_rate: Any,
) -> mp.mpf:
    """Evaluate the exact preregistered slow-rate rule."""

    try:
        p, v, h = PROTOCOL_FLAGS[protocol]
    except KeyError as exc:
        raise ValueError(f"unknown reset protocol: {protocol!r}") from exc
    M = _exact_number(inertia, "inertia")
    rho = _exact_number(reset_rate, "reset rate")
    if M <= 0 or rho < 0:
        raise ValueError("slow-rate domain requires M>0 and rho>=0")
    rates = [
        1 + rho * h,
        4 + rho * h,
        1 / M + rho * v,
        2 / M + rho * v,
        1 + 1 / M + rho * int(bool(v or h)),
        1 + rho * int(bool(p or h)),
        1 / M + rho * int(bool(p or v)),
    ]
    if p:
        rates.append(rho)
    positive = [rate for rate in rates if rate > 0]
    if not positive:
        raise ValueError("slow-rate rule produced no positive rate")
    result = min(positive)
    if not mp.isfinite(result):
        raise ArithmeticError("slow rate is nonfinite")
    return result


def scaled_horizon(
    protocol: str,
    inertia: Any,
    reset_rate: Any,
    scaled_H: Any,
) -> mp.mpf:
    H = _exact_number(scaled_H, "scaled horizon")
    if H <= 0:
        raise ValueError("scaled horizon must be positive")
    return H / slow_rate(protocol, inertia, reset_rate)


def propagate(operator: mp.matrix, state: mp.matrix, time: Any) -> mp.matrix:
    """Apply the fixed mpmath matrix exponential to one state."""

    _require_matrix_shape(operator, 28, 28, "operator")
    _require_matrix_shape(state, 28, 1, "state")
    t = _exact_number(time, "time")
    if t < 0:
        raise ValueError("propagation time must be nonnegative")
    result = mp.expm(operator * t) * state
    assert_finite_matrix(result, "propagated state")
    return result


def _submatrix(
    matrix: mp.matrix,
    rows: Sequence[int],
    columns: Sequence[int],
) -> mp.matrix:
    return mp.matrix([[matrix[row, column] for column in columns] for row in rows])


def _subvector(vector: mp.matrix, rows: Sequence[int]) -> mp.matrix:
    return mp.matrix([vector[row] for row in rows])


def _put_subvector(
    target: mp.matrix,
    rows: Sequence[int],
    values: mp.matrix,
) -> None:
    for offset, row in enumerate(rows):
        target[row] = values[offset]


def solve_position_stationary(operator: mp.matrix) -> mp.matrix:
    """Solve the constrained stationary system with ``one=1``."""

    _require_matrix_shape(operator, 28, 28, "operator")
    nonconstant = tuple(range(1, 28))
    block = _submatrix(operator, nonconstant, nonconstant)
    rhs = mp.matrix([-operator[row, 0] for row in nonconstant])
    solution = mp.zeros(28, 1)
    solution[0] = 1
    _put_subvector(solution, nonconstant, mp.lu_solve(block, rhs))
    assert_finite_matrix(solution, "stationary solution")
    return solution


def _vector2(state: mp.matrix, first: int, second: int) -> mp.matrix:
    return mp.matrix([state[first], state[second]])


def _symmetric2(
    state: mp.matrix,
    xx: int,
    xy: int,
    yy: int,
) -> mp.matrix:
    return mp.matrix(
        [[state[xx], state[xy]], [state[xy], state[yy]]]
    )


def _full2(
    state: mp.matrix,
    xx: int,
    xy: int,
    yx: int,
    yy: int,
) -> mp.matrix:
    return mp.matrix(
        [[state[xx], state[xy]], [state[yx], state[yy]]]
    )


def _put_symmetric2(
    state: mp.matrix,
    indices: tuple[int, int, int],
    value: mp.matrix,
) -> None:
    state[indices[0]] = value[0, 0]
    state[indices[1]] = (value[0, 1] + value[1, 0]) / 2
    state[indices[2]] = value[1, 1]


def _put_full2(
    state: mp.matrix,
    indices: tuple[int, int, int, int],
    value: mp.matrix,
) -> None:
    state[indices[0]] = value[0, 0]
    state[indices[1]] = value[0, 1]
    state[indices[2]] = value[1, 0]
    state[indices[3]] = value[1, 1]


def _outer(left: mp.matrix, right: mp.matrix) -> mp.matrix:
    return left * right.T


def _symmetrize(value: mp.matrix) -> mp.matrix:
    return (value + value.T) / 2


def _trace2(value: mp.matrix) -> mp.mpf:
    return value[0, 0] + value[1, 1]


def state_blocks(state: mp.matrix) -> dict[str, Any]:
    """Extract raw means and tensors from one 28-entry state."""

    _require_matrix_shape(state, 28, 1, "state")
    blocks: dict[str, Any] = {
        "one": state[0],
        "r_bar": _vector2(state, 1, 2),
        "v_bar": _vector2(state, 3, 4),
        "u_bar": _vector2(state, 5, 6),
        "R": _symmetric2(state, 7, 8, 9),
        "S": _symmetric2(state, 10, 11, 12),
        "C": _full2(state, 13, 14, 15, 16),
        "Q": _full2(state, 17, 18, 19, 20),
        "W": _full2(state, 21, 22, 23, 24),
        "U": _symmetric2(state, 25, 26, 27),
    }
    for name, value in blocks.items():
        if isinstance(value, mp.matrix):
            assert_finite_matrix(value, name)
        elif not mp.isfinite(value):
            raise ArithmeticError(f"{name} is nonfinite")
    return blocks


def stationary_formula_fields(state: mp.matrix) -> dict[str, Any]:
    """Extract every applicable stationary T-022 formula field."""

    blocks = state_blocks(state)
    r = blocks["r_bar"]
    v = blocks["v_bar"]
    u = blocks["u_bar"]
    R = blocks["R"]
    S = blocks["S"]
    C = blocks["C"]
    Q = blocks["Q"]
    W = blocks["W"]
    U = blocks["U"]
    covariance = R - _outer(r, r)
    C_centered = C - _outer(r, v)
    Q_centered = Q - _outer(r, u)
    Sigma_v = S - _outer(v, v)
    Sigma_u = U - _outer(u, u)
    K = W - _outer(v, u)
    return {
        "r_bar": r,
        "v_bar": v,
        "u_bar": u,
        "R": R,
        "S": S,
        "C": C,
        "Q": Q,
        "W": W,
        "U": U,
        "Cov_r": covariance,
        "D": None,
        "b": None,
        "C_centered": C_centered,
        "Q_centered": Q_centered,
        "Sigma_v": Sigma_v,
        "Sigma_u": Sigma_u,
        "K": K,
        "raw_rr_quadratic": None,
        "raw_rr_linear": None,
        "raw_ru_linear": None,
        "raw_rv_linear": None,
        "D_eff": None,
        "raw_MSD": _trace2(R),
        "speed": _trace2(S),
        "r_dot_v": _trace2(C),
        "centered_variance": _trace2(covariance),
    }


def solve_transport_polynomial(operator: mp.matrix) -> dict[str, Any]:
    """Construct the frozen algebraic long-time transport polynomial."""

    _require_matrix_shape(operator, 28, 28, "operator")
    c0 = mp.zeros(28, 1)
    c1 = mp.zeros(28, 1)
    c2 = mp.zeros(28, 1)
    c0[0] = 1

    internal_block = _submatrix(
        operator,
        INTERNAL_NONCONSTANT_INDICES,
        INTERNAL_NONCONSTANT_INDICES,
    )
    internal_rhs = mp.matrix(
        [-operator[row, 0] for row in INTERNAL_NONCONSTANT_INDICES]
    )
    internal_solution = mp.lu_solve(internal_block, internal_rhs)
    _put_subvector(c0, INTERNAL_NONCONSTANT_INDICES, internal_solution)

    first_block = _submatrix(
        operator,
        FIRST_MOMENT_INTERNAL_INDICES,
        FIRST_MOMENT_INTERNAL_INDICES,
    )
    first_stationary = _subvector(c0, FIRST_MOMENT_INTERNAL_INDICES)
    first_initial = mp.matrix([0, 0, 1, 0])
    integrated_deviation = -mp.lu_solve(
        first_block,
        first_initial - first_stationary,
    )
    b = mp.matrix([integrated_deviation[0], integrated_deviation[1]])
    v_bar = _vector2(c0, 3, 4)
    u_bar = _vector2(c0, 5, 6)
    c0[1] = b[0]
    c0[2] = b[1]
    c1[1] = v_bar[0]
    c1[2] = v_bar[1]

    raw_C_linear = _outer(v_bar, v_bar)
    raw_Q_linear = _outer(v_bar, u_bar)
    _put_full2(c1, C_INDICES, raw_C_linear)
    _put_full2(c1, Q_INDICES, raw_Q_linear)

    cross_indices = C_INDICES + Q_INDICES
    known = tuple(index for index in range(28) if index not in cross_indices)
    cross_block = _submatrix(operator, cross_indices, cross_indices)
    known_values = _subvector(c0, known)
    cross_rhs = _subvector(c1, cross_indices) - (
        _submatrix(operator, cross_indices, known) * known_values
    )
    _put_subvector(c0, cross_indices, mp.lu_solve(cross_block, cross_rhs))

    raw_C_constant = _full2(c0, *C_INDICES)
    raw_Q_constant = _full2(c0, *Q_INDICES)
    C_centered = raw_C_constant - _outer(b, v_bar)
    Q_centered = raw_Q_constant - _outer(b, u_bar)
    D = _symmetrize(C_centered)
    raw_R_quadratic = _outer(v_bar, v_bar)
    raw_R_linear = (
        _outer(v_bar, b) + _outer(b, v_bar) + 2 * D
    )
    _put_symmetric2(c2, R_INDICES, raw_R_quadratic)
    _put_symmetric2(c1, R_INDICES, raw_R_linear)
    _put_symmetric2(c0, R_INDICES, _outer(b, b))

    S = _symmetric2(c0, *S_INDICES)
    W = _full2(c0, *W_INDICES)
    U = _symmetric2(c0, *U_INDICES)
    result = {
        "c0": c0,
        "c1": c1,
        "c2": c2,
        "b": b,
        "v_bar": v_bar,
        "u_bar": u_bar,
        "S": S,
        "W": W,
        "U": U,
        "C_centered": C_centered,
        "Q_centered": Q_centered,
        "D": D,
        "raw_rr_quadratic": raw_R_quadratic,
        "raw_rr_linear": raw_R_linear,
        "raw_ru_linear": raw_Q_linear,
        "raw_rv_linear": raw_C_linear,
    }
    assert_finite_tree(result, "transport polynomial")
    return result


def extract_transport_refinement(
    operator: mp.matrix,
    state: mp.matrix,
    time: Any,
    algebraic_solution: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract the fixed finite-horizon transport quantities."""

    _require_matrix_shape(operator, 28, 28, "operator")
    _require_matrix_shape(state, 28, 1, "state")
    T = _exact_number(time, "transport extraction time")
    blocks = state_blocks(state)
    stationary_v = algebraic_solution["v_bar"]
    b = blocks["r_bar"] - T * stationary_v
    C_centered = blocks["C"] - _outer(blocks["r_bar"], blocks["v_bar"])
    Q_centered = blocks["Q"] - _outer(blocks["r_bar"], blocks["u_bar"])
    D = _symmetrize(C_centered)
    derivative = operator * state
    second_derivative = operator * derivative
    raw_ru_linear = _full2(derivative, *Q_INDICES)
    raw_rv_linear = _full2(derivative, *C_INDICES)
    raw_rr_quadratic = _symmetric2(second_derivative, *R_INDICES) / 2
    raw_rr_linear = (
        _symmetric2(derivative, *R_INDICES)
        - 2 * T * raw_rr_quadratic
    )
    result = {
        "b": b,
        "v_bar": blocks["v_bar"],
        "u_bar": blocks["u_bar"],
        "S": blocks["S"],
        "W": blocks["W"],
        "U": blocks["U"],
        "C_centered": C_centered,
        "Q_centered": Q_centered,
        "D": D,
        "raw_rr_quadratic": raw_rr_quadratic,
        "raw_rr_linear": raw_rr_linear,
        "raw_ru_linear": raw_ru_linear,
        "raw_rv_linear": raw_rv_linear,
        "derivative": derivative,
        "second_derivative": second_derivative,
    }
    assert_finite_tree(result, "transport refinement")
    return result


def reconstruct_transport_formula_fields(
    extraction: Mapping[str, Any],
    time: Any,
) -> dict[str, Any]:
    """Reconstruct every applicable long-time T-022 formula field."""

    t = _exact_number(time, "probe time")
    if t < 0:
        raise ValueError("probe time must be nonnegative")
    b = extraction["b"]
    v = extraction["v_bar"]
    u = extraction["u_bar"]
    S = extraction["S"]
    W = extraction["W"]
    U = extraction["U"]
    C_centered = extraction["C_centered"]
    Q_centered = extraction["Q_centered"]
    D = extraction["D"]
    r = v * t + b
    R = _outer(r, r) + 2 * D * t
    C = _outer(r, v) + C_centered
    Q = _outer(r, u) + Q_centered
    covariance = 2 * D * t
    Sigma_v = S - _outer(v, v)
    Sigma_u = U - _outer(u, u)
    K = W - _outer(v, u)
    fields = {
        "r_bar": r,
        "v_bar": v,
        "u_bar": u,
        "R": R,
        "S": S,
        "C": C,
        "Q": Q,
        "W": W,
        "U": U,
        "Cov_r": covariance,
        "D": D,
        "b": b,
        "C_centered": C_centered,
        "Q_centered": Q_centered,
        "Sigma_v": Sigma_v,
        "Sigma_u": Sigma_u,
        "K": K,
        "raw_rr_quadratic": extraction["raw_rr_quadratic"],
        "raw_rr_linear": extraction["raw_rr_linear"],
        "raw_ru_linear": extraction["raw_ru_linear"],
        "raw_rv_linear": extraction["raw_rv_linear"],
        "D_eff": _trace2(D) / 2,
        "raw_MSD": _trace2(R),
        "speed": _trace2(S),
        "r_dot_v": _trace2(C),
        "centered_variance": _trace2(covariance),
    }
    assert_finite_tree(fields, "transport formula fields")
    return fields


def flatten_formula_fields(fields: Mapping[str, Any]) -> dict[str, mp.mpf | None]:
    """Flatten the common formula schema into scalar Cartesian components."""

    if tuple(fields) != FORMULA_FIELDS:
        raise ValueError("formula fields do not use the locked ordering")
    flat: dict[str, mp.mpf | None] = {}
    for field, value in fields.items():
        if value is None:
            flat[field] = None
        elif isinstance(value, mp.matrix):
            if value.cols == 1:
                for row in range(value.rows):
                    flat[f"{field}[{row}]"] = value[row]
            else:
                for row in range(value.rows):
                    for column in range(value.cols):
                        flat[f"{field}[{row},{column}]"] = value[row, column]
        else:
            flat[field] = _exact_number(value, field)
    assert_finite_tree(
        {key: value for key, value in flat.items() if value is not None},
        "flattened formula fields",
    )
    return flat


def stationary_residual(
    operator: mp.matrix,
    stationary_state: mp.matrix,
) -> mp.mpf:
    return max_abs(operator * stationary_state)


def transport_polynomial_residuals(
    operator: mp.matrix,
    solution: Mapping[str, Any],
    probe_times: Sequence[Any],
) -> dict[str, mp.mpf]:
    """Return every frozen algebraic recurrence/ODE residual."""

    c0 = solution["c0"]
    c1 = solution["c1"]
    c2 = solution["c2"]
    result: dict[str, mp.mpf] = {
        "A_c2": max_abs(operator * c2),
        "A_c1_minus_2c2": max_abs(operator * c1 - 2 * c2),
        "A_c0_minus_c1": max_abs(operator * c0 - c1),
    }
    for probe in probe_times:
        t = _exact_number(probe, "probe time")
        state = c2 * t**2 + c1 * t + c0
        derivative = 2 * c2 * t + c1
        result[f"ode_at_{probe}"] = max_abs(derivative - operator * state)
    assert_finite_tree(result, "transport residuals")
    return result


def max_abs(value: mp.matrix | Sequence[mp.mpf]) -> mp.mpf:
    """Return the maximum finite absolute component, or exact zero if empty."""

    if isinstance(value, mp.matrix):
        components = [
            abs(value[row, column])
            for row in range(value.rows)
            for column in range(value.cols)
        ]
    else:
        components = [abs(component) for component in value]
    result = max(components, default=mp.mpf("0"))
    if not mp.isfinite(result):
        raise ArithmeticError("maximum absolute component is nonfinite")
    return result


def assert_finite_matrix(value: mp.matrix, label: str) -> None:
    for row in range(value.rows):
        for column in range(value.cols):
            if not mp.isfinite(value[row, column]):
                raise ArithmeticError(f"{label} contains a nonfinite component")


def assert_finite_tree(value: Any, label: str) -> None:
    if isinstance(value, mp.matrix):
        assert_finite_matrix(value, label)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            assert_finite_tree(item, f"{label}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            assert_finite_tree(item, f"{label}[{index}]")
    elif value is None:
        return
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, mp.mpf)):
        if not mp.isfinite(value):
            raise ArithmeticError(f"{label} is nonfinite")
    else:
        raise TypeError(f"{label} contains unsupported value {type(value)!r}")


def _require_matrix_shape(
    value: mp.matrix,
    rows: int,
    columns: int,
    label: str,
) -> None:
    if not isinstance(value, mp.matrix) or value.rows != rows or value.cols != columns:
        raise ValueError(f"{label} must have shape {rows}x{columns}")
