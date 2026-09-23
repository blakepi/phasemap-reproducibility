# S-071 all-seven direct-trajectory validation

**Task result:** BLOCKED — fixed production plan completed with aggregate
classification `unresolved`.

## Locked execution and provenance

The exact V-071-approved plan was executed once from clean source commit
`dad4ad08a9a6c379e309d541e9223f5de6f90514`:

```text
.venv\Scripts\python.exe experiments\run_s070_all_seven_trajectory_validation.py run experiments\S-070-all-seven-trajectory-validation-primary-v1.json
```

The command completed the fixed stochastic work in approximately 847 seconds,
wrote the canonical result, then exited with status `1` because the aggregate
classification was unresolved. This is the runner's intended fail-closed
behavior.

- Plan ID:
  `S-070-all-seven-trajectory-validation-primary-v1`.
- Plan version: `2.0.0`.
- Locked raw plan SHA-256:
  `06942ac935d31fc6c8244c4cbe947a31a4636b94374c889c796cf6212b167330`.
- Locked semantic plan SHA-256:
  `26c014473f959b2f7beb73a6c3f2a550d0e7ece41c6fad7e53fde416c27354ed`.
- Reviewed source-manifest SHA-256:
  `71acca668a5358bc02c905ef0be2f788a534a7a084f831597dbd2633d9bf6ac2`.
- Canonical raw result:
  `artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.json`.
- Raw result byte count: `109,533`.
- Raw result SHA-256:
  `5f765d9a8d7805d9081ac6d55e60e725e1b02f0684e5cfe2a21ad9a00b07b0a8`.
- Write-once attempt sentinel:
  `artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.attempt.json`.
- Attempt-sentinel byte count: `2,622`.
- Attempt-sentinel SHA-256:
  `a523b6135853383213bfecec2193c3b9a1a59982d15572852d594c9b2126cda9`.
- Sentinel creation time:
  `2026-07-30T11:08:13.461166+00:00`.
- Runtime: CPython `3.12.13`, NumPy `2.5.1`, Windows 11 AMD64.

The resource preflight passed before the sentinel and first stochastic draw.
It recorded 130,879,098,880 free disk bytes and 14,916,882,432 available
memory bytes against floors of 1.5 GB and 1.0 GB. The runner also authenticated
the fixed update, reset-event, bootstrap-draw, and temporary-storage caps.
The fixed execution completed 557,056 trajectories in 136 chunks: 458,752
main trajectories and 98,304 independent confirmation trajectories, containing
17,835,146 reset events.

## Exact outcome

| Required group | Validated | Unresolved | Contradicted | Total |
|---|---:|---:|---:|---:|
| Direct analytic-reference comparisons | 2 | 19 | 0 | 21 |
| Paired headline contrasts | 2 | 4 | 0 | 6 |
| Unpaired confirmations | 0 | 9 | 0 | 9 |
| Pathwise sector-identity checks | 3 | 0 | 0 | 3 |
| Reference-scope checks | 7 | 0 | 0 | 7 |
| **All required items** | **14** | **32** | **0** | **46** |

The validated direct comparisons were `MAIN_P_speed_direct` and
`H4_PVTheta_r_dot_v_direct`. The validated paired headline contrasts were
`H2_Theta_minus_V_v_x` and `H2_VTheta_minus_V_v_x`.

All 36 applicable fine/coarse discretization classifications validated. All
36 required sign or equality classifications validated. All 18 applicable
bootstrap-standard-error stability diagnostics validated; the largest
relative deviation was `0.05524`, below the locked `0.10` ceiling. All three exact
pathwise internal-sector identities and all seven reference-scope checks
validated. No convergence, sign, identity, provenance, resource, or scientific
contradiction was recorded.

The 32 unresolved items arise from the preregistered quantitative rule: the
Monte Carlo discrepancy interval expanded separately by `B_window` and
`B_disc` was not wholly contained within the fixed admissible margin. The
nominal interval was inside the margin for 12 rows before those required
envelopes were added; the other 20 rows already overlapped a margin boundary.
The unpaired confirmations were particularly imprecise relative to their
locked margins. The result therefore supports the expected signs, sector
identities, reference scope, and discretization behavior, but it does not
validate the planned quantitative all-seven trajectory claim.

## Post-run integrity review

Root and a fresh read-only reviewer independently parsed both JSON artifacts,
recomputed their byte hashes, authenticated the source commit, plan hashes,
reviewed source-manifest hash, fixed configuration, row uniqueness, and
classification totals, and checked the sentinel. The integrity disposition
was PASS. The scientific disposition remains `unresolved` with a hard stop.
Neither review reran stochastic work or modified either raw artifact.

## Fail-closed disposition

The attempt sentinel records `retry_authorized: false`. The plan and runner
prohibit a retry, top-up, alternate output, second final evaluation, tier
change, or post hoc margin change. The unresolved result may be used only as
disclosed design information for a separately authorized and preregistered
replacement; it may not be pooled into replacement evidence.

S-071 is blocked at the project's human pivot gate. Manuscript reconstruction,
scientific-figure reconstruction, integrated audit, clean-room reproduction,
and the new G7 candidate freeze remain downstream-blocked. The accepted
constrained-frame correction, exact G2–G6 theory, S-021 deterministic
all-seven numerical evidence, and the rejected candidate preserved as the
technical baseline are unaffected.
