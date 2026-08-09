import numpy as np
import pytest

from phasemap.common.model import State
from phasemap.simulation.protocols import (
    ALL_PROTOCOLS,
    PROTOCOL_REGISTRY,
    Protocol,
    ResetMap,
    apply_reset,
)


def test_registry_contains_exactly_seven_protocols() -> None:
    assert len(ALL_PROTOCOLS) == 7
    assert {p.value for p in ALL_PROTOCOLS} == {
        "P", "V", "Theta", "PV", "PTheta", "VTheta", "PVTheta"
    }
    assert set(PROTOCOL_REGISTRY) == set(ALL_PROTOCOLS)


def test_registry_encodes_the_contract_reset_components() -> None:
    assert PROTOCOL_REGISTRY == {
        Protocol.P: ResetMap(resets_position=True),
        Protocol.V: ResetMap(resets_velocity=True),
        Protocol.THETA: ResetMap(resets_orientation=True),
        Protocol.PV: ResetMap(
            resets_position=True, resets_velocity=True
        ),
        Protocol.P_THETA: ResetMap(
            resets_position=True, resets_orientation=True
        ),
        Protocol.V_THETA: ResetMap(
            resets_velocity=True, resets_orientation=True
        ),
        Protocol.PV_THETA: ResetMap(
            resets_position=True, resets_velocity=True, resets_orientation=True
        ),
    }


def test_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        PROTOCOL_REGISTRY[Protocol.P] = ResetMap()


def test_reset_rejects_non_protocol_inputs() -> None:
    state = State(np.array([1.0, -2.0]), np.array([3.0, -4.0]), 0.7)
    with pytest.raises(TypeError, match="protocol must be a Protocol"):
        apply_reset(state, "P")  # type: ignore[arg-type]


@pytest.mark.parametrize("protocol", ALL_PROTOCOLS)
def test_reset_map_changes_exactly_selected_components(protocol: Protocol) -> None:
    state = State(np.array([1.0, -2.0]), np.array([3.0, -4.0]), 0.7)
    out = apply_reset(state, protocol)

    np.testing.assert_array_equal(
        out.position, np.zeros(2) if protocol.resets_position else state.position
    )
    np.testing.assert_array_equal(
        out.velocity, np.zeros(2) if protocol.resets_velocity else state.velocity
    )
    assert out.orientation == (0.0 if protocol.resets_orientation else state.orientation)

    # The map must not mutate its input.
    np.testing.assert_array_equal(state.position, [1.0, -2.0])
    np.testing.assert_array_equal(state.velocity, [3.0, -4.0])
    assert state.orientation == 0.7
