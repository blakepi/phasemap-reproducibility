"""Fail-closed executor for the committed S-011 v2 finite-time spot checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phasemap.simulation.free_baseline import (  # noqa: E402
    covariance_trace_jackknife,
    simulate_free_paired,
)
from phasemap.theory.free_baseline import free_scalar_moments  # noqa: E402
from scripts.validate_validation_registry import (  # noqa: E402
    admissible_margin,
    characteristic_scale,
    classify_interval,
    load_registry,
    load_schema,
    validate_run_configuration,
)


PLAN_ID = "S-011-free-baseline-primary-v2"
PLAN_REL = "experiments/S-011-free-baseline-primary-v2.json"
PILOT_REL = "artifacts/raw/S-011-free-baseline-primary-v2-pilot.json"
CONFIRM_REL = "artifacts/raw/S-011-free-baseline-primary-v2-confirm.json"
OUTPUTS = {"pilot": PILOT_REL, "confirm": CONFIRM_REL}
LOCKED_FORMULA = (
    "ceil(N0 * (q * SE0 / "
    "(epsilon - abs(delta0) - B_window0 - B_disc0))^2)"
)
PAIRING = "coarse Wiener increments are sums of paired fine increments"
TIMES = [1.5, 3.0]
SEEDS = ([20260722101, 20260722102], [20260722201, 20260722202])
OBS = {
    "r_dot_v": "mean_position_dot_velocity",
    "cov_r_trace": "centered_spatial_variance",
}
PRIMARY_QUANTILE = 2.5758293035
B_DISC_FLOOR = 0.01
B_DISC_ESTIMATOR = (
    "max(B_disc_floor, abs(matching_fine_coarse_delta) + "
    "q * matching_fine_coarse_standard_error)"
)
UNCERTAINTY = {
    "interval": {
        "distribution": "normal",
        "quantity": "discrepancy",
        "quantile": PRIMARY_QUANTILE,
    },
    "methods": {
        "r_dot_v": {
            "direct_reference": {
                "estimator": "trajectory_mean",
                "standard_error": "trajectory_mean_standard_error",
            },
            "fine_coarse": {
                "estimator": "matched_pair_difference_mean",
                "standard_error": "matched_pair_difference_mean_standard_error",
            },
        },
        "cov_r_trace": {
            "direct_reference": {
                "estimator": "unbiased_sample_covariance_trace",
                "standard_error": "delete_one_trajectory_jackknife_standard_error",
            },
            "fine_coarse": {
                "estimator": "unbiased_matched_pair_covariance_trace_difference",
                "standard_error": "delete_one_matched_pair_jackknife_standard_error",
            },
        },
    },
    "systematic_envelopes": {
        "B_window": 0.0,
        "B_disc_floor": B_DISC_FLOOR,
        "B_disc_estimator": B_DISC_ESTIMATOR,
        "phase_policy": {
            "pilot_use": "estimate from pilot matched pairs for projection only",
            "confirmatory_use": (
                "estimate freshly from confirmatory matched pairs for final interval "
                "and classification"
            ),
            "pilot_values_enter_confirmatory_interval_or_classification": False,
        },
    },
}
EXPECTED_CONFIGURATIONS = tuple(
    (time, observable, comparison)
    for time in TIMES
    for observable in OBS
    for comparison in ("direct_reference", "fine_coarse")
)
ANALYSIS_FIELDS = {
    "id",
    "time",
    "observable_class",
    "comparison_kind",
    "evidence_tier",
    "reference",
    "delta",
    "standard_error",
    "interval",
    "epsilon",
    "B_window",
    "B_disc",
    "classification",
    "estimator",
    "standard_error_method",
}
PILOT_FIELDS = {
    "mode",
    "output",
    "evidence_role",
    "overall",
    "count",
    "seeds",
    "analysis",
    "per_config_n_target",
    "n_target",
    "eligible_for_confirmation",
    "plan_id",
    "plan_hash",
    "contract_version",
    "registry_version",
    "source_commit",
    "source_manifest",
    "parameters",
    "resolution",
    "pairing_policy",
    "compute_cap",
    "interval_construction",
}
MANIFEST = [
    "docs/scientific-contract/CONTRACT.md",
    "docs/scientific-contract/validation_registry.json",
    "docs/scientific-contract/validation_registry.schema.json",
    "scripts/validate_validation_registry.py",
    "experiments/run_s011_free_baseline.py",
    "src/phasemap/__init__.py",
    "src/phasemap/simulation/__init__.py",
    "src/phasemap/simulation/free_baseline.py",
    "src/phasemap/theory/__init__.py",
    "src/phasemap/theory/free_baseline.py",
    PLAN_REL,
]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without conflating booleans and numbers."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(
                _json_equal(left_item, right_item)
                for left_item, right_item in zip(left, right, strict=True)
            )
        )
    if _number(left) or _number(right):
        return _number(left) and _number(right) and left == right
    return type(left) is type(right) and left == right


def _fail(detail: str) -> None:
    raise ValueError(f"invalid S-011 v2 plan: {detail}")


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_load(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def load_preregistered_plan(path: Path) -> dict[str, Any]:
    return _json_load(_root(path))


def source_manifest() -> dict[str, str]:
    return {path: _hash(ROOT / path) for path in MANIFEST}


def _reference_inputs(time: float, observable: str) -> dict[str, float]:
    moments = free_scalar_moments(sp.Float(time), sp.Float(0.8), sp.Float(1.2))
    if observable == "r_dot_v":
        return {
            "r_squared_reference": float(moments.mean_squared_displacement),
            "v_squared_reference": float(moments.mean_squared_speed),
        }
    return {"reference": float(moments.centered_spatial_variance)}


def _reference(time: float, observable: str) -> float:
    moments = free_scalar_moments(sp.Float(time), sp.Float(0.8), sp.Float(1.2))
    if observable == "r_dot_v":
        return float(moments.mean_position_dot_velocity)
    return float(moments.centered_spatial_variance)


def _configuration_id(time: float, observable: str, comparison: str) -> str:
    short = {"r_dot_v": "rdotv", "cov_r_trace": "covtrace"}[observable]
    suffix = "direct" if comparison == "direct_reference" else "fine-coarse"
    return f"t{time:g}-{short}-{suffix}"


def validate_preregistered_plan(plan: dict[str, Any]) -> None:
    if not isinstance(plan, dict):
        _fail("top-level object")
    top = {
        "contract_version",
        "plan_id",
        "status",
        "scope",
        "rho_limit_claimed",
        "outputs",
        "parameters",
        "validation_times",
        "fine_step",
        "coarse_step",
        "pairing_policy",
        "sampling",
        "uncertainty",
        "run_configurations",
    }
    if set(plan) != top:
        _fail("top-level fields")
    if (
        not isinstance(plan["outputs"], dict)
        or not isinstance(plan["parameters"], dict)
        or not isinstance(plan["validation_times"], list)
        or not isinstance(plan["sampling"], dict)
        or not isinstance(plan["uncertainty"], dict)
        or not isinstance(plan["run_configurations"], list)
    ):
        _fail("top-level value types")
    identity = (
        plan["contract_version"],
        plan["plan_id"],
        plan["status"],
        plan["scope"],
        plan["rho_limit_claimed"],
    )
    if not _json_equal(
        list(identity),
        [
            "0.3",
            PLAN_ID,
            "preregistered-not-executed",
            "selected primary finite-time rho=0 spot checks only; "
            "not full free-baseline or G2 closure",
            False,
        ],
    ) or not isinstance(plan["rho_limit_claimed"], bool):
        _fail("identity/scope")
    if not _json_equal(plan["outputs"], OUTPUTS):
        _fail("outputs")
    expected_parameters = {"inertia": 0.8, "activity": 1.2, "reset_rate": 0.0}
    if not _json_equal(plan["parameters"], expected_parameters) or not all(
        _number(value) for value in plan["parameters"].values()
    ):
        _fail("parameters")
    if (
        not _json_equal(plan["validation_times"], TIMES)
        or not all(_number(value) for value in plan["validation_times"])
        or plan["fine_step"] != 0.002
        or plan["coarse_step"] != 0.004
        or not _number(plan["fine_step"])
        or not _number(plan["coarse_step"])
        or plan["pairing_policy"] != PAIRING
    ):
        _fail("times/resolution/pairing")
    if any(
        round(time / plan["fine_step"]) % 2
        or not math.isclose(
            round(time / plan["fine_step"]) * plan["fine_step"],
            time,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for time in TIMES
    ):
        _fail("integral steps")

    sampling = plan["sampling"]
    sampling_keys = {
        "pilot_size",
        "pilot_seeds",
        "confirmatory_seeds",
        "compute_cap",
        "projection_formula",
        "nonpositive_denominator_outcome",
        "cap_exceeded_outcome",
        "confirmatory_batch_size",
        "pilot_reused_in_confirmatory_estimate",
        "maximum_interim_evaluations",
        "maximum_final_evaluations",
        "continuous_polling_allowed",
        "repeated_top_up_allowed",
        "stop_at_first_pass_allowed",
    }
    if set(sampling) != sampling_keys:
        _fail("sampling fields")
    if not isinstance(sampling["pilot_seeds"], list) or not isinstance(
        sampling["confirmatory_seeds"], list
    ):
        _fail("seed list types")
    if not _json_equal(
        sampling,
        {
            "pilot_size": 2048,
            "pilot_seeds": SEEDS[0],
            "confirmatory_seeds": SEEDS[1],
            "compute_cap": 131072,
            "projection_formula": LOCKED_FORMULA,
            "nonpositive_denominator_outcome": "unresolved",
            "cap_exceeded_outcome": "unresolved",
            "confirmatory_batch_size": "N_target; not N_target minus N0",
            "pilot_reused_in_confirmatory_estimate": False,
            "maximum_interim_evaluations": 1,
            "maximum_final_evaluations": 1,
            "continuous_polling_allowed": False,
            "repeated_top_up_allowed": False,
            "stop_at_first_pass_allowed": False,
        },
    ):
        _fail("sizes/seeds")
    integer_values = [
        sampling["pilot_size"],
        sampling["compute_cap"],
        *sampling["pilot_seeds"],
        *sampling["confirmatory_seeds"],
    ]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in integer_values):
        _fail("sizes/seeds types")
    if any(
        isinstance(sampling[key], bool) or not isinstance(sampling[key], int)
        for key in ("maximum_interim_evaluations", "maximum_final_evaluations")
    ) or any(
        not isinstance(sampling[key], bool)
        for key in (
            "pilot_reused_in_confirmatory_estimate",
            "continuous_polling_allowed",
            "repeated_top_up_allowed",
            "stop_at_first_pass_allowed",
        )
    ):
        _fail("sequential policy types")
    if (
        len(set(sampling["pilot_seeds"])) != len(sampling["pilot_seeds"])
        or len(set(sampling["confirmatory_seeds"]))
        != len(sampling["confirmatory_seeds"])
        or set(sampling["pilot_seeds"]) & set(sampling["confirmatory_seeds"])
    ):
        _fail("seed uniqueness")
    sequential_policy = {
        "pilot_reused_in_confirmatory_estimate": False,
        "maximum_interim_evaluations": 1,
        "maximum_final_evaluations": 1,
        "continuous_polling_allowed": False,
        "repeated_top_up_allowed": False,
        "stop_at_first_pass_allowed": False,
    }
    if (
        sampling["projection_formula"] != LOCKED_FORMULA
        or sampling["nonpositive_denominator_outcome"] != "unresolved"
        or sampling["cap_exceeded_outcome"] != "unresolved"
        or sampling["confirmatory_batch_size"] != "N_target; not N_target minus N0"
        or any(
            not _json_equal(sampling[key], value)
            for key, value in sequential_policy.items()
        )
    ):
        _fail("sequential policy")
    if not _json_equal(plan["uncertainty"], UNCERTAINTY):
        _fail("uncertainty")

    registry, schema = load_registry(), load_schema()
    entries = plan["run_configurations"]
    if not isinstance(entries, list) or len(entries) != len(EXPECTED_CONFIGURATIONS):
        _fail("configuration count")
    for entry, (time, observable, comparison) in zip(
        entries, EXPECTED_CONFIGURATIONS, strict=True
    ):
        if not isinstance(entry, dict) or set(entry) != {
            "id",
            "time",
            "reference_inputs",
            "run_configuration",
        }:
            _fail("entry fields")
        configuration = entry["run_configuration"]
        references = entry["reference_inputs"]
        if not isinstance(configuration, dict) or not isinstance(references, dict):
            _fail("entry value types")
        try:
            validate_run_configuration(configuration, registry, schema)
        except ValueError as exc:
            _fail(f"registry run configuration: {exc}")
        if (
            entry["id"] != _configuration_id(time, observable, comparison)
            or entry["time"] != time
            or not _number(entry["time"])
            or configuration["observable_class"] != observable
            or configuration["comparison_kind"] != comparison
        ):
            _fail("entry order/mapping")
        paired = comparison == "fine_coarse"
        if (
            configuration["evidence_tier"] != "primary"
            or configuration["compute_cap"] != 131072
            or not _json_equal(
                configuration["systematic_envelopes"],
                {"B_window": 0.0, "B_disc": 0.0 if paired else B_DISC_FLOOR},
            )
            or configuration["valid_coupling_exists"] is not paired
            or configuration["paired_paths"] is not paired
            or configuration["claimed_zero_crossing"] is not False
        ):
            _fail("entry policy")
        expected_references = _reference_inputs(time, observable)
        expected_scale = characteristic_scale(registry, observable, expected_references)
        if (
            not _json_equal(references, expected_references)
            or not math.isclose(
                configuration["characteristic_scale"],
                expected_scale,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or configuration["relative_margin"] != 0.01
            or configuration["normalized_floor_fraction"] != 0.005
        ):
            _fail("references/scale/margin")


_cov_jackknife = covariance_trace_jackknife


def project_confirmatory_size(
    *,
    pilot_size: int,
    quantile: float,
    pilot_standard_error: float,
    epsilon: float,
    pilot_discrepancy: float,
    b_window: float,
    b_disc: float,
    compute_cap: int,
) -> int | None:
    if (
        isinstance(pilot_size, bool)
        or not isinstance(pilot_size, int)
        or isinstance(compute_cap, bool)
        or not isinstance(compute_cap, int)
        or pilot_size < 3
        or compute_cap < pilot_size
        or not _number(pilot_discrepancy)
        or any(
            not _number(value) or value < 0
            for value in (quantile, pilot_standard_error, epsilon, b_window, b_disc)
        )
        or quantile <= 0
        or epsilon <= 0
    ):
        raise ValueError("invalid projection inputs")
    denominator = epsilon - abs(pilot_discrepancy) - b_window - b_disc
    if denominator <= 0:
        return None
    ratio = quantile * pilot_standard_error / denominator
    if not math.isfinite(ratio) or ratio > math.sqrt(compute_cap / pilot_size):
        return None
    projected = pilot_size * ratio * ratio
    if not math.isfinite(projected) or projected > compute_cap:
        return None
    target = math.ceil(projected)
    return target if 3 <= target <= compute_cap else None


def _analysis(
    plan: dict[str, Any], n: int, seeds: list[int]
) -> list[dict[str, Any]]:
    parameters = plan["parameters"]
    cache = {
        time: simulate_free_paired(
            inertia=parameters["inertia"],
            activity=parameters["activity"],
            end_time=time,
            fine_step=plan["fine_step"],
            ensemble_size=n,
            seed=seeds[index],
        )
        for index, time in enumerate(TIMES)
    }
    registry = load_registry()
    quantile = registry["evidence_tiers"]["primary"][
        "normal_equivalent_quantile"
    ]
    rows: list[dict[str, Any]] = []
    for entry in plan["run_configurations"]:
        configuration = entry["run_configuration"]
        time = entry["time"]
        observable = configuration["observable_class"]
        result = cache[time]
        paired = configuration["comparison_kind"] == "fine_coarse"
        if observable == "cov_r_trace":
            direct, direct_se = _cov_jackknife(result.fine_positions)
            pair, pair_se = _cov_jackknife(
                result.fine_positions, result.coarse_positions
            )
        else:
            metric = OBS[observable]
            direct = result.fine.values[metric]
            direct_se = result.fine.standard_errors[metric]
            pair = result.fine.values[metric] - result.coarse.values[metric]
            pair_se = result.paired_standard_errors[metric]
        reference = _reference(time, observable)
        delta, standard_error = (pair, pair_se) if paired else (
            direct - reference,
            direct_se,
        )
        epsilon = admissible_margin(
            registry,
            observable,
            configuration["evidence_tier"],
            reference=0.0 if paired else reference,
            scale=configuration["characteristic_scale"],
            normalized_floor_fraction=configuration["normalized_floor_fraction"],
        )
        b_disc = (
            0.0
            if paired
            else max(B_DISC_FLOOR, abs(pair) + quantile * pair_se)
        )
        lower = delta - quantile * standard_error
        upper = delta + quantile * standard_error
        rows.append(
            {
                "id": entry["id"],
                "time": time,
                "observable_class": observable,
                "comparison_kind": configuration["comparison_kind"],
                "evidence_tier": configuration["evidence_tier"],
                "reference": 0.0 if paired else reference,
                "delta": delta,
                "standard_error": standard_error,
                "interval": [lower, upper],
                "epsilon": epsilon,
                "B_window": 0.0,
                "B_disc": b_disc,
                "classification": classify_interval(
                    registry,
                    lower,
                    upper,
                    epsilon,
                    b_window=0.0,
                    b_disc=b_disc,
                ),
                "estimator": plan["uncertainty"]["methods"][observable][
                    configuration["comparison_kind"]
                ]["estimator"],
                "standard_error_method": plan["uncertainty"]["methods"][observable][
                    configuration["comparison_kind"]
                ]["standard_error"],
            }
        )
    return rows


def _validate_analysis_rows(
    plan: dict[str, Any], rows: Any, registry: dict[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_CONFIGURATIONS):
        raise ValueError("pilot output analysis row count failure")
    quantile = registry["evidence_tiers"]["primary"][
        "normal_equivalent_quantile"
    ]
    paired_rows: dict[tuple[float, str], dict[str, Any]] = {}
    for row, entry, (time, observable, comparison) in zip(
        rows,
        plan["run_configurations"],
        EXPECTED_CONFIGURATIONS,
        strict=True,
    ):
        if not isinstance(row, dict) or set(row) != ANALYSIS_FIELDS:
            raise ValueError("pilot output analysis fields failure")
        configuration = entry["run_configuration"]
        expected_reference = 0.0 if comparison == "fine_coarse" else _reference(
            time, observable
        )
        expected_estimator = plan["uncertainty"]["methods"][observable][comparison][
            "estimator"
        ]
        expected_standard_error_method = plan["uncertainty"]["methods"][observable][
            comparison
        ]["standard_error"]
        if (
            row["id"] != entry["id"]
            or row["time"] != time
            or row["observable_class"] != observable
            or row["comparison_kind"] != comparison
            or row["evidence_tier"] != configuration["evidence_tier"]
            or row["reference"] != expected_reference
            or row["estimator"] != expected_estimator
            or row["standard_error_method"] != expected_standard_error_method
        ):
            raise ValueError("pilot output analysis semantics failure")
        numeric_fields = (
            "reference",
            "delta",
            "standard_error",
            "epsilon",
            "B_window",
            "B_disc",
        )
        if any(not _number(row[field]) for field in numeric_fields):
            raise ValueError("pilot output analysis nonfinite value")
        if (
            row["standard_error"] < 0
            or row["B_window"] < 0
            or row["B_disc"] < 0
        ):
            raise ValueError("pilot output analysis negative uncertainty")
        interval = row["interval"]
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or any(not _number(value) for value in interval)
            or interval
            != [
                row["delta"] - quantile * row["standard_error"],
                row["delta"] + quantile * row["standard_error"],
            ]
        ):
            raise ValueError("pilot output analysis interval failure")
        expected_epsilon = admissible_margin(
            registry,
            observable,
            configuration["evidence_tier"],
            reference=expected_reference,
            scale=configuration["characteristic_scale"],
            normalized_floor_fraction=configuration["normalized_floor_fraction"],
        )
        if row["epsilon"] != expected_epsilon or row["B_window"] != 0.0:
            raise ValueError("pilot output analysis margin failure")
        expected_classification = classify_interval(
            registry,
            interval[0],
            interval[1],
            row["epsilon"],
            b_window=row["B_window"],
            b_disc=row["B_disc"],
        )
        if row["classification"] != expected_classification:
            raise ValueError("pilot output analysis classification failure")
        if comparison == "fine_coarse":
            paired_rows[(time, observable)] = row

    for row, (time, observable, comparison) in zip(
        rows, EXPECTED_CONFIGURATIONS, strict=True
    ):
        if comparison == "fine_coarse":
            if row["B_disc"] != 0.0:
                raise ValueError("pilot output paired B_disc failure")
            continue
        paired = paired_rows[(time, observable)]
        expected_b_disc = max(
            B_DISC_FLOOR,
            abs(paired["delta"]) + quantile * paired["standard_error"],
        )
        if row["B_disc"] != expected_b_disc:
            raise ValueError("pilot output direct B_disc failure")
    return rows


def _pilot_targets(
    plan: dict[str, Any], rows: list[dict[str, Any]], registry: dict[str, Any]
) -> list[int | None]:
    sampling = plan["sampling"]
    quantile = registry["evidence_tiers"]["primary"][
        "normal_equivalent_quantile"
    ]
    return [
        project_confirmatory_size(
            pilot_size=sampling["pilot_size"],
            quantile=quantile,
            pilot_standard_error=row["standard_error"],
            epsilon=row["epsilon"],
            pilot_discrepancy=row["delta"],
            b_window=row["B_window"],
            b_disc=row["B_disc"],
            compute_cap=sampling["compute_cap"],
        )
        for row in rows
    ]


def _overall(rows: list[dict[str, Any]]) -> str:
    outcomes = [row["classification"] for row in rows]
    if outcomes and all(outcome == "validated" for outcome in outcomes):
        return "validated"
    if any(outcome == "contradicted" for outcome in outcomes):
        return "contradicted"
    return "unresolved"


def _clean_commit() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if status.strip():
        raise RuntimeError("pilot/confirm require a clean committed preregistration")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _reserve(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("x", encoding="utf-8", newline="")


def _exact_path_argument(
    supplied: Path | None, expected_relative: str, label: str
) -> Path:
    expected = Path(expected_relative)
    if supplied is not None and supplied != expected:
        raise ValueError(f"{label} must be exactly the canonical path {expected_relative}")
    return ROOT / expected


def _base_metadata(
    plan: dict[str, Any],
    *,
    mode: str,
    plan_hash: str,
    commit: str,
    manifest: dict[str, str],
    registry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": mode,
        "output": plan["outputs"][mode],
        "plan_id": PLAN_ID,
        "plan_hash": plan_hash,
        "contract_version": "0.3",
        "registry_version": registry["schema_version"],
        "source_commit": commit,
        "source_manifest": manifest,
        "parameters": plan["parameters"],
        "resolution": {
            "fine_step": plan["fine_step"],
            "coarse_step": plan["coarse_step"],
            "times": plan["validation_times"],
        },
        "pairing_policy": PAIRING,
        "compute_cap": plan["sampling"]["compute_cap"],
        "interval_construction": plan["uncertainty"]["interval"],
    }


def _validate_pilot_artifact(
    prior: dict[str, Any],
    plan: dict[str, Any],
    *,
    plan_hash: str,
    commit: str,
    manifest: dict[str, str],
    registry: dict[str, Any],
) -> int:
    if set(prior) != PILOT_FIELDS:
        raise ValueError("pilot output top-level fields failure")
    expected = _base_metadata(
        plan,
        mode="pilot",
        plan_hash=plan_hash,
        commit=commit,
        manifest=manifest,
        registry=registry,
    )
    if any(
        not _json_equal(prior.get(key), value) for key, value in expected.items()
    ):
        raise ValueError("pilot output metadata integrity failure")
    if (
        prior["evidence_role"] != "design-only"
        or prior["overall"] != "design-only"
        or isinstance(prior["count"], bool)
        or not isinstance(prior["count"], int)
        or prior["count"] != plan["sampling"]["pilot_size"]
        or not isinstance(prior["seeds"], list)
        or any(
            isinstance(seed, bool) or not isinstance(seed, int)
            for seed in prior["seeds"]
        )
        or prior["seeds"] != plan["sampling"]["pilot_seeds"]
    ):
        raise ValueError("pilot output design/count/seed failure")
    rows = _validate_analysis_rows(plan, prior["analysis"], registry)
    targets = _pilot_targets(plan, rows, registry)
    eligible = all(target is not None for target in targets)
    n_target = max(targets) if eligible else None
    stored_targets = prior["per_config_n_target"]
    exact_targets = (
        isinstance(stored_targets, list)
        and len(stored_targets) == len(targets)
        and all(
            stored is None
            if expected is None
            else (
                not isinstance(stored, bool)
                and isinstance(stored, int)
                and stored == expected
            )
            for stored, expected in zip(stored_targets, targets, strict=True)
        )
    )
    if (
        not exact_targets
        or prior["n_target"] != n_target
        or isinstance(prior["n_target"], bool)
        or not isinstance(prior["n_target"], int)
        or not isinstance(prior["eligible_for_confirmation"], bool)
        or prior["eligible_for_confirmation"] is not eligible
    ):
        raise ValueError("pilot projection integrity failure")
    if not eligible:
        raise ValueError("pilot is not eligible for confirmation")
    if isinstance(n_target, bool) or not isinstance(n_target, int):
        raise ValueError("pilot projection target type failure")
    return n_target


def _failure_receipt(
    metadata: dict[str, Any], mode: str, exc: Exception
) -> dict[str, Any]:
    return {
        "mode": mode,
        "output": metadata["output"],
        "status": "failed-after-reservation",
        "evidence_role": "design-only" if mode == "pilot" else "confirmatory",
        "plan_id": metadata["plan_id"],
        "plan_hash": metadata["plan_hash"],
        "source_commit": metadata["source_commit"],
        "source_manifest": metadata["source_manifest"],
        "exception": {"type": type(exc).__name__, "message": str(exc)},
    }


def execute(
    plan_path: Path,
    mode: str,
    output: Path | None = None,
    pilot_output: Path | None = None,
    expected_pilot_sha256: str | None = None,
) -> dict[str, Any]:
    if mode not in ("pilot", "confirm"):
        raise ValueError("mode must be pilot or confirm")
    if plan_path != Path(PLAN_REL):
        raise ValueError(f"plan must be exactly {PLAN_REL}")
    canonical_output = _exact_path_argument(output, OUTPUTS[mode], "output")
    plan = load_preregistered_plan(plan_path)
    validate_preregistered_plan(plan)
    commit = _clean_commit()
    manifest = source_manifest()
    plan_hash = _hash(ROOT / PLAN_REL)
    registry = load_registry()
    metadata = _base_metadata(
        plan,
        mode=mode,
        plan_hash=plan_hash,
        commit=commit,
        manifest=manifest,
        registry=registry,
    )

    pilot_hash: str | None = None
    count: int
    seeds: list[int]
    if mode == "confirm":
        if pilot_output is None:
            raise ValueError("confirm requires the canonical pilot output")
        pilot_path = _exact_path_argument(pilot_output, PILOT_REL, "pilot output")
        if expected_pilot_sha256 is None:
            raise ValueError("confirm requires expected pilot SHA-256")
        if (
            len(expected_pilot_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_pilot_sha256)
        ):
            raise ValueError("expected pilot SHA-256 must be 64 lowercase hex characters")
        pilot_hash = _hash(pilot_path)
        if pilot_hash != expected_pilot_sha256:
            raise ValueError("pilot SHA-256 mismatch")
        prior = _json_load(pilot_path)
        count = _validate_pilot_artifact(
            prior,
            plan,
            plan_hash=plan_hash,
            commit=commit,
            manifest=manifest,
            registry=registry,
        )
        seeds = plan["sampling"]["confirmatory_seeds"]
    else:
        if pilot_output is not None or expected_pilot_sha256 is not None:
            raise ValueError("pilot does not accept confirm authentication arguments")
        count = plan["sampling"]["pilot_size"]
        seeds = plan["sampling"]["pilot_seeds"]

    handle = _reserve(canonical_output)
    try:
        analysis = _analysis(plan, count, seeds)
        rows = _validate_analysis_rows(plan, analysis, registry)
        if mode == "pilot":
            targets = _pilot_targets(plan, rows, registry)
            eligible = all(target is not None for target in targets)
            target = max(targets) if eligible else None
            result = {
                **metadata,
                "evidence_role": "design-only",
                "overall": "design-only",
                "count": count,
                "seeds": seeds,
                "analysis": rows,
                "per_config_n_target": targets,
                "n_target": target,
                "eligible_for_confirmation": eligible,
            }
        else:
            result = {
                **metadata,
                "evidence_role": "confirmatory",
                "overall": _overall(rows),
                "count": count,
                "seeds": seeds,
                "pilot_output_hash": pilot_hash,
                "analysis": rows,
            }
        success_text = _json_text(result)
        handle.write(success_text)
        handle.flush()
        return result
    except Exception as exc:
        receipt_text = _json_text(_failure_receipt(metadata, mode, exc))
        handle.seek(0)
        handle.truncate()
        handle.write(receipt_text)
        handle.flush()
        raise
    finally:
        handle.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "pilot", "confirm"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-output", type=Path)
    parser.add_argument("--expected-pilot-sha256")
    arguments = parser.parse_args()
    if arguments.mode == "validate":
        validate_preregistered_plan(load_preregistered_plan(arguments.plan))
        print("S-011 v2 plan valid")
        return
    execute(
        arguments.plan,
        arguments.mode,
        arguments.output,
        arguments.pilot_output,
        arguments.expected_pilot_sha256,
    )


if __name__ == "__main__":
    main()
