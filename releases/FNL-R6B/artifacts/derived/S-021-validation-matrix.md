# S-021 all-seven second-order validation matrix

**Task result:** PASS

## Locked route and claim boundary

The result-free plan
`experiments/S-021-all-seven-moment-validation-primary-v1.json` fixes an
independently hand-coded 28-state Itô-plus-jump moment operator for all seven
deterministic reset maps. The numerical operator imports no PHASEMAP theory or
simulation module, performs no file access, and reads no prior result artifact.
It constructs every between-reset row and every reset pullback directly from
the contract's SDE and reset maps.

The separate comparison adapter is loaded only after the isolated numerical
outputs, residuals, algebraic solutions, and matrix hashes have been computed.
That adapter evaluates the accepted T-022 formula registry at 100 decimal
digits and, for `PVTheta`, independently evaluates the accepted T-012
complete-reset baseline.

This route is finite-grid numerical support for the accepted exact
second-order classification. It does not establish continuum-wide formulas,
exact equivalence between protocols, event sequencing, or any higher-order
claim.

## Immutable execution and provenance

- Plan commit:
  `6b55111d39e5e6fea8b65e58054692ffa3133e3b`.
- Frozen plan file SHA-256:
  `c648a3863c85767f43c49a6e315ccf8b599105c3f81c0c5fc4678522f91f1aeb`.
- Frozen plan semantic SHA-256:
  `56106349142a6710a6dc32f5af6d76356d132655367020cda6ec4f5cf2198422`.
- Clean implementation/source commit:
  `2f951c562aea217b985fc11059cdac305e0603f9`.
- Canonical raw artifact:
  `artifacts/raw/S-021-all-seven-moment-validation-primary-v1.json`.
- Canonical raw byte count: `25,375,107`.
- Canonical raw SHA-256:
  `0549abdd17901b468b5afd30bb4aa623d6ed47cf3c4bd711cc5eafc5c3a10996`.
- Independently recomputed canonical payload SHA-256:
  `e1bd56727edf5c74a3b791cd5edccfc30348bb5fdfa383ab1c6a7fc04184b96a`.
- Source manifest: all `17/17` recorded paths matched the committed bytes.

The canonical command was invoked exactly once from the clean source commit:

```text
.venv\Scripts\python.exe experiments\run_s021_all_seven_validation.py run experiments\S-021-all-seven-moment-validation-primary-v1.json
```

It completed in 248 seconds and atomically created the canonical path. The
runner prohibits overwrite, retry, alternate canonical output, and execution
from a dirty source tree. No second execution was attempted.

## Frozen matrix

The artifact contains all `91` protocol/case records:

- seven protocols: `P`, `V`, `Theta`, `PV`, `PTheta`, `VTheta`, `PVTheta`;
- thirteen exact-rational active, passive, resonance, above-resonance, and
  finite-inertia overdamped-support cases;
- four fixed cells per record: decimal precisions `50/80` crossed with scaled
  horizons `64/80`;
- one stationary probe for each of the `52` position-containing records; and
- four polynomial probes `0`, `1/2`, `2`, and `8` for each of the `39`
  transport records.

Every non-null T-022 scalar and Cartesian component is gating. Each row records
all four reference errors, both fixed-precision differences, both fixed-horizon
differences, and the finest propagation-versus-algebraic cross-check.

| Protocol | Records | Gating T-022 rows | Largest cell error | Largest precision difference | Largest horizon difference | Largest algebraic cross-check |
|---|---:|---:|---:|---:|---:|---:|
| `P` | 13 | 754 | `3.942e-25` | `8.590e-50` | `3.942e-25` | `6.931e-32` |
| `V` | 13 | 4,212 | `4.170e-26` | `1.213e-47` | `4.170e-26` | `5.848e-33` |
| `Theta` | 13 | 4,212 | `2.314e-24` | `2.041e-47` | `2.314e-24` | `3.932e-31` |
| `PV` | 13 | 754 | `1.231e-26` | `3.837e-50` | `1.231e-26` | `1.732e-33` |
| `PTheta` | 13 | 754 | `4.790e-27` | `1.103e-49` | `4.790e-27` | `5.390e-34` |
| `VTheta` | 13 | 4,212 | `3.923e-23` | `4.414e-47` | `3.923e-23` | `1.083e-29` |
| `PVTheta` | 13 | 754 | `4.414e-27` | `3.037e-49` | `4.414e-27` | `4.967e-34` |

