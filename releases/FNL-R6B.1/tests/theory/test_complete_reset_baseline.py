import sympy as sp

from phasemap.simulation.protocols import Protocol
from phasemap.theory.complete_reset_baseline import (
    complete_reset_stationary_second_moments,
    passive_complete_reset_position_fourth_moment,
    raw_radial_excess_kurtosis,
    source_complete_reset_stationary_msd,
    source_complete_reset_stationary_msv,
    source_passive_position_excess_kurtosis,
)
from phasemap.theory.free_baseline import free_effective_diffusion
from phasemap.theory.generator import Symbols, second_order_moment_system


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    M = sp.symbols("M", positive=True)
    Pe = sp.symbols("Pe", nonnegative=True)
    rho = sp.symbols("rho", positive=True)
    return M, Pe, rho


def test_full_second_order_output_solves_pvtheta_generator_exactly() -> None:
    M, Pe, rho = _symbols()
    moments = complete_reset_stationary_second_moments(M, Pe, rho)
    symbols = Symbols.create()
    matrix = second_order_moment_system(symbols, Protocol.PV_THETA).matrix
    residual = matrix.subs(
        {
            symbols.inertia: M,
            symbols.activity: Pe,
            symbols.reset_rate: rho,
        }
    ) * moments.as_generator_vector()
    assert all(sp.simplify(entry) == 0 for entry in residual)


def test_radial_second_moments_match_closest_source_exactly() -> None:
    M, Pe, rho = _symbols()
    moments = complete_reset_stationary_second_moments(M, Pe, rho)
    assert sp.simplify(
        moments.mean_squared_speed
        - source_complete_reset_stationary_msv(M, Pe, rho)
    ) == 0
    assert sp.simplify(
        moments.mean_squared_displacement
        - source_complete_reset_stationary_msd(M, Pe, rho)
    ) == 0


def test_fixed_orientation_reset_mean_and_centering_are_explicit() -> None:
    M, Pe, rho = _symbols()
    moments = complete_reset_stationary_second_moments(M, Pe, rho)
    expected_mean_x = Pe / ((rho + 1) * (1 + M * rho))
    assert sp.simplify(moments.position_mean[0] - expected_mean_x) == 0
    assert moments.position_mean[1] == 0
    assert sp.simplify(
        moments.centered_spatial_variance
        - (moments.mean_squared_displacement - expected_mean_x**2)
    ) == 0


def test_passive_higher_order_source_convention_is_reproduced() -> None:
    M, _, rho = _symbols()
    passive_msd = source_complete_reset_stationary_msd(M, 0, rho)
    passive_r4 = passive_complete_reset_position_fourth_moment(M, rho)
    observed = raw_radial_excess_kurtosis(passive_r4, passive_msd)
    expected = source_passive_position_excess_kurtosis(M, rho)
    assert sp.simplify(observed - expected) == 0


def test_rare_reset_limits_recover_free_transport_coefficients() -> None:
    M, Pe, rho = _symbols()
    msv = source_complete_reset_stationary_msv(M, Pe, rho)
    msd = source_complete_reset_stationary_msd(M, Pe, rho)
    assert sp.simplify(
        sp.limit(msv, rho, 0, dir="+") - (2 / M + Pe**2 / (1 + M))
    ) == 0
    assert sp.simplify(
        sp.limit(rho * msd, rho, 0, dir="+")
        - 4 * free_effective_diffusion(Pe)
    ) == 0
    assert sp.limit(source_passive_position_excess_kurtosis(M, rho), rho, 0) == 1


def test_frequent_reset_limits_match_source_scalings() -> None:
    M, Pe, rho = _symbols()
    msv = source_complete_reset_stationary_msv(M, Pe, rho)
    msd = source_complete_reset_stationary_msd(M, Pe, rho)
    assert sp.simplify(sp.limit(rho * msv, rho, sp.oo) - 4 / M**2) == 0
    assert sp.simplify(sp.limit(rho**3 * msd, rho, sp.oo) - 8 / M**2) == 0
    assert sp.limit(source_passive_position_excess_kurtosis(M, rho), rho, sp.oo) == 19
