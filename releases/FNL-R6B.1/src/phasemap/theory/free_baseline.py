"""Exact free inertial-active second moments for contract v0.3.

The formulas use the default initial state ``r(0)=v(0)=0, theta(0)=0`` and
zero reset rate.  They solve the scalar triangular subsystem used in Appendix
C of Patel and Shee, arXiv:2602.21134v1.  ``M=1`` is represented by its
continuous extension because the generic partial-fraction form has removable
``M-1`` denominators.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True, slots=True)
class FreeScalarMoments:
    """Exact scalar and mean observables for the free process."""

    orientation_mean_x: sp.Expr
    mean_velocity_x: sp.Expr
    mean_position_x: sp.Expr
    velocity_dot_orientation: sp.Expr
    position_dot_orientation: sp.Expr
    mean_squared_speed: sp.Expr
    mean_position_dot_velocity: sp.Expr
    mean_squared_displacement: sp.Expr
    centered_spatial_variance: sp.Expr


@dataclass(frozen=True, slots=True)
class FreeLaplaceScalarMoments:
    """Laplace-space hierarchy for the five scalar second moments."""

    velocity_dot_orientation: sp.Expr
    position_dot_orientation: sp.Expr
    mean_squared_speed: sp.Expr
    mean_position_dot_velocity: sp.Expr
    mean_squared_displacement: sp.Expr


def _equals_one(expression: sp.Expr) -> bool:
    return sp.simplify(expression - 1) == 0


def free_laplace_scalar_moments(
    laplace_variable: sp.Expr,
    inertia: sp.Expr,
    activity: sp.Expr,
) -> FreeLaplaceScalarMoments:
    """Return the exact zero-initial-state scalar hierarchy in Laplace space.

    The recursion is the direct transform of the backward-generator equations,
    and matches the free hierarchy in Appendix C of the published baseline.
    """

    s = sp.sympify(laplace_variable)
    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    vu = (Pe / M) / (s * (s + 1 + 1 / M))
    ru = vu / (s + 1)
    vv = (2 * Pe * vu / M + 4 / (M**2 * s)) / (s + 2 / M)
    rv = (vv + Pe * ru / M) / (s + 1 / M)
    rr = 2 * rv / s
    return FreeLaplaceScalarMoments(
        velocity_dot_orientation=sp.factor(vu),
        position_dot_orientation=sp.factor(ru),
        mean_squared_speed=sp.factor(vv),
        mean_position_dot_velocity=sp.factor(rv),
        mean_squared_displacement=sp.factor(rr),
    )


def free_scalar_moments(
    time: sp.Expr,
    inertia: sp.Expr,
    activity: sp.Expr,
) -> FreeScalarMoments:
    """Return exact free-process means and scalar second moments.

    Parameters are dimensionless time ``t >= 0``, inertia ``M > 0``, and
    activity ``Pe >= 0``.  The returned displacement moment is raw MSD;
    subtracting the squared mean gives the centered spatial variance.
    """

    requested_time = sp.sympify(time)
    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    t = sp.Dummy("t", nonnegative=True)

    orientation_mean_x = sp.exp(-t)
    vu = Pe / (M + 1) * (1 - sp.exp(-(M + 1) * t / M))
    ru = Pe / (M + 1) * (
        1 - (M + 1) * sp.exp(-t) + M * sp.exp(-(M + 1) * t / M)
    )

    passive_speed = 2 / M * (1 - sp.exp(-2 * t / M))
    passive_msd = 4 * t - 6 * M + 8 * M * sp.exp(-t / M) - 2 * M * sp.exp(-2 * t / M)

    if _equals_one(M):
        mean_velocity_x = Pe * t * sp.exp(-t)
        mean_position_x = Pe * (1 - (1 + t) * sp.exp(-t))
        active_speed = Pe**2 * (
            (1 - sp.exp(-2 * t)) / 2 - t * sp.exp(-2 * t)
        )
        active_msd = Pe**2 * (
            2 * t
            + 2 * t * sp.exp(-t)
            - t * sp.exp(-2 * t)
            - sp.Rational(9, 2)
            + 6 * sp.exp(-t)
            - sp.Rational(3, 2) * sp.exp(-2 * t)
        )
    else:
        mean_velocity_x = Pe * (sp.exp(-t) - sp.exp(-t / M)) / (1 - M)
        mean_position_x = Pe * (
            1 - M - sp.exp(-t) + M * sp.exp(-t / M)
        ) / (1 - M)
        active_speed = Pe**2 / (M + 1) * (
            1
            + (M + 1) * sp.exp(-2 * t / M) / (1 - M)
            - 2 * sp.exp(-(M + 1) * t / M) / (1 - M)
        )
        active_msd = Pe**2 * (
            2 * t
            - (3 * M**2 + 4 * M + 2) / (M + 1)
            - M**2 * sp.exp(-2 * t / M) / (M - 1)
            + 2 * M * (2 * M - 1) * sp.exp(-t / M) / (M - 1)
            + 2 * M * sp.exp(-(M + 1) * t / M) / ((M - 1) * (M + 1))
            - 2 * sp.exp(-t) / (M - 1)
        )

    mean_squared_speed = passive_speed + active_speed
    mean_squared_displacement = passive_msd + active_msd
    mean_position_dot_velocity = sp.diff(mean_squared_displacement, t) / 2
    centered_spatial_variance = mean_squared_displacement - mean_position_x**2

    def at_requested_time(expression: sp.Expr) -> sp.Expr:
        # Preserve the physically meaningful sum of decaying modes.  Global
        # factoring can combine exponentials into forms whose symbolic limits
        # spuriously depend on the sign of ``1/M-1``.
        return sp.expand_mul(expression.subs(t, requested_time))

    return FreeScalarMoments(
        orientation_mean_x=at_requested_time(orientation_mean_x),
        mean_velocity_x=at_requested_time(mean_velocity_x),
        mean_position_x=at_requested_time(mean_position_x),
        velocity_dot_orientation=at_requested_time(vu),
        position_dot_orientation=at_requested_time(ru),
        mean_squared_speed=at_requested_time(mean_squared_speed),
        mean_position_dot_velocity=at_requested_time(mean_position_dot_velocity),
        mean_squared_displacement=at_requested_time(mean_squared_displacement),
        centered_spatial_variance=at_requested_time(centered_spatial_variance),
    )


def free_stationary_mean_squared_speed(
    inertia: sp.Expr,
    activity: sp.Expr,
) -> sp.Expr:
    """Return the published free long-time mean-squared speed."""

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    return 2 / M + Pe**2 / (1 + M)


def overdamped_mean_squared_displacement(time: sp.Expr, activity: sp.Expr) -> sp.Expr:
    """Return the singular ``M -> 0`` position-process raw MSD."""

    t = sp.sympify(time)
    Pe = sp.sympify(activity)
    return 4 * t + 2 * Pe**2 * (t - 1 + sp.exp(-t))


def free_effective_diffusion(activity: sp.Expr) -> sp.Expr:
    """Return ``lim Tr(Cov(r))/(4t)`` for free inertial active motion."""

    Pe = sp.sympify(activity)
    return 1 + Pe**2 / 2
