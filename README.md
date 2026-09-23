# PHASEMAP

## Current archive: FNL-R6B.1 (packaging correction, 23 September 2026)

[Corrected archive DOI 10.5281/zenodo.22925278](https://doi.org/10.5281/zenodo.22925278)
and [current source tree](releases/FNL-R6B.1).
Start with [the packaging README](releases/FNL-R6B.1/docs/release/FNL_R6B1_PACKAGING_README.md).
This adds two already-public dependencies omitted from R6B's standalone ZIP,
preserves original figure-provenance hashes and tests the actual extracted
figure-reproduction command. No scientific code, numerical records, figures
or manuscript/PDFs changed; software remains 3.2.0rc2. The unchanged paper
retains the R6B DOI. Earlier directories and archives below remain historical.

Corrected code ZIP SHA-256:
`4940d0e17a005a02136746a04be711aacd91923e667ba144a22e02fa88344919`.
Research content commit `9c0608678b370db18ea7c7214895865898d955e1`;
presentation commit `2255f94ae2fbcf4ddd0098db21a9656e447004be`.
No journal submission is implied.

## Historical manuscript release: FNL-R6B (23 September 2026)

Current manuscript, supplement and reproducibility archive:
[Zenodo DOI 10.5281/zenodo.22924890](https://doi.org/10.5281/zenodo.22924890).
The corresponding current source tree is [releases/FNL-R6B](releases/FNL-R6B).
Software version remains 3.2.0rc2. Run the portable test command in that
directory's ARCHIVE_MANIFEST.json, and follow its docs/release/S074_REPRODUCTION.md.
The new directory is an exact extraction of the current public code ZIP;
earlier repository files below remain historical and are not the current paper.

R6B preserves every numerical record and figure. The raw-finest S-074 analysis
already contained 80/80 intervals, with 0 contradicted and 78/80 stricter design
targets met. Paired Richardson estimates use the same retained trajectories,
with their adoption chronology disclosed. S-071/S-073 remain unresolved,
unpooled historical evidence. No new sampling or journal submission.

Public code ZIP SHA-256:
`ecd62b7fa3b787e4514763bfc4271b855a02d66adeca30327d059ade5109341b`.
Source commit in the research repository:
`5dbfeec5a9af16d319f74bbfff0e6941f90304ef`; presentation commit:
`d38c159bc340d70370efb5427a7553190889721b`.

## Historical v3.1.1 repository description

PHASEMAP provides the exact second-order classification, software, numerical
records, figures, and manuscript sources for all seven nonempty deterministic
reset maps of a two-dimensional inertial active Brownian particle.

This public repository is a curated derivative of the immutable G7 candidate,
not the private project-control repository. Scientific files were exported from
tag `g7-major-revision-candidate-2026-08-01` at commit
`2c4dd609f230715c0eb148e874591f7ff38aa897`. The frozen scientific/content
source is `254d51bccaae68b227972f7b6dd3b54bec25cbfe`.

## Main result

At matched `M > 0`, `rho > 0`, `Pe >= 0`, initialization, reset targets, and
symmetry conventions, all 21 distinct pairs of nonempty reset maps have
different complete component-level second-order records. Three position-toggle
pairs preserve the complete internal `(v,u)` process while differing in their
spatial sector.

## Evidence boundary

- The exact classification is analytic.
- The independent S-021 finite-grid moment calculation validated all 91
  prespecified checks and 15,652 formula rows.
- Both trajectory attempts remain quantitatively unresolved and are published
  without pooling, retrying, top-up, or reinterpretation: S-071 is
  14/46 validated, 32/46 unresolved, 0 contradicted; S-073 is 32/46 validated,
  14/46 unresolved, 0 contradicted.
- Only qualitative trajectory evidence is retained: signs/equalities,
  Richardson convergence, sector identities, and reference-scope checks.

## Repository map

- `manuscript/`: article, technical supplement, and compiled publication files.
- `src/phasemap/`: analytic and numerical implementation.
- `experiments/`: fixed plans and experiment drivers.
- `artifacts/raw/`: immutable numerical outputs.
- `artifacts/derived/`: publication-relevant derivations and validation reports.
- `figures/`: deterministic publication figures.
- `docs/scientific-contract/`: model and validation definitions.
- `tests/`: complete deterministic test suite.

## Reproduce

See `docs/release/REPRODUCTION.md`. The canonical scientific environment was
CPython 3.12.13; the independent clean-room environment was CPython 3.12.10.
The declared supported range is Python 3.11-3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
```

## Citation

Use `CITATION.cff`. The archived release is available at
[doi:10.5281/zenodo.21856419](https://doi.org/10.5281/zenodo.21856419).

## Authors

G. Blake Pierpoint (corresponding author), Olivier Bernard, and Yichen Liu.

## License

Software is released under the MIT License. Manuscript text, figures,
documentation, and research-data records are released under Creative Commons
Attribution 4.0 International. See `LICENSES.md`.
