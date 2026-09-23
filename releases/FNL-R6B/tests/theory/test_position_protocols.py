import sympy as sp
import pytest

from phasemap.simulation.protocols import Protocol
from phasemap.theory.complete_reset_baseline import (
    complete_reset_stationary_second_moments,
)
from phasemap.theory.free_baseline import free_effective_diffusion
from phasemap.theory.generator import Symbols, second_order_moment_system
from phasemap.theory.position_protocols import (
    POSITION_PROTOCOLS,
    position_protocol_stationary_second_moments,
)


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    M = sp.symbols("M", positive=True)
    Pe = sp.symbols("Pe", nonnegative=True)
    rho = sp.symbols("rho", positive=True)
    return M, Pe, rho


@pytest.mark.parametrize("protocol", POSITION_PROTOCOLS)
def test_full_stationary_output_solves_each_generator_exactly(
    protocol: Protocol,
) -> None:
    M, Pe, rho = _symbols()
    moments = position_protocol_stationary_second_moments(protocol, M, Pe, rho)
    symbols = Symbols.create()
    matrix = second_order_moment_system(symbols, protocol).matrix.subs(
        {
            symbols.inertia: M,
            symbols.activity: Pe,
            symbols.reset_rate: rho,
        }
    )
    residual = matrix * moments.as_generator_vector()
    assert all(sp.simplify(entry) == 0 for entry in residual)
    assert moments.spatial_class == "stationary/localized"
    assert sp.simplify(
        moments.centered_spatial_variance
        - (
            moments.mean_squared_displacement
            - (moments.position_mean.T * moments.position_mean)[0]
        )
    ) == 0


def test_pvtheta_reproduces_complete_reset_baseline_componentwise() -> None:
    M, Pe, rho = _symbols()
    observed = position_protocol_stationary_second_moments(
        Protocol.PV_THETA, M, Pe, rho
    )
    expected = complete_reset_stationary_second_moments(M, Pe, rho)
    fields = (
        "position_mean",
        "velocity_mean",
        "orientation_mean",
        "position_second",
        "velocity_second",
        "position_velocity",
        "position_orientation",
        "velocity_orientation",
        "orientation_second",
        "centered_spatial_covariance",
    )
    for field in fields:
        difference = getattr(observed, field) - getattr(expected, field)
        assert all(sp.simplify(entry) == 0 for entry in difference)


@pytest.mark.parametrize("protocol", POSITION_PROTOCOLS)
def test_rare_reset_transport_limit_recovers_free_diffusion(
    protocol: Protocol,
) -> None:
    M, Pe, rho = _symbols()
    moments = position_protocol_stationary_second_moments(protocol, M, Pe, rho)
    assert sp.simplify(
        sp.limit(rho * moments.mean_squared_displacement, rho, 0, dir="+")
        - 4 * free_effective_diffusion(Pe)
    ) == 0
    assert sp.simplify(
        sp.limit(rho * moments.centered_spatial_variance, rho, 0, dir="+")
        - 4 * free_effective_diffusion(Pe)
    ) == 0
    assert sp.simplify(
        sp.limit(moments.mean_squared_speed, rho, 0, dir="+")
        - (2 / M + Pe**2 / (1 + M))
    ) == 0


def test_passive_limit_has_only_p_and_pv_translational_classes() -> None:
    M, _, rho = _symbols()
    passive = {
        protocol: position_protocol_stationary_second_moments(
            protocol, M, 0, rho
        )
        for protocol in POSITION_PROTOCOLS
    }
    assert passive[Protocol.P].as_generator_vector()[1:5, :] == passive[
        Protocol.P_THETA
    ].as_generator_vector()[1:5, :]
    for first, second in (
        (Protocol.P, Protocol.P_THETA),
        (Protocol.PV, Protocol.PV_THETA),
    ):
        for field in (
            "position_mean",
            "velocity_mean",
            "position_second",
            "velocity_second",
            "position_velocity",
        ):
            assert getattr(passive[first], field) == getattr(passive[second], field)

    assert sp.simplify(
        passive[Protocol.P].mean_squared_displacement
        - 4 / (rho * (1 + M * rho))
    ) == 0
    assert sp.simplify(
        passive[Protocol.PV].mean_squared_displacement
        - 8 / (rho * (1 + M * rho) * (2 + M * rho))
    ) == 0


