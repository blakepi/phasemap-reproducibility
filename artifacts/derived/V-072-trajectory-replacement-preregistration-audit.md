# V-072 trajectory-replacement preregistration audit

**Disposition:** PASS

This is a fresh, result-free re-review of corrected S-072 plan version `1.0.1`.
The earlier independent `REVISE` finding remains preserved in Git at
`661a9a2809ffa860b3cd84c0b88f337b383908fa`; it was not treated as approval.
The exact source reviewed here is
`b9caa1fcbb1d8244a1b65d7794b0c56be8212dfa`. Current review HEAD
`70d4a2b36f1c85a692ceb6292e13288c4874dc2d` changes only status/handoff
records: the reviewed source is its ancestor and every authenticated path is
unchanged between the two commits.

## S-072 production acceptance
S-072_AUDIT_ACCEPTANCE {"disposition":"PASS","plan_canonical_lf_sha256":"a0d3ea4f91e0c9bdbfd3a4c1a61af077a01e09d31e20e65821a0aebe8cabfd35","plan_id":"S-072-all-seven-trajectory-replacement-primary-v1","plan_semantic_sha256":"5787bf3ff0e3ec532b0fa8952912b8d8239a59ff7de7a8c36e9ffdb2a0a7e24d","plan_version":"1.0.1","reviewed_manifest_sha256":"49f0fb1c4fe918cb1d3dc23bfee3a48f514a8ed3ca09a3c90045863219f32808","reviewed_source_commit":"b9caa1fcbb1d8244a1b65d7794b0c56be8212dfa"}

## Authentication correction

The prior blocking defect is closed. The canonical manifest has 31 unique
entries and authenticates Contract Section 7, the registry, schema and
validator, the plan, reference adapter, runner, focused tests, `pyproject.toml`,
the pinned runtime requirements, and every Python file under `src/phasemap`.
This includes the complete transitive first-party reference closure, notably
`formula_registry.py`, `nonposition_protocols.py`, and
`position_protocols.py`. Independent enumeration found every one of the 31
entries changes the manifest digest when its hash is perturbed, and every
current canonical source blob is identical to the blob at the reviewed commit.

The acceptance record binds both the full manifest digest and the exact
reviewed source commit. Production additionally requires a clean execution
commit descended from that commit, with no difference on any manifest path;
the same manifest, commit, and runtime versions are rechecked after computation
and before write-once publication. NumPy `2.5.1` and SymPy `1.14.0` are pinned,
validated in the active environment, included through the requirements lock,
and recorded with Python/platform provenance in the result.

## Independent scientific and statistical review

- The conditional translational transition is correct for the locked SDE:
  `a=exp(-dt/M)`, `b=M(1-a)`, `q_vv=(1-a^2)/M`,
  `q_rv=(1-a)^2`, and
  `q_rr=2dt-4M(1-a)+M(1-a^2)`. Independent deterministic evaluation confirmed
  positive-semidefinite noise covariance over event-sized and all three fixed
  step scales.
- All seven reset maps zero exactly the selected conditional means and
  covariance blocks. Exact reset clocks split integration at events, and the
  finest, middle, and coarse levels share clocks and nested rotational Wiener
  increments. Translational Wiener noise is analytically marginalized; no
  component-2 RNG exists in production.
- Scalar observables add the exact conditional noise moments. Centered spatial
  covariance is the mean conditional covariance plus the unbiased covariance
  of conditional means. Every nonlinear spatial statistic is recomputed from
  complete conditional-path sufficient features inside each bootstrap
  replicate, including recentering and the full `D_eff` fit. No naive
  repeated-time OLS standard error is exposed.
- Primary and secondary first-order Richardson estimates are fixed as
  `2*Y_h-Y_2h` and `2*Y_2h-Y_4h`. Their matched difference divided by three is
  the leading primary residual-error estimator; `B_disc` is the maximum
  absolute endpoint of its matched interval. `B_window` remains separate.
- Bootstrap uncertainty uses 2,048 fixed whole-unit replicates in batches of
  eight with four fixed 512-replicate stability blocks. The normal-equivalent
  tier quantile is applied to the bootstrap standard error; no percentile tail
  is estimated and failed stability is unresolved without more work.

