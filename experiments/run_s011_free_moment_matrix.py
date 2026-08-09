"""One-shot executor for the frozen deterministic S-011 replacement plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from phasemap.simulation.free_moment_baseline import (  # noqa: E402
    BASIS_NAMES,
    OBSERVABLE_NAMES,
    SYMMETRY_ZERO_NAMES,
    TAYLOR_ORDER,
    build_free_moment_matrix,
    default_free_moment_state,
    extract_free_invariants,
    extract_free_observables,
    propagate_free_moment_state,
)
from phasemap.theory.free_baseline import (  # noqa: E402
    free_scalar_moments,
    overdamped_mean_squared_displacement,
)


PLAN_ID = "S-011-free-moment-matrix-primary-v1"
PLAN_REL = Path("experiments/S-011-free-moment-matrix-primary-v1.json")
OUTPUT_REL = Path("artifacts/raw/S-011-free-moment-matrix-primary-v1.json")
EXPECTED_PLAN_SEMANTIC_SHA256 = (
    "4901aa0f9c307dc6b08626f767805ef467df9d8ba67985588c3e1277dc33c655"
)
COARSE_MAX_STEP = sp.Rational(1, 16)
FINE_MAX_STEP = sp.Rational(1, 32)
ABSOLUTE_TOLERANCE = 1e-12

MANIFEST_PATHS = (
    Path("docs/scientific-contract/CONTRACT.md"),
    Path("docs/scientific-contract/validation_registry.json"),
    Path("artifacts/derived/T-010-generator-scaffold.md"),
    Path("artifacts/derived/T-011-free-baseline.md"),
    Path("pyproject.toml"),
    Path("src/phasemap/theory/generator.py"),
    Path("src/phasemap/theory/free_baseline.py"),
    Path("src/phasemap/simulation/free_moment_baseline.py"),
    PLAN_REL,
    Path("experiments/run_s011_free_moment_matrix.py"),
    Path("tests/simulation/test_free_moment_baseline.py"),
)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"nonfinite JSON value is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical_semantic_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def load_preregistered_plan(path: Path) -> dict[str, Any]:
    """Load strict JSON, rejecting duplicate keys and nonfinite constants."""

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    return value


def validate_preregistered_plan(plan: dict[str, Any]) -> None:
    """Require the exact frozen semantic content, then assert runtime locks."""

    semantic_hash = _sha256_bytes(_canonical_semantic_bytes(plan))
    if semantic_hash != EXPECTED_PLAN_SEMANTIC_SHA256:
        raise ValueError("plan does not match the frozen preregistration")
    if plan["plan_id"] != PLAN_ID or plan["status"] != "preregistered":
        raise ValueError("plan identity/status failure")
    if plan["canonical_output"] != OUTPUT_REL.as_posix():
        raise ValueError("canonical output failure")
    if tuple(plan["matrix_route"]["required_basis_names"]) != BASIS_NAMES:
        raise ValueError("basis lock failure")
    if tuple(plan["reference_route"]["observables"]) != OBSERVABLE_NAMES:
        raise ValueError("observable lock failure")
    if (
        tuple(plan["invariants"]["symmetry_forced_zero_basis_names"])
        != SYMMETRY_ZERO_NAMES
    ):
        raise ValueError("invariant lock failure")
    propagation = plan["propagation"]
    if (
        propagation["taylor_terms"] != TAYLOR_ORDER
        or sp.Rational(propagation["coarse_max_step"]) != COARSE_MAX_STEP
        or sp.Rational(propagation["fine_max_step"]) != FINE_MAX_STEP
        or propagation["adaptive_stepping"] is not False
        or propagation["retries"] is not False
        or propagation["matrix_exponential"] is not False
        or propagation["tolerance_tuning"] is not False
    ):
        raise ValueError("propagation lock failure")
    if plan["classification"]["absolute_tolerance"] != ABSOLUTE_TOLERANCE:
        raise ValueError("classification tolerance failure")
    if (
        plan["scope"]["ensemble_size"] != "not_applicable"
        or plan["scope"]["seed_policy"] != "not_applicable"
        or plan["scope"]["prior_pilot_reused"] is not False
        or plan["scope"]["prior_pilot_reclassified"] is not False
    ):
        raise ValueError("deterministic scope failure")


def source_manifest() -> dict[str, str]:
    """Hash every source named by the frozen provenance contract."""

    manifest: dict[str, str] = {}
    for relative in MANIFEST_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"required provenance source is absent: {relative}")
        manifest[relative.as_posix()] = _sha256_file(path)
    return manifest


def _clean_source_commit() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if status.strip():
        raise RuntimeError("execution requires a clean committed implementation")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise RuntimeError("could not identify the clean source commit")
    return commit


def _array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return _sha256_bytes(canonical.tobytes(order="C"))


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise TypeError(f"{label} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise FloatingPointError(f"{label} must be finite")
    return converted


def classify_values(
    coarse: float,
    fine: float,
    reference: float,
    tolerance: float = ABSOLUTE_TOLERANCE,
) -> dict[str, float | str]:
    """Apply the frozen validated/contradicted/unresolved decision rule."""

    coarse_value = _finite_number(coarse, "coarse")
    fine_value = _finite_number(fine, "fine")
    reference_value = _finite_number(reference, "reference")
    tolerance_value = _finite_number(tolerance, "tolerance")
    if tolerance_value <= 0:
        raise ValueError("tolerance must be positive")
    coarse_error = _finite_number(
        abs(coarse_value - reference_value), "coarse error"
    )
    fine_error = _finite_number(abs(fine_value - reference_value), "fine error")
    resolution_difference = _finite_number(
        abs(fine_value - coarse_value), "resolution difference"
    )
    maximum = max(coarse_error, fine_error, resolution_difference)
    if maximum <= tolerance_value:
        classification = "validated"
    elif (
        resolution_difference <= tolerance_value
        and coarse_error > tolerance_value
        and fine_error > tolerance_value
    ):
        classification = "contradicted"
    else:
        classification = "unresolved"
    return {
        "coarse": coarse_value,
        "fine": fine_value,
        "reference": reference_value,
        "coarse_error": coarse_error,
        "fine_error": fine_error,
        "resolution_difference": resolution_difference,
        "classification": classification,
    }


def aggregate_classifications(
    classifications: Iterable[str],
    *,
    trend_passed: bool = True,
) -> str:
    """Aggregate with contradiction priority and failed-trend unresolvedness."""

    outcomes = tuple(classifications)
    allowed = {"validated", "contradicted", "unresolved"}
    if not outcomes or any(value not in allowed for value in outcomes):
        raise ValueError("invalid or empty classifications")
    if any(value == "contradicted" for value in outcomes):
        return "contradicted"
    if any(value == "unresolved" for value in outcomes) or not trend_passed:
        return "unresolved"
    return "validated"


def _reference_values(time: str, inertia: str, activity: str) -> dict[str, float]:
    exact_time = sp.Rational(time)
    exact_inertia = sp.Rational(inertia)
    exact_activity = sp.Rational(activity)
    moments = free_scalar_moments(exact_time, exact_inertia, exact_activity)
    result: dict[str, float] = {}
    for name in OBSERVABLE_NAMES:
        value = float(sp.N(getattr(moments, name), 50))
        result[name] = _finite_number(value, f"reference {name}")
    return result


def _invariant_rows(
    coarse: dict[str, float | dict[str, float]],
    fine: dict[str, float | dict[str, float]],
) -> list[dict[str, Any]]:
    coarse_zero = coarse["symmetry_forced_zero"]
    fine_zero = fine["symmetry_forced_zero"]
    if not isinstance(coarse_zero, dict) or not isinstance(fine_zero, dict):
        raise TypeError("symmetry invariant extraction failure")
    specifications = [
        ("one", coarse["constant"], fine["constant"], 1.0),
        (
            "uu_xx+uu_yy",
            coarse["orientation_norm"],
            fine["orientation_norm"],
            1.0,
        ),
        *(
            (name, coarse_zero[name], fine_zero[name], 0.0)
            for name in SYMMETRY_ZERO_NAMES
        ),
    ]
    rows: list[dict[str, Any]] = []
    for name, coarse_value, fine_value, expected in specifications:
        rows.append(
            {
                "name": name,
                **classify_values(
                    _finite_number(coarse_value, f"coarse invariant {name}"),
                    _finite_number(fine_value, f"fine invariant {name}"),
                    expected,
                ),
            }
        )
    return rows


def _case_results(
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    by_case_time: dict[tuple[str, str], dict[str, Any]] = {}
    initial_state = default_free_moment_state()
    for parameter_case in plan["parameter_cases"]:
        case_id = parameter_case["id"]
        inertia = parameter_case["inertia"]
        activity = parameter_case["activity"]
        system = build_free_moment_matrix(inertia, activity)
        time_results: list[dict[str, Any]] = []
        case_classifications: list[str] = []
        for time in plan["times"]:
            coarse = propagate_free_moment_state(
                system.values,
                initial_state,
                time,
                COARSE_MAX_STEP,
            )
            fine = propagate_free_moment_state(
                system.values,
                initial_state,
                time,
                FINE_MAX_STEP,
            )
            coarse_observables = extract_free_observables(system.names, coarse.state)
            fine_observables = extract_free_observables(system.names, fine.state)
            references = _reference_values(time, inertia, activity)
            comparisons = [
                {
                    "observable": name,
                    **classify_values(
                        coarse_observables[name],
                        fine_observables[name],
                        references[name],
                    ),
                }
                for name in OBSERVABLE_NAMES
            ]
            invariants = _invariant_rows(
                extract_free_invariants(system.names, coarse.state),
                extract_free_invariants(system.names, fine.state),
            )
            classifications = [
                row["classification"] for row in (*comparisons, *invariants)
            ]
            time_classification = aggregate_classifications(classifications)
            time_result = {
                "time": time,
                "coarse": {
                    "max_step": str(COARSE_MAX_STEP),
                    "step_count": coarse.step_count,
                    "step_size": str(coarse.step_size),
                    "state": [float(value) for value in coarse.state],
                },
                "fine": {
                    "max_step": str(FINE_MAX_STEP),
                    "step_count": fine.step_count,
                    "step_size": str(fine.step_size),
                    "state": [float(value) for value in fine.state],
                },
                "comparisons": comparisons,
                "invariants": invariants,
                "classification": time_classification,
            }
            time_results.append(time_result)
            by_case_time[(case_id, time)] = time_result
            case_classifications.extend(classifications)
        cases.append(
            {
                "id": case_id,
                "inertia": inertia,
                "activity": activity,
                "matrix_sha256": _array_sha256(system.values),
                "times": time_results,
                "classification": aggregate_classifications(case_classifications),
            }
        )
    return cases, by_case_time


def evaluate_overdamped_support(
    plan: dict[str, Any],
    by_case_time: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate the locked fine-MSD monotonic trend after eligibility checks."""

    support = plan["overdamped_support"]
    activity = support["activity"]
    ids_by_inertia = {
        case["inertia"]: case["id"]
        for case in plan["parameter_cases"]
        if case["activity"] == activity
    }
    time_rows: list[dict[str, Any]] = []
    for time in support["times"]:
        finite_rows: list[dict[str, Any]] = []
        eligible = True
        for inertia in support["inertia_sequence"]:
            case_id = ids_by_inertia.get(inertia)
            if case_id is None or (case_id, time) not in by_case_time:
                raise ValueError("overdamped-support case/time lookup failure")
            time_result = by_case_time[(case_id, time)]
            comparison = next(
                row
                for row in time_result["comparisons"]
                if row["observable"] == support["observable"]
            )
            eligible = eligible and comparison["classification"] == "validated"
            finite_rows.append(
                {
                    "inertia": inertia,
                    "fine_value": comparison["fine"],
                    "finite_reference_classification": comparison["classification"],
                }
            )
        if not eligible:
            time_rows.append(
                {
                    "time": time,
                    "eligible": False,
                    "passed": False,
                    "reason": "finite-inertia comparison was not validated",
                }
            )
            continue

        exact_reference = overdamped_mean_squared_displacement(
            sp.Rational(time), sp.Rational(activity)
        )
        reference = _finite_number(
            float(sp.N(exact_reference, 50)),
            "overdamped reference",
        )
        discrepancies: list[float] = []
        for row in finite_rows:
            discrepancy = _finite_number(
                abs(float(row["fine_value"]) - reference),
                "overdamped discrepancy",
            )
            row["absolute_discrepancy"] = discrepancy
            discrepancies.append(discrepancy)
        passed = all(
            left > right
            for left, right in zip(
                discrepancies[:-1], discrepancies[1:], strict=True
            )
        )
        time_rows.append(
            {
                "time": time,
                "eligible": True,
                "overdamped_reference": reference,
                "finite_inertia": finite_rows,
                "passed": passed,
            }
        )
    return {
        "observable": support["observable"],
        "inertia_sequence": support["inertia_sequence"],
        "activity": activity,
        "times": time_rows,
        "passed": all(row["passed"] for row in time_rows),
    }


