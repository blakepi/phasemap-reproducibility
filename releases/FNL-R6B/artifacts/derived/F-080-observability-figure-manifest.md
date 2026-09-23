# F-080 observability figure manifest

**Task result:** reproducible exact-theory curves and source-bound measured symbols when available
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Accepted immutable inputs

| Source | Canonical-LF SHA-256 |
|---|---|
| `artifacts/derived/T-080-exact-observability-theorem.md` | `abfd0b472b8476188fe7a827c2c9d20f5971ce3f0e7ad4426814a40835854278` |
| `artifacts/derived/S-071-trajectory-validation.md` | `9d14631678b83dd4be590c957ad5fba8aa88c460fab7f477f95791c0b1dcb52f` |
| `artifacts/derived/S-073-trajectory-replacement-validation.md` | `5074dc0a02f3e378cb0f645ee4f1ced29743d336c7d85313238172f64d2ffb60` |

| Generator | Canonical-LF SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `0542a2fcfa9644c4480a4813f4f0f21373bde1f7206e99a964af8b0953d89c3a` |

## Generated panels

| Figure | SHA-256 |
|---|---|
| `figures/F-080-three-coordinate-decoder.svg` | `33e88e14a8bc1f7127d9b00740cca9f2a5e75b82fe16bb45db4064fde1a83954` |
| `figures/F-080-strict-subsignature-classes.svg` | `f807d04c035bbfebacb2c7a5e9eff527e96f792370384fd3aa036b9e3d68a47f` |
| `figures/F-080-transport-localization.svg` | `c4b9f80b45dbff2d68201f28daf5cb63b876408ea0ba2d331c1908bc3efba2e2` |

## Claim scope

| Figure | Allowed claim and boundary |
|---|---|
| `F-080-three-coordinate-decoder.svg` | Exact matched-parameter injectivity of `(G, Uxx, Tr S)` on the seven nonempty reset maps for `M>0`, `Pe>=0`, `rho>0`. It is not a finite-time, noisy, cross-parameter, or global-minimality claim. |
| `F-080-strict-subsignature-classes.svg` | Exact equality classes of proper observable projections. These are not protocol, full-record, or process equivalences. The passive/resonant `Tr S` degeneracy does not defeat the full decoder. |
| `F-080-transport-localization.svg` | Exact stationary centered-variance curves for localized protocols, plus exact `D_eff` and mean-drift curves for non-position protocols. The tuned `V`/`Theta` diffusion coincidence is broken by mean drift. S-074 symbols, when available, are measured estimates with one-standard-error bars, not sampled theory values. |

S-071 and S-073 are immutable, unresolved quantitative trajectory attempts;
they are provenance-only and are not represented in any visible panel. They
are not pooled with the separately authorized S-074 precision study.
S-074 measured-symbol source: `artifacts/derived/S-074-figure-points.json`; canonical-LF SHA-256 `21db0b09d27bfa0be726abbb1313d72b780f0039baf98269efae3168dd8b7fd3`.
The displayed estimator is the explicitly post-result paired Richardson reanalysis, adopted after observing finest-step bias. Reanalysis results SHA-256 `4f2d5dfcbb6e457e10717a68eae19c3e42d461d90ae0c08114294a275fae60f5`; immutable raw-primary results SHA-256 `08573e429b4816a87f24f556035173ab4aeb48ae466f52e774446ba3f44b4137`. Both original stricter planning-SE misses remain disclosed.
The S-074 pointwise precision and agreement results are reported in its study
record; symbols do not imply simultaneous coverage or parameter inference.
Every measured abscissa is an exact theory-curve node. The drawing grid is
densified while preserving all earlier formula nodes and their exact values;
no measured estimate or uncertainty is moved to improve visual agreement.
Every SVG has accessible title/description metadata and color-independent
labels. The paper's transport figure has no visible global title, subtitle,
or scope box; parameters and scope belong to its caption. Panel d uses a
shared mass axis, diffusion on the left and drift on the right. Negative
measured drift and its uncertainty are retained rather than clipped to zero.
Rate axes in panels a-c and the variance axis in a are logarithmic; sampled
rates and masses are labeled explicitly without changing the theory arrays.
