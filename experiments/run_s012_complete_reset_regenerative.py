"""Fail-closed one-shot executor for the frozen S-012 validation plan.

``validate`` performs no stochastic draw and creates no artifact.  ``pilot``
and ``confirm`` each have an exclusive, permanent attempt receipt and publish
to one canonical raw path only.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import string
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phasemap.common.model import ModelParams, State
from phasemap.simulation.complete_reset_regenerative import (
    CHUNK_SIZE,
    COARSE_STEP,
    FINE_STEP,
    PairedTerminalStates,
    covariance_trace_with_jackknife,
    kurtosis_with_jackknife,
    mean_with_se,
    paired_jackknife,
    simulate_regenerative_paired,
)
from phasemap.simulation.integrator import SimulationConfig, Trajectory, simulate
from phasemap.simulation.protocols import Protocol


PLAN_REL = Path("experiments/S-012-complete-reset-regenerative-primary-v1.json")
RAW = ROOT / "artifacts/raw"
PILOT = RAW / "S-012-complete-reset-regenerative-primary-v1-pilot.json"
CONFIRM = RAW / "S-012-complete-reset-regenerative-primary-v1-confirm.json"
FAILURE = RAW / "S-012-complete-reset-regenerative-primary-v1-failure.json"
PA = RAW / "S-012-complete-reset-regenerative-primary-v1-pilot-attempt.json"
CA = RAW / "S-012-complete-reset-regenerative-primary-v1-confirm-attempt.json"

PLAN_ID = "S-012-complete-reset-regenerative-primary-v1"
PLAN_SEMANTIC_SHA256 = (
    "32822df90a3b4c1c0fb25aa515e1494550dcefa8491b7f3b9136509408bfd566"
)
OUTPUT_SCHEMA_VERSION = "1.0.0"
Q = 2.5758293035
NORMALIZED_FLOOR = 0.005
RELATIVE_MARGIN = 0.01

EXPECTED_SCALE_RULES = {
    "u_x": "u_mean:sqrt(abs(uu_xx_reference))",
    "v_x": "v_mean:sqrt(abs(vv_xx_reference))",
    "r_x": "r_mean:sqrt(abs(rr_xx_reference))",
    "uu_xx": "uu:sqrt(abs(uu_xx_reference*uu_xx_reference))",
    "uu_yy": "uu:sqrt(abs(uu_yy_reference*uu_yy_reference))",
    "mean_squared_speed": "aggregated_trace:abs(reference)",
    "raw_mean_squared_displacement": "aggregated_trace:abs(reference)",
    "centered_spatial_variance": "cov_r_trace:abs(reference)",
    "raw_radial_excess_kurtosis_K": (
        "section_7_4_departure:max(1,abs(K_reference))"
    ),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Kept as a short alias because external audit snippets use this name.
sha = sha256_file


def _reject_nonfinite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_overflowed_nonfinite(value: Any, path: str = "$") -> None:
    """Reject finite-looking JSON numerals such as 1e999 that decode to inf."""

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite JSON number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_overflowed_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_overflowed_nonfinite(item, f"{path}[{index}]")


def load(path: Path) -> dict[str, Any]:
    """Strictly load one JSON object, rejecting duplicates and NaN/Infinity."""

    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    _reject_overflowed_nonfinite(value)
    return value


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate(plan: dict[str, Any]) -> None:
    """Fail closed unless the complete frozen plan has exactly known semantics."""

    if semantic_sha256(plan) != PLAN_SEMANTIC_SHA256:
        raise ValueError("plan semantic SHA-256 mismatch")
    if plan.get("plan_id") != PLAN_ID or plan.get("plan_version") != "1":
        raise ValueError("frozen plan identity mismatch")
    if plan.get("status") != "preregistered-not-executed":
        raise ValueError("frozen plan status mismatch")
    if plan["evidence"] != {
        "tier": "primary",
        "quantile": Q,
        "normalized_floor_fraction": NORMALIZED_FLOOR,
        "relative_margin": RELATIVE_MARGIN,
        "interval": "Delta_hat +/- q*SE_Delta",
        "margin": "epsilon=0.005*C+0.01*abs(reference)",
        "B_window": 0.0,
        "direct_B_disc": "abs(fine_minus_coarse_delta)+q*paired_SE_delta",
        "paired_B_disc": 0.0,
        "classification": {
            "validated": "expanded interval contained in [-epsilon,+epsilon]",
            "contradicted": "expanded interval disjoint from [-epsilon,+epsilon]",
            "unresolved": "otherwise",
        },
    }:
        raise ValueError("frozen evidence semantics mismatch")
    if len(plan["configurations"]) != 20:
        raise ValueError("frozen plan must contain exactly 20 configurations")
    if plan["sampling"]["N0"] != 8192:
        raise ValueError("frozen N0 mismatch")
    if plan["sampling"]["cap_per_case"] != 262144:
        raise ValueError("frozen sampling cap mismatch")
    if plan["integrator"]["fine_max_step"] != "1/512":
        raise ValueError("frozen fine resolution mismatch")
    if plan["integrator"]["coarse_max_step"] != "1/256":
        raise ValueError("frozen coarse resolution mismatch")
    kinds = {row["comparison_kind"] for row in plan["configurations"]}
    if kinds != {"direct_reference", "paired_fine_coarse"}:
        raise ValueError("frozen comparison kinds mismatch")


def _git_output(arguments: list[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def validate_raw_path_state(mode: str) -> None:
    """Validate ignored canonical paths explicitly for the requested stage."""

    if mode not in {"pilot", "confirm"}:
        raise ValueError(f"unsupported stage: {mode}")
    exists = {
        "pilot": PILOT.exists(),
        "confirm": CONFIRM.exists(),
        "failure": FAILURE.exists(),
        "pilot_attempt": PA.exists(),
        "confirm_attempt": CA.exists(),
    }
    if mode == "pilot" and any(exists.values()):
        raise RuntimeError(f"pilot requires all canonical raw paths absent: {exists}")
    expected_confirm = {
        "pilot": True,
        "confirm": False,
        "failure": False,
        "pilot_attempt": True,
        "confirm_attempt": False,
    }
    if mode == "confirm" and exists != expected_confirm:
        raise RuntimeError(
            f"confirm canonical raw-path state mismatch: {exists}"
        )


def clean_head(mode: str) -> str:
    if _git_output(["status", "--porcelain"]).strip():
        raise RuntimeError("a clean Git working tree is required")
    validate_raw_path_state(mode)
    head = _git_output(["rev-parse", "HEAD"]).strip()
    if len(head) != 40 or any(character not in string.hexdigits for character in head):
        raise RuntimeError("Git HEAD is not a full 40-character SHA")
    return head.lower()


def assert_event_trace(trace: Trajectory) -> None:
    """Assert exact-clock pre/post ordering and exact PVTheta reset state."""

    if trace.reset_times.size == 0:
        raise RuntimeError("BL2 event check produced no reset")
    reset_time = float(trace.reset_times[0])
    indices = np.flatnonzero(trace.times == reset_time)
    if indices.size < 2 or indices[-1] != indices[-2] + 1:
        raise RuntimeError("BL2 event check lacks adjacent equal-time records")
    post = int(indices[-1])
    if not np.array_equal(trace.positions[post], np.zeros(2, dtype=float)):
        raise RuntimeError("BL2 event check position is not exactly zero")
    if not np.array_equal(trace.velocities[post], np.zeros(2, dtype=float)):
        raise RuntimeError("BL2 event check velocity is not exactly zero")
    if float(trace.orientations[post]) != 0.0:
        raise RuntimeError("BL2 event check orientation is not exactly zero")


def event_check() -> None:
    """Run the reviewed fixed-seed exact-clock event-semantics prerequisite."""

    trace = simulate(
        ModelParams(inertia=1.0, activity=0.3, reset_rate=20.0),
        Protocol.PV_THETA,
        SimulationConfig(end_time=0.5, max_step=0.2, seed=7),
        State(
            position=np.array([2.0, -1.0]),
            velocity=np.array([1.0, -0.5]),
            orientation=0.4,
        ),
    )
    assert_event_trace(trace)


def source_manifest() -> dict[str, str]:
    names = [
        "docs/scientific-contract/CONTRACT.md",
        "docs/scientific-contract/validation_registry.json",
        "docs/scientific-contract/validation_registry.schema.json",
        "artifacts/derived/T-012-complete-reset-baseline.md",
        str(PLAN_REL).replace("\\", "/"),
        "experiments/run_s012_complete_reset_regenerative.py",
        "src/phasemap/simulation/complete_reset_regenerative.py",
        "src/phasemap/simulation/integrator.py",
        "src/phasemap/simulation/protocols.py",
        "src/phasemap/common/model.py",
        "src/phasemap/theory/complete_reset_baseline.py",
        "tests/simulation/test_complete_reset_regenerative.py",
    ]
    return {name: sha256_file(ROOT / name) for name in names}


# Compatibility name retained for review scripts written against the draft.
def manifest(_plan: Path | None = None) -> dict[str, str]:
    return source_manifest()


def reserve(path: Path, payload: dict[str, Any]) -> str:
    """Exclusively create and fsync a permanent stage-attempt receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical(payload).decode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    return sha256_file(path)


