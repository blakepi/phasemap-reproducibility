"""Result-free unit and contract locks for the S-070 trajectory plan."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

from phasemap.common.model import ModelParams
from phasemap.simulation.protocols import PROTOCOL_REGISTRY, Protocol
from phasemap.simulation.trajectory_validation import (
    PairedPathConfig,
    classify_expanded_interval,
    effective_diffusion,
    project_primary_sample_size,
    simulate_paired_paths,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "experiments/run_s070_all_seven_trajectory_validation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("s070_runner_test", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


@pytest.fixture(scope="module")
def plan(runner):
    return runner.load_preregistered_plan(ROOT / runner.PLAN_REL)


def test_result_free_plan_validates_and_covers_all_seven(runner, plan) -> None:
    runner.validate_preregistered_plan(plan)
    assert plan["production_execution_authorized_now"] is False
    assert plan["sampling"]["design"] == "fixed_nonadaptive_no_pilot"
    assert plan["sampling"]["pilot_size"] == 0
    assert plan["sampling"]["unpaired_count_per_required_protocol"] < plan[
        "sampling"
    ]["main_count_per_protocol"]
    assert plan["locked_model"]["protocol_order"] == [
        protocol.value for protocol in Protocol
    ]
    assert len(plan["headline_comparisons"]) == 4


def test_any_plan_semantic_mutation_fails_closed(runner, plan) -> None:
    changed = deepcopy(plan)
    changed["sampling"]["repeated_top_up_allowed"] = True
    with pytest.raises(ValueError, match="semantic lock"):
        runner.validate_preregistered_plan(changed)


def test_plan_contains_no_result_payload_keys(plan) -> None:
    forbidden = {
        "estimate",
        "observed",
        "pilot_result",
        "confirmation_result",
        "classification_result",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(plan)
    assert plan["result_free_lock"][
        "observed_trajectory_values_present"
    ] is False


def test_validate_mode_is_result_free_and_audits_isolation(
    runner, monkeypatch
) -> None:
    def forbidden_adapter_load():
        raise AssertionError("validate mode loaded analytic formula code")

    monkeypatch.setattr(runner, "_load_reference_adapter", forbidden_adapter_load)
    result = runner.validate()
    assert result["production_stochastic_execution"] is False
    assert result["status"] == "validated_result_free"
    assert result["isolation"]["trajectory_kernel_theory_imports"] is False
    assert result["v071_acceptance_marker"].startswith(
        "S-070_AUDIT_ACCEPTANCE "
    )
    assert result["manifest_entries"] == 10
    assert len(result["reviewed_source_manifest_sha256"]) == 64


def test_run_fails_before_simulation_without_v071(
    runner, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(runner, "AUDIT_REL", Path("missing-v071-audit.md"))

    def forbidden_simulation(*args, **kwargs):
        raise AssertionError("production simulation started before V-071")

    monkeypatch.setattr(runner, "_simulate_stream", forbidden_simulation)
    with pytest.raises(PermissionError, match="V-071"):
        runner.execute(ROOT / runner.PLAN_REL)


@pytest.mark.parametrize(
    "update",
    [
        {"end_time": 0.1, "fine_step": 0.03, "record_step": 0.06},
        {"end_time": 0.125, "fine_step": 0.015625, "record_step": 0.046875},
    ],
)
def test_paired_config_rejects_nonintegral_or_noncoarse_records(update) -> None:
    with pytest.raises(ValueError):
        PairedPathConfig(
            ensemble_size=4,
            base_seed=1,
            case_code=2,
            stream_code=3,
            **update,
        )


def _small_config(
    *,
    stream_code: int = 0,
    record_events: bool = False,
) -> PairedPathConfig:
    return PairedPathConfig(
        end_time=0.25,
        fine_step=1.0 / 64.0,
        record_step=1.0 / 16.0,
        ensemble_size=8,
        base_seed=17001,
        case_code=19,
        stream_code=stream_code,
        record_events=record_events,
    )


def test_small_paired_kernel_is_seed_reproducible() -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=8.0)
    first = simulate_paired_paths(params, Protocol.P_THETA, _small_config())
    second = simulate_paired_paths(params, Protocol.P_THETA, _small_config())
    assert first.reset_clock_sha256 == second.reset_clock_sha256
    assert first.array_sha256s() == second.array_sha256s()


def test_coarse_orientation_is_sum_coupled_without_orientation_reset() -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=0.0)
    result = simulate_paired_paths(params, Protocol.P, _small_config())
    np.testing.assert_allclose(
        result.fine_orientations,
        result.coarse_orientations,
        rtol=0.0,
        atol=2e-15,
    )


@pytest.mark.parametrize("protocol", tuple(Protocol))
def test_exact_event_log_records_contract_pre_post_map(protocol: Protocol) -> None:
    params = ModelParams(inertia=0.8, activity=0.9, reset_rate=30.0)
    result = simulate_paired_paths(
        params, protocol, _small_config(record_events=True)
    )
    log = result.event_log
    assert log is not None and log.times.size > 0
    reset_map = PROTOCOL_REGISTRY[protocol]
    for prefix in ("fine", "coarse"):
        pre_position = getattr(log, f"{prefix}_pre_positions")
        post_position = getattr(log, f"{prefix}_post_positions")
        pre_velocity = getattr(log, f"{prefix}_pre_velocities")
        post_velocity = getattr(log, f"{prefix}_post_velocities")
        pre_orientation = getattr(log, f"{prefix}_pre_orientations")
        post_orientation = getattr(log, f"{prefix}_post_orientations")
        np.testing.assert_allclose(
            post_position,
            0.0 if reset_map.resets_position else pre_position,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            post_velocity,
            0.0 if reset_map.resets_velocity else pre_velocity,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            post_orientation,
            0.0 if reset_map.resets_orientation else pre_orientation,
            rtol=0.0,
            atol=1e-12,
        )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (Protocol.PV, Protocol.V),
        (Protocol.P_THETA, Protocol.THETA),
        (Protocol.PV_THETA, Protocol.V_THETA),
    ],
)
def test_position_toggle_pairs_share_internal_paths(
    left: Protocol,
    right: Protocol,
) -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=8.0)
    left_result = simulate_paired_paths(params, left, _small_config())
    right_result = simulate_paired_paths(params, right, _small_config())
    assert left_result.reset_clock_sha256 == right_result.reset_clock_sha256
    np.testing.assert_array_equal(
        left_result.fine_velocities, right_result.fine_velocities
    )
    np.testing.assert_array_equal(
        left_result.fine_orientations, right_result.fine_orientations
    )
    np.testing.assert_array_equal(
        left_result.coarse_velocities, right_result.coarse_velocities
    )
    np.testing.assert_array_equal(
        left_result.coarse_orientations, right_result.coarse_orientations
    )


def test_independent_stream_code_changes_clock_and_path_hashes() -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=8.0)
    first = simulate_paired_paths(params, Protocol.PV, _small_config(stream_code=1))
    second = simulate_paired_paths(params, Protocol.PV, _small_config(stream_code=2))
    assert first.reset_clock_sha256 != second.reset_clock_sha256
    assert first.array_sha256s()["fine_positions"] != second.array_sha256s()[
        "fine_positions"
    ]


def test_effective_diffusion_uses_covariance_slope_without_ols_se() -> None:
    times = np.linspace(0.0, 8.0, 9)
    diffusion = 1.75
    base = np.array([-1.0, 0.0, 1.0])
    positions = np.zeros((times.size, base.size, 2))
    for index, time in enumerate(times):
        positions[index, :, 0] = math.sqrt(4.0 * diffusion * time) * base
    assert effective_diffusion(
        times, positions, window_start_fraction=0.5
    ) == pytest.approx(diffusion)


def test_batched_bootstrap_sufficient_features_recompute_exact_covariance(
    runner,
) -> None:
    positions = np.array(
        [
            [[0.0, 0.0], [1.0, -1.0], [2.0, 1.0], [-1.0, 2.0]],
            [[1.0, 0.0], [2.0, -2.0], [4.0, 2.0], [-2.0, 3.0]],
        ]
    )
    weights = np.array([[2, 0, 1, 1], [0, 1, 3, 0]], dtype=np.int64)
    features = runner._position_sufficient_features(positions)
    actual = runner._bootstrap_covariance_curves(
        weights, features, positions.shape[0]
    )
    explicit = []
    for row in weights:
        indices = np.repeat(np.arange(row.size), row)
        explicit.append(
            runner.covariance_trace_curve(positions[:, indices])
        )
    np.testing.assert_allclose(actual, np.asarray(explicit), rtol=0.0, atol=1e-12)


def test_h4_reference_scope_is_explicitly_classified(runner) -> None:
    adapter = runner._load_reference_adapter()
    references = {
        protocol.value: adapter.reference_fields(
            protocol.value,
            inertia=0.8,
            activity=1.2,
            reset_rate=1.0,
            time=32.0,
        )
        for protocol in Protocol
    }
    checks = runner._reference_scope_checks(references)
    assert len(checks) == 7
    assert all(check["classification"] == "validated" for check in checks)
    assert checks[-1]["reference_difference"] > 0.0


def test_h2_paired_drift_contrast_is_explicitly_classified(
    runner, plan
) -> None:
    left = {}
    right = {}
    for resolution in ("fine", "coarse"):
        for window in range(3):
            left[f"{resolution}_v_x_{window}"] = np.full(6, 1.25)
            right[f"{resolution}_v_x_{window}"] = np.full(6, 0.25)
    row = runner._ordinary_protocol_pair_comparison(
        left,
        right,
        comparison_id="H2_test",
        left_protocol="Theta",
        right_protocol="V",
        name="v_x",
        reference_difference=1.0,
        characteristic_scale=1.0,
        tier="primary",
        plan=plan,
    )
    assert row["classification"] == "validated"
    assert row["comparison_kind"] == "paired_protocol_common_random_numbers"


def test_section_7_projection_and_interval_rules_fail_closed() -> None:
    assert (
        project_primary_sample_size(
            pilot_size=100,
            quantile=2.0,
            pilot_standard_error=0.1,
            margin=0.5,
            pilot_discrepancy=0.1,
            b_window=0.05,
            b_disc=0.05,
            compute_cap=1000,
        )
        == 45
    )
    assert (
        project_primary_sample_size(
            pilot_size=100,
            quantile=2.0,
            pilot_standard_error=0.1,
            margin=0.2,
            pilot_discrepancy=0.1,
            b_window=0.05,
            b_disc=0.05,
            compute_cap=1000,
        )
        is None
    )
    assert (
        classify_expanded_interval(
            lower=-0.1,
            upper=0.1,
            margin=0.5,
            b_window=0.1,
            b_disc=0.1,
        )
        == "validated"
    )
    assert (
        classify_expanded_interval(
            lower=0.8,
            upper=1.0,
            margin=0.5,
            b_window=0.0,
            b_disc=0.0,
        )
        == "contradicted"
    )


def test_post_simulation_reference_adapter_evaluates_all_seven(runner) -> None:
    adapter = runner._load_reference_adapter()
    for protocol in Protocol:
        fields = adapter.reference_fields(
            protocol.value,
            inertia=0.8,
            activity=1.2,
            reset_rate=1.0,
            time=32.0,
        )
        assert fields["speed"] is not None
        if protocol in (Protocol.V, Protocol.THETA, Protocol.V_THETA):
            assert math.isfinite(float(fields["D_eff"]))
        else:
            assert fields["D_eff"] is None


def _audit_text(runner, marker: str, *, disposition: str = "PASS") -> str:
    return (
        f"**Disposition:** {disposition}\n\n"
        f"{runner.AUDIT_HEADER}\n"
        f"{marker}\n"
    )


def test_strict_v071_acceptance_record_authenticates(runner, tmp_path) -> None:
    digest = "a" * 64
    audit = tmp_path / "audit.md"
    audit.write_text(
        _audit_text(runner, runner.acceptance_marker(digest)),
        encoding="utf-8",
        newline="\n",
    )
    record = runner.authenticate_v071(
        audit, reviewed_manifest_sha256=digest
    )
    assert record["disposition"] == "PASS"
    assert record["reviewed_manifest_sha256"] == digest


@pytest.mark.parametrize(
    "mode",
    ["revise", "quoted", "duplicate", "malformed"],
)
def test_v071_rejection_modes_fail_before_simulation(
    runner, monkeypatch, tmp_path, mode
) -> None:
    digest = runner.source_manifest_digest()
    marker = runner.acceptance_marker(digest)
    if mode == "revise":
        text = _audit_text(runner, marker, disposition="REVISE")
    elif mode == "quoted":
        text = _audit_text(runner, f"> {marker}")
    elif mode == "duplicate":
        text = _audit_text(runner, marker) + marker + "\n"
    else:
        text = _audit_text(
            runner, runner.AUDIT_MARKER_PREFIX + '{"disposition":'
        )
    audit = tmp_path / f"{mode}.md"
    audit.write_text(text, encoding="utf-8", newline="\n")
    monkeypatch.setattr(runner, "AUDIT_REL", audit)

    def forbidden_simulation(*args, **kwargs):
        raise AssertionError("simulation started before strict V-071 auth")

    monkeypatch.setattr(runner, "_simulate_stream", forbidden_simulation)
    with pytest.raises(PermissionError):
        runner.execute(ROOT / runner.PLAN_REL)


def test_v071_source_digest_drift_is_rejected(runner, tmp_path) -> None:
    reviewed = "a" * 64
    audit = tmp_path / "stale-source-audit.md"
    audit.write_text(
        _audit_text(runner, runner.acceptance_marker(reviewed)),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(PermissionError, match="reviewed source"):
        runner.authenticate_v071(
            audit, reviewed_manifest_sha256="b" * 64
        )


def test_canonical_source_hash_is_eol_portable_and_detects_content_drift(
    runner, tmp_path
) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    changed = tmp_path / "changed.txt"
    lf.write_bytes(b"alpha\nbeta\n")
    crlf.write_bytes(b"alpha\r\nbeta\r\n")
    changed.write_bytes(b"alpha\nBETA\n")
    assert runner._canonical_file_sha256(lf) == runner._canonical_file_sha256(
        crlf
    )
    assert runner._canonical_file_sha256(lf) != runner._canonical_file_sha256(
        changed
    )


@pytest.mark.parametrize("target", ["registry", "schema", "contract"])
def test_contract_registry_schema_and_contract_drift_fail_closed(
    runner, plan, tmp_path, target
) -> None:
    registry = tmp_path / "validation_registry.json"
    schema = tmp_path / "validation_registry.schema.json"
    contract = tmp_path / "CONTRACT.md"
    shutil.copyfile(ROOT / runner.REGISTRY_REL, registry)
    shutil.copyfile(ROOT / runner.REGISTRY_SCHEMA_REL, schema)
    shutil.copyfile(ROOT / runner.CONTRACT_REL, contract)
    if target == "registry":
        value = json.loads(registry.read_text(encoding="utf-8"))
        value["status"] = "draft"
        registry.write_text(json.dumps(value), encoding="utf-8")
    elif target == "schema":
        value = json.loads(schema.read_text(encoding="utf-8"))
        value["title"] += " drift"
        schema.write_text(json.dumps(value), encoding="utf-8")
    else:
        text = contract.read_text(encoding="utf-8")
        contract.write_text(
            text.replace(
                "This section is scientifically normative.",
                "This section is scientifically normative and drifted.",
                1,
            ),
            encoding="utf-8",
        )
    with pytest.raises(ValueError):
        runner._contract_registry_context(
            plan,
            registry_path=registry,
            schema_path=schema,
            contract_path=contract,
        )


def test_contradiction_propagation_never_degrades_to_unresolved(runner) -> None:
    assert (
        runner._combine_required_outcomes("contradicted", "unresolved")
        == "contradicted"
    )
    assert (
        runner._combine_required_outcomes(
            "validated", "unresolved", "validated"
        )
        == "unresolved"
    )
    assert (
        runner._combine_required_outcomes("validated", "validated")
        == "validated"
    )


def test_executable_estimand_table_is_complete_and_locks_h4_centered_rows(
    runner, plan
) -> None:
    specs = runner.estimand_specs(
        plan,
        observable_classes=plan["contract_registry_lock"][
            "observable_classes"
        ],
    )
    assert set(specs) == runner._expected_comparison_ids()
    assert len(specs) == 46
    assert (
        specs["H2_V_v_x_direct"]["observable_class"]
        == "symmetry_forced_zero"
    )
    assert (
        specs["H4_PV_minus_PVTheta_centered_variance"][
            "required_sign_or_equality"
        ]
        == "positive"
    )
    assert (
        specs["H4_PV_minus_PVTheta_centered_variance_unpaired"][
            "pairing_role"
        ].startswith("smaller protocol-independent")
    )


def _constant_window_data(values, coarse_values=None):
    values = np.asarray(values, dtype=float)
    coarse = (
        values.copy()
        if coarse_values is None
        else np.asarray(coarse_values, dtype=float)
    )
    result = {}
    for resolution, sample in (("fine", values), ("coarse", coarse)):
        for window in range(3):
            result[f"{resolution}_v_x_{window}"] = sample.copy()
            result[f"{resolution}_speed_{window}"] = sample.copy()
            result[f"{resolution}_raw_msd_{window}"] = sample.copy()
            result[f"{resolution}_r_dot_v_{window}"] = sample.copy()
    return result


def test_unpaired_protocol_contrast_uses_independent_sample_se(
    runner, plan
) -> None:
    left = _constant_window_data([2.0, 4.0, 6.0])
    right = _constant_window_data([0.0, 1.0, 2.0])
    row = runner._ordinary_unpaired_protocol_pair_comparison(
        left,
        right,
        comparison_id="synthetic_unpaired",
        left_protocol="Theta",
        right_protocol="V",
        name="v_x",
        reference_difference=3.0,
        characteristic_scale=1000.0,
        tier="primary",
        plan=plan,
        required_claim="positive",
    )
    _, left_se = runner.mean_and_standard_error(left["fine_v_x_1"])
    _, right_se = runner.mean_and_standard_error(right["fine_v_x_1"])
    assert row["standard_error"] == pytest.approx(
        math.sqrt(left_se**2 + right_se**2)
    )
    assert row["comparison_kind"] == "unpaired_protocol_independent_streams"


def test_paired_protocol_requires_matching_reset_clock_hash(runner) -> None:
    matching = {
        "PV": {"hashes": {"reset_clock_chunks": "a" * 64}},
        "PVTheta": {"hashes": {"reset_clock_chunks": "a" * 64}},
    }
    assert (
        runner._require_matching_reset_clocks(matching, "PV", "PVTheta")
        == "a" * 64
    )
    mismatched = deepcopy(matching)
    mismatched["PVTheta"]["hashes"]["reset_clock_chunks"] = "b" * 64
    with pytest.raises(RuntimeError, match="reset-clock"):
        runner._require_matching_reset_clocks(
            mismatched, "PV", "PVTheta"
        )


def test_bootstrap_se_stability_is_fixed_and_not_percentile(runner, plan) -> None:
    values = np.tile(np.linspace(-1.0, 1.0, 512), 4)
    diagnostic = runner._bootstrap_se_stability(
        values,
        block_count=4,
        maximum_relative_deviation=0.1,
    )
    assert diagnostic["block_size"] == 512
    assert diagnostic["classification"] == "validated"
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    assert uncertainty["bootstrap_replicates"] == 2048
    assert "bootstrap-SE" in uncertainty["D_eff_interval"]
    assert "percentile" not in uncertainty["D_eff_interval"]


def test_h4_centered_variance_pair_is_an_executable_same_estimand_contrast(
    runner, plan
) -> None:
    times = np.arange(4, dtype=float)
    base = np.linspace(-1.0, 1.0, 128)
    right_positions = np.zeros((times.size, base.size, 2), dtype=float)
    right_positions[:, :, 0] = base
    left_positions = 2.0 * right_positions
    left = {
        "times": times,
        "fine_positions": left_positions,
        "coarse_positions": left_positions.copy(),
    }
    right = {
        "times": times,
        "fine_positions": right_positions,
        "coarse_positions": right_positions.copy(),
    }
    reference_difference = runner._position_statistic(
        times,
        left_positions,
        kind="centered_variance",
        fraction=runner.WINDOW_FRACTIONS[runner.PRIMARY_WINDOW_INDEX],
    ) - runner._position_statistic(
        times,
        right_positions,
        kind="centered_variance",
        fraction=runner.WINDOW_FRACTIONS[runner.PRIMARY_WINDOW_INDEX],
    )
    row = runner._bootstrap_position_pair_comparison(
        left,
        right,
        comparison_id="H4_synthetic_centered",
        left_protocol="PV",
        right_protocol="PVTheta",
        kind="centered_variance",
        reference_difference=reference_difference,
        characteristic_scale=reference_difference,
        tier="primary",
        plan=plan,
        seed=70072001,
        paired_protocols=True,
        required_claim="positive",
    )
    assert row["comparison_kind"] == "paired_protocol_common_random_numbers"
    assert row["estimate"] == pytest.approx(reference_difference)
    assert row["required_sign_or_equality"] == "positive"
    assert row["paired_fine_coarse"]["estimate"] == pytest.approx(0.0)


def test_attempt_sentinel_survives_crash_and_blocks_retry(
    runner, tmp_path
) -> None:
    sentinel = tmp_path / "attempt.json"

    def crash():
        raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic crash"):
        runner._run_after_attempt_sentinel(
            sentinel, {"attempt": 1}, crash
        )
    assert sentinel.is_file()
    assert json.loads(sentinel.read_text(encoding="utf-8")) == {"attempt": 1}
    with pytest.raises(FileExistsError):
        runner._run_after_attempt_sentinel(
            sentinel, {"attempt": 2}, lambda: None
        )
    assert json.loads(sentinel.read_text(encoding="utf-8")) == {"attempt": 1}


def test_resource_preflight_failure_occurs_before_simulation(
    runner, plan, monkeypatch, tmp_path
) -> None:
    with pytest.raises(RuntimeError, match="free disk"):
        runner.resource_preflight(
            plan,
            free_disk_bytes=0,
            available_memory_bytes=10**12,
            output_path=tmp_path / "output.json",
            attempt_path=tmp_path / "attempt.json",
        )

    monkeypatch.setattr(
        runner, "authenticate_v071", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(runner, "_clean_source_commit", lambda: "a" * 40)

    def failed_preflight(*args, **kwargs):
        raise RuntimeError("synthetic preflight failure")

    def forbidden_simulation(*args, **kwargs):
        raise AssertionError("simulation started after failed preflight")

    monkeypatch.setattr(runner, "resource_preflight", failed_preflight)
    monkeypatch.setattr(runner, "_simulate_stream", forbidden_simulation)
    with pytest.raises(RuntimeError, match="synthetic preflight failure"):
        runner.execute(ROOT / runner.PLAN_REL)


def test_result_row_provenance_covers_every_estimand(runner, plan) -> None:
    rows = [
        {
            "comparison_id": comparison_id,
            "classification": "validated",
        }
        for comparison_id in sorted(runner._expected_comparison_ids())
    ]
    runner._decorate_and_validate_result_rows((rows,), plan)
    required = {
        "observable_class",
        "estimator",
        "interval_construction",
        "coverage",
        "quantile",
        "pairing_role",
        "registry_schema_version",
        "registry_sha256",
        "compute_cap",
    }
    assert all(required.issubset(row) for row in rows)


def test_reset_event_cap_fails_closed() -> None:
    params = ModelParams(inertia=0.8, activity=1.2, reset_rate=1000.0)
    config = PairedPathConfig(
        end_time=0.25,
        fine_step=1.0 / 64.0,
        record_step=1.0 / 16.0,
        ensemble_size=8,
        base_seed=17001,
        case_code=19,
        stream_code=0,
        max_reset_events_per_trajectory=1,
    )
    with pytest.raises(RuntimeError, match="reset-event cap"):
        simulate_paired_paths(params, Protocol.P, config)
