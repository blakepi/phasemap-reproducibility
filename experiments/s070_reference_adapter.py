"""Post-simulation analytic-reference adapter for S-070.

The trajectory kernel never imports this module.  The production runner may
load it only after stochastic summaries and hashes are frozen.
"""

from __future__ import annotations

from typing import Any

import sympy as sp

from phasemap.simulation.protocols import Protocol
from phasemap.theory.formula_registry import TIME, export_formula_registry


def _decode(value: object, time: float) -> float | list[list[float]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("formula-registry value must be an encoded object or null")
    kind = value.get("kind")
    substitutions = {TIME: sp.Rational(str(time))}
    if kind == "scalar":
        expression = sp.sympify(value["expression"]).subs(substitutions)
        return float(sp.N(expression, 17))
    if kind == "matrix":
        entries = value.get("entries")
        if not isinstance(entries, list):
            raise TypeError("encoded matrix entries must be a list")
        return [
            [
                float(sp.N(sp.sympify(expression).subs(substitutions), 17))
                for expression in row
            ]
            for row in entries
        ]
    raise ValueError(f"unknown encoded formula kind: {kind!r}")


def reference_fields(
    protocol: str,
    *,
    inertia: float,
    activity: float,
    reset_rate: float,
    time: float,
) -> dict[str, Any]:
    """Evaluate the public formula registry for one post-simulation comparison."""

    parsed_protocol = Protocol(protocol)
    records = export_formula_registry(
        sp.Rational(str(inertia)),
        sp.Rational(str(activity)),
        sp.Rational(str(reset_rate)),
    )
    encoded = records[parsed_protocol.value]["formulas"]
    if not isinstance(encoded, dict):
        raise TypeError("formula registry record has no formula mapping")
    return {name: _decode(value, time) for name, value in encoded.items()}
