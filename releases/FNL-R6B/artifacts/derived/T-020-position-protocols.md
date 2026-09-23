# T-020 position-containing protocol second moments

**Task result:** PASS

**Contract:** v0.3 (locked)

**Protocols:** `P`, `PV`, `PTheta`, `PVTheta`

**Physical domain:** `M>0`, `Pe>=0`, `rho>0`

## Result

All four protocols that reset position have a unique finite stationary
component-level second-order solution and are therefore
**spatially stationary/localized** for every `rho>0`.  None is classified by
a fitted small diffusion coefficient: its centered spatial covariance
converges to the finite matrix given below.  At `rho=0` the reset generators
reduce exactly to the free process, the stationary spatial law disappears,
and position is diffusive with

```text
D_eff = lim Tr Cov(r)/(4t) = 1 + Pe^2/2.
```

The result contains all means and all raw matrices required by contract
section 4.  No fourth moment or G4 discriminator was derived.

## Exact common solution

Write

```text
e = (1,0)^T,  I = 2x2 identity,
u_bar = E[u],       v_bar = E[v],       r_bar = E[r],
U = E[u u^T],       W = E[v u^T],       S = E[v v^T],
Q = E[r u^T],       C = E[r v^T],       R = E[r r^T].
```

The orientation block is

```text
P, PV:
    u_bar = 0,
    U = I/2.

PTheta, PVTheta:
    u_bar = rho e/(rho+1),
    U = diag((rho+2)/(rho+4), 2/(rho+4)).
```

The velocity and velocity-orientation blocks are

```text
P:
    v_bar = Pe u_bar,
    W = Pe U/(1+M).

PV:
    v_bar = Pe u_bar/(1+M rho),
    W = Pe U/[1+M(1+rho)].

PTheta:
    v_bar = Pe u_bar,
    W = [Pe U + M rho v_bar e^T]/[1+M(1+rho)].

PVTheta:
    v_bar = Pe u_bar/(1+M rho),
    W = Pe U/[1+M(1+rho)].
```

The extra rank-one term for `PTheta` is essential: orientation reset retains
velocity and maps `v u^T` to `v e^T`.  Omitting it would violate the exact
generator equation.

For all four protocols,

```text
r_bar = v_bar/rho,

S = [Pe(W+W^T) + 2I/M] / [2 + M rho 1_{V reset}],
Q = W/(rho+1),
C = [M S + Pe Q]/(1+M rho),
R = (C+C^T)/rho,
Cov(r) = R - r_bar r_bar^T.
```

These formulas specify every Cartesian component.  The derived contract
scalars are

```text
E[|r|^2] = Tr R,
E[|v|^2] = Tr S,
E[r dot v] = Tr C,
Tr Cov(r) = Tr R - |r_bar|^2.
```

They are implemented by
`position_protocol_stationary_second_moments`.  For each protocol, the
resulting 28-entry vector exactly annihilates the T-010 generator matrix.

## Closure and stationarity proof

Between jumps and after applying the indicated deterministic reset maps, the
full hierarchy is triangular:

```text
u_bar' = -u_bar + rho(e-u_bar)                     [Theta reset]
u_bar' = -u_bar                                    [otherwise]

U' = 2I-4U + rho(ee^T-U)                          [Theta reset]
U' = 2I-4U                                         [otherwise]

v_bar' = -(v_bar-Pe u_bar)/M
         - rho v_bar                               [V reset only]

W' = Pe U/M -(1+1/M)W                             [P]
W' = Pe U/M -(1+1/M+rho)W                         [PV, PVTheta]
W' = Pe U/M -(1+1/M)W + rho(v_bar e^T-W)          [PTheta]

S' = -2S/M + Pe(W+W^T)/M + 2I/M^2
     - rho S                                       [V reset only]

r_bar' = v_bar-rho r_bar
Q' = W-(1+rho)Q
C' = S+Pe Q/M-(1/M+rho)C
R' = C+C^T-rho R.
```

On the physical domain, every nonconstant homogeneous decay rate in this
ordering is strictly positive: orientation rates are `1` and `4` (increased
by `rho` under orientation reset), velocity rates include `1/M` and `2/M`,
and every position-containing block includes `rho`.  Thus each upstream
block converges, followed successively by `r_bar`, `Q`, `C`, and `R`.
The displayed stationary point is unique and finite.  Consequently
`Cov(r(t))` converges to `Cov(r)` and all four protocols are localized.

