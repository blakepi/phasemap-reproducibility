"""Exact matched-parameter reset-mask observability signature.

The public three-coordinate signature is deliberately narrower than the
accepted 28-coordinate stationary/asymptotic record.  It is defined only on
the finite-inertia, positive-reset-rate domain, where the long-time spatial
class, ``U_xx``, and ``Tr(S)`` exactly decode the nonempty reset mask.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol

from .nonposition_protocols import nonposition_protocol_second_moments
from .position_protocols import position_protocol_stationary_second_moments


OBSERVABILITY_FIELDS: tuple[str, ...] = (
    "spatial_class",
    "orientation_xx",
    "kinetic_trace",
)
"""Stable field order for the exact three-observable signature."""


@dataclass(frozen=True, slots=True)
class ObservabilitySignature:
    """Long-time observables used by the matched-parameter decoder.

    ``spatial_class`` is a tagged asymptotic observable, not a scalar moment:
    it is ``"stationary/localized"`` for position-reset maps and
    ``"diffusive"`` otherwise.  The two scalar fields are stationary internal
    moments.  The class intentionally does not imply finite-time or noisy-data
    identifiability.
    """

    spatial_class: str
    orientation_xx: sp.Expr
    kinetic_trace: sp.Expr

    def projection(self, *fields: str) -> tuple[object, ...]:
        """Return an ordered strict or full observable projection.

        Rejecting an unknown or repeated field keeps partial-observability
        comparisons explicit rather than silently changing their scope.
        """

        if not fields or any(field not in OBSERVABILITY_FIELDS for field in fields):
            raise ValueError("projection fields must be nonempty observability fields")
        if len(set(fields)) != len(fields):
            raise ValueError("projection fields must not repeat")
        values: dict[str, object] = {
            "spatial_class": self.spatial_class,
            "orientation_xx": self.orientation_xx,
            "kinetic_trace": self.kinetic_trace,
        }
        return tuple(values[field] for field in fields)


def observability_signature(
    protocol: Protocol,
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> ObservabilitySignature:
    """Return the accepted three-observable long-time signature for ``protocol``.

    The formula providers retain their established domains.  The decoder below
    enforces the stricter common theorem domain ``M > 0, Pe >= 0, rho > 0``.
    """

    if protocol not in ALL_PROTOCOLS:
        raise TypeError("protocol must be a canonical nonempty Protocol")
    if protocol.resets_position:
        moments = position_protocol_stationary_second_moments(
            protocol, inertia, activity, reset_rate
        )
    else:
        moments = nonposition_protocol_second_moments(
            protocol, inertia, activity, reset_rate
        )
    return ObservabilitySignature(
        spatial_class=moments.spatial_class,
        orientation_xx=sp.sympify(moments.orientation_second[0, 0]),
        kinetic_trace=sp.sympify(moments.velocity_second.trace()),
    )


def _same_exact(left: sp.Expr, right: sp.Expr) -> bool:
    return sp.simplify(sp.sympify(left) - sp.sympify(right)) == 0


def _require_decoder_domain(
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    """Require a provably physical finite-parameter decoder input.

    Ambiguous SymPy assumptions are rejected rather than allowing a caller to
    apply a theorem outside its stated domain.
    """

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    if M.is_positive is not True:
        raise ValueError("the decoder requires inertia M > 0")
    if Pe.is_nonnegative is not True:
        raise ValueError("the decoder requires activity Pe >= 0")
    if rho.is_positive is not True:
        raise ValueError("the decoder requires reset rate rho > 0")
    return M, Pe, rho


def decode_reset_mask(
    signature: ObservabilitySignature,
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> Protocol:
    """Decode one canonical reset map or fail closed on an invalid signature.

    This exact comparison is intended for symbolic formula records or exact
    numeric values.  It is not an estimator for finite, noisy measurements.
    """

    M, Pe, rho = _require_decoder_domain(inertia, activity, reset_rate)
    matches: list[Protocol] = []
    for protocol in ALL_PROTOCOLS:
        candidate = observability_signature(protocol, M, Pe, rho)
        if (
            candidate.spatial_class == signature.spatial_class
            and _same_exact(candidate.orientation_xx, signature.orientation_xx)
            and _same_exact(candidate.kinetic_trace, signature.kinetic_trace)
        ):
            matches.append(protocol)
    if len(matches) != 1:
        raise ValueError(
            "signature does not decode a unique nonempty reset mask on the "
            "matched-parameter physical domain"
        )
    return matches[0]
