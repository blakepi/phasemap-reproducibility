# F-050 figure provenance manifest

**Task result:** PASS
**Contract:** v0.4
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Canonical source hashes

All text hashes below are calculated from UTF-8 bytes after normalizing line
endings to LF, so they are stable across Git checkouts.

| Accepted source | SHA-256 |
|---|---|
| `artifacts/derived/B-040-central-claim.md` | `af7590a716286eb0af7cfdc11caeb7c7993643acb225137bed1ba28902ac4004` |
| `artifacts/derived/S-021-validation-matrix.md` | `0756ede891c36341a382e951dc7ac0af38e0bdd46563430d3f5a13c6a0480dbf` |
| `docs/scientific-contract/CONTRACT.md` | `f85159ebadf97942ab271a17d34501ce91263945645ebaf946bd765a2105d14c` |

| Generation script | SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `0542a2fcfa9644c4480a4813f4f0f21373bde1f7206e99a964af8b0953d89c3a` |

## Generated figure hashes

| Figure | SHA-256 |
|---|---|
| `figures/F-050-all-seven-structural-map.svg` | `cd40fb3171adafb0ba59e8822192140de89a49ce2f2d05a6d99d67290aaf8a13` |
| `figures/F-050-s021-validation-coverage.svg` | `ffec69bbe3dd5acd4892633898da75ba3a699ad9e4f7761061f7400ba066e492` |

## Claim map

| Figure | Allowed claim | Scope and evidence boundary |
|---|---|---|
| `F-050-all-seven-structural-map.svg` | Every distinct pair is exactly distinguishable on the complete component-level second-order record. | `M>0`, `rho>0`, `Pe>=0`; the displayed nonoverlapping `12 + 6 + 3` analytic witness partition supports the claim. Position-toggle matches are sector identities, not protocol equivalence. |
| `F-050-all-seven-structural-map.svg` | Position-reset toggles preserve the complete internal `(v,u)` process while spatial transport changes to localization. | `PV/V`, `PTheta/Theta`, and `PVTheta/VTheta`; no internal higher-order discriminator is implied. |
| `F-050-all-seven-structural-map.svg` | `PV/PVTheta` have equal `Tr(S)=E|v|^2`, `Tr(C)=E[r dot v]`, and `Tr(R)=E|r|^2`. | Contracted-observable degeneracy only. Their centered spatial traces differ for `Pe>0`; orientation and component records separate the pair throughout `Pe>=0`. |
| `F-050-s021-validation-coverage.svg` | The locked independent finite-grid matrix validated all 91 numeric gates and 15,652 formula rows. | S-021 supports accepted exact theory but does not prove continuum-wide equality/inequality or establish a higher-order claim. |

No optional higher-order/distributional result is represented. Raw MSD and centered covariance are distinct throughout.
