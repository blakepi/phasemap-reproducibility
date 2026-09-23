import sympy as sp
import pytest

from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol
from phasemap.theory.generator import (
    NonphysicalMomentStateError,
    Symbols,
    backward_generator,
    reset_map,
    second_order_moment_system,
    second_order_observables,
)


def test_position_generator_under_position_reset() -> None:
    s = Symbols.create()
    assert sp.simplify(backward_generator(s.x, s, Protocol.P) - (s.vx - s.reset_rate*s.x)) == 0
    assert sp.simplify(backward_generator(s.x, s, Protocol.V) - s.vx) == 0


def test_velocity_generator_under_velocity_reset() -> None:
    s = Symbols.create()
    expected = -(s.vx - s.activity*sp.cos(s.theta))/s.inertia - s.reset_rate*s.vx
    assert sp.simplify(backward_generator(s.vx, s, Protocol.V) - expected) == 0


def test_second_velocity_moment_has_correct_diffusion_term() -> None:
    s = Symbols.create()
    expected = (
        -2*s.vx*(s.vx - s.activity*sp.cos(s.theta))/s.inertia
        + 2/s.inertia**2
    )
    assert sp.simplify(backward_generator(s.vx**2, s, None) - expected) == 0


def test_orientation_harmonic_under_orientation_reset() -> None:
    s = Symbols.create()
    observable = sp.cos(s.theta)
    expected = -sp.cos(s.theta) + s.reset_rate*(1-sp.cos(s.theta))
    assert sp.simplify(backward_generator(observable, s, Protocol.THETA) - expected) == 0


@pytest.mark.parametrize(
    ("protocol", "expected"),
    [
        (Protocol.P, (0, 0, "vx", "vy", "theta")),
        (Protocol.V, ("x", "y", 0, 0, "theta")),
        (Protocol.THETA, ("x", "y", "vx", "vy", 0)),
        (Protocol.PV, (0, 0, 0, 0, "theta")),
        (Protocol.P_THETA, (0, 0, "vx", "vy", 0)),
        (Protocol.V_THETA, ("x", "y", 0, 0, 0)),
        (Protocol.PV_THETA, (0, 0, 0, 0, 0)),
    ],
)
def test_common_reset_map_represents_all_seven_protocols(
    protocol: Protocol,
    expected: tuple[int | str, ...],
) -> None:
    s = Symbols.create()
    by_name = {"x": s.x, "y": s.y, "vx": s.vx, "vy": s.vy, "theta": s.theta}
    expected_expressions = tuple(
        sp.Integer(value) if isinstance(value, int) else by_name[value]
        for value in expected
    )
    image = reset_map(s, protocol)
    assert (image.x, image.y, image.vx, image.vy, image.theta) == expected_expressions


def test_second_order_state_matches_contract_component_count() -> None:
    state = second_order_observables(Symbols.create())
    assert len(state) == 28
    assert tuple(state) == (
        "one", "r_x", "r_y", "v_x", "v_y", "u_x", "u_y",
        "rr_xx", "rr_xy", "rr_yy",
        "vv_xx", "vv_xy", "vv_yy",
        "rv_xx", "rv_xy", "rv_yx", "rv_yy",
        "ru_xx", "ru_xy", "ru_yx", "ru_yy",
        "vu_xx", "vu_xy", "vu_yx", "vu_yy",
        "uu_xx", "uu_xy", "uu_yy",
    )


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_all_generators_preserve_or_restore_physical_trace_constraint(
    protocol: Protocol,
) -> None:
    s = Symbols.create()
    system = second_order_moment_system(s, protocol)
    constraint = system.physical_trace_constraint
    expected = (
        -s.reset_rate * constraint
        if protocol.resets_orientation
        else sp.zeros(1, len(system.names))
    )
    assert constraint * system.matrix == expected


def test_reconciled_frame_rank_and_nullity_at_audit_point() -> None:
    s = Symbols.create()
    audit_point = {s.inertia: 2, s.activity: 3, s.reset_rate: 5}
    expected = {
        Protocol.P: (26, 2),
        Protocol.P_THETA: (27, 1),
    }
    for protocol, (rank, nullity) in expected.items():
        matrix = second_order_moment_system(s, protocol).matrix.subs(audit_point)
        assert matrix.rank() == rank
        assert len(matrix.nullspace()) == nullity


def test_physical_moment_state_validation_accepts_exact_trace_constraint() -> None:
    system = second_order_moment_system(Symbols.create(), Protocol.P)
    state = {name: sp.Integer(0) for name in system.names}
    state["one"] = sp.Integer(1)
    state["uu_xx"] = sp.Rational(3, 5)
    state["uu_yy"] = sp.Rational(2, 5)
    accepted = system.require_physical_state(state)
    assert system.physical_trace_residual(accepted) == 0


def test_nonphysical_moment_state_fails_closed() -> None:
    system = second_order_moment_system(Symbols.create(), Protocol.P_THETA)
    state = [sp.Integer(0)] * len(system.names)
    state[system.names.index("one")] = sp.Integer(1)
    state[system.names.index("uu_xx")] = sp.Rational(3, 5)
    state[system.names.index("uu_yy")] = sp.Rational(3, 5)
    with pytest.raises(NonphysicalMomentStateError, match=r"Tr\(U\)-1=1/5"):
        system.require_physical_state(state)


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_all_generator_images_reconstruct_from_closed_second_order_state(
    protocol: Protocol,
) -> None:
    s = Symbols.create()
    system = second_order_moment_system(s, protocol)
    assert system.matrix.shape == (28, 28)
    for row, observable in enumerate(system.observables):
        reconstructed = sum(
            system.matrix[row, column] * basis
            for column, basis in enumerate(system.observables)
        )
        image = backward_generator(observable, s, protocol)
        difference = sp.expand(sp.expand_trig(image - reconstructed))
        assert sp.simplify(difference) == 0


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_zero_reset_rate_limit_recovers_free_moment_system(protocol: Protocol) -> None:
    s = Symbols.create()
    reset_system = second_order_moment_system(s, protocol)
    free_system = second_order_moment_system(s, None)
    assert reset_system.matrix.subs(s.reset_rate, 0) == free_system.matrix


def test_passive_limit_removes_active_velocity_coupling() -> None:
    s = Symbols.create()
    expected_vx = -s.vx / s.inertia
    expected_vx2 = -2 * s.vx**2 / s.inertia + 2 / s.inertia**2
    assert sp.simplify(backward_generator(s.vx, s).subs(s.activity, 0) - expected_vx) == 0
    assert sp.simplify(backward_generator(s.vx**2, s).subs(s.activity, 0) - expected_vx2) == 0
