# PHASEMAP scientific contract

**Status:** APPROVED - Option C publication-boundary amendment authorized by Blake

**Contract version:** 0.4

**Base scientific content commit:** `374e26716efde0763f4ea0598576656ad2d6d113`

**G1 disposition:** named-person approvals waived by direct user instruction on 22 July 2026; no approval is attributed to Blake, Yi-Chen, or Olivier

**Option C disposition:** Blake explicitly approved the full-record-distinguishability plus scope-limited-degeneracy publication boundary on 24 July 2026

**Prepared:** 21 July 2026 from the precomputed draft plus C-001/C-002/C-003 audits

This locked contract integrates the C-001/C-002/C-003 audits, the accepted
S-021/V-020 evidence, and the approved Option C publication-boundary
amendment. The underlying model, reset maps, second-order definitions,
validation thresholds, and accepted G2/G3 results are unchanged. The ordinary
named-person G1 approval process was waived by explicit user direction; that
waiver changes process status only and does not represent an approval by any
unchecked approver.

## 1. Between-reset dynamics

Use the dimensionless two-dimensional inertial active Brownian model

```text
d r = v dt
M d v = -(v - Pe u(theta)) dt + sqrt(2) dW_t
d theta = sqrt(2) dW_r
u(theta) = (cos theta, sin theta)
```

with a standard two-component translational Wiener process and an independent standard scalar rotational Wiener process. Thus `E[dW_i dW_j]=delta_ij dt`, `E[dW_r^2]=dt`, and cross-covariances vanish. Parameters are inertia `M>0`, activity `Pe>=0`, and reset rate `rho>=0`.

The dimensional precursor is

```text
d r_d = v_d dt_d
m d v_d = -gamma (v_d - v_a u(theta)) dt_d + sqrt(2 gamma k_B T) dW_d
d theta = sqrt(2 D_r) dW_r,d
```

with `D=k_B T/gamma`. The locked scaling is `t=D_r t_d`, `r=r_d/sqrt(D/D_r)`, `v=v_d/sqrt(D D_r)`, `M=m D_r/gamma`, `Pe=v_a/sqrt(D D_r)`, and `rho=rho_0/D_r`. This produces the dimensionless equations above exactly. The primary-source audit and derivation are recorded in `artifacts/derived/C-001-model-contract.md`.

## 2. Reset process and seven protocols

Reset events form an independent Poisson process of rate `rho`. At each event, apply one fixed-state reset map and leave every unlisted state variable unchanged:

| Protocol | Instantaneous map |
|---|---|
| `P` | `r -> 0` |
| `V` | `v -> 0` |
| `Theta` | `theta -> 0` |
| `PV` | `r -> 0`, `v -> 0` |
| `PTheta` | `r -> 0`, `theta -> 0` |
| `VTheta` | `v -> 0`, `theta -> 0` |
| `PVTheta` | `r -> 0`, `v -> 0`, `theta -> 0` |

If the pre-reset state is `X-=(r-,v-,theta-)`, each protocol has conditional post-reset law `delta_{R_q(X-)}`, the Dirac mass at the table's deterministic image. The zero reference values are two-component zeros for position and velocity and scalar zero for orientation; every unlisted component is retained exactly. Random post-reset distributions are deferred.

## 3. Initial and event semantics

- Default initial state: `r(0)=0`, `v(0)=0`, `theta(0)=0`.
- The continuous SDE evolves between jumps; a jump is instantaneous and does not advance physical time.
- Preferred simulator: sample exact exponential waiting times and integrate/split at each reset time.
- At a reset time, record the integrated pre-reset state, apply the map without advancing time, and record the post-reset state at the same time. Two consecutive trajectory entries may therefore share a timestamp and represent the left and right event limits.
- A small-step Bernoulli implementation using probability `rho*dt` is a separate baseline-reproduction route, not the primary truth implementation.
- Simultaneous noise and jump events have probability zero in continuous time. The numerical convention is: finish the segment ending at the sampled reset time, then apply and record the reset. `test_simulator_smoke.py` locks this ordering.

## 4. Required observables

For every protocol, predeclare the full component-level second-order closure set, with `u=(cos(theta),sin(theta))`:

- means `E[r]`, `E[v]`, and `E[u]`;
- raw matrices `E[r r^T]`, `E[v v^T]`, `E[r v^T]`, `E[r u^T]`, `E[v u^T]`, and `E[u u^T]`, including every two-dimensional component and the transposes implied by scalar products;
- derived scalars `E[|r|^2]`, `E[|v|^2]`, and `E[r dot v]`;
- centered spatial covariance and its trace;
- stationary variance when finite;
- centered effective diffusion `D_eff = lim_{t->infty} Tr Cov(r(t))/(4t)` when diffusive;
- an explicit identity ledger using only the labels defined in section 5;
- optionally, one selected fourth-order, cumulant, characteristic-function, or
  distributional contrast when it adds interpretation beyond the exact
  second-order structure.

G4 first ranks exact sector identities and contracted-observable degeneracies
with their full-record separating witnesses. A higher-order or distributional
contrast is not required for the minimum publication claim. If one is pursued,
G4 must preregister its observable, comparison pair, estimator, tolerance, and
falsification rule before evaluating it; changing it afterward requires a
recorded replacement-target decision.

Separate mean drift, localization, and fluctuation growth. Do not classify a protocol from raw MSD alone when the reset convention creates a nonzero mean.

## 5. Asymptotic classes

The G3 classification must distinguish at least:

- spatially stationary/localized: finite long-time centered spatial variance;
- diffusive: covariance grows linearly with finite `D_eff`;
- ballistic or anomalous: any other verified leading growth law;
- unresolved: evidence insufficient within tolerance.

The accepted V-020 result establishes **full-record distinguishability**:
after parameter and symmetry conventions are matched, every distinct protocol
pair differs in at least one member of the full predeclared second-order output
set for `M>0`, `rho>0`, and `Pe>=0`.

Restricted equalities must use only the following labels:

- **contracted-observable degeneracy:** exact equality of one explicitly named
  scalar contraction or finite list of contractions while other required
  outputs differ;
- **sector identity:** exact equality of one explicitly named stochastic
  sector while outputs outside that sector may differ;
- **conditional identity:** exact equality only under a stated parameter or
  observable condition;
- **resonant identity:** an exact conditional identity on a stated resonance
  surface;
- **limiting identity:** equality only after a stated singular or asymptotic
  limit.

None of these restricted identities is protocol equivalence. In particular,
contracted-observable degeneracy is not full-record equality; trace equality is
not full second-order equality; sector identity is not full-process identity;
and passive, resonant, or limiting identity is not generic finite-parameter
equivalence.

## 6. Mandatory limits and baselines

- `PVTheta` reproduces the selected complete-reset inertial baseline.
- `rho -> 0` reproduces free inertial active motion.
- `Pe -> 0` reproduces the appropriate passive underdamped reset problem.
- `M -> 0` is a singular Smoluchowski--Kramers position-process limit: `d r = Pe u dt + sqrt(2) dW`. Velocity is no longer an independent state, so protocols distinguished only by velocity reset require an explicit limiting comparison and may not be treated as distinct overdamped reset maps by direct substitution.
- Rare- and frequent-reset asymptotics are checked where defined.
- Position-containing protocols should be tested for spatial stationarity; non-position protocols must not be assumed stationary.

## 7. Numerical validation

The machine-readable validation registry is
`docs/scientific-contract/validation_registry.json`. It is an approved
component of this contract candidate and contains the executable evidence-tier,
observable-class, scale, uncertainty, sampling, and pairing rules used by
validation code. Its structure is validated by
`docs/scientific-contract/validation_registry.schema.json`.

This section is scientifically normative. The registry may encode and
specialize only the rules permitted here. A disagreement between this section,
the registry, or an implementing test is a BL2 contract-implementation
mismatch. Affected validation must stop until the disagreement is corrected in
one candidate-content commit.

### 7.1 Exact and deterministic checks

- Symbolic identities must simplify exactly to zero.
- Protocol equivalence at second order is established by exact symbolic or
  exact-matrix equality of the full predeclared second-order output set. It is
  not established by numerical tolerance or visual curve agreement.
- Deterministic floating-point state, reset-map, and event-ordering checks use
  absolute tolerance `1e-12` unless a test preregisters a tighter,
  scale-aware bound.
- Exact-clock reset semantics are the primary numerical implementation.
  Small-step Bernoulli resetting is a materially separate baseline-
  reproduction and event-semantics route, not the truth implementation.

