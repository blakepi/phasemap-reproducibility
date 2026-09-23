# Portable publication archive

`scripts/build_portable_publication_archive.py` creates the successor archive
without Git metadata, virtual environments, caches, or previous build output.
It includes the documented install and validation entry points and records the
actual collected test count in `ARCHIVE_MANIFEST.json` at build time. The count
is therefore provenance, not a claim copied from an earlier release.

Archive bytes are independent of Git checkout line-ending settings. Declared
UTF-8 text members are normalized to LF before link processing and ZIP
construction, while PDF members are preserved byte-for-byte. In a Git
checkout, every allowlisted member must also be tracked; an extracted archive
without Git metadata remains a supported rebuild root.

Build the archive from a supported CPython 3.11 or 3.12 environment after
following [REPRODUCTION.md](REPRODUCTION.md):

```powershell
$env:PYTHONUTF8='1'; python scripts/build_portable_publication_archive.py
Expand-Archive dist/PHASEMAP-portable-publication-archive.zip extracted
Set-Location extracted
$env:PYTHONUTF8='1'; python -m pytest -q tests/simulation/test_simulator_smoke.py tests/theory tests/simulation/test_s074_gpu_trajectories.py tests/simulation/test_s074_precision_statistics.py tests/simulation/test_s074_precision_study.py tests/integration/test_validation_registry.py tests/integration/test_g7_publication_contract.py tests/integration/test_submission_archive.py tests/integration/test_fnl_submission.py tests/integration/test_s074_publication.py tests/integration/test_s074_richardson.py
```

The archive includes the Markdown manuscript, the public FNL article,
supplement, and general-summary sources with their official class, retained
REVTeX sources, and vector-PDF figure assets. It deliberately excludes the FNL
cover letter and both submission-metadata files: they are local journal-workflow
materials, not public reproducibility payload. The
revised article uses two native tables and one transport figure; the older
classifier graphic assets remain as historical reference material. The smaller
FNL source-only ZIP includes just the referenced transport figure PDF.
The exact validated R2 code/data archives are published as version 3.2.0rc2 at
[Zenodo, DOI 10.5281/zenodo.22581850](https://doi.org/10.5281/zenodo.22581850).
The historical DOI-only R3 submission carrier reuses those exact ZIPs and supplies updated
FNL manuscript sources separately. Rebuilding the portable archive from R3
will include its updated citation metadata and is not claimed to reproduce the
pre-DOI R2 ZIP hash. Neither version alters the published v3.1.1 GitHub release,
its Zenodo record, or any frozen S-071/S-073 artifacts.
The current FNL-R6B archive is `PHASEMAP_FNL_R6B_Reproducibility.zip`,
prepared for DOI `10.5281/zenodo.22924890`. It supplies current manuscript
sources and keeps scientific software version 3.2.0rc2. The numerical-record
ZIP remains byte-identical. Earlier R2/R3 statements describe those snapshots.
The documented validator deliberately excludes Git-lineage tests: they audit a
frozen Git candidate and are not portable to a metadata-free extracted archive.

## Manuscript PDF QA

Build and inspect both locally rendered candidate PDFs with:

```powershell
python scripts/build_manuscript_pdf.py
```

This requires `latexmk`, `pdflatex`, a Chromium browser, `pdfimages`,
`pdffonts`, `pdftotext`, and `pdftoppm`. The command converts the accepted SVG
figures to vector PDFs, compiles the main article and supplement, and fails if
a figure contains raster image objects, a font is Type 3 or unembedded, text
extraction is empty, or page rendering produces no PNG. Review every page in
`dist/PHASEMAP_Main_Manuscript_pages/` and
`dist/PHASEMAP_Supplemental_Material_pages/` before any submission decision.

## FNL submission build

Run `python scripts/build_fnl_submission.py` for the FNL manuscript,
supplement, cover letter, general summary and self-contained LaTeX source ZIP.
The four PDFs are written to `dist/FNL_SUBMISSION/`; page images for inspection
are written to `dist/FNL_QA/`. The builder always uses the supplied vector
figures; `--skip-figures` is accepted as an explicit automation flag. The
source ZIP can be extracted and compiled independently
with `latexmk -pdf` from its `manuscript/journal/fnl/` directory.

That four-PDF builder requires the private cover-letter source and is intended
for the author's complete submission-source ZIP. In this public archive,
compile `PHASEMAP_FNL.tex`, `PHASEMAP_FNL_Supplement.tex`, and
`PHASEMAP_FNL_General_Summary.tex` individually with `latexmk -pdf` in
`manuscript/journal/fnl/`. No cover letter or referee metadata is published.

The exact archived test command and collected count are generated in
`ARCHIVE_MANIFEST.json`. Expensive stochastic production is not
part of this reproduction command. Immutable numerical result records are
supplied separately with the review materials.

The S-074 successor adds the exact GPU producer, both prospective plans and
the resource-only extension, CPU statistical/matrix checks, and the
results-to-table/figure renderer. The manifest's portable test command now
includes those focused suites. GPU comparisons are explicitly skipped on a
machine without CuPy/CUDA; the recorded GPU qualification is separate.
Raw evidence is not duplicated inside the code ZIP. Extract the numerical
records beside it as described in [S074_REPRODUCTION.md](S074_REPRODUCTION.md).

The post-result Richardson amendment, CPU reanalysis script, nonlinear paired
jackknife regressions, all 80-row diagnostics and the separately identified
reanalysis outputs are included. These do not replace the original primary
results in the numerical archive. CSV files are declared UTF-8 text and use
the same canonical LF policy as other text; binary accumulator files remain
byte-exact in the numerical archive.