def _float64_metadata() -> dict[str, Any]:
    info = np.finfo(np.float64)
    return {
        "dtype": np.dtype(np.float64).str,
        "bits": info.bits,
        "eps": float(info.eps),
        "epsneg": float(info.epsneg),
        "tiny": float(info.tiny),
        "max": float(info.max),
        "nmant": info.nmant,
        "nexp": info.nexp,
    }


def build_result_payload(
    plan: dict[str, Any],
    *,
    source_commit: str,
    manifest: dict[str, str],
) -> dict[str, Any]:
    """Execute the frozen grid; callers must enforce the clean-source gate."""

    validate_preregistered_plan(plan)
    cases, by_case_time = _case_results(plan)
    overdamped_support = evaluate_overdamped_support(plan, by_case_time)
    classifications = [
        row["classification"]
        for case in cases
        for time in case["times"]
        for row in (*time["comparisons"], *time["invariants"])
    ]
    initial_state = default_free_moment_state()
    matrix_hashes = {case["id"]: case["matrix_sha256"] for case in cases}
    step_counts = {
        case["id"]: {
            time["time"]: {
                "coarse": time["coarse"]["step_count"],
                "fine": time["fine"]["step_count"],
            }
            for time in case["times"]
        }
        for case in cases
    }
    return {
        "schema_version": "1.0.0",
        "task_id": "S-011",
        "status": "completed",
        "evidence_role": "deterministic_primary",
        "plan_id": PLAN_ID,
        "contract_version": plan["contract_version"],
        "registry_schema_version": plan["registry_schema_version"],
        "canonical_output": OUTPUT_REL.as_posix(),
        "plan_sha256": _sha256_file(ROOT / PLAN_REL),
        "source_commit": source_commit,
        "source_manifest": manifest,
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy_version": np.__version__,
            "sympy_version": sp.__version__,
            "operating_system": platform.platform(),
            "machine_architecture": platform.machine(),
            "float64": _float64_metadata(),
        },
        "configuration": {
            "basis_names": list(BASIS_NAMES),
            "parameter_cases": plan["parameter_cases"],
            "times": plan["times"],
            "taylor_order": TAYLOR_ORDER,
            "coarse_max_step": str(COARSE_MAX_STEP),
            "fine_max_step": str(FINE_MAX_STEP),
            "initial_state": [float(value) for value in initial_state],
            "initial_state_sha256": _array_sha256(initial_state),
            "matrix_hashes": matrix_hashes,
            "step_counts": step_counts,
            "ensemble_size": "not_applicable",
            "seed_policy": "not_applicable",
        },
        "cases": cases,
        "overdamped_support": overdamped_support,
        "overall_classification": aggregate_classifications(
            classifications,
            trend_passed=overdamped_support["passed"],
        ),
        "canonical_artifact_hash_recording": (
            "printed after atomic publication and recorded externally in "
            "artifacts/derived/S-011-free-numerical.md"
        ),
    }


