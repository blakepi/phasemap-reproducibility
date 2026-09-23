#!/usr/bin/env python3
"""Deterministic post-result Richardson reanalysis of preserved S-074 data."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import run_s074_precision as s074
from phasemap.simulation.precision_statistics import estimate, paired_difference
from scripts import render_s074_publication


SOURCE_DIR = ROOT / "artifacts/raw/S-074-precision-primary-v2"
OUTPUT_DIR = ROOT / "artifacts/derived/S-074-Richardson-2026-09-06"
REPORT_PATH = ROOT / "artifacts/derived/N-075-richardson-reanalysis.md"
CONTRACT_PATH = ROOT / "docs/scientific-contract/S-074_RICHARDSON_REANALYSIS.md"
EXPECTED_RESULTS_SHA256 = "08573e429b4816a87f24f556035173ab4aeb48ae466f52e774446ba3f44b4137"
Q = 2.5758293035
ESTIMATOR_IDENTITY = "paired_first_order_richardson_post_result"
SCHEMA = "phasemap.s074.richardson-reanalysis.v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def write_immutable(path: Path | str, content: bytes) -> str:
    """Create an output atomically, or verify byte-identical replay."""

    target = Path(path)
    digest = _sha256(content)
    if target.exists():
        if target.read_bytes() != content:
            raise RuntimeError(f"conflicting existing output: {target}")
        return digest
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.candidate")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return digest


def load_source_results(
    path: Path | str, expected_sha256: str = EXPECTED_RESULTS_SHA256
) -> dict[str, Any]:
    """Load the frozen primary result only after exact byte-hash verification."""

    source = Path(path)
    raw = source.read_bytes()
    actual = _sha256(raw)
    if actual != expected_sha256:
        raise RuntimeError(
            f"source results SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"source results are not valid UTF-8 JSON: {source}") from error
    if payload.get("schema") != "phasemap.s074.results.v1":
        raise RuntimeError("source results schema mismatch")
    if len(payload.get("rows", [])) != 80 or len(payload.get("figure_points", [])) != 52:
        raise RuntimeError("source results do not preserve the 80-row/52-point inventory")
    return payload


def _paired(
    state: Mapping[str, Any], layout: Mapping[str, Any], observable: str,
    coefficients: Sequence[float], window: int,
) -> dict[str, float]:
    return paired_difference(
        dict(state), dict(layout),
        [{"observable": observable, "window": window, "level_coeffs": coefficients}],
    )


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    floor = 64.0 * float.fromhex("0x1.0000000000000p-52") * max(
        1.0, abs(numerator), abs(denominator)
    )
    return None if abs(denominator) <= floor else numerator / denominator


def _classification(discrepancy: float, half_width: float, epsilon: float) -> str:
    lower, upper = discrepancy - half_width, discrepancy + half_width
    if lower >= -epsilon and upper <= epsilon:
        return "validated"
    if upper < -epsilon or lower > epsilon:
        return "contradicted"
    return "unresolved"


def reanalyze_row(
    case: Mapping[str, Any], frozen_row: Mapping[str, Any],
    original_row: Mapping[str, Any], state: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compute one all-level, all-window paired Richardson row."""

    observable = str(frozen_row["observable"])
    layout = dict(case["layout"])
    q = float(frozen_row.get("q", Q))
    if q != Q:
        raise RuntimeError(f"unexpected q for {frozen_row['id']}: {q}")
    window_rows: list[dict[str, Any]] = []
    for window in range(3):
        levels = [
            estimate(dict(state), layout, observable, window, coefficients)
            for coefficients in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        ]
        richardson = _paired(state, layout, observable, (2.0, -1.0, 0.0), window)
        richardson_prime = _paired(state, layout, observable, (0.0, 2.0, -1.0), window)
        fine_gap = _paired(state, layout, observable, (1.0, -1.0, 0.0), window)
        coarse_gap = _paired(state, layout, observable, (0.0, 1.0, -1.0), window)
        residual = _paired(state, layout, observable, (2.0, -3.0, 1.0), window)
        window_rows.append({
            "id": str(frozen_row["id"]), "case_id": str(case["id"]), "window": window,
            "h_value": float(levels[0]["value"]), "h_se": float(levels[0]["se"]),
            "two_h_value": float(levels[1]["value"]), "two_h_se": float(levels[1]["se"]),
            "four_h_value": float(levels[2]["value"]), "four_h_se": float(levels[2]["se"]),
            "richardson_value": float(richardson["value"]),
            "richardson_se": float(richardson["se"]),
            "richardson_prime_value": float(richardson_prime["value"]),
            "richardson_prime_se": float(richardson_prime["se"]),
            "fine_gap_value": float(fine_gap["value"]), "fine_gap_se": float(fine_gap["se"]),
            "coarse_gap_value": float(coarse_gap["value"]), "coarse_gap_se": float(coarse_gap["se"]),
            "residual_value": float(residual["value"]), "residual_se": float(residual["se"]),
            "b_r": abs(float(residual["value"])) + q * float(residual["se"]),
        })

    primary = window_rows[0]
    estimate_value = float(primary["richardson_value"])
    standard_error = float(primary["richardson_se"])
    discrepancy = estimate_value - float(frozen_row["reference"])
    b_r = float(primary["b_r"])
    richardson_window_envelope = max(
        abs(float(window_rows[index]["richardson_value"]) - estimate_value)
        for index in (1, 2)
    )
    original_window_envelope = float(original_row["b_window"])
    transient = float(frozen_row["transient_residual"])
    b_late = max(original_window_envelope, richardson_window_envelope, transient)
    half_width = q * standard_error + b_r + b_late
    epsilon = float(frozen_row["epsilon"])
    precision_scale = float(frozen_row["precision_scale"])
    tau = float(frozen_row["tau"])
    precision_1pct_pass = standard_error <= 0.01 * precision_scale
    stronger_tau_pass = standard_error <= tau

    fine_gap = float(primary["fine_gap_value"])
    fine_gap_se = float(primary["fine_gap_se"])
    floating_floor = 64.0 * float.fromhex("0x1.0000000000000p-52") * max(
        1.0, abs(float(primary["h_value"])), abs(float(primary["two_h_value"])),
        abs(float(primary["four_h_value"])),
    )
    if abs(fine_gap) <= max(q * fine_gap_se, floating_floor):
        convergence_ratio = None
        convergence_status = "indeterminate_negligible_fine_gap"
    else:
        convergence_ratio = float(primary["coarse_gap_value"]) / fine_gap
        convergence_status = "reported_diagnostic_only"

    raw_se = float(original_row["se"])
    raw_discrepancy = float(original_row["estimate"]) - float(frozen_row["reference"])
    raw_z = _safe_ratio(raw_discrepancy, raw_se)
    richardson_z = _safe_ratio(discrepancy, standard_error)
    se_inflation = _safe_ratio(standard_error, raw_se)
    interval = [discrepancy - half_width, discrepancy + half_width]
    classification = _classification(discrepancy, half_width, epsilon)
    flags = []
    if convergence_ratio is None:
        flags.append("convergence_ratio_indeterminate")
    if raw_z is not None and abs(raw_z) > 3.0:
        flags.append("raw_abs_standardized_discrepancy_gt_3")
    if richardson_z is not None and abs(richardson_z) > 3.0:
        flags.append("richardson_abs_standardized_discrepancy_gt_3")

    result = {
        "id": str(frozen_row["id"]), "case_id": str(case["id"]),
        "group": str(case["group"]), "protocol": str(case["protocol"]),
        "M": float(case["M"]), "Pe": float(case["Pe"]), "rho": float(case["rho"]),
        "observable": observable, "observable_class": str(frozen_row["observable_class"]),
        "reference": float(frozen_row["reference"]), "estimate": estimate_value,
        "se": standard_error, "n": int(state["n"]),
        "se_fraction": standard_error / precision_scale, "tau": tau, "epsilon": epsilon,
        "q": q, "discrepancy": discrepancy, "interval": interval,
        "classification": classification, "precision_1pct_pass": precision_1pct_pass,
        "stronger_tau_pass": stronger_tau_pass,
        "qualification_pass": precision_1pct_pass and stronger_tau_pass,
        "b_r": b_r, "b_late": b_late, "b_total": b_r + b_late,
        "original_primary_window_envelope": original_window_envelope,
        "richardson_window_envelope": richardson_window_envelope,
        "transient_residual": transient, "windows": copy.deepcopy(window_rows),
        "raw_standardized_discrepancy": raw_z,
        "richardson_standardized_discrepancy": richardson_z,
        "se_inflation": se_inflation, "convergence_ratio": convergence_ratio,
        "convergence_ratio_status": convergence_status,
        "diagnostic_flags": flags, "post_result": True,
        "estimator_identity": ESTIMATOR_IDENTITY,
        "raw_primary": copy.deepcopy(dict(original_row)),
    }
    return result, window_rows


