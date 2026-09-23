# V-020 second-order classification and equivalence map

**Task result:** CLASSIFICATION PASS; CONTRACTED SECONDARY CLAIM BLOCKED

**Contract:** v0.3 (locked)

## Executive verdict

The exact all-seven stationary/diffusive classification is complete and has
no unresolved or contradicted numerical result. T-020 and T-021 provide the
component-level analytical laws, and the independently implemented S-021
matrix validates all `15,652` T-022 rows, `754` T-012 rows, `91` numeric
gates, and six mandatory-limit groups.

No two distinct protocols are equivalent under the contract's definition of
second-order equivalence. Contract sections 5 and 7.1 require exact equality
of the **full predeclared component-level second-order output set** after
matching parameters and symmetries. For every `M>0`, `rho>0`, and `Pe>=0`,
each distinct protocol pair is separated by at least one required mean,
matrix component, centered quantity, or spatial-growth class.

The narrower identities found below are real and potentially useful, but none
is a full protocol equivalence. Consequently the section 8 secondary claim
cannot proceed as written, and no G4 higher-order target may be selected on
the premise that a contract-full second-order equivalence exists.

## Frozen asymptotic classification

| Protocol | Position reset | Centered spatial class for `rho>0` | Raw-MSD class for `rho>0` | Exact condition |
|---|---:|---|---|---|
| `P` | yes | stationary/localized | bounded | all `M>0`, `Pe>=0` |
| `PV` | yes | stationary/localized | bounded | all `M>0`, `Pe>=0` |
| `PTheta` | yes | stationary/localized | bounded | all `M>0`, `Pe>=0` |
| `PVTheta` | yes | stationary/localized | bounded | all `M>0`, `Pe>=0` |
| `V` | no | diffusive | diffusive | `v_bar=0` identically |
| `Theta` | no | diffusive | ballistic iff `Pe*rho>0`; otherwise diffusive | `v_bar=Pe*rho e_x/(1+rho)` |
| `VTheta` | no | diffusive | ballistic iff `Pe*rho>0`; otherwise diffusive | `v_bar=Pe*rho e_x/[(1+rho)(1+M*rho)]` |

Within the seven-map family and at positive reset rate, resetting position is
necessary and sufficient for finite long-time centered spatial variance.
Without position reset, centered covariance is always diffusive. Raw ballistic
growth occurs exactly for `Theta` or `VTheta` when both activity and reset
rate are nonzero. At `rho=0`, every reset generator vanishes and all seven
maps reduce to the accepted free diffusive process with
`D_eff=1+Pe^2/2`.

Analytical evidence is in T-020 and T-021. Numerical evidence is the complete
S-021 matrix: every protocol validated at every one of the thirteen
exact-rational cases, including passive, resonance, above-resonance, rare- and
frequent-reset support, and the finite-inertia overdamped sequence.

## Why no full second-order equivalence exists

There are 21 distinct protocol pairs.

- Each of the 12 position/non-position pairs is separated by bounded
  localized position moments versus centered diffusive growth.
- If two maps differ in orientation-reset status, then for `rho>0` their
  required `u_bar` and `U` outputs differ, independent of activity.
- Among pairs with the same orientation-reset status but different
  velocity-reset status, `v_bar` differs when `Pe>0` where applicable, and
  the required velocity matrix `S` differs already at `Pe=0`.
- Toggling only position reset leaves the internal `(v,u)` sector unchanged
  but changes the required spatial output from transport to localization.

These witnesses separate every pair even at passive endpoints or special
parameter values where selected traces coincide. Two independent V-020
reviews reached the same conclusion. S-021 numerically validates the exact
formula records used by the proof; it is supporting evidence, not the basis
for declaring exact inequality.

## Exact scope-limited identity ledger

### Internal-sector identities

For all `M>0`, `Pe>=0`, and `rho>0`,

```text
PV       = V       on {v_bar, u_bar, S, W, U} and centered internal blocks,
PTheta   = Theta   on the same internal sector,
PVTheta  = VTheta  on the same internal sector.
```

Position reset does not enter the `(v,u)` generator, so these identities
extend to the full internal stochastic process, not merely its second
moments. S-021 compared 29 flattened internal fields for each pair at all
thirteen cases; every stored algebraic difference was exactly zero. The
spatial outputs remain non-equivalent because the left member is localized
and the right member transports. These pairs cannot yield a higher-order
**internal** discriminator.

### Generic contracted-scalar identities

For `PV` and `PVTheta`, trace normalization `Tr(U)=1` implies exact equality
of

```text
E[|v|^2] = Tr(S),
E[r dot v] = Tr(C),
E[|r|^2] = Tr(R)
```

for every finite physical parameter point. S-021 found byte-identical
algebraic values for all three scalars at all thirteen cases. At
`(M,Pe,rho)=(4/5,6/5,1)`, both protocols give

