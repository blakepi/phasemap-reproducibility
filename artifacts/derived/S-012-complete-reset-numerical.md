# S-012 complete-reset numerical reproduction

**Task result:** PASS (deterministic replacement validated; stochastic pilot remains design-only)

## Locked route

Plan `S-012-complete-reset-regenerative-primary-v1` fixes an independent
regenerative terminal-age Euler--Maruyama reproduction of the stationary
`PVTheta` law. The active and passive cases are
`(M,Pe,rho)=(4/5,6/5,1)` and `(4/5,0,1)`. Every trajectory begins at the
complete-reset state and evolves freely to one iid age `A~Exp(rho)`. The
fine step is `1/512`; the paired coarse step is `1/256`, constructed only by
merging consecutive fine intervals and summing their Brownian increments.

The plan contains 20 primary configurations: direct analytic-reference and
paired fine/coarse comparisons for eight active observables, plus both
comparisons for passive raw MSD and passive raw-radial excess kurtosis `K`.
Passive raw `E[|r|^4]` is supporting only. The primary tier uses
`q=2.5758293035`, normalized floor `0.005`, relative margin `0.01`, and the
registered characteristic scale for every row. A direct row uses
`B_disc=abs(fine-coarse delta)+q*paired_SE`; a paired row uses `B_disc=0`.

One design-only pilot of `N0=8192` new trajectories per case may project one
disjoint confirmatory batch. Confirmation is allowed only if every one of the
20 projections is valid and no larger than `N_cap=262144` per case. The plan
forbids polling, top-ups, retries, pilot reuse, parameter tuning, and tier or
margin changes.

## Immutable execution and provenance

- Frozen plan file SHA-256:
  `d37bfc7d930adbad66453e4a14bab087300b4b156e35d725e2dc9ce0654c8fba`.
- Frozen semantic SHA-256:
  `32822df90a3b4c1c0fb25aa515e1494550dcefa8491b7f3b9136509408bfd566`.
- Clean implementation/source commit:
  `5ab40d124f712d91ad2bbeb351fb765e99cb1759`.
- Pilot seed: `20260722301`; count: `8192` per case.
- Immutable pilot-attempt SHA-256:
  `5515f298e7a09a8a65fb53fcd41342f61bc53b0c7fb57d0776c5381a6619c48f`.
- Immutable pilot output:
  `artifacts/raw/S-012-complete-reset-regenerative-primary-v1-pilot.json`.
- Pilot output SHA-256:
  `a0e5f4ff609dc585c49408c962cadf56b625295a9a252fe1b2ab5ccb6b5bf05b`.
- No technical-failure receipt, confirm-attempt receipt, or confirmatory
  output exists.

The built-in exact-clock `PVTheta` event prerequisite passed before the pilot
attempt was reserved. The raw output records contract and registry versions,
the complete source manifest, execution environment, parameters, resolutions,
sampling policy, seeds and stream codes, analytic references, all estimates
and uncertainty fields, and hashes of every age and terminal-state array.
Mean sampled ages were `1.019901246339069` (active) and
`1.0134583915278157` (passive), consistent with the locked unit-rate age law.

## Pilot result

All ten paired fine/coarse rows were **validated** and eligible in isolation.
All ten direct analytic-reference rows were **unresolved**; none was
contradicted. The direct-row projections were:

