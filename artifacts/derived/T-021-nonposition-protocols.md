# T-021 non-position protocol second moments

**Task result:** PASS

**Contract:** v0.3 (locked)

**Protocols:** `V`, `Theta`, `VTheta`

**Physical domain:** `M>0`, `Pe>=0`, `rho>=0`

## Classification

All three protocols are **diffusive in centered spatial covariance**:

```text
Cov(r(t)) = 2 D t + O(1),
D_eff = lim Tr Cov(r(t))/(4t) = Tr(D)/2.
```

The tensor `D` below is finite for the full physical domain.  `V` has zero
stationary velocity mean and a diffusive raw MSD.  `Theta` and `VTheta` have
nonzero stationary velocity means exactly when `Pe*rho>0`; at those parameter
points,

```text
E[r(t)] = v_bar t + b + o(1),
E[r(t)r(t)^T] = v_bar v_bar^T t^2
                + (v_bar b^T + b v_bar^T + 2D)t + O(1).
```

their raw MSD is ballistic even though the centered fluctuations are
diffusive.  At the endpoints `Pe=0` or `rho=0`, their drift vanishes and the
raw MSD is diffusive.  With symbolic nonnegative parameters for which
zero/nonzero cannot be decided, the API reports this classification
conditionally.  This separation is required by contract section 4.

## Exact component-level solution

Write

```text
e = (1,0)^T, I = 2x2 identity,
u_bar = E[u],             v_bar = E[v],
U = E[u u^T],             W = E[v u^T],
S = E[v v^T],
Sigma_u = U-u_bar u_bar^T,
Sigma_v = S-v_bar v_bar^T,
K = W-v_bar u_bar^T.
```

Every displayed internal matrix is diagonal; every omitted `xy` and `yx`
component is exactly zero.

### `V`

With `B=1+M rho` and `L=1+M(1+rho)`,

```text
u_bar = v_bar = 0,                 U = I/2,
W = Pe I/(2L),
S = [Pe(W+W^T)+2I/M]/(2+M rho).
```

### `Theta`

With `a=1+rho`, `L=1+Ma`, and
`U=diag((rho+2)/(rho+4), 2/(rho+4))`,

```text
u_bar = (rho/a)e,
v_bar = Pe u_bar,
W = [Pe U + M rho v_bar e^T]/L,
S = [Pe(W+W^T)+2I/M]/2.
```

The rank-one term in `W` is mandatory because a `Theta` reset retains
velocity and maps `v u^T` to `v e^T`.

### `VTheta`

With `a=1+rho`, `B=1+M rho`, `L=1+M(1+rho)`, and the same `U` as above,

```text
u_bar = (rho/a)e,
v_bar = Pe rho e/(aB),
W = Pe U/L,
S = [Pe(W+W^T)+2I/M]/(2+M rho).
```

Unlike `Theta`, a simultaneous velocity reset maps `v u^T` to zero, so no
rank-one retained-velocity term occurs.

## Exact centered transport law

Let

```text
alpha = 1+rho       for Theta or VTheta,    alpha = 1 for V,
B     = 1+M rho     for V or VTheta,        B = 1 for Theta.
```

Then the complete centered position cross-moment and diffusion laws are

```text
lim Cov(r,u) = Q = K/alpha,
lim Cov(r,v) = C = (M Sigma_v + Pe Q)/B,
D = (C+C^T)/2,
D_eff = Tr(D)/2.
```

These equations specify both Cartesian diffusion coefficients.  Here all
matrices are diagonal, so `D=diag(D_x,D_y)` and `D_eff=(D_x+D_y)/2`.

Useful expanded forms are

```text
D_V,x = D_V,y
      = [M Pe^2 rho + 2M Pe^2 + 4M rho + 4M + 2Pe^2 + 4]
        / [2(1+M rho)(2+M rho)(1+M(1+rho))],

D_Theta,x = 1 + Pe^2(5rho+2)/[(1+rho)^3(rho+4)],
D_Theta,y = 1 + 2Pe^2/[(1+rho)(rho+4)],
D_eff,Theta = 1 + Pe^2(2rho+1)/[2(1+rho)^3].
```

For `VTheta`, the compact component form is more legible than one expanded
rational polynomial:

```text
K_x = Pe(rho+2)/[(rho+4)L] - Pe rho^2/[(1+rho)^2 B],
K_y = 2Pe/[(rho+4)L],
Sigma_v,x = 2[Pe W_x+1/M]/(2+M rho)
            - Pe^2 rho^2/[(1+rho)^2 B^2],
Sigma_v,y = 2[Pe W_y+1/M]/(2+M rho),
D_VTheta,i = [M Sigma_v,i + Pe K_i/(1+rho)]/B.
```

This is an explicit component-level rational law because `W_x`, `W_y`,
`B`, and `L` are given above.