def publish(path: Path, payload: dict[str, Any]) -> str:
    """Atomically publish without permitting overwrite or aliases."""

    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(canonical(payload))
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_file(path)


def _rational(value: str) -> float:
    return float(Fraction(value))


def reference(case: dict[str, Any]) -> dict[str, float]:
    """Evaluate independent T-012 references and scale parents for one case."""

    import sympy as sp

    from phasemap.theory.complete_reset_baseline import (
        complete_reset_stationary_second_moments,
        source_passive_position_excess_kurtosis,
    )

    inertia = sp.Rational(case["inertia"])
    activity = sp.Rational(case["activity"])
    reset_rate = sp.Rational(case["reset_rate"])
    moments = complete_reset_stationary_second_moments(
        inertia,
        activity,
        reset_rate,
    )
    values = {
        "u_x": float(moments.orientation_mean[0]),
        "v_x": float(moments.velocity_mean[0]),
        "r_x": float(moments.position_mean[0]),
        "uu_xx": float(moments.orientation_second[0, 0]),
        "uu_yy": float(moments.orientation_second[1, 1]),
        "vv_xx": float(moments.velocity_second[0, 0]),
        "rr_xx": float(moments.position_second[0, 0]),
        "mean_squared_speed": float(moments.mean_squared_speed),
        "raw_mean_squared_displacement": float(moments.mean_squared_displacement),
        "centered_spatial_variance": float(moments.centered_spatial_variance),
    }
    if case["activity"] == "0":
        values["raw_radial_excess_kurtosis_K"] = float(
            source_passive_position_excess_kurtosis(inertia, reset_rate)
        )
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError(f"non-finite analytic reference for {case['case_id']}")
    return values


