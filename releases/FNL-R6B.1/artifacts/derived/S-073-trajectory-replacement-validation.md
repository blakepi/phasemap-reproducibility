# S-073 all-seven trajectory-replacement validation

**Task result:** BLOCKED — the single fixed production plan completed with
aggregate classification `unresolved`.

## Locked execution and provenance

The exact V-072-accepted plan was executed once from clean execution commit
`904e888dd229243e9cb35dda329c05437f03b464`:

```text
.venv\Scripts\python.exe experiments\run_s072_all_seven_trajectory_replacement.py run experiments\S-072-all-seven-trajectory-replacement-primary-v1.json
```

The command completed the fixed stochastic work in approximately 2,634
seconds, wrote the canonical result, then exited with status `1` because the
aggregate classification was unresolved. This is the runner's intended
fail-closed behavior.

- Plan ID: `S-072-all-seven-trajectory-replacement-primary-v1`.
- Plan version: `1.0.1`.
- Canonical-LF plan SHA-256:
  `a0d3ea4f91e0c9bdbfd3a4c1a61af077a01e09d31e20e65821a0aebe8cabfd35`.
- Semantic plan SHA-256:
  `5787bf3ff0e3ec532b0fa8952912b8d8239a59ff7de7a8c36e9ffdb2a0a7e24d`.
- Reviewed source commit:
  `b9caa1fcbb1d8244a1b65d7794b0c56be8212dfa`.
- Complete 31-entry source-manifest SHA-256:
  `49f0fb1c4fe918cb1d3dc23bfee3a48f514a8ed3ca09a3c90045863219f32808`.
- Canonical raw result:
  `artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.json`.
- Raw result byte count: `198,526`.
- Raw result SHA-256:
  `7c59fa6c4ce9d5cc4473fa995c54d78bb7cc53ef829a478deb66731b55c21076`.
- Write-once attempt sentinel:
  `artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.attempt.json`.
- Attempt-sentinel byte count: `3,350`.
- Attempt-sentinel SHA-256:
  `19e184ad92eed4a8f6e2549868387281bd9c46abcfc265b032e7a6e1ad26b279`.
- Sentinel creation time:
  `2026-08-01T07:23:36.830446+00:00`.
- Canonical output creation time:
  `2026-08-01T08:07:29.178551+00:00`.
- Runtime: CPython `3.12.13`, NumPy `2.5.1`, SymPy `1.14.0`,
  Windows 11 AMD64.

The resource preflight passed before the sentinel and first stochastic draw.
It recorded `117,212,852,224` free disk bytes and `8,452,657,152` available
memory bytes against floors of 3.0 GB and 2.0 GB. The fixed execution completed
557,056 conditional units in 136 chunks: 458,752 main units and 98,304 fresh
unpaired-confirmation units, containing 17,832,528 reset events. It used the
locked three-level conditional-moment method with zero sampled translational
normal draws.

## Exact outcome

| Required group | Validated | Unresolved | Contradicted | Total |
|---|---:|---:|---:|---:|
| Direct analytic-reference comparisons | 15 | 6 | 0 | 21 |
| Paired headline contrasts | 5 | 1 | 0 | 6 |
| Unpaired confirmations | 2 | 7 | 0 | 9 |
| Pathwise sector-identity checks | 3 | 0 | 0 | 3 |
| Reference-scope checks | 7 | 0 | 0 | 7 |
| **All required items** | **32** | **14** | **0** | **46** |

All 36 required sign or equality checks validated. All 36 matched Richardson
residual checks validated. All 18 applicable bootstrap-standard-error
stability checks validated; the largest relative deviation was `0.067916`,
below the locked `0.10` ceiling. The three `D_eff` rows used the fixed
2,048-replicate whole-trajectory bootstrap; OLS supplied only the slope point
estimate, never a naive repeated-time standard error. All three exact internal
sector identities and all seven reference-scope checks validated.

Seven rows failed expanded-interval containment and the separately locked
variance-reduction adequacy gate:

- `H4_PV_minus_PVTheta_centered_variance`;
- `H3_PV_minus_V_speed_unpaired`;
- `H3_PVTheta_minus_VTheta_speed_unpaired`;
- `H4_PV_minus_PVTheta_speed_unpaired`;
- `H4_PV_minus_PVTheta_raw_msd_unpaired`;
- `H4_PV_minus_PVTheta_r_dot_v_unpaired`;
- `H4_PV_minus_PVTheta_centered_variance_unpaired`.

Seven additional rows passed scientific interval containment but failed the
fixed adequacy gate:

- `H1_P_centered_variance_direct`;
- `H1_PV_centered_variance_direct`;
- `H4_PV_raw_msd_direct`;
- `H1_PTheta_centered_variance_direct`;
- `H1_PVTheta_centered_variance_direct`;
- `H4_PVTheta_raw_msd_direct`;
- `H2_VTheta_minus_V_v_x_unpaired`.

No sign, identity, convergence, bootstrap-stability, provenance, resource, or
scientific contradiction was recorded. Relative to immutable S-071, the fresh
replacement improved the validated total from 14/46 to 32/46, but the locked
contract requires every gating item to validate. It therefore does not
validate the planned quantitative all-seven trajectory claim.

## Post-run integrity and classification review

Root and two fresh read-only reviewers independently parsed both JSON
artifacts, recomputed their hashes, authenticated the plan, exact V-072 marker,
all 31 source-manifest entries, source and execution lineage, runtime,
registry, 89 fresh seed domains, resource arithmetic, all 46 unique IDs, and
every recorded classification. Integrity and classification arithmetic both
passed with zero discrepancies. No reviewer reran stochastic work or modified
the raw artifacts.

The immutable S-071 evidence remained byte-identical:

- raw SHA-256:
  `5f765d9a8d7805d9081ac6d55e60e725e1b02f0684e5cfe2a21ad9a00b07b0a8`;
- sentinel SHA-256:
  `a523b6135853383213bfecec2193c3b9a1a59982d15572852d594c9b2126cda9`.

The S-073 sentinel preceded the canonical output by `2,632.346598` seconds.
Exactly the canonical raw result and sentinel exist; no temporary, alternate,
retry, extra hardlink, or second task-ID artifact was found. The runner and
kernel contain no S-071 raw-artifact access path, and the recorded boundary
confirms that no S-071 observation was opened, used, or pooled.

## Fail-closed disposition

The attempt sentinel records `retry_authorized: false`. S-073 may not be
retried, topped up, pooled, polled for additional data, assigned an alternate
output, or reclassified by changing a tier, margin, window, or threshold.
S-073 is blocked at the post-failure human pivot gate.

M-070 manuscript reconstruction, F-070 figure reconstruction, I-070
integration, V-070 audit, R-071 clean-room reproduction, and M-071 candidate
freeze remain blocked. The exact G2-G6 results, S-021 deterministic evidence,
T-070 correction, P-070 release repair, immutable S-071 evidence, and rejected
G7 technical baseline remain unaffected. Any further quantitative trajectory
route would require an explicitly authorized, materially new, separately
preregistered methodology; otherwise the manuscript must be narrowed to the
qualitative trajectory evidence actually obtained.
