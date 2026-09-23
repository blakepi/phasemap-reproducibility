import sympy as sp
import pytest

from phasemap.simulation.protocols import Protocol
from phasemap.theory.free_baseline import (
    free_effective_diffusion,
    free_stationary_mean_squared_speed,
)
from phasemap.theory.generator import Symbols, second_order_moment_system
from phasemap.theory.nonposition_protocols import (
    NONPOSITION_PROTOCOLS,
    nonposition_protocol_second_moments,
)


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    M = sp.symbols("M", positive=True, finite=True)
    Pe, rho = sp.symbols("Pe rho", nonnegative=True, finite=True)
    return M, Pe, rho


def _all_zero(matrix: sp.MatrixBase) -> bool:
    return all(sp.simplify(entry) == 0 for entry in matrix)


@pytest.mark.parametrize("protocol", NONPOSITION_PROTOCOLS)
def test_transport_polynomial_satisfies_full_28_state_generator_exactly(
    protocol: Protocol,
) -> None:
    M, Pe, rho = _symbols()
    t = sp.symbols("t", nonnegative=True)
    moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
    vector = moments.as_generator_asymptotic_vector(t)

    symbols = Symbols.create()
    matrix = second_order_moment_system(symbols, protocol).matrix.subs(
        {
            symbols.inertia: M,
            symbols.activity: Pe,
            symbols.reset_rate: rho,
        }
    )
    residual = matrix * vector - vector.diff(t)
    assert _all_zero(residual)
    assert moments.spatial_class == "diffusive"


@pytest.mark.parametrize("protocol", NONPOSITION_PROTOCOLS)
def test_diffusion_matches_independent_green_kubo_resolvent(
    protocol: Protocol,
) -> None:
    """Check D without using the position cross-moment recurrence.

    The centered conditional first moments of z=(v,u) obey z'=Bz.  Integrating
    exp(Bt) times the independently assembled stationary covariance gives the
    zero-frequency Green--Kubo tensor.
    """

    M, Pe, rho = _symbols()
    moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
    alpha = 1 + rho * int(protocol.resets_orientation)
    beta = (1 + M * rho * int(protocol.resets_velocity)) / M
    identity = sp.eye(2)
    zero = sp.zeros(2)
    B = sp.BlockMatrix(
        [
            [-beta * identity, Pe * identity / M],
            [zero, -alpha * identity],
        ]
    ).as_explicit()
    stationary_covariance = sp.BlockMatrix(
        [
            [
                moments.velocity_covariance,
                moments.velocity_orientation_covariance,
            ],
            [
                moments.velocity_orientation_covariance.T,
                moments.orientation_covariance,
            ],
        ]
    ).as_explicit()
    integrated_forward_covariance = -B.inv() * stationary_covariance
    green_kubo = (
        integrated_forward_covariance[:2, :2]
        + integrated_forward_covariance[:2, :2].T
    ) / 2
    assert _all_zero(green_kubo - moments.diffusion_tensor)


@pytest.mark.parametrize("protocol", NONPOSITION_PROTOCOLS)
def test_default_initial_mean_offset_is_independent_first_moment_integral(
    protocol: Protocol,
) -> None:
    M, Pe, rho = _symbols()
    moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
    alpha = 1 + rho * int(protocol.resets_orientation)
    beta = (1 + M * rho * int(protocol.resets_velocity)) / M
    identity = sp.eye(2)
    zero = sp.zeros(2)
    B = sp.BlockMatrix(
        [
            [-beta * identity, Pe * identity / M],
            [zero, -alpha * identity],
        ]
    ).as_explicit()
    initial_deviation = sp.Matrix.vstack(
        -moments.velocity_mean,
        sp.ImmutableDenseMatrix([1, 0]) - moments.orientation_mean,
    )
    integrated_deviation = -B.inv() * initial_deviation
    assert _all_zero(
        integrated_deviation[:2, :] - moments.position_mean_offset
    )