## Mandatory limits

### Complete reset

For `PVTheta`, the component formulas reduce exactly to the accepted T-012
complete-reset solution:

```text
u_bar = rho e/(rho+1),
v_bar = rho Pe e/[(rho+1)(1+M rho)],
r_bar = Pe e/[(rho+1)(1+M rho)].
```

Every mean, raw second matrix, cross matrix, and centered covariance agrees
componentwise with
`complete_reset_stationary_second_moments`.

### Rare reset and free transport

For every position-containing protocol,

```text
lim(rho->0+) E[|v|^2] = 2/M + Pe^2/(1+M),
lim(rho->0+) rho E[|r|^2] = 4 + 2Pe^2
                           = 4 D_eff,free.
```

The stationary position law is singular in this limit, as it must be:
setting `rho=0` in the underlying generator recovers the free diffusive
process rather than a finite stationary position distribution.  The bounded
mean terms do not affect the scaled centered-variance limit.

### Passive underdamped reduction

At `Pe=0`, orientation reset drops out of every translational moment.  There
are exactly two passive translational classes:

```text
P = PTheta:
    S = I/M,
    R = 2I/[rho(1+M rho)],
    E[|r|^2] = 4/[rho(1+M rho)].

PV = PVTheta:
    S = 2I/[M(2+M rho)],
    R = 4I/[rho(1+M rho)(2+M rho)],
    E[|r|^2] = 8/[rho(1+M rho)(2+M rho)].
```

All translational means vanish, so raw and centered position variances agree.

### Singular overdamped position-process limit

Velocity is not retained as a state at `M=0`.  Taking `M->0+` only in the
position output gives the required protocol collapse:

```text
P = PV       in position second moments,
PTheta = PVTheta in position second moments.
```

More explicitly,

```text
R_overdamped = 2I/rho + 2Pe^2 U/[rho(rho+1)],
r_bar = 0                                      [P, PV],
r_bar = Pe e/(rho+1)                           [PTheta, PVTheta],
Cov(r) = R_overdamped-r_bar r_bar^T.
```

Here `U=I/2` without orientation reset and
`U=diag((rho+2)/(rho+4),2/(rho+4))` with orientation reset.  This is the
stationary second-order position law of
`dr=Pe u dt+sqrt(2)dW`; no direct substitution is made in a finite-inertia
velocity formula.

### Frequent reset

The exact leading raw-MSD scalings are

```text
lim(rho->infinity) rho^2 E_P[|r|^2]
    = 4/M + 2Pe^2/(1+M),

lim(rho->infinity) rho^2 E_PTheta[|r|^2]
    = 4/M + 2Pe^2,

lim(rho->infinity) rho^3 E_PV[|r|^2]
    = lim(rho->infinity) rho^3 E_PVTheta[|r|^2]
    = 8/M^2.
```

For `PTheta`, the nonzero mean contributes
`lim rho^2 |r_bar|^2=Pe^2`, so its corresponding centered-variance
coefficient is `4/M+Pe^2`.  The other displayed leading raw and centered
scalings coincide.

## Implementation and exact validation

- `src/phasemap/theory/position_protocols.py` implements the four exact
  stationary solutions and exposes the common 28-entry generator ordering.
- `tests/theory/test_position_protocols.py` checks exact generator residuals,
  complete-reset component equality, centered covariance, rare reset,
  passive reduction, singular overdamped collapse, frequent-reset scalings,
  and rejection of non-position protocols.
- Focused test:
  `.venv\Scripts\python.exe -m pytest tests\theory\test_position_protocols.py -q`
  -> **PASS**, 15 tests.
- Theory suite:
  `.venv\Scripts\python.exe -m pytest tests\theory -q`
  -> **PASS**, 56 tests.
- Full suite:
  `.venv\Scripts\python.exe -m pytest -q`
  -> **PASS**, 260 tests.

One initial overdamped-limit assertion compared unsimplified SymPy matrix
syntax structurally.  Replacing it with entrywise exact simplification
resolved the test; no formula or scientific conclusion changed.

## Assumptions and limitations

- Reset events use the contract's independent Poisson clock and fixed zero
  reset states.
- Matrices are raw moments until the explicitly centered covariance step.
- The formulas require `rho>0`; `rho=0` is handled by the free baseline.
- This task does not classify the three non-position protocols, assert a
  second-order equivalence across the full seven-map output, or select/derive
  any fourth-order or distributional discriminator.