def characteristic_scale(config: dict[str, Any], refs: dict[str, float]) -> float:
    """Dispatch the exact registry/Section 7.4 characteristic-scale rule."""

    observable = config["observable"]
    expected = EXPECTED_SCALE_RULES.get(observable)
    if expected is None or config["scale_rule"] != expected:
        raise ValueError(f"frozen scale rule mismatch for {config['id']}")
    if observable == "u_x":
        scale = math.sqrt(abs(refs["uu_xx"]))
    elif observable == "v_x":
        scale = math.sqrt(abs(refs["vv_xx"]))
    elif observable == "r_x":
        scale = math.sqrt(abs(refs["rr_xx"]))
    elif observable in {"uu_xx", "uu_yy"}:
        scale = abs(refs[observable])
    elif observable == "raw_radial_excess_kurtosis_K":
        scale = max(1.0, abs(refs[observable]))
    else:
        scale = abs(refs[observable])
    if not math.isfinite(scale) or scale < 0.0:
        raise ValueError(f"invalid characteristic scale for {config['id']}")
    return scale


def classify_interval(
    delta: float,
    standard_error: float,
    epsilon: float,
    b_disc: float,
    b_window: float = 0.0,
    quantile: float = Q,
) -> tuple[list[float], list[float], str]:
    numbers = (delta, standard_error, epsilon, b_disc, b_window, quantile)
    if not all(math.isfinite(float(value)) for value in numbers):
        raise ValueError("classification inputs must be finite")
    if min(standard_error, epsilon, b_disc, b_window, quantile) < 0.0:
        raise ValueError("classification widths must be nonnegative")
    interval = [
        delta - quantile * standard_error,
        delta + quantile * standard_error,
    ]
    expansion = b_window + b_disc
    expanded = [interval[0] - expansion, interval[1] + expansion]
    if expanded[0] >= -epsilon and expanded[1] <= epsilon:
        classification = "validated"
    elif expanded[1] < -epsilon or expanded[0] > epsilon:
        classification = "contradicted"
    else:
        classification = "unresolved"
    return interval, expanded, classification


def projection_for_row(
    n0: int,
    row: dict[str, Any],
    cap: int,
    quantile: float = Q,
) -> dict[str, Any]:
    denominator = (
        row["epsilon"]
        - abs(row["delta"])
        - row.get("B_window", 0.0)
        - row["B_disc"]
    )
    result: dict[str, Any] = {
        "id": row["id"],
        "denominator": denominator,
        "projected_count": None,
        "eligible": False,
        "reason": None,
    }
    if not math.isfinite(denominator) or denominator <= 0.0:
        result["reason"] = "nonpositive_or_nonfinite_denominator"
        return result
    projected_float = n0 * (quantile * row["SE"] / denominator) ** 2
    if not math.isfinite(projected_float) or projected_float < 0.0:
        result["reason"] = "nonfinite_projection"
        return result
    projected = int(math.ceil(projected_float))
    result["projected_count"] = projected
    if projected > cap:
        result["reason"] = "above_cap"
        return result
    result["eligible"] = True
    return result


# Compatibility helper used by initial focused tests.
def project_target(n0: int, row: dict[str, Any], cap: int) -> int | None:
    projection = projection_for_row(n0, row, cap)
    return projection["projected_count"] if projection["eligible"] else None


def pilot_projection(
    rows: list[dict[str, Any]],
    n0: int,
    cap: int,
) -> dict[str, Any]:
    if len(rows) != 20:
        raise ValueError("pilot projection requires exactly 20 rows")
    projections = [projection_for_row(n0, row, cap) for row in rows]
    eligible = all(item["eligible"] for item in projections)
    target = None
    if eligible:
        target = max(n0, *(item["projected_count"] for item in projections))
        if target > cap:
            raise RuntimeError("eligible projection unexpectedly exceeds cap")
    return {
        "formula": (
            "ceil(N0*(q*SE0/(epsilon-abs(Delta0)-B_window0-B_disc0))^2)"
        ),
        "cap_per_case": cap,
        "rows": projections,
        "confirmation_eligible": eligible,
        "N_target_global": target,
    }


def overall_precedence(
    rows: list[dict[str, Any]],
    *,
    expected_count: int | None = None,
) -> str:
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f"expected {expected_count} classification rows")
    outcomes = [row.get("classification") for row in rows]
    if not outcomes or any(
        outcome not in {"validated", "contradicted", "unresolved"}
        for outcome in outcomes
    ):
        raise ValueError("invalid or empty classifications")
    if "contradicted" in outcomes:
        return "contradicted"
    if "unresolved" in outcomes:
        return "unresolved"
    return "validated"


