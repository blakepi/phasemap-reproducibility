# S-011 free-baseline numerical reproduction

**Task result:** PASS (deterministic replacement validated; stochastic v2 remains design-only)

## Prior calculation preserved as design evidence

The prior free-process calculation used `M=0.8`, `Pe=1.2`, `rho=0`, `t=6.0`,
fine step `0.002`, paired coarse step `0.004`, and a fixed `N=8192` ensemble.
Its base seed was `20260722011`; the final scheduled seed was `20260722022`.
The obsolete configuration is retained as
`experiments/S-011-free-baseline-design-v1.json`; its configuration and source
SHA-256 values are respectively
`f73001aa61300db40044b47b76bb1a34244c882f6088236e57abacb59a2e654b` and
`7f35453c8bd1262c7bc430e03ac10bdb95b11b97f06e58de7b7c11248cda1719`.

The calculation was incorrectly labelled primary. Its configuration omitted
the required compute cap and executable per-observable registry
configurations. It is therefore non-gating design evidence, not a valid
primary run; no primary pass or contradiction is assigned, and it cannot
close G2.

| Observable | Analytic | Fine minus analytic | Fine minus coarse |
|---|---:|---:|---:|
| centered spatial variance | 29.408576 | -0.143662 | -0.000717 |
| raw MSD | 30.819403 | +0.123365 | -0.002433 |
| mean squared speed | 3.299990 | -0.070529 | -0.003409 |
| `E[r dot v]` | 3.422339 | -0.088036 | -0.003176 |
| `E[r_x]` | 1.187782 | +0.107255 | -0.001215 |
| `E[v_x]` | 0.011554 | +0.004274 | +0.000036 |
| `E[r dot u]` | 0.663693 | +0.029984 | +0.000968 |
| `E[v dot u]` | 0.666666 | -0.012363 | -0.000326 |

Fine standard errors were `0.312962`, `0.328999`, `0.034549`, `0.080089`,
`0.041657`, `0.014032`, `0.043068`, and `0.012749`, respectively. Paired
resolution differences were small relative to those standard errors. These
numbers may inform a prospective compute estimate only; they are not used to
alter, extend, or classify the invalid run.

## Corrected preregistration and execution

`experiments/S-011-free-baseline-primary-v2.json` is a separate primary plan
for selected finite-time `rho=0` spot checks only: `E[r dot v]`
and unbiased `Tr Cov(r)` at `t=1.5` and `t=3.0`. It does not claim a
positive-rate `rho -> 0` sequence. It has one design-only pilot (`N0=2048`)
and at most one disjoint confirmatory batch (`N_target`, never
`N_target-N0`), `N_cap=131072`, no polling/top-ups or first-pass stopping,
and paired fine/coarse paths. Each of the eight ordered configurations has an
exact ID, primary evidence tier, analytic reference, registry-derived scale,
comparison kind, and estimator declaration.

The uncertainty methods are explicit and observable-specific:

- Direct `r_dot_v` is a trajectory mean with the trajectory-mean SE
  `sample_sd/sqrt(N)`; its fine/coarse check is the mean and SE of matched
  trajectory-level differences.
- Direct `cov_r_trace` is the unbiased sample-covariance trace with a
  delete-one trajectory jackknife SE; its fine/coarse check is the difference
  of the two unbiased covariance traces with a delete-one matched-pair
  jackknife SE.
- Every discrepancy interval is the point estimate plus or minus
  `q=2.5758293035` times its stated SE. `B_window=0`. For each direct row,
  `B_disc=max(0.01, abs(matching_fine_coarse_delta) +
  q*matching_fine_coarse_standard_error)`; the paired row itself has
  `B_disc=0`, so the same resolution uncertainty is not counted twice.

The discretization estimator is phase-local. Pilot matched pairs estimate
`B_disc,0` only for the fixed sample-size projection. Confirmatory matched
pairs freshly estimate the confirmatory `B_disc` used in the final expanded
interval and classification. No pilot estimate, uncertainty, envelope, row
classification, or trajectory enters the confirmatory estimate or final
classification.

