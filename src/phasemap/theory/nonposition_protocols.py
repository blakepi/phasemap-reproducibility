"""Exact second-order transport for protocols that do not reset position.

The supported maps are ``V``, ``Theta``, and ``VTheta``.  Their internal
velocity-orientation moments have finite stationary limits, while position is
an additive functional of the stationary velocity process.  Consequently the
centered spatial covariance is diffusive even when orientation resetting
produces a nonzero mean velocity and a ballistic raw mean-squared
displacement.

The formulas use the contract-v0.3 default initial state only to fix the
constant offset in the asymptotic position mean.  The stationary internal
moments and diffusion tensor are independent of that initial condition.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from phasemap.simulation.protocols import Protocol


NONPOSITION_PROTOCOLS: tuple[Protocol, ...] = (
    Protocol.V,
    Protocol.THETA,
    Protocol.V_THETA,
)


def _symmetrize(matrix: sp.MatrixBase) -> sp.ImmutableDenseMatrix:
    return sp.ImmutableDenseMatrix((matrix + matrix.T) / 2)


@dataclass(frozen=True, slots=True)
class NonPositionProtocolSecondMoments:
    """Full stationary-internal and long-time spatial second-order output.

    Matrix indices are Cartesian ``(x, y)``.  The raw internal matrices use
    the order in their names, for example ``velocity_orientation[i, j]`` is
    ``E[v_i u_j]``.  Position has no stationary law.  Instead,

    ``E[r(t)] = position_mean_drift*t + position_mean_offset + o(1)``

    and

    ``Cov(r(t)) = 2*diffusion_tensor*t + O(1)``.

    The two centered position cross-moment limits are respectively
    ``lim Cov(r,u)`` and ``lim Cov(r,v)``.
    """

    protocol: Protocol
    position_mean_drift: sp.ImmutableDenseMatrix
    position_mean_offset: sp.ImmutableDenseMatrix
    velocity_mean: sp.ImmutableDenseMatrix
    orientation_mean: sp.ImmutableDenseMatrix
    velocity_second: sp.ImmutableDenseMatrix
    velocity_orientation: sp.ImmutableDenseMatrix
    orientation_second: sp.ImmutableDenseMatrix
    velocity_covariance: sp.ImmutableDenseMatrix
    orientation_covariance: sp.ImmutableDenseMatrix
    velocity_orientation_covariance: sp.ImmutableDenseMatrix
    position_orientation_centered_limit: sp.ImmutableDenseMatrix
    position_velocity_centered_limit: sp.ImmutableDenseMatrix
    diffusion_tensor: sp.ImmutableDenseMatrix

    @property
    def spatial_class(self) -> str:
        """Contract-v0.3 class based on centered spatial covariance."""

        return "diffusive"

    @property
    def raw_msd_class(self) -> str:
        """Long-time raw-MSD class, separated from the centered class.

        A symbolic nonnegative activity or reset rate can equal zero, so the
        resulting drift may be neither provably zero nor provably nonzero.
        That case is reported conditionally rather than being overclassified.
        """

        drift = tuple(sp.simplify(entry) for entry in self.position_mean_drift)
        if all(entry == 0 for entry in drift):
            return "diffusive"
        if any(entry.is_zero is False for entry in drift):
            return "ballistic (nonzero mean drift); centered covariance diffusive"
        return (
            "conditional: ballistic if mean drift is nonzero; "
            "diffusive if mean drift is zero "
            "(centered covariance diffusive in either case)"
        )

    @property
    def effective_diffusion(self) -> sp.Expr:
        """Return ``lim Tr Cov(r(t))/(4t)`` in two dimensions."""

        return sp.trace(self.diffusion_tensor) / 2

    @property
    def stationary_mean_squared_speed(self) -> sp.Expr:
        return sp.trace(self.velocity_second)

    @property
    def raw_position_orientation_linear_coefficient(
        self,
    ) -> sp.ImmutableDenseMatrix:
        """Coefficient of ``t`` in ``E[r(t) u(t)^T]``."""

        return sp.ImmutableDenseMatrix(
            self.position_mean_drift * self.orientation_mean.T
        )

    @property
    def raw_position_velocity_linear_coefficient(
        self,
    ) -> sp.ImmutableDenseMatrix:
        """Coefficient of ``t`` in ``E[r(t) v(t)^T]``."""

        return sp.ImmutableDenseMatrix(
            self.position_mean_drift * self.velocity_mean.T
        )

    @property
    def raw_position_second_quadratic_coefficient(
        self,
    ) -> sp.ImmutableDenseMatrix:
        """Coefficient of ``t^2`` in ``E[r(t) r(t)^T]``."""

        return sp.ImmutableDenseMatrix(
            self.position_mean_drift * self.position_mean_drift.T
        )

    @property
    def raw_position_second_linear_coefficient(
        self,
    ) -> sp.ImmutableDenseMatrix:
        """Coefficient of ``t`` in ``E[r(t) r(t)^T]``."""

        drift = self.position_mean_drift
        offset = self.position_mean_offset
        return sp.ImmutableDenseMatrix(
            drift * offset.T + offset * drift.T + 2 * self.diffusion_tensor
        )

    def asymptotic_position_mean(self, time: sp.Expr) -> sp.ImmutableDenseMatrix:
        """Return the affine long-time position mean (without the ``o(1)``)."""

        t = sp.sympify(time)
        return sp.ImmutableDenseMatrix(
            self.position_mean_drift * t + self.position_mean_offset
        )

    def as_generator_asymptotic_vector(
        self,
        time: sp.Expr,
    ) -> sp.ImmutableDenseMatrix:
        """Return an exact polynomial solution of the 28-state moment ODE.

        Internal moments are placed at stationarity.  The position blocks use
        their exact affine/quadratic transport polynomial.  This is the
        generator-compatible long-time solution; the true default-initial
        solution differs only by decaying internal modes and bounded spatial
        terms.
        """

        t = sp.sympify(time)
        r = self.asymptotic_position_mean(t)
        v = self.velocity_mean
        u = self.orientation_mean
        vv = self.velocity_second
        vu = self.velocity_orientation
        uu = self.orientation_second
        ru = sp.ImmutableDenseMatrix(
            r * u.T + self.position_orientation_centered_limit
        )
        rv = sp.ImmutableDenseMatrix(
            r * v.T + self.position_velocity_centered_limit
        )
        rr = sp.ImmutableDenseMatrix(r * r.T + 2 * self.diffusion_tensor * t)
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


def nonposition_protocol_second_moments(
    protocol: Protocol,
    inertia: sp.Expr,
    activity: sp.Expr,
    reset_rate: sp.Expr,
) -> NonPositionProtocolSecondMoments:
    """Return exact internal moments and spatial transport for one protocol.

    The physical domain is ``M>0``, ``Pe>=0``, and ``rho>=0``.  Position-
    containing protocols raise ``ValueError`` because their spatial law is
    stationary rather than the transport law represented here.
    """

    if protocol not in NONPOSITION_PROTOCOLS:
        raise ValueError(
            f"{protocol.value} resets position; "
            "use the stationary position-protocol solution"
        )

    M = sp.sympify(inertia)
    Pe = sp.sympify(activity)
    rho = sp.sympify(reset_rate)
    zero = sp.Integer(0)
    identity = sp.eye(2)
    e_x = sp.ImmutableDenseMatrix([1, 0])

    resets_orientation = int(protocol.resets_orientation)
    resets_velocity = int(protocol.resets_velocity)
    orientation_decay = 1 + rho * resets_orientation
    velocity_decay = 1 + M * rho * resets_velocity

    if protocol.resets_orientation:
        orientation_mean = sp.ImmutableDenseMatrix(
            [rho / (rho + 1), zero]
        )
        orientation_second = sp.ImmutableDenseMatrix(
            [[(rho + 2) / (rho + 4), zero], [zero, 2 / (rho + 4)]]
        )
    else:
        orientation_mean = sp.ImmutableDenseMatrix([zero, zero])
        orientation_second = sp.ImmutableDenseMatrix(identity / 2)

    velocity_mean = sp.ImmutableDenseMatrix(
        Pe * orientation_mean / velocity_decay
    )

    if protocol is Protocol.THETA:
        # Theta reset retains v and maps v u^T to v e_x^T.
        velocity_orientation = sp.ImmutableDenseMatrix(
            (
                Pe * orientation_second
                + M * rho * velocity_mean * e_x.T
            )
            / (1 + M * (1 + rho))
        )
    else:
        velocity_orientation = sp.ImmutableDenseMatrix(
            Pe * orientation_second / (1 + M * (1 + rho * resets_velocity))
        )

    velocity_second = sp.ImmutableDenseMatrix(
        (
            Pe * (velocity_orientation + velocity_orientation.T)
            + 2 * identity / M
        )
        / (2 + M * rho * resets_velocity)
    )

    orientation_covariance = sp.ImmutableDenseMatrix(
        orientation_second - orientation_mean * orientation_mean.T
    )
    velocity_covariance = sp.ImmutableDenseMatrix(
        velocity_second - velocity_mean * velocity_mean.T
    )
    velocity_orientation_covariance = sp.ImmutableDenseMatrix(
        velocity_orientation - velocity_mean * orientation_mean.T
    )

    position_orientation_centered_limit = sp.ImmutableDenseMatrix(
        velocity_orientation_covariance / orientation_decay
    )
    position_velocity_centered_limit = sp.ImmutableDenseMatrix(
        (
            M * velocity_covariance
            + Pe * position_orientation_centered_limit
        )
        / velocity_decay
    )
    diffusion_tensor = _symmetrize(position_velocity_centered_limit)

    # With the contract's initial u=e_x and v=0, integrate the decaying
    # first-moment modes exactly.  This fixes the O(1) offset in E[r(t)].
    initial_orientation_deviation = e_x - orientation_mean
    integrated_orientation_deviation = (
        initial_orientation_deviation / orientation_decay
    )
    position_mean_offset = sp.ImmutableDenseMatrix(
        (
            -velocity_mean + Pe * integrated_orientation_deviation / M
        )
        * M
        / velocity_decay
    )

    return NonPositionProtocolSecondMoments(
        protocol=protocol,
        position_mean_drift=velocity_mean,
        position_mean_offset=position_mean_offset,
        velocity_mean=velocity_mean,
        orientation_mean=orientation_mean,
        velocity_second=velocity_second,
        velocity_orientation=velocity_orientation,
        orientation_second=orientation_second,
        velocity_covariance=velocity_covariance,
        orientation_covariance=orientation_covariance,
        velocity_orientation_covariance=velocity_orientation_covariance,
        position_orientation_centered_limit=position_orientation_centered_limit,
        position_velocity_centered_limit=position_velocity_centered_limit,
        diffusion_tensor=diffusion_tensor,
    )