def observable_values(
    result: PairedTerminalStates,
    observable: str,
) -> tuple[np.ndarray, np.ndarray]:
    fine_position = result.fine_position
    fine_velocity = result.fine_velocity
    fine_theta = result.fine_orientation
    coarse_position = result.coarse_position
    coarse_velocity = result.coarse_velocity
    coarse_theta = result.coarse_orientation
    if observable == "u_x":
        return np.cos(fine_theta), np.cos(coarse_theta)
    if observable == "v_x":
        return fine_velocity[:, 0], coarse_velocity[:, 0]
    if observable == "r_x":
        return fine_position[:, 0], coarse_position[:, 0]
    if observable == "uu_xx":
        return np.cos(fine_theta) ** 2, np.cos(coarse_theta) ** 2
    if observable == "uu_yy":
        return np.sin(fine_theta) ** 2, np.sin(coarse_theta) ** 2
    if observable == "mean_squared_speed":
        return (
            np.sum(fine_velocity * fine_velocity, axis=1),
            np.sum(coarse_velocity * coarse_velocity, axis=1),
        )
    if observable == "raw_mean_squared_displacement":
        return (
            np.sum(fine_position * fine_position, axis=1),
            np.sum(coarse_position * coarse_position, axis=1),
        )
    raise KeyError(observable)


def statistic_triplet(
    result: PairedTerminalStates,
    observable: str,
) -> dict[str, float]:
    if observable == "centered_spatial_variance":
        fine_estimate, fine_se = covariance_trace_with_jackknife(
            result.fine_position
        )
        coarse_estimate, coarse_se = covariance_trace_with_jackknife(
            result.coarse_position
        )
        paired_estimate, paired_se = paired_jackknife(
            result.fine_position,
            result.coarse_position,
            covariance_trace_with_jackknife,
        )
    elif observable == "raw_radial_excess_kurtosis_K":
        fine_estimate, fine_se = kurtosis_with_jackknife(result.fine_position)
        coarse_estimate, coarse_se = kurtosis_with_jackknife(
            result.coarse_position
        )
        paired_estimate, paired_se = paired_jackknife(
            result.fine_position,
            result.coarse_position,
            kurtosis_with_jackknife,
        )
    else:
        fine_values, coarse_values = observable_values(result, observable)
        fine_estimate, fine_se = mean_with_se(fine_values)
        coarse_estimate, coarse_se = mean_with_se(coarse_values)
        paired_estimate, paired_se = mean_with_se(fine_values - coarse_values)
    values = {
        "fine_estimate": fine_estimate,
        "fine_SE": fine_se,
        "coarse_estimate": coarse_estimate,
        "coarse_SE": coarse_se,
        "paired_estimate": paired_estimate,
        "paired_SE": paired_se,
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError(f"non-finite statistic for {observable}")
    if min(fine_se, coarse_se, paired_se) < 0.0:
        raise ValueError(f"negative standard error for {observable}")
    return values


def _supporting_passive_r4(result: PairedTerminalStates) -> dict[str, Any]:
    fine_r2 = np.sum(result.fine_position * result.fine_position, axis=1)
    coarse_r2 = np.sum(result.coarse_position * result.coarse_position, axis=1)
    fine = fine_r2 * fine_r2
    coarse = coarse_r2 * coarse_r2
    fine_estimate, fine_se = mean_with_se(fine)
    coarse_estimate, coarse_se = mean_with_se(coarse)
    paired_estimate, paired_se = mean_with_se(fine - coarse)
    return {
        "id": "passive-raw-r4-supporting-only",
        "case": "passive",
        "observable": "raw_E_abs_r_fourth",
        "gating": False,
        "fine_estimate": fine_estimate,
        "fine_SE": fine_se,
        "coarse_estimate": coarse_estimate,
        "coarse_SE": coarse_se,
        "paired_estimate": paired_estimate,
        "paired_SE": paired_se,
    }


def _case_provenance(
    result: PairedTerminalStates,
    count: int,
    base_seed: int,
    case_code: int,
) -> dict[str, Any]:
    if result.ages.shape != (count,) or not np.all(np.isfinite(result.ages)):
        raise ValueError("invalid age output shape or values")
    if np.any(result.ages < 0.0):
        raise ValueError("regenerative ages must be nonnegative")
    return {
        "count": count,
        "base_seed": base_seed,
        "case_code": case_code,
        "age_summary": {
            "minimum": float(result.ages.min()),
            "maximum": float(result.ages.max()),
            "mean": float(result.ages.mean()),
        },
        "array_sha256": result.array_sha256s(),
    }


def analyse(
    plan: dict[str, Any],
    count: int,
    base_seed: int,
) -> dict[str, Any]:
    """Execute the two registered cases and construct all auditable statistics."""

    cases = {case["case_id"]: case for case in plan["parameters"]}
    references = {name: reference(case) for name, case in cases.items()}
    results: dict[str, PairedTerminalStates] = {}
    for case in plan["parameters"]:
        results[case["case_id"]] = simulate_regenerative_paired(
            inertia=_rational(case["inertia"]),
            activity=_rational(case["activity"]),
            reset_rate=_rational(case["reset_rate"]),
            count=count,
            base_seed=base_seed,
            case_code=case["case_code"],
            chunk_size=plan["rng"]["chunk_size"],
        )

    unique_pairs = {
        (config["case"], config["observable"])
        for config in plan["configurations"]
    }
    statistics = {
        key: statistic_triplet(results[key[0]], key[1]) for key in unique_pairs
    }

    rows: list[dict[str, Any]] = []
    quantile = float(plan["evidence"]["quantile"])
    floor = float(plan["evidence"]["normalized_floor_fraction"])
    relative = float(plan["evidence"]["relative_margin"])
    for config in plan["configurations"]:
        key = (config["case"], config["observable"])
        stats = statistics[key]
        paired = config["comparison_kind"] == "paired_fine_coarse"
        analytic_reference = references[config["case"]][config["observable"]]
        validation_reference = 0.0 if paired else analytic_reference
        estimate = stats["paired_estimate"] if paired else stats["fine_estimate"]
        standard_error = stats["paired_SE"] if paired else stats["fine_SE"]
        delta = estimate - validation_reference
        b_disc = (
            0.0
            if paired
            else abs(stats["paired_estimate"]) + quantile * stats["paired_SE"]
        )
        scale = characteristic_scale(config, references[config["case"]])
        epsilon = floor * scale + relative * abs(validation_reference)
        interval, expanded, classification = classify_interval(
            delta,
            standard_error,
            epsilon,
            b_disc,
            0.0,
            quantile,
        )
        row = {
            "id": config["id"],
            "case": config["case"],
            "observable": config["observable"],
            "comparison_kind": config["comparison_kind"],
            "estimator": config["estimator"],
            "SE_method": config["SE"],
            "scale_rule": config["scale_rule"],
            **stats,
            "estimate": estimate,
            "analytic_reference": analytic_reference,
            "reference": validation_reference,
            "delta": delta,
            "SE": standard_error,
            "quantile": quantile,
            "characteristic_scale": scale,
            "normalized_floor_fraction": floor,
            "relative_margin": relative,
            "epsilon": epsilon,
            "B_window": 0.0,
            "B_disc": b_disc,
            "interval": interval,
            "expanded_interval": expanded,
            "classification": classification,
        }
        rows.append(row)

    case_provenance = {
        case["case_id"]: _case_provenance(
            results[case["case_id"]],
            count,
            base_seed,
            case["case_code"],
        )
        for case in plan["parameters"]
    }
    return {
        "rows": rows,
        "references": references,
        "case_provenance": case_provenance,
        "supporting_only": _supporting_passive_r4(results["passive"]),
    }


def _environment() -> dict[str, str]:
    import sympy

    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "sympy": sympy.__version__,
    }