def test_component_symmetry_and_raw_versus_centered_classes() -> None:
    M, Pe, rho = _symbols()
    v = nonposition_protocol_second_moments(Protocol.V, M, Pe, rho)
    theta = nonposition_protocol_second_moments(
        Protocol.THETA, M, Pe, rho
    )
    vtheta = nonposition_protocol_second_moments(
        Protocol.V_THETA, M, Pe, rho
    )
    for moments in (v, theta, vtheta):
        assert moments.diffusion_tensor[0, 1] == 0
        assert moments.diffusion_tensor[1, 0] == 0
        assert moments.position_mean_drift[1] == 0
        assert moments.effective_diffusion == (
            moments.diffusion_tensor[0, 0]
            + moments.diffusion_tensor[1, 1]
        ) / 2
    assert v.position_mean_drift == sp.zeros(2, 1)
    assert v.raw_msd_class == "diffusive"
    expected_conditional = (
        "conditional: ballistic if mean drift is nonzero; "
        "diffusive if mean drift is zero "
        "(centered covariance diffusive in either case)"
    )
    assert theta.raw_msd_class == expected_conditional
    assert vtheta.raw_msd_class == expected_conditional
    assert sp.simplify(
        theta.raw_position_second_quadratic_coefficient[0, 0]
        - (Pe * rho / (rho + 1)) ** 2
    ) == 0
    assert sp.simplify(
        vtheta.raw_position_second_quadratic_coefficient[0, 0]
        - (Pe * rho / ((rho + 1) * (1 + M * rho))) ** 2
    ) == 0


@pytest.mark.parametrize("protocol", (Protocol.THETA, Protocol.V_THETA))
@pytest.mark.parametrize(
    ("activity", "reset_rate"),
    ((0, 1), (1, 0), (0, 0)),
)
def test_zero_drift_endpoints_have_diffusive_raw_msd_class(
    protocol: Protocol,
    activity: int,
    reset_rate: int,
) -> None:
    moments = nonposition_protocol_second_moments(
        protocol, 2, activity, reset_rate
    )
    assert moments.position_mean_drift == sp.zeros(2, 1)
    assert moments.raw_msd_class == "diffusive"


@pytest.mark.parametrize("protocol", (Protocol.THETA, Protocol.V_THETA))
def test_positive_numeric_drift_has_ballistic_raw_msd_class(
    protocol: Protocol,
) -> None:
    moments = nonposition_protocol_second_moments(protocol, 2, 3, 5)
    assert moments.position_mean_drift[0] > 0
    assert moments.raw_msd_class == (
        "ballistic (nonzero mean drift); centered covariance diffusive"
    )


def test_expanded_v_and_theta_diffusion_laws() -> None:
    M, Pe, rho = _symbols()
    v = nonposition_protocol_second_moments(Protocol.V, M, Pe, rho)
    theta = nonposition_protocol_second_moments(
        Protocol.THETA, M, Pe, rho
    )
    expected_v = (
        M * Pe**2 * rho
        + 2 * M * Pe**2
        + 4 * M * rho
        + 4 * M
        + 2 * Pe**2
        + 4
    ) / (
        2
        * (1 + M * rho)
        * (2 + M * rho)
        * (1 + M * (1 + rho))
    )
    expected_theta_x = (
        1
        + Pe**2
        * (5 * rho + 2)
        / ((1 + rho) ** 3 * (rho + 4))
    )
    expected_theta_y = (
        1
        + 2 * Pe**2 / ((1 + rho) * (rho + 4))
    )
    expected_theta_effective = (
        1 + Pe**2 * (2 * rho + 1) / (2 * (1 + rho) ** 3)
    )
    assert sp.simplify(v.diffusion_tensor[0, 0] - expected_v) == 0
    assert sp.simplify(v.diffusion_tensor[1, 1] - expected_v) == 0
    assert sp.simplify(theta.diffusion_tensor[0, 0] - expected_theta_x) == 0
    assert sp.simplify(theta.diffusion_tensor[1, 1] - expected_theta_y) == 0
    assert sp.simplify(
        theta.effective_diffusion - expected_theta_effective
    ) == 0


