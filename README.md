# PHASEMAP

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
