# F-070 scientific figure provenance manifest

**Task result:** PASS — scope-bounded qualitative trajectory evidence only
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Accepted inputs

| Accepted source | Canonical-LF SHA-256 |
|---|---|
| `artifacts/derived/T-070-constrained-moment-frame.md` | `d8318b37af140660baf64fd062b88f3f00c7494012e440d310696a2587add79b` |
| `artifacts/derived/S-073-trajectory-replacement-validation.md` | `5074dc0a02f3e378cb0f645ee4f1ced29743d336c7d85313238172f64d2ffb60` |

| Generation script | Canonical-LF SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `49507b263f6cc469ea1cb69ad9a05fe3cc0987aee53d52aae320fce7eb66ee01` |

## Generated figure hashes

| Figure | SHA-256 |
|---|---|
| `figures/F-070-reset-lattice-and-classifier.svg` | `f91f438e5d52f078ede99e8d83999aeb837c8cc164ee208e2458233345f8a8a9` |
| `figures/F-070-physical-transport-and-degeneracies.svg` | `22664e2f5bb30f3ee4fa58ba40ba6813161f8717178ba5c5f6c920ac322a8541` |
| `figures/F-070-qualitative-trajectory-evidence.svg` | `776cd8fabeef7390f96e18fd01364a992251bcad4de093a9fa285bce6488df25` |

## Scientific scope and accessibility

| Figure | Allowed claim and boundary |
|---|---|
| `F-070-reset-lattice-and-classifier.svg` | The seven nonempty maps and exact full-record `12 + 6 + 3` witness partition. Scope: `M>0`, `rho>0`, `Pe>=0`; restricted identities are not protocol equivalence. |
| `F-070-physical-transport-and-degeneracies.svg` | The physical 28-coordinate frame and exact transport/identity scopes. Raw `E|r|^2` and centered `Cov(r)` are distinct quantities. |
| `F-070-qualitative-trajectory-evidence.svg` | S-071 reached 14/46 and S-073 reached 32/46 validated items, with neither contradicted. It displays only validated signs/equalities, Richardson convergence, sector identities, and reference scope. |

Every SVG has a title and plain-language description. The S-073 fixed attempt
is integrity/classification valid but scientifically unresolved for the
quantitative all-seven trajectory claim: 14/46 gating items remain unresolved.
The figures do not represent a retry, pooling, threshold change, or quantitative
all-seven trajectory validation.
