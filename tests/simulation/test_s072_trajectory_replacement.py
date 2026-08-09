"""Result-free deterministic locks for the S-072 replacement implementation."""

from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

from phasemap.simulation.protocols import Protocol
from phasemap.simulation.trajectory_replacement import (
    ConditionalLevelRecord,
    TriplePathConfig,
    _apply_conditional_reset,
    _flush_level,
    _new_level,
    centered_covariance_curve_from_features,
    conditional_position_features,
    conditional_scalar_curves,
    linear_conditional_coefficients,
    richardson_samples,
    seed_tuple,
)


ROOT = Path(__file__).resolve().parents[2]
KERNEL_PATH = ROOT / "src/phasemap/simulation/trajectory_replacement.py"
RUNNER_PATH = ROOT / "experiments/run_s072_all_seven_trajectory_replacement.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("s072_runner_test", RUNNER_PATH)
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


def _record() -> ConditionalLevelRecord:
    return ConditionalLevelRecord(
        position_means=np.array(
            [[[1.0, 2.0], [3.0, 4.0]], [[2.0, 1.0], [4.0, 3.0]]]
        ),
        velocity_means=np.array(
            [[[0.5, 1.0], [1.5, 2.0]], [[1.0, 0.5], [2.0, 1.5]]]
        ),
        orientations=np.zeros((2, 2)),
        position_variance_per_axis=np.array([[0.25, 0.5], [0.75, 1.0]]),
        position_velocity_covariance_per_axis=np.array(
            [[0.1, 0.2], [0.3, 0.4]]
        ),
        velocity_variance_per_axis=np.array([[0.4, 0.3], [0.2, 0.1]]),
    )


def test_three_level_config_is_exactly_nested_and_record_aligned() -> None:
    config = TriplePathConfig(
        end_time=32.0,
        finest_step=1.0 / 256.0,
        record_step=2.0,
        ensemble_size=16,
        base_seed=1,
        case_code=7001,
        stream_code=0,
    )
    assert config.finest_steps == 8192
    assert config.record_stride == 512
    with pytest.raises(ValueError, match="divisible by four"):
        TriplePathConfig(1.0, 0.2, 1.0, 2, 1, 1, 1)
    with pytest.raises(ValueError, match="align with every level"):
        TriplePathConfig(1.0, 0.125, 0.25, 2, 1, 1, 1)


def test_seed_tuple_is_complete_and_rejects_boolean_aliases() -> None:
    assert seed_tuple(72070001, 7001, 4, 3) == (72070001, 7001, 4, 3)
    with pytest.raises(ValueError):
        seed_tuple(True, 7001, 4, 3)


def test_exact_conditional_coefficients_match_closed_form_and_psd() -> None:
    dt = np.array([0.125, 0.25])
    inertia = 0.8
    a, b, q_rr, q_rv, q_vv = linear_conditional_coefficients(dt, inertia)
    expected_a = np.exp(-dt / inertia)
    assert np.allclose(a, expected_a, rtol=0.0, atol=1e-15)
    assert np.allclose(b, inertia * (1.0 - expected_a), atol=1e-15)
    assert np.all(q_rr > 0.0)
    assert np.all(q_rv > 0.0)
    assert np.all(q_vv > 0.0)
    assert np.all(q_rr * q_vv - q_rv * q_rv >= -1e-14)


def test_deterministic_flush_propagates_exact_translational_moments() -> None:
    state = _new_level(2)
    state.pending_dt[:] = np.array([0.125, 0.25])
    state.pending_rotation[:] = np.array([0.2, -0.1])
    indices = np.array([0, 1], dtype=np.int64)
    a, b, q_rr, q_rv, q_vv = linear_conditional_coefficients(
        state.pending_dt.copy(), 0.8
    )
    _flush_level(state, indices, inertia=0.8, activity=1.2)
    assert np.allclose(state.velocity[:, 0], (1.0 - a) * 1.2)
    assert np.allclose(state.position[:, 0], (np.array([0.125, 0.25]) - b) * 1.2)
    assert np.allclose(state.c_rr, q_rr)
    assert np.allclose(state.c_rv, q_rv)
    assert np.allclose(state.c_vv, q_vv)
    assert np.array_equal(state.orientation, np.array([0.2, -0.1]))
    assert np.count_nonzero(state.pending_dt) == 0