The canonical single-use outputs are
`artifacts/raw/S-011-free-baseline-primary-v2-pilot.json` and
`artifacts/raw/S-011-free-baseline-primary-v2-confirm.json`. Aliases are
rejected. Each path is atomically reserved immediately before stochastic
analysis, cannot be overwritten, and receives either one strictly serialized
success document or one valid failure receipt. The pilot is labeled
`design-only`; its row classifications are diagnostics, not gate evidence.
Confirmation requires the externally supplied exact pilot SHA-256 and
revalidates the complete pilot semantics, projections, and joint maximum
before the confirm path is reserved or confirmatory RNG is entered; this
authentication does not reuse pilot evidence in the final analysis.

Both success outputs record the plan and output identity, contract and
registry versions, source commit, hashes for the contract, registry, schema,
validator, runner, simulator, analytic reference implementation, and plan,
parameters, exact seeds and counts, time-step and validation-time resolution,
pairing policy, evidence tier, estimator, SE method, and interval construction.
Confirmatory `overall` is `validated` only when every row is validated,
`contradicted` when any row is contradicted, and `unresolved` otherwise.

## Pilot outcome and blocker

The plan and executor passed independent review, were committed as
`364859ea4f9432e7391ad860fff855d14ebcdad7`, and the one permitted pilot ran
once with `N0=2048`. Its immutable canonical output is
`artifacts/raw/S-011-free-baseline-primary-v2-pilot.json`, SHA-256
`82f2ab603fbd5d24075b685e7f03efe6c81a2c47006239a3b7bef524d5792dbb`.
The confirmatory output does not exist.

All four paired fine/coarse pilot intervals were contained in their margins,
so the numerical resolution checks were diagnostically validated. The direct
analytic-reference pilot intervals were unresolved, as expected for
design-only evidence. The locked projection produced this outcome:

| Configuration | Denominator | Raw projected target | Contract result |
|---|---:|---:|---|
| `t1.5-rdotv-direct` | -0.0572273 | n/a | nonpositive; unresolved |
| `t1.5-rdotv-fine-coarse` | 0.0134638 | 1 | below estimator minimum 3; unresolved |
| `t1.5-covtrace-direct` | -0.00402796 | n/a | nonpositive; unresolved |
| `t1.5-covtrace-fine-coarse` | 0.0110658 | 2 | below estimator minimum 3; unresolved |
| `t3-rdotv-direct` | 0.00767451 | 2,517,340 | exceeds `N_cap=131072`; unresolved |
| `t3-rdotv-fine-coarse` | 0.0273609 | 1 | below estimator minimum 3; unresolved |
| `t3-covtrace-direct` | 0.0920002 | 72,854 | eligible in isolation |
| `t3-covtrace-fine-coarse` | 0.0481985 | 1 | below estimator minimum 3; unresolved |

Because the preregistered joint rule requires every per-configuration target
to be eligible before taking their maximum, `n_target=null` and
`eligible_for_confirmation=false`. No confirmation, top-up, retry, tier
change, or alternate output is allowed. This is an unresolved baseline
blocker rather than a contradiction: the paired convergence evidence is
sound, but the plan cannot produce gating direct-reference evidence under its
locked margins, estimator minimum, and compute cap.

These spot checks cannot alone establish the full free baseline or G2.
T-010 exact matrix closure and T-011 analytic evidence remain accepted, and
S-012 remains technically ready, but V-010 and the G2 transition remain
blocked until the approved replacement below and S-012 produce reviewable
evidence.

## Approved deterministic replacement

On 2026-07-22 the user directed, `I Approve the preferred deterministic S-011
replacement route.` The result-free plan
`experiments/S-011-free-moment-matrix-primary-v1.json` replaces the blocked
stochastic gate-closing route without changing or reclassifying its pilot.

