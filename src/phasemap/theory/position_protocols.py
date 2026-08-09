"""Exact stationary second moments for the four position-reset protocols.

The supported maps are ``P``, ``PV``, ``PTheta``, and ``PVTheta``.  For
``rho > 0`` every one is spatially localized.  The formulas retain the full
component-level second-order output required by contract v0.3, including the
anisotropy and nonzero mean caused by resetting orientation to zero.

Only the stationary solution is represented here.  At ``rho = 0`` the
stationary position law ceases to exist and the exact free-process formulas
in :mod:`phasemap.theory.free_baseline` apply instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from phasemap.simulation.protocols import Protocol


POSITION_PROTOCOLS: tuple[Protocol, ...] = (
    Protocol.P,
    Protocol.PV,
    Protocol.P_THETA,
    Protocol.PV_THETA,
)


@dataclass(frozen=True, slots=True)
class PositionProtocolSecondMoments:
    """Full stationary component-level second-order output.

    Matrix indices follow Cartesian order ``(x, y)``.  Cross matrices use
    the order in their names, for example ``position_velocity[i, j]`` is
    ``E[r_i v_j]``.  All second moments are raw; centered spatial covariance
    is supplied separately.
    """

    protocol: Protocol
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
    def spatial_class(self) -> str:
        """Return the contract-v0.3 class for ``rho > 0``."""

        return "stationary/localized"

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


def position_protocol_stationary_second_moments(
    protocol: Protocol,
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> PositionProtocolSecondMoments:
    """Return exact stationary moments for a position-containing protocol.

    The physical domain is ``M > 0``, ``Pe >= 0``, and ``rho > 0``.  A
    non-position protocol raises ``ValueError`` because it need not possess a
    stationary spatial law.
    """

    if protocol not in POSITION_PROTOCOLS:
        raise ValueError(
            f"{protocol.value} does not reset position; "
            "no stationary spatial law is asserted"
        )

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    zero = sp.Integer(0)
    identity = sp.eye(2)
    e_x = sp.ImmutableDenseMatrix([1, 0])

    if protocol.resets_orientation:
        orientation_mean = sp.ImmutableDenseMatrix([rho / (rho + 1), zero])
        orientation_second = sp.ImmutableDenseMatrix(
            [[(rho + 2) / (rho + 4), zero], [zero, 2 / (rho + 4)]]
        )
    else:
        orientation_mean = sp.ImmutableDenseMatrix([zero, zero])
        orientation_second = sp.ImmutableDenseMatrix(identity / 2)

    velocity_decay = 1 + M * rho if protocol.resets_velocity else sp.Integer(1)
    velocity_mean = sp.ImmutableDenseMatrix(Pe * orientation_mean / velocity_decay)
    position_mean = sp.ImmutableDenseMatrix(velocity_mean / rho)

    if protocol is Protocol.P_THETA:
        # Theta reset maps v u^T to v e_x^T because velocity is retained.
        velocity_orientation = sp.ImmutableDenseMatrix(
            (
                Pe * orientation_second
                + M * rho * velocity_mean * e_x.T
            )
            / (1 + M * (1 + rho))
        )
    else:
        vu_decay = (
            1 + M * (1 + rho)
            if protocol.resets_velocity
            else 1 + M
        )
        velocity_orientation = sp.ImmutableDenseMatrix(
            Pe * orientation_second / vu_decay
        )

    velocity_second_decay = (
        2 + M * rho if protocol.resets_velocity else sp.Integer(2)
    )
    velocity_second = sp.ImmutableDenseMatrix(
        (
            Pe * (velocity_orientation + velocity_orientation.T)
            + 2 * identity / M
        )
        / velocity_second_decay
    )

    # Position reset sends each of r, r u^T, r v^T, and r r^T to zero.
    position_orientation = sp.ImmutableDenseMatrix(
        velocity_orientation / (rho + 1)
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

    return PositionProtocolSecondMoments(
        protocol=protocol,
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
