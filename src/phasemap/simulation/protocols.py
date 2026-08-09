"""Canonical seven reset maps from the PHASEMAP G1 contract candidate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from phasemap.common.model import State


class Protocol(str, Enum):
    P = "P"
    V = "V"
    THETA = "Theta"
    PV = "PV"
    P_THETA = "PTheta"
    V_THETA = "VTheta"
    PV_THETA = "PVTheta"

    @property
    def resets_position(self) -> bool:
        return PROTOCOL_REGISTRY[self].resets_position

    @property
    def resets_velocity(self) -> bool:
        return PROTOCOL_REGISTRY[self].resets_velocity

    @property
    def resets_orientation(self) -> bool:
        return PROTOCOL_REGISTRY[self].resets_orientation


ALL_PROTOCOLS: tuple[Protocol, ...] = tuple(Protocol)


@dataclass(frozen=True, slots=True)
class ResetMap:
    """Contract-defined components set to their fixed zero references."""

    resets_position: bool = False
    resets_velocity: bool = False
    resets_orientation: bool = False


PROTOCOL_REGISTRY: Mapping[Protocol, ResetMap] = MappingProxyType({
    Protocol.P: ResetMap(resets_position=True),
    Protocol.V: ResetMap(resets_velocity=True),
    Protocol.THETA: ResetMap(resets_orientation=True),
    Protocol.PV: ResetMap(resets_position=True, resets_velocity=True),
    Protocol.P_THETA: ResetMap(resets_position=True, resets_orientation=True),
    Protocol.V_THETA: ResetMap(resets_velocity=True, resets_orientation=True),
    Protocol.PV_THETA: ResetMap(
        resets_position=True, resets_velocity=True, resets_orientation=True
    ),
})


def apply_reset(state: State, protocol: Protocol) -> State:
    """Return the fixed-reference post-reset state without mutating ``state``."""

    if not isinstance(protocol, Protocol):
        raise TypeError("protocol must be a Protocol")
    reset_map = PROTOCOL_REGISTRY[protocol]
    out = state.copy()
    if reset_map.resets_position:
        out.position.fill(0.0)
    if reset_map.resets_velocity:
        out.velocity.fill(0.0)
    if reset_map.resets_orientation:
        out.orientation = 0.0
    return out
