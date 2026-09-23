from dataclasses import astuple

import sympy as sp

from phasemap.theory.free_baseline import (
    free_effective_diffusion,
    free_laplace_scalar_moments,
    free_scalar_moments,
    free_stationary_mean_squared_speed,
    overdamped_mean_squared_displacement,
)


def _symbols() -> tuple[sp.Symbol, sp.Symbol, sp.Symbol]:
    t = sp.symbols("t", nonnegative=True)
    M = sp.symbols("M", positive=True)
    Pe = sp.symbols("Pe", nonnegative=True)
    return t, M, Pe


def test_free_laplace_hierarchy_matches_generator_recursion() -> None:
    s = sp.symbols("s", positive=True)
    _, M, Pe = _symbols()
    moments = free_laplace_scalar_moments(s, M, Pe)
    assert sp.simplify((s + 1 + 1 / M) * moments.velocity_dot_orientation - Pe / (s * M)) == 0
    assert sp.simplify((s + 1) * moments.position_dot_orientation - moments.velocity_dot_orientation) == 0
    assert sp.simplify(
        (s + 2 / M) * moments.mean_squared_speed
        - 2 * Pe * moments.velocity_dot_orientation / M
        - 4 / (s * M**2)
    ) == 0
    assert sp.simplify(
        (s + 1 / M) * moments.mean_position_dot_velocity
        - moments.mean_squared_speed
        - Pe * moments.position_dot_orientation / M
    ) == 0
    assert sp.simplify(s * moments.mean_squared_displacement - 2 * moments.mean_position_dot_velocity) == 0


def test_time_domain_formulas_satisfy_exact_scalar_moment_odes() -> None:
    t, M, Pe = _symbols()
    moments = free_scalar_moments(t, M, Pe)
    vu = moments.velocity_dot_orientation
    ru = moments.position_dot_orientation
    vv = moments.mean_squared_speed
    rv = moments.mean_position_dot_velocity
    rr = moments.mean_squared_displacement
    assert sp.simplify(sp.diff(vu, t) - (Pe / M - (1 + 1 / M) * vu)) == 0
    assert sp.simplify(sp.diff(ru, t) - (vu - ru)) == 0
    assert sp.simplify(sp.diff(vv, t) - (-2 * vv / M + 2 * Pe * vu / M + 4 / M**2)) == 0
    assert sp.simplify(sp.diff(rv, t) - (vv + Pe * ru / M - rv / M)) == 0
    assert sp.simplify(sp.diff(rr, t) - 2 * rv) == 0


def test_zero_initial_conditions_hold_exactly() -> None:
    _, M, Pe = _symbols()
    moments = free_scalar_moments(0, M, Pe)
    values = astuple(moments)
    assert values[0] == 1
    for expression in values[1:]:
        assert sp.simplify(expression) == 0


def test_published_free_stationary_speed_is_reproduced() -> None:
    _, M, Pe = _symbols()
    s = sp.symbols("s", positive=True)
    observed = sp.limit(
        s * free_laplace_scalar_moments(s, M, Pe).mean_squared_speed,
        s,
        0,
        dir="+",
    )
    expected = free_stationary_mean_squared_speed(M, Pe)
    assert sp.simplify(observed - expected) == 0
    assert sp.simplify(expected.subs(Pe, 0) - 2 / M) == 0


def test_passive_reduction_is_underdamped_brownian_motion() -> None:
    t, M, Pe = _symbols()
    moments = free_scalar_moments(t, M, Pe)
    expected_speed = 2 * (1 - sp.exp(-2 * t / M)) / M
    expected_msd = 4 * t - 6 * M + 8 * M * sp.exp(-t / M) - 2 * M * sp.exp(-2 * t / M)
    assert sp.simplify(moments.mean_squared_speed.subs(Pe, 0) - expected_speed) == 0
    assert sp.simplify(moments.mean_squared_displacement.subs(Pe, 0) - expected_msd) == 0


def test_overdamped_position_process_limit_is_exact() -> None:
    t = sp.symbols("t", positive=True)
    M = sp.symbols("M", positive=True)
    Pe = sp.symbols("Pe", nonnegative=True)
    inertial_msd = free_scalar_moments(t, M, Pe).mean_squared_displacement
    overdamped_msd = overdamped_mean_squared_displacement(t, Pe)
    assert sp.simplify(sp.limit(inertial_msd, M, 0, dir="+") - overdamped_msd) == 0
    assert sp.simplify(overdamped_msd.subs(Pe, 0) - 4 * t) == 0


def test_resonant_inertia_one_is_continuous_and_satisfies_odes() -> None:
    t, M, Pe = _symbols()
    generic = free_scalar_moments(t, M, Pe)
    resonant = free_scalar_moments(t, 1, Pe)
    assert sp.simplify(sp.limit(generic.mean_squared_speed, M, 1) - resonant.mean_squared_speed) == 0
    assert sp.simplify(
        sp.limit(generic.mean_squared_displacement, M, 1)
        - resonant.mean_squared_displacement
    ) == 0
    assert sp.simplify(
        sp.diff(resonant.mean_squared_speed, t)
        - (-2 * resonant.mean_squared_speed + 2 * Pe * resonant.velocity_dot_orientation + 4)
    ) == 0


def test_long_time_growth_gives_centered_effective_diffusion() -> None:
    t, M, Pe = _symbols()
    moments = free_scalar_moments(t, M, Pe)
    trace_growth = sp.limit(moments.centered_spatial_variance / t, t, sp.oo)
    assert sp.simplify(trace_growth / 4 - free_effective_diffusion(Pe)) == 0
    assert sp.simplify(free_effective_diffusion(0) - 1) == 0
