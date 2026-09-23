# S-074 trajectory reproduction

S-074 is a new full-noise Euler--Maruyama study, authorized independently of
the historical S-071 and S-073 datasets. Those earlier quantitative studies
remain unresolved. Neither was pooled, retried, topped up, or reclassified.

## Read and recompute the numerical results

Extract `PHASEMAP_FNL_Reproducibility.zip` and
`PHASEMAP_FNL_Numerical_Records.zip` into the same directory. The code archive
contains the package, exact scientific sources, plans, optional GPU dependency
lock, tests, manuscript sources and figures. The numerical archive preserves
raw JSON and NumPy files byte-for-byte, with their relative paths and hashes.
The latter includes both the design-only pilot's original carrier and the
separate production carrier. Install the package as described in
[REPRODUCTION.md](REPRODUCTION.md), then run from the extracted root:

```powershell
python experiments/run_s074_precision.py --plan experiments/S-074-precision-primary-v2.json validate
python scripts/reanalyze_s074_richardson.py
python src/phasemap/analysis/generate_final_figures.py --check
```

Validation reconstructs the 80 results from immutable production sufficient
statistics and checks the frozen source, fixed counts, pilot origin, original
receipts and artifact hashes. It does not sample trajectories and does not
require a GPU. The figure/table renderer reads completed results only. The
exact recorded Python/NumPy environment is provided in `freeze.json`; binary
identity of regenerated floating-point reductions is not promised for a
different numerical runtime or hardware.

## GPU study and fixed sample size

The optional production environment is CPython 3.12.14 with the exact packages
in `requirements/s074-gpu-lock.txt`. The recorded GPU is an NVIDIA GeForce
RTX 5060 Ti; the freeze records CuPy, CUDA runtime, driver, device and source
identities. The producer checks that environment before sampling. The GPU
kernel implements full translational and rotational noise, exact exponential
reset clocks and coupled Brownian increments at three Euler--Maruyama steps.
No analytic reference is supplied to the trajectory kernel.

The single excluded pilot uses 4096 independent trajectories in each of 41
parameter--protocol cells. It qualified all 80 planned comparisons against
the declared timestep checks. The whole-trajectory jackknife/bootstrap SE
ratios range from 0.95465 to 1.05064. Production sample sizes depend on pilot
SEs only, not on observed agreement with theory. The unchanged formula projects
23,519,232 fresh trajectories in total, at most 1,146,880 in a cell. The pilot
does not enter any production estimate.

The initial computational ceilings were insufficient for that projection.
Before any production, plan v2 increases only the allowances to 2,097,152 per
cell and 33,554,432 total. The actual fixed sample sizes are not those ceilings.
All estimands, parameters, seeds, steps, horizons, precision targets, agreement
margins and the allocation formula stay unchanged. Version 2 resolves the
original pilot read-only through its pinned freeze and original producer
receipts. It does not create a new pilot or relabel the old producer identity.

The original first core-P transaction stopped while encoding a NumPy boolean
in diagnostic JSON. An explicit Python-boolean conversion fixed that storage
error. The replayed features, accumulator and layout matched all three original
SHA-256 hashes exactly. Both this technical recovery and the resource extension
precede production; neither changed a scientific observation or selected a
replacement random stream.

The command sequence used to create the recorded study is documented with
results in the accompanying S-074 validation report. Do not run a producer to
verify already completed results. A scientific replication in a different
environment is a new versioned study, not an overwrite of these records.

## Interpretation

All 80 requested 1% SE targets were achieved (maximum 0.857567% of the
declared scale), all 80 expanded pointwise intervals were contained, and all
timestep checks passed. Two spatial-variance rows at M=2, Pe=3, rho=0.5
(PV and PTheta) exceeded the additional epsilon/(3q) design-SE target.
Their immutable precision flags and aggregate all-criteria qualification
remain false. See the [complete outcome report](../../artifacts/derived/S-074-precision-validation.md).
The `summarize` command therefore saves all results and returns a qualification
failure; the separate `validate` command passes record integrity and exact
recomputation without changing those flags. No additional sampling is needed
to satisfy the requested 1% target and no top-up was performed.

The frozen primary estimate is the raw finest-step estimate. It is still
available unchanged in `artifacts/raw/S-074-precision-primary-v2/results.json`.
To render that historical primary analysis separately, use:

```powershell
python scripts/render_s074_publication.py --results artifacts/raw/S-074-precision-primary-v2/results.json --output-dir tmp/S074_raw_primary_tables
```

## Post-result paired Richardson reanalysis

After observing the finest-step bias, a separately authorized analysis uses
`R = 2 X_h - X_2h` for all 80 rows, never choosing between raw and extrapolated
estimates according to closeness to theory. The amendment is
`docs/scientific-contract/S-074_RICHARDSON_REANALYSIS.md`. The CPU-only command
above authenticates and merges the preserved production accumulators, then
writes distinctly identified results, diagnostics, checksums, tables and 52
figure points under `artifacts/derived/S-074-Richardson-2026-09-06/`. It does
not overwrite the original results, change the frozen producer, or sample any
additional trajectories. An existing conflicting derived output fails closed.

