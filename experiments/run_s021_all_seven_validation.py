"""Frozen, one-shot S-021 all-seven deterministic validation runner.

``validate`` is deliberately non-scientific: it checks locks, source paths,
and import isolation without evaluating the canonical grid or writing output.
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
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

import mpmath as mp

ROOT = Path(__file__).resolve().parents[1]
PLAN_REL = Path("experiments/S-021-all-seven-moment-validation-primary-v1.json")
OUTPUT_REL = Path("artifacts/raw/S-021-all-seven-moment-validation-primary-v1.json")
OPERATOR_REL = Path("experiments/s021_all_seven_operator.py")
ADAPTER_REL = Path("experiments/s021_formula_adapter.py")
PLAN_ID = "S-021-all-seven-moment-validation-primary-v1"
EXPECTED_PLAN_SEMANTIC_SHA256 = "56106349142a6710a6dc32f5af6d76356d132655367020cda6ec4f5cf2198422"
EXPECTED_PLAN_RAW_SHA256 = "c648a3863c85767f43c49a6e315ccf8b599105c3f81c0c5fc4678522f91f1aeb"
SERIALIZED_SIGNIFICANT_DIGITS = 50
PRECISIONS = (50, 80)
SCALED_HORIZONS = ("64", "80")
PROBE_TIMES = ("0", "1/2", "2", "8")
POSITION_PROTOCOLS = ("P", "PV", "PTheta", "PVTheta")
TRANSPORT_PROTOCOLS = ("V", "Theta", "VTheta")
CELL_NAMES = ("dps50_H64", "dps80_H64", "dps50_H80", "dps80_H80")

# Every provenance source named by the frozen plan, plus the three S-021 files.
MANIFEST_PATHS = (
    Path("docs/scientific-contract/CONTRACT.md"),
    Path("docs/scientific-contract/validation_registry.json"),
    Path("docs/scientific-contract/validation_registry.schema.json"),
    Path("artifacts/derived/T-012-complete-reset-baseline.md"),
    Path("artifacts/derived/T-020-position-protocols.md"),
    Path("artifacts/derived/T-021-nonposition-protocols.md"),
    Path("artifacts/derived/T-022-formula-registry.md"),
    Path("artifacts/derived/S-020-protocol-registry.md"),
    Path("src/phasemap/theory/complete_reset_baseline.py"),
    Path("src/phasemap/theory/formula_registry.py"),
    Path("src/phasemap/theory/position_protocols.py"),
    Path("src/phasemap/theory/nonposition_protocols.py"),
    PLAN_REL, OPERATOR_REL, ADAPTER_REL,
    Path("experiments/run_s021_all_seven_validation.py"),
    Path("tests/integration/test_s021_all_seven_validation.py"),
)
FORBIDDEN_IMPORT_PREFIXES = ("phasemap.theory", "phasemap.simulation")
FORBIDDEN_ARTIFACT_MARKERS = ("artifacts/raw/S-011", "artifacts/raw/S-012", "artifacts/raw/S-021")


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
        for key, item in value.items(): _reject_nonfinite_tree(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value): _reject_nonfinite_tree(item, f"{path}[{index}]")


def _semantic_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def load_preregistered_plan(path: Path) -> dict[str, Any]:
    if path != ROOT / PLAN_REL:
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid S-021 plan JSON") from exc
    if not isinstance(plan, dict):
        raise ValueError("S-021 plan root must be an object")
    _reject_nonfinite_tree(plan)
    return plan


def validate_preregistered_plan(plan: Mapping[str, Any]) -> None:
    if _sha256_bytes(_semantic_bytes(plan)) != EXPECTED_PLAN_SEMANTIC_SHA256:
        raise ValueError("invalid S-021 plan: semantic lock mismatch")
    if _sha256_file(ROOT / PLAN_REL) != EXPECTED_PLAN_RAW_SHA256:
        raise ValueError("invalid S-021 plan: raw lock mismatch")
    if plan.get("plan_id") != PLAN_ID or plan.get("canonical_output") != OUTPUT_REL.as_posix():
        raise ValueError("invalid S-021 plan identity")
    grid = plan.get("parameter_grid", {})
    if tuple(grid.get("all_protocols", ())) != POSITION_PROTOCOLS[:1] + TRANSPORT_PROTOCOLS[:2] + POSITION_PROTOCOLS[1:2] + POSITION_PROTOCOLS[2:3] + TRANSPORT_PROTOCOLS[2:] + POSITION_PROTOCOLS[3:]:
        raise ValueError("invalid S-021 protocol order")
    if len(grid.get("cases", ())) != 13 or tuple(plan.get("numerical_schedule", {}).get("arithmetic_precisions_decimal_digits", ())) != PRECISIONS:
        raise ValueError("invalid S-021 grid or precision schedule")


def _decimal(value: Any) -> str:
    # An mpf retains the precision at which it was created. Reconstructing it
    # through mp.mpf under the caller's (possibly default 15-digit) context
    # silently discards those retained bits before publication.
    if isinstance(value, mp.mpf):
        numeric = value
    else:
        with mp.workdps(
            max(mp.mp.dps, SERIALIZED_SIGNIFICANT_DIGITS + 10)
        ):
            numeric = mp.mpf(value)
    if not mp.isfinite(numeric): raise ValueError("scientific value is nonfinite")
    return mp.nstr(numeric, SERIALIZED_SIGNIFICANT_DIGITS, strip_zeros=False)


def _serial(value: Any) -> Any:
    if isinstance(value, mp.mpf): return _decimal(value)
    if isinstance(value, mp.matrix): return [[_decimal(value[i, j]) for j in range(value.cols)] for i in range(value.rows)]
    if isinstance(value, Mapping): return {str(key): _serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_serial(item) for item in value]
    if isinstance(value, float): return _decimal(value)
    return value


def _imports_and_literals(path: Path) -> tuple[set[str], str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module)
    return imports, text


def audit_isolation() -> dict[str, Any]:
    operator_imports, operator_text = _imports_and_literals(ROOT / OPERATOR_REL)
    if any(name.startswith(FORBIDDEN_IMPORT_PREFIXES) for name in operator_imports):
        raise ValueError("operator imports forbidden PHASEMAP module")
    if any(marker in operator_text for marker in FORBIDDEN_ARTIFACT_MARKERS):
        raise ValueError("operator contains forbidden result-artifact marker")
    if "open(" in operator_text or "Path(" in operator_text:
        raise ValueError("operator must not perform file access")
    return {"operator_imports": sorted(operator_imports), "operator_file_access": False, "status": "validated"}


def source_manifest() -> dict[str, str]:
    missing = [path.as_posix() for path in MANIFEST_PATHS if not (ROOT / path).is_file()]
    if missing: raise FileNotFoundError(f"required source manifest path missing: {missing}")
    return {path.as_posix(): _sha256_file(ROOT / path) for path in MANIFEST_PATHS}


def _clean_source_commit() -> str:
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    if status.strip(): raise RuntimeError("clean committed source is required")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    if len(commit) != 40: raise RuntimeError("Git did not return a full source commit")
    return commit


def _atomic_publish_once(path: Path, payload: dict[str, Any]) -> str:
    if path.exists(): raise FileExistsError(f"canonical output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(_pretty_bytes(_serial(payload))); handle.flush(); os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_file(path)


def classify(*, cell_errors: Sequence[mp.mpf], precision: Sequence[mp.mpf], horizon: Sequence[mp.mpf], algebraic: Sequence[mp.mpf], invariants: Sequence[mp.mpf], residuals: Sequence[mp.mpf], tolerance: Any = "1e-12", residual_tolerance: Any = "1e-30") -> str:
    tol, rtol = mp.mpf(tolerance), mp.mpf(residual_tolerance)
    converged = all(value <= tol for value in (*precision, *horizon, *algebraic, *invariants)) and all(value <= rtol for value in residuals)
    if converged and cell_errors and all(value > tol for value in cell_errors): return "contradicted"
    if converged and all(value <= tol for value in cell_errors): return "validated"
    return "unresolved"


def _load_module(name: str, relative: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None: raise ImportError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def _max_difference(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, mp.mpf]:
    if tuple(left) != tuple(right): raise ValueError("formula keys differ")
    result: dict[str, mp.mpf] = {}
    for key in left:
        if left[key] is None and right[key] is None: continue
        if left[key] is None or right[key] is None: raise ValueError(f"null mismatch for {key}")
        result[key] = abs(left[key] - right[key])
    return result


def _invariant_discrepancies(operator: Any, state: mp.matrix) -> dict[str, mp.mpf]:
    blocks = operator.state_blocks(state)
    values = {"one": abs(blocks["one"] - 1), "orientation_norm": abs(blocks["U"][0, 0] + blocks["U"][1, 1] - 1)}
    for name in operator.SYMMETRY_ZERO_NAMES: values[f"symmetry.{name}"] = abs(state[operator.INDEX[name]])
    return values


def _cell_specs() -> tuple[tuple[int, str, str], ...]:
    return (
        (50, "64", "dps50_H64"),
        (80, "64", "dps80_H64"),
        (50, "80", "dps50_H80"),
        (80, "80", "dps80_H80"),
    )


def _isolated_case(
    plan_case: Mapping[str, str],
    protocol: str,
    operator: Any,
) -> dict[str, Any]:
    """Compute one case without importing or consulting the formula adapter."""

    M, Pe, rho = plan_case["M"], plan_case["Pe"], plan_case["rho"]
    cells: dict[str, Any] = {}
    for dps, H, label in _cell_specs():
        with mp.workdps(dps):
            A = operator.build_operator(protocol, M, Pe, rho)
            time = operator.scaled_horizon(protocol, M, rho, H)
            propagated = operator.propagate(A, operator.initial_state(), time)
            probes: dict[str, Any] = {}
            if protocol in POSITION_PROTOCOLS:
                algebraic_state = operator.solve_position_stationary(A)
                probes["stationary"] = {
                    "fields": operator.flatten_formula_fields(
                        operator.stationary_formula_fields(propagated)
                    ),
                    "algebraic_fields": operator.flatten_formula_fields(
                        operator.stationary_formula_fields(algebraic_state)
                    ),
                }
                residuals = {
                    "stationary": operator.stationary_residual(
                        A, algebraic_state
                    )
                }
            else:
                solution = operator.solve_transport_polynomial(A)
                extraction = operator.extract_transport_refinement(
                    A, propagated, time, solution
                )
                for probe in PROBE_TIMES:
                    probes[probe] = {
                        "fields": operator.flatten_formula_fields(
                            operator.reconstruct_transport_formula_fields(
                                extraction, probe
                            )
                        ),
                        "algebraic_fields": operator.flatten_formula_fields(
                            operator.reconstruct_transport_formula_fields(
                                solution, probe
                            )
                        ),
                    }
                residuals = operator.transport_polynomial_residuals(
                    A, solution, PROBE_TIMES
                )
            cells[label] = {
                "dps": dps,
                "scaled_H": H,
                "time": time,
                "probes": probes,
                "invariants": _invariant_discrepancies(operator, propagated),
                "residuals": residuals,
                "operator_matrix_sha256": _sha256_bytes(
                    _semantic_bytes(_serial(A))
                ),
            }
    return {
        "case": dict(plan_case),
        "protocol": protocol,
        "cells": cells,
    }


def _row_classification(
    cells: Mapping[str, Any],
    probe: str,
    key: str,
    reference: mp.mpf,
) -> dict[str, Any]:
    values = {
        label: cells[label]["probes"][probe]["fields"][key]
        for label in CELL_NAMES
    }
    algebraic_value = cells["dps80_H80"]["probes"][probe][
        "algebraic_fields"
    ][key]
    if any(value is None for value in values.values()) or algebraic_value is None:
        raise ValueError(f"unexpected null comparison row {probe}:{key}")
    cell_errors = {
        label: abs(value - reference) for label, value in values.items()
    }
    precision = {
        "H64": abs(values["dps80_H64"] - values["dps50_H64"]),
        "H80": abs(values["dps80_H80"] - values["dps50_H80"]),
    }
    horizon = {
        "dps50": abs(values["dps50_H80"] - values["dps50_H64"]),
        "dps80": abs(values["dps80_H80"] - values["dps80_H64"]),
    }
    algebraic = abs(values["dps80_H80"] - algebraic_value)
    outcome = classify(
        cell_errors=list(cell_errors.values()),
        precision=list(precision.values()),
        horizon=list(horizon.values()),
        algebraic=[algebraic],
        invariants=(),
        residuals=(),
    )
    return {
        "reference": reference,
        "cells": values,
        "cell_errors": cell_errors,
        "precision_differences": precision,
        "horizon_differences": horizon,
        "finest_algebraic_cross_check": algebraic,
        "classification": outcome,
    }


def _aggregate_classifications(values: Sequence[str]) -> str:
    if not values:
        raise ValueError("no classifications to aggregate")
    if "contradicted" in values:
        return "contradicted"
    if all(value == "validated" for value in values):
        return "validated"
    if all(value in {"validated", "unresolved"} for value in values):
        return "unresolved"
    raise ValueError(f"invalid classification set: {values}")


def _attach_formula_evidence(
    record: dict[str, Any],
    adapter: Any,
    reference_cache: dict[tuple[str, str, str, str, str | None], Any],
) -> None:
    protocol = record["protocol"]
    case = record["case"]
    probe_names = ("stationary",) if protocol in POSITION_PROTOCOLS else PROBE_TIMES
    formula_rows: dict[str, Any] = {}
    for probe in probe_names:
        reference_probe = None if probe == "stationary" else probe
        cache_key = (
            protocol,
            case["M"],
            case["Pe"],
            case["rho"],
            reference_probe,
        )
        if cache_key not in reference_cache:
            reference_cache[cache_key] = adapter.t022_reference(
                protocol,
                case["M"],
                case["Pe"],
                case["rho"],
                reference_probe,
                100,
            )
        reference = reference_cache[cache_key]
        for label in CELL_NAMES:
            fields = record["cells"][label]["probes"][probe]["fields"]
            if tuple(fields) != tuple(reference):
                raise ValueError("operator/reference flattened keys differ")
        for key, value in reference.items():
            if value is None:
                if any(
                    record["cells"][label]["probes"][probe]["fields"][key]
                    is not None
                    for label in CELL_NAMES
                ):
                    raise ValueError(f"null mismatch for {probe}:{key}")
                continue
            row_id = f"{probe}:{key}"
            formula_rows[row_id] = _row_classification(
                record["cells"], probe, key, value
            )

    tolerance = mp.mpf("1e-12")
    invariant_values = [
        value
        for label in CELL_NAMES
        for value in record["cells"][label]["invariants"].values()
    ]
    finest_residuals = list(
        record["cells"]["dps80_H80"]["residuals"].values()
    )
    residual_tolerance = (
        mp.mpf("1e-40")
        if protocol in POSITION_PROTOCOLS
        else mp.mpf("1e-30")
    )
    numeric_gate = (
        "validated"
        if all(value <= tolerance for value in invariant_values)
        and all(value <= residual_tolerance for value in finest_residuals)
        else "unresolved"
    )
    record["formula_rows"] = formula_rows
    record["numeric_gate"] = {
        "all_cell_invariant_discrepancies": invariant_values,
        "finest_residuals": record["cells"]["dps80_H80"]["residuals"],
        "residual_tolerance": residual_tolerance,
        "classification": numeric_gate,
    }

    classifications = [
        row["classification"] for row in formula_rows.values()
    ] + [numeric_gate]

    if protocol == "PVTheta":
        t012_reference = adapter.t012_reference(
            case["M"], case["Pe"], case["rho"], 100
        )
        t012_rows: dict[str, Any] = {}
        for key, value in t012_reference.items():
            if value is None:
                continue
            t012_rows[key] = _row_classification(
                record["cells"], "stationary", key, value
            )
        t012_classification = _aggregate_classifications(
            [row["classification"] for row in t012_rows.values()]
        )
        record["t012_gate"] = {
            "rows": t012_rows,
            "classification": t012_classification,
        }
        classifications.append(t012_classification)

    record["classification"] = _aggregate_classifications(classifications)


def _finest_value(
    by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    protocol: str,
    case_id: str,
    field: str,
    *,
    probe: str | None = None,
) -> mp.mpf:
    record = by_key[(protocol, case_id)]
    selected_probe = (
        "stationary"
        if protocol in POSITION_PROTOCOLS
        else ("0" if probe is None else probe)
    )
    value = record["cells"]["dps80_H80"]["probes"][selected_probe][
        "fields"
    ][field]
    if value is None:
        raise ValueError(f"inapplicable limit field {protocol}:{field}")
    return value


def _strictly_decreasing(discrepancies: Sequence[mp.mpf]) -> bool:
    return bool(discrepancies) and all(
        left > right
        for left, right in zip(discrepancies[:-1], discrepancies[1:])
    )


def _strict_or_numerical_identity(
    discrepancies: Sequence[mp.mpf],
) -> bool:
    """Allow only a high-precision representation of an exact-zero identity."""

    if discrepancies and all(value <= mp.mpf("1e-40") for value in discrepancies):
        return True
    return _strictly_decreasing(discrepancies)


def _limit_outcome(
    underlying: Sequence[str],
    conditions_pass: bool,
) -> str:
    if "contradicted" in underlying:
        return "contradicted"
    if all(value == "validated" for value in underlying) and conditions_pass:
        return "validated"
    return "unresolved"


def _translational_keys(fields: Mapping[str, Any]) -> tuple[str, ...]:
    excluded_prefixes = (
        "u_bar",
        "U[",
        "W[",
        "Q[",
        "Q_centered[",
        "Sigma_u[",
        "K[",
        "raw_ru_linear[",
    )
    return tuple(
        key
        for key, value in fields.items()
        if value is not None
        and not any(key == prefix or key.startswith(prefix) for prefix in excluded_prefixes)
    )


def _limit_records(
    plan: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    operator: Any,
) -> dict[str, Any]:
    by_key = {
        (record["protocol"], record["case"]["id"]): record
        for record in records
    }
    rules = plan["mandatory_limit_checks"]
    tolerance = mp.mpf("1e-12")
    groups: dict[str, Any] = {}

    complete_rows = [
        by_key[("PVTheta", case_id)]
        for case_id in rules["complete_reset"]["cases"]
    ]
    complete_underlying = [row["classification"] for row in complete_rows]
    complete_t012 = [
        row["t012_gate"]["classification"] for row in complete_rows
    ]
    groups["complete_reset"] = {
        "rule": rules["complete_reset"],
        "underlying_classifications": complete_underlying,
        "t012_classifications": complete_t012,
        "classification": _limit_outcome(
            complete_underlying,
            all(value == "validated" for value in complete_t012),
        ),
    }

    passive_ids = (
        "active-rho-1",
        "passive-approach-pe-3-5",
        "passive-approach-pe-3-10",
        "passive",
    )
    passive_sequences: dict[str, Any] = {}
    passive_underlying: list[str] = []
    for protocol in plan["parameter_grid"]["all_protocols"]:
        rows = [by_key[(protocol, case_id)] for case_id in passive_ids]
        passive_underlying.extend(row["classification"] for row in rows)
        M = operator.parse_rational(rows[-1]["case"]["M"])
        rho = operator.parse_rational(rows[-1]["case"]["rho"])
        if protocol in ("P", "PTheta"):
            target = 4 / (rho * (1 + M * rho))
            field = "raw_MSD"
        elif protocol in ("PV", "PVTheta"):
            target = 8 / (rho * (1 + M * rho) * (2 + M * rho))
            field = "raw_MSD"
        elif protocol == "Theta":
            target = mp.mpf(1)
            field = "D_eff"
        else:
            target = 2 / ((1 + M * rho) * (2 + M * rho))
            field = "D_eff"
        values = [
            _finest_value(by_key, protocol, case_id, field)
            for case_id in passive_ids
        ]
        discrepancies = [abs(value - target) for value in values]
        passive_sequences[protocol] = {
            "field": field,
            "target": target,
            "values": values,
            "absolute_discrepancies": discrepancies,
            "strictly_decreasing_to_zero": (
                _strictly_decreasing(discrepancies)
                and discrepancies[-1] <= tolerance
            ),
        }

    passive_pair_differences: dict[str, Any] = {}
    for left, right in (("P", "PTheta"), ("PV", "PVTheta"), ("V", "VTheta")):
        left_record = by_key[(left, "passive")]
        right_record = by_key[(right, "passive")]
        left_probe = "stationary" if left in POSITION_PROTOCOLS else "0"
        right_probe = "stationary" if right in POSITION_PROTOCOLS else "0"
        left_fields = left_record["cells"]["dps80_H80"]["probes"][left_probe][
            "fields"
        ]
        right_fields = right_record["cells"]["dps80_H80"]["probes"][right_probe][
            "fields"
        ]
        keys = sorted(
            set(_translational_keys(left_fields))
            & set(_translational_keys(right_fields))
        )
        differences = {
            key: abs(left_fields[key] - right_fields[key]) for key in keys
        }
        passive_pair_differences[f"{left}={right}"] = differences
    passive_conditions = all(
        item["strictly_decreasing_to_zero"]
        for item in passive_sequences.values()
    ) and all(
        value <= tolerance
        for differences in passive_pair_differences.values()
        for value in differences.values()
    )
    groups["passive"] = {
        "rule": rules["passive"],
        "sequences": passive_sequences,
        "endpoint_pair_differences": passive_pair_differences,
        "underlying_classifications": passive_underlying,
        "classification": _limit_outcome(
            passive_underlying, passive_conditions
        ),
    }

    rare_ids = ("active-rho-1", "active-rho-1-2", "active-rho-1-4")
    rare_sequences: dict[str, Any] = {}
    rare_underlying: list[str] = []
    for protocol in plan["parameter_grid"]["all_protocols"]:
        rows = [by_key[(protocol, case_id)] for case_id in rare_ids]
        rare_underlying.extend(row["classification"] for row in rows)
        M = operator.parse_rational(rows[0]["case"]["M"])
        Pe = operator.parse_rational(rows[0]["case"]["Pe"])
        if protocol in POSITION_PROTOCOLS:
            values = [
                operator.parse_rational(row["case"]["rho"])
                * _finest_value(by_key, protocol, row["case"]["id"], "raw_MSD")
                for row in rows
            ]
            target = 4 + 2 * Pe**2
            series = {"rho*raw_MSD": [abs(value - target) for value in values]}
        else:
            d_values = [
                _finest_value(by_key, protocol, row["case"]["id"], "D_eff")
                for row in rows
            ]
            b_values = [
                _finest_value(by_key, protocol, row["case"]["id"], "b[0]")
                for row in rows
            ]
            series = {
                "D_eff": [abs(value - (1 + Pe**2 / 2)) for value in d_values],
                "b_x": [abs(value - Pe) for value in b_values],
            }
        rare_sequences[protocol] = {
            name: {
                "absolute_discrepancies": values,
                "trend_passed": _strict_or_numerical_identity(values),
            }
            for name, values in series.items()
        }
    rare_conditions = all(
        series["trend_passed"]
        for protocol in rare_sequences.values()
        for series in protocol.values()
    )
    groups["rare_reset"] = {
        "rule": rules["rare_reset"],
        "sequences": rare_sequences,
        "underlying_classifications": rare_underlying,
        "classification": _limit_outcome(rare_underlying, rare_conditions),
    }

    frequent_ids = ("active-rho-1", "active-rho-2", "active-rho-4")
    frequent_sequences: dict[str, Any] = {}
    frequent_underlying: list[str] = []
    for protocol in plan["parameter_grid"]["all_protocols"]:
        rows = [by_key[(protocol, case_id)] for case_id in frequent_ids]
        frequent_underlying.extend(row["classification"] for row in rows)
        M = operator.parse_rational(rows[0]["case"]["M"])
        Pe = operator.parse_rational(rows[0]["case"]["Pe"])
        rhos = [operator.parse_rational(row["case"]["rho"]) for row in rows]
        if protocol == "P":
            values = [
                rho**2
                * _finest_value(by_key, protocol, row["case"]["id"], "raw_MSD")
                for rho, row in zip(rhos, rows)
            ]
            series = {"rho^2*raw_MSD": [abs(v - (4 / M + 2 * Pe**2 / (1 + M))) for v in values]}
        elif protocol == "PTheta":
            values = [
                rho**2
                * _finest_value(by_key, protocol, row["case"]["id"], "raw_MSD")
                for rho, row in zip(rhos, rows)
            ]
            series = {"rho^2*raw_MSD": [abs(v - (4 / M + 2 * Pe**2)) for v in values]}
        elif protocol in ("PV", "PVTheta"):
            values = [
                rho**3
                * _finest_value(by_key, protocol, row["case"]["id"], "raw_MSD")
                for rho, row in zip(rhos, rows)
            ]
            series = {"rho^3*raw_MSD": [abs(v - 8 / M**2) for v in values]}
        elif protocol == "V":
            values = [
                rho**2
                * _finest_value(by_key, protocol, row["case"]["id"], "D_eff")
                for rho, row in zip(rhos, rows)
            ]
            series = {"rho^2*D_eff": [abs(v - (Pe**2 + 4) / (2 * M**2)) for v in values]}
        elif protocol == "Theta":
            d_values = [
                _finest_value(by_key, protocol, row["case"]["id"], "D_eff")
                for row in rows
            ]
            v_values = [
                _finest_value(by_key, protocol, row["case"]["id"], "v_bar[0]")
                for row in rows
            ]
            series = {
                "D_eff": [abs(v - 1) for v in d_values],
                "v_bar_x": [abs(v - Pe) for v in v_values],
            }
        else:
            d_values = [
                rho**2
                * _finest_value(by_key, protocol, row["case"]["id"], "D_eff")
                for rho, row in zip(rhos, rows)
            ]
            v_values = [
                rho
                * _finest_value(
                    by_key, protocol, row["case"]["id"], "v_bar[0]"
                )
                for rho, row in zip(rhos, rows)
            ]
            series = {
                "rho^2*D_eff": [abs(v - 2 / M**2) for v in d_values],
                "rho*v_bar_x": [abs(v - Pe / M) for v in v_values],
            }
        frequent_sequences[protocol] = {
            name: {
                "absolute_discrepancies": values,
                "trend_passed": _strictly_decreasing(values),
            }
            for name, values in series.items()
        }
    frequent_conditions = all(
        series["trend_passed"]
        for protocol in frequent_sequences.values()
        for series in protocol.values()
    )
    groups["frequent_reset"] = {
        "rule": rules["frequent_reset"],
        "sequences": frequent_sequences,
        "underlying_classifications": frequent_underlying,
        "classification": _limit_outcome(
            frequent_underlying, frequent_conditions
        ),
    }

    resonance_rows = [
        by_key[(protocol, case_id)]
        for protocol in plan["parameter_grid"]["all_protocols"]
        for case_id in ("resonance", "above-resonance")
    ]
    resonance_underlying = [row["classification"] for row in resonance_rows]
    groups["resonance"] = {
        "rule": rules["resonance"],
        "underlying_classifications": resonance_underlying,
        "classification": _limit_outcome(resonance_underlying, True),
    }

    overdamped_ids = ("overdamped-1-4", "overdamped-1-16", "overdamped-1-64")
    overdamped_sequences: dict[str, Any] = {}
    overdamped_underlying: list[str] = []
    for protocol in plan["parameter_grid"]["all_protocols"]:
        rows = [by_key[(protocol, case_id)] for case_id in overdamped_ids]
        overdamped_underlying.extend(row["classification"] for row in rows)
        Pe = operator.parse_rational(rows[0]["case"]["Pe"])
        rho = operator.parse_rational(rows[0]["case"]["rho"])
        if protocol in POSITION_PROTOCOLS:
            raw_target = 4 / rho + 2 * Pe**2 / (rho * (rho + 1))
            centered_target = raw_target
            if protocol in ("PTheta", "PVTheta"):
                centered_target -= (Pe / (rho + 1)) ** 2
            series = {
                "raw_MSD": [
                    abs(
                        _finest_value(
                            by_key, protocol, row["case"]["id"], "raw_MSD"
                        )
                        - raw_target
                    )
                    for row in rows
                ],
                "centered_variance": [
                    abs(
                        _finest_value(
                            by_key,
                            protocol,
                            row["case"]["id"],
                            "centered_variance",
                        )
                        - centered_target
                    )
                    for row in rows
                ],
            }
        else:
            if protocol == "V":
                target = 1 + Pe**2 / 2
            else:
                sigma_trace = 1 - (rho / (rho + 1)) ** 2
                target = 1 + Pe**2 * sigma_trace / (2 * (1 + rho))
            series = {
                "D_eff": [
                    abs(
                        _finest_value(
                            by_key, protocol, row["case"]["id"], "D_eff"
                        )
                        - target
                    )
                    for row in rows
                ]
            }
        overdamped_sequences[protocol] = {
            name: {
                "absolute_discrepancies": values,
                "trend_passed": _strict_or_numerical_identity(values),
            }
            for name, values in series.items()
        }
    overdamped_conditions = all(
        series["trend_passed"]
        for protocol in overdamped_sequences.values()
        for series in protocol.values()
    )
    groups["strict_overdamped_trend"] = {
        "rule": rules["strict_overdamped_trend"],
        "sequences": overdamped_sequences,
        "underlying_classifications": overdamped_underlying,
        "classification": _limit_outcome(
            overdamped_underlying, overdamped_conditions
        ),
    }
    if tuple(groups) != tuple(rules):
        raise ValueError("mandatory limit record set differs from frozen plan")
    return groups


def build_result_payload(
    plan: Mapping[str, Any],
    *,
    source_commit: str,
    manifest: Mapping[str, str],
) -> dict[str, Any]:
    """Compute independent outputs first, then load references and classify."""

    operator = _load_module("s021_operator_canonical", OPERATOR_REL)
    records = [
        _isolated_case(case, protocol, operator)
        for protocol in plan["parameter_grid"]["all_protocols"]
        for case in plan["parameter_grid"]["cases"]
    ]

    # This dynamic import occurs only after every isolated numerical output,
    # algebraic solution, invariant, residual, and matrix hash is frozen.
    adapter = _load_module("s021_formula_adapter_canonical", ADAPTER_REL)
    reference_cache: dict[
        tuple[str, str, str, str, str | None], Any
    ] = {}
    with mp.workdps(100):
        for record in records:
            _attach_formula_evidence(record, adapter, reference_cache)
        limits = _limit_records(plan, records, operator)
    classifications = [
        record["classification"] for record in records
    ] + [item["classification"] for item in limits.values()]
    overall = _aggregate_classifications(classifications)
    provenance_hashes = {
        path.as_posix(): digest for path, digest in (
            (path, manifest[path.as_posix()]) for path in MANIFEST_PATHS
        )
    }
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": "S-021",
        "status": "completed",
        "evidence_role": "independent_implementation_path_numerical_support",
        "plan_id": PLAN_ID,
        "contract_version": plan["contract_version"],
        "validation_registry_schema_version": plan[
            "validation_registry_schema_version"
        ],
        "formula_registry_schema_version": plan[
            "formula_registry_schema_version"
        ],
        "canonical_output": OUTPUT_REL.as_posix(),
        "provenance": {
            "clean_source_commit": source_commit,
            "source_manifest": dict(manifest),
            "provenance_hashes": provenance_hashes,
            "plan_hash": EXPECTED_PLAN_RAW_SHA256,
            "plan_semantic_hash": EXPECTED_PLAN_SEMANTIC_SHA256,
            "operator_module_hash": _sha256_file(ROOT / OPERATOR_REL),
            "comparison_adapter_hash": _sha256_file(ROOT / ADAPTER_REL),
            "runner_hash": _sha256_file(Path(__file__)),
            "test_hash": manifest[
                "tests/integration/test_s021_all_seven_validation.py"
            ],
            "python_version": sys.version,
            "mpmath_version": mp.__version__,
            "sympy_version": adapter.sp.__version__,
            "operating_system": platform.platform(),
            "machine_architecture": platform.machine(),
        },
        "configuration": {
            "basis_names": list(operator.BASIS_NAMES),
            "locked_reset_maps": dict(operator.PROTOCOL_FLAGS),
            "parameter_grid": plan["parameter_grid"],
            "arithmetic_precisions": list(PRECISIONS),
            "scaled_horizons": list(SCALED_HORIZONS),
            "transport_probe_times": list(PROBE_TIMES),
            "scientific_serialization": (
                "finite decimal strings with 50 significant digits"
            ),
        },
        "claim_boundary": plan["scope"],
        "isolation_audit": audit_isolation(),
        "cases": records,
        "limit_records": limits,
        "overall_classification": overall,
        "canonical_artifact_hash_recording": {
            "actual_file_sha256": (
                "returned after atomic publication and recorded in the "
                "S-021 acceptance artifact/commit"
            ),
            "self_hash_note": "the byte hash cannot be embedded in the bytes it hashes",
        },
    }
    payload["canonical_payload_sha256"] = {
        "definition": (
            "SHA-256 of canonical sorted-key serialized semantics before "
            "this field"
        ),
        "sha256": _sha256_bytes(_semantic_bytes(_serial(payload))),
    }
    return payload


def build_synthetic_payload() -> dict[str, Any]:
    """Return a result-free fixture for payload and serialization tests."""

    return {
        "synthetic": True,
        "canonical_grid_evaluated": False,
        "plan_id": PLAN_ID,
        "scientific_value": mp.mpf("1.25"),
    }


def execute(plan_path: Path) -> tuple[dict[str, Any], str]:
    if plan_path != PLAN_REL: raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    if (ROOT / OUTPUT_REL).exists(): raise FileExistsError(f"canonical output already exists: {OUTPUT_REL.as_posix()}")
    plan = load_preregistered_plan(ROOT / plan_path); validate_preregistered_plan(plan); audit_isolation()
    commit, manifest = _clean_source_commit(), source_manifest()
    payload = build_result_payload(plan, source_commit=commit, manifest=manifest)
    if _clean_source_commit() != commit or source_manifest() != manifest: raise RuntimeError("source changed during canonical calculation")
    return payload, _atomic_publish_once(ROOT / OUTPUT_REL, payload)


def validate() -> dict[str, Any]:
    plan = load_preregistered_plan(ROOT / PLAN_REL); validate_preregistered_plan(plan)
    isolation = audit_isolation(); manifest = source_manifest()
    _load_module("s021_operator_validation", OPERATOR_REL)
    adapter = _load_module("s021_adapter_validation", ADAPTER_REL)
    self_check = adapter.reference_self_check()
    return {
        "plan_id": PLAN_ID,
        "plan_raw_sha256": EXPECTED_PLAN_RAW_SHA256,
        "manifest_entries": len(manifest),
        "isolation": isolation,
        "reference_self_check": self_check,
        "status": "validated",
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=("validate", "run")); parser.add_argument("plan", type=Path, nargs="?", default=PLAN_REL)
    arguments = parser.parse_args()
    if arguments.plan != PLAN_REL: raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    if arguments.mode == "validate": print(json.dumps(validate(), sort_keys=True)); return
    _, artifact_hash = execute(arguments.plan)
    print(f"published {OUTPUT_REL.as_posix()} sha256={artifact_hash}")


if __name__ == "__main__": main()
