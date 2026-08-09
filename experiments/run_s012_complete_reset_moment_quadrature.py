"""One-shot executor for the frozen S-012 deterministic moment quadrature."""

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
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import mpmath as mp
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from phasemap.simulation.complete_reset_moment_quadrature import (  # noqa: E402
    BASIS_NAMES,
    OBSERVABLE_NAMES,
    PASSIVE_BASIS_NAMES,
    SYMMETRY_ZERO_NAMES,
    augmented_quadrature,
    build_augmented_matrix,
    build_free_second_order_matrix,
    build_passive_fourth_matrix,
    build_resolvent_matrix,
    complete_reset_initial_state,
    extract_invariants,
    extract_second_order_observables,
    map_state,
    passive_outputs,
    passive_reset_state,
    resolvent_stationary,
    stationary_residual,
)
from phasemap.theory.complete_reset_baseline import (  # noqa: E402
    complete_reset_stationary_second_moments,
    passive_complete_reset_position_fourth_moment,
    source_passive_position_excess_kurtosis,
)


PLAN_ID = "S-012-complete-reset-moment-quadrature-primary-v1"
PLAN_REL = Path(
    "experiments/S-012-complete-reset-moment-quadrature-primary-v1.json"
)
OUTPUT_REL = Path(
    "artifacts/raw/S-012-complete-reset-moment-quadrature-primary-v1.json"
)
EXPECTED_PLAN_SEMANTIC_SHA256 = (
    "42983d3ec78ee46048f3cb5dce58393b05a03771770029be82610e452f619bc5"
)

PRECISIONS = (50, 80)
SCALED_HORIZONS = ("64", "80")
CELL_NAMES = (
    "dps50_rhoT64",
    "dps80_rhoT64",
    "dps50_rhoT80",
    "dps80_rhoT80",
)
COMPARISON_DPS = 90
SERIALIZED_SIGNIFICANT_DIGITS = 50
with mp.workdps(COMPARISON_DPS):
    ABSOLUTE_TOLERANCE = mp.mpf("1e-12")
    FORWARD_ERROR_BOUND = mp.mpf("1e-40")

