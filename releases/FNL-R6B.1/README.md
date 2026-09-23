# PHASEMAP

PHASEMAP contains the research software, exact moment calculations, and
reproducibility checks for coordinate-selective resetting of inertial active
Brownian motion. The current submission candidate targets
Fluctuation and Noise Letters. The upload instructions are in
`docs/release/FNL_SUBMISSION_README.md`; the journal sources are in
`manuscript/journal/fnl/`.

## Supported Python versions

The package supports CPython 3.11 and 3.12. The exact dependency set is
locked in `docs/release/TESTED_CONSTRAINTS.txt`; interpreter markers retain
NumPy 2.4.6 on Python 3.11 and NumPy 2.5.1 on Python 3.12. FNL preparation
uses CPython 3.12.14. Earlier scientific validation used CPython 3.12.13, and historical R-060 clean-room closure used
CPython 3.12.10, and the release matrix tests CPython 3.11 and 3.12.

## Reproduce locally

Use the platform-neutral instructions in
[`docs/release/REPRODUCTION.md`](docs/release/REPRODUCTION.md). They install
the project with the locked constraints and run the smoke/core test set. The
successor archive and manuscript PDF QA procedures are documented in
[`docs/release/PORTABLE_PUBLICATION_ARCHIVE.md`](docs/release/PORTABLE_PUBLICATION_ARCHIVE.md).

## Release status

The 3.2.0rc2 candidate adds a fresh full-noise GPU trajectory study, S-074:
23,519,232 independent production trajectories across 41 parameter–protocol
cells. All 80 reported observables meet the requested 1% standard-error target
and pointwise interval-containment comparisons; all timestep checks pass.
Two additional, stricter design-SE targets were missed and remain explicitly
flagged. The original S-071/S-073 quantitative studies remain unresolved and
are not pooled with the new estimates. See
[`docs/release/S074_REPRODUCTION.md`](docs/release/S074_REPRODUCTION.md).
The publication table and 52 figure symbols use a separately documented
post-result paired Richardson reanalysis of the same preserved data. All
80 rows are retained; the original raw-primary results and both stricter
precision misses remain explicitly available.

The validated 3.2.0rc2 code and numerical records are published at
[Zenodo, DOI 10.5281/zenodo.22581850](https://doi.org/10.5281/zenodo.22581850).
That record preserves the exact pre-DOI R2 scientific snapshot. The R3
submission update adds this citation to the manuscript and administrative
metadata without changing the software, figures or numerical evidence. Its
delivered code/data ZIPs are byte-identical to the published files. The older
public GitHub v3.1.1 release remains a historical version; use the new Zenodo
record for S-074 reproduction. The corresponding author confirms no funding,
no competing interests and no arXiv posting.
Coauthor final-manuscript approval is separate from retrieved metadata. See
`docs/release/RELEASE_MANIFEST.json` for frozen-source provenance.

The MIT license applies to the original research software; research data and
authors' text/figures use CC BY 4.0, as specified in `LICENSES.md`.
World Scientific's
LaTeX class and bibliography style retain their supplied copyright notices.
The manuscript's publication agreement is separate from the software license.
