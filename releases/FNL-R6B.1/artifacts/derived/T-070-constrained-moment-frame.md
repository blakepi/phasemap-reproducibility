# T-070 constrained 28-coordinate moment frame

## Disposition

The accepted second-order closure retains its implementation-stable 28 stored
coordinates. They are now described as a redundant coordinate frame, not an
unrestricted independent basis. No accepted generator formula, stationary or
transport formula, protocol classification, restricted identity, or all-pair
distinguishability statement was changed.

## Physical invariant manifold

The stored frame contains the homogeneous constant coordinate `one` and the
three symmetric orientation entries `uu_xx`, `uu_xy`, and `uu_yy`. A physical
moment state satisfies exactly

```text
one = 1
uu_xx + uu_yy = 1
```

Equivalently, the homogeneous coordinate constraint is
`one - uu_xx - uu_yy = 0`. The generator API exposes this constraint and
fails closed when a supplied state does not satisfy the unit constant and
unit orientation trace exactly.

For orientation-reset indicator `eta`, the existing component equations imply

```text
d(Tr(U) - 1)/dt = -rho * eta * (Tr(U) - 1).
```

Thus `P`, `V`, and `PV` preserve the trace residual, while `Theta`, `PTheta`,
`VTheta`, and `PVTheta` restore it exponentially. All seven generators leave
the physical invariant manifold invariant.

## Reconciled rank check

At the outside-review audit point `(M, Pe, rho) = (2, 3, 5)`, exact SymPy
arithmetic gives:

| Protocol | rank | nullity |
|---|---:|---:|
| `P` | 26 | 2 |
| `PTheta` | 27 | 1 |

The different ambient nullities are consistent with preservation versus
restoration of the redundant trace direction and do not alter the accepted
physical formulas.

## Implementation and regression boundary

- `src/phasemap/theory/generator.py` documents the frame, exposes the exact
  trace row, and validates physical states.
- `tests/theory/test_generator.py` locks all-seven preservation/restoration,
  the reconciled ranks/nullities, acceptance of exact physical states, and
  fail-closed rejection of a nonphysical trace.
- `tests/integration/test_g7_publication_contract.py` prevents reintroduction
  of unrestricted-basis wording in the supplement.
- `manuscript/PHASEMAP_TECHNICAL_SUPPLEMENT.md` restricts coordinate-system
  uniqueness to the physical invariant manifold.

## Scientific stop check

The task stayed within constrained-frame Option B. The ordered entries and
matrix construction are unchanged. The all-seven full-record theorem and its
21-pair witness partition are unchanged.
