"""Regression checks for the strict all-seven formula export."""

import json

import sympy as sp

from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol
from phasemap.theory.formula_registry import (
    FORMULA_FIELDS,
    FORMULA_REGISTRY_VERSION,
    SHARED_NOTATION,
    TIME,
    export_formula_registry,
)
from phasemap.theory.nonposition_protocols import nonposition_protocol_second_moments
from phasemap.theory.position_protocols import position_protocol_stationary_second_moments


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    return (
        sp.symbols("M", positive=True),
        sp.symbols("Pe", nonnegative=True),
        sp.symbols("rho", positive=True),
    )


def _encoded(value: sp.Expr | sp.MatrixBase | None) -> object:
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


def _symmetric_matrix(vector: sp.MatrixBase, start: int) -> sp.ImmutableDenseMatrix:
    return sp.ImmutableDenseMatrix(
        [[vector[start], vector[start + 1]], [vector[start + 1], vector[start + 2]]]
    )


def test_all_seven_records_are_strict_json_with_shared_notation() -> None:
    records = export_formula_registry(*_symbols())
    assert tuple(records) == tuple(protocol.value for protocol in ALL_PROTOCOLS)
    assert json.loads(json.dumps(records)) == records
    for protocol in ALL_PROTOCOLS:
        record = records[protocol.value]
        assert record["schema_version"] == FORMULA_REGISTRY_VERSION
        assert record["protocol"] == protocol.value
        assert record["notation"] == dict(SHARED_NOTATION)
        assert tuple(record["formulas"]) == FORMULA_FIELDS


def test_position_records_export_the_accepted_t020_formula_api() -> None:
    M, Pe, rho = _symbols()
    records = export_formula_registry(M, Pe, rho)
    for protocol in (Protocol.P, Protocol.PV, Protocol.P_THETA, Protocol.PV_THETA):
        moments = position_protocol_stationary_second_moments(protocol, M, Pe, rho)
        formulas = records[protocol.value]["formulas"]
        assert records[protocol.value]["position_regime"] == "stationary"
        assert records[protocol.value]["spatial_class"] == moments.spatial_class
        for field, value in {
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
        }.items():
            assert formulas[field] == _encoded(value)
        assert records[protocol.value]["scope"] == "stationary"
        expected_centered = {
            "C_centered": moments.position_velocity - moments.position_mean * moments.velocity_mean.T,
            "Q_centered": moments.position_orientation - moments.position_mean * moments.orientation_mean.T,
            "Sigma_v": moments.velocity_second - moments.velocity_mean * moments.velocity_mean.T,
            "Sigma_u": moments.orientation_second - moments.orientation_mean * moments.orientation_mean.T,
            "K": moments.velocity_orientation - moments.velocity_mean * moments.orientation_mean.T,
            "raw_MSD": moments.mean_squared_displacement,
            "speed": moments.mean_squared_speed,
            "r_dot_v": moments.mean_position_dot_velocity,
            "centered_variance": moments.centered_spatial_variance,
        }
        for field, value in expected_centered.items():
            assert formulas[field] == _encoded(value)
        assert formulas["D"] is None
        assert formulas["D_eff"] is None
        assert formulas["b"] is None


def test_transport_records_export_the_accepted_t021_formula_api() -> None:
    M, Pe, rho = _symbols()
    records = export_formula_registry(M, Pe, rho)
    for protocol in (Protocol.V, Protocol.THETA, Protocol.V_THETA):
        moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
        formulas = records[protocol.value]["formulas"]
        assert records[protocol.value]["position_regime"] == "transport"
        assert records[protocol.value]["spatial_class"] == moments.spatial_class
        assert records[protocol.value]["raw_msd_class"] == moments.raw_msd_class
        for field, value in {
            "r_bar": moments.asymptotic_position_mean(TIME),
            "v_bar": moments.velocity_mean,
            "u_bar": moments.orientation_mean,
            "R": moments.asymptotic_position_mean(TIME) * moments.asymptotic_position_mean(TIME).T + 2 * moments.diffusion_tensor * TIME,
            "S": moments.velocity_second,
            "C": moments.asymptotic_position_mean(TIME) * moments.velocity_mean.T + moments.position_velocity_centered_limit,
            "Q": moments.asymptotic_position_mean(TIME) * moments.orientation_mean.T + moments.position_orientation_centered_limit,
            "W": moments.velocity_orientation,
            "U": moments.orientation_second,
            "Cov_r": 2 * moments.diffusion_tensor * TIME,
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
            "raw_MSD": sp.trace(moments.asymptotic_position_mean(TIME) * moments.asymptotic_position_mean(TIME).T + 2 * moments.diffusion_tensor * TIME),
            "speed": moments.stationary_mean_squared_speed,
            "r_dot_v": sp.trace(moments.asymptotic_position_mean(TIME) * moments.velocity_mean.T + moments.position_velocity_centered_limit),
            "centered_variance": sp.trace(2 * moments.diffusion_tensor * TIME),
        }.items():
            assert formulas[field] == _encoded(value)
        assert records[protocol.value]["scope"] == "long_time_polynomial"


def test_transport_raw_position_blocks_match_t021_generator_polynomial() -> None:
    M, Pe, rho = _symbols()
    records = export_formula_registry(M, Pe, rho)
    for protocol in (Protocol.V, Protocol.THETA, Protocol.V_THETA):
        vector = nonposition_protocol_second_moments(
            protocol, M, Pe, rho
        ).as_generator_asymptotic_vector(TIME)
        formulas = records[protocol.value]["formulas"]
        expected = {
            "r_bar": vector[1:3, :],
            "R": _symmetric_matrix(vector, 7),
            "C": sp.ImmutableDenseMatrix(
                [[vector[13], vector[14]], [vector[15], vector[16]]]
            ),
            "Q": sp.ImmutableDenseMatrix(
                [[vector[17], vector[18]], [vector[19], vector[20]]]
            ),
        }
        for field, value in expected.items():
            assert formulas[field] == _encoded(value)