MANIFEST_PATHS = (
    Path("docs/scientific-contract/CONTRACT.md"),
    Path("docs/scientific-contract/validation_registry.json"),
    Path("docs/scientific-contract/validation_registry.schema.json"),
    Path("artifacts/derived/T-010-generator-scaffold.md"),
    Path("artifacts/derived/T-012-complete-reset-baseline.md"),
    PLAN_REL,
    Path("src/phasemap/simulation/complete_reset_moment_quadrature.py"),
    Path("experiments/run_s012_complete_reset_moment_quadrature.py"),
    Path("src/phasemap/theory/complete_reset_baseline.py"),
    Path("tests/simulation/test_complete_reset_moment_quadrature.py"),
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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_preregistered_plan(path: Path) -> dict[str, Any]:
    if path != ROOT / PLAN_REL:
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("invalid S-012 plan JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("S-012 plan root must be an object")
    _reject_nonfinite_tree(value)
    return value


def validate_preregistered_plan(plan: dict[str, Any]) -> None:
    try:
        semantic_hash = _sha256_bytes(_semantic_bytes(plan))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid S-012 plan: noncanonical value") from exc
    if semantic_hash != EXPECTED_PLAN_SEMANTIC_SHA256:
        raise ValueError("invalid S-012 plan: semantic lock mismatch")
    if (
        plan.get("plan_id") != PLAN_ID
        or plan.get("canonical_output") != OUTPUT_REL.as_posix()
    ):
        raise ValueError("invalid S-012 plan identity")
    if plan["second_order_route"]["basis_names"] != list(BASIS_NAMES):
        raise ValueError("invalid S-012 second-order basis")
    if plan["passive_fourth_route"]["basis_names"] != list(PASSIVE_BASIS_NAMES):
        raise ValueError("invalid S-012 passive basis")
    if plan["regenerative_quadrature"]["resolution_cells"] != list(CELL_NAMES):
        raise ValueError("invalid S-012 quadrature cells")


def _sympy_rational(value: str) -> sp.Rational:
    return sp.Rational(value)


def _mp_expr(value: sp.Expr) -> mp.mpf:
    with mp.workdps(COMPARISON_DPS):
        return mp.mpf(str(sp.N(value, COMPARISON_DPS)))


def _decimal(value: Any) -> str:
    with mp.workdps(COMPARISON_DPS):
        numeric = mp.mpf(value)
        if not mp.isfinite(numeric):
            raise ValueError("scientific value is nonfinite")
        return mp.nstr(
            numeric,
            SERIALIZED_SIGNIFICANT_DIGITS,
            strip_zeros=False,
        )


def _serial(value: Any) -> Any:
    if isinstance(value, mp.mpf):
        return _decimal(value)
    if isinstance(value, mp.matrix):
        if value.cols == 1:
            return [_decimal(value[row]) for row in range(value.rows)]
        return [
            [_decimal(value[row, column]) for column in range(value.cols)]
            for row in range(value.rows)
        ]
    if isinstance(value, dict):
        return {key: _serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serial(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite float")
        return _decimal(value)
    return value


def _matrix_hash(matrix: mp.matrix) -> str:
    return _sha256_bytes(_semantic_bytes(_serial(matrix)))


def _finite(values: Sequence[mp.mpf], label: str) -> None:
    if not all(mp.isfinite(value) for value in values):
        raise ArithmeticError(f"{label} contains a nonfinite value")


def _classify(
    cells: list[mp.mpf],
    reference: mp.mpf,
    precision_differences: list[mp.mpf],
    horizon_differences: list[mp.mpf],
    infinite_horizon_tail: mp.mpf,
    forward_error: mp.mpf,
    tolerance: mp.mpf = ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    _finite(
        [
            *cells,
            reference,
            *precision_differences,
            *horizon_differences,
            infinite_horizon_tail,
            forward_error,
            tolerance,
        ],
        "classification input",
    )
    if tolerance <= 0 or forward_error < 0:
        raise ValueError("classification bounds must be nonnegative")
    errors = [abs(cell - reference) for cell in cells]
    stable = (
        all(
            value <= tolerance
            for value in (
                *precision_differences,
                *horizon_differences,
                infinite_horizon_tail,
            )
        )
        and forward_error <= FORWARD_ERROR_BOUND
    )
    if stable and all(error <= tolerance for error in errors):
        classification = "validated"
    elif stable and all(error > tolerance for error in errors):
        classification = "contradicted"
    else:
        classification = "unresolved"
    return {
        "cell_errors": errors,
        "precision_differences": precision_differences,
        "tail_horizon_differences": horizon_differences,
        "infinite_horizon_tail": infinite_horizon_tail,
        "forward_error_bound": forward_error,
        "classification": classification,
    }


def _convergence_classification(
    precision_differences: list[mp.mpf],
    horizon_differences: list[mp.mpf],
    infinite_horizon_tail: mp.mpf,
    forward_error: mp.mpf,
    tolerance: mp.mpf = ABSOLUTE_TOLERANCE,
) -> str:
    _finite(
        [
            *precision_differences,
            *horizon_differences,
            infinite_horizon_tail,
            forward_error,
        ],
        "convergence input",
    )
    passed = (
        all(
            value <= tolerance
            for value in (
                *precision_differences,
                *horizon_differences,
                infinite_horizon_tail,
            )
        )
        and forward_error <= FORWARD_ERROR_BOUND
    )
    return "validated" if passed else "unresolved"


def _reference_second(case: Mapping[str, str]) -> dict[str, mp.mpf]:
    item = complete_reset_stationary_second_moments(
        _sympy_rational(case["inertia"]),
        _sympy_rational(case["activity"]),
        _sympy_rational(case["reset_rate"]),
    )
    vector = item.as_generator_vector()
    values = {
        name: _mp_expr(vector[index]) for index, name in enumerate(BASIS_NAMES)
    }
    values.update(
        {
            "orientation_mean_x": _mp_expr(item.orientation_mean[0]),
            "mean_velocity_x": _mp_expr(item.velocity_mean[0]),
            "mean_position_x": _mp_expr(item.position_mean[0]),
            "velocity_dot_orientation": _mp_expr(
                sp.trace(item.velocity_orientation)
            ),
            "position_dot_orientation": _mp_expr(
                sp.trace(item.position_orientation)
            ),
            "mean_squared_speed": _mp_expr(item.mean_squared_speed),
            "mean_position_dot_velocity": _mp_expr(
                item.mean_position_dot_velocity
            ),
            "mean_squared_displacement": _mp_expr(
                item.mean_squared_displacement
            ),
            "centered_spatial_variance": _mp_expr(
                item.centered_spatial_variance
            ),
        }
    )
    return values


def _reference_passive(case: Mapping[str, str]) -> dict[str, mp.mpf]:
    inertia = _sympy_rational(case["inertia"])
    reset_rate = _sympy_rational(case["reset_rate"])
    second = _reference_second(case)
    return {
        "raw_E_abs_r_fourth": _mp_expr(
            passive_complete_reset_position_fourth_moment(
                inertia,
                reset_rate,
            )
        ),
        "raw_radial_excess_kurtosis_K": _mp_expr(
            source_passive_position_excess_kurtosis(
                inertia,
                reset_rate,
            )
        ),
        "mean_squared_displacement": second["mean_squared_displacement"],
        "mean_position_dot_velocity": second["mean_position_dot_velocity"],
        "mean_squared_speed": second["mean_squared_speed"],
    }


MatrixFactory = Callable[[], mp.matrix]
ResetFactory = Callable[[], mp.matrix]


def _evaluate_route(
    matrix_factory: MatrixFactory,
    reset_factory: ResetFactory,
    reset_rate: str,
) -> dict[str, Any]:
    states: dict[str, mp.matrix] = {}
    augmented_hashes: dict[str, str] = {}
    residuals: dict[str, mp.mpf] = {}

    for dps in PRECISIONS:
        for horizon in SCALED_HORIZONS:
            cell = f"dps{dps}_rhoT{horizon}"
            with mp.workdps(dps):
                matrix = matrix_factory()
                reset = reset_factory()
                augmented = build_augmented_matrix(matrix, reset_rate)
                state = augmented_quadrature(
                    matrix,
                    reset,
                    reset_rate,
                    dps=dps,
                    rho_times_T=horizon,
                )
                states[cell] = state
                augmented_hashes[cell] = _matrix_hash(augmented)
                residuals[cell] = stationary_residual(
                    matrix,
                    state,
                    reset,
                    reset_rate,
                )

    with mp.workdps(80):
        matrix = matrix_factory()
        reset = reset_factory()
        infinity, condition, normalized_residual = resolvent_stationary(
            matrix,
            reset,
            reset_rate,
            dps=80,
        )
        resolvent_hash = _matrix_hash(
            build_resolvent_matrix(matrix, reset_rate)
        )
        reset_hash = _sha256_bytes(_semantic_bytes(_serial(reset)))

    forward_error = condition * normalized_residual
    _finite(
        [condition, normalized_residual, forward_error, *residuals.values()],
        "route diagnostics",
    )
    if condition <= 0 or normalized_residual < 0 or forward_error < 0:
        raise ArithmeticError("invalid route diagnostics")
    residual_classification = (
        "validated"
        if all(value <= ABSOLUTE_TOLERANCE for value in residuals.values())
        and forward_error <= FORWARD_ERROR_BOUND
        else "unresolved"
    )
    return {
        "states": states,
        "infinity": infinity,
        "augmented_matrix_sha256": augmented_hashes,
        "resolvent_matrix_sha256": resolvent_hash,
        "initial_state_sha256": reset_hash,
        "stationary_residuals": residuals,
        "condition_number": condition,
        "resolvent_normalized_residual": normalized_residual,
        "forward_error_bound": forward_error,
        "stationary_residual_classification": residual_classification,
    }


def _comparison_rows(
    route: Mapping[str, Any],
    extractor: Callable[[mp.matrix], Mapping[str, mp.mpf]],
    references: Mapping[str, mp.mpf],
) -> dict[str, Any]:
    outputs = {
        cell: extractor(state) for cell, state in route["states"].items()
    }
    infinity = extractor(route["infinity"])
    forward_error = route["forward_error_bound"]
    result: dict[str, Any] = {}
    for name, reference in references.items():
        cells = [outputs[cell][name] for cell in CELL_NAMES]
        precision = [
            abs(
                outputs["dps80_rhoT64"][name]
                - outputs["dps50_rhoT64"][name]
            ),
            abs(
                outputs["dps80_rhoT80"][name]
                - outputs["dps50_rhoT80"][name]
            ),
        ]
        horizons = [
            abs(
                outputs["dps50_rhoT80"][name]
                - outputs["dps50_rhoT64"][name]
            ),
            abs(
                outputs["dps80_rhoT80"][name]
                - outputs["dps80_rhoT64"][name]
            ),
        ]
        result[name] = {
            "cells": {cell: outputs[cell][name] for cell in CELL_NAMES},
            "reference": reference,
            **_classify(
                cells,
                reference,
                precision,
                horizons,
                abs(outputs["dps80_rhoT80"][name] - infinity[name]),
                forward_error,
            ),
        }
    return result


def _raw_convergence_rows(
    route: Mapping[str, Any],
    names: tuple[str, ...],
) -> dict[str, Any]:
    outputs = {
        cell: map_state(names, state)
        for cell, state in route["states"].items()
    }
    infinity = map_state(names, route["infinity"])
    result: dict[str, Any] = {}
    for name in names:
        precision = [
            abs(
                outputs["dps80_rhoT64"][name]
                - outputs["dps50_rhoT64"][name]
            ),
            abs(
                outputs["dps80_rhoT80"][name]
                - outputs["dps50_rhoT80"][name]
            ),
        ]
        horizons = [
            abs(
                outputs["dps50_rhoT80"][name]
                - outputs["dps50_rhoT64"][name]
            ),
            abs(
                outputs["dps80_rhoT80"][name]
                - outputs["dps80_rhoT64"][name]
            ),
        ]
        tail = abs(outputs["dps80_rhoT80"][name] - infinity[name])
        result[name] = {
            "cells": {cell: outputs[cell][name] for cell in CELL_NAMES},
            "precision_differences": precision,
            "tail_horizon_differences": horizons,
            "infinite_horizon_tail": tail,
            "forward_error_bound": route["forward_error_bound"],
            "classification": _convergence_classification(
                precision,
                horizons,
                tail,
                route["forward_error_bound"],
            ),
        }
    return result


def _validate_cross_closure(
    passive_rows: Mapping[str, Any],
    second_rows: Mapping[str, Any],
) -> dict[str, Any]:
    differences: dict[str, dict[str, mp.mpf]] = {}
    for name in (
        "mean_squared_displacement",
        "mean_position_dot_velocity",
        "mean_squared_speed",
    ):
        differences[name] = {
            cell: abs(
                passive_rows[name]["cells"][cell]
                - second_rows[name]["cells"][cell]
            )
            for cell in CELL_NAMES
        }
    flat = [
        value for per_output in differences.values() for value in per_output.values()
    ]
    _finite(flat, "passive cross closure")
    if any(value > ABSOLUTE_TOLERANCE for value in flat):
        raise RuntimeError("BL2 passive cross-closure failure")
    return {
        "differences": differences,
        "classification": "validated",
    }


def _case_result(case: Mapping[str, str]) -> dict[str, Any]:
    inertia = case["inertia"]
    activity = case["activity"]
    reset_rate = case["reset_rate"]
    second_route = _evaluate_route(
        lambda: build_free_second_order_matrix(inertia, activity),
        complete_reset_initial_state,
        reset_rate,
    )
    reference = _reference_second(case)
    raw_components = _comparison_rows(
        second_route,
        lambda state: map_state(BASIS_NAMES, state),
        {name: reference[name] for name in BASIS_NAMES},
    )
    observables = _comparison_rows(
        second_route,
        extract_second_order_observables,
        {name: reference[name] for name in OBSERVABLE_NAMES},
    )
    invariants = _comparison_rows(
        second_route,
        extract_invariants,
        {
            "constant": mp.mpf(1),
            "orientation_norm": mp.mpf(1),
            **{name: mp.mpf(0) for name in SYMMETRY_ZERO_NAMES},
        },
    )
    result: dict[str, Any] = {
        "id": case["id"],
        "inertia": inertia,
        "activity": activity,
        "reset_rate": reset_rate,
        "second_order": {
            key: second_route[key]
            for key in (
                "states",
                "augmented_matrix_sha256",
                "resolvent_matrix_sha256",
                "initial_state_sha256",
                "stationary_residuals",
                "condition_number",
                "resolvent_normalized_residual",
                "forward_error_bound",
                "stationary_residual_classification",
            )
        },
    }
    result["second_order"].update(
        {
            "raw_components": raw_components,
            "observables": observables,
            "invariants": invariants,
        }
    )

    if activity == "0":
        passive_route = _evaluate_route(
            lambda: build_passive_fourth_matrix(inertia),
            passive_reset_state,
            reset_rate,
        )
        outputs = _comparison_rows(
            passive_route,
            passive_outputs,
            _reference_passive(case),
        )
        raw_convergence = _raw_convergence_rows(
            passive_route,
            PASSIVE_BASIS_NAMES,
        )
        cross_closure = _validate_cross_closure(outputs, observables)
        result["passive_fourth"] = {
            key: passive_route[key]
            for key in (
                "states",
                "augmented_matrix_sha256",
                "resolvent_matrix_sha256",
                "initial_state_sha256",
                "stationary_residuals",
                "condition_number",
                "resolvent_normalized_residual",
                "forward_error_bound",
                "stationary_residual_classification",
            )
        }
        result["passive_fourth"].update(
            {
                "raw_component_convergence": raw_convergence,
                "outputs": outputs,
                "cross_closure": cross_closure,
            }
        )
    return result


def source_manifest() -> dict[str, str]:
    return {
        path.as_posix(): _sha256_file(ROOT / path) for path in MANIFEST_PATHS
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
        raise RuntimeError("clean committed source is required")
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


def _atomic_publish_once(path: Path, payload: dict[str, Any]) -> str:
    if path.exists():
        raise FileExistsError(f"canonical output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(_pretty_bytes(_serial(payload)))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256_file(path)


def _strictly_decreasing(values: Sequence[mp.mpf]) -> bool:
    return all(left > right for left, right in zip(values[:-1], values[1:]))


def _limit_record(
    *,
    plan_record: Mapping[str, Any],
    approached_limit: str,
    discrepancies: Mapping[str, list[mp.mpf]],
) -> dict[str, Any]:
    passed = all(_strictly_decreasing(values) for values in discrepancies.values())
    return {
        "approached_limit": approached_limit,
        "parameter_sequence": plan_record.get(
            "parameter_sequence",
            plan_record.get("inertia_sequence"),
        ),
        "expected_laws": plan_record["observables_and_expected_laws"],
        "observable_and_evidence_tier": {
            "observables": list(discrepancies),
            "evidence_tier": "deterministic_primary_under_CONTRACT_7.1",
        },
        "estimator_and_uncertainty": plan_record[
            "estimator_and_uncertainty"
        ],
        "observed_absolute_discrepancies": discrepancies,
        "fitting_window_envelope": "not_applicable",
        "discretization_envelope": (
            "precision and exponential-age-tail refinements are gated "
            "separately; no envelope is added"
        ),
        "classification": "validated" if passed else "unresolved",
        "passed": passed,
        "claim": plan_record.get("claim", "finite numerical support only"),
    }


def _limit_records(
    plan: Mapping[str, Any],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    by_id = {case["id"]: case for case in cases}
    cell = "dps80_rhoT80"

    def value(case_id: str, observable: str) -> mp.mpf:
        return by_id[case_id]["second_order"]["observables"][observable][
            "cells"
        ][cell]

    def passive_k(case_id: str) -> mp.mpf:
        return by_id[case_id]["passive_fourth"]["outputs"][
            "raw_radial_excess_kurtosis_K"
        ]["cells"][cell]

    inertia = mp.mpf("0.8")
    activity = mp.mpf("1.2")

    rare_ids = (
        (mp.mpf(1), "active-central", "passive-central"),
        (mp.mpf("0.5"), "active-rho-1-2", "passive-rho-1-2"),
        (mp.mpf("0.25"), "active-rho-1-4", "passive-rho-1-4"),
    )
    rare = {
        "mean_squared_speed": [
            abs(
                value(active_id, "mean_squared_speed")
                - (2 / inertia + activity**2 / (1 + inertia))
            )
            for _, active_id, _ in rare_ids
        ],
        "rho_times_mean_squared_displacement": [
            abs(
                rho * value(active_id, "mean_squared_displacement")
                - 4 * (1 + activity**2 / 2)
            )
            for rho, active_id, _ in rare_ids
        ],
        "passive_raw_radial_excess_kurtosis_K": [
            abs(passive_k(passive_id) - 1)
            for _, _, passive_id in rare_ids
        ],
    }

    frequent_ids = (
        (mp.mpf(1), "active-central", "passive-central"),
        (mp.mpf(2), "active-rho-2", "passive-rho-2"),
        (mp.mpf(4), "active-rho-4", "passive-rho-4"),
    )
    frequent = {
        "rho_times_mean_squared_speed": [
            abs(
                rho * value(active_id, "mean_squared_speed")
                - 4 / inertia**2
            )
            for rho, active_id, _ in frequent_ids
        ],
        "rho_cubed_times_mean_squared_displacement": [
            abs(
                rho**3 * value(active_id, "mean_squared_displacement")
                - 8 / inertia**2
            )
            for rho, active_id, _ in frequent_ids
        ],
        "passive_raw_radial_excess_kurtosis_K": [
            abs(passive_k(passive_id) - 19)
            for _, _, passive_id in frequent_ids
        ],
    }

    overdamped_ids = (
        ("overdamped-support-1",),
        ("overdamped-support-2",),
        ("overdamped-support-3",),
    )
    target_x = activity / 2
    target_msd = 4 + activity**2
    overdamped = {
        "mean_position_x": [
            abs(value(case_id, "mean_position_x") - target_x)
            for (case_id,) in overdamped_ids
        ],
        "mean_squared_displacement": [
            abs(value(case_id, "mean_squared_displacement") - target_msd)
            for (case_id,) in overdamped_ids
        ],
        "centered_spatial_variance": [
            abs(
                value(case_id, "centered_spatial_variance")
                - (target_msd - target_x**2)
            )
            for (case_id,) in overdamped_ids
        ],
    }

    configurations = plan["limit_regressions"]
    return {
        "rare_reset": {
            "cell": cell,
            **_limit_record(
                plan_record=configurations["rare_reset"],
                approached_limit="rho -> 0+",
                discrepancies=rare,
            ),
        },
        "frequent_reset": {
            "cell": cell,
            **_limit_record(
                plan_record=configurations["frequent_reset"],
                approached_limit="rho -> infinity",
                discrepancies=frequent,
            ),
        },
        "overdamped_position_support": {
            "cell": cell,
            **_limit_record(
                plan_record=configurations["overdamped_position_support"],
                approached_limit="M -> 0+ position-process limit",
                discrepancies=overdamped,
            ),
        },
    }


def _case_classifications(case: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    second = case["second_order"]
    result.append(second["stationary_residual_classification"])
    for group in ("raw_components", "observables", "invariants"):
        result.extend(row["classification"] for row in second[group].values())
    passive = case.get("passive_fourth")
    if passive is not None:
        result.append(passive["stationary_residual_classification"])
        result.extend(
            row["classification"]
            for row in passive["raw_component_convergence"].values()
        )
        result.extend(
            row["classification"] for row in passive["outputs"].values()
        )
        result.append(passive["cross_closure"]["classification"])
    return result


def build_result_payload(
    plan: dict[str, Any],
    *,
    source_commit: str,
    manifest: dict[str, str],
) -> dict[str, Any]:
    validate_preregistered_plan(plan)
    with mp.workdps(COMPARISON_DPS):
        cases = [_case_result(case) for case in plan["parameter_cases"]]
        limit_records = _limit_records(plan, cases)
        classifications = [
            classification
            for case in cases
            for classification in _case_classifications(case)
        ]
        classifications.extend(
            record["classification"] for record in limit_records.values()
        )
        if not classifications:
            raise RuntimeError("no S-012 classifications were produced")
        if "contradicted" in classifications:
            overall = "contradicted"
        elif "unresolved" in classifications:
            overall = "unresolved"
        elif all(value == "validated" for value in classifications):
            overall = "validated"
        else:
            raise RuntimeError("invalid S-012 classification")

        payload: dict[str, Any] = {
            "schema_version": "1.0.0",
            "task_id": "S-012",
            "status": "completed",
            "evidence_role": "deterministic_primary",
            "plan_id": PLAN_ID,
            "contract_version": plan["contract_version"],
            "validation_registry_schema_version": plan[
                "registry_schema_version"
            ],
            "canonical_output": OUTPUT_REL.as_posix(),
            "plan_sha256": _sha256_file(ROOT / PLAN_REL),
            "plan_semantic_sha256": EXPECTED_PLAN_SEMANTIC_SHA256,
            "source_commit": source_commit,
            "source_manifest": manifest,
            "provenance_hashes": {
                "contract_hash": manifest[
                    "docs/scientific-contract/CONTRACT.md"
                ],
                "validation_registry_hash": manifest[
                    "docs/scientific-contract/validation_registry.json"
                ],
                "validation_registry_schema_hash": manifest[
                    "docs/scientific-contract/validation_registry.schema.json"
                ],
                "T-010_artifact_hash": manifest[
                    "artifacts/derived/T-010-generator-scaffold.md"
                ],
                "T-012_artifact_hash": manifest[
                    "artifacts/derived/T-012-complete-reset-baseline.md"
                ],
                "numerical_module_hash": manifest[
                    "src/phasemap/simulation/"
                    "complete_reset_moment_quadrature.py"
                ],
                "reference_module_hash": manifest[
                    "src/phasemap/theory/complete_reset_baseline.py"
                ],
                "runner_hash": manifest[
                    "experiments/"
                    "run_s012_complete_reset_moment_quadrature.py"
                ],
                "test_hash": manifest[
                    "tests/simulation/"
                    "test_complete_reset_moment_quadrature.py"
                ],
            },
            "environment": {
                "python_version": platform.python_version(),
                "mpmath_version": mp.__version__,
                "sympy_version": sp.__version__,
                "operating_system": platform.platform(),
                "machine_architecture": platform.machine(),
            },
            "configuration": {
                "basis_names": list(BASIS_NAMES),
                "passive_basis_names": list(PASSIVE_BASIS_NAMES),
                "parameter_cases": plan["parameter_cases"],
                "arithmetic_precisions": list(PRECISIONS),
                "comparison_arithmetic_decimal_digits": COMPARISON_DPS,
                "serialized_significant_digits": (
                    SERIALIZED_SIGNIFICANT_DIGITS
                ),
                "scaled_tail_horizons": list(SCALED_HORIZONS),
                "excluded_prior_artifact_hashes": {
                    "pilot": plan["scope"]["prior_pilot_sha256"],
                    "pilot_attempt": plan["scope"][
                        "prior_pilot_attempt_sha256"
                    ],
                },
            },
            "cases": cases,
            "limit_regression_records": limit_records,
            "overall_classification": overall,
            "canonical_artifact_hash_recording": {
                "actual_file_sha256": (
                    "returned after atomic publication and recorded in the "
                    "S-012 acceptance artifact/commit"
                ),
                "self_hash_note": (
                    "the byte hash cannot be embedded in the bytes it hashes"
                ),
            },
        }
        semantic_payload = _serial(payload)
        payload["canonical_payload_sha256"] = {
            "definition": (
                "SHA-256 of canonical sorted-key semantics before this field"
            ),
            "sha256": _sha256_bytes(_semantic_bytes(semantic_payload)),
        }
        return payload


def execute(plan_path: Path) -> tuple[dict[str, Any], str]:
    if plan_path != PLAN_REL:
        raise ValueError(f"plan must be exactly {PLAN_REL.as_posix()}")
    output = ROOT / OUTPUT_REL
    if output.exists():
        raise FileExistsError(
            f"canonical output already exists: {OUTPUT_REL.as_posix()}"
        )
    plan = load_preregistered_plan(ROOT / plan_path)
    validate_preregistered_plan(plan)
    source_commit = _clean_source_commit()
    manifest = source_manifest()
    payload = build_result_payload(
        plan,
        source_commit=source_commit,
        manifest=manifest,
    )
    if _clean_source_commit() != source_commit or source_manifest() != manifest:
        raise RuntimeError("source changed during the canonical calculation")
    artifact_hash = _atomic_publish_once(output, payload)
    return payload, artifact_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "run"))
    parser.add_argument("plan", type=Path)
    arguments = parser.parse_args()
    plan = load_preregistered_plan(ROOT / arguments.plan)
    validate_preregistered_plan(plan)
    if arguments.mode == "validate":
        print(f"validated {PLAN_ID}")
        return
    _, artifact_hash = execute(arguments.plan)
    print(f"published {OUTPUT_REL.as_posix()} sha256={artifact_hash}")


if __name__ == "__main__":
    main()