def _execution_locks(plan: dict[str, Any], base_seed: int) -> dict[str, Any]:
    rng = deepcopy(plan["rng"])
    rng["stage_base_seed"] = base_seed
    return {
        "parameters": deepcopy(plan["parameters"]),
        "integrator": deepcopy(plan["integrator"]),
        "evidence": deepcopy(plan["evidence"]),
        "estimators": deepcopy(plan["estimators"]),
        "sampling": deepcopy(plan["sampling"]),
        "rng": rng,
        "resolved_steps": {
            "fine": FINE_STEP,
            "coarse": COARSE_STEP,
            "chunk_size": CHUNK_SIZE,
        },
    }


def _attempt_payload(
    stage: str,
    plan: dict[str, Any],
    plan_hash: str,
    source_commit: str,
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    return {
        "artifact_type": "S-012-stage-attempt",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "stage": stage,
        "plan_id": plan["plan_id"],
        "plan_sha256": plan_hash,
        "plan_semantic_sha256": PLAN_SEMANTIC_SHA256,
        "source_commit": source_commit,
        "source_manifest": source_hashes,
    }


def _base_result_payload(
    *,
    stage: str,
    plan: dict[str, Any],
    plan_hash: str,
    source_commit: str,
    source_hashes: dict[str, str],
    attempt_hash: str,
    count: int,
    base_seed: int,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "S-012-regenerative-validation",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "stage": stage,
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "contract_version": plan["contract_version"],
        "validation_registry_schema_version": plan[
            "validation_registry_schema_version"
        ],
        "plan_sha256": plan_hash,
        "plan_semantic_sha256": PLAN_SEMANTIC_SHA256,
        "source_commit": source_commit,
        "source_manifest": source_hashes,
        "attempt_receipt_sha256": attempt_hash,
        "count_per_case": count,
        "configuration_ids": [row["id"] for row in plan["configurations"]],
        "execution_locks": _execution_locks(plan, base_seed),
        "environment": _environment(),
        "analytic_references": analysis["references"],
        "case_provenance": analysis["case_provenance"],
        "rows": analysis["rows"],
        "supporting_only": analysis["supporting_only"],
    }


def build_pilot_payload(
    *,
    plan: dict[str, Any],
    plan_hash: str,
    source_commit: str,
    source_hashes: dict[str, str],
    attempt_hash: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    count = plan["sampling"]["N0"]
    payload = _base_result_payload(
        stage="pilot",
        plan=plan,
        plan_hash=plan_hash,
        source_commit=source_commit,
        source_hashes=source_hashes,
        attempt_hash=attempt_hash,
        count=count,
        base_seed=plan["rng"]["base_seeds"]["pilot"],
        analysis=analysis,
    )
    projection = pilot_projection(
        analysis["rows"],
        count,
        plan["sampling"]["cap_per_case"],
    )
    payload.update(
        {
            "data_role": "design-only-pilot",
            "projection": projection,
            "confirmation_eligible": projection["confirmation_eligible"],
            "N_target_global": projection["N_target_global"],
            "overall": "design-only",
        }
    )
    return payload


def build_confirm_payload(
    *,
    plan: dict[str, Any],
    plan_hash: str,
    source_commit: str,
    source_hashes: dict[str, str],
    attempt_hash: str,
    count: int,
    authenticated_pilot_sha256: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    payload = _base_result_payload(
        stage="confirm",
        plan=plan,
        plan_hash=plan_hash,
        source_commit=source_commit,
        source_hashes=source_hashes,
        attempt_hash=attempt_hash,
        count=count,
        base_seed=plan["rng"]["base_seeds"]["confirmatory"],
        analysis=analysis,
    )
    payload.update(
        {
            "data_role": "confirmatory-only",
            "authenticated_pilot_sha256": authenticated_pilot_sha256,
            "confirmatory_target_from_pilot": count,
            "overall": overall_precedence(
                analysis["rows"],
                expected_count=20,
            ),
        }
    )
    return payload


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in string.hexdigits for character in value)
    )


def _close(left: Any, right: Any) -> bool:
    try:
        left_float = float(left)
        right_float = float(right)
        return (
            math.isfinite(left_float)
            and math.isfinite(right_float)
            and math.isclose(left_float, right_float, rel_tol=1e-13, abs_tol=1e-15)
        )
    except (TypeError, ValueError):
        return False


def _validate_rows_against_plan(
    rows: Any,
    plan: dict[str, Any],
    references: dict[str, dict[str, float]],
) -> None:
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("pilot must contain exactly 20 rows")
    configurations = plan["configurations"]
    if [row.get("id") for row in rows] != [row["id"] for row in configurations]:
        raise ValueError("pilot configuration row order mismatch")
    paired_rows = {
        (row["case"], row["observable"]): row
        for row in rows
        if row.get("comparison_kind") == "paired_fine_coarse"
    }
    for row, config in zip(rows, configurations, strict=True):
        for key, plan_key in (
            ("case", "case"),
            ("observable", "observable"),
            ("comparison_kind", "comparison_kind"),
            ("estimator", "estimator"),
            ("SE_method", "SE"),
            ("scale_rule", "scale_rule"),
        ):
            if row.get(key) != config[plan_key]:
                raise ValueError(f"pilot row metadata mismatch: {config['id']} {key}")
        numeric = [
            "fine_estimate",
            "fine_SE",
            "coarse_estimate",
            "coarse_SE",
            "paired_estimate",
            "paired_SE",
            "estimate",
            "analytic_reference",
            "reference",
            "delta",
            "SE",
            "quantile",
            "characteristic_scale",
            "normalized_floor_fraction",
            "relative_margin",
            "epsilon",
            "B_window",
            "B_disc",
        ]
        if any(not _close(row.get(key), row.get(key)) for key in numeric):
            raise ValueError(f"non-finite pilot row value: {config['id']}")
        if min(row["fine_SE"], row["coarse_SE"], row["paired_SE"], row["SE"]) < 0:
            raise ValueError(f"negative pilot SE: {config['id']}")
        refs = references[config["case"]]
        analytic = refs[config["observable"]]
        paired = config["comparison_kind"] == "paired_fine_coarse"
        validation_reference = 0.0 if paired else analytic
        estimate = row["paired_estimate"] if paired else row["fine_estimate"]
        standard_error = row["paired_SE"] if paired else row["fine_SE"]
        if not _close(row["paired_estimate"], row["fine_estimate"] - row["coarse_estimate"]):
            raise ValueError(f"pilot paired estimate mismatch: {config['id']}")
        for actual, expected, label in (
            (row["analytic_reference"], analytic, "analytic reference"),
            (row["reference"], validation_reference, "validation reference"),
            (row["estimate"], estimate, "estimate"),
            (row["delta"], estimate - validation_reference, "delta"),
            (row["SE"], standard_error, "SE"),
            (row["quantile"], Q, "quantile"),
            (row["normalized_floor_fraction"], NORMALIZED_FLOOR, "floor"),
            (row["relative_margin"], RELATIVE_MARGIN, "relative margin"),
            (row["B_window"], 0.0, "B_window"),
        ):
            if not _close(actual, expected):
                raise ValueError(f"pilot {label} mismatch: {config['id']}")
        scale = characteristic_scale(config, refs)
        epsilon = NORMALIZED_FLOOR * scale + RELATIVE_MARGIN * abs(
            validation_reference
        )
        paired_row = paired_rows[(config["case"], config["observable"])]
        b_disc = (
            0.0
            if paired
            else abs(paired_row["paired_estimate"]) + Q * paired_row["paired_SE"]
        )
        if not _close(row["characteristic_scale"], scale):
            raise ValueError(f"pilot characteristic scale mismatch: {config['id']}")
        if not _close(row["epsilon"], epsilon) or not _close(row["B_disc"], b_disc):
            raise ValueError(f"pilot envelope mismatch: {config['id']}")
        interval, expanded, classification = classify_interval(
            row["delta"],
            row["SE"],
            epsilon,
            b_disc,
        )
        if row.get("interval") != interval:
            raise ValueError(f"pilot interval mismatch: {config['id']}")
        if row.get("expanded_interval") != expanded:
            raise ValueError(f"pilot expanded interval mismatch: {config['id']}")
        if row.get("classification") != classification:
            raise ValueError(f"pilot classification mismatch: {config['id']}")


def authenticate_pilot(
    *,
    plan: dict[str, Any],
    plan_hash: str,
    source_commit: str,
    source_hashes: dict[str, str],
    cli_sha256: str | None,
) -> tuple[dict[str, Any], int, str]:
    """Authenticate every locked pilot field before confirmation is allowed."""

    if not _is_sha256(cli_sha256) or sha256_file(PILOT) != cli_sha256.lower():
        raise ValueError("confirm pilot CLI SHA-256 authentication failed")
    attempt = load(PA)
    expected_attempt = _attempt_payload(
        "pilot",
        plan,
        plan_hash,
        source_commit,
        source_hashes,
    )
    if attempt != expected_attempt:
        raise ValueError("pilot attempt receipt semantics mismatch")
    attempt_hash = sha256_file(PA)
    pilot = load(PILOT)
    expected_static = {
        "artifact_type": "S-012-regenerative-validation",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "stage": "pilot",
        "data_role": "design-only-pilot",
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "contract_version": plan["contract_version"],
        "validation_registry_schema_version": plan[
            "validation_registry_schema_version"
        ],
        "plan_sha256": plan_hash,
        "plan_semantic_sha256": PLAN_SEMANTIC_SHA256,
        "source_commit": source_commit,
        "source_manifest": source_hashes,
        "attempt_receipt_sha256": attempt_hash,
        "count_per_case": plan["sampling"]["N0"],
        "configuration_ids": [row["id"] for row in plan["configurations"]],
        "execution_locks": _execution_locks(
            plan,
            plan["rng"]["base_seeds"]["pilot"],
        ),
        "overall": "design-only",
    }
    expected_pilot_keys = {
        "artifact_type",
        "schema_version",
        "stage",
        "data_role",
        "plan_id",
        "plan_version",
        "contract_version",
        "validation_registry_schema_version",
        "plan_sha256",
        "plan_semantic_sha256",
        "source_commit",
        "source_manifest",
        "attempt_receipt_sha256",
        "count_per_case",
        "configuration_ids",
        "execution_locks",
        "environment",
        "analytic_references",
        "case_provenance",
        "rows",
        "supporting_only",
        "projection",
        "confirmation_eligible",
        "N_target_global",
        "overall",
    }
    if set(pilot) != expected_pilot_keys:
        raise ValueError("pilot output schema keys mismatch")
    for key, expected in expected_static.items():
        if pilot.get(key) != expected:
            raise ValueError(f"pilot authentication mismatch: {key}")
    expected_references = {
        case["case_id"]: reference(case) for case in plan["parameters"]
    }
    if pilot.get("analytic_references") != expected_references:
        raise ValueError("pilot analytic references mismatch")
    _validate_rows_against_plan(pilot.get("rows"), plan, expected_references)
    expected_projection = pilot_projection(
        pilot["rows"],
        plan["sampling"]["N0"],
        plan["sampling"]["cap_per_case"],
    )
    if pilot.get("projection") != expected_projection:
        raise ValueError("pilot projection mismatch")
    if pilot.get("confirmation_eligible") is not True:
        raise ValueError("pilot is not eligible for confirmation")
    if expected_projection["confirmation_eligible"] is not True:
        raise ValueError("recomputed pilot is not eligible for confirmation")
    target = expected_projection["N_target_global"]
    if (
        isinstance(target, bool)
        or not isinstance(target, int)
        or target < plan["sampling"]["N0"]
        or target > plan["sampling"]["cap_per_case"]
        or pilot.get("N_target_global") != target
    ):
        raise ValueError("pilot global target mismatch")
    case_provenance = pilot.get("case_provenance")
    expected_cases = {case["case_id"] for case in plan["parameters"]}
    if not isinstance(case_provenance, dict) or set(case_provenance) != expected_cases:
        raise ValueError("pilot case provenance keys mismatch")
    for case in plan["parameters"]:
        record = case_provenance[case["case_id"]]
        if (
            record.get("count") != plan["sampling"]["N0"]
            or record.get("base_seed") != plan["rng"]["base_seeds"]["pilot"]
            or record.get("case_code") != case["case_code"]
        ):
            raise ValueError(f"pilot case provenance mismatch: {case['case_id']}")
        hashes = record.get("array_sha256")
        expected_hash_names = {
            "ages",
            "fine_position",
            "fine_velocity",
            "fine_orientation",
            "coarse_position",
            "coarse_velocity",
            "coarse_orientation",
        }
        if not isinstance(hashes, dict) or set(hashes) != expected_hash_names:
            raise ValueError(f"pilot array hashes missing: {case['case_id']}")
        if not all(_is_sha256(value) for value in hashes.values()):
            raise ValueError(f"pilot array hash invalid: {case['case_id']}")
        summary = record.get("age_summary")
        if not isinstance(summary, dict) or set(summary) != {
            "minimum",
            "maximum",
            "mean",
        }:
            raise ValueError(f"pilot age summary missing: {case['case_id']}")
        minimum = summary["minimum"]
        maximum = summary["maximum"]
        mean = summary["mean"]
        if (
            not all(_close(value, value) for value in (minimum, maximum, mean))
            or minimum < 0.0
            or not minimum <= mean <= maximum
        ):
            raise ValueError(f"pilot age summary invalid: {case['case_id']}")
    if pilot.get("environment") != _environment():
        raise ValueError("pilot execution environment mismatch")
    supporting = pilot.get("supporting_only")
    if not isinstance(supporting, dict) or supporting.get("gating") is not False:
        raise ValueError("pilot supporting-only r4 record missing")
    if (
        supporting.get("id") != "passive-raw-r4-supporting-only"
        or supporting.get("case") != "passive"
        or supporting.get("observable") != "raw_E_abs_r_fourth"
    ):
        raise ValueError("pilot supporting-only observable mismatch")
    supporting_numbers = [
        "fine_estimate",
        "fine_SE",
        "coarse_estimate",
        "coarse_SE",
        "paired_estimate",
        "paired_SE",
    ]
    if any(not _close(supporting.get(key), supporting.get(key)) for key in supporting_numbers):
        raise ValueError("pilot supporting-only r4 contains non-finite values")
    if min(
        supporting["fine_SE"],
        supporting["coarse_SE"],
        supporting["paired_SE"],
    ) < 0.0:
        raise ValueError("pilot supporting-only r4 contains a negative SE")
    if not _close(
        supporting["paired_estimate"],
        supporting["fine_estimate"] - supporting["coarse_estimate"],
    ):
        raise ValueError("pilot supporting-only r4 paired estimate mismatch")
    return pilot, target, cli_sha256.lower()


def execute(
    mode: str,
    plan_path: Path,
    pilot_sha256: str | None = None,
) -> dict[str, Any]:
    if mode not in {"pilot", "confirm"}:
        raise ValueError(f"unsupported execution stage: {mode}")
    if plan_path != PLAN_REL:
        raise ValueError("the canonical relative plan path is required")
    absolute_plan = ROOT / plan_path
    plan = load(absolute_plan)
    validate(plan)
    plan_hash = sha256_file(absolute_plan)
    source_commit = clean_head(mode)
    source_hashes = source_manifest()

    authenticated_pilot_sha256: str | None = None
    if mode == "confirm":
        _, count, authenticated_pilot_sha256 = authenticate_pilot(
            plan=plan,
            plan_hash=plan_hash,
            source_commit=source_commit,
            source_hashes=source_hashes,
            cli_sha256=pilot_sha256,
        )
        base_seed = plan["rng"]["base_seeds"]["confirmatory"]
        attempt_path = CA
        output_path = CONFIRM
    else:
        if pilot_sha256 is not None:
            raise ValueError("pilot does not accept --pilot-sha256")
        count = plan["sampling"]["N0"]
        base_seed = plan["rng"]["base_seeds"]["pilot"]
        attempt_path = PA
        output_path = PILOT

    # The event prerequisite intentionally precedes stage reservation: BL2
    # blocks the scientific attempt and must not consume the one pilot/final.
    event_check()
    attempt_payload = _attempt_payload(
        mode,
        plan,
        plan_hash,
        source_commit,
        source_hashes,
    )
    attempt_hash = reserve(attempt_path, attempt_payload)
    try:
        analysis = analyse(plan, count, base_seed)
        if mode == "pilot":
            payload = build_pilot_payload(
                plan=plan,
                plan_hash=plan_hash,
                source_commit=source_commit,
                source_hashes=source_hashes,
                attempt_hash=attempt_hash,
                analysis=analysis,
            )
        else:
            assert authenticated_pilot_sha256 is not None
            payload = build_confirm_payload(
                plan=plan,
                plan_hash=plan_hash,
                source_commit=source_commit,
                source_hashes=source_hashes,
                attempt_hash=attempt_hash,
                count=count,
                authenticated_pilot_sha256=authenticated_pilot_sha256,
                analysis=analysis,
            )
        publish(output_path, payload)
        return payload
    except BaseException as error:
        failure_payload = {
            "artifact_type": "S-012-technical-failure",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "stage": mode,
            "error_type": type(error).__name__,
            "error": str(error),
            "plan_id": plan["plan_id"],
            "plan_sha256": plan_hash,
            "plan_semantic_sha256": PLAN_SEMANTIC_SHA256,
            "source_commit": source_commit,
            "source_manifest": source_hashes,
            "attempt_receipt_sha256": attempt_hash,
        }
        try:
            publish(FAILURE, failure_payload)
        finally:
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "pilot", "confirm"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("--pilot-sha256")
    arguments = parser.parse_args()
    if arguments.plan != PLAN_REL:
        parser.error(f"plan must be the canonical relative path: {PLAN_REL}")
    plan = load(ROOT / arguments.plan)
    validate(plan)
    if arguments.mode == "validate":
        if arguments.pilot_sha256 is not None:
            parser.error("validate does not accept --pilot-sha256")
        print(
            f"S-012 plan valid: semantic_sha256={PLAN_SEMANTIC_SHA256}; "
            "no stochastic draw performed"
        )
        return
    payload = execute(
        arguments.mode,
        arguments.plan,
        arguments.pilot_sha256,
    )
    output = PILOT if arguments.mode == "pilot" else CONFIRM
    print(
        f"{arguments.mode} sha256={sha256_file(output)} "
        f"overall={payload['overall']}"
    )


if __name__ == "__main__":
    main()