def test_p_pv_velocity_matrix_witness_is_positive_for_all_activity() -> None:
    M, Pe, rho = _symbols()
    p = position_protocol_stationary_second_moments(Protocol.P, M, Pe, rho)
    pv = position_protocol_stationary_second_moments(Protocol.PV, M, Pe, rho)
    expected = rho * (
        M**2 * Pe**2 * rho
        + M**2 * Pe**2
        + 2 * M**2 * rho
        + 2 * M**2
        + 3 * M * Pe**2
        + 2 * M * rho
        + 4 * M
        + 2
    ) / (2 * (M + 1) * (M * rho + 2) * (M * rho + M + 1))

    assert expected.is_positive is True
    for index in range(2):
        assert sp.factor(
            p.velocity_second[index, index]
            - pv.velocity_second[index, index]
            - expected
        ) == 0


def test_singular_overdamped_limit_collapses_velocity_reset_distinction() -> None:
    M, Pe, rho = _symbols()
    moments = {
        protocol: position_protocol_stationary_second_moments(
            protocol, M, Pe, rho
        )
        for protocol in POSITION_PROTOCOLS
    }
    for first, second in (
        (Protocol.P, Protocol.PV),
        (Protocol.P_THETA, Protocol.PV_THETA),
    ):
        for field in ("position_mean", "position_second", "centered_spatial_covariance"):
            difference = getattr(moments[first], field) - getattr(
                moments[second], field
            )
            assert all(
                sp.simplify(sp.limit(entry, M, 0, dir="+")) == 0
                for entry in difference
            )

    expected_isotropic = sp.eye(2) * (
        2 / rho + Pe**2 / (rho * (rho + 1))
    )
    p_limit = moments[Protocol.P].position_second.applyfunc(
        lambda entry: sp.limit(entry, M, 0, dir="+")
    )
    assert all(
        sp.simplify(entry) == 0
        for entry in p_limit - expected_isotropic
    )

    orientation_second = moments[Protocol.P_THETA].orientation_second
    expected_theta_reset = (
        2 * sp.eye(2) / rho
        + 2 * Pe**2 * orientation_second / (rho * (rho + 1))
    )
    ptheta_limit = moments[Protocol.P_THETA].position_second.applyfunc(
        lambda entry: sp.limit(entry, M, 0, dir="+")
    )
    assert all(
        sp.simplify(entry) == 0
        for entry in ptheta_limit - expected_theta_reset
    )


def test_frequent_reset_scalings_separate_velocity_reset_protocols() -> None:
    M, Pe, rho = _symbols()
    p = position_protocol_stationary_second_moments(Protocol.P, M, Pe, rho)
    pv = position_protocol_stationary_second_moments(Protocol.PV, M, Pe, rho)
    ptheta = position_protocol_stationary_second_moments(
        Protocol.P_THETA, M, Pe, rho
    )
    pvtheta = position_protocol_stationary_second_moments(
        Protocol.PV_THETA, M, Pe, rho
    )
    assert sp.simplify(
        sp.limit(rho**2 * p.mean_squared_displacement, rho, sp.oo)
        - (4 / M + 2 * Pe**2 / (1 + M))
    ) == 0
    assert sp.simplify(
        sp.limit(rho**2 * ptheta.mean_squared_displacement, rho, sp.oo)
        - (4 / M + 2 * Pe**2)
    ) == 0
    assert sp.simplify(
        sp.limit(rho**2 * ptheta.centered_spatial_variance, rho, sp.oo)
        - (4 / M + Pe**2)
    ) == 0
    for moments in (pv, pvtheta):
        assert sp.simplify(
            sp.limit(
                rho**3 * moments.mean_squared_displacement,
                rho,
                sp.oo,
            )
            - 8 / M**2
        ) == 0


@pytest.mark.parametrize("protocol", (Protocol.V, Protocol.THETA, Protocol.V_THETA))
def test_non_position_protocols_are_rejected(protocol: Protocol) -> None:
    with pytest.raises(ValueError, match="does not reset position"):
        position_protocol_stationary_second_moments(protocol, 1, 1, 1)
