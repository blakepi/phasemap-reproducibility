"""Symbolic backward generator and second-order closure for contract v0.3.

For a smooth observable f(x,y,vx,vy,theta), the between-reset backward
generator is

  L0 f = v . grad_r f - (v-Pe*u)/M . grad_v f
         + (1/M^2) Delta_v f + d_theta^2 f.

A Poisson reset protocol S adds rho [f(R_S X)-f(X)].
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import sympy as sp

from phasemap.simulation.protocols import Protocol


@dataclass(frozen=True, slots=True)
class Symbols:
    x: sp.Symbol
    y: sp.Symbol
    vx: sp.Symbol
    vy: sp.Symbol
    theta: sp.Symbol
    inertia: sp.Symbol
    activity: sp.Symbol
    reset_rate: sp.Symbol

    @classmethod
    def create(cls) -> "Symbols":
        x, y, vx, vy, theta = sp.symbols("x y vx vy theta", real=True)
        inertia = sp.symbols("M", positive=True, finite=True)
        activity, reset_rate = sp.symbols("Pe rho", nonnegative=True, finite=True)
        return cls(x, y, vx, vy, theta, inertia, activity, reset_rate)


@dataclass(frozen=True, slots=True)
class ResetMap:
    """Full deterministic image of one contract reset map."""

    x: sp.Expr
    y: sp.Expr
    vx: sp.Expr
    vy: sp.Expr
    theta: sp.Expr

    def substitution(self, symbols: Symbols) -> dict[sp.Symbol, sp.Expr]:
        """Return a simultaneous substitution for applying this map."""

        return {
            symbols.x: self.x,
            symbols.y: self.y,
            symbols.vx: self.vx,
            symbols.vy: self.vy,
            symbols.theta: self.theta,
        }


@dataclass(frozen=True, slots=True)
class SecondOrderMomentSystem:
    """Exact linear system for the closed 28-coordinate moment frame.

    If ``m[i] = E[observables[i]]``, then ``d m / dt = matrix * m``.
    The state includes the constant observable because deterministic resets
    can add affine terms, for example orientation reset sends ``cos(theta)``
    to one.  The stored coordinates are deliberately redundant: physical
    states satisfy ``one = 1`` and ``uu_xx + uu_yy = 1``.
    """

    names: tuple[str, ...]
    observables: tuple[sp.Expr, ...]
    matrix: sp.ImmutableDenseMatrix

    @property
    def physical_trace_constraint(self) -> sp.ImmutableDenseMatrix:
        """Return the row encoding ``one - uu_xx - uu_yy = 0``."""

        row = sp.MutableDenseMatrix.zeros(1, len(self.names))
        row[0, self.names.index("one")] = 1
        row[0, self.names.index("uu_xx")] = -1
        row[0, self.names.index("uu_yy")] = -1
        return sp.ImmutableDenseMatrix(row)

    def physical_trace_residual(
        self,
        moment_state: Mapping[str, object] | Sequence[object],
    ) -> sp.Expr:
        """Return ``one - uu_xx - uu_yy`` for an ordered or named state."""

        values = _ordered_moment_state(self.names, moment_state)
        return sp.simplify(
            values[self.names.index("one")]
            - values[self.names.index("uu_xx")]
            - values[self.names.index("uu_yy")]
        )

    def require_physical_state(
        self,
        moment_state: Mapping[str, object] | Sequence[object],
    ) -> tuple[sp.Expr, ...]:
        """Return an admissible state, or fail closed on nonphysical input.

        Admissibility is exact: the constant coordinate must be one and the
        orientation second moment must have unit trace.  A symbolic residual
        that cannot be proved to vanish is rejected rather than tolerated.
        """

        values = _ordered_moment_state(self.names, moment_state)
        constant_residual = sp.simplify(
            values[self.names.index("one")] - sp.Integer(1)
        )
        trace_residual = sp.simplify(
            values[self.names.index("uu_xx")]
            + values[self.names.index("uu_yy")]
            - sp.Integer(1)
        )
        if constant_residual != 0 or trace_residual != 0:
            raise NonphysicalMomentStateError(
                "moment state is outside the physical invariant manifold: "
                f"one-1={constant_residual}, Tr(U)-1={trace_residual}"
            )
        return values


class MomentClosureError(ValueError):
    """Raised when a generator image leaves the declared moment state."""


class NonphysicalMomentStateError(ValueError):
    """Raised when a moment vector violates its exact physical constraints."""


def _ordered_moment_state(
    names: tuple[str, ...],
    moment_state: Mapping[str, object] | Sequence[object],
) -> tuple[sp.Expr, ...]:
    """Normalize a named or ordered state without accepting partial input."""

    if isinstance(moment_state, Mapping):
        missing = tuple(name for name in names if name not in moment_state)
        extras = tuple(name for name in moment_state if name not in names)
        if missing or extras:
            raise NonphysicalMomentStateError(
                f"moment-state keys disagree with the frame; "
                f"missing={missing}, extras={extras}"
            )
        values = tuple(sp.sympify(moment_state[name]) for name in names)
    else:
        if isinstance(moment_state, (str, bytes)):
            raise NonphysicalMomentStateError("moment state must be numeric or symbolic")
        values = tuple(sp.sympify(value) for value in moment_state)
        if len(values) != len(names):
            raise NonphysicalMomentStateError(
                f"moment state has {len(values)} entries; expected {len(names)}"
            )
    return values


def reset_map(symbols: Symbols, protocol: Protocol) -> ResetMap:
    """Return the common full-state representation of a contract reset map."""

    zero = sp.Integer(0)
    return ResetMap(
        x=zero if protocol.resets_position else symbols.x,
        y=zero if protocol.resets_position else symbols.y,
        vx=zero if protocol.resets_velocity else symbols.vx,
        vy=zero if protocol.resets_velocity else symbols.vy,
        theta=zero if protocol.resets_orientation else symbols.theta,
    )


def reset_substitution(symbols: Symbols, protocol: Protocol) -> dict[sp.Symbol, sp.Expr]:
    """Return the simultaneous substitution for ``protocol``.

    This compatibility helper is backed by :func:`reset_map`, so generator
    and moment-system code use the same complete reset-map representation.
    """

    return reset_map(symbols, protocol).substitution(symbols)


def _backward_generator_expression(
    observable: sp.Expr,
    symbols: Symbols,
    protocol: Protocol | None = None,
) -> sp.Expr:
    s = symbols
    drift = (
        s.vx * sp.diff(observable, s.x)
        + s.vy * sp.diff(observable, s.y)
        - (s.vx - s.activity * sp.cos(s.theta)) / s.inertia
        * sp.diff(observable, s.vx)
        - (s.vy - s.activity * sp.sin(s.theta)) / s.inertia
        * sp.diff(observable, s.vy)
    )
    diffusion = (
        sp.diff(observable, s.vx, 2) / s.inertia**2
        + sp.diff(observable, s.vy, 2) / s.inertia**2
        + sp.diff(observable, s.theta, 2)
    )
    jump = sp.Integer(0)
    if protocol is not None:
        reset_value = observable.subs(reset_substitution(s, protocol), simultaneous=True)
        jump = s.reset_rate * (reset_value - observable)
    return drift + diffusion + jump


def backward_generator(
    observable: sp.Expr,
    symbols: Symbols,
    protocol: Protocol | None = None,
) -> sp.Expr:
    """Return the simplified symbolic backward generator acting on ``observable``."""

    return sp.simplify(_backward_generator_expression(observable, symbols, protocol))


def second_order_observables(symbols: Symbols) -> Mapping[str, sp.Expr]:
    """Return the ordered 28-entry frame required by contract section 4.

    Symmetric matrices retain three stored components, and the four components
    of each nonsymmetric cross-moment matrix are retained.  The orientation
    entries obey ``uu_xx + uu_yy = one`` on physical states, so these 28
    stored coordinates are a redundant frame rather than an independent
    basis.  Scalar observables such as ``E[|r|^2]`` are exact linear
    combinations of the raw state and therefore do not enlarge the closure.
    """

    s = symbols
    c, q = sp.cos(s.theta), sp.sin(s.theta)
    entries = {
        "one": sp.Integer(1),
        "r_x": s.x,
        "r_y": s.y,
        "v_x": s.vx,
        "v_y": s.vy,
        "u_x": c,
        "u_y": q,
        "rr_xx": s.x**2,
        "rr_xy": s.x * s.y,
        "rr_yy": s.y**2,
        "vv_xx": s.vx**2,
        "vv_xy": s.vx * s.vy,
        "vv_yy": s.vy**2,
        "rv_xx": s.x * s.vx,
        "rv_xy": s.x * s.vy,
        "rv_yx": s.y * s.vx,
        "rv_yy": s.y * s.vy,
        "ru_xx": s.x * c,
        "ru_xy": s.x * q,
        "ru_yx": s.y * c,
        "ru_yy": s.y * q,
        "vu_xx": s.vx * c,
        "vu_xy": s.vx * q,
        "vu_yx": s.vy * c,
        "vu_yy": s.vy * q,
        "uu_xx": c**2,
        "uu_xy": c * q,
        "uu_yy": q**2,
    }
    return MappingProxyType(entries)


def _algebraic_polynomial(expression: sp.Expr, symbols: Symbols) -> sp.Poly:
    """Represent first/second orientation harmonics as polynomials in u."""

    ux, uy = sp.symbols("_u_x _u_y", real=True)
    expanded = sp.expand_trig(expression)
    algebraic = sp.expand(
        expanded.xreplace(
            {
                sp.cos(symbols.theta): ux,
                sp.sin(symbols.theta): uy,
            }
        )
    )
    variables = (symbols.x, symbols.y, symbols.vx, symbols.vy, ux, uy)
    return sp.Poly(algebraic, *variables, domain="EX")


def second_order_moment_system(
    symbols: Symbols,
    protocol: Protocol | None = None,
) -> SecondOrderMomentSystem:
    """Build the exact closed linear moment system for one reset protocol.

    ``protocol=None`` returns the between-reset/free system.  Construction is
    fail-closed: an undeclared monomial raises :class:`MomentClosureError`
    rather than being discarded or silently approximated.
    """

    state = second_order_observables(symbols)
    names = tuple(state)
    observables = tuple(state.values())
    monomial_to_column: dict[tuple[int, ...], int] = {}
    for column, observable in enumerate(observables):
        terms = _algebraic_polynomial(observable, symbols).terms()
        if len(terms) != 1 or terms[0][1] != 1:
            raise MomentClosureError(f"invalid frame observable {names[column]!r}")
        monomial_to_column[terms[0][0]] = column

    matrix = sp.MutableDenseMatrix.zeros(len(observables), len(observables))
    for row, observable in enumerate(observables):
        # Use the uncollapsed differential and jump terms here.  Simplifying
        # their sum can apply u_x**2 + u_y**2 = 1 differently depending on
        # whether a reset term is present, producing different (but equivalent)
        # coordinates in the intentionally redundant raw uu state.
        image = _backward_generator_expression(observable, symbols, protocol)
        for monomial, coefficient in _algebraic_polynomial(image, symbols).terms():
            column = monomial_to_column.get(monomial)
            if column is None:
                raise MomentClosureError(
                    f"generator image for {names[row]!r} contains "
                    f"undeclared monomial {monomial}: {image}"
                )
            matrix[row, column] += coefficient

    return SecondOrderMomentSystem(
        names=names,
        observables=observables,
        matrix=sp.ImmutableDenseMatrix(matrix),
    )
