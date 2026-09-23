# S-074 paired Richardson reanalysis — post-result amendment

Blake authorized implementation of the reviewed corrections and reanalysis
on 6 September 2026, after inspection of the original S-074 outcomes and a
read-only feasibility calculation. This is explicitly post-result analysis,
not a preregistered replacement for the raw-finest primary study. It may be
publication-facing when identified as such. The original study, all frozen
sources, sample counts, references, margins, failures and raw records remain
unchanged. No new trajectories, pilot reuse, pooling, row selection or top-up.

## Fixed calculation

Use all 41 cells / 80 rows from the existing v2 archive, with the same three
coupled levels, trajectory counts and three late-time windows. Verify the
freeze, source hashes, receipts and complete allocation through the existing
read-only loaders. The source results SHA-256 is
`08573e429b4816a87f24f556035173ab4aeb48ae466f52e774446ba3f44b4137`.

For every row and window, R = 2 X_h - X_2h and R' = 2 X_2h - X_4h.
Use the stored joint sufficient-feature covariance. Linear moments use the
paired independent-trajectory SE. Centered variance and diffusion use the
existing exact finite-N delete-one whole-trajectory jackknife for the
combined statistic, including recentering and slope under deletion. Naive
OLS errors and independent-error addition are not allowed.

Keep q=2.5758293035, epsilon, the reference/parent precision scale and tau
unchanged. Define the residual envelope by

```text
B_R = abs(2 X_h - 3 X_2h + X_4h)
      + q SE(2 X_h - 3 X_2h + X_4h).
B_late = max(original primary window envelope,
             max_{w=1,2} abs(R_w-R_0),
             original deterministic transient residual).
delta_R = R_0 - reference.
I_R = delta_R +/- (q SE_R + B_R + B_late).
```

Classify interval containment, contradiction or unresolved overlap using
the original epsilon. Precision against 1% and against the stronger tau
are separate from interval agreement. Preserve the raw-primary outcomes
alongside the reanalysis outcomes, even if they differ. A changed estimator
does not erase either original stricter-SE miss. Retain a concise explicit
statement of both misses in the supplement; typographic asterisks may be
removed from the reanalysis table if that statement remains unambiguous.

## Diagnostics, not selection rules

Report all raw h/2h/4h values and SEs, R/R' and combined SEs, paired step
differences, uncertainty-aware residual, raw and reanalysis standardized
discrepancies, SE inflation and both precision flags. Report convergence
ratios only where the denominator is larger than its paired q-SE and a
floating-point floor; otherwise identify them as indeterminate. Report all
class-mean standardized discrepancies and all absolute values above three.
These are diagnostics, not acceptance thresholds or row-selection rules.

The supplied approximate +0.004 core-V speed forecast is not a selection
criterion: the measured fine/coarse gap is 0.0032449717123261834 and its
step ratio is 2.0056424980406367. These known readback values are not targets
to tune toward. No conditional raw/Richardson mixture is selected by closeness
to a reference. The weak-order claim is supported empirically by the paired
levels, not a new rigorous global error bound.

## Reproducibility and integration

The new CPU-only script is `scripts/reanalyze_s074_richardson.py`; its default
output is `artifacts/derived/S-074-Richardson-2026-09-06/`. Use a distinct
schema/estimator identity, link the original result and freeze hashes, retain
all 80 rows and 52 figure points, and emit checksums plus raw-step and
diagnostic CSVs. Repeated generation must reproduce identical bytes or fail
on a conflicting existing output. Test the real nonlinear paired jackknife
against literal deletions, not only a reconstruction from stored marginal SEs.

Publication text must say that Richardson was adopted after observing the
finest-step bias. The main/supplement source, table and figure must agree on
which estimator they display. S-071/S-073 retain their unresolved outcomes;
their disclosure may be shortened and moved out of the main discussion.

## Confirmed author facts and remaining factual boundaries

Blake states: no funding, no competing interests, no arXiv posting. These
facts can be placed in the manuscript and submission materials. The
corresponding email is gpierpo1@jh.edu. Bernard and Liu's metadata should be
retrieved from other project author records, with the source recorded.
Metadata retrieval is not coauthor approval of the current manuscript.
No prior FNL rejection, invitation to resubmit, human re-derivation of every
equation, or unpublished-service DOI is inferred. FNL remains selected;
Physica A is a separately labeled alternative. Existing authorization for
release preparation and service publication remains, but journal submission
and missing authenticated access are separate from this implementation.
