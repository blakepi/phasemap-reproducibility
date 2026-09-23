"""Exact complete-reset baseline for contract v0.3.

The reset map is ``PVTheta``: position, velocity, and orientation are reset
to ``(0, 0, 0)`` at rate ``rho``.  For ``rho > 0``, the steady state is the
renewal mixture of free excursions, so an observable with free Laplace
transform ``F(s)`` has steady expectation ``rho * F(rho)``.

The passive fourth-order helper deliberately reproduces the closest source's
*raw radial* excess-kurtosis convention,

    <|r|^4> / (2 <|r|^2>^2) - 1.

It is exposed only for ``Pe = 0``, where the complete-reset spatial mean is
zero.  This is a baseline convention, not the contract's later G4 target.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True, slots=True)
class CompleteResetSecondMoments:
    """Full stationary component-level second-order output for ``PVTheta``.

    Matrix indices follow Cartesian order ``(x, y)``.  Cross matrices use
    the order in their names, for example ``position_velocity[i, j]`` is
    ``E[r_i v_j]``.  All second moments are raw; centered spatial covariance
    is supplied separately.
    """

    position_mean: sp.ImmutableDenseMatrix
    velocity_mean: sp.ImmutableDenseMatrix
    orientation_mean: sp.ImmutableDenseMatrix
    position_second: sp.ImmutableDenseMatrix
    velocity_second: sp.ImmutableDenseMatrix
    position_velocity: sp.ImmutableDenseMatrix
    position_orientation: sp.ImmutableDenseMatrix
    velocity_orientation: sp.ImmutableDenseMatrix
    orientation_second: sp.ImmutableDenseMatrix
    centered_spatial_covariance: sp.ImmutableDenseMatrix

    @property
    def mean_squared_displacement(self) -> sp.Expr:
        return sp.trace(self.position_second)

    @property
    def mean_squared_speed(self) -> sp.Expr:
        return sp.trace(self.velocity_second)

    @property
    def mean_position_dot_velocity(self) -> sp.Expr:
        return sp.trace(self.position_velocity)

    @property
    def centered_spatial_variance(self) -> sp.Expr:
        return sp.trace(self.centered_spatial_covariance)

    def as_generator_vector(self) -> sp.ImmutableDenseMatrix:
        """Return the 28-entry ordering used by ``second_order_moment_system``."""

        r = self.position_mean
        v = self.velocity_mean
        u = self.orientation_mean
        rr = self.position_second
        vv = self.velocity_second
        rv = self.position_velocity
        ru = self.position_orientation
        vu = self.velocity_orientation
        uu = self.orientation_second
        return sp.ImmutableDenseMatrix(
            [
                1,
                r[0],
                r[1],
                v[0],
                v[1],
                u[0],
                u[1],
                rr[0, 0],
                rr[0, 1],
                rr[1, 1],
                vv[0, 0],
                vv[0, 1],
                vv[1, 1],
                rv[0, 0],
                rv[0, 1],
                rv[1, 0],
                rv[1, 1],
                ru[0, 0],
                ru[0, 1],
                ru[1, 0],
                ru[1, 1],
                vu[0, 0],
                vu[0, 1],
                vu[1, 0],
                vu[1, 1],
                uu[0, 0],
                uu[0, 1],
                uu[1, 1],
            ]
        )


def complete_reset_stationary_second_moments(
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> CompleteResetSecondMoments:
    """Return the exact ``PVTheta`` stationary means and raw second moments.

    The physical domain is ``M > 0``, ``Pe >= 0``, and ``rho > 0``.  The
    expressions solve the full 28-observable generator system rather than
    assuming rotational symmetry, which is broken by resetting ``theta`` to
    zero.
    """

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    zero = sp.Integer(0)

    orientation_mean = sp.ImmutableDenseMatrix([rho / (rho + 1), zero])
    velocity_mean = sp.ImmutableDenseMatrix(
        [rho * Pe / ((rho + 1) * (1 + M * rho)), zero]
    )
    position_mean = sp.ImmutableDenseMatrix(
        [Pe / ((rho + 1) * (1 + M * rho)), zero]
    )

    orientation_second = sp.ImmutableDenseMatrix(
        [[(rho + 2) / (rho + 4), zero], [zero, 2 / (rho + 4)]]
    )
    velocity_orientation = sp.ImmutableDenseMatrix(
        Pe * orientation_second / (1 + M * (1 + rho))
    )
    position_orientation = sp.ImmutableDenseMatrix(
        velocity_orientation / (rho + 1)
    )

    identity = sp.eye(2)
    velocity_second = sp.ImmutableDenseMatrix(
        (
            Pe * (velocity_orientation + velocity_orientation.T)
            + 2 * identity / M
        )
        / (2 + M * rho)
    )
    position_velocity = sp.ImmutableDenseMatrix(
        (M * velocity_second + Pe * position_orientation) / (1 + M * rho)
    )
    position_second = sp.ImmutableDenseMatrix(
        (position_velocity + position_velocity.T) / rho
    )
    centered_spatial_covariance = sp.ImmutableDenseMatrix(
        position_second - position_mean * position_mean.T
    )

    return CompleteResetSecondMoments(
        position_mean=position_mean,
        velocity_mean=velocity_mean,
        orientation_mean=orientation_mean,
        position_second=position_second,
        velocity_second=velocity_second,
        position_velocity=position_velocity,
        position_orientation=position_orientation,
        velocity_orientation=velocity_orientation,
        orientation_second=orientation_second,
        centered_spatial_covariance=centered_spatial_covariance,
    )


def source_complete_reset_stationary_msv(
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> sp.Expr:
    """Closest-source steady mean-squared velocity (main-text Eq. 5)."""

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    return 2 / (2 + M * rho) * (
        2 / M + Pe**2 / (1 + M * (1 + rho))
    )


def source_complete_reset_stationary_msd(
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> sp.Expr:
    """Closest-source steady raw mean-squared displacement (Eq. 7)."""

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    return 2 / (rho * (1 + M * rho) * (2 + M * rho)) * (
        4
        + Pe**2
        * (2 + 2 * M + 3 * M * rho)
        / ((rho + 1) * (1 + M + M * rho))
    )


def passive_complete_reset_position_fourth_moment(
    inertia: sp.Expr,
    reset_rate: sp.Expr,
) -> sp.Expr:
    """Return the source's exact passive steady ``E[|r|^4]`` baseline."""

    M = sp.sympify(inertia)
    rho = sp.sympify(reset_rate)
    Mrho = M * rho
    return 256 * (12 + 5 * Mrho * (5 + 2 * Mrho)) / (
        rho**2
        * (1 + Mrho) ** 2
        * (2 + Mrho) ** 2
        * (3 + Mrho)
        * (4 + Mrho)
    )


def raw_radial_excess_kurtosis(
    radial_fourth_moment: sp.Expr,
    radial_second_moment: sp.Expr,
) -> sp.Expr:
    """Apply the source's 2D raw-radial excess-kurtosis normalization."""

    fourth = sp.sympify(radial_fourth_moment)
    second = sp.sympify(radial_second_moment)
    return sp.factor(fourth / (2 * second**2) - 1)


def source_passive_position_excess_kurtosis(
    inertia: sp.Expr,
    reset_rate: sp.Expr,
) -> sp.Expr:
    """Return the passive position excess kurtosis (main-text Eq. 13)."""

    M = sp.sympify(inertia)
    rho = sp.sympify(reset_rate)
    return 19 + 54 / (3 + M * rho) - 144 / (4 + M * rho)
