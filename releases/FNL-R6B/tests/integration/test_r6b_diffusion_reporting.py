"""Exact checks for the explicit R6B diffusion-gap and thermal-floor reporting."""
import sympy as sp

from phasemap.simulation.protocols import Protocol
from phasemap.theory.nonposition_protocols import nonposition_protocol_second_moments


def test_displayed_diffusion_gap_is_exact_and_positive():
    M, Pe, rho = sp.symbols('M Pe rho', positive=True)
    v = nonposition_protocol_second_moments(Protocol.V, M, Pe, rho)
    vt = nonposition_protocol_second_moments(Protocol.V_THETA, M, Pe, rho)
    polynomial = (M**2*(rho**4+4*rho**3+4*rho**2+rho)
                  + M*(2*rho**3+7*rho**2+4*rho)+rho**2+3*rho+1)
    displayed = Pe**2*rho*polynomial/(2*(1+rho)**3*(1+M*rho)**3*(1+M*(1+rho)))
    assert sp.factor(v.effective_diffusion-vt.effective_diffusion-displayed) == 0
    assert all(c > 0 for c in sp.Poly(polynomial, M, rho).coeffs())
    assert displayed.is_positive is True


def test_displayed_thermal_floor_matches_exact_passive_tensor():
    M, rho = sp.symbols('M rho', positive=True)
    for protocol in (Protocol.V, Protocol.V_THETA, Protocol.THETA):
        passive = nonposition_protocol_second_moments(protocol, M, sp.S.Zero, rho)
        floor = 1 if protocol == Protocol.THETA else 2/((1+M*rho)*(2+M*rho))
        assert (passive.diffusion_tensor-floor*sp.eye(2)).applyfunc(sp.factor) == sp.zeros(2)