@pytest.mark.parametrize(
    ("protocol", "zero_position", "zero_velocity", "zero_orientation"),
    [
        (Protocol.P, True, False, False),
        (Protocol.V, False, True, False),
        (Protocol.THETA, False, False, True),
        (Protocol.PV_THETA, True, True, True),
    ],
)
def test_conditional_reset_zeroes_exact_selected_moments(
    protocol: Protocol,
    zero_position: bool,
    zero_velocity: bool,
    zero_orientation: bool,
) -> None:
    state = _new_level(2)
    state.position[:] = 1.0
    state.velocity[:] = 2.0
    state.orientation[:] = 3.0
    state.c_rr[:] = 4.0
    state.c_rv[:] = 5.0
    state.c_vv[:] = 6.0
    _apply_conditional_reset(state, np.array([0], dtype=np.int64), protocol)
    assert np.all(state.position[0] == (0.0 if zero_position else 1.0))
    assert np.all(state.velocity[0] == (0.0 if zero_velocity else 2.0))
    assert state.orientation[0] == (0.0 if zero_orientation else 3.0)
    assert state.c_rr[0] == (0.0 if zero_position else 4.0)
    assert state.c_vv[0] == (0.0 if zero_velocity else 6.0)
    assert state.c_rv[0] == (0.0 if zero_position or zero_velocity else 5.0)
    assert np.all(state.position[1] == 1.0)


def test_conditional_observables_include_analytic_noise_moments() -> None:
    record = _record()
    curves = conditional_scalar_curves(record)
    assert np.allclose(
        curves["speed"],
        np.sum(record.velocity_means**2, axis=2)
        + 2.0 * record.velocity_variance_per_axis,
    )
    assert np.allclose(
        curves["raw_msd"],
        np.sum(record.position_means**2, axis=2)
        + 2.0 * record.position_variance_per_axis,
    )
    assert np.allclose(
        curves["r_dot_v"],
        np.sum(record.position_means * record.velocity_means, axis=2)
        + 2.0 * record.position_velocity_covariance_per_axis,
    )


def test_centered_covariance_uses_total_variance_decomposition() -> None:
    record = _record()
    features = conditional_position_features(record)
    actual = centered_covariance_curve_from_features(features)
    conditional_trace = 2.0 * record.position_variance_per_axis.mean(axis=1)
    centered = record.position_means - record.position_means.mean(
        axis=1, keepdims=True
    )
    between = np.sum(centered * centered, axis=(1, 2))
    assert np.allclose(actual, conditional_trace + between)


def test_richardson_pair_is_fixed_first_order_extrapolation() -> None:
    truth = np.array([1.0, -2.0])
    coefficient = np.array([0.4, -0.2])
    finest = truth + coefficient * 0.5
    middle = truth + coefficient
    coarse = truth + 2.0 * coefficient
    primary, secondary = richardson_samples(finest, middle, coarse)
    assert np.allclose(primary, truth)
    assert np.allclose(secondary, truth)


def test_kernel_has_no_reference_prior_result_or_translational_rng_route() -> None:
    source = KERNEL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(name.startswith("phasemap.theory") for name in imports)
    assert "artifacts" not in source
    assert "S-071" not in source
    assert source.count("ROTATIONAL_WIENER_COMPONENT") >= 2
    assert source.count("TRANSLATIONAL_COMPONENT_MARGINALIZED") == 1


def test_locked_plan_validates_and_preserves_all_estimands(runner, plan) -> None:
    runner.validate_preregistered_plan(plan)
    specs = runner.estimand_specs(
        plan,
        observable_classes=plan["contract_registry_lock"]["observable_classes"],
    )
    assert len(plan["estimand_table"]) == 18
    assert len(specs) == 46
    assert set(specs) == runner._expected_comparison_ids()
    assert plan["production_execution_authorized_now"] is False
    assert plan["sampling"]["count_change_from_s071"] == 0


