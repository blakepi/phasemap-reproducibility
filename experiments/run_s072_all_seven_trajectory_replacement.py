"""Result-free validator and one-shot S-072 replacement runner.

``validate`` authenticates the fixed plan without constructing an RNG or
loading analytic references.  ``run`` remains fail-closed until V-072 binds an
exact PASS marker to the plan and source manifest.  There is no pilot, polling,
top-up, retry, alternate-output, or second-evaluation interface.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
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
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from phasemap.common.model import ModelParams
from phasemap.simulation.protocols import ALL_PROTOCOLS, Protocol
from phasemap.simulation.trajectory_replacement import (
    LEVEL_NAMES,
    ROTATIONAL_WIENER_COMPONENT,
    RESET_CLOCK_COMPONENT,
    TriplePathConfig,
    centered_covariance_curve_from_features,
    conditional_position_features,
    conditional_scalar_curves,
    richardson_samples,
    seed_tuple,
    simulate_conditional_triple_paths,
)
from phasemap.simulation.trajectory_validation import (
    classify_expanded_interval,
    mean_and_standard_error,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_REL = Path("experiments/S-072-all-seven-trajectory-replacement-primary-v1.json")
RUNNER_REL = Path("experiments/run_s072_all_seven_trajectory_replacement.py")
KERNEL_REL = Path("src/phasemap/simulation/trajectory_replacement.py")
BASE_UTIL_REL = Path("src/phasemap/simulation/trajectory_validation.py")
PROTOCOL_REL = Path("src/phasemap/simulation/protocols.py")
MODEL_REL = Path("src/phasemap/common/model.py")
ADAPTER_REL = Path("experiments/s070_reference_adapter.py")
TEST_REL = Path("tests/simulation/test_s072_trajectory_replacement.py")
PYPROJECT_REL = Path("pyproject.toml")
RUNTIME_REQUIREMENTS_REL = Path("requirements/runtime.txt")
REGISTRY_REL = Path("docs/scientific-contract/validation_registry.json")
REGISTRY_SCHEMA_REL = Path("docs/scientific-contract/validation_registry.schema.json")
REGISTRY_VALIDATOR_REL = Path("scripts/validate_validation_registry.py")
CONTRACT_REL = Path("docs/scientific-contract/CONTRACT.md")
AUDIT_REL = Path("artifacts/derived/V-072-trajectory-replacement-preregistration-audit.md")
OUTPUT_REL = Path("artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.json")
ATTEMPT_REL = Path(
    "artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.attempt.json"
)

PLAN_ID = "S-072-all-seven-trajectory-replacement-primary-v1"
PLAN_VERSION = "1.0.1"
EXPECTED_PLAN_CANONICAL_LF_SHA256 = "a0d3ea4f91e0c9bdbfd3a4c1a61af077a01e09d31e20e65821a0aebe8cabfd35"
EXPECTED_PLAN_SEMANTIC_SHA256 = "5787bf3ff0e3ec532b0fa8952912b8d8239a59ff7de7a8c36e9ffdb2a0a7e24d"
SOURCE_MANIFEST_CANONICALIZATION = "utf8_strict_eol_lf_v1"
AUDIT_HEADER = "## S-072 production acceptance"
AUDIT_MARKER_PREFIX = "S-072_AUDIT_ACCEPTANCE "
LOCKED_RUNTIME_VERSIONS = {"numpy": "2.5.1", "sympy": "1.14.0"}

POSITION_PROTOCOLS = ("P", "PV", "PTheta", "PVTheta")
TRANSPORT_PROTOCOLS = ("V", "Theta", "VTheta")
UNPAIRED_PROTOCOLS = ("V", "Theta", "PV", "PTheta", "VTheta", "PVTheta")
WINDOW_FRACTIONS = (0.5, 2.0 / 3.0, 0.75)
PRIMARY_WINDOW_INDEX = 1
SCALAR_NAMES = ("speed", "r_dot_v", "raw_msd", "v_x")
BOOTSTRAP_ANALYSES = (
    ("direct_P", 1000),
    ("direct_V", 1001),
    ("direct_Theta", 1002),
    ("direct_PV", 1003),
    ("direct_PTheta", 1004),
    ("direct_VTheta", 1005),
    ("direct_PVTheta", 1006),
    ("paired_H4_centered", 2000),
    ("unpaired_H4_centered", 3000),
)
PHASEMAP_SOURCE_PATHS = tuple(
    path.relative_to(ROOT)
    for path in sorted((ROOT / "src/phasemap").rglob("*.py"))
)
MANIFEST_PATHS = (
    CONTRACT_REL,
    REGISTRY_REL,
    REGISTRY_SCHEMA_REL,
    REGISTRY_VALIDATOR_REL,
    PLAN_REL,
    ADAPTER_REL,
    RUNNER_REL,
    TEST_REL,
    PYPROJECT_REL,
    RUNTIME_REQUIREMENTS_REL,
) + PHASEMAP_SOURCE_PATHS

REFERENCE_SOURCE_CLOSURE = (
    Path("src/phasemap/theory/formula_registry.py"),
    Path("src/phasemap/theory/nonposition_protocols.py"),
    Path("src/phasemap/theory/position_protocols.py"),
)


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


def _canonical_text_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is forbidden: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"reviewed source is not strict UTF-8: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _canonical_file_sha256(path: Path) -> str:
    return _sha256_bytes(_canonical_text_bytes(path))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


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


def _load_registry_validator(path: Path | None = None) -> Any:
    validator_path = ROOT / REGISTRY_VALIDATOR_REL if path is None else path
    spec = importlib.util.spec_from_file_location(
        "s072_reviewed_validation_registry_validator", validator_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load registry validator: {validator_path}")
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
    registry_file = ROOT / REGISTRY_REL if registry_path is None else registry_path
    schema_file = ROOT / REGISTRY_SCHEMA_REL if schema_path is None else schema_path
    contract_file = ROOT / CONTRACT_REL if contract_path is None else contract_path
    validator_file = (
        ROOT / REGISTRY_VALIDATOR_REL if validator_path is None else validator_path
    )
    registry = _load_json_object(registry_file)
    schema = _load_json_object(schema_file)
    contract_text = _canonical_text_bytes(contract_file).decode("utf-8")
    validator = _load_registry_validator(validator_file)
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
        raise ValueError("S-072 contract/registry lock is absent")
    for key, value in context.items():
        if lock.get(key) != value:
            raise ValueError(f"S-072 contract/registry lock mismatch: {key}")
    return context


def _expected_comparison_ids() -> set[str]:
    protocols = tuple(protocol.value for protocol in ALL_PROTOCOLS)
    ids = {f"MAIN_{protocol}_speed_direct" for protocol in protocols}
    ids.update(
        f"H1_{protocol}_centered_variance_direct"
        for protocol in POSITION_PROTOCOLS
    )
    ids.update(f"H1_{protocol}_D_eff_direct" for protocol in TRANSPORT_PROTOCOLS)
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
    table = plan.get("estimand_table")
    if not isinstance(table, list) or not table:
        raise ValueError("S-072 estimand table is absent")
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
    families: set[str] = set()
    for family in table:
        if not isinstance(family, dict) or not required.issubset(family):
            raise ValueError("estimand family is malformed")
        family_id = family["family_id"]
        if not isinstance(family_id, str) or family_id in families:
            raise ValueError("estimand family IDs must be unique")
        families.add(family_id)
        comparison_ids = family["comparison_ids"]
        if not isinstance(comparison_ids, list) or not comparison_ids:
            raise ValueError(f"estimand family {family_id} has no IDs")
        for comparison_id in comparison_ids:
            if not isinstance(comparison_id, str) or comparison_id in specs:
                raise ValueError("comparison IDs must be unique strings")
            spec = dict(family)
            spec.pop("comparison_ids", None)
            for field, target in (
                ("tier_by_id", "tier"),
                ("observable_class_by_id", "observable_class"),
            ):
                if field in family:
                    mapping = family[field]
                    if not isinstance(mapping, dict) or comparison_id not in mapping:
                        raise ValueError(f"missing {field} entry for {comparison_id}")
                    spec[target] = mapping[comparison_id]
                spec.pop(field, None)
            spec["comparison_id"] = comparison_id
            if spec["tier"] not in {"primary", "central_disputed", "deterministic"}:
                raise ValueError(f"invalid tier for {comparison_id}")
            if spec["compute_cap_role"] not in {"main", "unpaired", "deterministic"}:
                raise ValueError(f"invalid cap role for {comparison_id}")
            if observable_classes is not None and spec["observable_class"] not in observable_classes:
                raise ValueError(f"unregistered observable class for {comparison_id}")
            specs[comparison_id] = spec
    if set(specs) != _expected_comparison_ids():
        raise ValueError("estimand comparison coverage differs from S-071")
    return specs


def _expected_seed_domains(plan: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    seeds = plan["seed_policy"]
    case_code = int(plan["parameter_cases"][0]["case_code"])
    main = [
        {"tuple": list(seed_tuple(int(seeds["main_base_seed"]), case_code, stream, component))}
        for stream in range(16)
        for component in (RESET_CLOCK_COMPONENT, ROTATIONAL_WIENER_COMPONENT)
    ]
    unpaired = [
        {
            "protocol": protocol,
            "tuple": list(
                seed_tuple(
                    int(seeds["unpaired_base_seeds"][protocol]),
                    case_code,
                    stream,
                    component,
                )
            ),
        }
        for protocol in UNPAIRED_PROTOCOLS
        for stream in range(4)
        for component in (RESET_CLOCK_COMPONENT, ROTATIONAL_WIENER_COMPONENT)
    ]
    bootstrap = [
        {
            "analysis": analysis,
            "tuple": [int(seeds["bootstrap_base_seed"]), case_code, code, 4],
        }
        for analysis, code in BOOTSTRAP_ANALYSES
    ]
    return main, unpaired, bootstrap


def validate_seed_domains(plan: Mapping[str, Any]) -> dict[str, Any]:
    seeds = plan["seed_policy"]
    main, unpaired, bootstrap = _expected_seed_domains(plan)
    if seeds.get("explicit_main_rng_tuples") != main:
        raise ValueError("main RNG tuple enumeration differs from schedule")
    if seeds.get("explicit_unpaired_rng_tuples") != unpaired:
        raise ValueError("unpaired RNG tuple enumeration differs from schedule")
    if seeds.get("explicit_bootstrap_rng_tuples") != bootstrap:
        raise ValueError("bootstrap RNG tuple enumeration differs from schedule")
    new_tuples = [tuple(item["tuple"]) for item in main + unpaired + bootstrap]
    if len(set(new_tuples)) != 89:
        raise ValueError("S-072 RNG domains are not uniquely enumerated")
    forbidden = {int(value) for value in seeds["forbidden_s071_base_seeds"]}
    if forbidden != {
        70070001,
        70071201,
        70071301,
        70071401,
        70071501,
        70071601,
        70071701,
        70072001,
        70079999,
    }:
        raise ValueError("S-071 forbidden seed namespace is incomplete")
    if any(domain[0] in forbidden for domain in new_tuples):
        raise ValueError("S-072 RNG tuple overlaps an S-071 base namespace")
    unpaired_bases = [int(seeds["unpaired_base_seeds"][p]) for p in UNPAIRED_PROTOCOLS]
    if len(set(unpaired_bases)) != len(unpaired_bases):
        raise ValueError("unpaired protocol base seeds are not mutually distinct")
    if seeds.get("translational_component_status") != (
        "Component 2 is reserved and analytically marginalized; production "
        "must instantiate no component-2 RNG."
    ):
        raise ValueError("translational RNG component is not disabled")
    return {
        "main_unique": 32,
        "unpaired_unique": 48,
        "bootstrap_unique": 9,
        "total_unique": 89,
        "disjoint_from_s071": True,
    }


def validate_preregistered_plan(plan: Mapping[str, Any]) -> None:
    canonical_hash = _canonical_file_sha256(ROOT / PLAN_REL)
    semantic_hash = _sha256_bytes(_semantic_bytes(plan))
    if canonical_hash != EXPECTED_PLAN_CANONICAL_LF_SHA256:
        raise ValueError("invalid S-072 plan: canonical-LF lock mismatch")
    if semantic_hash != EXPECTED_PLAN_SEMANTIC_SHA256:
        raise ValueError("invalid S-072 plan: semantic lock mismatch")
    if (
        plan.get("plan_id") != PLAN_ID
        or plan.get("plan_version") != PLAN_VERSION
        or plan.get("task_id") != "S-072"
        or plan.get("status") != "preregistered_not_executed"
        or plan.get("contract_version") != "0.4"
        or plan.get("production_execution_authorized_now") is not False
    ):
        raise ValueError("invalid S-072 identity or result-free state")
    authentication = plan.get("source_authentication", {})
    if (
        authentication.get("repository_python_glob") != "src/phasemap/**/*.py"
        or authentication.get("required_reference_dependency_files")
        != [path.as_posix() for path in REFERENCE_SOURCE_CLOSURE]
        or authentication.get("runtime_dependency_files")
        != [PYPROJECT_REL.as_posix(), RUNTIME_REQUIREMENTS_REL.as_posix()]
        or authentication.get("reviewed_source_commit_binding")
        != (
            "The V-072 marker binds the newest commit touching any manifest "
            "path; production requires that commit to be an ancestor of the "
            "clean execution HEAD with no manifest-path diff."
        )
    ):
        raise ValueError("S-072 source-authentication closure is incomplete")
    runtime_lock = plan.get("runtime_environment_lock", {})
    if (
        runtime_lock.get("versions") != LOCKED_RUNTIME_VERSIONS
        or runtime_lock.get("requirements_file")
        != RUNTIME_REQUIREMENTS_REL.as_posix()
        or runtime_dependency_versions() != LOCKED_RUNTIME_VERSIONS
    ):
        raise ValueError("S-072 runtime dependency lock differs")
    result_lock = plan.get("result_free_lock", {})
    for field in (
        "observed_trajectory_values_present",
        "pilot_values_present",
        "confirmation_values_present",
        "prior_stochastic_samples_present",
        "s071_samples_pooled_or_reused",
        "production_code_reads_s071_artifacts",
    ):
        if result_lock.get(field) is not False:
            raise ValueError(f"S-072 result-free lock failed: {field}")
    if plan.get("prior_attempt_boundary", {}).get("status") != "immutable_unresolved_design_only":
        raise ValueError("S-071 immutable boundary is absent")
    protocols = [protocol.value for protocol in ALL_PROTOCOLS]
    if plan.get("locked_model", {}).get("protocol_order") != protocols:
        raise ValueError("S-072 does not cover the canonical seven protocols")
    cases = plan.get("parameter_cases")
    if not isinstance(cases, list) or len(cases) != 1 or cases[0].get("protocols") != protocols:
        raise ValueError("S-072 active case differs from the retained case")
    schedule = plan.get("numerical_schedule", {})
    if (
        schedule.get("end_time") != 32.0
        or schedule.get("finest_step") != 0.00390625
        or schedule.get("middle_step") != 0.0078125
        or schedule.get("coarse_step") != 0.015625
        or schedule.get("level_step_ratio") != [1, 2, 4]
        or schedule.get("record_step") != 2.0
        or schedule.get("chunk_size") != 4096
        or schedule.get("max_reset_events_per_trajectory") != 256
        or schedule.get("fixed_work") is not True
        or schedule.get("adaptive_time_step") is not False
        or schedule.get("bernoulli_resetting") is not False
    ):
        raise ValueError("invalid three-level fixed schedule")
    sampling = plan.get("sampling", {})
    if (
        sampling.get("design") != "fixed_nonadaptive_no_pilot_fresh_replacement"
        or sampling.get("main_conditional_units_per_protocol") != 65536
        or sampling.get("unpaired_conditional_units_per_required_protocol") != 16384
        or sampling.get("physical_translational_paths_sampled") != 0
        or sampling.get("count_change_from_s071") != 0
        or sampling.get("pilot_size") != 0
        or sampling.get("interim_evaluations_planned") != 0
        or sampling.get("maximum_final_evaluations") != 1
        or sampling.get("main_compute_cap_per_protocol") != 65536
        or sampling.get("unpaired_compute_cap_per_required_protocol") != 16384
        or sampling.get("continuous_polling_allowed") is not False
        or sampling.get("repeated_top_up_allowed") is not False
        or sampling.get("stop_at_first_pass_allowed") is not False
        or tuple(sampling.get("unpaired_protocols", ())) != UNPAIRED_PROTOCOLS
    ):
        raise ValueError("invalid fixed sampling or one-shot rules")
    windows = plan.get("late_time_windows", {})
    if (
        tuple(windows.get("available", ()))
        != ("[T/2,T]", "[2T/3,T]", "[3T/4,T]")
        or windows.get("primary") != "[2T/3,T]"
    ):
        raise ValueError("late-time windows differ from Contract Section 7")
    context = _contract_registry_context(plan)
    estimand_specs(plan, observable_classes=context["observable_classes"])
    uncertainty = plan.get("uncertainty_and_systematic_envelopes", {})
    tiers = context["evidence_tiers"]
    if (
        uncertainty.get("primary", {}).get("quantile")
        != tiers["primary"]["normal_equivalent_quantile"]
        or uncertainty.get("central_disputed", {}).get("quantile")
        != tiers["central_disputed"]["normal_equivalent_quantile"]
        or uncertainty.get("normalized_floor_fraction") != 0.005
        or uncertainty.get("bootstrap_replicates") != 2048
        or uncertainty.get("bootstrap_batch_size") != 8
        or uncertainty.get("bootstrap_se_stability", {}).get("block_count") != 4
        or uncertainty.get("bootstrap_se_stability", {}).get("block_size") != 512
        or uncertainty.get("bootstrap_se_stability", {}).get("maximum_relative_deviation") != 0.1
    ):
        raise ValueError("S-072 uncertainty rules differ from registry/S-071")
    adequacy = plan.get("variance_reduction_adequacy", {})
    if (
        adequacy.get("per_row_monte_carlo_half_width_max_fraction_of_margin") != 0.5
        or adequacy.get("per_row_combined_uncertainty_and_envelope_max_fraction_of_margin") != 0.75
        or "unresolved" not in adequacy.get("failure_outcome", "")
    ):
        raise ValueError("variance-reduction adequacy rule is not fixed")
    validate_seed_domains(plan)
    resources = plan.get("resource_estimate", {})
    expected_resources = {
        "total_conditional_units": 557056,
        "finest_steps_per_unit": 8192,
        "middle_steps_per_unit": 4096,
        "coarse_steps_per_unit": 2048,
        "maximum_total_reset_events": 142606336,
        "maximum_three_level_conditional_segments": 8413773824,
        "maximum_rotational_normal_draws": 4706009088,
        "translational_normal_draws": 0,
        "exact_bootstrap_trajectory_weight_draws": 1140850688,
        "maximum_bootstrap_feature_multiply_add_terms": 260113956864,
        "minimum_free_disk_bytes": 3000000000,
        "minimum_available_memory_bytes": 2000000000,
    }
    if any(resources.get(key) != value for key, value in expected_resources.items()):
        raise ValueError("S-072 resource arithmetic differs from fixed design")
    if plan.get("fail_closed_execution", {}).get("one_execution_command_only") is not True:
        raise ValueError("S-072 does not lock one production command")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(_canonical_text_bytes(path).decode("utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def audit_isolation() -> dict[str, Any]:
    kernel_source = _canonical_text_bytes(ROOT / KERNEL_REL).decode("utf-8")
    runner_source = _canonical_text_bytes(ROOT / RUNNER_REL).decode("utf-8")
    kernel_imports = _imports(ROOT / KERNEL_REL)
    forbidden_import = any(name.startswith("phasemap.theory") for name in kernel_imports)
    prior_task = "S-" + "071"
    forbidden_tokens = (
        f"artifacts/raw/{prior_task}",
        f"artifacts\\raw\\{prior_task}",
        f"{prior_task}-all-seven-trajectory-validation-primary-v1.json",
    )
    if forbidden_import or any(token in kernel_source for token in forbidden_tokens):
        raise RuntimeError("replacement kernel has a forbidden theory/prior-result dependency")
    if any(token in runner_source for token in forbidden_tokens):
        raise RuntimeError("production runner contains an S-071 raw-artifact route")
    if "TRANSLATIONAL_COMPONENT_MARGINALIZED" not in kernel_source:
        raise RuntimeError("kernel does not explicitly reserve translational RNG")
    manifest_paths = set(MANIFEST_PATHS)
    if not set(PHASEMAP_SOURCE_PATHS).issubset(manifest_paths):
        raise RuntimeError("source manifest omits repository Python source")
    if not set(REFERENCE_SOURCE_CLOSURE).issubset(manifest_paths):
        raise RuntimeError("source manifest omits analytic-reference dependencies")
    if not {PYPROJECT_REL, RUNTIME_REQUIREMENTS_REL}.issubset(manifest_paths):
        raise RuntimeError("source manifest omits runtime dependency locks")
    return {
        "trajectory_kernel_theory_imports": False,
        "kernel_or_runner_s071_runtime_path": False,
        "translational_rng_instantiated": False,
        "reference_adapter_loaded_during_validation": False,
        "complete_repository_python_manifest": True,
        "complete_reference_source_closure": True,
    }


def source_manifest(paths: Sequence[Path] = MANIFEST_PATHS) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"source-manifest input is absent: {relative}")
        manifest[relative.as_posix()] = _canonical_file_sha256(path)
    return manifest


def source_manifest_digest(manifest: Mapping[str, str] | None = None) -> str:
    selected = source_manifest() if manifest is None else dict(manifest)
    return _sha256_bytes(_semantic_bytes(selected))


def runtime_dependency_versions() -> dict[str, str]:
    """Return the external numerical-library versions locked by the plan."""

    return {
        "numpy": str(np.__version__),
        "sympy": importlib.metadata.version("sympy"),
    }


def manifest_source_commit(paths: Sequence[Path] = MANIFEST_PATHS) -> str:
    """Return the newest commit that changed any authenticated source path."""

    command = ["git", "log", "-1", "--format=%H", "--"] + [
        path.as_posix() for path in paths
    ]
    commit = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RuntimeError("Git did not return a full manifest-source commit")
    return commit


def acceptance_record(
    reviewed_manifest_sha256: str,
    reviewed_source_commit: str | None = None,
) -> dict[str, str]:
    source_commit = (
        manifest_source_commit()
        if reviewed_source_commit is None
        else reviewed_source_commit
    )
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise ValueError("reviewed source commit must be a full lowercase SHA")
    return {
        "disposition": "PASS",
        "plan_id": PLAN_ID,
        "plan_canonical_lf_sha256": EXPECTED_PLAN_CANONICAL_LF_SHA256,
        "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
        "plan_version": PLAN_VERSION,
        "reviewed_manifest_sha256": reviewed_manifest_sha256,
        "reviewed_source_commit": source_commit,
    }


def acceptance_marker(
    reviewed_manifest_sha256: str | None = None,
    reviewed_source_commit: str | None = None,
) -> str:
    digest = (
        source_manifest_digest()
        if reviewed_manifest_sha256 is None
        else reviewed_manifest_sha256
    )
    return AUDIT_MARKER_PREFIX + json.dumps(
        acceptance_record(digest, reviewed_source_commit),
        sort_keys=True,
        separators=(",", ":"),
    )


def validate() -> dict[str, Any]:
    plan = load_preregistered_plan(ROOT / PLAN_REL)
    validate_preregistered_plan(plan)
    isolation = audit_isolation()
    manifest = source_manifest()
    source_commit = manifest_source_commit()
    versions = runtime_dependency_versions()
    return {
        "status": "validated_result_free",
        "plan_id": PLAN_ID,
        "plan_canonical_lf_sha256": EXPECTED_PLAN_CANONICAL_LF_SHA256,
        "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
        "production_stochastic_execution": False,
        "s071_artifacts_opened": False,
        "runtime_dependency_versions": versions,
        "seed_domains": validate_seed_domains(plan),
        "isolation": isolation,
        "source_manifest_entries": len(manifest),
        "reviewed_source_manifest_sha256": source_manifest_digest(manifest),
        "reviewed_source_commit": source_commit,
        "v072_acceptance_marker": acceptance_marker(
            source_manifest_digest(manifest), source_commit
        ),
    }


def _level_window_samples(record: Any, times: np.ndarray) -> dict[str, np.ndarray]:
    curves = conditional_scalar_curves(record)
    samples: dict[str, np.ndarray] = {}
    for window_index, fraction in enumerate(WINDOW_FRACTIONS):
        mask = times >= fraction * times[-1]
        for name in SCALAR_NAMES:
            samples[f"{name}_{window_index}"] = np.mean(
                curves[name][mask], axis=0
            )
    return samples


def _simulate_stream(
    plan: Mapping[str, Any],
    protocol: Protocol,
    *,
    count: int,
    base_seed: int,
    stream_base: int,
    destination: Path,
    store_position_features: bool,
) -> dict[str, Any]:
    """Generate one fresh conditional-path stream in bounded chunks."""

    case = plan["parameter_cases"][0]
    schedule = plan["numerical_schedule"]
    chunk_size = int(schedule["chunk_size"])
    if count % chunk_size:
        raise ValueError("fixed conditional-unit count must divide chunk size")
    scalar_chunks: dict[str, list[np.ndarray]] = {}
    feature_chunks: dict[str, list[np.ndarray]] = {
        name: [] for name in LEVEL_NAMES
    }
    hashers = {
        "reset_clock_chunks": hashlib.sha256(),
        **{
            f"{level}_{field}": hashlib.sha256()
            for level in LEVEL_NAMES
            for field in (
                "position_means",
                "velocity_means",
                "orientations",
                "position_variance_per_axis",
                "position_velocity_covariance_per_axis",
                "velocity_variance_per_axis",
            )
        },
    }
    total_resets = 0
    times: np.ndarray | None = None
    params = ModelParams(
        inertia=float(case["M"]),
        activity=float(case["Pe"]),
        reset_rate=float(case["rho"]),
    )
    used_domains: list[list[int]] = []
    for chunk_index, start in enumerate(range(0, count, chunk_size)):
        stream_code = stream_base + chunk_index
        result = simulate_conditional_triple_paths(
            params,
            protocol,
            TriplePathConfig(
                end_time=float(schedule["end_time"]),
                finest_step=float(schedule["finest_step"]),
                record_step=float(schedule["record_step"]),
                ensemble_size=min(chunk_size, count - start),
                base_seed=base_seed,
                case_code=int(case["case_code"]),
                stream_code=stream_code,
                max_reset_events_per_trajectory=int(
                    schedule["max_reset_events_per_trajectory"]
                ),
            ),
        )
        used_domains.extend(
            [
                list(
                    seed_tuple(
                        base_seed,
                        int(case["case_code"]),
                        stream_code,
                        component,
                    )
                )
                for component in (
                    RESET_CLOCK_COMPONENT,
                    ROTATIONAL_WIENER_COMPONENT,
                )
            ]
        )
        if times is None:
            times = result.times
        elif not np.array_equal(times, result.times):
            raise RuntimeError("conditional-path chunk record times differ")
        level_samples: dict[str, dict[str, np.ndarray]] = {}
        for level in LEVEL_NAMES:
            record = getattr(result, level)
            level_samples[level] = _level_window_samples(record, result.times)
            if store_position_features:
                feature_chunks[level].append(conditional_position_features(record))
            for field, digest in record.array_hashes().items():
                hashers[f"{level}_{field}"].update(bytes.fromhex(digest))
        for name in SCALAR_NAMES:
            for window_index in range(len(WINDOW_FRACTIONS)):
                finest = level_samples["finest"][f"{name}_{window_index}"]
                middle = level_samples["middle"][f"{name}_{window_index}"]
                coarse = level_samples["coarse"][f"{name}_{window_index}"]
                primary, secondary = richardson_samples(
                    finest, middle, coarse
                )
                scalar_chunks.setdefault(
                    f"primary_{name}_{window_index}", []
                ).append(primary)
                scalar_chunks.setdefault(
                    f"secondary_{name}_{window_index}", []
                ).append(secondary)
        hashers["reset_clock_chunks"].update(
            bytes.fromhex(result.reset_clock_sha256)
        )
        total_resets += int(np.sum(result.reset_counts))
    if times is None:
        raise RuntimeError("no conditional-path chunks were generated")
    payload: dict[str, np.ndarray] = {"times": times}
    for name, chunks in scalar_chunks.items():
        payload[name] = np.concatenate(chunks)
    if store_position_features:
        for level in LEVEL_NAMES:
            payload[f"{level}_position_features"] = np.concatenate(
                feature_chunks[level], axis=1
            )
    np.savez(destination, **payload)
    return {
        "protocol": protocol.value,
        "conditional_unit_count": count,
        "sampled_translational_paths": 0,
        "base_seed": base_seed,
        "stream_base": stream_base,
        "chunks": count // chunk_size,
        "reset_event_count": total_resets,
        "rng_tuples": used_domains,
        "hashes": {
            name: hasher.hexdigest() for name, hasher in hashers.items()
        },
    }


def _load_stream_data(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as loaded:
        return {name: loaded[name] for name in loaded.files}


def _combine_required_outcomes(*outcomes: str) -> str:
    if not outcomes or any(
        outcome not in {"validated", "unresolved", "contradicted"}
        for outcome in outcomes
    ):
        raise ValueError("invalid classification vocabulary")
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
    raise ValueError(f"unknown sign/equality claim: {required_claim}")


def _adequacy_diagnostic(
    *,
    quantile: float,
    standard_error: float,
    b_window: float,
    b_disc: float,
    margin: float,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    rule = plan["variance_reduction_adequacy"]
    half_width = quantile * standard_error
    half_limit = (
        float(rule["per_row_monte_carlo_half_width_max_fraction_of_margin"])
        * margin
    )
    combined = half_width + b_window + b_disc
    combined_limit = (
        float(
            rule[
                "per_row_combined_uncertainty_and_envelope_max_fraction_of_margin"
            ]
        )
        * margin
    )
    passed = half_width <= half_limit and combined <= combined_limit
    return {
        "monte_carlo_half_width": half_width,
        "monte_carlo_half_width_limit": half_limit,
        "combined_uncertainty_and_envelope": combined,
        "combined_limit": combined_limit,
        "classification": "validated" if passed else "unresolved",
        "failure_authorizes_more_work": False,
    }


def _tier_values(
    plan: Mapping[str, Any], tier: str
) -> tuple[float, float, float]:
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    return (
        float(uncertainty[tier]["quantile"]),
        float(uncertainty[tier]["relative_margin"]),
        float(uncertainty["normalized_floor_fraction"]),
    )


def _ordinary_comparison_from_units(
    primary: np.ndarray,
    secondary: np.ndarray,
    window_estimates: Sequence[float],
    *,
    comparison_id: str,
    observable: str,
    reference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    required_claim: str,
    relative_term_enabled: bool = True,
) -> dict[str, Any]:
    quantile, relative, floor = _tier_values(plan, tier)
    estimate, standard_error = mean_and_standard_error(primary)
    # For first-order Richardson, the leading residual error of R_h is
    # -(R_h-R_2h)/3.  Its sign is immaterial to the symmetric envelope.
    residual_units = (primary - secondary) / 3.0
    residual, residual_se = mean_and_standard_error(residual_units)
    b_window = max(
        abs(value - window_estimates[PRIMARY_WINDOW_INDEX])
        for value in window_estimates
    )
    b_disc = abs(residual) + quantile * residual_se
    margin = floor * characteristic_scale + (
        relative * abs(reference) if relative_term_enabled else 0.0
    )
    discrepancy = estimate - reference
    lower = discrepancy - quantile * standard_error
    upper = discrepancy + quantile * standard_error
    scientific = classify_expanded_interval(
        lower=lower,
        upper=upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    residual_lower = residual - quantile * residual_se
    residual_upper = residual + quantile * residual_se
    residual_outcome = classify_expanded_interval(
        lower=residual_lower,
        upper=residual_upper,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = estimate - quantile * standard_error
    estimand_upper = estimate + quantile * standard_error
    sign = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    adequacy = _adequacy_diagnostic(
        quantile=quantile,
        standard_error=standard_error,
        b_window=b_window,
        b_disc=b_disc,
        margin=margin,
        plan=plan,
    )
    return {
        "comparison_id": comparison_id,
        "observable": observable,
        "tier": tier,
        "reference": reference,
        "estimate": estimate,
        "standard_error": standard_error,
        "discrepancy_interval": [lower, upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign,
        "richardson_residual": {
            "formula": "(R_h-R_2h)/3",
            "estimate": residual,
            "standard_error": residual_se,
            "interval": [residual_lower, residual_upper],
            "classification": residual_outcome,
        },
        "variance_reduction_adequacy": adequacy,
        "scientific_discrepancy_classification": scientific,
        "classification": _combine_required_outcomes(
            scientific, residual_outcome, sign, adequacy["classification"]
        ),
    }


def _ordinary_direct(
    data: Mapping[str, np.ndarray],
    *,
    comparison_id: str,
    name: str,
    reference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    required_claim: str,
    relative_term_enabled: bool = True,
) -> dict[str, Any]:
    primary = data[f"primary_{name}_{PRIMARY_WINDOW_INDEX}"]
    secondary = data[f"secondary_{name}_{PRIMARY_WINDOW_INDEX}"]
    windows = [
        float(np.mean(data[f"primary_{name}_{index}"]))
        for index in range(len(WINDOW_FRACTIONS))
    ]
    return _ordinary_comparison_from_units(
        primary,
        secondary,
        windows,
        comparison_id=comparison_id,
        observable=name,
        reference=reference,
        characteristic_scale=characteristic_scale,
        tier=tier,
        plan=plan,
        required_claim=required_claim,
        relative_term_enabled=relative_term_enabled,
    )


def _ordinary_protocol_pair(
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
    required_claim: str,
    paired_protocols: bool,
) -> dict[str, Any]:
    left_primary = left_data[f"primary_{name}_{PRIMARY_WINDOW_INDEX}"]
    right_primary = right_data[f"primary_{name}_{PRIMARY_WINDOW_INDEX}"]
    left_secondary = left_data[f"secondary_{name}_{PRIMARY_WINDOW_INDEX}"]
    right_secondary = right_data[f"secondary_{name}_{PRIMARY_WINDOW_INDEX}"]
    if paired_protocols:
        primary = left_primary - right_primary
        secondary = left_secondary - right_secondary
        windows = [
            float(
                np.mean(
                    left_data[f"primary_{name}_{index}"]
                    - right_data[f"primary_{name}_{index}"]
                )
            )
            for index in range(len(WINDOW_FRACTIONS))
        ]
        row = _ordinary_comparison_from_units(
            primary,
            secondary,
            windows,
            comparison_id=comparison_id,
            observable=name,
            reference=reference_difference,
            characteristic_scale=characteristic_scale,
            tier=tier,
            plan=plan,
            required_claim=required_claim,
        )
        row["comparison_kind"] = "paired_protocol_common_random_numbers"
    else:
        quantile, relative, floor = _tier_values(plan, tier)
        left_mean, left_se = mean_and_standard_error(left_primary)
        right_mean, right_se = mean_and_standard_error(right_primary)
        estimate = left_mean - right_mean
        standard_error = math.hypot(left_se, right_se)
        left_residual = (left_primary - left_secondary) / 3.0
        right_residual = (right_primary - right_secondary) / 3.0
        left_residual_mean, left_residual_se = mean_and_standard_error(
            left_residual
        )
        right_residual_mean, right_residual_se = mean_and_standard_error(
            right_residual
        )
        residual = left_residual_mean - right_residual_mean
        residual_se = math.hypot(left_residual_se, right_residual_se)
        windows = [
            float(
                np.mean(left_data[f"primary_{name}_{index}"])
                - np.mean(right_data[f"primary_{name}_{index}"])
            )
            for index in range(len(WINDOW_FRACTIONS))
        ]
        b_window = max(
            abs(value - windows[PRIMARY_WINDOW_INDEX]) for value in windows
        )
        b_disc = abs(residual) + quantile * residual_se
        margin = floor * characteristic_scale + relative * abs(
            reference_difference
        )
        discrepancy = estimate - reference_difference
        lower = discrepancy - quantile * standard_error
        upper = discrepancy + quantile * standard_error
        scientific = classify_expanded_interval(
            lower=lower,
            upper=upper,
            margin=margin,
            b_window=b_window,
            b_disc=b_disc,
        )
        residual_lower = residual - quantile * residual_se
        residual_upper = residual + quantile * residual_se
        residual_outcome = classify_expanded_interval(
            lower=residual_lower,
            upper=residual_upper,
            margin=margin,
            b_window=0.0,
            b_disc=0.0,
        )
        estimand_lower = estimate - quantile * standard_error
        estimand_upper = estimate + quantile * standard_error
        sign = _signed_interval_outcome(
            lower=estimand_lower,
            upper=estimand_upper,
            b_window=b_window,
            b_disc=b_disc,
            required_claim=required_claim,
        )
        adequacy = _adequacy_diagnostic(
            quantile=quantile,
            standard_error=standard_error,
            b_window=b_window,
            b_disc=b_disc,
            margin=margin,
            plan=plan,
        )
        row = {
            "comparison_id": comparison_id,
            "observable": name,
            "comparison_kind": "unpaired_protocol_independent_streams",
            "tier": tier,
            "reference": reference_difference,
            "reference_difference": reference_difference,
            "estimate": estimate,
            "standard_error": standard_error,
            "component_standard_errors": {
                "left": left_se,
                "right": right_se,
                "combination": "sqrt(left_se^2+right_se^2)",
            },
            "discrepancy_interval": [lower, upper],
            "estimand_interval": [estimand_lower, estimand_upper],
            "characteristic_scale": characteristic_scale,
            "margin": margin,
            "B_window": b_window,
            "B_disc": b_disc,
            "required_sign_or_equality": required_claim,
            "sign_classification": sign,
            "richardson_residual": {
                "formula": "independent difference of (R_h-R_2h)/3",
                "estimate": residual,
                "standard_error": residual_se,
                "interval": [residual_lower, residual_upper],
                "classification": residual_outcome,
            },
            "variance_reduction_adequacy": adequacy,
            "scientific_discrepancy_classification": scientific,
            "classification": _combine_required_outcomes(
                scientific,
                residual_outcome,
                sign,
                adequacy["classification"],
            ),
        }
    row["protocols"] = [left_protocol, right_protocol]
    row["reference_difference"] = reference_difference
    return row


def _covariance_curves_from_weighted_features(
    weights: np.ndarray,
    features: np.ndarray,
) -> np.ndarray:
    """Recompute total centered covariance for complete-unit resamples."""

    if (
        weights.ndim != 2
        or features.ndim != 3
        or features.shape[2] != 4
        or weights.shape[1] != features.shape[1]
    ):
        raise ValueError("bootstrap weights/features have incompatible shapes")
    count = features.shape[1]
    if count < 2 or np.any(np.sum(weights, axis=1) != count):
        raise ValueError("each bootstrap replicate must contain exactly N units")
    flattened = np.transpose(features, (1, 0, 2)).reshape(count, -1)
    means = (weights @ flattened / count).reshape(
        weights.shape[0], features.shape[0], 4
    )
    between = (count / (count - 1.0)) * (
        means[:, :, 2]
        - means[:, :, 0] * means[:, :, 0]
        - means[:, :, 1] * means[:, :, 1]
    )
    return means[:, :, 3] + between


def _curve_values(
    times: np.ndarray,
    curves: np.ndarray,
    *,
    kind: str,
    fraction: float,
) -> np.ndarray:
    if curves.ndim == 1:
        matrix = curves[None, :]
        scalar = True
    elif curves.ndim == 2:
        matrix = curves
        scalar = False
    else:
        raise ValueError("covariance curves must have one or two dimensions")
    if matrix.shape[1] != times.size:
        raise ValueError("curve and time axes differ")
    mask = times >= fraction * times[-1]
    if kind == "centered_variance":
        values = np.mean(matrix[:, mask], axis=1)
    elif kind == "D_eff":
        x = times[mask]
        centered_x = x - x.mean()
        denominator = float(np.dot(centered_x, centered_x))
        values = (
            np.sum((matrix[:, mask] - matrix[:, mask].mean(axis=1, keepdims=True)) * centered_x, axis=1)
            / denominator
            / 4.0
        )
    else:
        raise ValueError(f"unknown position statistic: {kind}")
    return values[0] if scalar else values


def _position_point(
    times: np.ndarray,
    features: np.ndarray,
    *,
    kind: str,
    fraction: float,
) -> float:
    curve = centered_covariance_curve_from_features(features)
    return float(_curve_values(times, curve, kind=kind, fraction=fraction))


def _bootstrap_se_stability(
    replicates: np.ndarray,
    *,
    block_count: int,
    maximum_relative_deviation: float,
) -> dict[str, Any]:
    values = np.asarray(replicates, dtype=float)
    if (
        values.ndim != 1
        or values.size < block_count * 2
        or values.size % block_count
        or not np.all(np.isfinite(values))
    ):
        raise ValueError("bootstrap replicates do not match fixed blocks")
    full = float(values.std(ddof=1))
    block_size = values.size // block_count
    blocks = [
        float(values[index * block_size : (index + 1) * block_size].std(ddof=1))
        for index in range(block_count)
    ]
    if full == 0.0:
        relative = 0.0 if all(value == 0.0 for value in blocks) else math.inf
    else:
        relative = max(abs(value - full) / full for value in blocks)
    return {
        "full_standard_error": full,
        "block_count": block_count,
        "block_size": block_size,
        "block_standard_errors": blocks,
        "maximum_relative_deviation": relative,
        "allowed_maximum_relative_deviation": maximum_relative_deviation,
        "classification": (
            "validated"
            if math.isfinite(relative) and relative <= maximum_relative_deviation
            else "unresolved"
        ),
    }


def _bootstrap_rng(
    plan: Mapping[str, Any], analysis_code: int
) -> np.random.Generator:
    case_code = int(plan["parameter_cases"][0]["case_code"])
    domain = [
        int(plan["seed_policy"]["bootstrap_base_seed"]),
        case_code,
        analysis_code,
        4,
    ]
    permitted = {
        tuple(item["tuple"])
        for item in plan["seed_policy"]["explicit_bootstrap_rng_tuples"]
    }
    if tuple(domain) not in permitted:
        raise RuntimeError("bootstrap RNG domain was not preregistered")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(domain)))


def _position_levels(data: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    levels = {
        level: data[f"{level}_position_features"] for level in LEVEL_NAMES
    }
    shapes = {value.shape for value in levels.values()}
    if len(shapes) != 1:
        raise ValueError("three position-feature levels differ in shape")
    return levels


def _bootstrap_position_direct(
    data: Mapping[str, np.ndarray],
    *,
    comparison_id: str,
    kind: str,
    reference: float,
    characteristic_scale: float,
    tier: str,
    plan: Mapping[str, Any],
    analysis_code: int,
    required_claim: str,
) -> dict[str, Any]:
    times = data["times"]
    levels = _position_levels(data)
    count = levels["finest"].shape[1]
    primary_fraction = WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX]
    level_points = {
        level: _position_point(
            times, features, kind=kind, fraction=primary_fraction
        )
        for level, features in levels.items()
    }
    point_primary = 2.0 * level_points["finest"] - level_points["middle"]
    point_secondary = 2.0 * level_points["middle"] - level_points["coarse"]
    window_values = []
    for fraction in WINDOW_FRACTIONS:
        finest = _position_point(
            times, levels["finest"], kind=kind, fraction=fraction
        )
        middle = _position_point(
            times, levels["middle"], kind=kind, fraction=fraction
        )
        window_values.append(2.0 * finest - middle)
    b_window = max(
        abs(value - window_values[PRIMARY_WINDOW_INDEX])
        for value in window_values
    )
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    replicates = int(uncertainty["bootstrap_replicates"])
    batch_size = int(uncertainty["bootstrap_batch_size"])
    rng = _bootstrap_rng(plan, analysis_code)
    probabilities = np.full(count, 1.0 / count, dtype=float)
    primary_boot = np.empty(replicates, dtype=float)
    residual_boot = np.empty(replicates, dtype=float)
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        weights = rng.multinomial(count, probabilities, size=stop - start)
        replicate_levels: dict[str, np.ndarray] = {}
        for level, features in levels.items():
            curves = _covariance_curves_from_weighted_features(weights, features)
            replicate_levels[level] = _curve_values(
                times,
                curves,
                kind=kind,
                fraction=primary_fraction,
            )
        primary_values = (
            2.0 * replicate_levels["finest"] - replicate_levels["middle"]
        )
        secondary_values = (
            2.0 * replicate_levels["middle"] - replicate_levels["coarse"]
        )
        primary_boot[start:stop] = primary_values
        residual_boot[start:stop] = (primary_values - secondary_values) / 3.0
    stability_rule = uncertainty["bootstrap_se_stability"]
    stability_kwargs = {
        "block_count": int(stability_rule["block_count"]),
        "maximum_relative_deviation": float(
            stability_rule["maximum_relative_deviation"]
        ),
    }
    primary_stability = _bootstrap_se_stability(
        primary_boot, **stability_kwargs
    )
    residual_stability = _bootstrap_se_stability(
        residual_boot, **stability_kwargs
    )
    standard_error = float(primary_stability["full_standard_error"])
    residual_se = float(residual_stability["full_standard_error"])
    quantile, relative, floor = _tier_values(plan, tier)
    residual = (point_primary - point_secondary) / 3.0
    b_disc = abs(residual) + quantile * residual_se
    margin = floor * characteristic_scale + relative * abs(reference)
    discrepancy = point_primary - reference
    lower = discrepancy - quantile * standard_error
    upper = discrepancy + quantile * standard_error
    scientific = classify_expanded_interval(
        lower=lower,
        upper=upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    residual_lower = residual - quantile * residual_se
    residual_upper = residual + quantile * residual_se
    residual_outcome = classify_expanded_interval(
        lower=residual_lower,
        upper=residual_upper,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = point_primary - quantile * standard_error
    estimand_upper = point_primary + quantile * standard_error
    sign = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    adequacy = _adequacy_diagnostic(
        quantile=quantile,
        standard_error=standard_error,
        b_window=b_window,
        b_disc=b_disc,
        margin=margin,
        plan=plan,
    )
    stability = _combine_required_outcomes(
        primary_stability["classification"],
        residual_stability["classification"],
    )
    return {
        "comparison_id": comparison_id,
        "observable": kind,
        "tier": tier,
        "reference": reference,
        "estimate": point_primary,
        "standard_error": standard_error,
        "discrepancy_interval": [lower, upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "bootstrap_replicates": replicates,
        "bootstrap_se_stability": primary_stability,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign,
        "richardson_residual": {
            "formula": "(R_h-R_2h)/3",
            "estimate": residual,
            "standard_error": residual_se,
            "interval": [residual_lower, residual_upper],
            "bootstrap_se_stability": residual_stability,
            "classification": residual_outcome,
        },
        "variance_reduction_adequacy": adequacy,
        "scientific_discrepancy_classification": scientific,
        "classification": _combine_required_outcomes(
            scientific,
            residual_outcome,
            sign,
            adequacy["classification"],
            stability,
        ),
    }


def _bootstrap_position_pair(
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
    analysis_code: int,
    paired_protocols: bool,
    required_claim: str,
) -> dict[str, Any]:
    if not np.array_equal(left_data["times"], right_data["times"]):
        raise ValueError("protocol position-feature record times differ")
    times = left_data["times"]
    left = _position_levels(left_data)
    right = _position_levels(right_data)
    left_count = left["finest"].shape[1]
    right_count = right["finest"].shape[1]
    if paired_protocols and left_count != right_count:
        raise ValueError("paired position comparison requires equal counts")
    primary_fraction = WINDOW_FRACTIONS[PRIMARY_WINDOW_INDEX]

    def level_difference(level: str, fraction: float) -> float:
        return _position_point(
            times, left[level], kind=kind, fraction=fraction
        ) - _position_point(times, right[level], kind=kind, fraction=fraction)

    points = {
        level: level_difference(level, primary_fraction)
        for level in LEVEL_NAMES
    }
    point_primary = 2.0 * points["finest"] - points["middle"]
    point_secondary = 2.0 * points["middle"] - points["coarse"]
    window_values = []
    for fraction in WINDOW_FRACTIONS:
        finest = level_difference("finest", fraction)
        middle = level_difference("middle", fraction)
        window_values.append(2.0 * finest - middle)
    b_window = max(
        abs(value - window_values[PRIMARY_WINDOW_INDEX])
        for value in window_values
    )
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    replicates = int(uncertainty["bootstrap_replicates"])
    batch_size = int(uncertainty["bootstrap_batch_size"])
    rng = _bootstrap_rng(plan, analysis_code)
    left_probabilities = np.full(left_count, 1.0 / left_count, dtype=float)
    right_probabilities = np.full(right_count, 1.0 / right_count, dtype=float)
    primary_boot = np.empty(replicates, dtype=float)
    residual_boot = np.empty(replicates, dtype=float)
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        size = stop - start
        left_weights = rng.multinomial(
            left_count, left_probabilities, size=size
        )
        right_weights = (
            left_weights
            if paired_protocols
            else rng.multinomial(right_count, right_probabilities, size=size)
        )
        differences: dict[str, np.ndarray] = {}
        for level in LEVEL_NAMES:
            left_values = _curve_values(
                times,
                _covariance_curves_from_weighted_features(
                    left_weights, left[level]
                ),
                kind=kind,
                fraction=primary_fraction,
            )
            right_values = _curve_values(
                times,
                _covariance_curves_from_weighted_features(
                    right_weights, right[level]
                ),
                kind=kind,
                fraction=primary_fraction,
            )
            differences[level] = left_values - right_values
        primary_values = 2.0 * differences["finest"] - differences["middle"]
        secondary_values = 2.0 * differences["middle"] - differences["coarse"]
        primary_boot[start:stop] = primary_values
        residual_boot[start:stop] = (primary_values - secondary_values) / 3.0
    stability_rule = uncertainty["bootstrap_se_stability"]
    stability_kwargs = {
        "block_count": int(stability_rule["block_count"]),
        "maximum_relative_deviation": float(
            stability_rule["maximum_relative_deviation"]
        ),
    }
    primary_stability = _bootstrap_se_stability(primary_boot, **stability_kwargs)
    residual_stability = _bootstrap_se_stability(residual_boot, **stability_kwargs)
    standard_error = float(primary_stability["full_standard_error"])
    residual_se = float(residual_stability["full_standard_error"])
    quantile, relative, floor = _tier_values(plan, tier)
    residual = (point_primary - point_secondary) / 3.0
    b_disc = abs(residual) + quantile * residual_se
    margin = floor * characteristic_scale + relative * abs(reference_difference)
    discrepancy = point_primary - reference_difference
    lower = discrepancy - quantile * standard_error
    upper = discrepancy + quantile * standard_error
    scientific = classify_expanded_interval(
        lower=lower,
        upper=upper,
        margin=margin,
        b_window=b_window,
        b_disc=b_disc,
    )
    residual_lower = residual - quantile * residual_se
    residual_upper = residual + quantile * residual_se
    residual_outcome = classify_expanded_interval(
        lower=residual_lower,
        upper=residual_upper,
        margin=margin,
        b_window=0.0,
        b_disc=0.0,
    )
    estimand_lower = point_primary - quantile * standard_error
    estimand_upper = point_primary + quantile * standard_error
    sign = _signed_interval_outcome(
        lower=estimand_lower,
        upper=estimand_upper,
        b_window=b_window,
        b_disc=b_disc,
        required_claim=required_claim,
    )
    adequacy = _adequacy_diagnostic(
        quantile=quantile,
        standard_error=standard_error,
        b_window=b_window,
        b_disc=b_disc,
        margin=margin,
        plan=plan,
    )
    stability = _combine_required_outcomes(
        primary_stability["classification"],
        residual_stability["classification"],
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
        "reference": reference_difference,
        "reference_difference": reference_difference,
        "estimate": point_primary,
        "standard_error": standard_error,
        "discrepancy_interval": [lower, upper],
        "estimand_interval": [estimand_lower, estimand_upper],
        "characteristic_scale": characteristic_scale,
        "margin": margin,
        "B_window": b_window,
        "B_disc": b_disc,
        "bootstrap_replicates": replicates,
        "bootstrap_se_stability": primary_stability,
        "required_sign_or_equality": required_claim,
        "sign_classification": sign,
        "richardson_residual": {
            "formula": "(R_h-R_2h)/3",
            "estimate": residual,
            "standard_error": residual_se,
            "interval": [residual_lower, residual_upper],
            "bootstrap_se_stability": residual_stability,
            "classification": residual_outcome,
        },
        "variance_reduction_adequacy": adequacy,
        "scientific_discrepancy_classification": scientific,
        "classification": _combine_required_outcomes(
            scientific,
            residual_outcome,
            sign,
            adequacy["classification"],
            stability,
        ),
    }


def _load_reference_adapter() -> Any:
    path = ROOT / ADAPTER_REL
    spec = importlib.util.spec_from_file_location(
        "s072_post_path_reference_adapter", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load reference adapter: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _matrix_entry(value: Any, row: int, column: int = 0) -> float:
    if not isinstance(value, list):
        raise TypeError("reference matrix is not a list")
    return float(value[row][column])


def _analyze_protocol(
    data: Mapping[str, np.ndarray],
    protocol: str,
    references: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    analysis_code: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    speed_reference = float(references["speed"])
    speed_scale = abs(_matrix_entry(references["S"], 0, 0)) + abs(
        _matrix_entry(references["S"], 1, 1)
    )
    rows.append(
        _ordinary_direct(
            data,
            comparison_id=f"MAIN_{protocol}_speed_direct",
            name="speed",
            reference=speed_reference,
            characteristic_scale=speed_scale,
            tier=(
                "central_disputed"
                if protocol in ("PV", "PVTheta")
                else "primary"
            ),
            plan=plan,
            required_claim="positive",
        )
    )
    if protocol in POSITION_PROTOCOLS:
        centered_reference = float(references["centered_variance"])
        rows.append(
            _bootstrap_position_direct(
                data,
                comparison_id=f"H1_{protocol}_centered_variance_direct",
                kind="centered_variance",
                reference=centered_reference,
                characteristic_scale=abs(centered_reference),
                tier="primary",
                plan=plan,
                analysis_code=analysis_code,
                required_claim="positive",
            )
        )
    else:
        vx_reference = _matrix_entry(references["v_bar"], 0, 0)
        vx_scale = math.sqrt(abs(_matrix_entry(references["S"], 0, 0)))
        rows.append(
            _ordinary_direct(
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
            _bootstrap_position_direct(
                data,
                comparison_id=f"H1_{protocol}_D_eff_direct",
                kind="D_eff",
                reference=d_reference,
                characteristic_scale=d_scale,
                tier="primary",
                plan=plan,
                analysis_code=analysis_code,
                required_claim="positive",
            )
        )
    if protocol in ("PV", "PVTheta"):
        raw_reference = float(references["raw_MSD"])
        rows.append(
            _ordinary_direct(
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
        rows.append(
            _ordinary_direct(
                data,
                comparison_id=f"H4_{protocol}_r_dot_v_direct",
                name="r_dot_v",
                reference=rdot_reference,
                characteristic_scale=math.sqrt(
                    abs(raw_reference * speed_reference)
                ),
                tier="central_disputed",
                plan=plan,
                required_claim="positive",
            )
        )
    for row in rows:
        row["protocol"] = protocol
        row["role"] = "main_direct_reference"
    return rows


def _require_matching_reset_clocks(
    metadata: Mapping[str, Any], left: str, right: str
) -> str:
    left_hash = metadata[left]["hashes"]["reset_clock_chunks"]
    right_hash = metadata[right]["hashes"]["reset_clock_chunks"]
    if (
        not isinstance(left_hash, str)
        or len(left_hash) != 64
        or left_hash != right_hash
    ):
        raise RuntimeError(
            f"paired comparison reset clocks differ: {left} vs {right}"
        )
    return left_hash


def _paired_headline_rows(
    data: Mapping[str, Mapping[str, np.ndarray]],
    metadata: Mapping[str, Any],
    references: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
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
            _ordinary_protocol_pair(
                data[left],
                data[right],
                comparison_id=f"H2_{left}_minus_{right}_v_x",
                left_protocol=left,
                right_protocol=right,
                name="v_x",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="positive",
                paired_protocols=True,
            )
        )
    _require_matching_reset_clocks(metadata, "PV", "PVTheta")
    pv = references["PV"]
    full = references["PVTheta"]
    scales = {
        "speed": abs(_matrix_entry(pv["S"], 0, 0))
        + abs(_matrix_entry(pv["S"], 1, 1)),
        "raw_msd": abs(float(pv["raw_MSD"])),
        "r_dot_v": math.sqrt(abs(float(pv["raw_MSD"]) * float(pv["speed"]))),
    }
    reference_fields = {
        "speed": "speed",
        "raw_msd": "raw_MSD",
        "r_dot_v": "r_dot_v",
    }
    for name in ("speed", "raw_msd", "r_dot_v"):
        field = reference_fields[name]
        rows.append(
            _ordinary_protocol_pair(
                data["PV"],
                data["PVTheta"],
                comparison_id=f"H4_PV_minus_PVTheta_{name}",
                left_protocol="PV",
                right_protocol="PVTheta",
                name=name,
                reference_difference=float(pv[field]) - float(full[field]),
                characteristic_scale=scales[name],
                tier="central_disputed",
                plan=plan,
                required_claim="equality_zero",
                paired_protocols=True,
            )
        )
    centered_difference = float(pv["centered_variance"]) - float(
        full["centered_variance"]
    )
    rows.append(
        _bootstrap_position_pair(
            data["PV"],
            data["PVTheta"],
            comparison_id="H4_PV_minus_PVTheta_centered_variance",
            left_protocol="PV",
            right_protocol="PVTheta",
            kind="centered_variance",
            reference_difference=centered_difference,
            characteristic_scale=abs(centered_difference),
            tier="primary",
            plan=plan,
            analysis_code=2000,
            paired_protocols=True,
            required_claim="positive",
        )
    )
    for row in rows:
        row["role"] = "main_common_random_number_same_estimand_contrast"
    return rows


def _unpaired_headline_rows(
    data: Mapping[str, Mapping[str, np.ndarray]],
    references: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left, right in (("Theta", "V"), ("VTheta", "V")):
        left_reference = _matrix_entry(references[left]["v_bar"], 0, 0)
        right_reference = _matrix_entry(references[right]["v_bar"], 0, 0)
        scale = max(
            math.sqrt(abs(_matrix_entry(references[left]["S"], 0, 0))),
            math.sqrt(abs(_matrix_entry(references[right]["S"], 0, 0))),
        )
        rows.append(
            _ordinary_protocol_pair(
                data[left],
                data[right],
                comparison_id=f"H2_{left}_minus_{right}_v_x_unpaired",
                left_protocol=left,
                right_protocol=right,
                name="v_x",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="positive",
                paired_protocols=False,
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
            _ordinary_protocol_pair(
                data[left],
                data[right],
                comparison_id=f"H3_{left}_minus_{right}_speed_unpaired",
                left_protocol=left,
                right_protocol=right,
                name="speed",
                reference_difference=left_reference - right_reference,
                characteristic_scale=scale,
                tier="primary",
                plan=plan,
                required_claim="equality_zero",
                paired_protocols=False,
            )
        )
    pv = references["PV"]
    full = references["PVTheta"]
    scales = {
        "speed": abs(_matrix_entry(pv["S"], 0, 0))
        + abs(_matrix_entry(pv["S"], 1, 1)),
        "raw_msd": abs(float(pv["raw_MSD"])),
        "r_dot_v": math.sqrt(abs(float(pv["raw_MSD"]) * float(pv["speed"]))),
    }
    reference_fields = {
        "speed": "speed",
        "raw_msd": "raw_MSD",
        "r_dot_v": "r_dot_v",
    }
    for name in ("speed", "raw_msd", "r_dot_v"):
        field = reference_fields[name]
        rows.append(
            _ordinary_protocol_pair(
                data["PV"],
                data["PVTheta"],
                comparison_id=f"H4_PV_minus_PVTheta_{name}_unpaired",
                left_protocol="PV",
                right_protocol="PVTheta",
                name=name,
                reference_difference=float(pv[field]) - float(full[field]),
                characteristic_scale=scales[name],
                tier="central_disputed",
                plan=plan,
                required_claim="equality_zero",
                paired_protocols=False,
            )
        )
    centered_difference = float(pv["centered_variance"]) - float(
        full["centered_variance"]
    )
    rows.append(
        _bootstrap_position_pair(
            data["PV"],
            data["PVTheta"],
            comparison_id="H4_PV_minus_PVTheta_centered_variance_unpaired",
            left_protocol="PV",
            right_protocol="PVTheta",
            kind="centered_variance",
            reference_difference=centered_difference,
            characteristic_scale=abs(centered_difference),
            tier="primary",
            plan=plan,
            analysis_code=3000,
            paired_protocols=False,
            required_claim="positive",
        )
    )
    for row in rows:
        row["role"] = "smaller_unpaired_same_estimand_confirmation"
    return rows


def _reference_scope_checks(
    references: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for left, right in (
        ("PV", "V"),
        ("PTheta", "Theta"),
        ("PVTheta", "VTheta"),
    ):
        left_reference = float(references[left]["speed"])
        right_reference = float(references[right]["speed"])
        checks.append(
            {
                "comparison_id": f"H3_{left}_{right}_speed_reference_common_nonzero",
                "protocols": [left, right],
                "observable": "speed",
                "left_reference": left_reference,
                "right_reference": right_reference,
                "reference_difference": left_reference - right_reference,
                "required": "exact common and nonzero accepted reference",
                "classification": (
                    "validated"
                    if left_reference == right_reference and left_reference != 0.0
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
    context = _contract_registry_context(plan)
    specs = estimand_specs(plan, observable_classes=context["observable_classes"])
    rows = [row for group in groups for row in group]
    identifiers = [row.get("comparison_id") for row in rows]
    if not all(isinstance(value, str) for value in identifiers):
        raise RuntimeError("every result row requires a comparison ID")
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(specs):
        raise RuntimeError("result rows differ from the retained estimand table")
    sampling = plan["sampling"]
    uncertainty = plan["uncertainty_and_systematic_envelopes"]
    for row in rows:
        spec = specs[row["comparison_id"]]
        cap_role = spec["compute_cap_role"]
        if cap_role == "main":
            cap = int(sampling["main_compute_cap_per_protocol"])
        elif cap_role == "unpaired":
            cap = int(sampling["unpaired_compute_cap_per_required_protocol"])
        else:
            cap = 0
        tier = spec["tier"]
        if row.get("tier", tier) != tier:
            raise RuntimeError(f"tier drift: {row['comparison_id']}")
        if "required_sign_or_equality" in row and row["required_sign_or_equality"] != spec["required_sign_or_equality"]:
            raise RuntimeError(f"sign/equality drift: {row['comparison_id']}")
        row.update(
            {
                "headline": spec["headline"],
                "registered_observable": spec["observable"],
                "observable_class": spec["observable_class"],
                "parent_scale_inputs": spec["parent_scale_inputs"],
                "evidence_tier": tier,
                "estimator": spec["estimator"],
                "interval_construction": spec["interval_construction"],
                "coverage": (
                    None if tier == "deterministic" else float(uncertainty[tier]["coverage"])
                ),
                "quantile": (
                    None if tier == "deterministic" else float(uncertainty[tier]["quantile"])
                ),
                "pairing_role": spec["pairing_role"],
                "required_sign_or_equality": spec["required_sign_or_equality"],
                "registry_schema_version": context["schema_version"],
                "registry_sha256": context["registry_semantic_sha256"],
                "compute_cap": cap,
                "compute_cap_role": cap_role,
            }
        )


def _aggregate(classifications: Sequence[str]) -> str:
    if any(value == "contradicted" for value in classifications):
        return "contradicted"
    if any(value != "validated" for value in classifications):
        return "unresolved"
    return "validated"


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


def _authenticate_reviewed_source_lineage(
    reviewed_source_commit: str,
    execution_commit: str,
    paths: Sequence[Path] = MANIFEST_PATHS,
) -> None:
    """Require reviewed source to be unchanged along the execution lineage."""

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", reviewed_source_commit, execution_commit],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise PermissionError("reviewed source commit is not an execution ancestor")
    unchanged = subprocess.run(
        ["git", "diff", "--quiet", reviewed_source_commit, execution_commit, "--"]
        + [path.as_posix() for path in paths],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if unchanged.returncode != 0:
        raise PermissionError("authenticated source paths changed after V-072 review")


def authenticate_v072(
    audit_path: Path | None = None,
    *,
    reviewed_manifest_sha256: str | None = None,
    reviewed_source_commit: str | None = None,
) -> dict[str, str]:
    audit = ROOT / AUDIT_REL if audit_path is None else audit_path
    if not audit.is_file():
        raise PermissionError("V-072 audit is absent; production is prohibited")
    try:
        text = _canonical_text_bytes(audit).decode("utf-8")
    except ValueError as exc:
        raise PermissionError("V-072 audit is not canonical readable text") from exc
    lines = text.splitlines()
    dispositions = [line for line in lines if line.startswith("**Disposition:**")]
    if dispositions != ["**Disposition:** PASS"]:
        raise PermissionError("V-072 requires exactly one PASS disposition")
    headers = [index for index, line in enumerate(lines) if line == AUDIT_HEADER]
    if len(headers) != 1:
        raise PermissionError("V-072 requires exactly one acceptance header")
    if text.count(AUDIT_MARKER_PREFIX) != 1:
        raise PermissionError("V-072 requires one marker occurrence")
    markers = [
        index
        for index, line in enumerate(lines)
        if line.startswith(AUDIT_MARKER_PREFIX)
    ]
    if len(markers) != 1 or markers[0] != headers[0] + 1:
        raise PermissionError("V-072 marker must immediately follow its header")
    marker_line = lines[markers[0]]
    if marker_line.lstrip() != marker_line or marker_line.startswith((">", "-", "*", "`")):
        raise PermissionError("V-072 marker must be standalone and unquoted")
    encoded = marker_line[len(AUDIT_MARKER_PREFIX) :]
    try:
        record = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise PermissionError("V-072 marker is malformed") from exc
    expected = acceptance_record(
        source_manifest_digest()
        if reviewed_manifest_sha256 is None
        else reviewed_manifest_sha256,
        manifest_source_commit()
        if reviewed_source_commit is None
        else reviewed_source_commit,
    )
    if not isinstance(record, dict) or record != expected:
        raise PermissionError(
            "V-072 did not bind the exact plan/source manifest and commit"
        )
    if encoded != _semantic_bytes(expected).decode("utf-8"):
        raise PermissionError("V-072 marker JSON is not canonical")
    return expected


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
    return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES"))


def resource_preflight(
    plan: Mapping[str, Any],
    *,
    free_disk_bytes: int | None = None,
    available_memory_bytes: int | None = None,
    output_path: Path | None = None,
    attempt_path: Path | None = None,
) -> dict[str, int | str]:
    resources = plan["resource_estimate"]
    output = ROOT / OUTPUT_REL if output_path is None else output_path
    attempt = ROOT / ATTEMPT_REL if attempt_path is None else attempt_path
    if output.exists():
        raise FileExistsError(f"canonical output already exists: {output}")
    if attempt.exists():
        raise FileExistsError(f"write-once sentinel already exists: {attempt}")
    free = int(shutil.disk_usage(ROOT).free) if free_disk_bytes is None else int(free_disk_bytes)
    available = _available_memory_bytes() if available_memory_bytes is None else int(available_memory_bytes)
    minimum_disk = int(resources["minimum_free_disk_bytes"])
    minimum_memory = int(resources["minimum_available_memory_bytes"])
    if free < minimum_disk:
        raise RuntimeError(f"free disk {free} is below fixed floor {minimum_disk}")
    if available < minimum_memory:
        raise RuntimeError(
            f"available memory {available} is below fixed floor {minimum_memory}"
        )
    return {
        "status": "validated_before_stochastic_execution",
        "free_disk_bytes": free,
        "available_memory_bytes": available,
        "minimum_free_disk_bytes": minimum_disk,
        "minimum_available_memory_bytes": minimum_memory,
        "maximum_three_level_conditional_segments": int(
            resources["maximum_three_level_conditional_segments"]
        ),
        "maximum_rotational_normal_draws": int(
            resources["maximum_rotational_normal_draws"]
        ),
        "translational_normal_draws": 0,
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


def _create_attempt_sentinel(path: Path, payload: Mapping[str, Any]) -> str:
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
    _create_attempt_sentinel(path, payload)
    return callback()


def _atomic_publish_once(path: Path, payload: Mapping[str, Any]) -> str:
    if path.exists():
        raise FileExistsError(f"canonical output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(_pretty_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_file(path)


def _sector_identity_checks(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for left, right in (
        ("PV", "V"),
        ("PTheta", "Theta"),
        ("PVTheta", "VTheta"),
    ):
        clock_hash = _require_matching_reset_clocks(metadata, left, right)
        fields = (
            "velocity_means",
            "orientations",
            "velocity_variance_per_axis",
        )
        matched = all(
            metadata[left]["hashes"][f"{level}_{field}"]
            == metadata[right]["hashes"][f"{level}_{field}"]
            for level in LEVEL_NAMES
            for field in fields
        )
        checks.append(
            {
                "comparison_id": f"H3_{left}_{right}_pathwise_internal",
                "pair": [left, right],
                "observable": "complete recorded conditional velocity/orientation sector at all three levels",
                "reset_clock_sha256": clock_hash,
                "pathwise_internal_hashes_equal": matched,
                "classification": "validated" if matched else "contradicted",
            }
        )
    return checks


def execute(plan_path: Path) -> tuple[dict[str, Any], str]:
    if plan_path.resolve() != (ROOT / PLAN_REL).resolve():
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    plan = load_preregistered_plan(ROOT / PLAN_REL)
    validate_preregistered_plan(plan)
    audit_isolation()
    manifest = source_manifest()
    manifest_digest = source_manifest_digest(manifest)
    reviewed_source_commit = manifest_source_commit()
    review_record = authenticate_v072(
        reviewed_manifest_sha256=manifest_digest,
        reviewed_source_commit=reviewed_source_commit,
    )
    execution_commit = _clean_source_commit()
    _authenticate_reviewed_source_lineage(
        review_record["reviewed_source_commit"], execution_commit
    )
    preflight = resource_preflight(plan)
    dependency_versions = runtime_dependency_versions()
    sampling = plan["sampling"]
    seeds = plan["seed_policy"]
    case = plan["parameter_cases"][0]
    metadata: dict[str, dict[str, Any]] = {"main": {}, "unpaired": {}}

    with tempfile.TemporaryDirectory(prefix="phasemap-s072-") as temporary:
        temporary_root = Path(temporary)
        paths: dict[tuple[str, str], Path] = {}
        attempt_payload = {
            "schema_version": "1.0.0",
            "task_id": "S-073",
            "plan_id": PLAN_ID,
            "plan_version": PLAN_VERSION,
            "plan_canonical_lf_sha256": EXPECTED_PLAN_CANONICAL_LF_SHA256,
            "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
            "reviewed_source_manifest_sha256": manifest_digest,
            "reviewed_source_commit": reviewed_source_commit,
            "execution_commit": execution_commit,
            "runtime_dependency_versions": dependency_versions,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "resource_preflight": preflight,
            "fixed_compute_caps": plan["resource_estimate"],
            "status": "production_attempt_started_before_first_stochastic_draw",
            "retry_authorized": False,
            "s071_samples_used": False,
        }

        def stochastic_work() -> None:
            for protocol in ALL_PROTOCOLS:
                destination = temporary_root / f"main-{protocol.value}.npz"
                metadata["main"][protocol.value] = _simulate_stream(
                    plan,
                    protocol,
                    count=int(sampling["main_conditional_units_per_protocol"]),
                    base_seed=int(seeds["main_base_seed"]),
                    stream_base=int(seeds["main_protocol_stream_code"]),
                    destination=destination,
                    store_position_features=True,
                )
                paths[("main", protocol.value)] = destination
            for protocol_name in UNPAIRED_PROTOCOLS:
                protocol = Protocol(protocol_name)
                destination = temporary_root / f"unpaired-{protocol.value}.npz"
                metadata["unpaired"][protocol.value] = _simulate_stream(
                    plan,
                    protocol,
                    count=int(
                        sampling["unpaired_conditional_units_per_required_protocol"]
                    ),
                    base_seed=int(seeds["unpaired_base_seeds"][protocol.value]),
                    stream_base=int(seeds["unpaired_protocol_stream_code"]),
                    destination=destination,
                    store_position_features=protocol.value in ("PV", "PVTheta"),
                )
                paths[("unpaired", protocol.value)] = destination

        # This exclusive, fsynced write is the final operation before the first
        # scientific RNG construction.  A crash therefore cannot authorize retry.
        _run_after_attempt_sentinel(
            ROOT / ATTEMPT_REL, attempt_payload, stochastic_work
        )

        sector_checks = _sector_identity_checks(metadata["main"])
        # All conditional path summaries and hashes are frozen before this load.
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
        main_data = {
            protocol.value: _load_stream_data(paths[("main", protocol.value)])
            for protocol in ALL_PROTOCOLS
        }
        unpaired_data = {
            protocol: _load_stream_data(paths[("unpaired", protocol)])
            for protocol in UNPAIRED_PROTOCOLS
        }
        comparisons: list[dict[str, Any]] = []
        for index, protocol in enumerate(ALL_PROTOCOLS):
            comparisons.extend(
                _analyze_protocol(
                    main_data[protocol.value],
                    protocol.value,
                    references[protocol.value],
                    plan,
                    analysis_code=1000 + index,
                )
            )
        paired_rows = _paired_headline_rows(
            main_data, metadata["main"], references, plan
        )
        unpaired_rows = _unpaired_headline_rows(
            unpaired_data, references, plan
        )
        reference_checks = _reference_scope_checks(references)
        _decorate_and_validate_result_rows(
            (
                comparisons,
                paired_rows,
                unpaired_rows,
                sector_checks,
                reference_checks,
            ),
            plan,
        )
        all_rows = (
            comparisons
            + paired_rows
            + unpaired_rows
            + sector_checks
            + reference_checks
        )
        overall = _aggregate([row["classification"] for row in all_rows])
        payload: dict[str, Any] = {
            "schema_version": "1.0.0",
            "task_id": "S-073",
            "plan_id": PLAN_ID,
            "status": "completed_fixed_plan",
            "method_label": "conditional-moment hybrid Monte Carlo",
            "contract_version": plan["contract_version"],
            "source_commit": reviewed_source_commit,
            "execution_commit": execution_commit,
            "source_manifest": manifest,
            "source_manifest_sha256": manifest_digest,
            "plan_canonical_lf_sha256": EXPECTED_PLAN_CANONICAL_LF_SHA256,
            "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
            "resource_preflight": preflight,
            "attempt_sentinel": ATTEMPT_REL.as_posix(),
            "prior_attempt_boundary": {
                "task_id": "S-071",
                "samples_used": False,
                "runtime_artifacts_opened": False,
                "pooling": False,
            },
            "configuration": {
                "case": case,
                "schedule": plan["numerical_schedule"],
                "sampling": sampling,
                "seed_policy": seeds,
            },
            "stream_metadata": metadata,
            "sector_identity_checks": sector_checks,
            "reference_scope_checks": reference_checks,
            "comparisons": comparisons,
            "paired_headline_comparisons": paired_rows,
            "unpaired_confirmations": unpaired_rows,
            "overall_classification": overall,
            "provenance": {
                "python_version": sys.version,
                "numpy_version": np.__version__,
                "sympy_version": dependency_versions["sympy"],
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
            current_commit != execution_commit
            or manifest_source_commit() != reviewed_source_commit
            or source_manifest() != manifest
            or source_manifest_digest() != manifest_digest
            or runtime_dependency_versions() != dependency_versions
        ):
            raise RuntimeError("source changed during the fixed calculation")
        digest = _atomic_publish_once(ROOT / OUTPUT_REL, payload)
        if overall != "validated":
            raise RuntimeError(
                f"S-072 replacement ended {overall}; raw sha256={digest}; "
                "retry, polling, top-up, and alternate output are prohibited"
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