The SE uses the full paired covariance. Centered statistics use the exact
finite-N whole-trajectory delete-one jackknife, including recentering and the
diffusion slope. The residual envelope is
`abs(2 X_h - 3 X_2h + X_4h) + q SE(2 X_h - 3 X_2h + X_4h)`; the late-window
envelope is at least as large as the original primary envelope. The original
q, agreement margin and both precision thresholds are unchanged.

All 80 extrapolated rows also meet the requested 1% target and the pointwise
expanded-interval containment comparison. The maximum SE is 0.858580% of the
declared scale. The same PV and PTheta spatial-variance rows still miss the
stricter design-SE threshold (0.204557% and 0.196936%, respectively). Both
primary and reanalysis qualification flags remain false; no asterisk removal
in the table changes these outcomes. The observed core-V fine/coarse speed
gap is 0.0032449717, not the incoming draft's approximate 0.004 forecast.
All convergence and standardized-discrepancy diagnostics are reported rather
than used to select rows or tune the estimator.

The publication table and Figure 1 display these paired Richardson estimates.
Symbols are actual extrapolated estimates with one-SE bars, not theory values
or graphical displacements. Sampling SE, discretization and observation-window
sensitivity remain separate. Precision or software integrity alone does not
imply agreement. No claim of simultaneous interval coverage or globally
identifiable unknown physical parameters is made.

## Journal presentation and preserved analysis history

The R4 editorial revision describes the reported estimator as a numerical
method and keeps its selection chronology and stricter sizing-target outcomes
in this archive documentation. It does not retroactively change the raw-finest
primary study, mark either missed target as achieved, or claim that the
Richardson choice was preregistered. The preceding sections and the archived
amendment/results retain those facts explicitly.

In an R4 source checkout, the following renders the revised Table S1 wording
from the identical results without changing the numerical rows or point data:

```powershell
python scripts/render_s074_publication.py --results artifacts/derived/S-074-Richardson-2026-09-06/results.json --output-dir tmp/S074_journal_tables --presentation journal
```

Use a fresh output directory. Default `--presentation archive` retains the
historical tables byte-for-byte, including the text originally checksummed by
the Richardson analysis. It remains the default used by the reanalysis
command above. Neither presentation mode overwrites conflicting Richardson
outputs. The frozen code ZIP at DOI `10.5281/zenodo.22581850` is the earlier R2
snapshot and intentionally predates the R4 presentation switch; its original
reproduction commands and analysis history remain valid. The R6B-bound archive
draft `PHASEMAP_FNL_R6B_Reproducibility.zip` is reserved at DOI
`10.5281/zenodo.22924890`, with unchanged software and numerical records but
current manuscript sources; it is not yet published.

## R5 external-review clarification

On 7 September 2026 Blake approved restoring a concise statement of the
Richardson selection chronology and both stricter precision misses to the
submitted supplement and table legend. This supersedes only the preceding
R4 editorial placement choice. All underlying records, estimator identities,
80 comparisons, 52 points and acceptance margins remain unchanged.

The R5 delivery includes the current journal-only table renderer as
`reproduction/render_s074_publication.py`. This standalone standard-library
script can be used without replacing any file in the published code archive:

```powershell
python PATH_TO_R5/reproduction/render_s074_publication.py --results artifacts/derived/S-074-Richardson-2026-09-06/results.json --output-dir R5_journal_table --presentation journal
```

Run from the extracted public code/data root after the CPU-only reconstruction
commands above. The output table body and figure-point JSON are identical to
the archived numerical values; only the journal caption and parameter-heading
layout differ. Use `PHASEMAP_FNL_Source.zip` in the R5 delivery for the revised
manuscript, supplement and exact included Figure 1 PDF. Its four entry points
build with `latexmk -pdf` from `manuscript/journal/fnl`. Neither this add-on nor
the source ZIP claims to replace the complete public scientific archive.

## R6 journal-label clarification

R6 changes only the journal-facing spatial-variance label from V to
s_r^2 = Tr Cov(r), avoiding confusion with the velocity-reset protocol V.
The observable, all values and statuses, 80 comparisons and 52 figure points
are unchanged. Default archive-mode tables remain byte-identical. R5's
Richardson chronology and both stricter precision misses stay visible.

The R6 pre-publication package includes the current standalone renderer under
reproduction/render_s074_publication.py; use the preceding command with
PATH_TO_R6 and a fresh output directory. The R6B successor draft is reserved
at DOI `10.5281/zenodo.22924890`, binding its current manuscript sources to the
unchanged software and numerical records, but it is not yet published. DOI
`10.5281/zenodo.22581850` remains the historical R2 code/data record.
