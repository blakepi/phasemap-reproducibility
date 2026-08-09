"""Independent deterministic complete-reset moment/quadrature route for S-012.

This module intentionally contains no theory, stochastic, or file-system
dependencies.  Its matrices are direct transcriptions of the frozen plan.
"""
from __future__ import annotations

from typing import Mapping

import mpmath as mp


BASIS_NAMES = (
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
PASSIVE_BASIS_NAMES = (
    "one",
    "S",
    "P",
    "Q",
    "S2",
    "SP",
    "P2",
    "SQ",
    "PQ",
    "Q2",
)
OBSERVABLE_NAMES = (
    "orientation_mean_x",
    "mean_velocity_x",
    "mean_position_x",
    "velocity_dot_orientation",
    "position_dot_orientation",
    "mean_squared_speed",
    "mean_position_dot_velocity",
    "mean_squared_displacement",
    "centered_spatial_variance",
)
SYMMETRY_ZERO_NAMES = (
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


def exact_rational(value: str | int | mp.mpf) -> mp.mpf:
    """Parse a frozen rational in the caller's active mpmath context."""

    if isinstance(value, bool):
        raise TypeError("exact rational values must not be bool")
    try:
        text = str(value)
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            result = mp.mpf(numerator) / mp.mpf(denominator)
        else:
            result = mp.mpf(text)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("value must be a finite exact rational") from exc
    if not mp.isfinite(result):
        raise ValueError("value must be finite")
    return result


def _zeros(n: int) -> mp.matrix:
    return mp.matrix(n, n)


def complete_reset_initial_state() -> mp.matrix:
    """Return the fixed PVTheta reset state in the locked 28-state ordering."""
    state = mp.matrix(len(BASIS_NAMES), 1)
    for name in ("one", "u_x", "uu_xx"):
        state[BASIS_NAMES.index(name)] = 1
    return state


def passive_reset_state() -> mp.matrix:
    state = mp.matrix(len(PASSIVE_BASIS_NAMES), 1)
    state[0] = 1
    return state


def build_free_second_order_matrix(
    inertia: str | int | mp.mpf,
    activity: str | int | mp.mpf,
) -> mp.matrix:
    """Hand-code the plan's free 28-state direct Itô moment matrix."""

    M, Pe = exact_rational(inertia), exact_rational(activity)
    if M <= 0 or Pe < 0:
        raise ValueError("inertia must be positive and activity nonnegative")
    A = _zeros(28)
    i = {name: n for n, name in enumerate(BASIS_NAMES)}

    def put(row: str, column: str, value: mp.mpf | int = 1) -> None:
        A[i[row], i[column]] += value

    put("r_x", "v_x")
    put("r_y", "v_y")
    for axis in ("x", "y"):
        put(f"v_{axis}", f"v_{axis}", -1 / M)
        put(f"v_{axis}", f"u_{axis}", Pe / M)
        put(f"u_{axis}", f"u_{axis}", -1)
    put("rr_xx", "rv_xx", 2)
    put("rr_xy", "rv_xy")
    put("rr_xy", "rv_yx")
    put("rr_yy", "rv_yy", 2)
    for name, vu1, vu2, constant in (
        ("vv_xx", "vu_xx", "vu_xx", True),
        ("vv_xy", "vu_xy", "vu_yx", False),
        ("vv_yy", "vu_yy", "vu_yy", True),
    ):
        put(name, name, -2 / M)
        put(name, vu1, Pe / M)
        put(name, vu2, Pe / M)
        if constant:
            put(name, "one", 2 / M**2)
    for name, vv, ru in (
        ("rv_xx", "vv_xx", "ru_xx"),
        ("rv_xy", "vv_xy", "ru_xy"),
        ("rv_yx", "vv_xy", "ru_yx"),
        ("rv_yy", "vv_yy", "ru_yy"),
    ):
        put(name, vv)
        put(name, name, -1 / M)
        put(name, ru, Pe / M)
    for name, vu in (
        ("ru_xx", "vu_xx"),
        ("ru_xy", "vu_xy"),
        ("ru_yx", "vu_yx"),
        ("ru_yy", "vu_yy"),
    ):
        put(name, vu)
        put(name, name, -1)
    for name, uu in (
        ("vu_xx", "uu_xx"),
        ("vu_xy", "uu_xy"),
        ("vu_yx", "uu_xy"),
        ("vu_yy", "uu_yy"),
    ):
        put(name, name, -(1 + 1 / M))
        put(name, uu, Pe / M)
    for name in ("uu_xx", "uu_yy"):
        put(name, "one", 2)
        put(name, name, -4)
    put("uu_xy", "uu_xy", -4)
    return A


def build_passive_fourth_matrix(inertia: str | int | mp.mpf) -> mp.matrix:
    """Hand-code the separate ten-state passive scalar Itô closure."""
    M = exact_rational(inertia)
    if M <= 0:
        raise ValueError("inertia must be positive")
    A = _zeros(10)
    i = {name: n for n, name in enumerate(PASSIVE_BASIS_NAMES)}

    def put(row: str, col: str, value: mp.mpf | int = 1) -> None:
        A[i[row], i[col]] += value

    put("S", "P", 2)
    put("P", "Q")
    put("P", "P", -1 / M)
    put("Q", "Q", -2 / M)
    put("Q", "one", 4 / M**2)
    put("S2", "SP", 4)
    put("SP", "SQ")
    put("SP", "P2", 2)
    put("SP", "SP", -1 / M)
    put("P2", "PQ", 2)
    put("P2", "P2", -2 / M)
    put("P2", "S", 2 / M**2)
    put("SQ", "PQ", 2)
    put("SQ", "SQ", -2 / M)
    put("SQ", "S", 4 / M**2)
    put("PQ", "Q2")
    put("PQ", "PQ", -3 / M)
    put("PQ", "P", 8 / M**2)
    put("Q2", "Q2", -4 / M)
    put("Q2", "Q", 16 / M**2)
    return A


def build_augmented_matrix(
    A: mp.matrix,
    reset_rate: str | int | mp.mpf,
) -> mp.matrix:
    """Return the exact weighted-state/accumulator block matrix."""

    rho = exact_rational(reset_rate)
    if rho <= 0 or A.rows != A.cols:
        raise ValueError("positive reset rate and a square matrix are required")
    n = A.rows
    B = mp.matrix(2 * n, 2 * n)
    for row in range(n):
        for column in range(n):
            B[row, column] = A[row, column]
        B[row, row] -= rho
        B[n + row, row] = rho
    return B


def augmented_quadrature(
    A: mp.matrix,
    reset: mp.matrix,
    reset_rate: str | int | mp.mpf,
    *,
    dps: int,
    rho_times_T: str | int | mp.mpf,
) -> mp.matrix:
    """Evaluate the fixed exponential-age accumulator by one augmented expm."""

    if dps < 2:
        raise ValueError("invalid quadrature cell")
    n = A.rows
    if A.cols != n or reset.rows != n or reset.cols != 1:
        raise ValueError("matrix/reset dimensions do not match")
    with mp.workdps(dps):
        rho = exact_rational(reset_rate)
        horizon = exact_rational(rho_times_T)
        if horizon <= 0:
            raise ValueError("invalid quadrature cell")
        B = build_augmented_matrix(A, rho)
        initial = mp.matrix(2 * n, 1)
        for row in range(n):
            initial[row] = reset[row]
        output = mp.expm(B * (horizon / rho)) * initial
        return mp.matrix([output[n + row] for row in range(n)])


def build_resolvent_matrix(
    A: mp.matrix,
    reset_rate: str | int | mp.mpf,
) -> mp.matrix:
    """Return C=rho*I-A in the caller's active precision context."""

    rho = exact_rational(reset_rate)
    if rho <= 0 or A.rows != A.cols:
        raise ValueError("positive reset rate and a square matrix are required")
    return rho * mp.eye(A.rows) - A


def resolvent_stationary(
    A: mp.matrix,
    reset: mp.matrix,
    reset_rate: str | int | mp.mpf,
    *,
    dps: int = 80,
) -> tuple[mp.matrix, mp.mpf, mp.mpf]:
    """Solve the mandatory infinite-horizon resolvent and report conditioning."""

    if dps < 2 or A.rows != A.cols or reset.rows != A.rows or reset.cols != 1:
        raise ValueError("invalid resolvent inputs")
    with mp.workdps(dps):
        rho = exact_rational(reset_rate)
        C = build_resolvent_matrix(A, rho)
        state = mp.lu_solve(C, rho * reset)

        def norm(matrix: mp.matrix) -> mp.mpf:
            return max(
                sum(abs(matrix[row, column]) for column in range(matrix.cols))
                for row in range(matrix.rows)
            )

        condition = norm(C) * norm(C**-1)
        residual = norm(C * state - rho * reset) / max(
            1,
            norm(C) * norm(state) + norm(rho * reset),
        )
        if (
            not mp.isfinite(condition)
            or condition <= 0
            or not mp.isfinite(residual)
            or residual < 0
        ):
            raise ArithmeticError("invalid resolvent conditioning result")
        return state, condition, residual


def extract_second_order_observables(state: mp.matrix) -> Mapping[str, mp.mpf]:
    if state.rows != 28 or state.cols != 1:
        raise ValueError("second-order state must have 28 entries")
    i = {name: n for n, name in enumerate(BASIS_NAMES)}
    raw = state[i["rr_xx"]] + state[i["rr_yy"]]
    return {
        "orientation_mean_x": state[i["u_x"]],
        "mean_velocity_x": state[i["v_x"]],
        "mean_position_x": state[i["r_x"]],
        "velocity_dot_orientation": state[i["vu_xx"]] + state[i["vu_yy"]],
        "position_dot_orientation": state[i["ru_xx"]] + state[i["ru_yy"]],
        "mean_squared_speed": state[i["vv_xx"]] + state[i["vv_yy"]],
        "mean_position_dot_velocity": state[i["rv_xx"]] + state[i["rv_yy"]],
        "mean_squared_displacement": raw,
        "centered_spatial_variance": (
            raw - state[i["r_x"]] ** 2 - state[i["r_y"]] ** 2
        ),
    }


def extract_invariants(state: mp.matrix) -> Mapping[str, mp.mpf]:
    if state.rows != 28 or state.cols != 1:
        raise ValueError("second-order state must have 28 entries")
    i = {name: n for n, name in enumerate(BASIS_NAMES)}
    return {
        "constant": state[i["one"]],
        "orientation_norm": state[i["uu_xx"]] + state[i["uu_yy"]],
        **{name: state[i[name]] for name in SYMMETRY_ZERO_NAMES},
    }


def map_state(
    names: tuple[str, ...],
    state: mp.matrix,
) -> Mapping[str, mp.mpf]:
    """Return every raw component in an explicitly checked basis order."""

    if state.rows != len(names) or state.cols != 1:
        raise ValueError("state does not match its declared basis")
    return {name: state[index] for index, name in enumerate(names)}


def passive_outputs(state: mp.matrix) -> Mapping[str, mp.mpf]:
    if state.rows != 10 or state.cols != 1:
        raise ValueError("passive state must have 10 entries")
    i = {name: n for n, name in enumerate(PASSIVE_BASIS_NAMES)}
    S, S2 = state[i["S"]], state[i["S2"]]
    if S == 0:
        raise ZeroDivisionError("passive kurtosis is undefined for S=0")
    return {
        "raw_E_abs_r_fourth": S2,
        "raw_radial_excess_kurtosis_K": S2 / (2 * S**2) - 1,
        "mean_squared_displacement": S,
        "mean_position_dot_velocity": state[i["P"]],
        "mean_squared_speed": state[i["Q"]],
    }


def stationary_residual(
    A: mp.matrix,
    state: mp.matrix,
    reset: mp.matrix,
    reset_rate: str | int | mp.mpf,
) -> mp.mpf:
    rho = exact_rational(reset_rate)
    if A.rows != A.cols or state.rows != A.rows or reset.rows != A.rows:
        raise ValueError("matrix/state/reset dimensions do not match")
    result = max(abs(value) for value in A * state + rho * (reset - state))
    if not mp.isfinite(result):
        raise ArithmeticError("stationary residual is nonfinite")
    return result
