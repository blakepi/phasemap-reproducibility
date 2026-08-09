# T-012 complete-reset analytic baseline

## Result

Under locked contract v0.3, the `PVTheta` map resets
`(r,v,theta)` to `(0,0,0)` at Poisson rate `rho`. The exact stationary
component-level second-order output was implemented in
`src/phasemap/theory/complete_reset_baseline.py`. It solves the same 28-entry
generator state as T-010 and retains the anisotropy and nonzero means caused
by resetting orientation to the positive x axis.

The closest source is Patel and Shee, *Controlling inertial active Brownian
motion via stochastic resetting*, arXiv:2602.21134v1. Its retrieved v1 TeX
source was checked directly on 22 July 2026:
<https://arxiv.org/abs/2602.21134>.

## Analytic route

Complete resetting gives the renewal/final-value identity

```text
E_rho[f]_stationary = rho * Laplace(E_free[f])(s=rho).
```

Equivalently, the stationary vector annihilates the T-010 `PVTheta` moment
matrix. The implementation uses the latter component hierarchy. With
Cartesian matrix indices and `I` the 2x2 identity,

```text
E[u]  = (rho/(rho+1), 0)
E[v]  = (rho*Pe/((rho+1)(1+M*rho)), 0)
E[r]  = (Pe/((rho+1)(1+M*rho)), 0)

E[uu^T] = diag((rho+2)/(rho+4), 2/(rho+4))
E[vu^T] = Pe E[uu^T] / (1+M(1+rho))
E[ru^T] = E[vu^T] / (rho+1)
E[vv^T] = {Pe(E[vu^T]+E[uv^T]) + 2 I/M} / (2+M*rho)
E[rv^T] = {M E[vv^T] + Pe E[ru^T]} / (1+M*rho)
E[rr^T] = {E[rv^T]+E[vr^T]} / rho.
```

The centered spatial covariance is computed as
`E[rr^T]-E[r]E[r]^T`; raw MSD is not substituted for centered variance.

## Exact source reproduction

Taking traces gives the source's main-text Eqs. 5 and 7 exactly:

```text
E[|v|^2] = 2/(2+M*rho) * [2/M + Pe^2/(1+M(1+rho))]

E[|r|^2] = 2/[rho(1+M*rho)(2+M*rho)]
             * [4 + Pe^2(2+2M+3M*rho)/((rho+1)(1+M+M*rho))].
```

Symbolic discrepancies between these source forms and the component solution
simplify exactly to zero. The full 28-entry stationary vector also gives an
exact zero residual under the T-010 `PVTheta` generator matrix.

## Selected higher-order baseline convention

This task reproduces one narrow source convention, not the deferred G4
discriminator. The selected quantity is the source's **raw radial** passive
position excess kurtosis

```text
K = E[|r|^4] / (2 E[|r|^2]^2) - 1,  with Pe=0.
```

The restriction to `Pe=0` is deliberate: the spatial mean is then exactly
zero, so the raw source normalization is unambiguous despite fixed-orientation
resetting. The source passive fourth moment reduces exactly to

```text
E[|r|^4] = 256[12+5M*rho(5+2M*rho)]
            / {rho^2(1+M*rho)^2(2+M*rho)^2(3+M*rho)(4+M*rho)},
```

and therefore reproduces its Eq. 13,

```text
K = 19 + 54/(3+M*rho) - 144/(4+M*rho).
```

No active fourth-order atlas or G4 claim was derived.

## Rare/frequent-reset checks

All limits below were checked by exact symbolic limits:

- `rho -> 0+`: `E[|v|^2] -> 2/M + Pe^2/(1+M)`.
- `rho -> 0+`: `rho E[|r|^2] -> 4(1+Pe^2/2)`, the free centered-diffusion coefficient relation.
- `rho -> 0+`, passive: `K -> 1`.
- `rho -> infinity`: `rho E[|v|^2] -> 4/M^2`.
- `rho -> infinity`: `rho^3 E[|r|^2] -> 8/M^2`.
- `rho -> infinity`, passive: `K -> 19`.

## Validation

- `.venv\Scripts\python.exe -m pytest tests\theory\test_complete_reset_baseline.py -q`: **PASS**, 6 tests.
- `.venv\Scripts\python.exe -m pytest tests\theory -q`: **PASS**, 41 tests.
- `.venv\Scripts\python.exe -m pytest -q`: **PASS**, 102 tests. A transient
  cross-suite module-name collision from concurrent S-011 work was resolved by
  the root renaming the S-011 test before this final default-suite run; T-012
  did not modify the S-011-owned file.

## Acceptance and limitations

- Second moments match closest source: **PASS**.
- Selected higher-order baseline convention reproduced: **PASS**.
- Rare/frequent reset checks pass: **PASS**.
- Contract version: **0.3**, unchanged.
- Physical domain: `M>0`, `Pe>=0`, `rho>0`; `rho=0` is a limiting free process without a stationary position law.
- No failed analytic route occurred; the G2 failure stop was not triggered.
