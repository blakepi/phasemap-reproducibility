# S-074: prospective precision-study amendment, version 1

Authorized by Blake on 6 September 2026, before S-074 scientific sampling.
This new study does not pool, overwrite or reclassify S-071 or S-073. Their
unresolved results remain public historical evidence. The original v0.4
contract and registry remain byte-unchanged for those studies.

## What is amended

S-074 samples independent physical-noise Euler--Maruyama trajectories, including
both translational and rotational noise. Exponential reset clocks are exact;
all three step levels share the same clocks and summed Brownian increments.
The primary estimator uses the finest EM level, not a theory-corrected value.
Earlier conditional-moment timestep validation is not transferred to this
method. Initial position, velocity and orientation are zero.

The accompanying executable plan declares 41 parameter--protocol cells and
their paper-facing observables. It does not inherit the former 46 comparison
identifiers, duplicate unpaired checks, or conditional-noise adequacy tests.
It includes all seven protocols at the active core, four reset rates for the
Figure 1 curves, and three masses on the tuned V/Theta branch. Every planned
cell is retained, independently of its result.

One excluded pilot of 4096 independent trajectories per cell sizes a fresh,
fixed production sample from estimated standard errors only. No observed
discrepancy from a reference enters the sample-size projection. The target is
at most 1% of the nonzero reference magnitude, or the declared parent scale
for a symmetry-forced zero. A stricter design SE of epsilon/(3q) leaves room
for bias and the 99% interval. The precision scale is |R| for every nonzero
moment, including small diffusion coefficients; the characteristic scale C
used in epsilon is distinct and is never substituted into that relative-SE
denominator. The larger required N is used, inflated by
1.20 and rounded up to batches of 8192. Minimum N is 32768/cell, maximum
1048576/cell and maximum total 16777216. About one million is a resource
estimate, not a scientific stopping criterion. A projection above either cap
is reported before production, not silently clipped. Production is not
pooled with any pilot or earlier study and is not topped up or stopped on
first agreement. Monitoring completed work is permitted.

Linear moments use one late-window summary per independent trajectory.
Centered spatial variance and effective diffusion use the finite-N unbiased
ensemble covariance; diffusion is one quarter of its intercept-including
fixed-window slope. Their uncertainty is the delete-one whole-trajectory
jackknife, recomputing centering and slope algebraically under each deletion.
The independent-unit covariance of the sufficient features preserves pairing
across levels and windows. Naive OLS slope SE is forbidden. This explicitly
replaces the default production bootstrap for S-074 only. The pilot checks
the jackknife against 1024 whole-trajectory multinomial bootstrap replicates:
ratio 0.90--1.10, and each fixed 512-replicate half within 10% of the full SE.
A failure requires a logged prospective method revision before production.

## Accuracy and comparison rules retained

The v0.4 primary-tier quantile q=2.5758293035, observable scale dispatch,
epsilon=0.005 C + 0.01 |R| (no relative term at symmetry zeros), and
validated/contradicted/unresolved expanded-interval definitions are unchanged.
Precision and agreement are separate outcomes. Individual trace scales are
the corresponding trace magnitudes; the velocity-mean scale is sqrt(S_xx),
the mixed trace scale is sqrt(Tr R Tr S), and D uses max(|D|,1). Contrasts
use the larger parent scale and independent-protocol errors, not relative
error against a vanishing difference. All reported comparisons are pointwise,
not a claim of simultaneous 99% coverage.

Before the pilot, h is the inverse power of two no larger than
min(1/512, M/200, 1/(200 rho)). The h,2h,4h coupled estimates are retained.
The pilot fine-step bias envelope is |Y_h-Y_2h|+q SE(Y_h-Y_2h); it must be
no greater than epsilon/4. A second-order residual
|Y_h-1.5Y_2h+0.5Y_4h|+q SE of that paired expression must also be no greater
than epsilon/8. These are empirical weak-step diagnostics, not rigorous
error bounds or a transfer of an earlier method's Richardson result.
Their failure requires a logged prospective step revision before production.
The same envelopes are recomputed and reported at fixed production N.
Production must also meet both step-qualification inequalities; a failure
remains a qualification failure even if its expanded interval is contained.

T starts at the next even integer >= max(64,24/rho,16M). There are 65 equally
spaced records and windows [T/2,T], [2T/3,T], [3T/4,T]. Before sampling, the
existing 28-moment generator propagates the declared zero initial state to
these times; the same mean/covariance/slope functionals are compared with the
stationary or asymptotic references. T doubles, at most to 1024, until every
window's finite-time bias is <= epsilon/12. This deterministic calculation
fails as infeasible if that condition is not achieved by T=1024; no horizon
is silently clipped. It
selects the observation horizon, never supplies trajectory increments or
corrects measured results. Its residual is retained separately. The observed
production window envelope is the largest change from the primary window;
sampling SE, step envelope and window envelope are not conflated.

The final interval for the discrepancy is delta +/- q SE, expanded by the
step envelope plus the maximum of the observed window envelope and the
deterministic finite-time residual. All outcomes, including contradictions,
precision failures and qualification failures, are reported without selecting
successful rows. The manifest fixes source hashes, registry/contract identity,
environment, seeds, parameters and array reduction layout before sampling.
Batch files are immutable; resumption reuses verified completed batches and
continues at the next disjoint path offset. A crashed incomplete batch may
be reproduced identically, never replaced with a different random stream.

The h selection is a conservative resource choice, not a claim that exact
reset clocks require rho*h resolution. An engineering-only GPU timing check
(8192 paths, T=8, h=1/512, rho=6, PVTheta) took 0.722 seconds, including
startup; its outcomes were not used for scientific design. The minimum
allocation is 1,343,488 production trajectories; the stated larger cap permits
honest precision sizing rather than implying that 16.8 million is about one
million. The actual allocation and projected runtime will be logged after
the excluded pilot and before production.

## Reporting

The manuscript gives a concise account, the supplement lists the numerical
estimates and uncertainty, and Figure 1 uses actual measured symbols. S-071
and S-073 remain explicitly unresolved quantitative attempts. New evidence
cannot retrospectively turn them into successful experiments. This amendment
authorizes a new empirical check, not broader parameter inference or a change
to the exact physical model, formulas, or reference attribution.
