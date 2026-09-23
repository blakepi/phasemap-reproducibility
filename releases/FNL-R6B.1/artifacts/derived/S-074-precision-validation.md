# S-074 full-noise trajectory results — 6 September 2026

## Outcome

All **80/80 reported observables meet the requested 1% standard-error target**.
The largest SE divided by its declared precision scale is
`0.00857567116354545` (0.857567%, figure-rho6-VTheta:spatial). Nonzero
references use their own absolute magnitude; symmetry-zero mean velocities
use the prospectively declared parent scale, not a relative error against zero.

All **80/80 expanded pointwise discrepancy intervals are contained** in their
unchanged comparison margins: 80 validated interval classifications, zero
unresolved intervals, zero contradicted intervals. All 80 production
timestep checks pass. These are finite-parameter empirical comparisons, not
a continuum proof, simultaneous-coverage claim, or inference from noisy data.

The stronger planning target `SE <= min(0.01 C_prec, epsilon/(3q))` is met
by **78/80**, not 80/80. Two stationary spatial-variance rows exceed its
conservative `epsilon/(3q)` component while comfortably meeting 1%:

| Row | Reference | Estimate | SE | SE/reference | Strict design SE |
|---|---:|---:|---:|---:|---:|
| M=2, Pe=3, rho=0.5, PV | 11.6666666667 | 11.6500787632 | 0.0238653147593 | 0.204559841% | 0.0226464281830 |
| M=2, Pe=3, rho=0.5, PTheta | 16 | 15.9983594240 | 0.0315110778310 | 0.196944236% | 0.0310579586509 |

The largest strict-target ratio is 1.05382246447. Both flags remain false
in the immutable results; the aggregate `precision_pass` and
`qualification_pass` remain false. No threshold, data, estimate, source hash,
classification, or recorded flag has been changed after observing results.
This report does not convert the study into an unqualified all-criteria PASS.
The paper and table must distinguish the achieved user-requested precision
and interval agreement from these two stricter design-target misses.

For additional context, every row also satisfies the original registry's
`q SE <= 0.5 epsilon` and `q SE+B <= 0.75 epsilon` precision budgets: their
largest ratios are 0.351274154824 and 0.574911060643, respectively. This is
a reported comparison with existing rules, not a retrospective replacement
of the stronger S-074 flags. No extra trajectories are needed to meet the
user's stated 1% requirement; no further production or pooling was performed.

## Fixed execution and provenance

- 41 parameter–protocol cells, all seven protocols, 80 rows; all are retained.
- 23,519,232 fresh independent production trajectories, 2871 batches of 8192;
  per-cell N ranges from 49,152 to 1,146,880. No allocation changed in production.
- Separate excluded pilot: 4096 per cell, 167,936 total. Pilot and historical
  studies contribute zero weight to every production estimate.
- Production ran from 06:16:33 to 07:30:53 UTC on 6 September 2026
  (74 minutes 20 seconds, logged wall time), NVIDIA GeForce RTX 5060 Ti.
- CPython 3.12.14, NumPy 2.5.1, CuPy 14.2.0; CUDA runtime 12090,
  driver 13030. Exact environment and sources are in the frozen records.
- Final plan: `experiments/S-074-precision-primary-v2.json`.
- Plan semantic SHA-256:
  `e00bce97ad4711455fdc1d6337105a78cd37c47e6614763aa28c0260b763c318`.
- Freeze file SHA-256:
  `691486b6b2685e37f4dc51a85b4c7b588915a5bc99cb1d58792d9305d7bd23c4`.
- Scientific source-manifest SHA-256:
  `f4fa2cf48b6e916a6a92a8b93bd22420b34465d7452100ab0b25466ff0fdf1cd`.
- Fixed allocation SHA-256:
  `5ad0dd01abb84adfd23257b01fec9e422637c493b92fe9cb9b3a597d83fb64c5`.
- Final results SHA-256:
  `08573e429b4816a87f24f556035173ab4aeb48ae466f52e774446ba3f44b4137`.
- Raw results: `artifacts/raw/S-074-precision-primary-v2/results.json`.
  Original qualified pilot: `artifacts/raw/S-074-precision-primary-v1-iofix/`.

The original serialization recovery and the pre-production resource-only
cap extension are fully recorded in `docs/release/FNL_R2_WORK_LOG.md`,
`docs/release/S074_REPRODUCTION.md`, the two prospective plans and the
separate resource extension. Both earlier carriers remain unchanged.
S-071 remains 14/46 validated, 32 unresolved, 0 contradicted; S-073 remains
32/46 validated, 14 unresolved, 0 contradicted. Neither is pooled or relabeled.

## Method and checks

Independent physical-noise Euler–Maruyama trajectories start at zero and
include both translational and rotational noise. The primary values are
raw finest-step estimates, not theory-corrected or extrapolated estimates.
Exact exponential reset clocks and summed Brownian increments couple h,
2h and 4h. Fine h is 1/512, 1/1024 or 1/2048; T is 64 or 160.
There are 65 equally spaced records and three declared late windows.
The 28-moment generator selected T before sampling and supplies no increments
or correction to measured results.

Uncertainty is between independent trajectories, with a delete-one
whole-trajectory jackknife for centered covariances and diffusion slopes.
The excluded pilot's jackknife/bootstrap SE ratios are 0.95465–1.05064;
all pilot method checks passed. Naive OLS slope SE is not used.

Primary pointwise q=2.5758293035 and epsilon=0.005 C+0.01|R| are unchanged
(zero relative term for symmetry zeros). Each discrepancy interval is expanded
by the empirical fine/coarse envelope plus the larger of observed window
sensitivity and the deterministic transient residual. These empirical
envelopes are not rigorous discretization-error bounds.

| Diagnostic across all 80 rows | Maximum |
|---|---:|
| First paired-step envelope / (epsilon/4) | 0.397483237901 |
| Second paired-step envelope / (epsilon/8) | 0.0106106447330 |
| Observed late-window sensitivity / epsilon | 0.216136979459 |
| Absolute discrepancy / epsilon | 0.256932235965 |

## Commands and actual results

The commands below use the isolated `tmp/S074_ENV/Scripts/python.exe`.
They are shown without the local interpreter prefix for portability.

```text
python experiments/run_s074_precision.py --plan experiments/S-074-precision-primary-v2.json produce
python experiments/run_s074_precision.py --plan experiments/S-074-precision-primary-v2.json summarize
python experiments/run_s074_precision.py --plan experiments/S-074-precision-primary-v2.json validate
python -m pytest -o addopts='' -q tests/simulation/test_s074_gpu_trajectories.py tests/simulation/test_s074_precision_statistics.py tests/simulation/test_s074_precision_study.py
```

- `produce`: exit 0; all fixed cells and batches completed.
- `summarize`: saved the complete immutable results, then returned exit 1
  because the two stronger design-SE flags failed. This expected fail-closed
  signal is retained, not treated as a missing dataset or suppressed success.
- `validate`: exit 0, integrity PASS; recomputed 41 cells / 80 rows from the
  stored sufficient statistics and verified every source, receipt and fixed
  count. Integrity PASS does not change either failed design flag.
- Post-production GPU/statistics/study tests: **80 passed in 8.03 s**.
- Publication renderer: retained all 80 table rows and 52 figure points.

Local execution logs: `tmp/S074_production_v2.log`,
`tmp/S074_final_reduction.log`, `tmp/S074_final_validation.log`,
`tmp/S074_postproduction_gpu_tests.log`.
Independent final interpretation and publication review is V-092; its
findings are recorded separately in `docs/release/FNL_R2_REVIEW.md`.
