"""Fail-closed exact regressions for the three-observable reset-mask decoder."""

from collections import defaultdict

import pytest
import sympy as sp

from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol
from phasemap.theory.observability import (
    ObservabilitySignature,
    decode_reset_mask,
    observability_signature,
)


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    return (
        sp.symbols("M", positive=True),
        sp.symbols("Pe", nonnegative=True),
        sp.symbols("rho", positive=True),
    )


def _trace_levels(
    M: sp.Expr, Pe: sp.Expr, rho: sp.Expr
) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    """Independent theorem-level formulas A, B, and C for Tr(S)."""

    A = (M * Pe**2 + 2 * M + 2) / (M * (M + 1))
    B = 2 * (M * Pe**2 + 2 * M * rho + 2 * M + 2) / (
        M * (M * rho + 2) * (M * rho + M + 1)
    )
    C = (
        M**2 * Pe**2 * rho**2
        + M * Pe**2 * rho
        + M * Pe**2
        + 2 * M * rho**2
        + 4 * M * rho
        + 2 * M
        + 2 * rho
        + 2
    ) / (M * (rho + 1) * (M * rho + M + 1))
    return A, B, C


def _signature_groups(
    M: sp.Expr, Pe: sp.Expr, rho: sp.Expr, *fields: str
) -> set[frozenset[Protocol]]:
    grouped: defaultdict[tuple[object, ...], set[Protocol]] = defaultdict(set)
    for protocol in ALL_PROTOCOLS:
        grouped[observability_signature(protocol, M, Pe, rho).projection(*fields)].add(
            protocol
        )
    return {frozenset(group) for group in grouped.values()}


def test_symbolic_signature_rows_and_all_velocity_margins_are_exact() -> None:
    M, Pe, rho = _symbols()
    A, B, C = _trace_levels(M, Pe, rho)
    expected = {
        Protocol.P: ("stationary/localized", sp.Rational(1, 2), A),
        Protocol.V: ("diffusive", sp.Rational(1, 2), B),
        Protocol.THETA: ("diffusive", (rho + 2) / (rho + 4), C),
        Protocol.PV: ("stationary/localized", sp.Rational(1, 2), B),
        Protocol.P_THETA: ("stationary/localized", (rho + 2) / (rho + 4), C),
        Protocol.V_THETA: ("diffusive", (rho + 2) / (rho + 4), B),
        Protocol.PV_THETA: ("stationary/localized", (rho + 2) / (rho + 4), B),
    }
    for protocol, (spatial_class, u_xx, trace) in expected.items():
        observed = observability_signature(protocol, M, Pe, rho)
        assert observed.spatial_class == spatial_class
        assert sp.simplify(observed.orientation_xx - u_xx) == 0
        assert sp.simplify(observed.kinetic_trace - trace) == 0

    N0 = (
        M**2 * Pe**2 * rho
        + M**2 * Pe**2
        + 2 * M**2 * rho
        + 2 * M**2
        + 3 * M * Pe**2
        + 2 * M * rho
        + 4 * M
        + 2
    )
    N1 = (
        M**2 * Pe**2 * rho**2
        + 3 * M * Pe**2 * rho
        + M * Pe**2
        + 2 * M * rho**2
        + 4 * M * rho
        + 2 * M
        + 2 * rho
        + 2
    )
    margin_zero_orientation = rho * N0 / (
        (M + 1) * (M * rho + 2) * (M * rho + M + 1)
    )
    margin_orientation_reset = rho * N1 / (
        (rho + 1) * (M * rho + 2) * (M * rho + M + 1)
    )
    assert margin_zero_orientation.is_positive is True
    assert margin_orientation_reset.is_positive is True
    assert sp.simplify(A - B - margin_zero_orientation) == 0
    assert sp.simplify(C - B - margin_orientation_reset) == 0
    assert sp.simplify((rho + 2) / (rho + 4) - sp.Rational(1, 2)) > 0


