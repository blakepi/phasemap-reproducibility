# FNL-R6B.1: packaging-only correction

Successor archive DOI: https://doi.org/10.5281/zenodo.22925278.
Manuscript release: FNL-R6B, https://doi.org/10.5281/zenodo.22924890.
Scientific software version: 3.2.0rc2 (unchanged).

## What changed

FNL-R6B's standalone source ZIP omitted
`artifacts/derived/T-070-constrained-moment-frame.md`. Its export sanitizer
also removed a link to the omitted `Q-030-target-lock.md`, changing B-040's
source hash while retaining the original F-050 provenance manifest. Those
packaging defects were identified after R6B publication and disclosed.

This correction includes both already-public documents, preserving the
original B-040 source bytes and original figure manifests. A regression
test builds and extracts the real ZIP and runs the complete figure and
provenance check. No figure, numerical result, scientific implementation,
registry, estimator, margin or manuscript is revised.

All four author PDFs and the private editable manuscript-source ZIP are
byte-identical to R6B. Their R6B DOI remains intentional. This successor
provides corrected packaging of the same research, not a revised paper.
The corresponding author reported coauthor approval of R6B and explicitly
authorized this packaging-only successor. No new author certification is
inferred. No journal submission or completion email was performed.

## Use these files

- `PHASEMAP_FNL_R6B1_Reproducibility.zip`: corrected current source archive.
- `PHASEMAP_FNL_Numerical_Records.zip`: unchanged numerical evidence,
  SHA-256 `b7138bd988a3667fd1f79d7fc5f0b6a13fe0276503e922ca24c0f8956b278f55`.
- `PHASEMAP_FNL.pdf`, `PHASEMAP_FNL_Supplement.pdf` and
  `PHASEMAP_FNL_General_Summary.pdf`: unchanged public R6B PDFs.
- Earlier `PHASEMAP_FNL_R6B_Reproducibility.zip`,
  `PHASEMAP_FNL_Reproducibility.zip` and `FNL_R6B_PUBLIC_RELEASE_README.md`
  are retained historical snapshots, not the corrected source package.

Extract the corrected code archive and numerical archive into one empty
directory. Follow [REPRODUCTION.md](REPRODUCTION.md) for the tested environment.
From the extracted directory run:

```powershell
$env:PYTHONUTF8='1'
python experiments/run_s074_precision.py --plan experiments/S-074-precision-primary-v2.json validate
python scripts/reanalyze_s074_richardson.py
python src/phasemap/analysis/generate_final_figures.py --check
```

Then run the exact portable pytest command in `ARCHIVE_MANIFEST.json`.
These commands reconstruct preserved results; they do not sample trajectories.
The raw/Richardson chronology, two stricter design-precision misses and
unresolved unpooled historical outcomes remain explicit.

For the three public PDFs, run `latexmk -pdf` separately on
`PHASEMAP_FNL.tex`, `PHASEMAP_FNL_Supplement.tex` and
`PHASEMAP_FNL_General_Summary.tex` in `manuscript/journal/fnl/`.
The four-PDF builder requires the private cover-letter source and belongs
to the author's separate complete submission-source ZIP. Private cover-letter
and referee metadata are not in the public archive.

Licenses, third-party notices, creator order and ORCIDs remain unchanged.
Earlier Zenodo records and Git tags are immutable and preserved. The release
receipt records final publication and anonymous-download verification;
a reserved DOI by itself does not establish publication.
