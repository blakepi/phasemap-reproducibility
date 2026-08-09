"""S-021 comparison adapter for the accepted T-022 and T-012 formulas.

This is the only S-021 module that imports PHASEMAP theory code or SymPy.
It performs no artifact access and exposes only finite, independently
flattened ``mpmath`` reference values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import mpmath as mp
import sympy as sp

from phasemap.theory.complete_reset_baseline import (
    complete_reset_stationary_second_moments,
)
from phasemap.theory.formula_registry import (
    FORMULA_FIELDS,
    export_formula_registry,
)


POSITION_PROTOCOLS: tuple[str, ...] = ("P", "PV", "PTheta", "PVTheta")
TRANSPORT_PROTOCOLS: tuple[str, ...] = ("V", "Theta", "VTheta")
ALL_PROTOCOLS: tuple[str, ...] = (
    "P",
    "V",
    "Theta",
    "PV",
    "PTheta",
    "VTheta",
    "PVTheta",
)

EXPECTED_FORMULA_FIELDS: tuple[str, ...] = (
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

VECTOR_FIELDS: frozenset[str] = frozenset(
    {"r_bar", "v_bar", "u_bar", "b"}
)
MATRIX_FIELDS: frozenset[str] = frozenset(
    {
        "R",
        "S",
        "C",
        "Q",
        "W",
        "U",
        "Cov_r",
        "D",
        "C_centered",
        "Q_centered",
        "Sigma_v",
        "Sigma_u",
        "K",
        "raw_rr_quadratic",
        "raw_rr_linear",
        "raw_ru_linear",
        "raw_rv_linear",
    }
)
SCALAR_FIELDS: frozenset[str] = frozenset(
    {
        "D_eff",
        "raw_MSD",
        "speed",
        "r_dot_v",
        "centered_variance",
    }
)
POSITION_NULL_FIELDS: frozenset[str] = frozenset(
    {
        "D",
        "b",
        "raw_rr_quadratic",
        "raw_rr_linear",
        "raw_ru_linear",
        "raw_rv_linear",
        "D_eff",
    }
)

_RATIONAL_PATTERN = re.compile(r"[+-]?\d+(?:/[+-]?\d+)?\Z")

if tuple(FORMULA_FIELDS) != EXPECTED_FORMULA_FIELDS:
    raise RuntimeError("production T-022 formula fields changed")


def _exact_rational(
    value: str,
    label: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> sp.Rational:
    if not isinstance(value, str) or _RATIONAL_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} is not an exact decimal-free rational")
    if "/" in value:
        numerator_text, denominator_text = value.split("/", 1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)
        if denominator == 0:
            raise ZeroDivisionError(f"{label} has a zero denominator")
        result = sp.Rational(numerator, denominator)
    else:
        result = sp.Rational(int(value), 1)
    if positive and result <= 0:
        raise ValueError(f"{label} must be positive")
    if nonnegative and result < 0:
        raise ValueError(f"{label} must be nonnegative")
    return result


def _validated_dps(dps: int) -> int:
    if isinstance(dps, bool) or not isinstance(dps, int) or dps < 15:
        raise ValueError("dps must be an integer of at least 15")
    return dps


def _decode_srepr(expression: str) -> sp.Expr:
    if not isinstance(expression, str):
        raise TypeError("encoded SymPy expression must be a string")
    decoded = sp.sympify(expression, locals=vars(sp))
    if not isinstance(decoded, sp.Expr):
        raise TypeError("encoded formula did not decode to a SymPy expression")
    return decoded


def _evaluate_expression(
    expression: sp.Expr,
    *,
    probe_time: sp.Rational | None,
    dps: int,
) -> mp.mpf:
    substitutions: dict[sp.Symbol, sp.Rational] = {}
    for symbol in expression.free_symbols:
        if symbol.name != "t":
            raise ValueError(f"unexpected free formula symbol: {symbol}")
        if probe_time is None:
            raise ValueError("transport formula requires an exact probe time")
        substitutions[symbol] = probe_time
    evaluated = expression.subs(substitutions)
    if evaluated.free_symbols:
        raise ValueError("formula remained symbolic after exact substitution")
    with mp.workdps(dps):
        numeric = mp.mpf(str(sp.N(evaluated, dps)))
        if not mp.isfinite(numeric):
            raise ArithmeticError("reference formula evaluated as nonfinite")
        return numeric


def _component_key(field: str, row: int, column: int, columns: int) -> str:
    if columns == 1:
        return f"{field}[{row}]"
    return f"{field}[{row},{column}]"


def _expected_shape(field: str) -> tuple[int, int] | None:
    if field in VECTOR_FIELDS:
        return (2, 1)
    if field in MATRIX_FIELDS:
        return (2, 2)
    if field in SCALAR_FIELDS:
        return None
    raise ValueError(f"unknown formula field: {field}")


def _flatten_encoded_record(
    record: Mapping[str, Any],
    *,
    probe_time: sp.Rational | None,
    dps: int,
) -> dict[str, mp.mpf | None]:
    formulas = record.get("formulas")
    if not isinstance(formulas, dict) or tuple(formulas) != EXPECTED_FORMULA_FIELDS:
        raise ValueError("T-022 formula record does not use the locked fields")
    protocol = record.get("protocol")
    expected_nulls = POSITION_NULL_FIELDS if protocol in POSITION_PROTOCOLS else set()
    flat: dict[str, mp.mpf | None] = {}
    observed_nulls: set[str] = set()
    for field in EXPECTED_FORMULA_FIELDS:
        encoded = formulas[field]
        shape = _expected_shape(field)
        if encoded is None:
            observed_nulls.add(field)
            flat[field] = None
            continue
        if not isinstance(encoded, dict):
            raise TypeError(f"T-022 field {field} has an invalid encoding")
        if shape is None:
            if encoded.get("kind") != "scalar" or set(encoded) != {
                "kind",
                "expression",
            }:
                raise ValueError(f"T-022 scalar field {field} is malformed")
            flat[field] = _evaluate_expression(
                _decode_srepr(encoded["expression"]),
                probe_time=probe_time,
                dps=dps,
            )
            continue
        if (
            encoded.get("kind") != "matrix"
            or encoded.get("shape") != list(shape)
            or set(encoded) != {"kind", "shape", "entries"}
        ):
            raise ValueError(f"T-022 matrix field {field} is malformed")
        entries = encoded["entries"]
        if (
            not isinstance(entries, list)
            or len(entries) != shape[0]
            or any(
                not isinstance(row, list) or len(row) != shape[1]
                for row in entries
            )
        ):
            raise ValueError(f"T-022 matrix entries for {field} are malformed")
        for row in range(shape[0]):
            for column in range(shape[1]):
                flat[_component_key(field, row, column, shape[1])] = (
                    _evaluate_expression(
                        _decode_srepr(entries[row][column]),
                        probe_time=probe_time,
                        dps=dps,
                    )
                )
    if observed_nulls != set(expected_nulls):
        raise ValueError(
            f"T-022 null semantics mismatch for {protocol}: {observed_nulls}"
        )
    _require_finite_flat(flat)
    return flat


def _flatten_symbolic_fields(
    fields: Mapping[str, sp.Expr | sp.MatrixBase | None],
    *,
    dps: int,
) -> dict[str, mp.mpf | None]:
    if tuple(fields) != EXPECTED_FORMULA_FIELDS:
        raise ValueError("T-012 formula fields do not use the locked ordering")
    flat: dict[str, mp.mpf | None] = {}
    observed_nulls: set[str] = set()
    for field in EXPECTED_FORMULA_FIELDS:
        value = fields[field]
        shape = _expected_shape(field)
        if value is None:
            observed_nulls.add(field)
            flat[field] = None
            continue
        if shape is None:
            if not isinstance(value, sp.Expr):
                raise TypeError(f"T-012 scalar field {field} is malformed")
            flat[field] = _evaluate_expression(
                value,
                probe_time=None,
                dps=dps,
            )
            continue
        if not isinstance(value, sp.MatrixBase) or value.shape != shape:
            raise ValueError(f"T-012 matrix field {field} is malformed")
        for row in range(shape[0]):
            for column in range(shape[1]):
                flat[_component_key(field, row, column, shape[1])] = (
                    _evaluate_expression(
                        value[row, column],
                        probe_time=None,
                        dps=dps,
                    )
                )
    if observed_nulls != set(POSITION_NULL_FIELDS):
        raise ValueError("T-012 null semantics do not match PVTheta")
    _require_finite_flat(flat)
    return flat


def _require_finite_flat(values: Mapping[str, mp.mpf | None]) -> None:
    for key, value in values.items():
        if value is not None and not mp.isfinite(value):
            raise ArithmeticError(f"reference component {key} is nonfinite")


def _parameters(
    inertia: str,
    activity: str,
    reset_rate: str,
) -> tuple[sp.Rational, sp.Rational, sp.Rational]:
    return (
        _exact_rational(inertia, "inertia", positive=True),
        _exact_rational(activity, "activity", nonnegative=True),
        _exact_rational(reset_rate, "reset rate", nonnegative=True),
    )


@lru_cache(maxsize=None)
def _registry_for(
    inertia: sp.Rational,
    activity: sp.Rational,
    reset_rate: sp.Rational,
) -> dict[str, dict[str, object]]:
    """Cache the exact per-case export; probe-time evaluation stays separate."""

    return export_formula_registry(inertia, activity, reset_rate)


def t022_reference(
    protocol: str,
    inertia: str,
    activity: str,
    reset_rate: str,
    probe_time: str | None,
    dps: int = 100,
) -> dict[str, mp.mpf | None]:
    """Evaluate and flatten every applicable T-022 field."""

    precision = _validated_dps(dps)
    if protocol not in ALL_PROTOCOLS:
        raise ValueError(f"unknown protocol: {protocol!r}")
    if protocol in POSITION_PROTOCOLS:
        if probe_time is not None:
            raise ValueError("position protocols require probe_time=None")
        exact_time = None
    else:
        if probe_time is None:
            raise ValueError("transport protocols require an exact probe time")
        exact_time = _exact_rational(
            probe_time,
            "probe time",
            nonnegative=True,
        )
    M, Pe, rho = _parameters(inertia, activity, reset_rate)
    if protocol in POSITION_PROTOCOLS and rho <= 0:
        raise ValueError("position-protocol T-022 formulas require rho>0")
    records = _registry_for(M, Pe, rho)
    if tuple(records) != ALL_PROTOCOLS:
        raise ValueError("T-022 registry protocol order or membership changed")
    record = records[protocol]
    expected_scope = (
        "stationary" if protocol in POSITION_PROTOCOLS
        else "long_time_polynomial"
    )
    if (
        record.get("protocol") != protocol
        or record.get("scope") != expected_scope
    ):
        raise ValueError("T-022 record identity or scope mismatch")
    return _flatten_encoded_record(
        record,
        probe_time=exact_time,
        dps=precision,
    )


def t012_reference(
    inertia: str,
    activity: str,
    reset_rate: str,
    dps: int = 100,
) -> dict[str, mp.mpf | None]:
    """Evaluate the accepted T-012 PVTheta stationary fields independently."""

    precision = _validated_dps(dps)
    M, Pe, rho = _parameters(inertia, activity, reset_rate)
    if rho <= 0:
        raise ValueError("T-012 complete-reset stationary formulas require rho>0")
    moments = complete_reset_stationary_second_moments(M, Pe, rho)
    r = moments.position_mean
    v = moments.velocity_mean
    u = moments.orientation_mean
    R = moments.position_second
    S = moments.velocity_second
    C = moments.position_velocity
    Q = moments.position_orientation
    W = moments.velocity_orientation
    U = moments.orientation_second
    covariance = moments.centered_spatial_covariance
    C_centered = sp.ImmutableDenseMatrix(C - r * v.T)
    Q_centered = sp.ImmutableDenseMatrix(Q - r * u.T)
    Sigma_v = sp.ImmutableDenseMatrix(S - v * v.T)
    Sigma_u = sp.ImmutableDenseMatrix(U - u * u.T)
    K = sp.ImmutableDenseMatrix(W - v * u.T)
    fields: dict[str, sp.Expr | sp.MatrixBase | None] = {
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
        "raw_MSD": moments.mean_squared_displacement,
        "speed": moments.mean_squared_speed,
        "r_dot_v": moments.mean_position_dot_velocity,
        "centered_variance": moments.centered_spatial_variance,
    }
    return _flatten_symbolic_fields(fields, dps=precision)


def reference_self_check(
    inertia: str = "3/2",
    activity: str = "2/3",
    reset_rate: str = "5/7",
    dps: int = 100,
) -> dict[str, str | int]:
    """Cross-check T-022 PVTheta against the separate T-012 API."""

    t022 = t022_reference(
        "PVTheta",
        inertia,
        activity,
        reset_rate,
        None,
        dps,
    )
    t012 = t012_reference(inertia, activity, reset_rate, dps)
    if tuple(t022) != tuple(t012):
        raise ValueError("T-022 and T-012 flattened keys differ")
    with mp.workdps(_validated_dps(dps)):
        discrepancies = [
            abs(t022[key] - t012[key])
            for key in t022
            if t022[key] is not None and t012[key] is not None
        ]
        if any((t022[key] is None) != (t012[key] is None) for key in t022):
            raise ValueError("T-022 and T-012 null semantics differ")
        maximum = max(discrepancies, default=mp.mpf("0"))
        if not mp.isfinite(maximum):
            raise ArithmeticError("reference self-check discrepancy is nonfinite")
        return {
            "protocol": "PVTheta",
            "non_null_components": len(discrepancies),
            "null_fields": len(POSITION_NULL_FIELDS),
            "max_abs_discrepancy": mp.nstr(
                maximum,
                _validated_dps(dps),
                strip_zeros=False,
            ),
        }