### 7.2 Stochastic discrepancy and admissible margin

For stochastic validation quantity `j`, let

- `R_j` be the predeclared analytic, exact-matrix, or higher-authority
  reference;
- `S_hat_j` be the numerical estimate;
- `Delta_hat_j = S_hat_j - R_j`;
- `c(j)` be the observable class declared in the registry;
- `C_j > 0` be the characteristic scale generated by the registry's declared
  scale rule;
- `a_c` be the normalized absolute-floor fraction for class `c(j)`;
- `r_t` be the relative margin for evidence tier `t`.

The admissible discrepancy is

```text
epsilon_j,t = a_c(j) * C_j + r_t * abs(R_j).
The absolute-floor term is therefore scale-aware; no universal raw-unit
constant such as 0.005 is applied to every observable.

Let


I_Delta,j,t = [L_j,t, U_j,t]
be the preregistered pointwise uncertainty interval for Delta_hat_j. A
normal or Student-t interval may be written as
Delta_hat_j +/- q_t * SE_Delta,j. A bootstrap interval may be used when
declared in the registry.

Let


B_j = B_window,j + B_disc,j
be the nonnegative sum of separately estimated fitting-window and
discretization envelopes. Do not hide these systematic envelopes inside a
Monte Carlo standard error.

Use the expanded discrepancy interval


I_expanded,j,t = [L_j,t - B_j, U_j,t + B_j].
Classify the comparison as follows:

validated when
I_expanded,j,t is wholly contained in
[-epsilon_j,t, +epsilon_j,t];

contradicted when
I_expanded,j,t is disjoint from
[-epsilon_j,t, +epsilon_j,t];

unresolved otherwise.

An unresolved result is not agreement. It may trigger additional,
predeclared computation, estimator revision, or a recorded pivot, but it
cannot be averaged together with another route to create a pass. A
contradicted central result is BL3.

7.3 Characteristic scales and zero crossings
Characteristic scales are declared by observable class rather than by
manually assigning a separate tolerance to every protocol-component pair.

For component indices i,j, the default parent-moment scales are


C_r_i       = sqrt(abs(R_rr_ii))
C_v_i       = sqrt(abs(R_vv_ii))
C_u_i       = sqrt(abs(R_uu_ii))

C_rr_ij     = sqrt(abs(R_rr_ii * R_rr_jj))
C_vv_ij     = sqrt(abs(R_vv_ii * R_vv_jj))
C_uu_ij     = sqrt(abs(R_uu_ii * R_uu_jj))

C_rv_ij     = sqrt(abs(R_rr_ii * R_vv_jj))
C_ru_ij     = sqrt(abs(R_rr_ii * R_uu_jj))
C_vu_ij     = sqrt(abs(R_vv_ii * R_uu_jj))

C_r_dot_v   = sqrt(abs(R_abs_r_squared * R_abs_v_squared)).
A symmetry-forced zero uses its parent-moment scale and the normalized
absolute-floor term only; relative error against zero is not reported.

A signed observable that crosses zero uses its parent-moment scale rather than
abs(R_j) alone. When the location of the crossing is part of a scientific
claim, pointwise value agreement is insufficient. The run plan must
preregister:

a parameter bracket around the theoretical root;

the required signs on either side;

a root estimator and uncertainty method;

an admissible parameter-space error epsilon_root.

The estimated root interval must be wholly contained in the preregistered
root-location margin. A crossing whose slope is too small to locate within the
declared compute cap is reported as unresolved.

7.4 Evidence tiers
The registry defines three default evidence tiers:

routine_screen: approximately 95.45% pointwise coverage, normal-equivalent
q = 2, and relative margin r = 0.02. This tier is for automated smoke
tests, broad parameter screening, and compute triage. It is non-gating and
cannot by itself close G2-G7 or support a central publication statement.

primary: 99% pointwise coverage, normal-equivalent
q = 2.5758293035, and relative margin r = 0.01. This tier is used for
preregistered publication-facing validation points and ordinary
gate-closing numerical evidence.

central_disputed: approximately 99.73% pointwise coverage,
normal-equivalent q = 3, and relative margin r = 0.01. This tier is
reserved for a small preregistered set of main-text, disputed, or
release-audit points.

The default normalized floor fraction is recorded in the registry and may be
overridden only by observable class before results are inspected. The
pointwise tiers do not imply simultaneous coverage of the entire validation
atlas. Exact symbolic or exact-matrix analysis remains the comprehensive
evidence route for the full second-order classification.

Any observable-specific departure from a default tier, scale rule, margin,
interval construction, or floor must be preregistered before the corresponding
results are inspected.

7.5 Effective-diffusion and long-time fitting
D_eff is estimated only for protocols already classified as diffusive.
Localized protocols are assessed through convergence of centered spatial
variance and are not assigned a small fitted diffusion coefficient merely
because a finite-time slope is nonzero.

For ensemble simulations, the default uncertainty route for D_eff is a
whole-trajectory bootstrap:

resample independent trajectories as complete units;

recompute the ensemble mean trajectory and centered covariance within each
replicate;

refit the long-time slope within each replicate;

construct the declared bootstrap interval from the replicated
D_eff estimates.

A least-squares slope may be used as a point estimator, but naive OLS standard
errors that treat repeated time points as independent are prohibited.

The default late-time sensitivity windows are


[T/2, T]
[2T/3, T]
[3T/4, T].
The primary fitting window must be declared before result inspection. Define


B_window =
    max over admissible windows
    abs(D_hat_window - D_hat_primary).
Discretization sensitivity is reported separately as B_disc using the
preregistered fine/coarse or extrapolated comparison.

When only one long trajectory is available, batch means or a moving/stationary
block bootstrap may be used on an approximately stationary increment process
after burn-in. It must not be applied naively to the nonstationary growing
covariance curve.

7.6 Pilot runs and fixed sequential sampling
Every adaptive run plan must preregister:

pilot size N0;

pilot seed set;

confirmatory seed set;

evidence tier;

compute cap N_cap;

estimator and uncertainty method;

the maximum number of interim evaluations.

Only one pilot evaluation and one final evaluation are permitted.

After the pilot, compute the required sample size exactly once using


N_target =
    ceil(
        N0 *
        (
            q_t * SE_0 /
            (
                epsilon_j,t
                - abs(Delta_hat_0)
                - B_window,0
                - B_disc,0
            )
        )^2
    ).
If the denominator is nonpositive, or if N_target > N_cap, the result is
reported as unresolved or escalated under the preregistered compute rule.
Codex must not continue increasing the sample size until the result happens to
pass.

For routine_screen only, the pilot may remain in the final estimate. Codex
then runs exactly N_target - N0 additional trajectories in one batch and
performs one final analysis. This result remains non-gating.

For primary and central_disputed evidence, when the observed pilot
discrepancy enters the projection above, the pilot is design-only and is
excluded from the confirmatory estimate and interval. Codex runs
N_target new trajectories using a disjoint confirmatory seed set and performs
one final analysis. It must not subtract N0 from the confirmatory batch size.

Continuous polling, repeated top-ups, stopping at the first passing result, or
changing the evidence tier after observing results is prohibited. Any more
elaborate adaptive design requires an independently reviewed, preregistered
sequential-inference rule before use.

7.7 Paired paths, covariance, and independent routes
Fine-versus-coarse discretization checks use paired stochastic paths whenever
a valid coupling exists. Coarse Brownian increments are formed from the
corresponding fine increments, and exact-clock comparisons share the same
sampled reset times. For paired runs, estimate uncertainty from the
trajectory-level differences directly:


d_i = A_i - B_i
SE_Delta = sample_sd(d_i) / sqrt(N).
Paired bootstrap resampling must resample matched pairs together.

Common random numbers are allowed for comparing materially different
numerical methods and should be disclosed. They do not by themselves create
or destroy methodological independence. Independence is determined by method
family, derivation structure, implementation path, shared formulas, and shared
production code.

Every central numerical comparison that uses common random numbers also
requires a smaller unpaired confirmation with independently generated random
streams. A G7 clean-room audit uses an independent random stream and does not
reuse production stochastic infrastructure.

7.8 Convergence, limits, provenance, and route independence
Time-step convergence uses at least two resolutions and the applicable
interval-containment rule for the paired fine/coarse difference.

Baseline and limit regression tests must state:

the approached limit;

parameter sequence;

expected law;

observable and evidence tier;

estimator and uncertainty method;

observed discrepancy;

fitting-window and discretization envelopes;

final classification as validated, contradicted, or unresolved.

All stochastic runs record contract version, code commit, registry version,
parameters, seed policy, pilot and confirmatory sample counts, evidence tier,
integration resolution, estimator, interval construction, uncertainty
estimate, systematic envelopes, pairing policy, compute cap, and artifact
hashes.

Every central result requires a primary route and a materially independent
route. Acceptable independence changes method family, derivation structure, or
implementation path: for example symbolic generator/matrix closure versus
simulation, direct moment ODEs versus renewal/Laplace analysis, or exact-clock
versus independently implemented small-step simulation for event semantics.
Shared use of this contract is allowed; shared derived formulas, stochastic
infrastructure, assumptions, and production code must be disclosed. New
seeds, precision changes, or review of the same algebra do not count as an
independent route.

Route owner, method family, shared assumptions and code, expected tolerance,
evidence tier, and discrepancy outcome are recorded. A contradicted central
result is BL3 and cannot be averaged away. An unresolved result blocks the
affected gate or claim until resolved or handled through the recorded pivot
process.

## 8. Publication boundary

The minimum publication claim is:

1. a unified finite-inertia all-seven reset-map second-order classification;
2. exact full-record distinguishability of every distinct protocol pair on
   `M>0`, `rho>0`, and `Pe>=0`; and
3. an exact ledger of contracted-observable degeneracy, sector identity,
   conditional identity, resonant identity, and limiting identity, each paired
   with its full-record separating witness or stated scope boundary.

`PV`/`PVTheta` is eligible, but not automatically selected, as a
contracted-observable-degeneracy example. Any higher-order or distributional
result is an **optional higher-order/distributional contrast** and may be
included only when it adds interpretive value beyond the exact second-order
structure. It must not be described as breaking a full second-order
equivalence.

Prohibited representations are:

- contracted-observable degeneracy as protocol equivalence;
- trace equality as full second-order equality;
- sector identity as full-process identity;
- passive, resonant, or limiting identity as generic finite-parameter
  equivalence;
- a higher-order contrast as breaking a full second-order equivalence; and
- raw-MSD equality as centered-covariance equality.

Complete reset, standard jump generators, component resetting in overdamped
active matter, passive velocity resetting, and fourth moments by themselves
are not novelty claims.

## 9. Deferred scope

No random reset-state distributions, chirality, confinement, first passage, optimization, experimental fitting, multiple kinetic models, or broad all-protocol fourth-order atlas unless the minimum paper is already secure and humans authorize expansion.

## 10. G1 disposition and lock record

The ordinary G1 process required Blake, Yi-Chen, and Olivier to approve the exact candidate content commit recorded in `G1_APPROVAL_CHECKLIST.md` after Codex verified:

1. source fidelity of the equations and dimensionless mapping;
2. fixed reset-state choice and protocol maps;
3. mean/covariance observable definitions;
4. simulator event semantics;
5. initial tolerances and independent-route standard;
6. publication and deferred-scope boundary.

The decisions ordinarily requiring an explicit yes/no were the tensor closure set in section 4; the G4 preregistration deferral; the numerical agreement rule in section 7; and the independent-route standard in section 7.

On 22 July 2026, the user explicitly directed the root to bypass this human-approval gate and continue with authoritative G2 work. The lock transaction therefore records a one-time process waiver rather than named-person approvals. All Blake, Yi-Chen, and Olivier approval boxes remain unchecked, and no consent is inferred or attributed to them.

The original root lock transaction changed the status to `APPROVED`, version
to `0.3`, aligned registry metadata and program state/status, and tagged the
lock commit `contract-v0.3`. That waiver applied only to the G1 transition and
did not silently waive later release, external-contact, or submission
controls.

On 24 July 2026, after S-021 and V-020 established the complete second-order
record and disproved the former section 8 premise, Blake explicitly approved
Option C and directed the program to continue. Version `0.4` therefore changes
only sections 4, 5, and 8 and the corresponding program/novelty/task
interfaces. It preserves the model, observables, validation rules, accepted
evidence, and the theorem that no distinct pair has full-record equality.
Higher-order/distributional work becomes optional rather than a minimum-paper
gate. G6 release-candidate and G7 submission authorization remain separate
human gates.
