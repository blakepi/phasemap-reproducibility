"""Machine-readable all-seven second-order formula registry.

The registry is a serialization layer over the accepted T-020 and T-021
formula APIs.  It deliberately contains no independent formula algebra:
changing an underlying accepted formula is reflected here only through the
corresponding public theory API and its regression checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import sympy as sp

from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol

from .nonposition_protocols import (
    NONPOSITION_PROTOCOLS,
    nonposition_protocol_second_moments,
)
from .position_protocols import (
    POSITION_PROTOCOLS,
    position_protocol_stationary_second_moments,
)


FORMULA_REGISTRY_VERSION = "1.0"
"""Version of the strict export schema, not a scientific-contract version."""

TIME = sp.Symbol("t", nonnegative=True)
"""Shared exact time symbol for long-time transport-polynomial records."""

SHARED_NOTATION: Mapping[str, str] = MappingProxyType(
    {
        "inertia": "M",
        "activity": "Pe",
        "reset_rate": "rho",
        "time": "t",
        "position_mean": "r_bar",
        "velocity_mean": "v_bar",
        "orientation_mean": "u_bar",
        "position_second": "R",
        "velocity_second": "S",
        "position_velocity": "C",
        "position_orientation": "Q",
        "velocity_orientation": "W",
        "orientation_second": "U",
        "centered_spatial_covariance": "Cov_r",
        "diffusion_tensor": "D",
        "position_mean_offset": "b",
        "velocity_covariance": "Sigma_v",
        "orientation_covariance": "Sigma_u",
        "velocity_orientation_covariance": "K",
        "position_velocity_centered": "C_centered",
        "position_orientation_centered": "Q_centered",
        "effective_diffusion": "D_eff",
        "mean_squared_displacement": "raw_MSD",
        "mean_squared_speed": "speed",
        "mean_position_dot_velocity": "r_dot_v",
        "centered_spatial_variance": "centered_variance",
    }
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


def _encode(value: sp.Expr | sp.MatrixBase | None) -> object:
    """Return a JSON-serializable, exact SymPy representation of ``value``."""

    if value is None:
        return None
    if isinstance(value, sp.MatrixBase):
        return {
            "kind": "matrix",
            "shape": [value.rows, value.cols],
            "entries": [
                [sp.srepr(value[row, column]) for column in range(value.cols)]
                for row in range(value.rows)
            ],
        }
    return {"kind": "scalar", "expression": sp.srepr(value)}


def _record(
    protocol: Protocol,
    *,
    position_regime: str,
    spatial_class: str,
    raw_msd_class: str,
    formulas: Mapping[str, sp.Expr | sp.MatrixBase | None],
) -> dict[str, object]:
    if tuple(formulas) != FORMULA_FIELDS:
        raise ValueError("formula record does not use the shared field ordering")
    return {
        "schema_version": FORMULA_REGISTRY_VERSION,
        "protocol": protocol.value,
        "position_regime": position_regime,
        "scope": (
            "stationary" if position_regime == "stationary"
            else "long_time_polynomial"
        ),
        "spatial_class": spatial_class,
        "raw_msd_class": raw_msd_class,
        "notation": dict(SHARED_NOTATION),
        "formulas": {field: _encode(formulas[field]) for field in FORMULA_FIELDS},
    }


def export_formula_registry(
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> dict[str, dict[str, object]]:
    """Export exact, JSON-serializable formula records for all seven maps.

    Position-reset records require the accepted T-020 domain ``rho > 0``.
    Non-position records retain the T-021 domain ``rho >= 0``.  SymPy
    ``srepr`` strings preserve exact expressions without float conversion.
    """

    records: dict[str, dict[str, object]] = {}
    for protocol in ALL_PROTOCOLS:
        if protocol in POSITION_PROTOCOLS:
            moments = position_protocol_stationary_second_moments(
                protocol, inertia, activity, reset_rate
            )
            formulas = {
                "r_bar": moments.position_mean,
                "v_bar": moments.velocity_mean,
                "u_bar": moments.orientation_mean,
                "R": moments.position_second,
                "S": moments.velocity_second,
                "C": moments.position_velocity,
                "Q": moments.position_orientation,
                "W": moments.velocity_orientation,
                "U": moments.orientation_second,
                "Cov_r": moments.centered_spatial_covariance,
                "D": None,
                "b": None,
                "C_centered": sp.ImmutableDenseMatrix(
                    moments.position_velocity
                    - moments.position_mean * moments.velocity_mean.T
                ),
                "Q_centered": sp.ImmutableDenseMatrix(
                    moments.position_orientation
                    - moments.position_mean * moments.orientation_mean.T
                ),
                "Sigma_v": sp.ImmutableDenseMatrix(
                    moments.velocity_second
                    - moments.velocity_mean * moments.velocity_mean.T
                ),
                "Sigma_u": sp.ImmutableDenseMatrix(
                    moments.orientation_second
                    - moments.orientation_mean * moments.orientation_mean.T
                ),
                "K": sp.ImmutableDenseMatrix(
                    moments.velocity_orientation
                    - moments.velocity_mean * moments.orientation_mean.T
                ),
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
            records[protocol.value] = _record(
                protocol,
                position_regime="stationary",
                spatial_class=moments.spatial_class,
                raw_msd_class="stationary/localized",
                formulas=formulas,
            )
        elif protocol in NONPOSITION_PROTOCOLS:
            moments = nonposition_protocol_second_moments(
                protocol, inertia, activity, reset_rate
            )
            position_mean = moments.asymptotic_position_mean(TIME)
            position_orientation = sp.ImmutableDenseMatrix(
                position_mean * moments.orientation_mean.T
                + moments.position_orientation_centered_limit
            )
            position_velocity = sp.ImmutableDenseMatrix(
                position_mean * moments.velocity_mean.T
                + moments.position_velocity_centered_limit
            )
            position_second = sp.ImmutableDenseMatrix(
                position_mean * position_mean.T
                + 2 * moments.diffusion_tensor * TIME
            )
            centered_covariance = sp.ImmutableDenseMatrix(
                2 * moments.diffusion_tensor * TIME
            )
            formulas = {
                "r_bar": position_mean,
                "v_bar": moments.velocity_mean,
                "u_bar": moments.orientation_mean,
                "R": position_second,
                "S": moments.velocity_second,
                "C": position_velocity,
                "Q": position_orientation,
                "W": moments.velocity_orientation,
                "U": moments.orientation_second,
                "Cov_r": centered_covariance,
                "D": moments.diffusion_tensor,
                "b": moments.position_mean_offset,
                "C_centered": moments.position_velocity_centered_limit,
                "Q_centered": moments.position_orientation_centered_limit,
                "Sigma_v": moments.velocity_covariance,
                "Sigma_u": moments.orientation_covariance,
                "K": moments.velocity_orientation_covariance,
                "raw_rr_quadratic": moments.raw_position_second_quadratic_coefficient,
                "raw_rr_linear": moments.raw_position_second_linear_coefficient,
                "raw_ru_linear": moments.raw_position_orientation_linear_coefficient,
                "raw_rv_linear": moments.raw_position_velocity_linear_coefficient,
                "D_eff": moments.effective_diffusion,
                "raw_MSD": sp.trace(position_second),
                "speed": moments.stationary_mean_squared_speed,
                "r_dot_v": sp.trace(position_velocity),
                "centered_variance": sp.trace(centered_covariance),
            }
            records[protocol.value] = _record(
                protocol,
                position_regime="transport",
                spatial_class=moments.spatial_class,
                raw_msd_class=moments.raw_msd_class,
                formulas=formulas,
            )
        else:  # Defensive: the simulation registry is the authoritative map set.
            raise ValueError(f"no accepted second-order formula record for {protocol}")
    return records