def _figure_points(
    original_points: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {(str(row["case_id"]), str(row["observable"])): row for row in rows}
    output: list[dict[str, Any]] = []
    for original in original_points:
        series = str(original["series"])
        observable = "v_x" if "drift" in series else "spatial"
        row = by_key[(str(original["case_id"]), observable)]
        output.append({
            "series": series, "x": float(original["x"]), "case_id": str(row["case_id"]),
            "n": int(row["n"]), "estimate": float(row["estimate"]), "se": float(row["se"]),
            "reference": float(row["reference"]), "classification": str(row["classification"]),
            "precision_1pct_pass": bool(row["precision_1pct_pass"]),
            "stronger_tau_pass": bool(row["stronger_tau_pass"]),
            "qualification_pass": bool(row["qualification_pass"]),
            "b_r": float(row["b_r"]), "b_late": float(row["b_late"]),
            "b_total": float(row["b_total"]), "post_result": True,
            "estimator_identity": ESTIMATOR_IDENTITY,
            "source_manifest_sha256": str(original["source_manifest_sha256"]),
            "plan_semantic_sha256": str(original["plan_semantic_sha256"]),
        })
    if len(output) != 52:
        raise RuntimeError("Richardson figure-point inventory is not exactly 52")
    return output


def _diagnostic_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    classes = sorted({str(row["observable_class"]) for row in rows})
    class_means: dict[str, Any] = {}
    for label in classes:
        subset = [row for row in rows if row["observable_class"] == label]
        raw_values = [float(row["raw_standardized_discrepancy"]) for row in subset if row["raw_standardized_discrepancy"] is not None]
        richardson_values = [float(row["richardson_standardized_discrepancy"]) for row in subset if row["richardson_standardized_discrepancy"] is not None]
        class_means[label] = {
            "count": len(subset),
            "raw_mean_standardized_discrepancy": sum(raw_values) / len(raw_values) if raw_values else None,
            "richardson_mean_standardized_discrepancy": sum(richardson_values) / len(richardson_values) if richardson_values else None,
        }
    above_three = []
    for row in rows:
        for estimator, key in (
            ("raw_finest_em", "raw_standardized_discrepancy"),
            (ESTIMATOR_IDENTITY, "richardson_standardized_discrepancy"),
        ):
            value = row[key]
            if value is not None and abs(float(value)) > 3.0:
                above_three.append({"id": row["id"], "estimator": estimator, "value": value})
    heuristic_failures = [
        {"id": row["id"], "flags": list(row["diagnostic_flags"])}
        for row in rows if row["diagnostic_flags"]
    ]
    return {
        "class_mean_standardized_discrepancies": class_means,
        "absolute_standardized_discrepancies_above_three": above_three,
        "diagnostic_heuristic_failures": heuristic_failures,
        "diagnostics_are_not_selection_rules": True,
    }


def _csv_bytes(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return buffer.getvalue().encode("utf-8")


def _report(payload: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    core = payload["core_v_speed_readback"]
    reout = payload["reanalysis_outcomes"]
    return f"""# N-075 paired Richardson reanalysis

The authorized CPU-only post-result reanalysis used all 41 cells and all 80 rows from the receipt-verified S-074 v2 accumulators. It did not sample, top up, pool, or select rows. The frozen raw-primary result SHA-256 is `{payload['source_results_sha256']}`; its two stricter design-SE misses remain nested in every row and listed in the aggregate source outcome.

Estimator: `R = 2 X_h - X_2h`, with exact paired whole-trajectory uncertainty. Nonlinear centered variance/diffusion uses the finite-N deletion algebra in the preserved sufficient-feature covariance. The residual envelope is `abs(2 X_h - 3 X_2h + X_4h) + q SE`; late-time bias is the maximum of the original window envelope, Richardson window contrasts, and the original transient residual.

Direct result: {reout['classification_counts']['validated']}/80 contained, {reout['precision_1pct_pass_count']}/80 at 1%, and {reout['stronger_tau_pass_count']}/80 at the stronger target. Core-V speed readback: fine/coarse gap `{core['fine_coarse_gap']:.17g}` and step ratio `{core['step_ratio']:.16g}`. These and all diagnostic flags are reported, not used for selection.

Checksummed carriers: `{summary['results_file']}`, `{summary['raw_step_csv']}`, `{summary['diagnostic_csv']}`, and the 52-point publication carrier.
"""


def reanalyze(
    source_dir: Path | str = SOURCE_DIR, output_dir: Path | str = OUTPUT_DIR,
    report_path: Path | str = REPORT_PATH,
) -> dict[str, Any]:
    """Verify preserved inputs, compute all paired rows, and emit immutable outputs."""

    source = Path(source_dir)
    destination = Path(output_dir)
    original = load_source_results(source / "results.json")
    freeze, verified_base, freeze_hash = s074._load_freeze(s074.V2_PLAN_PATH, source)
    if verified_base.resolve() != source.resolve():
        raise RuntimeError("verified source directory differs from requested source")
    allocation = s074._load_allocation(freeze, source, freeze_hash)
    original_by_id = {str(row["id"]): row for row in original["rows"]}
    frozen_ids = [str(row["id"]) for case in freeze["cases"] for row in case["rows"]]
    if list(original_by_id) != frozen_ids or len(original_by_id) != 80:
        raise RuntimeError("source row order or identity differs from the freeze")

    allocation_by_case = {str(item["case_id"]): int(item["n"]) for item in allocation["cells"]}
    rows: list[dict[str, Any]] = []
    raw_steps: list[dict[str, Any]] = []
    for case in freeze["cases"]:
        n = allocation_by_case[str(case["id"])]
        state = s074._merged_production_state(
            case, freeze["plan"], source, n, freeze_hash,
            freeze["source_manifest_sha256"], freeze["environment_sha256"],
        )
        for frozen_row in case["rows"]:
            row, steps = reanalyze_row(
                case, frozen_row, original_by_id[str(frozen_row["id"])], state
            )
            rows.append(row)
            raw_steps.extend(steps)
    if len(rows) != 80 or len(raw_steps) != 240:
        raise RuntimeError("reanalysis did not retain 80 rows and three windows per row")

    misses = [
        str(row["id"]) for row in original["rows"]
        if not bool(row["precision_pass"])
    ]
    diagnostics = _diagnostic_summary(rows)
    counts = {
        label: sum(row["classification"] == label for row in rows)
        for label in ("validated", "contradicted", "unresolved")
    }
    core = next(row for row in rows if row["id"] == "core-V:speed")
    core_window = core["windows"][0]
    payload = {
        "schema": SCHEMA, "estimator_identity": ESTIMATOR_IDENTITY,
        "analysis_timing": "post_result_after_observing_finest_step_bias",
        "source_results_sha256": EXPECTED_RESULTS_SHA256,
        "source_freeze_sha256": freeze_hash,
        "source_manifest_sha256": freeze["source_manifest_sha256"],
        "plan_semantic_sha256": freeze["plan_semantic_sha256"],
        "contract_sha256": _sha256(CONTRACT_PATH.read_bytes()),
        "reanalysis_source_sha256": _sha256(Path(__file__).read_bytes()),
        "no_new_sampling": True, "cells": len(freeze["cases"]),
        "raw_primary_outcomes": {
            "schema": original["schema"], "primary_estimator": original["primary_estimator"],
            "precision_pass": original["precision_pass"],
            "discretization_pass": original["discretization_pass"],
            "qualification_pass": original["qualification_pass"],
            "scientific_validation_pass": original["scientific_validation_pass"],
            "classification_counts": copy.deepcopy(original["classification_counts"]),
            "stricter_target_misses": misses, "no_post_result_top_up": True,
        },
        "reanalysis_outcomes": {
            "classification_counts": counts,
            "precision_1pct_pass_count": sum(bool(row["precision_1pct_pass"]) for row in rows),
            "stronger_tau_pass_count": sum(bool(row["stronger_tau_pass"]) for row in rows),
            "all_rows_retained": len(rows) == 80,
        },
        "core_v_speed_readback": {
            "fine_coarse_gap": float(core_window["two_h_value"]) - float(core_window["h_value"]),
            "step_ratio": core["convergence_ratio"],
            "not_a_selection_criterion": True,
        },
        **diagnostics, "rows": rows, "table_rows": copy.deepcopy(rows),
        "figure_points": _figure_points(original["figure_points"], rows),
    }

    diagnostic_rows = [{
        "id": row["id"], "case_id": row["case_id"],
        "observable_class": row["observable_class"],
        "raw_standardized_discrepancy": row["raw_standardized_discrepancy"],
        "richardson_standardized_discrepancy": row["richardson_standardized_discrepancy"],
        "se_inflation": row["se_inflation"],
        "precision_1pct_pass": row["precision_1pct_pass"],
        "stronger_tau_pass": row["stronger_tau_pass"],
        "convergence_ratio": row["convergence_ratio"],
        "convergence_ratio_status": row["convergence_ratio_status"],
        "diagnostic_flags": ";".join(row["diagnostic_flags"]),
    } for row in rows]
    raw_fields = (
        "id", "case_id", "window", "h_value", "h_se", "two_h_value", "two_h_se",
        "four_h_value", "four_h_se", "richardson_value", "richardson_se",
        "richardson_prime_value", "richardson_prime_se", "fine_gap_value", "fine_gap_se",
        "coarse_gap_value", "coarse_gap_se", "residual_value", "residual_se", "b_r",
    )
    diagnostic_fields = (
        "id", "case_id", "observable_class", "raw_standardized_discrepancy",
        "richardson_standardized_discrepancy", "se_inflation", "precision_1pct_pass",
        "stronger_tau_pass", "convergence_ratio", "convergence_ratio_status", "diagnostic_flags",
    )
    results_path = destination / "results.json"
    raw_path = destination / "raw-step-values.csv"
    diagnostic_path = destination / "diagnostics.csv"
    summary_path = destination / "summary.json"
    write_immutable(results_path, _json_bytes(payload))
    write_immutable(raw_path, _csv_bytes(raw_steps, raw_fields))
    write_immutable(diagnostic_path, _csv_bytes(diagnostic_rows, diagnostic_fields))
    summary = {
        "schema": "phasemap.s074.richardson-summary.v1",
        "results_file": results_path.name, "raw_step_csv": raw_path.name,
        "diagnostic_csv": diagnostic_path.name, "rows": len(rows),
        "raw_step_rows": len(raw_steps), "figure_points": len(payload["figure_points"]),
        "source_results_sha256": EXPECTED_RESULTS_SHA256,
        "reanalysis_outcomes": payload["reanalysis_outcomes"],
    }
    write_immutable(summary_path, _json_bytes(summary))
    rendered = render_s074_publication.render(results_path, destination)
    artifact_paths = [results_path, raw_path, diagnostic_path, summary_path, *rendered.values()]
    checksums = {
        "schema": "phasemap.s074.richardson-checksums.v1",
        "sha256": {path.name: _sha256(path.read_bytes()) for path in artifact_paths},
    }
    checksums_path = destination / "checksums.json"
    write_immutable(checksums_path, _json_bytes(checksums))
    write_immutable(Path(report_path), _report(payload, summary).encode("utf-8"))
    return {
        "status": "PASS", "cells": 41, "rows": 80, "figure_points": 52,
        "output_dir": str(destination), "report": str(report_path),
        "stronger_tau_pass_count": payload["reanalysis_outcomes"]["stronger_tau_pass_count"],
        "results_sha256": checksums["sha256"]["results.json"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser


def main() -> int:
    args = _parser().parse_args()
    print(json.dumps(reanalyze(args.source_dir, args.output_dir, args.report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