def _atomic_publish_once(path: Path, payload: dict[str, Any]) -> str:
    """Publish complete bytes without overwriting an existing canonical file."""

    if path.exists():
        raise FileExistsError(f"canonical output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        data = _pretty_json_bytes(payload)
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_file(path)


def execute(plan_path: Path) -> tuple[dict[str, Any], str]:
    """Run the frozen plan once and atomically create only its canonical output."""

    if plan_path != PLAN_REL:
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    output = ROOT / OUTPUT_REL
    if output.exists():
        raise FileExistsError(f"canonical output already exists: {OUTPUT_REL.as_posix()}")
    plan = load_preregistered_plan(ROOT / plan_path)
    validate_preregistered_plan(plan)
    source_commit = _clean_source_commit()
    manifest = source_manifest()
    payload = build_result_payload(
        plan,
        source_commit=source_commit,
        manifest=manifest,
    )
    artifact_hash = _atomic_publish_once(output, payload)
    return payload, artifact_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "run"))
    parser.add_argument("plan", type=Path)
    arguments = parser.parse_args()
    if arguments.plan != PLAN_REL:
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    plan = load_preregistered_plan(ROOT / arguments.plan)
    validate_preregistered_plan(plan)
    if arguments.mode == "validate":
        print(f"validated {PLAN_ID}")
        return
    payload, artifact_hash = execute(arguments.plan)
    print(
        f"{payload['overall_classification']} {OUTPUT_REL.as_posix()} "
        f"sha256={artifact_hash}"
    )


if __name__ == "__main__":
    main()