| Direct configuration | Delta | SE | B_disc | epsilon | Projection denominator | Projected count | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| active `u_x` | -0.00262124 | 0.00663531 | 5.91e-17 | 0.00887298 | 0.00625174 | 61,228 | eligible alone |
| active `v_x` | -0.00137123 | 0.0112341 | 0.000540845 | 0.00864892 | 0.00673685 | 151,143 | eligible alone |
| active `r_x` | 0.0130745 | 0.0119461 | 0.000235389 | 0.00878598 | -0.00452391 | n/a | nonpositive |
| active `uu_xx` | 0.00801399 | 0.00384211 | 3.91e-17 | 0.009 | 0.000986006 | 825,285 | above cap |
| active `uu_yy` | -0.00801399 | 0.00384211 | 3.90e-17 | 0.006 | -0.00201399 | n/a | nonpositive |
| active mean-squared speed | 0.0271259 | 0.0282236 | 0.00344067 | 0.0327198 | 0.00215320 | 9,338,553 | above cap |
| active raw MSD | 0.170108 | 0.0788750 | 0.000436185 | 0.0336996 | -0.136844 | n/a | nonpositive |
| active centered spatial variance | 0.161479 | 0.0757732 | 0.000563545 | 0.0320330 | -0.130009 | n/a | nonpositive |
| passive raw MSD | 0.0118904 | 0.0466025 | 0.000218239 | 0.0238095 | 0.0117009 | 862,189 | above cap |
| passive raw-radial `K` | -0.232566 | 0.193080 | 0.00197641 | 0.0481579 | -0.186385 | n/a | nonpositive |

The paired projections were all eligible and small: active `u_x=1`,
`v_x=1`, `r_x=1`, `uu_xx=1`, `uu_yy=1`, mean-squared speed `=5`, raw MSD
`=3`, centered spatial variance `=3`; passive raw MSD `=2` and passive `K=13`.
The supporting passive raw fourth moment was `20.3465885169186` with
trajectory-mean SE `1.7186314480030405`; it was not used for gating or
projection.

Five direct rows have nonpositive projection denominators, and three other
direct rows project above the cap. Because the locked joint rule requires all
20 rows to be eligible before taking their maximum,
`confirmation_eligible=false` and `N_target_global=null`.

## Classification and stop

This result is an **unresolved sampling/design blockade**, not a technical
failure and not a scientific contradiction. The paired results show that the
fixed fine/coarse discretization is adequate at the pilot points, but the
direct-reference evidence cannot be confirmed under the frozen margins and
compute cap.

The confirmatory seed `20260722401` was not entered. No confirmation, top-up,
retry, alternate output, tier change, or post hoc parameter/margin change is
allowed. The pilot may be used only as design evidence for a separately
preregistered replacement route and may never enter that route's primary
estimate or interval.

Independent post-pilot reviews recomputed all 20 denominators and projections,
verified the attempt/pilot hashes, source commit, manifest, row envelopes, and
classifications, and agreed that confirmation is prohibited. The production
authentication routine validated the locked plan/source fields, all gating
rows, and the projection before stopping at the expected
`pilot is not eligible for confirmation` condition.

One non-causal audit limitation was found after the stop: the supporting-only
raw-`r4` paired mean differs from `fine_mean-coarse_mean` by
`1.47278e-15`, an ordinary floating-point reduction-order difference just
outside the executor's unused `1e-15` absolute authentication tolerance. The
stored supporting estimates and SEs are finite, this field is non-gating, and
it does not enter any envelope, projection, or classification. Because the
pilot is already ineligible, the later supporting-only authentication branch
is unreachable and no source change or rerun is authorized. A replacement
route must avoid exact algebraic consistency assumptions across independently
reduced floating-point means.

## Approved deterministic replacement

On 2026-07-23 the user directed, `Approve the preferred deterministic S-012
replacement route.` The result-free plan
`experiments/S-012-complete-reset-moment-quadrature-primary-v1.json` replaces
the blocked stochastic gate-closing route without changing, reclassifying, or
reading any pilot estimate into the new calculation.

The replacement hand-codes the complete 28-state Itô moment ODE from the
locked SDE and applies exponential-age regenerative quadrature through an
augmented deterministic linear system. It uses the fixed `PVTheta` reset state,
four predeclared numerical cells formed by decimal precisions `50/80` and
scaled tail horizons `rho*T=64/80`, and the contract's absolute deterministic
tolerance `1e-12`. All 28 raw second-order components, nine derived/centered
observables, invariants, stationary residuals, passive cross-closure checks,
and fixed rare-, frequent-, and overdamped-limit trends are gating.