```text
speed   = 2.1813186813186813...
r_dot_v = 1.1233211233211233...
raw_MSD = 2.2466422466422466...
```

This is not full equivalence. `PVTheta` has nonzero orientation and spatial
means, its component matrices are anisotropic, and

```text
Tr Cov_PV(r) - Tr Cov_PVTheta(r)
  = Pe^2 / [(1+rho)^2 (1+M*rho)^2] > 0
```

for active positive-rate cases.

For `V` and `VTheta`, `Tr(S)` is likewise exactly equal for all parameters,
and S-021 reproduces that identity at all thirteen cases. Nevertheless
`VTheta` has nonzero drift when `Pe*rho>0`, whereas `V` has zero drift, and

```text
D_eff,V - D_eff,VTheta > 0
```

throughout the active positive-rate interior. At the standard active case,
the validated values are `0.6385836385...` and `0.5091914258...`.

These are contracted-observable degeneracies, not protocol equivalences under
contract v0.3.

### Resonant contracted-scalar identity

For `P` and `PTheta`, exact factorization gives

```text
Tr(S_P)-Tr(S_PTheta)
  proportional to Pe^2 (M*rho-1),
```

and the same factor propagates to `Tr(C)` and `Tr(R)`. The scalar triple
therefore coincides exactly when `Pe=0` or `M*rho=1`. S-021 directly samples
the active resonance `M=rho=1`:

| Scalar | `P` | `PTheta` |
|---|---:|---:|
| speed | `2.72` | `2.72` |
| `r_dot_v` | `1.54` | `1.54` |
| raw MSD | `3.08` | `3.08` |
| centered variance | `3.08` | `2.72` |

At the same point, `u_bar,x` is `0` versus `0.5` and `r_bar,x` is `0` versus
`0.6`, so the full output remains distinct.

### Conditional and limiting identities

| Scope | Exact relation | Numerical support | Why it is not full finite-inertia equivalence |
|---|---|---|---|
| Passive `Pe=0` translational sector | `P=PTheta`, `PV=PVTheta`, `V=VTheta` | S-021 endpoint maxima: `0`, `0`, and `1.6571e-37` | orientation outputs still differ |
| Position-process `M->0+` | `P=PV`, `PTheta=PVTheta`, `Theta=VTheta` | all eleven preregistered overdamped trends pass; paired differences decrease | velocity ceases to be a state; limit-only |
| Zero-rate `rho=0` | all seven maps reduce to the free process | rare-reset sequences approach the exact free laws | no positive-rate reset acts; S-021 does not evaluate the endpoint |
| Rare/frequent leading laws | several scaled leading coefficients coincide | all nineteen rare/frequent sequences pass | leading-order or trace equality only |

One additional exact analytic curve makes the `V` and `Theta` diffusion
tensors equal:

```text
rho = 1/2,
Pe^2 = 27 M (M+6)(3M+2)
       / [2(44-9M-80M^2-12M^3)],
0 < M < 0.658170892...
```

`Theta` still has nonzero mean drift and ballistic raw MSD while `V` does
not. S-021 did not sample this tuned curve, so it is recorded as
analytic-only and is not admitted as a numerically witnessed V-020
candidate.

## Blocker and attempted routes

**Blocker:** `BL3-G4-EQUIVALENCE`. Contract section 8 requires a protocol
equivalence at second order to be broken by a higher-order or distributional
observable. The accepted exact G3 result proves that no such full-output pair
exists in the finite positive-rate model.

Two routes were exhausted:

1. Pairwise full-output comparison over all 21 pairs. Every pair has an exact
   required-field or growth-class witness, so no full equivalence exists.
2. Conditional, resonant, passive, overdamped, zero-rate, trace, and tuned
   diffusion searches. They produce only sector, scalar, or limiting
   identities and cannot satisfy sections 5 and 7.1.

The unified all-seven classification, every G2 baseline, T-020, T-021,
T-022, S-020, and S-021 remain accepted and unaffected. The blocker concerns
only the contracted secondary publication claim and the G4 target premise.

## Preferred resolution requiring human approval

The least disruptive scientifically honest option is a narrow contract and
claim amendment:

> Replace “protocol equivalence at second order” in the secondary claim with
> “an exact predeclared contracted-second-order observable degeneracy,” while
> explicitly disclosing that the full component-level outputs are not
> equivalent.

Under that amendment, the generic `PV`/`PVTheta` equality of raw MSD, speed,
and `r_dot_v` would enter B-030 for ranking against other scope-limited
candidates. This document does **not** select a pair or higher-order
observable.

The alternative is to remove the equivalence-breaking secondary claim and
frame any higher-order result as a contrast between already distinct
protocols. Either option changes the locked publication boundary/minimum
paper and therefore requires Blake's explicit choice under the human-gate
rules. Keeping the current wording while treating a trace identity as full
equivalence is not admissible.