## Registry, estimands, seeds, and resources

The approved registry and Contract Section 7 are unchanged. Their locked
semantic hashes and Section 7 hash validate exactly. The three evidence tiers,
15 observable classes, scale dispatch, normalized floor `0.005`, primary
quantile `2.5758293035` and relative margin `0.01`, central-disputed quantile
`3.0` and relative margin `0.01`, expanded-interval classification, late-time
windows, and paired/unpaired requirements are preserved.

The replacement retains exactly 46 comparison IDs in 18 estimand families.
Independent comparison with the immutable S-071 plan found identical IDs,
tiers, observable classes, sign/equality requirements, compute-cap roles,
main count `65,536` per protocol, unpaired count `16,384` per required
protocol, and no change in registry margins. The only comparison-rule change
is the preregistered matched three-level Richardson residual replacing the old
two-level fine/coarse residual; it is method-specific bias control and does not
relax any acceptance threshold.

All 89 enumerated RNG domains are unique: 32 main reset/rotation domains, 48
protocol-independent confirmation domains, and nine bootstrap domains. They
use only components 1, 3, and 4 and fresh `7207...` base namespaces disjoint
from every S-071 `7007...` namespace. The runner has no S-071 artifact read,
pooling, retry, top-up, overwrite, or alternate-output route. The method is a
material conditional-moment/three-level replacement at unchanged sample
counts, not an S-071 retry or sample-size increase.

Resource arithmetic independently closes at 557,056 conditional units,
8,413,773,824 maximum three-level conditional segments, 4,706,009,088 maximum
rotational normal draws, zero translational draws, 1,140,850,688 bootstrap
trajectory-weight draws, and 260,113,956,864 maximum bootstrap feature
multiply-add terms. Fixed disk and memory preflights occur before the sentinel.

## One-shot and fail-closed controls

The audit marker, plan hashes, complete manifest, source commit, clean lineage,
runtime versions, resource floors, and absence of both canonical output and
sentinel are deterministic preconditions. The sentinel is created exclusively
and fsynced before the first scientific RNG construction; a crash leaves it in
place, and any concurrent or later attempt fails. There is one canonical
production command and one canonical output path. Any unresolved or
contradicted required row, adequacy failure, invariant failure, source drift,
or cap failure writes no alternative evidence and authorizes no retry, polling,
top-up, pooling, or threshold change.

At review start, S-073 output and sentinel were absent. S-071 remained
byte-identical at raw SHA-256
`5f765d9a8d7805d9081ac6d55e60e725e1b02f0684e5cfe2a21ad9a00b07b0a8`
and sentinel SHA-256
`a523b6135853383213bfecec2193c3b9a1a59982d15572852d594c9b2126cda9`.

## Result-free validation performed

- `.venv\Scripts\python.exe experiments\run_s072_all_seven_trajectory_replacement.py validate`
  passed with the exact plan hashes, 31-entry manifest digest, reviewed source
  commit, runtime versions, 89 seed domains, and no stochastic execution,
  reference loading, translational RNG, or S-071 artifact access.
- `.venv\Scripts\python.exe -m pytest tests\simulation\test_s072_trajectory_replacement.py -q`
  passed `41/41` tests.
- `.venv\Scripts\python.exe scripts\validate_validation_registry.py` passed
  three tiers, 15 observable classes, and Contract Section 7 SHA-256
  `65f1af81e0187de5daf45bf0857d6d757d01a3b9897442493fe22b9e6c69dd60`.
- `.venv\Scripts\python.exe scripts\taskctl.py validate` passed 50 tasks with
  `max_threads=4` and `max_depth=1`.
- Independent deterministic checks passed all 31 manifest-entry drift probes,
  reviewed-blob equality, all seven reset maps, covariance positivity,
  total-variance reconstruction, Richardson `/3` algebra, exact estimand and
  seed counts, resource arithmetic, and reviewed-source lineage.

No pilot, stochastic probe, production run, S-071 observation read, pooling,
retry, or top-up was performed. This PASS authorizes only the single
preregistered S-073 execution under the unchanged plan; it does not predict
that execution's scientific classification.