The passive calculation uses a separately hand-derived ten-state closure for
`S=|r|^2`, `P=r dot v`, `Q=|v|^2`, and their fourth-order products. Both raw
`E[|r|^4]` and raw-radial excess kurtosis `K` are gating in every passive
plan case; the former pilot's supporting-only `r4` estimate is explicitly
excluded. The numerical module may not import the T-010 generator builder,
T-012 formulas, either stochastic S-012 production module, or the S-011
propagator. T-012 is used only by the runner as the independent exact
reference.

The plan fixes sixteen exact-rational parameter cases, including active and
passive reset-rate sequences, the `M=1` and `M=2` checks, and the finite
`M=1/2,1/4,1/8` overdamped-support sequence. Ensemble sizes, seeds,
stochastic margins, polling, and top-ups are not applicable. Execution is
permitted only once from a clean committed implementation and must atomically
create the distinct canonical output named in the plan.

## Historical stochastic validation record

Before execution, the implementation passed independent review, 22 focused
S-012 tests, the complete 229-test repository suite, task-graph validation,
validation-registry validation, and `scripts/validate_pack.py`. The exact
result-free validation command was:

```text
.venv\Scripts\python.exe experiments\run_s012_complete_reset_regenerative.py validate experiments\S-012-complete-reset-regenerative-primary-v1.json
```

The one and only pilot command was:

```text
.venv\Scripts\python.exe experiments\run_s012_complete_reset_regenerative.py pilot experiments\S-012-complete-reset-regenerative-primary-v1.json
```

## Deterministic replacement outcome

The result-free plan was frozen and pushed in commit
`3332da5a08cdb518f9bc1deeba96f43c34499d80`. The corrected implementation
passed two independent pre-execution audits, 13 focused tests, the complete
242-test repository suite, task-graph validation, registry validation, and
`scripts/validate_pack.py`. It was then frozen and pushed in clean source
commit `3c56be2b1a43bc77d7c531bd130348729c8bc2b3`.

The canonical command was invoked exactly once from that clean commit. It
returned `validated` and atomically created only
`artifacts/raw/S-012-complete-reset-moment-quadrature-primary-v1.json`.
Its external byte SHA-256 is
`c51b401ba83cb3947e9b533eb9c00b052238699d5c1ed2511b4112371a5510c5`;
the independently recomputed canonical payload SHA-256 is
`d4884631b858eac93c23de77f1b7fcb731e40aadb396f6841321eeb8196424fb`.

All sixteen exact-rational cases and all four precision/tail cells were
present. Independent post-execution recomputation matched all 937 gating
decisions: 448 raw second-order rows, 144 derived-observable rows, 224
invariant rows, 90 passive fourth-order rows, 72 passive cross-closure cells,
22 stationary-residual routes, and three limit trends. Every decision was
validated; none was unresolved or contradicted.

The largest raw 28-state error was `1.426609032873699954e-25`; the largest
derived-observable error was `2.852063321906204888e-25`. The largest overall
cell/reference error was the passive raw fourth moment at
`3.438233877354135587e-22`, and the largest passive `K` error was
`6.749185294247181757e-23`. The maximum arithmetic-precision difference was
`6.316128170734220061e-49`, the maximum tail-horizon difference was
`3.438233275453004516e-22`, the largest stationary residual was
`8.329942287961986982e-23`, and passive cross-closure differences were
exactly zero. All are below the locked absolute tolerance `1e-12`.

The rare-reset, frequent-reset, and finite-inertia overdamped-support
discrepancies decreased strictly along their preregistered sequences. Both
independent post-execution audits confirmed the artifact and payload hashes,
all ten source-manifest hashes, all 132 augmented/resolvent/initial-state
hashes, plan/source identity, contract and registry metadata, exact
classification aggregation, and isolation from the stochastic pilot and
forbidden production imports.

## Disposition

S-012 is accepted through the approved deterministic pivot. The earlier
stochastic pilot remains design-only, and its confirmation path remains
permanently prohibited. The deterministic evidence closes S-012's dependency
edge and advances G2 to the independent V-010 baseline audit; it does not by
itself close G2.