@pytest.mark.parametrize("protocol", NONPOSITION_PROTOCOLS)
def test_rare_reset_limit_recovers_free_internal_and_transport_laws(
    protocol: Protocol,
) -> None:
    M, Pe, rho = _symbols()
    moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
    identity = sp.eye(2)
    assert _all_zero(
        moments.diffusion_tensor.applyfunc(
            lambda entry: sp.limit(entry, rho, 0, dir="+")
        )
        - free_effective_diffusion(Pe) * identity
    )
    assert sp.simplify(
        sp.limit(
            moments.stationary_mean_squared_speed,
            rho,
            0,
            dir="+",
        )
        - free_stationary_mean_squared_speed(M, Pe)
    ) == 0
    assert _all_zero(
        moments.position_mean_drift.applyfunc(
            lambda entry: sp.limit(entry, rho, 0, dir="+")
        )
    )
    assert _all_zero(
        moments.position_mean_offset.applyfunc(
            lambda entry: sp.limit(entry, rho, 0, dir="+")
        )
        - sp.ImmutableDenseMatrix([Pe, 0])
    )


def test_passive_limit_reduces_to_two_underdamped_transport_classes() -> None:
    M, _, rho = _symbols()
    v = nonposition_protocol_second_moments(Protocol.V, M, 0, rho)
    theta = nonposition_protocol_second_moments(Protocol.THETA, M, 0, rho)
    vtheta = nonposition_protocol_second_moments(
        Protocol.V_THETA, M, 0, rho
    )
    expected_velocity_reset = 2 / ((1 + M * rho) * (2 + M * rho))
    assert _all_zero(
        v.diffusion_tensor - expected_velocity_reset * sp.eye(2)
    )
    assert _all_zero(v.diffusion_tensor - vtheta.diffusion_tensor)
    assert _all_zero(theta.diffusion_tensor - sp.eye(2))
    assert sp.simplify(v.effective_diffusion - expected_velocity_reset) == 0
    assert sp.simplify(theta.effective_diffusion - 1) == 0


def test_singular_overdamped_position_limit_collapses_velocity_reset() -> None:
    M, Pe, rho = _symbols()
    v = nonposition_protocol_second_moments(Protocol.V, M, Pe, rho)
    theta = nonposition_protocol_second_moments(
        Protocol.THETA, M, Pe, rho
    )
    vtheta = nonposition_protocol_second_moments(
        Protocol.V_THETA, M, Pe, rho
    )
    expected_free = (1 + Pe**2 / 2) * sp.eye(2)
    assert _all_zero(
        v.diffusion_tensor.applyfunc(
            lambda entry: sp.limit(entry, M, 0, dir="+")
        )
        - expected_free
    )
    theta_limit = theta.diffusion_tensor.applyfunc(
        lambda entry: sp.limit(entry, M, 0, dir="+")
    )
    vtheta_limit = vtheta.diffusion_tensor.applyfunc(
        lambda entry: sp.limit(entry, M, 0, dir="+")
    )
    expected_orientation_reset = (
        sp.eye(2)
        + Pe**2
        * theta.orientation_covariance
        / (1 + rho)
    )
    assert _all_zero(theta_limit - expected_orientation_reset)
    assert _all_zero(vtheta_limit - expected_orientation_reset)


def test_frequent_reset_limits_are_exact() -> None:
    M, Pe, rho = _symbols()
    v = nonposition_protocol_second_moments(Protocol.V, M, Pe, rho)
    theta = nonposition_protocol_second_moments(
        Protocol.THETA, M, Pe, rho
    )
    vtheta = nonposition_protocol_second_moments(
        Protocol.V_THETA, M, Pe, rho
    )
    assert sp.simplify(
        sp.limit(rho**2 * v.effective_diffusion, rho, sp.oo)
        - (Pe**2 + 4) / (2 * M**2)
    ) == 0
    assert sp.simplify(
        sp.limit(theta.effective_diffusion, rho, sp.oo) - 1
    ) == 0
    assert sp.simplify(
        sp.limit(rho**2 * vtheta.effective_diffusion, rho, sp.oo)
        - 2 / M**2
    ) == 0
    assert sp.simplify(
        sp.limit(theta.position_mean_drift[0], rho, sp.oo) - Pe
    ) == 0
    assert sp.simplify(
        sp.limit(rho * vtheta.position_mean_drift[0], rho, sp.oo)
        - Pe / M
    ) == 0


@pytest.mark.parametrize(
    "protocol",
    (Protocol.P, Protocol.PV, Protocol.P_THETA, Protocol.PV_THETA),
)
def test_position_protocols_are_rejected(protocol: Protocol) -> None:
    with pytest.raises(ValueError, match="resets position"):
        nonposition_protocol_second_moments(protocol, 1, 1, 1)
