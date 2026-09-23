"""PHASEMAP pre-publication research scaffold.

This package encodes the locked-candidate model and protocol semantics.  It is
not itself a scientific result: all formulas and numerical outputs still need
G1-G7 validation under the repository architecture.
"""

from .common.model import ModelParams, State
from .simulation.protocols import Protocol, apply_reset

__all__ = ["ModelParams", "State", "Protocol", "apply_reset"]
