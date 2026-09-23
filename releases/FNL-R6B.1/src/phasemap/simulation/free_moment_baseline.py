"""Deterministic free-process propagation of the T-010 moment system.

This module is deliberately independent of both the T-011 analytic reference
implementation and the stochastic S-011 simulator.  It constructs the exact
T-010 free moment matrix, converts that matrix once to binary64, and advances
the locked 28-state initial value problem with the preregistered order-18
Taylor action.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TypeAlias

import numpy as np
import numpy.typing as npt
import sympy as sp

from phasemap.theory.generator import Symbols, second_order_moment_system


FloatArray: TypeAlias = npt.NDArray[np.float64]
ExactRational: TypeAlias = str | int | Fraction | sp.Rational

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

TAYLOR_ORDER = 18
MIN_INERTIA = sp.Rational(1, 8)
MAX_TIME = sp.Rational(6)
ALLOWED_MAX_STEPS = (sp.Rational(1, 16), sp.Rational(1, 32))


@dataclass(frozen=True, slots=True)
class FreeMomentMatrix:
    """A validated binary64 realization of the exact T-010 free matrix."""

    names: tuple[str, ...]
    values: FloatArray


@dataclass(frozen=True, slots=True)
class FreeMomentPropagation:
    """One fixed-resolution propagation from the locked initial state."""

    state: FloatArray
    step_count: int
    step_size: sp.Rational


def _rational(value: ExactRational, label: str) -> sp.Rational:
    """Parse one exact rational without accepting binary floating-point input."""

    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{label} must be supplied as an exact rational")
    if isinstance(value, Fraction):
        result = sp.Rational(value.numerator, value.denominator)
    elif isinstance(value, sp.Rational):
        result = value
    elif isinstance(value, (str, int)):
        try:
            result = sp.Rational(value)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"{label} must be a finite exact rational") from exc
    else:
        raise TypeError(f"{label} must be supplied as an exact rational")
    if result.is_finite is not True:
        raise ValueError(f"{label} must be finite")
    return result


def build_free_moment_matrix(
    inertia: ExactRational,
    activity: ExactRational,
) -> FreeMomentMatrix:
    """Build the free T-010 matrix after exact rational substitution.

    No T-011 expression or stochastic simulation code enters this route.
    """

    exact_inertia = _rational(inertia, "inertia")
    exact_activity = _rational(activity, "activity")
    if exact_inertia < MIN_INERTIA:
        raise ValueError("inertia must be at least 1/8 for the frozen route")
    if exact_activity < 0:
        raise ValueError("activity must be nonnegative")

    symbols = Symbols.create()
    system = second_order_moment_system(symbols, None)
    if system.names != BASIS_NAMES:
        raise RuntimeError("T-010 basis does not match the frozen S-011 basis")
    if system.matrix.shape != (len(BASIS_NAMES), len(BASIS_NAMES)):
        raise RuntimeError("T-010 matrix does not have the required 28x28 shape")

    exact_matrix = system.matrix.subs(
        {
            symbols.inertia: exact_inertia,
            symbols.activity: exact_activity,
        }
    )
    if exact_matrix.free_symbols:
        raise RuntimeError("free symbols remain after T-010 parameter substitution")

    values = np.array(exact_matrix.tolist(), dtype=np.float64, order="C")
    if values.shape != (len(BASIS_NAMES), len(BASIS_NAMES)):
        raise RuntimeError("binary64 matrix conversion changed the required shape")
    if not np.isfinite(values).all():
        raise FloatingPointError("T-010 matrix conversion produced a nonfinite value")
    values.setflags(write=False)
    return FreeMomentMatrix(names=system.names, values=values)


def default_free_moment_state(
    names: tuple[str, ...] = BASIS_NAMES,
) -> FloatArray:
    """Return the locked state for r(0)=v(0)=0 and theta(0)=0."""

    if names != BASIS_NAMES:
        raise ValueError("basis names do not match the frozen S-011 basis")
    state = np.zeros(len(names), dtype=np.float64)
    index = {name: position for position, name in enumerate(names)}
    state[index["one"]] = 1.0
    state[index["u_x"]] = 1.0
    state[index["uu_xx"]] = 1.0
    return state


def _validated_matrix_and_state(
    matrix: npt.ArrayLike,
    state: npt.ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    values = np.asarray(matrix, dtype=np.float64)
    vector = np.asarray(state, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("matrix must be square")
    if vector.ndim != 1 or vector.shape[0] != values.shape[0]:
        raise ValueError("state must be a vector matching the matrix dimension")
    if not np.isfinite(values).all() or not np.isfinite(vector).all():
        raise FloatingPointError("matrix and state must be finite")
    return values, vector


def taylor18_step(
    matrix: npt.ArrayLike,
    state: npt.ArrayLike,
    step_size: float,
) -> FloatArray:
    """Apply the fixed order-18 Taylor polynomial for one linear-ODE step."""

    values, vector = _validated_matrix_and_state(matrix, state)
    if isinstance(step_size, bool) or not np.isfinite(step_size) or step_size < 0:
        raise ValueError("step_size must be a finite nonnegative float")

    term = vector.copy()
    result = vector.copy()
    for order in range(1, TAYLOR_ORDER + 1):
        term = (step_size / order) * (values @ term)
        if not np.isfinite(term).all():
            raise FloatingPointError("Taylor recurrence produced a nonfinite term")
        result = result + term
        if not np.isfinite(result).all():
            raise FloatingPointError("Taylor recurrence produced a nonfinite state")
    return result


def propagate_free_moment_state(
    matrix: npt.ArrayLike,
    initial_state: npt.ArrayLike,
    time: ExactRational,
    max_step: ExactRational,
) -> FreeMomentPropagation:
    """Propagate with the frozen equal-step rule and an explicit t=0 branch."""

    values, vector = _validated_matrix_and_state(matrix, initial_state)
    exact_time = _rational(time, "time")
    exact_max_step = _rational(max_step, "max_step")
    if exact_time < 0:
        raise ValueError("time must be nonnegative")
    if exact_time > MAX_TIME:
        raise ValueError("time must not exceed 6 for the frozen route")
    if exact_max_step not in ALLOWED_MAX_STEPS:
        raise ValueError("max_step must be exactly 1/16 or 1/32")
    if exact_time == 0:
        return FreeMomentPropagation(
            state=vector.copy(),
            step_count=0,
            step_size=sp.Rational(0),
        )

    ratio = exact_time / exact_max_step
    step_count = int((ratio.p + ratio.q - 1) // ratio.q)
    exact_step_size = exact_time / step_count
    step_size = float(exact_step_size)
    state = vector.copy()
    for _ in range(step_count):
        state = taylor18_step(values, state, step_size)
    return FreeMomentPropagation(
        state=state,
        step_count=step_count,
        step_size=exact_step_size,
    )


def _state_index_and_values(
    names: tuple[str, ...],
    state: npt.ArrayLike,
) -> tuple[dict[str, int], FloatArray]:
    if names != BASIS_NAMES:
        raise ValueError("basis names do not match the frozen S-011 basis")
    vector = np.asarray(state, dtype=np.float64)
    if vector.shape != (len(BASIS_NAMES),):
        raise ValueError("state does not have the required 28 entries")
    if not np.isfinite(vector).all():
        raise FloatingPointError("state contains a nonfinite value")
    return {name: position for position, name in enumerate(names)}, vector


def extract_free_observables(
    names: tuple[str, ...],
    state: npt.ArrayLike,
) -> dict[str, float]:
    """Extract the nine preregistered T-011 comparison observables."""

    index, values = _state_index_and_values(names, state)
    r_x = values[index["r_x"]]
    r_y = values[index["r_y"]]
    raw_msd = values[index["rr_xx"]] + values[index["rr_yy"]]
    result = {
        "orientation_mean_x": float(values[index["u_x"]]),
        "mean_velocity_x": float(values[index["v_x"]]),
        "mean_position_x": float(r_x),
        "velocity_dot_orientation": float(
            values[index["vu_xx"]] + values[index["vu_yy"]]
        ),
        "position_dot_orientation": float(
            values[index["ru_xx"]] + values[index["ru_yy"]]
        ),
        "mean_squared_speed": float(
            values[index["vv_xx"]] + values[index["vv_yy"]]
        ),
        "mean_position_dot_velocity": float(
            values[index["rv_xx"]] + values[index["rv_yy"]]
        ),
        "mean_squared_displacement": float(raw_msd),
        "centered_spatial_variance": float(raw_msd - r_x * r_x - r_y * r_y),
    }
    if not all(np.isfinite(value) for value in result.values()):
        raise FloatingPointError("observable extraction produced a nonfinite value")
    return result


def extract_free_invariants(
    names: tuple[str, ...],
    state: npt.ArrayLike,
) -> dict[str, float | dict[str, float]]:
    """Extract the locked constant, orientation, and reflection invariants."""

    index, values = _state_index_and_values(names, state)
    result = {
        "constant": float(values[index["one"]]),
        "orientation_norm": float(
            values[index["uu_xx"]] + values[index["uu_yy"]]
        ),
        "symmetry_forced_zero": {
            name: float(values[index[name]]) for name in SYMMETRY_ZERO_NAMES
        },
    }
    scalar_values = (result["constant"], result["orientation_norm"])
    zero_values = result["symmetry_forced_zero"]
    if not isinstance(zero_values, dict) or not all(
        np.isfinite(value) for value in (*scalar_values, *zero_values.values())
    ):
        raise FloatingPointError("invariant extraction produced a nonfinite value")
    return result