All `15,652/15,652` T-022 formula rows validated at the locked absolute
tolerance `1e-12`; none was unresolved or contradicted. All `91/91` numeric
gates validated. The global maxima were:

- formula/reference cell error: `3.9228287380124944e-23`;
- arithmetic-precision difference: `4.4135261387789055e-47`;
- fixed-horizon difference: `3.9228276546835499e-23`;
- finest propagation/algebraic difference: `1.0833289445797574e-29`;
- invariant discrepancy: `1.0542197943230523e-81`; and
- largest all-cell position and transport residuals:
  `1.0006345117365164e-50` and `1.037961080188892e-47`;
  the largest finest-cell residual was `7.6062073166203969e-78`.

These are below the locked formula/refinement ceiling `1e-12` and the
position/transport residual ceilings `1e-40` and `1e-30`.

## Complete-reset and mandatory-limit gates

For all thirteen `PVTheta` cases, the independent T-012 layer supplied `754`
gating component/scalar rows. All `754/754` validated. Its largest cell error
was `4.4136875707898514e-27`, and its largest propagation/algebraic
cross-check was `4.9669510193505826e-34`.

| Mandatory group | Stored scope | Result |
|---|---|---|
| Complete reset | all 13 `PVTheta` cases plus full T-012 field gate | validated |
| Passive | 7 protocol sequences and passive endpoint pair equalities | validated |
| Rare reset | 10 declared scaled-observable sequences | validated |
| Frequent reset | 9 declared scaled-observable sequences | validated |
| Resonance | all fields at `M=1` and `M=2` for all 7 protocols | validated |
| Strict overdamped trend | 11 declared finite-inertia sequences | validated |

All seven passive discrepancies decreased strictly along
`Pe=6/5,3/5,3/10,0`; the largest terminal discrepancy was
`1.2032342585636101e-34`, and every passive endpoint pair equality met the
locked tolerance. All ten rare-reset, nine frequent-reset, and eleven
finite-inertia overdamped-support series satisfied their exact preregistered
trend dispatch. These finite sequences support, but do not replace, the
contract's singular-limit interpretation.

## Authentication and review

The result-free implementation passed two independent pre-execution audits,
the 35 focused S-021 tests, the complete 328-test repository suite,
control-pack validation, task-graph validation, validation-registry
validation, strict plan/source authentication, and a static isolation audit.

After execution, the raw byte hash, plan hashes, payload hash, source commit,
all source-manifest entries, grid completeness, stored discrepancy
classifications, T-012 gate, limit dispatch, and scientific claim boundary
were independently rechecked by two read-only reviewers without rerunning the
canonical grid. Both returned PASS with no blocking finding.

The artifact contains no binary JSON floating-point values for scientific
quantities; finite numerical values are stored as 50-significant-digit decimal
strings. The retained-high-precision serialization path has a regression test
that serializes a 100-digit value from a default-precision caller without
precision loss.

The first post-execution packaging check found one lifecycle-only test defect:
the result-free validate-mode test asserted that the canonical path must remain
absent forever. The acceptance change made that test phase-invariant by hashing
the before/after canonical bytes and still forbidding any publication call.
No plan, operator, adapter, runner, canonical byte, numerical value, or
classification changed, and the raw artifact continues to identify the exact
clean execution-source commit above.

## Disposition

S-021 is accepted as independent implementation-path numerical support for the
all-seven exact second-order theory. Its overall classification is
`validated`; there is no BL2 provenance failure, BL3 scientific
contradiction, or unresolved second-order discrepancy. This closes S-021's
dependency edge and permits the independent V-020 classification/equivalence
review. It does not itself select a G4 higher-order target or establish a
higher-order inequivalence.