## Raw cross moments and the default-initial mean

For the locked initial state `r(0)=v(0)=0`, `u(0)=e`, the asymptotic mean
offsets are

```text
b_V      = Pe e/(1+M rho),
b_Theta  = Pe[1-M rho(1+rho)] e/(1+rho)^2,
b_VTheta = Pe(1-M rho^2)e/[(1+rho)^2(1+M rho)^2].
```

The entire predeclared position-containing output follows componentwise:

```text
E[r u^T] = (v_bar t+b)u_bar^T + Q + o(1),
E[r v^T] = (v_bar t+b)v_bar^T + C + o(1),
E[r r^T] = (v_bar t+b)(v_bar t+b)^T + 2Dt + O(1).
```

Together with `u_bar`, `v_bar`, `U`, `W`, and `S`, this supplies all 28 raw
components required by the contract, their centered spatial covariance, and
the derived scalars:

```text
E[|v|^2] = Tr(S),
E[r dot v] = Tr(E[r v^T]),
E[|r|^2] = Tr(E[r r^T]).
```

The implementation's 28-entry polynomial vector satisfies
`A m(t)-d m(t)/dt=0` exactly for the T-010 generator of each protocol.

## Mandatory limits

### Rare reset

For every non-position protocol,

```text
lim(rho->0+) v_bar = 0,
lim(rho->0+) b = Pe e,
lim(rho->0+) E[|v|^2] = 2/M + Pe^2/(1+M),
lim(rho->0+) D = (1+Pe^2/2)I.
```

Thus all three maps recover the accepted free inertial-active internal and
position-transport laws.

### Passive underdamped reduction

At `Pe=0`, orientation resetting disappears from translational moments and
there are exactly two classes:

```text
Theta:
    D = I,                D_eff = 1.

V = VTheta:
    D = 2I/[(1+M rho)(2+M rho)],
    D_eff = 2/[(1+M rho)(2+M rho)].
```

### Singular overdamped position-process limit

Velocity is not an independent state at `M=0`.  Taking `M->0+` only in the
position outputs gives

```text
V:
    D -> (1+Pe^2/2)I,

Theta = VTheta:
    D -> I + Pe^2 Sigma_u/(1+rho).
```

Therefore the velocity-reset distinction collapses exactly:
`V` becomes the no-reset overdamped position process, and `VTheta` becomes
the same overdamped map as `Theta`.  No direct `M=0` substitution is made in
a finite-inertia velocity law.

### Frequent reset

The exact leading limits are

```text
lim(rho->infinity) rho^2 D_eff,V
    = (Pe^2+4)/(2M^2),

lim(rho->infinity) D_eff,Theta = 1,
lim(rho->infinity) v_bar,Theta = Pe e,

lim(rho->infinity) rho^2 D_eff,VTheta = 2/M^2,
lim(rho->infinity) rho v_bar,VTheta = (Pe/M)e.
```

The order of limits matters for raw transport: for every fixed finite
`rho>0`, `Theta` and `VTheta` retain a ballistic raw-MSD term whenever
`Pe>0`, while at `Pe=0` or `rho=0` their raw MSD is diffusive.  The
`VTheta` drift coefficient nevertheless vanishes as
`rho->infinity`.

## Independent validation

- `src/phasemap/theory/nonposition_protocols.py` implements the exact
  stationary internal matrices, centered transport tensor, default-initial
  mean offset, and full generator-compatible asymptotic vector.
- `tests/theory/test_nonposition_protocols.py` checks all 28 generator rows
  exactly and independently derives `D` by integrating the centered
  conditional `(v,u)` first-moment semigroup (a zero-frequency Green--Kubo
  block resolvent).  It also independently integrates the first-moment
  transient to verify `b`.
- Focused test:
  `.venv\Scripts\python.exe -m pytest tests\theory\test_nonposition_protocols.py -q`
  -> **PASS**, 29 tests.
- Theory suite:
  `.venv\Scripts\python.exe -m pytest tests\theory -q`
  -> **PASS**, 85 tests.
- Full suite:
  `.venv\Scripts\python.exe -m pytest -q`
  -> **PASS**, 289 tests.

## Assumptions and limitations

- Reset events use the locked independent Poisson clock and deterministic zero
  reset maps.
- The polynomial raw-moment representation is the exact long-time transport
  solution with stationary internal blocks.  The true default-initial
  trajectory contains decaying internal modes and bounded spatial
  corrections; these do not change `b`, `D`, or the classifications.
- `Theta` and `VTheta` are ballistic in raw MSD only when their mean drift is
  nonzero (`Pe*rho>0`); at `Pe=0` or `rho=0` raw and centered transport are
  diffusive.
- No stationary position law is asserted for these protocols.
- No fourth moment, G4 discriminator, simulation path, equivalence claim, or
  scientific-contract change was introduced.