The replacement constructs the full free 28-state matrix only through T-010,
converts exact rational parameter substitutions once to binary64, and
integrates the moment ODE with a fixed order-18 Taylor action at maximum steps
`1/16` and `1/32`. It compares all nine T-011 scalar/mean outputs, the constant
and orientation-norm identities, and every declared symmetry-forced zero at
seven fixed parameter cases and six fixed times. Every comparison must satisfy
the deterministic absolute tolerance `1e-12`; converged disagreement is BL3
and failed resolution convergence is unresolved. After the finite-inertia
comparisons validate, fine-resolution raw MSD must also approach the exact
overdamped law strictly along the fixed `M=1/2,1/4,1/8` sequence at
`t=1/2,3/2,3`.

This route shares the locked contract, T-010 generator/basis, parameters, and
initial state. It does not call T-011's scalar ODE, Laplace, or closed-form
implementation from the numerical integrator and does not use the stochastic
simulator or pilot trajectories. Ensemble size, seeds, stochastic evidence
tier, polling, and top-ups are not applicable. Execution is permitted only
from a clean committed implementation with the complete provenance declared in
the plan.

## Deterministic replacement outcome

The result-free plan was frozen in commit
`6abd530eaaf4be7f94b99188bc29ac2d4872a740`. The independently reviewed
implementation was frozen and pushed in clean source commit
`8cdfc6138707ca48e98da2357b3e8bc797db0f11`. The canonical plan was then
executed exactly once. It returned `validated` and created only
`artifacts/raw/S-011-free-moment-matrix-primary-v1.json`.

The canonical raw artifact SHA-256 is
`82f6d06b5670c45e7dde772e902bc2fe0bc54dc58537332a4f5656b7cfc47285`.
This line is the external durable hash record required by the frozen plan; the
raw JSON is unchanged after publication.

All seven parameter cases and six times were present. Every one of the 966
predeclared rows validated: nine T-011 observables plus fourteen invariants at
each of 42 case-time records. The largest error or resolution difference was
`7.105427357601002e-14`, for centered spatial variance at
`M=1/4`, `Pe=6/5`, `t=6`; this is below the locked absolute tolerance
`1e-12`. The worst invariant resolution difference was
`1.3322676295501878e-15`.

The fine-resolution raw-MSD discrepancy from the exact overdamped law
decreased strictly along `M=1/2,1/4,1/8` at every declared time:

| Time | `M=1/2` | `M=1/4` | `M=1/8` | Result |
|---:|---:|---:|---:|---|
| `1/2` | 1.92797772213308 | 1.44410028596995 | 0.860626593610074 | pass |
| `3/2` | 3.86026018926396 | 2.07207484445634 | 1.03819033821456 | pass |
| `3` | 4.52693690159720 | 2.24418941166754 | 1.10951617753710 | pass |

Independent post-execution audit recomputed every classification, verified all
eleven source-manifest blobs against the recorded clean commit, confirmed the
canonical hash, and found the numerical and methodological evidence sound.
The deterministic core uses T-010's 28-state generator matrix; the separate
runner evaluates the T-011 reference at 50-digit precision. No stochastic
trajectory, pilot estimate, or stochastic production calculation enters the
replacement result.

## Checks and disposition

The implementation tests cover frozen-plan semantics, strict JSON, exact
T-010 basis and initial state, the order-18 recurrence, the zero-time branch,
fail-closed inputs, observable/invariant extraction, classification priority,
fine-only overdamped-trend eligibility, provenance, and atomic no-overwrite
publication. Repository control-pack validation exercises the task graph,
registry, and complete test suite.

S-011 is accepted through the approved deterministic pivot. The failed v2
confirmation path remains permanently prohibited, and its pilot remains
design-only. This acceptance unblocks S-011's dependency edge but does not by
itself close G2; S-012 and the independent V-010 baseline audit remain.