def test_any_semantic_plan_mutation_fails_closed(runner, plan) -> None:
    changed = deepcopy(plan)
    changed["sampling"]["continuous_polling_allowed"] = True
    with pytest.raises(ValueError, match="semantic lock"):
        runner.validate_preregistered_plan(changed)


def test_validate_mode_cannot_load_references_or_simulate(
    runner, monkeypatch
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("result-free validation crossed into stochastic work")

    monkeypatch.setattr(runner, "_load_reference_adapter", forbidden)
    monkeypatch.setattr(runner, "_simulate_stream", forbidden)
    result = runner.validate()
    assert result["status"] == "validated_result_free"
    assert result["production_stochastic_execution"] is False
    assert result["s071_artifacts_opened"] is False
    assert result["source_manifest_entries"] == len(runner.MANIFEST_PATHS)
    assert result["runtime_dependency_versions"] == runner.LOCKED_RUNTIME_VERSIONS
    assert result["reviewed_source_commit"] == runner.manifest_source_commit()


def test_execute_without_v072_fails_before_simulation(
    runner, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(runner, "AUDIT_REL", tmp_path / "missing-v072.md")

    def forbidden(*args, **kwargs):
        raise AssertionError("simulation started before V-072 authentication")

    monkeypatch.setattr(runner, "_simulate_stream", forbidden)
    with pytest.raises(PermissionError, match="V-072 audit is absent"):
        runner.execute(ROOT / runner.PLAN_REL)


def _audit_text(runner, marker: str, *, disposition: str = "PASS") -> str:
    return (
        f"**Disposition:** {disposition}\n\n"
        f"{runner.AUDIT_HEADER}\n"
        f"{marker}\n"
    )


def test_strict_v072_pass_marker_authenticates(runner, tmp_path) -> None:
    digest = "a" * 64
    audit = tmp_path / "audit.md"
    audit.write_text(
        _audit_text(runner, runner.acceptance_marker(digest)),
        encoding="utf-8",
        newline="\n",
    )
    record = runner.authenticate_v072(
        audit, reviewed_manifest_sha256=digest
    )
    assert record["disposition"] == "PASS"
    assert record["reviewed_manifest_sha256"] == digest
    assert record["reviewed_source_commit"] == runner.manifest_source_commit()


@pytest.mark.parametrize("mode", ["revise", "quoted", "duplicate", "malformed"])
def test_v072_marker_rejection_variants(
    runner, tmp_path, mode: str
) -> None:
    digest = "a" * 64
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
    with pytest.raises(PermissionError):
        runner.authenticate_v072(audit, reviewed_manifest_sha256=digest)


def test_v072_source_manifest_drift_is_rejected(runner, tmp_path) -> None:
    reviewed = "a" * 64
    audit = tmp_path / "stale-source.md"
    audit.write_text(
        _audit_text(runner, runner.acceptance_marker(reviewed)),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(PermissionError, match="exact plan/source manifest"):
        runner.authenticate_v072(
            audit, reviewed_manifest_sha256="b" * 64
        )


def test_complete_manifest_covers_repository_and_reference_source(runner) -> None:
    manifest_paths = tuple(runner.MANIFEST_PATHS)
    assert len(manifest_paths) == len(set(manifest_paths))
    repository_python = {
        path.relative_to(ROOT)
        for path in (ROOT / "src/phasemap").rglob("*.py")
    }
    assert repository_python == set(runner.PHASEMAP_SOURCE_PATHS)
    assert repository_python.issubset(manifest_paths)
    assert set(runner.REFERENCE_SOURCE_CLOSURE).issubset(manifest_paths)
    assert runner.PYPROJECT_REL in manifest_paths
    assert runner.RUNTIME_REQUIREMENTS_REL in manifest_paths


@pytest.mark.parametrize(
    "dependency",
    [
        "src/phasemap/theory/formula_registry.py",
        "src/phasemap/theory/nonposition_protocols.py",
        "src/phasemap/theory/position_protocols.py",
    ],
)
def test_reference_dependency_drift_invalidates_v072(
    runner, tmp_path, dependency: str
) -> None:
    manifest = runner.source_manifest()
    baseline_digest = runner.source_manifest_digest(manifest)
    source_commit = runner.manifest_source_commit()
    audit = tmp_path / (Path(dependency).stem + "-drift.md")
    audit.write_text(
        _audit_text(
            runner,
            runner.acceptance_marker(baseline_digest, source_commit),
        ),
        encoding="utf-8",
        newline="\n",
    )
    drifted = dict(manifest)
    drifted[dependency] = "0" * 64
    drifted_digest = runner.source_manifest_digest(drifted)
    assert drifted_digest != baseline_digest
    with pytest.raises(PermissionError, match="exact plan/source manifest"):
        runner.authenticate_v072(
            audit,
            reviewed_manifest_sha256=drifted_digest,
            reviewed_source_commit=source_commit,
        )


def test_reviewed_source_commit_drift_invalidates_v072(runner, tmp_path) -> None:
    digest = runner.source_manifest_digest()
    source_commit = runner.manifest_source_commit()
    audit = tmp_path / "source-commit-drift.md"
    audit.write_text(
        _audit_text(runner, runner.acceptance_marker(digest, source_commit)),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(PermissionError, match="manifest and commit"):
        runner.authenticate_v072(
            audit,
            reviewed_manifest_sha256=digest,
            reviewed_source_commit="0" * 40,
        )


def test_reviewed_source_lineage_is_enforced(runner) -> None:
    source_commit = runner.manifest_source_commit()
    runner._authenticate_reviewed_source_lineage(source_commit, source_commit)
    with pytest.raises(PermissionError, match="not an execution ancestor"):
        runner._authenticate_reviewed_source_lineage("0" * 40, source_commit)


def test_runtime_dependency_versions_are_pinned(runner, plan) -> None:
    assert plan["runtime_environment_lock"]["versions"] == {
        "numpy": "2.5.1",
        "sympy": "1.14.0",
    }
    assert runner.runtime_dependency_versions() == runner.LOCKED_RUNTIME_VERSIONS


@pytest.mark.parametrize("target", ["registry", "schema", "contract"])
def test_registry_schema_and_contract_drift_fail_closed(
    runner, plan, tmp_path, target: str
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


def test_contradiction_aggregation_has_fail_closed_precedence(runner) -> None:
    assert runner._combine_required_outcomes(
        "contradicted", "unresolved"
    ) == "contradicted"
    assert runner._aggregate(["validated", "contradicted", "unresolved"]) == (
        "contradicted"
    )
    assert runner._aggregate(["validated", "unresolved"]) == "unresolved"
    assert runner._aggregate(["validated", "validated"]) == "validated"


def test_exact_seed_domains_are_fresh_and_never_use_component_two(
    runner, plan
) -> None:
    result = runner.validate_seed_domains(plan)
    assert result == {
        "main_unique": 32,
        "unpaired_unique": 48,
        "bootstrap_unique": 9,
        "total_unique": 89,
        "disjoint_from_s071": True,
    }
    seed_policy = plan["seed_policy"]
    entries = (
        seed_policy["explicit_main_rng_tuples"]
        + seed_policy["explicit_unpaired_rng_tuples"]
        + seed_policy["explicit_bootstrap_rng_tuples"]
    )
    domains = [tuple(entry["tuple"]) for entry in entries]
    assert len(domains) == len(set(domains)) == 89
    assert {domain[3] for domain in domains} == {1, 3, 4}
    assert 2 not in {domain[3] for domain in domains}
    unpaired_bases = list(seed_policy["unpaired_base_seeds"].values())
    assert len(unpaired_bases) == len(set(unpaired_bases)) == 6


def _constant_richardson_data(values, secondary_values=None):
    primary = np.asarray(values, dtype=float)
    secondary = (
        primary.copy()
        if secondary_values is None
        else np.asarray(secondary_values, dtype=float)
    )
    result = {}
    for name in ("v_x", "speed", "raw_msd", "r_dot_v"):
        for window in range(3):
            result[f"primary_{name}_{window}"] = primary.copy()
            result[f"secondary_{name}_{window}"] = secondary.copy()
    return result


def test_unpaired_contrast_uses_independent_sample_se(runner, plan) -> None:
    left = _constant_richardson_data([2.0, 4.0, 6.0])
    right = _constant_richardson_data([0.0, 1.0, 2.0])
    row = runner._ordinary_protocol_pair(
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
        paired_protocols=False,
    )
    _, left_se = runner.mean_and_standard_error(left["primary_v_x_1"])
    _, right_se = runner.mean_and_standard_error(right["primary_v_x_1"])
    assert row["standard_error"] == pytest.approx(
        math.hypot(left_se, right_se)
    )
    assert row["comparison_kind"] == "unpaired_protocol_independent_streams"


def test_reset_clock_pairing_is_required(runner) -> None:
    matching = {
        "PV": {"hashes": {"reset_clock_chunks": "a" * 64}},
        "PVTheta": {"hashes": {"reset_clock_chunks": "a" * 64}},
    }
    assert runner._require_matching_reset_clocks(
        matching, "PV", "PVTheta"
    ) == "a" * 64
    mismatched = deepcopy(matching)
    mismatched["PVTheta"]["hashes"]["reset_clock_chunks"] = "b" * 64
    with pytest.raises(RuntimeError, match="reset clocks differ"):
        runner._require_matching_reset_clocks(
            mismatched, "PV", "PVTheta"
        )


def test_richardson_discretization_envelope_uses_divisor_three(
    runner, plan
) -> None:
    primary = np.array([4.0, 5.0, 6.0])
    secondary = np.array([1.0, 2.0, 3.0])
    row = runner._ordinary_comparison_from_units(
        primary,
        secondary,
        [5.0, 5.0, 5.0],
        comparison_id="synthetic_richardson",
        observable="speed",
        reference=5.0,
        characteristic_scale=1000.0,
        tier="primary",
        plan=plan,
        required_claim="positive",
    )
    assert row["richardson_residual"]["formula"] == "(R_h-R_2h)/3"
    assert row["richardson_residual"]["estimate"] == pytest.approx(1.0)
    assert row["richardson_residual"]["standard_error"] == 0.0
    assert row["B_disc"] == pytest.approx(1.0)


def test_bootstrap_se_stability_is_fixed_and_not_percentile(
    runner, plan
) -> None:
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


def test_write_once_sentinel_survives_crash_and_blocks_retry(
    runner, tmp_path
) -> None:
    sentinel = tmp_path / "attempt.json"

    def crash():
        raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic crash"):
        runner._run_after_attempt_sentinel(
            sentinel, {"attempt": 1}, crash
        )
    assert json.loads(sentinel.read_text(encoding="utf-8")) == {"attempt": 1}
    with pytest.raises(FileExistsError):
        runner._run_after_attempt_sentinel(
            sentinel, {"attempt": 2}, lambda: None
        )
    assert json.loads(sentinel.read_text(encoding="utf-8")) == {"attempt": 1}


def test_resource_preflight_blocks_before_simulation(
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
        runner,
        "authenticate_v072",
        lambda *args, **kwargs: {
            "reviewed_source_commit": runner.manifest_source_commit()
        },
    )
    monkeypatch.setattr(runner, "_clean_source_commit", lambda: "a" * 40)
    monkeypatch.setattr(
        runner, "_authenticate_reviewed_source_lineage", lambda *args: None
    )

    def failed_preflight(*args, **kwargs):
        raise RuntimeError("synthetic preflight failure")

    def forbidden(*args, **kwargs):
        raise AssertionError("simulation started after failed preflight")

    monkeypatch.setattr(runner, "resource_preflight", failed_preflight)
    monkeypatch.setattr(runner, "_simulate_stream", forbidden)
    with pytest.raises(RuntimeError, match="synthetic preflight failure"):
        runner.execute(ROOT / runner.PLAN_REL)


def test_result_row_provenance_covers_every_estimand(runner, plan) -> None:
    rows = [
        {"comparison_id": comparison_id, "classification": "validated"}
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
        "compute_cap_role",
    }
    assert all(required.issubset(row) for row in rows)