@pytest.mark.parametrize(
    ("M", "Pe", "rho"),
    ((2, 3, 5), (sp.Rational(1, 2), 0, 3), (3, sp.Rational(5, 4), sp.Rational(2, 5))),
)
def test_numeric_decoder_is_injective_and_no_position_diffusion_is_strict(
    M: sp.Expr, Pe: sp.Expr, rho: sp.Expr
) -> None:
    signatures = {
        protocol: observability_signature(protocol, M, Pe, rho)
        for protocol in ALL_PROTOCOLS
    }
    assert len({signature.projection("spatial_class", "orientation_xx", "kinetic_trace") for signature in signatures.values()}) == len(ALL_PROTOCOLS)
    for protocol, signature in signatures.items():
        assert decode_reset_mask(signature, M, Pe, rho) is protocol
        if not protocol.resets_position:
            from phasemap.theory.nonposition_protocols import (
                nonposition_protocol_second_moments,
            )

            diffusion = nonposition_protocol_second_moments(
                protocol, M, Pe, rho
            ).diffusion_tensor
            assert diffusion[0, 0] > 0
            assert diffusion[1, 1] > 0


def test_all_strict_subsignature_equivalence_classes_are_explicit() -> None:
    M, Pe, rho = 2, 3, 5
    assert _signature_groups(M, Pe, rho, "spatial_class") == {
        frozenset((Protocol.P, Protocol.PV, Protocol.P_THETA, Protocol.PV_THETA)),
        frozenset((Protocol.V, Protocol.THETA, Protocol.V_THETA)),
    }
    assert _signature_groups(M, Pe, rho, "orientation_xx") == {
        frozenset((Protocol.P, Protocol.V, Protocol.PV)),
        frozenset((Protocol.THETA, Protocol.P_THETA, Protocol.V_THETA, Protocol.PV_THETA)),
    }
    assert _signature_groups(M, Pe, rho, "kinetic_trace") == {
        frozenset((Protocol.P,)),
        frozenset((Protocol.THETA, Protocol.P_THETA)),
        frozenset((Protocol.V, Protocol.PV, Protocol.V_THETA, Protocol.PV_THETA)),
    }
    assert _signature_groups(M, Pe, rho, "spatial_class", "orientation_xx") == {
        frozenset((Protocol.P, Protocol.PV)),
        frozenset((Protocol.P_THETA, Protocol.PV_THETA)),
        frozenset((Protocol.V,)),
        frozenset((Protocol.THETA, Protocol.V_THETA)),
    }
    assert _signature_groups(M, Pe, rho, "spatial_class", "kinetic_trace") == {
        frozenset((Protocol.P,)),
        frozenset((Protocol.P_THETA,)),
        frozenset((Protocol.PV, Protocol.PV_THETA)),
        frozenset((Protocol.V, Protocol.V_THETA)),
        frozenset((Protocol.THETA,)),
    }
    assert _signature_groups(M, Pe, rho, "orientation_xx", "kinetic_trace") == {
        frozenset((Protocol.P,)),
        frozenset((Protocol.V, Protocol.PV)),
        frozenset((Protocol.THETA, Protocol.P_THETA)),
        frozenset((Protocol.V_THETA, Protocol.PV_THETA)),
    }


@pytest.mark.parametrize(("M", "Pe", "rho"), ((2, 0, 3), (2, 3, sp.Rational(1, 2))))
def test_passive_and_resonant_trace_exceptions_merge_only_the_documented_classes(
    M: sp.Expr, Pe: sp.Expr, rho: sp.Expr
) -> None:
    assert _signature_groups(M, Pe, rho, "kinetic_trace") == {
        frozenset((Protocol.P, Protocol.THETA, Protocol.P_THETA)),
        frozenset((Protocol.V, Protocol.PV, Protocol.V_THETA, Protocol.PV_THETA)),
    }
    assert _signature_groups(M, Pe, rho, "spatial_class", "kinetic_trace") == {
        frozenset((Protocol.P, Protocol.P_THETA)),
        frozenset((Protocol.PV, Protocol.PV_THETA)),
        frozenset((Protocol.V, Protocol.V_THETA)),
        frozenset((Protocol.THETA,)),
    }


def test_decoder_rejects_the_zero_rate_exception_and_nonunique_input() -> None:
    signature = ObservabilitySignature("diffusive", sp.Rational(1, 2), 1)
    with pytest.raises(ValueError, match="rho > 0"):
        decode_reset_mask(signature, 1, 1, 0)
    with pytest.raises(ValueError, match="does not decode a unique"):
        decode_reset_mask(
            ObservabilitySignature("diffusive", sp.Rational(1, 2), 0), 1, 1, 1
        )
