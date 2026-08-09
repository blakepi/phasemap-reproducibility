"""Result-free validator and audit-gated S-070 fixed-plan runner.

``validate`` performs no stochastic calculation and loads no analytic formula
code.  ``run`` is unavailable until V-071 records acceptance of the exact plan
hashes.  The production path is fixed-work, write-once, and has no retry,
polling, pilot, or top-up mode.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from phasemap.common.model import ModelParams
from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol
from phasemap.simulation.trajectory_validation import (
    PairedPathConfig,
    classify_expanded_interval,
    covariance_trace_curve,
    effective_diffusion,
    mean_and_standard_error,
    paired_mean_and_standard_error,
    simulate_paired_paths,
)
ROOT = Path(__file__).resolve().parents[1]
PLAN_REL = Path("experiments/S-070-all-seven-trajectory-validation-primary-v1.json")
KERNEL_REL = Path("src/phasemap/simulation/trajectory_validation.py")
ADAPTER_REL = Path("experiments/s070_reference_adapter.py")
TEST_REL = Path("tests/simulation/test_s070_trajectory_validation.py")
REGISTRY_REL = Path("docs/scientific-contract/validation_registry.json")
REGISTRY_SCHEMA_REL = Path(
    "docs/scientific-contract/validation_registry.schema.json"
)
REGISTRY_VALIDATOR_REL = Path("scripts/validate_validation_registry.py")
CONTRACT_REL = Path("docs/scientific-contract/CONTRACT.md")
GITATTRIBUTES_REL = Path(".gitattributes")
AUDIT_REL = Path("artifacts/derived/V-071-trajectory-preregistration-audit.md")
OUTPUT_REL = Path("artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.json")
ATTEMPT_REL = Path(
    "artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.attempt.json"
)
PLAN_ID = "S-070-all-seven-trajectory-validation-primary-v1"
PLAN_VERSION = "2.0.0"

# Filled after the exact result-free plan is frozen.
EXPECTED_PLAN_RAW_SHA256 = "06942ac935d31fc6c8244c4cbe947a31a4636b94374c889c796cf6212b167330"
EXPECTED_PLAN_SEMANTIC_SHA256 = "26c014473f959b2f7beb73a6c3f2a550d0e7ece41c6fad7e53fde416c27354ed"

POSITION_PROTOCOLS = ("P", "PV", "PTheta", "PVTheta")
TRANSPORT_PROTOCOLS = ("V", "Theta", "VTheta")
UNPAIRED_PROTOCOLS = ("V", "Theta", "PV", "PTheta", "VTheta", "PVTheta")
WINDOW_FRACTIONS = (0.5, 2.0 / 3.0, 0.75)
PRIMARY_WINDOW_INDEX = 1
SCALAR_NAMES = ("speed", "r_dot_v", "raw_msd", "v_x")
MANIFEST_PATHS = (
    GITATTRIBUTES_REL,
    CONTRACT_REL,
    REGISTRY_REL,
    REGISTRY_SCHEMA_REL,
    REGISTRY_VALIDATOR_REL,
    PLAN_REL,
    KERNEL_REL,
    ADAPTER_REL,
    Path("experiments/run_s070_all_seven_trajectory_validation.py"),
    TEST_REL,
)
AUDIT_HEADER = "## S-070 production acceptance"
AUDIT_MARKER_PREFIX = "S-070_AUDIT_ACCEPTANCE "
SOURCE_MANIFEST_CANONICALIZATION = "utf8_strict_eol_lf_v1"


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_tree(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite JSON number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_nonfinite_tree(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonfinite_tree(item, f"{path}[{index}]")


def _semantic_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_text_bytes(path: Path) -> bytes:
    """Return checkout-portable UTF-8 bytes with all line endings normalized."""

    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is forbidden in reviewed source: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"reviewed source is not strict UTF-8: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _canonical_file_sha256(path: Path) -> str:
    return _sha256_bytes(_canonical_text_bytes(path))


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            _canonical_text_bytes(path).decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    _reject_nonfinite_tree(value)
    return value


def load_preregistered_plan(path: Path) -> dict[str, Any]:
    if path.resolve() != (ROOT / PLAN_REL).resolve():
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    return _load_json_object(path)


def _load_registry_validator() -> Any:
    """Load the repository's reviewed strict JSON-Schema subset validator."""

    path = ROOT / REGISTRY_VALIDATOR_REL
    spec = importlib.util.spec_from_file_location(
        "s070_reviewed_validation_registry_validator", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load reviewed registry validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract_registry_context(
    plan: Mapping[str, Any],
    *,
    registry_path: Path | None = None,
    schema_path: Path | None = None,
    contract_path: Path | None = None,
    validator_path: Path | None = None,
) -> dict[str, Any]:
    """Validate and bind the full approved Section 7 registry surface."""

    registry_file = ROOT / REGISTRY_REL if registry_path is None else registry_path
    schema_file = (
        ROOT / REGISTRY_SCHEMA_REL if schema_path is None else schema_path
    )
    contract_file = ROOT / CONTRACT_REL if contract_path is None else contract_path
    validator_file = (
        ROOT / REGISTRY_VALIDATOR_REL if validator_path is None else validator_path
    )
    registry = _load_json_object(registry_file)
    schema = _load_json_object(schema_file)
    contract_text = _canonical_text_bytes(contract_file).decode("utf-8")

    if validator_path is None:
        validator = _load_registry_validator()
    else:
        spec = importlib.util.spec_from_file_location(
            "s070_test_validation_registry_validator", validator_file
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load registry validator: {validator_file}")
        validator = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = validator
        spec.loader.exec_module(validator)
    validator.validate_registry_instance(registry, schema)
    validator.validate_contract_alignment(contract_text, registry)

    section_7 = validator.extract_section_7(contract_text)
    context = {
        "schema_version": registry.get("schema_version"),
        "contract_version": registry.get("contract_version"),
        "status": registry.get("status"),
        "evidence_tiers": registry.get("evidence_tiers"),
        "pairing": registry.get("pairing"),
        "observable_classes": registry.get("observable_classes"),
        "contract_section_7_sha256": _sha256_bytes(section_7.encode("utf-8")),
        "registry_semantic_sha256": _sha256_bytes(_semantic_bytes(registry)),
        "schema_semantic_sha256": _sha256_bytes(_semantic_bytes(schema)),
        "registry_validator_canonical_sha256": _canonical_file_sha256(
            validator_file
        ),
    }
    lock = plan.get("contract_registry_lock")
    if not isinstance(lock, Mapping):
        raise ValueError("S-070 contract/registry lock is absent")
    for key in (
        "schema_version",
        "contract_version",
        "status",
        "evidence_tiers",
        "pairing",
        "observable_classes",
        "contract_section_7_sha256",
        "registry_semantic_sha256",
        "schema_semantic_sha256",
        "registry_validator_canonical_sha256",
    ):
        if lock.get(key) != context[key]:
            raise ValueError(f"S-070 contract/registry lock mismatch: {key}")
    return context


def _expected_comparison_ids() -> set[str]:
    protocols = tuple(protocol.value for protocol in ALL_PROTOCOLS)
    ids = {f"MAIN_{protocol}_speed_direct" for protocol in protocols}
    ids.update(
        f"H1_{protocol}_centered_variance_direct"
        for protocol in POSITION_PROTOCOLS
    )
    ids.update(
        f"H1_{protocol}_D_eff_direct" for protocol in TRANSPORT_PROTOCOLS
    )
    ids.update(f"H2_{protocol}_v_x_direct" for protocol in TRANSPORT_PROTOCOLS)
    for protocol in ("PV", "PVTheta"):
        ids.add(f"H4_{protocol}_raw_msd_direct")
        ids.add(f"H4_{protocol}_r_dot_v_direct")
    ids.update(
        {
            "H2_Theta_minus_V_v_x",
            "H2_VTheta_minus_V_v_x",
            "H4_PV_minus_PVTheta_speed",
            "H4_PV_minus_PVTheta_raw_msd",
            "H4_PV_minus_PVTheta_r_dot_v",
            "H4_PV_minus_PVTheta_centered_variance",
            "H2_Theta_minus_V_v_x_unpaired",
            "H2_VTheta_minus_V_v_x_unpaired",
            "H3_PV_minus_V_speed_unpaired",
            "H3_PTheta_minus_Theta_speed_unpaired",
            "H3_PVTheta_minus_VTheta_speed_unpaired",
            "H4_PV_minus_PVTheta_speed_unpaired",
            "H4_PV_minus_PVTheta_raw_msd_unpaired",
            "H4_PV_minus_PVTheta_r_dot_v_unpaired",
            "H4_PV_minus_PVTheta_centered_variance_unpaired",
            "H3_PV_V_pathwise_internal",
            "H3_PTheta_Theta_pathwise_internal",
            "H3_PVTheta_VTheta_pathwise_internal",
            "H3_PV_V_speed_reference_common_nonzero",
            "H3_PTheta_Theta_speed_reference_common_nonzero",
            "H3_PVTheta_VTheta_speed_reference_common_nonzero",
            "H4_reference_common_speed",
            "H4_reference_common_r_dot_v",
            "H4_reference_common_raw_MSD",
            "H4_reference_distinct_centered_variance",
        }
    )
    return ids


def estimand_specs(
    plan: Mapping[str, Any],
    *,
    observable_classes: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Expand the executable comparison-family table to one locked row per ID."""

    table = plan.get("estimand_table")
    if not isinstance(table, list) or not table:
        raise ValueError("S-070 executable estimand table is absent")
    required = {
        "family_id",
        "comparison_ids",
        "headline",
        "observable",
        "observable_class",
        "parent_scale_inputs",
        "tier",
        "estimator",
        "interval_construction",
        "pairing_role",
        "required_sign_or_equality",
        "compute_cap_role",
    }
    specs: dict[str, dict[str, Any]] = {}
    family_ids: set[str] = set()
    for family in table:
        if not isinstance(family, dict) or not required.issubset(family):
            raise ValueError("estimand family is malformed or incomplete")
        family_id = family["family_id"]
        if not isinstance(family_id, str) or family_id in family_ids:
            raise ValueError("estimand family IDs must be unique nonempty strings")
        family_ids.add(family_id)
        comparison_ids = family["comparison_ids"]
        if not isinstance(comparison_ids, list) or not comparison_ids:
            raise ValueError(f"estimand family {family_id} has no comparison IDs")
        for comparison_id in comparison_ids:
            if not isinstance(comparison_id, str) or comparison_id in specs:
                raise ValueError("estimand comparison IDs must be unique strings")
            spec = dict(family)
            spec.pop("comparison_ids", None)
            if "tier_by_id" in family:
                mapping = family["tier_by_id"]
                if not isinstance(mapping, dict) or comparison_id not in mapping:
                    raise ValueError(f"missing tier map for {comparison_id}")
                spec["tier"] = mapping[comparison_id]
            if "observable_class_by_id" in family:
                mapping = family["observable_class_by_id"]
                if not isinstance(mapping, dict) or comparison_id not in mapping:
                    raise ValueError(
                        f"missing observable-class map for {comparison_id}"
                    )
                spec["observable_class"] = mapping[comparison_id]
            spec.pop("tier_by_id", None)
            spec.pop("observable_class_by_id", None)
            spec["comparison_id"] = comparison_id
            if spec["tier"] not in {
                "primary",
                "central_disputed",
                "deterministic",
            }:
                raise ValueError(f"invalid estimand tier for {comparison_id}")
            if spec["compute_cap_role"] not in {
                "main",
                "unpaired",
                "deterministic",
            }:
                raise ValueError(f"invalid compute-cap role for {comparison_id}")
            if (
                observable_classes is not None
                and spec["observable_class"] not in observable_classes
            ):
                raise ValueError(
                    f"unregistered observable class for {comparison_id}"
                )
            if not isinstance(spec["parent_scale_inputs"], list) or not spec[
                "parent_scale_inputs"
            ]:
                raise ValueError(f"missing parent-scale inputs for {comparison_id}")
            specs[comparison_id] = spec
    expected = _expected_comparison_ids()
    if set(specs) != expected:
        missing = sorted(expected - set(specs))
        extra = sorted(set(specs) - expected)
        raise ValueError(
            f"estimand table comparison coverage mismatch; missing={missing}, "
            f"extra={extra}"
        )
    return specs


def validate_preregistered_plan(plan: Mapping[str, Any]) -> None:
    raw_hash = _canonical_file_sha256(ROOT / PLAN_REL)
    semantic_hash = _sha256_bytes(_semantic_bytes(plan))
    if raw_hash != EXPECTED_PLAN_RAW_SHA256:
        raise ValueError("invalid S-070 plan: raw lock mismatch")
    if semantic_hash != EXPECTED_PLAN_SEMANTIC_SHA256:
        raise ValueError("invalid S-070 plan: semantic lock mismatch")
    if (
        plan.get("plan_id") != PLAN_ID
        or plan.get("plan_version") != PLAN_VERSION
        or plan.get("status") != "preregistered_not_executed"
        or plan.get("contract_version") != "0.4"
        or plan.get("production_execution_authorized_now") is not False
    ):
        raise ValueError("invalid S-070 identity or result-free state")
    result_lock = plan.get("result_free_lock", {})
    forbidden_true = (
        "observed_trajectory_values_present",
        "pilot_values_present",
        "confirmation_values_present",
        "prior_stochastic_result_artifacts_used",
    )
    if any(result_lock.get(name) is not False for name in forbidden_true):
        raise ValueError("S-070 plan contains or permits result leakage")

    protocols = plan.get("locked_model", {}).get("protocol_order")
    if tuple(protocols or ()) != tuple(protocol.value for protocol in ALL_PROTOCOLS):
        raise ValueError("S-070 plan does not cover the canonical seven protocols")
    cases = plan.get("parameter_cases")
    if not isinstance(cases, list) or len(cases) != 1:
        raise ValueError("S-070 must contain the one frozen active case")
    if tuple(cases[0].get("protocols", ())) != tuple(protocols):
        raise ValueError("active case does not cover all seven protocols")

    schedule = plan.get("numerical_schedule", {})
    if (
        schedule.get("coarse_step") != 2.0 * schedule.get("fine_step", math.nan)
        or schedule.get("coarse_to_fine_ratio") != 2
        or schedule.get("fixed_work") is not True
        or schedule.get("adaptive_time_step") is not False
        or schedule.get("bernoulli_resetting") is not False
        or schedule.get("max_reset_events_per_trajectory") != 256
    ):
        raise ValueError("invalid exact-clock paired discretization schedule")
    sampling = plan.get("sampling", {})
    if (
        sampling.get("design") != "fixed_nonadaptive_no_pilot"
        or sampling.get("pilot_size") != 0
        or sampling.get("pilot_reused_in_confirmation") is not False
        or sampling.get("interim_evaluations_planned") != 0
        or sampling.get("maximum_final_evaluations") != 1
        or sampling.get("main_count_per_protocol")
        != sampling.get("main_compute_cap_per_protocol")
        or sampling.get("unpaired_count_per_required_protocol")
        != sampling.get("unpaired_compute_cap_per_required_protocol")
        or sampling.get("continuous_polling_allowed") is not False
        or sampling.get("repeated_top_up_allowed") is not False
        or sampling.get("stop_at_first_pass_allowed") is not False
    ):
        raise ValueError("invalid fixed sampling or fail-closed cap rules")
    if not (
        3
        <= sampling["unpaired_count_per_required_protocol"]
        < sampling["main_count_per_protocol"]
    ):
        raise ValueError("unpaired confirmation must be positive and smaller")
    if tuple(sampling.get("unpaired_protocols", ())) != UNPAIRED_PROTOCOLS:
        raise ValueError("unpaired protocol set differs from H2-H4 requirements")

    windows = plan.get("late_time_windows", {})
    if (
        tuple(windows.get("available", ()))
        != ("[T/2,T]", "[2T/3,T]", "[3T/4,T]")
        or windows.get("primary") != "[2T/3,T]"
    ):
        raise ValueError("late-time windows differ from Contract Section 7")
    uncertainty = plan.get("uncertainty_and_systematic_envelopes", {})
    registry_context = _contract_registry_context(plan)
    registry_tiers = registry_context["evidence_tiers"]
    estimand_specs(
        plan,
        observable_classes=registry_context["observable_classes"],
    )
    attributes = _canonical_text_bytes(ROOT / GITATTRIBUTES_REL).decode("utf-8")
    required_attribute = (
        "experiments/S-070-all-seven-trajectory-validation-primary-v1.json "
        "text eol=lf"
    )
    if attributes.splitlines().count(required_attribute) != 1:
        raise ValueError("S-070 plan lacks its unique checkout-portable LF rule")
    if (
        uncertainty.get("primary", {}).get("quantile")
        != registry_tiers["primary"]["normal_equivalent_quantile"]
        or uncertainty.get("central_disputed", {}).get("quantile")
        != registry_tiers["central_disputed"][
            "normal_equivalent_quantile"
        ]
        or uncertainty.get("normalized_floor_fraction")
        != 0.005
        or uncertainty.get("D_eff_interval", "").find(
            "whole-trajectory bootstrap"
        )
        < 0
        or not math.isfinite(
            float(uncertainty.get("D_eff_declared_class_scale", math.nan))
        )
        or float(uncertainty.get("D_eff_declared_class_scale", math.nan)) <= 0.0
        or uncertainty.get("bootstrap_replicates") != 2048
        or uncertainty.get("bootstrap_batch_size") != 8
        or uncertainty.get("bootstrap_se_stability", {}).get("block_count") != 4
        or uncertainty.get("bootstrap_se_stability", {}).get("block_size") != 512
        or uncertainty.get("bootstrap_se_stability", {}).get(
            "maximum_relative_deviation"
        )
        != 0.1
        or "bootstrap-SE" not in uncertainty.get("D_eff_interval", "")
    ):
        raise ValueError("S-070 uncertainty rules differ from registry")
    if len(plan.get("headline_comparisons", ())) != 4:
        raise ValueError("S-070 headline-comparison coverage is incomplete")
    if not all(
        item.get("unpaired_confirmation")
        for item in plan["headline_comparisons"][1:]
    ):
        raise ValueError("central CRN comparisons lack unpaired confirmation")
    resources = plan.get("resource_estimate", {})
    fine_steps = round(schedule["end_time"] / schedule["fine_step"])
    coarse_steps = round(schedule["end_time"] / schedule["coarse_step"])
    total_trajectories = (
        len(ALL_PROTOCOLS) * sampling["main_count_per_protocol"]
        + len(UNPAIRED_PROTOCOLS)
        * sampling["unpaired_count_per_required_protocol"]
    )
    max_events = int(schedule["max_reset_events_per_trajectory"])
    fine_updates = total_trajectories * fine_steps
    coarse_updates = total_trajectories * coarse_steps
    maximum_reset_events = total_trajectories * max_events
    maximum_segments = total_trajectories * (
        fine_steps + coarse_steps + 2 * max_events
    )
    expected_weights = (
        8 * sampling["main_count_per_protocol"]
        * uncertainty["bootstrap_replicates"]
        + 2
        * sampling["unpaired_count_per_required_protocol"]
        * uncertainty["bootstrap_replicates"]
    )
    expected_multiply_adds = (
        uncertainty["bootstrap_replicates"]
        * 3
        * resources.get("recorded_times", -1)
        * (
            18 * sampling["main_count_per_protocol"]
            + 4 * sampling["unpaired_count_per_required_protocol"]
        )
    )
    if (
        resources.get("total_trajectories") != total_trajectories
        or resources.get("fine_steps_per_trajectory") != fine_steps
        or resources.get("coarse_steps_per_trajectory") != coarse_steps
        or resources.get("max_reset_events_per_trajectory") != max_events
        or resources.get("fine_base_state_segment_updates") != fine_updates
        or resources.get("coarse_base_state_segment_updates") != coarse_updates
        or resources.get("maximum_total_reset_events") != maximum_reset_events
        or resources.get("maximum_fine_plus_coarse_state_segment_updates")
        != maximum_segments
        or resources.get("exact_bootstrap_trajectory_weight_draws")
        != expected_weights
        or resources.get("maximum_bootstrap_feature_multiply_add_terms")
        != expected_multiply_adds
        or resources.get("recorded_times")
        != round(schedule["end_time"] / schedule["record_step"]) + 1
        or resources.get("minimum_free_disk_bytes") != 1_500_000_000
        or resources.get("minimum_available_memory_bytes") != 1_000_000_000
    ):
        raise ValueError("S-070 result-free resource estimate differs from schedule")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def audit_isolation() -> dict[str, Any]:
    kernel_path = ROOT / KERNEL_REL
    adapter_path = ROOT / ADAPTER_REL
    kernel_imports = _imports(kernel_path)
    adapter_imports = _imports(adapter_path)
    if any(name.startswith("phasemap.theory") for name in kernel_imports):
        raise ValueError("trajectory kernel imports forbidden theory code")
    kernel_text = kernel_path.read_text(encoding="utf-8")
    forbidden_markers = (
        "artifacts/raw/S-011",
        "artifacts/raw/S-012",
        "artifacts/raw/S-021",
        "formula_registry",
        "moment_operator",
    )
    if any(marker in kernel_text for marker in forbidden_markers):
        raise ValueError("trajectory kernel contains forbidden result/formula marker")
    if any(name.startswith("phasemap.simulation.trajectory_validation") for name in adapter_imports):
        raise ValueError("reference adapter imports the trajectory kernel")
    return {
        "kernel_imports": sorted(kernel_imports),
        "adapter_imports": sorted(adapter_imports),
        "trajectory_kernel_theory_imports": False,
        "reference_layer_separate": True,
        "status": "validated",
    }


def source_manifest(
    *,
    root: Path = ROOT,
    paths: tuple[Path, ...] = MANIFEST_PATHS,
) -> dict[str, str]:
    missing = [
        path.as_posix() for path in paths if not (root / path).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"S-070 source manifest paths missing: {missing}")
    return {
        path.as_posix(): _canonical_file_sha256(root / path)
        for path in sorted(paths, key=lambda item: item.as_posix())
    }


def source_manifest_digest(manifest: Mapping[str, str] | None = None) -> str:
    files = source_manifest() if manifest is None else dict(manifest)
    envelope = {
        "algorithm": "sha256",
        "canonicalization": SOURCE_MANIFEST_CANONICALIZATION,
        "files": files,
    }
    return _sha256_bytes(_semantic_bytes(envelope))


def acceptance_record(
    reviewed_manifest_sha256: str | None = None,
) -> dict[str, str]:
    digest = (
        source_manifest_digest()
        if reviewed_manifest_sha256 is None
        else reviewed_manifest_sha256
    )
    return {
        "disposition": "PASS",
        "plan_id": PLAN_ID,
        "plan_raw_sha256": EXPECTED_PLAN_RAW_SHA256,
        "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
        "plan_version": PLAN_VERSION,
        "reviewed_manifest_sha256": digest,
    }


def acceptance_marker(reviewed_manifest_sha256: str | None = None) -> str:
    return AUDIT_MARKER_PREFIX + _semantic_bytes(
        acceptance_record(reviewed_manifest_sha256)
    ).decode("utf-8")


def validate() -> dict[str, Any]:
    plan = load_preregistered_plan(ROOT / PLAN_REL)
    validate_preregistered_plan(plan)
    isolation = audit_isolation()
    manifest = source_manifest()
    manifest_digest = source_manifest_digest(manifest)
    return {
        "plan_id": PLAN_ID,
        "plan_raw_sha256": EXPECTED_PLAN_RAW_SHA256,
        "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
        "reviewed_source_manifest": manifest,
        "reviewed_source_manifest_sha256": manifest_digest,
        "source_manifest_canonicalization": SOURCE_MANIFEST_CANONICALIZATION,
        "v071_acceptance_header": AUDIT_HEADER,
        "v071_acceptance_disposition": "**Disposition:** PASS",
        "v071_acceptance_marker": acceptance_marker(manifest_digest),
        "manifest_entries": len(manifest),
        "isolation": isolation,
        "production_stochastic_execution": False,
        "status": "validated_result_free",
    }


def _clean_source_commit() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    if status.strip():
        raise RuntimeError("clean committed source is required for production")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if len(commit) != 40:
        raise RuntimeError("Git did not return a full source commit")
    return commit


def authenticate_v071(
    audit_path: Path | None = None,
    *,
    reviewed_manifest_sha256: str | None = None,
) -> dict[str, str]:
    audit = ROOT / AUDIT_REL if audit_path is None else audit_path
    if not audit.is_file():
        raise PermissionError("V-071 audit artifact is absent; production is prohibited")
    try:
        text = _canonical_text_bytes(audit).decode("utf-8")
    except ValueError as exc:
        raise PermissionError("V-071 audit is not canonical readable text") from exc
    lines = text.splitlines()
    disposition_lines = [
        line for line in lines if line.startswith("**Disposition:**")
    ]
    if disposition_lines != ["**Disposition:** PASS"]:
        raise PermissionError(
            "V-071 requires exactly one unambiguous PASS disposition"
        )
    header_indices = [
        index for index, line in enumerate(lines) if line == AUDIT_HEADER
    ]
    if len(header_indices) != 1:
        raise PermissionError("V-071 requires exactly one acceptance header")
    if text.count(AUDIT_MARKER_PREFIX) != 1:
        raise PermissionError(
            "V-071 requires one marker occurrence, including quoted text"
        )
    marker_indices = [
        index
        for index, line in enumerate(lines)
        if line.startswith(AUDIT_MARKER_PREFIX)
    ]
    if len(marker_indices) != 1:
        raise PermissionError("V-071 requires exactly one standalone marker")
    header_index = header_indices[0]
    marker_index = marker_indices[0]
    if marker_index != header_index + 1:
        raise PermissionError(
            "V-071 marker must immediately follow the acceptance header"
        )
    marker_line = lines[marker_index]
    if marker_line.lstrip() != marker_line or marker_line.startswith(
        (">", "-", "*", "`")
    ):
        raise PermissionError("V-071 marker must be standalone and unquoted")
    if any(
        line.strip().startswith("```")
        for line in lines[max(0, marker_index - 1) : marker_index + 2]
    ):
        raise PermissionError("V-071 marker may not be fenced")
    encoded = marker_line[len(AUDIT_MARKER_PREFIX) :]
    try:
        record = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise PermissionError("V-071 structured marker is malformed") from exc
    expected = acceptance_record(reviewed_manifest_sha256)
    if not isinstance(record, dict) or record != expected:
        raise PermissionError(
            "V-071 did not accept the exact locked plan and reviewed source"
        )
    if encoded != _semantic_bytes(expected).decode("utf-8"):
        raise PermissionError("V-071 structured marker is not canonical JSON")
    return expected


def _load_reference_adapter() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s070_reference_adapter_after_simulation", ROOT / ADAPTER_REL
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load S-070 reference adapter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _scalar_samples(
    positions: np.ndarray,
    velocities: np.ndarray,
    times: np.ndarray,
) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for window_index, fraction in enumerate(WINDOW_FRACTIONS):
        mask = times >= fraction * times[-1]
        suffix = str(window_index)
        result[f"speed_{suffix}"] = np.mean(
            np.sum(velocities[mask] ** 2, axis=2), axis=0
        )
        result[f"r_dot_v_{suffix}"] = np.mean(
            np.sum(positions[mask] * velocities[mask], axis=2), axis=0
        )
        result[f"raw_msd_{suffix}"] = np.mean(
            np.sum(positions[mask] ** 2, axis=2), axis=0
        )
        result[f"v_x_{suffix}"] = np.mean(velocities[mask, :, 0], axis=0)
    return result


def _simulate_stream(
    plan: Mapping[str, Any],
    protocol: Protocol,
    *,
    count: int,
    base_seed: int,
    stream_base: int,
    destination: Path,
) -> dict[str, Any]:
    case = plan["parameter_cases"][0]
    schedule = plan["numerical_schedule"]
    chunk_size = int(schedule["chunk_size"])
    if count % chunk_size:
        raise ValueError("fixed trajectory count must be divisible by chunk size")

    positions: dict[str, list[np.ndarray]] = {"fine": [], "coarse": []}
    scalars: dict[str, list[np.ndarray]] = {}
    hashers = {
        name: hashlib.sha256()
        for name in (
            "fine_positions",
            "fine_velocities",
            "fine_orientations",
            "coarse_positions",
            "coarse_velocities",
            "coarse_orientations",
            "reset_clock_chunks",
        )
    }
    reset_count = 0
    times: np.ndarray | None = None
    params = ModelParams(
        inertia=float(case["M"]),
        activity=float(case["Pe"]),
        reset_rate=float(case["rho"]),
    )
    for chunk_index, start in enumerate(range(0, count, chunk_size)):
        result = simulate_paired_paths(
            params,
            protocol,
            PairedPathConfig(
                end_time=float(schedule["end_time"]),
                fine_step=float(schedule["fine_step"]),
                record_step=float(schedule["record_step"]),
                ensemble_size=min(chunk_size, count - start),
                base_seed=base_seed,
                case_code=int(case["case_code"]),
                stream_code=stream_base + chunk_index,
                max_reset_events_per_trajectory=int(
                    schedule["max_reset_events_per_trajectory"]
                ),
            ),
        )
        if times is None:
            times = result.times
        elif not np.array_equal(times, result.times):
            raise RuntimeError("chunk record times differ")
        for resolution in ("fine", "coarse"):
            pos = getattr(result, f"{resolution}_positions")
            vel = getattr(result, f"{resolution}_velocities")
            ori = getattr(result, f"{resolution}_orientations")
            positions[resolution].append(pos)
            for label, array in (
                (f"{resolution}_positions", pos),
                (f"{resolution}_velocities", vel),
                (f"{resolution}_orientations", ori),
            ):
                hashers[label].update(
                    np.ascontiguousarray(array, dtype="<f8").tobytes()
                )
            for name, values in _scalar_samples(pos, vel, result.times).items():
                scalars.setdefault(f"{resolution}_{name}", []).append(values)
        hashers["reset_clock_chunks"].update(
            bytes.fromhex(result.reset_clock_sha256)
        )
        reset_count += int(np.sum(result.reset_counts))
    if times is None:
        raise RuntimeError("no trajectory chunks were simulated")

    payload: dict[str, np.ndarray] = {"times": times}
    for resolution in ("fine", "coarse"):
        payload[f"{resolution}_positions"] = np.concatenate(
            positions[resolution], axis=1
        )
    for name, chunks in scalars.items():
        payload[name] = np.concatenate(chunks)
    np.savez(destination, **payload)
    return {
        "protocol": protocol.value,
        "count": count,
        "base_seed": base_seed,
        "stream_base": stream_base,
        "chunks": count // chunk_size,
        "reset_event_count": reset_count,
        "hashes": {name: hasher.hexdigest() for name, hasher in hashers.items()},
    }


def _combine_required_outcomes(*outcomes: str) -> str:
    """Preserve any required contradiction; unresolved never masks it."""

    allowed = {"validated", "contradicted", "unresolved"}
    if not outcomes or any(value not in allowed for value in outcomes):
        raise ValueError("required outcomes must use the registered vocabulary")
    if "contradicted" in outcomes:
        return "contradicted"
    if "unresolved" in outcomes:
        return "unresolved"
    return "validated"


def _signed_interval_outcome(
    *,
    lower: float,
    upper: float,
    b_window: float,
    b_disc: float,
    required_claim: str,
) -> str:
    expanded_lower = lower - b_window - b_disc
    expanded_upper = upper + b_window + b_disc
    if required_claim in {"equality_reference", "equality_zero"}:
        return "validated"
    if required_claim == "positive":
        if expanded_lower > 0.0:
            return "validated"
        if expanded_upper <= 0.0:
            return "contradicted"
        return "unresolved"
    if required_claim == "negative":
        if expanded_upper < 0.0:
            return "validated"
        if expanded_lower >= 0.0:
            return "contradicted"
        return "unresolved"
    raise ValueError(f"unknown required sign/equality claim: {required_claim}")


def _ordinary_comparison(
    data: Mapping[str, np.ndarray],
    *,
    comparison_id: str | None = None,
    name: str,
    reference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    required_claim: str = "equality_reference",
    relative_term_enabled: bool = True,
) -> dict[str, Any]:
    tier_rule = plan["uncertainty_and_systematic_envelopes"][tier]
    quantile = float(tier_rule["quantile"])
    relative = float(tier_rule["relative_margin"])
    floor = float(
        plan["uncertainty_and_systematic_envelopes"][
            "normalized_floor_fraction"
        ]
    )
    fine = data[f"fine_{name}_{PRIMARY_WINDOW_INDEX}"]
    coarse = data[f"coarse_{name}_{PRIMARY_WINDOW_INDEX}"]
    estimate, se = mean_and_standard_error(fine)
    paired_delta, paired_se = paired_mean_and_standard_error(fine, coarse)
    window_estimates = [
        float(np.mean(data[f"fine_{name}_{index}"]))
        for index in range(len(WINDOW_FRACTIONS))
    ]
    b_window = max(
        abs(value - window_estimates[PRIMARY_WINDOW_INDEX])
        for value in window_estimates
    )
    b_disc = abs(paired_delta) + quantile * paired_se
    margin = floor * characteristic_scale + (
        relative * abs(reference) if relative_term_enabled else 0.0
    )
    delta = estimate - reference
    discrepancy_lower = delta - quantile * se
    discrepancy_upper = delta + quantile * se
    outcome = classify_expanded_interval(
        lower=discrepancy_lower,
        upper=discrepancy_upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    disc_outcome = classify_expanded_interval(
        lower=paired_delta - quantile * paired_se,
        upper=paired_delta + quantile * paired_se,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = estimate - quantile * se
    estimand_upper = estimate + quantile * se
    sign_outcome = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    row = {
        "observable": name,
        "tier": tier,
        "reference": reference,
        "estimate": estimate,
        "standard_error": se,
        "discrepancy_interval": [discrepancy_lower, discrepancy_upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign_outcome,
        "paired_fine_coarse": {
            "estimate": paired_delta,
            "standard_error": paired_se,
            "classification": disc_outcome,
        },
        "scientific_discrepancy_classification": outcome,
        "classification": _combine_required_outcomes(
            outcome, disc_outcome, sign_outcome
        ),
    }
    if comparison_id is not None:
        row["comparison_id"] = comparison_id
    return row


def _ordinary_protocol_pair_comparison(
    left_data: Mapping[str, np.ndarray],
    right_data: Mapping[str, np.ndarray],
    *,
    comparison_id: str,
    left_protocol: str,
    right_protocol: str,
    name: str,
    reference_difference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    required_claim: str = "equality_reference",
) -> dict[str, Any]:
    """Classify a disclosed CRN protocol contrast at trajectory level."""

    tier_rule = plan["uncertainty_and_systematic_envelopes"][tier]
    quantile = float(tier_rule["quantile"])
    relative = float(tier_rule["relative_margin"])
    floor = float(
        plan["uncertainty_and_systematic_envelopes"][
            "normalized_floor_fraction"
        ]
    )
    fine_difference = (
        left_data[f"fine_{name}_{PRIMARY_WINDOW_INDEX}"]
        - right_data[f"fine_{name}_{PRIMARY_WINDOW_INDEX}"]
    )
    coarse_difference = (
        left_data[f"coarse_{name}_{PRIMARY_WINDOW_INDEX}"]
        - right_data[f"coarse_{name}_{PRIMARY_WINDOW_INDEX}"]
    )
    estimate, se = mean_and_standard_error(fine_difference)
    discretization, discretization_se = paired_mean_and_standard_error(
        fine_difference, coarse_difference
    )
    window_estimates = [
        float(
            np.mean(
                left_data[f"fine_{name}_{index}"]
                - right_data[f"fine_{name}_{index}"]
            )
        )
        for index in range(len(WINDOW_FRACTIONS))
    ]
    b_window = max(
        abs(value - window_estimates[PRIMARY_WINDOW_INDEX])
        for value in window_estimates
    )
    b_disc = abs(discretization) + quantile * discretization_se
    margin = (
        floor * characteristic_scale
        + relative * abs(reference_difference)
    )
    delta = estimate - reference_difference
    discrepancy_lower = delta - quantile * se
    discrepancy_upper = delta + quantile * se
    outcome = classify_expanded_interval(
        lower=discrepancy_lower,
        upper=discrepancy_upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    disc_outcome = classify_expanded_interval(
        lower=discretization - quantile * discretization_se,
        upper=discretization + quantile * discretization_se,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = estimate - quantile * se
    estimand_upper = estimate + quantile * se
    sign_outcome = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    return {
        "comparison_id": comparison_id,
        "protocols": [left_protocol, right_protocol],
        "observable": name,
        "comparison_kind": "paired_protocol_common_random_numbers",
        "tier": tier,
        "reference_difference": reference_difference,
        "estimate": estimate,
        "standard_error": se,
        "discrepancy_interval": [discrepancy_lower, discrepancy_upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign_outcome,
        "paired_fine_coarse": {
            "estimate": discretization,
            "standard_error": discretization_se,
            "classification": disc_outcome,
        },
        "scientific_discrepancy_classification": outcome,
        "classification": _combine_required_outcomes(
            outcome, disc_outcome, sign_outcome
        ),
    }


def _ordinary_unpaired_protocol_pair_comparison(
    left_data: Mapping[str, np.ndarray],
    right_data: Mapping[str, np.ndarray],
    *,
    comparison_id: str,
    left_protocol: str,
    right_protocol: str,
    name: str,
    reference_difference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    required_claim: str = "equality_reference",
) -> dict[str, Any]:
    """Classify a protocol contrast from independent trajectory streams."""

    tier_rule = plan["uncertainty_and_systematic_envelopes"][tier]
    quantile = float(tier_rule["quantile"])
    relative = float(tier_rule["relative_margin"])
    floor = float(
        plan["uncertainty_and_systematic_envelopes"][
            "normalized_floor_fraction"
        ]
    )
    left_fine = left_data[f"fine_{name}_{PRIMARY_WINDOW_INDEX}"]
    right_fine = right_data[f"fine_{name}_{PRIMARY_WINDOW_INDEX}"]
    left_mean, left_se = mean_and_standard_error(left_fine)
    right_mean, right_se = mean_and_standard_error(right_fine)
    estimate = left_mean - right_mean
    se = math.sqrt(left_se * left_se + right_se * right_se)

    left_disc = (
        left_fine - left_data[f"coarse_{name}_{PRIMARY_WINDOW_INDEX}"]
    )
    right_disc = (
        right_fine - right_data[f"coarse_{name}_{PRIMARY_WINDOW_INDEX}"]
    )
    left_disc_mean, left_disc_se = mean_and_standard_error(left_disc)
    right_disc_mean, right_disc_se = mean_and_standard_error(right_disc)
    discretization = left_disc_mean - right_disc_mean
    discretization_se = math.sqrt(
        left_disc_se * left_disc_se + right_disc_se * right_disc_se
    )
    window_estimates = [
        float(
            np.mean(left_data[f"fine_{name}_{index}"])
            - np.mean(right_data[f"fine_{name}_{index}"])
        )
        for index in range(len(WINDOW_FRACTIONS))
    ]
    b_window = max(
        abs(value - window_estimates[PRIMARY_WINDOW_INDEX])
        for value in window_estimates
    )
    b_disc = abs(discretization) + quantile * discretization_se
    margin = floor * characteristic_scale + relative * abs(
        reference_difference
    )
    delta = estimate - reference_difference
    discrepancy_lower = delta - quantile * se
    discrepancy_upper = delta + quantile * se
    outcome = classify_expanded_interval(
        lower=discrepancy_lower,
        upper=discrepancy_upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    disc_outcome = classify_expanded_interval(
        lower=discretization - quantile * discretization_se,
        upper=discretization + quantile * discretization_se,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = estimate - quantile * se
    estimand_upper = estimate + quantile * se
    sign_outcome = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    return {
        "comparison_id": comparison_id,
        "protocols": [left_protocol, right_protocol],
        "observable": name,
        "comparison_kind": "unpaired_protocol_independent_streams",
        "tier": tier,
        "reference_difference": reference_difference,
        "estimate": estimate,
        "standard_error": se,
        "component_standard_errors": {
            "left": left_se,
            "right": right_se,
            "combination": "sqrt(left_se^2+right_se^2)",
        },
        "discrepancy_interval": [discrepancy_lower, discrepancy_upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign_outcome,
        "paired_fine_coarse_within_protocol": {
            "estimate": discretization,
            "standard_error": discretization_se,
            "component_standard_errors": {
                "left": left_disc_se,
                "right": right_disc_se,
                "combination": "sqrt(left_se^2+right_se^2)",
            },
            "classification": disc_outcome,
        },
        "scientific_discrepancy_classification": outcome,
        "classification": _combine_required_outcomes(
            outcome, disc_outcome, sign_outcome
        ),
    }


def _position_statistic(
    times: np.ndarray,
    positions: np.ndarray,
    *,
    kind: str,
    fraction: float,
) -> float:
    if kind == "centered_variance":
        curve = covariance_trace_curve(positions)
        return float(np.mean(curve[times >= fraction * times[-1]]))
    if kind == "D_eff":
        return effective_diffusion(
            times, positions, window_start_fraction=fraction
        )
    raise ValueError(f"unknown position statistic: {kind}")


def _position_sufficient_features(positions: np.ndarray) -> np.ndarray:
    """Return per-trajectory features sufficient for centered covariance."""

    if (
        positions.ndim != 3
        or positions.shape[2] != 2
        or not np.all(np.isfinite(positions))
    ):
        raise ValueError("positions must be finite with shape (time,N,2)")
    x = positions[:, :, 0].T
    y = positions[:, :, 1].T
    radial_second = np.sum(positions * positions, axis=2).T
    return np.ascontiguousarray(
        np.concatenate((x, y, radial_second), axis=1), dtype=float
    )


def _bootstrap_covariance_curves(
    weights: np.ndarray,
    features: np.ndarray,
    time_count: int,
) -> np.ndarray:
    """Exactly recompute centered covariance curves from resample counts."""

    if (
        weights.ndim != 2
        or features.ndim != 2
        or weights.shape[1] != features.shape[0]
        or features.shape[1] != 3 * time_count
    ):
        raise ValueError("bootstrap weight/feature shapes are inconsistent")
    sample_size = features.shape[0]
    if sample_size < 3 or np.any(np.sum(weights, axis=1) != sample_size):
        raise ValueError("each bootstrap row must contain exactly N draws")
    totals = weights @ features
    sum_x = totals[:, :time_count]
    sum_y = totals[:, time_count : 2 * time_count]
    sum_r2 = totals[:, 2 * time_count :]
    return (
        sum_r2 - (sum_x * sum_x + sum_y * sum_y) / sample_size
    ) / (sample_size - 1)


def _curve_statistic_batch(
    times: np.ndarray,
    curves: np.ndarray,
    *,
    kind: str,
    fraction: float,
) -> np.ndarray:
    mask = times >= fraction * times[-1]
    if kind == "centered_variance":
        return np.mean(curves[:, mask], axis=1)
    if kind == "D_eff":
        x = times[mask]
        centered_x = x - x.mean()
        denominator = float(np.dot(centered_x, centered_x))
        return (curves[:, mask] - curves[:, mask].mean(axis=1, keepdims=True)) @ centered_x / (4.0 * denominator)
    raise ValueError(f"unknown curve statistic: {kind}")


def _bootstrap_se_stability(
    values: np.ndarray,
    *,
    block_count: int,
    maximum_relative_deviation: float,
) -> dict[str, Any]:
    """Apply the fixed replicate-block stability diagnostic to a bootstrap SE."""

    sample = np.asarray(values, dtype=float)
    if (
        sample.ndim != 1
        or sample.size < 2 * block_count
        or sample.size % block_count
        or not np.all(np.isfinite(sample))
    ):
        raise ValueError("bootstrap stability sample has invalid shape or values")
    full_se = float(sample.std(ddof=1))
    block_standard_errors = [
        float(block.std(ddof=1)) for block in np.split(sample, block_count)
    ]
    if full_se == 0.0:
        maximum = (
            0.0
            if all(value == 0.0 for value in block_standard_errors)
            else math.inf
        )
    else:
        maximum = max(
            abs(value - full_se) / full_se
            for value in block_standard_errors
        )
    return {
        "full_standard_error": full_se,
        "block_count": block_count,
        "block_size": sample.size // block_count,
        "block_standard_errors": block_standard_errors,
        "maximum_relative_deviation": maximum,
        "allowed_maximum_relative_deviation": maximum_relative_deviation,
        "classification": (
            "validated"
            if maximum <= maximum_relative_deviation
            else "unresolved"
        ),
    }


def _bootstrap_position_comparison(
    data: Mapping[str, np.ndarray],
    *,
    comparison_id: str | None = None,
    kind: str,
    reference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    seed: int,
    required_claim: str = "equality_reference",
) -> dict[str, Any]:
    times = data["times"]
    fine = data["fine_positions"]
    coarse = data["coarse_positions"]
    count = fine.shape[1]
    replicates = int(
        plan["uncertainty_and_systematic_envelopes"]["bootstrap_replicates"]
    )
    quantile = float(
        plan["uncertainty_and_systematic_envelopes"][tier]["quantile"]
    )
    relative = float(
        plan["uncertainty_and_systematic_envelopes"][tier]["relative_margin"]
    )
    floor = float(
        plan["uncertainty_and_systematic_envelopes"][
            "normalized_floor_fraction"
        ]
    )
    point_fine = _position_statistic(
        times,
        fine,
        kind=kind,
        fraction=WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX],
    )
    point_coarse = _position_statistic(
        times,
        coarse,
        kind=kind,
        fraction=WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX],
    )
    window_values = [
        _position_statistic(times, fine, kind=kind, fraction=fraction)
        for fraction in WINDOW_FRACTIONS
    ]
    b_window = max(
        abs(value - window_values[PRIMARY_WINDOW_INDEX])
        for value in window_values
    )
    rng = np.random.default_rng(seed)
    fine_boot = np.empty(replicates, dtype=float)
    paired_boot = np.empty(replicates, dtype=float)
    batch_size = int(
        plan["uncertainty_and_systematic_envelopes"]["bootstrap_batch_size"]
    )
    probabilities = np.full(count, 1.0 / count, dtype=float)
    fine_features = _position_sufficient_features(fine)
    coarse_features = _position_sufficient_features(coarse)
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        weights = rng.multinomial(
            count, probabilities, size=stop - start
        )
        fine_curves = _bootstrap_covariance_curves(
            weights, fine_features, times.size
        )
        coarse_curves = _bootstrap_covariance_curves(
            weights, coarse_features, times.size
        )
        fine_values = _curve_statistic_batch(
            times,
            fine_curves,
            kind=kind,
            fraction=WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX],
        )
        coarse_values = _curve_statistic_batch(
            times,
            coarse_curves,
            kind=kind,
            fraction=WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX],
        )
        fine_boot[start:stop] = fine_values
        paired_boot[start:stop] = fine_values - coarse_values
    stability_rule = plan["uncertainty_and_systematic_envelopes"][
        "bootstrap_se_stability"
    ]
    fine_stability = _bootstrap_se_stability(
        fine_boot,
        block_count=int(stability_rule["block_count"]),
        maximum_relative_deviation=float(
            stability_rule["maximum_relative_deviation"]
        ),
    )
    paired_stability = _bootstrap_se_stability(
        paired_boot,
        block_count=int(stability_rule["block_count"]),
        maximum_relative_deviation=float(
            stability_rule["maximum_relative_deviation"]
        ),
    )
    bootstrap_se = float(fine_stability["full_standard_error"])
    paired_se = float(paired_stability["full_standard_error"])
    delta = point_fine - reference
    lower = delta - quantile * bootstrap_se
    upper = delta + quantile * bootstrap_se
    paired_point = point_fine - point_coarse
    paired_lower = paired_point - quantile * paired_se
    paired_upper = paired_point + quantile * paired_se
    b_disc = abs(paired_point) + quantile * paired_se
    margin = floor * characteristic_scale + relative * abs(reference)
    outcome = classify_expanded_interval(
        lower=float(lower),
        upper=float(upper),
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    disc_outcome = classify_expanded_interval(
        lower=float(paired_lower),
        upper=float(paired_upper),
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = point_fine - quantile * bootstrap_se
    estimand_upper = point_fine + quantile * bootstrap_se
    sign_outcome = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    stability_outcome = _combine_required_outcomes(
        fine_stability["classification"],
        paired_stability["classification"],
    )
    row = {
        "observable": kind,
        "tier": tier,
        "reference": reference,
        "estimate": point_fine,
        "standard_error": bootstrap_se,
        "discrepancy_interval": [float(lower), float(upper)],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "bootstrap_replicates": replicates,
        "bootstrap_se_stability": fine_stability,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign_outcome,
        "paired_fine_coarse": {
            "estimate": paired_point,
            "standard_error": paired_se,
            "interval": [float(paired_lower), float(paired_upper)],
            "bootstrap_se_stability": paired_stability,
            "classification": disc_outcome,
        },
        "scientific_discrepancy_classification": outcome,
        "classification": _combine_required_outcomes(
            outcome,
            disc_outcome,
            sign_outcome,
            stability_outcome,
        ),
    }
    if comparison_id is not None:
        row["comparison_id"] = comparison_id
    return row


def _bootstrap_position_pair_comparison(
    left_data: Mapping[str, np.ndarray],
    right_data: Mapping[str, np.ndarray],
    *,
    comparison_id: str,
    left_protocol: str,
    right_protocol: str,
    kind: str,
    reference_difference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    seed: int,
    paired_protocols: bool,
    required_claim: str,
) -> dict[str, Any]:
    """Bootstrap a same-estimand protocol contrast at whole-trajectory grain."""

    left_times = left_data["times"]
    right_times = right_data["times"]
    if not np.array_equal(left_times, right_times):
        raise ValueError("protocol contrast record times differ")
    times = left_times
    left_fine = left_data["fine_positions"]
    left_coarse = left_data["coarse_positions"]
    right_fine = right_data["fine_positions"]
    right_coarse = right_data["coarse_positions"]
    left_count = left_fine.shape[1]
    right_count = right_fine.shape[1]
    if paired_protocols and left_count != right_count:
        raise ValueError("paired protocol bootstrap requires identical counts")

    primary_fraction = WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX]
    point_fine = _position_statistic(
        times, left_fine, kind=kind, fraction=primary_fraction
    ) - _position_statistic(
        times, right_fine, kind=kind, fraction=primary_fraction
    )
    point_coarse = _position_statistic(
        times, left_coarse, kind=kind, fraction=primary_fraction
    ) - _position_statistic(
        times, right_coarse, kind=kind, fraction=primary_fraction
    )
    window_values = [
        _position_statistic(times, left_fine, kind=kind, fraction=fraction)
        - _position_statistic(
            times, right_fine, kind=kind, fraction=fraction
        )
        for fraction in WINDOW_FRACTIONS
    ]
    b_window = max(
        abs(value - window_values[PRIMARY_WINDOW_INDEX])
        for value in window_values
    )

    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    replicates = int(uncertainty["bootstrap_replicates"])
    batch_size = int(uncertainty["bootstrap_batch_size"])
    quantile = float(uncertainty[tier]["quantile"])
    relative = float(uncertainty[tier]["relative_margin"])
    floor = float(uncertainty["normalized_floor_fraction"])
    rng = np.random.default_rng(seed)
    left_probabilities = np.full(left_count, 1.0 / left_count, dtype=float)
    right_probabilities = np.full(right_count, 1.0 / right_count, dtype=float)
    features = {
        "left_fine": _position_sufficient_features(left_fine),
        "left_coarse": _position_sufficient_features(left_coarse),
        "right_fine": _position_sufficient_features(right_fine),
        "right_coarse": _position_sufficient_features(right_coarse),
    }
    fine_boot = np.empty(replicates, dtype=float)
    paired_boot = np.empty(replicates, dtype=float)
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        size = stop - start
        left_weights = rng.multinomial(
            left_count, left_probabilities, size=size
        )
        right_weights = (
            left_weights
            if paired_protocols
            else rng.multinomial(
                right_count, right_probabilities, size=size
            )
        )
        left_fine_values = _curve_statistic_batch(
            times,
            _bootstrap_covariance_curves(
                left_weights, features["left_fine"], times.size
            ),
            kind=kind,
            fraction=primary_fraction,
        )
        left_coarse_values = _curve_statistic_batch(
            times,
            _bootstrap_covariance_curves(
                left_weights, features["left_coarse"], times.size
            ),
            kind=kind,
            fraction=primary_fraction,
        )
        right_fine_values = _curve_statistic_batch(
            times,
            _bootstrap_covariance_curves(
                right_weights, features["right_fine"], times.size
            ),
            kind=kind,
            fraction=primary_fraction,
        )
        right_coarse_values = _curve_statistic_batch(
            times,
            _bootstrap_covariance_curves(
                right_weights, features["right_coarse"], times.size
            ),
            kind=kind,
            fraction=primary_fraction,
        )
        replicate_difference = left_fine_values - right_fine_values
        fine_boot[start:stop] = replicate_difference
        paired_boot[start:stop] = replicate_difference - (
            left_coarse_values - right_coarse_values
        )

    stability_rule = uncertainty["bootstrap_se_stability"]
    stability_kwargs = {
        "block_count": int(stability_rule["block_count"]),
        "maximum_relative_deviation": float(
            stability_rule["maximum_relative_deviation"]
        ),
    }
    fine_stability = _bootstrap_se_stability(fine_boot, **stability_kwargs)
    paired_stability = _bootstrap_se_stability(paired_boot, **stability_kwargs)
    bootstrap_se = float(fine_stability["full_standard_error"])
    paired_se = float(paired_stability["full_standard_error"])
    delta = point_fine - reference_difference
    discrepancy_lower = delta - quantile * bootstrap_se
    discrepancy_upper = delta + quantile * bootstrap_se
    discretization = point_fine - point_coarse
    paired_lower = discretization - quantile * paired_se
    paired_upper = discretization + quantile * paired_se
    b_disc = abs(discretization) + quantile * paired_se
    margin = floor * characteristic_scale + relative * abs(
        reference_difference
    )
    outcome = classify_expanded_interval(
        lower=discrepancy_lower,
        upper=discrepancy_upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    disc_outcome = classify_expanded_interval(
        lower=paired_lower,
        upper=paired_upper,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = point_fine - quantile * bootstrap_se
    estimand_upper = point_fine + quantile * bootstrap_se
    sign_outcome = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    stability_outcome = _combine_required_outcomes(
        fine_stability["classification"],
        paired_stability["classification"],
    )
    return {
        "comparison_id": comparison_id,
        "protocols": [left_protocol, right_protocol],
        "observable": kind,
        "comparison_kind": (
            "paired_protocol_common_random_numbers"
            if paired_protocols
            else "unpaired_protocol_independent_streams"
        ),
        "tier": tier,
        "reference_difference": reference_difference,
        "estimate": point_fine,
        "standard_error": bootstrap_se,
        "discrepancy_interval": [discrepancy_lower, discrepancy_upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "bootstrap_replicates": replicates,
        "bootstrap_se_stability": fine_stability,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign_outcome,
        "paired_fine_coarse": {
            "estimate": discretization,
            "standard_error": paired_se,
            "interval": [paired_lower, paired_upper],
            "bootstrap_se_stability": paired_stability,
            "classification": disc_outcome,
        },
        "scientific_discrepancy_classification": outcome,
        "classification": _combine_required_outcomes(
            outcome,
            disc_outcome,
            sign_outcome,
            stability_outcome,
        ),
    }


def _matrix_entry(value: Any, row: int, column: int = 0) -> float:
    if not isinstance(value, list):
        raise TypeError("reference matrix is not a list")
    return float(value[row][column])


def _analyze_protocol(
    path: Path,
    protocol: str,
    references: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    with np.load(path) as loaded:
        data = {name: loaded[name] for name in loaded.files}
    rows: list[dict[str, Any]] = []
    speed_reference = float(references["speed"])
    speed_scale = abs(_matrix_entry(references["S"], 0, 0)) + abs(
        _matrix_entry(references["S"], 1, 1)
    )
    speed_tier = (
        "central_disputed" if protocol in ("PV", "PVTheta") else "primary"
    )
    rows.append(
        _ordinary_comparison(
            data,
            comparison_id=f"MAIN_{protocol}_speed_direct",
            name="speed",
            reference=speed_reference,
            characteristic_scale=speed_scale,
            tier=speed_tier,
            plan=plan,
            required_claim="positive",
        )
    )
    if protocol in POSITION_PROTOCOLS:
        centered_reference = float(references["centered_variance"])
        rows.append(
            _bootstrap_position_comparison(
                data,
                comparison_id=f"H1_{protocol}_centered_variance_direct",
                kind="centered_variance",
                reference=centered_reference,
                characteristic_scale=abs(centered_reference),
                tier="primary",
                plan=plan,
                seed=bootstrap_seed,
                required_claim="positive",
            )
        )
    else:
        vx_reference = _matrix_entry(references["v_bar"], 0, 0)
        vx_scale = math.sqrt(abs(_matrix_entry(references["S"], 0, 0)))
        rows.append(
            _ordinary_comparison(
                data,
                comparison_id=f"H2_{protocol}_v_x_direct",
                name="v_x",
                reference=vx_reference,
                characteristic_scale=vx_scale,
                tier="primary",
                plan=plan,
                required_claim=(
                    "equality_zero" if protocol == "V" else "positive"
                ),
                relative_term_enabled=protocol != "V",
            )
        )
        d_reference = float(references["D_eff"])
        d_scale = max(
            abs(d_reference),
            float(
                plan["uncertainty_and_systematic_envelopes"][
                    "D_eff_declared_class_scale"
                ]
            ),
        )
        rows.append(
            _bootstrap_position_comparison(
                data,
                comparison_id=f"H1_{protocol}_D_eff_direct",
                kind="D_eff",
                reference=d_reference,
                characteristic_scale=d_scale,
                tier="primary",
                plan=plan,
                seed=bootstrap_seed + 1,
                required_claim="positive",
            )
        )
    if protocol in ("PV", "PVTheta"):
        raw_reference = float(references["raw_MSD"])
        rows.append(
            _ordinary_comparison(
                data,
                comparison_id=f"H4_{protocol}_raw_msd_direct",
                name="raw_msd",
                reference=raw_reference,
                characteristic_scale=abs(raw_reference),
                tier="central_disputed",
                plan=plan,
                required_claim="positive",
            )
        )
        rdot_reference = float(references["r_dot_v"])
        rdot_scale = math.sqrt(abs(raw_reference * speed_reference))
        rows.append(
            _ordinary_comparison(
                data,
                comparison_id=f"H4_{protocol}_r_dot_v_direct",
                name="r_dot_v",
                reference=rdot_reference,
                characteristic_scale=rdot_scale,
                tier="central_disputed",
                plan=plan,
                required_claim="positive",
            )
        )
    for row in rows:
        row["protocol"] = protocol
        row["role"] = "main_direct_reference"
    return rows


def _load_stream_data(
    path: Path,
    *,
    include_positions: bool = True,
) -> dict[str, np.ndarray]:
    with np.load(path) as loaded:
        names = (
            loaded.files
            if include_positions
            else [
                name
                for name in loaded.files
                if name not in ("times", "fine_positions", "coarse_positions")
            ]
        )
        return {name: loaded[name] for name in names}


def _unpaired_headline_rows(
    paths: Mapping[tuple[str, str], Path],
    references: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
    *,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    """Return the required same-estimand independent-stream confirmations."""

    cache: dict[str, dict[str, np.ndarray]] = {}

    def data(protocol: str) -> dict[str, np.ndarray]:
        if protocol not in cache:
            cache[protocol] = _load_stream_data(
                paths[("unpaired", protocol)],
                include_positions=protocol in ("PV", "PVTheta"),
            )
        return cache[protocol]

    rows: list[dict[str, Any]] = []
    for left, right in (("Theta", "V"), ("VTheta", "V")):
        left_reference = _matrix_entry(references[left]["v_bar"], 0, 0)
        right_reference = _matrix_entry(references[right]["v_bar"], 0, 0)
        scale = max(
            math.sqrt(abs(_matrix_entry(references[left]["S"], 0, 0))),
            math.sqrt(abs(_matrix_entry(references[right]["S"], 0, 0))),
        )
        rows.append(
            _ordinary_unpaired_protocol_pair_comparison(
                data(left),
                data(right),
                comparison_id=f"H2_{left}_minus_{right}_v_x_unpaired",
                left_protocol=left,
                right_protocol=right,
                name="v_x",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="positive",
            )
        )

    for left, right in (
        ("PV", "V"),
        ("PTheta", "Theta"),
        ("PVTheta", "VTheta"),
    ):
        left_reference = float(references[left]["speed"])
        right_reference = float(references[right]["speed"])
        scale = max(
            abs(_matrix_entry(references[left]["S"], 0, 0))
            + abs(_matrix_entry(references[left]["S"], 1, 1)),
            abs(_matrix_entry(references[right]["S"], 0, 0))
            + abs(_matrix_entry(references[right]["S"], 1, 1)),
        )
        rows.append(
            _ordinary_unpaired_protocol_pair_comparison(
                data(left),
                data(right),
                comparison_id=f"H3_{left}_minus_{right}_speed_unpaired",
                left_protocol=left,
                right_protocol=right,
                name="speed",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="equality_zero",
            )
        )

    pv = references["PV"]
    full = references["PVTheta"]
    common_scales = {
        "speed": abs(_matrix_entry(pv["S"], 0, 0))
        + abs(_matrix_entry(pv["S"], 1, 1)),
        "raw_msd": abs(float(pv["raw_MSD"])),
        "r_dot_v": math.sqrt(abs(float(pv["raw_MSD"]) * float(pv["speed"]))),
    }
    reference_names = {
        "speed": "speed",
        "raw_msd": "raw_MSD",
        "r_dot_v": "r_dot_v",
    }
    for name in ("speed", "raw_msd", "r_dot_v"):
        reference_name = reference_names[name]
        rows.append(
            _ordinary_unpaired_protocol_pair_comparison(
                data("PV"),
                data("PVTheta"),
                comparison_id=(
                    f"H4_PV_minus_PVTheta_{name}_unpaired"
                ),
                left_protocol="PV",
                right_protocol="PVTheta",
                name=name,
                reference_difference=(
                    float(pv[reference_name]) - float(full[reference_name])
                ),
                characteristic_scale=common_scales[name],
                tier="central_disputed",
                plan=plan,
                required_claim="equality_zero",
            )
        )
    centered_reference_difference = float(pv["centered_variance"]) - float(
        full["centered_variance"]
    )
    rows.append(
        _bootstrap_position_pair_comparison(
            data("PV"),
            data("PVTheta"),
            comparison_id=(
                "H4_PV_minus_PVTheta_centered_variance_unpaired"
            ),
            left_protocol="PV",
            right_protocol="PVTheta",
            kind="centered_variance",
            reference_difference=centered_reference_difference,
            characteristic_scale=abs(centered_reference_difference),
            tier="primary",
            plan=plan,
            seed=bootstrap_seed,
            paired_protocols=False,
            required_claim="positive",
        )
    )
    for row in rows:
        row["role"] = "smaller_unpaired_same_estimand_confirmation"
    return rows


def _require_matching_reset_clocks(
    metadata: Mapping[str, Any],
    left_protocol: str,
    right_protocol: str,
) -> str:
    """Return the common reset-clock hash or fail before a paired contrast."""

    left = metadata[left_protocol]["hashes"]["reset_clock_chunks"]
    right = metadata[right_protocol]["hashes"]["reset_clock_chunks"]
    if not isinstance(left, str) or len(left) != 64 or left != right:
        raise RuntimeError(
            "paired protocol contrast requires identical reset-clock hashes: "
            f"{left_protocol} vs {right_protocol}"
        )
    return left


def _paired_headline_rows(
    paths: Mapping[tuple[str, str], Path],
    metadata: Mapping[str, Any],
    references: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
    *,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    """Return explicit H2 drift and H4 same-estimand CRN rows."""

    cache: dict[str, dict[str, np.ndarray]] = {}

    def data(protocol: str) -> dict[str, np.ndarray]:
        if protocol not in cache:
            cache[protocol] = _load_stream_data(
                paths[("main", protocol)],
                include_positions=protocol in ("PV", "PVTheta"),
            )
        return cache[protocol]

    rows: list[dict[str, Any]] = []
    for left, right in (("Theta", "V"), ("VTheta", "V")):
        _require_matching_reset_clocks(metadata, left, right)
        left_reference = _matrix_entry(references[left]["v_bar"], 0, 0)
        right_reference = _matrix_entry(references[right]["v_bar"], 0, 0)
        scale = max(
            math.sqrt(abs(_matrix_entry(references[left]["S"], 0, 0))),
            math.sqrt(abs(_matrix_entry(references[right]["S"], 0, 0))),
        )
        rows.append(
            _ordinary_protocol_pair_comparison(
                data(left),
                data(right),
                comparison_id=f"H2_{left}_minus_{right}_v_x",
                left_protocol=left,
                right_protocol=right,
                name="v_x",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="positive",
            )
        )

    pv = references["PV"]
    full = references["PVTheta"]
    common_scales = {
        "speed": abs(_matrix_entry(pv["S"], 0, 0))
        + abs(_matrix_entry(pv["S"], 1, 1)),
        "raw_msd": abs(float(pv["raw_MSD"])),
        "r_dot_v": math.sqrt(
            abs(float(pv["raw_MSD"]) * float(pv["speed"]))
        ),
    }
    _require_matching_reset_clocks(metadata, "PV", "PVTheta")
    reference_names = {
        "speed": "speed",
        "raw_msd": "raw_MSD",
        "r_dot_v": "r_dot_v",
    }
    for name in ("speed", "raw_msd", "r_dot_v"):
        reference_name = reference_names[name]
        rows.append(
            _ordinary_protocol_pair_comparison(
                data("PV"),
                data("PVTheta"),
                comparison_id=f"H4_PV_minus_PVTheta_{name}",
                left_protocol="PV",
                right_protocol="PVTheta",
                name=name,
                reference_difference=(
                    float(pv[reference_name]) - float(full[reference_name])
                ),
                characteristic_scale=common_scales[name],
                tier="central_disputed",
                plan=plan,
                required_claim="equality_zero",
            )
        )
    rows.append(
        _bootstrap_position_pair_comparison(
            data("PV"),
            data("PVTheta"),
            comparison_id="H4_PV_minus_PVTheta_centered_variance",
            left_protocol="PV",
            right_protocol="PVTheta",
            kind="centered_variance",
            reference_difference=(
                float(pv["centered_variance"])
                - float(full["centered_variance"])
            ),
            characteristic_scale=abs(
                float(pv["centered_variance"])
                - float(full["centered_variance"])
            ),
            tier="primary",
            plan=plan,
            seed=bootstrap_seed,
            paired_protocols=True,
            required_claim="positive",
        )
    )
    for row in rows:
        row["role"] = "main_common_random_number_same_estimand_contrast"
    return rows


def _reference_scope_checks(
    references: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Lock H3 common nonzero references and H4's restricted scope."""

    checks: list[dict[str, Any]] = []
    for left, right in (
        ("PV", "V"),
        ("PTheta", "Theta"),
        ("PVTheta", "VTheta"),
    ):
        left_reference = float(references[left]["speed"])
        right_reference = float(references[right]["speed"])
        difference = left_reference - right_reference
        checks.append(
            {
                "comparison_id": (
                    f"H3_{left}_{right}_speed_reference_common_nonzero"
                ),
                "protocols": [left, right],
                "observable": "speed",
                "left_reference": left_reference,
                "right_reference": right_reference,
                "reference_difference": difference,
                "required": "exact common and nonzero accepted reference",
                "classification": (
                    "validated"
                    if left_reference == right_reference
                    and left_reference != 0.0
                    else "contradicted"
                ),
            }
        )

    pv = references["PV"]
    full = references["PVTheta"]
    for field in ("speed", "r_dot_v", "raw_MSD"):
        difference = float(pv[field]) - float(full[field])
        checks.append(
            {
                "comparison_id": f"H4_reference_common_{field}",
                "reference_difference": difference,
                "required": "exact common accepted reference",
                "classification": (
                    "validated" if abs(difference) <= 1e-12 else "contradicted"
                ),
            }
        )
    centered_difference = float(pv["centered_variance"]) - float(
        full["centered_variance"]
    )
    checks.append(
        {
            "comparison_id": "H4_reference_distinct_centered_variance",
            "reference_difference": centered_difference,
            "required": "PV minus PVTheta strictly positive",
            "classification": (
                "validated" if centered_difference > 0.0 else "contradicted"
            ),
        }
    )
    return checks


def _decorate_and_validate_result_rows(
    groups: tuple[list[dict[str, Any]], ...],
    plan: Mapping[str, Any],
) -> None:
    """Attach promised row-level provenance and enforce exact table coverage."""

    context = _contract_registry_context(plan)
    specs = estimand_specs(
        plan, observable_classes=context["observable_classes"]
    )
    rows = [row for group in groups for row in group]
    identifiers = [row.get("comparison_id") for row in rows]
    if not all(isinstance(value, str) for value in identifiers):
        raise RuntimeError("every result row must have a comparison_id")
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("result comparison IDs are duplicated")
    if set(identifiers) != set(specs):
        raise RuntimeError(
            "result rows differ from the executable estimand table; "
            f"missing={sorted(set(specs) - set(identifiers))}, "
            f"extra={sorted(set(identifiers) - set(specs))}"
        )
    sampling = plan["sampling"]
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    for row in rows:
        comparison_id = row["comparison_id"]
        spec = specs[comparison_id]
        cap_role = spec["compute_cap_role"]
        if cap_role == "main":
            compute_cap = int(sampling["main_compute_cap_per_protocol"])
        elif cap_role == "unpaired":
            compute_cap = int(
                sampling["unpaired_compute_cap_per_required_protocol"]
            )
        else:
            compute_cap = 0
        tier = spec["tier"]
        coverage = (
            None if tier == "deterministic" else float(uncertainty[tier]["coverage"])
        )
        quantile = (
            None if tier == "deterministic" else float(uncertainty[tier]["quantile"])
        )
        if row.get("tier", tier) != tier:
            raise RuntimeError(
                f"result tier differs from estimand table: {comparison_id}"
            )
        if "required_sign_or_equality" in row and row[
            "required_sign_or_equality"
        ] != spec["required_sign_or_equality"]:
            raise RuntimeError(
                f"result sign/equality claim differs from table: {comparison_id}"
            )
        row.update(
            {
                "headline": spec["headline"],
                "registered_observable": spec["observable"],
                "observable_class": spec["observable_class"],
                "parent_scale_inputs": spec["parent_scale_inputs"],
                "evidence_tier": tier,
                "estimator": spec["estimator"],
                "interval_construction": spec["interval_construction"],
                "coverage": coverage,
                "quantile": quantile,
                "pairing_role": spec["pairing_role"],
                "required_sign_or_equality": spec[
                    "required_sign_or_equality"
                ],
                "registry_schema_version": context["schema_version"],
                "registry_sha256": context["registry_semantic_sha256"],
                "compute_cap": compute_cap,
                "compute_cap_role": cap_role,
            }
        )


def _aggregate(classifications: list[str]) -> str:
    if any(value == "contradicted" for value in classifications):
        return "contradicted"
    if any(value != "validated" for value in classifications):
        return "unresolved"
    return "validated"


def _available_memory_bytes() -> int:
    if os.name == "nt":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.ullAvailPhys)
    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
    return page_size * available_pages


def resource_preflight(
    plan: Mapping[str, Any],
    *,
    free_disk_bytes: int | None = None,
    available_memory_bytes: int | None = None,
    output_path: Path | None = None,
    attempt_path: Path | None = None,
) -> dict[str, int | str]:
    """Fail before any stochastic draw if fixed caps/resources are unavailable."""

    resources = plan["resource_estimate"]
    output = ROOT / OUTPUT_REL if output_path is None else output_path
    attempt = ROOT / ATTEMPT_REL if attempt_path is None else attempt_path
    if output.exists():
        raise FileExistsError(f"canonical output already exists: {output}")
    if attempt.exists():
        raise FileExistsError(f"write-once attempt sentinel already exists: {attempt}")
    free = (
        int(shutil.disk_usage(ROOT).free)
        if free_disk_bytes is None
        else int(free_disk_bytes)
    )
    available = (
        _available_memory_bytes()
        if available_memory_bytes is None
        else int(available_memory_bytes)
    )
    minimum_disk = int(resources["minimum_free_disk_bytes"])
    minimum_memory = int(resources["minimum_available_memory_bytes"])
    if free < minimum_disk:
        raise RuntimeError(
            f"resource preflight failed: free disk {free} < {minimum_disk}"
        )
    if available < minimum_memory:
        raise RuntimeError(
            "resource preflight failed: available memory "
            f"{available} < {minimum_memory}"
        )
    return {
        "status": "validated_before_stochastic_execution",
        "free_disk_bytes": free,
        "available_memory_bytes": available,
        "minimum_free_disk_bytes": minimum_disk,
        "minimum_available_memory_bytes": minimum_memory,
        "maximum_fine_plus_coarse_state_segment_updates": int(
            resources["maximum_fine_plus_coarse_state_segment_updates"]
        ),
        "maximum_total_reset_events": int(
            resources["maximum_total_reset_events"]
        ),
        "exact_bootstrap_trajectory_weight_draws": int(
            resources["exact_bootstrap_trajectory_weight_draws"]
        ),
        "maximum_bootstrap_feature_multiply_add_terms": int(
            resources["maximum_bootstrap_feature_multiply_add_terms"]
        ),
    }


def _create_attempt_sentinel(
    path: Path,
    payload: Mapping[str, Any],
) -> str:
    """Create and fsync the irreversible production-attempt record."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_pretty_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    return _sha256_file(path)


def _run_after_attempt_sentinel(
    path: Path,
    payload: Mapping[str, Any],
    callback: Callable[[], Any],
) -> Any:
    """Create the write-once sentinel, then perform the first stochastic work."""

    _create_attempt_sentinel(path, payload)
    return callback()


def _atomic_publish_once(path: Path, payload: Mapping[str, Any]) -> str:
    if path.exists():
        raise FileExistsError(f"canonical output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(_pretty_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_file(path)


def execute(plan_path: Path) -> tuple[dict[str, Any], str]:
    if plan_path.resolve() != (ROOT / PLAN_REL).resolve():
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    plan = load_preregistered_plan(ROOT / PLAN_REL)
    validate_preregistered_plan(plan)
    audit_isolation()
    manifest = source_manifest()
    manifest_digest = source_manifest_digest(manifest)
    authenticate_v071(reviewed_manifest_sha256=manifest_digest)
    commit = _clean_source_commit()
    preflight = resource_preflight(plan)
    sampling = plan["sampling"]
    seeds = plan["seed_policy"]
    case = plan["parameter_cases"][0]
    metadata: dict[str, dict[str, Any]] = {"main": {}, "unpaired": {}}
    paths: dict[tuple[str, str], Path] = {}

    with tempfile.TemporaryDirectory(prefix="phasemap-s070-") as temporary:
        temporary_root = Path(temporary)
        attempt_payload = {
            "schema_version": "1.0.0",
            "task_id": "S-071",
            "plan_id": PLAN_ID,
            "plan_version": PLAN_VERSION,
            "plan_raw_sha256": EXPECTED_PLAN_RAW_SHA256,
            "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
            "reviewed_source_manifest_sha256": manifest_digest,
            "source_commit": commit,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "resource_preflight": preflight,
            "fixed_compute_caps": plan["resource_estimate"],
            "status": "production_attempt_started_before_first_stochastic_draw",
            "retry_authorized": False,
        }
        # This is deliberately the final operation before the first RNG call.
        _create_attempt_sentinel(ROOT / ATTEMPT_REL, attempt_payload)
        # All stochastic paths and hashes are fixed before formula code loads.
        for protocol in ALL_PROTOCOLS:
            destination = temporary_root / f"main-{protocol.value}.npz"
            metadata["main"][protocol.value] = _simulate_stream(
                plan,
                protocol,
                count=int(sampling["main_count_per_protocol"]),
                base_seed=int(seeds["main_base_seed"]),
                stream_base=int(seeds["main_protocol_stream_code"]),
                destination=destination,
            )
            paths[("main", protocol.value)] = destination
        for protocol_name in UNPAIRED_PROTOCOLS:
            protocol = Protocol(protocol_name)
            destination = temporary_root / f"unpaired-{protocol.value}.npz"
            metadata["unpaired"][protocol.value] = _simulate_stream(
                plan,
                protocol,
                count=int(sampling["unpaired_count_per_required_protocol"]),
                base_seed=int(seeds["unpaired_base_seeds"][protocol.value]),
                stream_base=int(seeds["unpaired_protocol_stream_code"]),
                destination=destination,
            )
            paths[("unpaired", protocol.value)] = destination

        sector_pairs = (
            ("PV", "V"),
            ("PTheta", "Theta"),
            ("PVTheta", "VTheta"),
        )
        sector_checks = []
        for left, right in sector_pairs:
            reset_clock_sha256 = _require_matching_reset_clocks(
                metadata["main"], left, right
            )
            left_hashes = metadata["main"][left]["hashes"]
            right_hashes = metadata["main"][right]["hashes"]
            matched = all(
                left_hashes[name] == right_hashes[name]
                for name in (
                    "fine_velocities",
                    "fine_orientations",
                    "coarse_velocities",
                    "coarse_orientations",
                )
            )
            sector_checks.append(
                {
                    "comparison_id": (
                        f"H3_{left}_{right}_pathwise_internal"
                    ),
                    "pair": [left, right],
                    "observable": "complete_recorded_velocity_and_orientation_arrays",
                    "reset_clock_sha256": reset_clock_sha256,
                    "pathwise_internal_hashes_equal": matched,
                    "classification": "validated" if matched else "contradicted",
                }
            )

        adapter = _load_reference_adapter()
        references = {
            protocol.value: adapter.reference_fields(
                protocol.value,
                inertia=float(case["M"]),
                activity=float(case["Pe"]),
                reset_rate=float(case["rho"]),
                time=float(plan["numerical_schedule"]["end_time"]),
            )
            for protocol in ALL_PROTOCOLS
        }
        comparisons: list[dict[str, Any]] = []
        unpaired_comparisons: list[dict[str, Any]] = []
        bootstrap_base = int(seeds["bootstrap_base_seed"])
        for index, protocol in enumerate(ALL_PROTOCOLS):
            comparisons.extend(
                _analyze_protocol(
                    paths[("main", protocol.value)],
                    protocol.value,
                    references[protocol.value],
                    plan,
                    bootstrap_seed=bootstrap_base + 100 * index,
                )
            )
        unpaired_comparisons.extend(
            _unpaired_headline_rows(
                paths,
                references,
                plan,
                bootstrap_seed=bootstrap_base + 10000,
            )
        )
        paired_headline_comparisons = _paired_headline_rows(
            paths,
            metadata["main"],
            references,
            plan,
            bootstrap_seed=bootstrap_base + 20000,
        )
        reference_scope_checks = _reference_scope_checks(references)
        _decorate_and_validate_result_rows(
            (
                comparisons,
                paired_headline_comparisons,
                unpaired_comparisons,
                sector_checks,
                reference_scope_checks,
            ),
            plan,
        )

        classifications = [
            row["classification"] for row in comparisons
        ] + [
            row["classification"] for row in unpaired_comparisons
        ] + [
            row["classification"] for row in sector_checks
        ] + [
            row["classification"] for row in paired_headline_comparisons
        ] + [
            row["classification"] for row in reference_scope_checks
        ]
        overall = _aggregate(classifications)
        payload: dict[str, Any] = {
            "schema_version": "1.0.0",
            "task_id": "S-071",
            "plan_id": PLAN_ID,
            "status": "completed_fixed_plan",
            "contract_version": plan["contract_version"],
            "source_commit": commit,
            "source_manifest": manifest,
            "source_manifest_sha256": manifest_digest,
            "plan_raw_sha256": EXPECTED_PLAN_RAW_SHA256,
            "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
            "resource_preflight": preflight,
            "attempt_sentinel": ATTEMPT_REL.as_posix(),
            "configuration": {
                "case": case,
                "schedule": plan["numerical_schedule"],
                "sampling": sampling,
                "seed_policy": seeds,
            },
            "stream_metadata": metadata,
            "sector_identity_checks": sector_checks,
            "reference_scope_checks": reference_scope_checks,
            "comparisons": comparisons,
            "paired_headline_comparisons": paired_headline_comparisons,
            "unpaired_confirmations": unpaired_comparisons,
            "overall_classification": overall,
            "provenance": {
                "python_version": sys.version,
                "numpy_version": np.__version__,
                "operating_system": platform.platform(),
                "machine_architecture": platform.machine(),
            },
        }
        current_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if (
            current_commit != commit
            or source_manifest() != manifest
            or source_manifest_digest() != manifest_digest
        ):
            raise RuntimeError("source changed during canonical calculation")
        digest = _atomic_publish_once(ROOT / OUTPUT_REL, payload)
        if overall != "validated":
            raise RuntimeError(
                f"S-070 fixed plan ended {overall}; raw result sha256={digest}; "
                "publication and any top-up are blocked"
            )
        return payload, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "run"))
    parser.add_argument("plan", type=Path, nargs="?", default=PLAN_REL)
    arguments = parser.parse_args()
    if arguments.mode == "validate":
        if arguments.plan != PLAN_REL:
            raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
        print(json.dumps(validate(), sort_keys=True))
        return
    _, digest = execute(arguments.plan)
    print(f"published {OUTPUT_REL.as_posix()} sha256={digest}")


if __name__ == "__main__":
    main()
