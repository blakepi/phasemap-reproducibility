#!/usr/bin/env python3
"""Render fixed S-074 results JSON into publication table and figure inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_NUMBERS = ("M", "Pe", "rho", "reference", "estimate", "se", "se_fraction", "b_disc", "b_window", "transient_residual", "b_total")
_POINT_NUMBERS = ("x", "estimate", "se", "reference", "b_disc", "b_window", "transient_residual", "b_total")
_R_NUMBERS = ("M", "Pe", "rho", "reference", "estimate", "se", "se_fraction", "b_r", "b_late", "transient_residual", "b_total")
_R_POINT_NUMBERS = ("x", "estimate", "se", "reference", "b_r", "b_late", "b_total")
_STATUS = {"validated": "V", "unresolved": "U", "contradicted": "C"}
_PROTOCOLS = ("P", "V", "Theta", "PV", "PTheta", "VTheta", "PVTheta")
_POSITION_PROTOCOLS = {"P", "PV", "PTheta", "PVTheta"}
_RAW_PRIMARY_MISSES = [
    "figure-rho0p5-PV:spatial",
    "figure-rho0p5-PTheta:spatial",
]


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


def _load(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load results JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("results JSON must be an object")
    return payload, hashlib.sha256(raw).hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _validate_row(row: Any, mode: str = "raw") -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("result rows must be objects")
    if mode == "raw":
        required = {"id", "case_id", "group", "protocol", "observable", "classification", "n", "precision_pass", "discretization_pass", "qualification_pass", *_NUMBERS}
        boolean_fields = ("precision_pass", "discretization_pass", "qualification_pass")
        numbers = _NUMBERS
    else:
        required = {"id", "case_id", "group", "protocol", "observable", "classification", "n", "precision_1pct_pass", "stronger_tau_pass", "qualification_pass", "post_result", "estimator_identity", "raw_primary", *_R_NUMBERS}
        boolean_fields = ("precision_1pct_pass", "stronger_tau_pass", "qualification_pass", "post_result")
        numbers = _R_NUMBERS
    missing = required - set(row)
    if missing:
        raise ValueError(f"result row missing {sorted(missing)}")
    if not all(isinstance(row[key], str) and row[key] for key in ("id", "case_id", "group", "protocol", "observable")):
        raise ValueError("result row identity fields must be nonempty strings")
    if row["classification"] not in _STATUS:
        raise ValueError("result row has invalid classification")
    if isinstance(row["n"], bool) or not isinstance(row["n"], int) or row["n"] < 3:
        raise ValueError("result row n must be an integer at least 3")
    if not all(isinstance(row[key], bool) for key in boolean_fields):
        raise ValueError("result row qualification metadata must be boolean")
    for key in numbers:
        _finite(row[key], f"row {row['id']} {key}")
    if row["se"] < 0:
        raise ValueError("result row se must be nonnegative")
    if row["protocol"] not in _PROTOCOLS or row["group"] not in {"core", "figure", "tuned"}:
        raise ValueError("result row has unknown protocol or group")
    expected = {"u_xx", "speed", "spatial"}
    if row["protocol"] not in _POSITION_PROTOCOLS:
        expected.add("v_x")
    if row["group"] == "core" and row["protocol"] in {"PV", "PVTheta"}:
        expected.update(("raw_msd", "r_dot_v"))
    if row["group"] == "figure":
        expected = {"spatial"} | ({"v_x"} if row["protocol"] not in _POSITION_PROTOCOLS else set())
    if row["group"] == "tuned":
        expected = {"spatial", "v_x"}
    if row["observable"] not in expected:
        raise ValueError("result row observable is not physical for its group/protocol")
    if mode == "richardson":
        if row["post_result"] is not True or row["estimator_identity"] != "paired_first_order_richardson_post_result":
            raise ValueError("Richardson row estimator identity is invalid")
        raw_primary = row["raw_primary"]
        if not isinstance(raw_primary, dict) or raw_primary.get("id") != row["id"]:
            raise ValueError("Richardson row does not preserve its raw primary row")
    return row


def _expected_points(rows: list[dict[str, Any]]) -> set[tuple[str, str, float]]:
    expected: set[tuple[str, str, float]] = set()
    for row in rows:
        if row["group"] == "figure":
            if row["observable"] == "spatial":
                series = f"{'variance' if row['protocol'] in _POSITION_PROTOCOLS else 'diffusion'}_{row['protocol']}"
            elif row["observable"] == "v_x":
                series = f"drift_{row['protocol']}"
            else:
                continue
            expected.add((row["case_id"], series, float(row["rho"])))
        elif row["group"] == "tuned":
            if row["observable"] == "spatial":
                series = f"tuned_diffusion_{row['protocol']}"
            elif row["observable"] == "v_x":
                series = "tuned_drift_V" if row["protocol"] == "V" else "tuned_theta_drift"
            else:
                continue
            expected.add((row["case_id"], series, float(row["M"])))
    return expected


def _validate(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    schema = payload.get("schema")
    if schema == "phasemap.s074.results.v1":
        mode = "raw"
    elif schema == "phasemap.s074.richardson-reanalysis.v1":
        mode = "richardson"
        if (
            payload.get("estimator_identity") != "paired_first_order_richardson_post_result"
            or payload.get("analysis_timing") != "post_result_after_observing_finest_step_bias"
            or not isinstance(payload.get("source_results_sha256"), str)
            or len(payload["source_results_sha256"]) != 64
        ):
            raise ValueError("Richardson results identity is invalid")
        raw_outcomes = payload.get("raw_primary_outcomes")
        if (
            not isinstance(raw_outcomes, dict)
            or raw_outcomes.get("precision_pass") is not False
            or raw_outcomes.get("qualification_pass") is not False
            or raw_outcomes.get("stricter_target_misses") != _RAW_PRIMARY_MISSES
        ):
            raise ValueError("Richardson results do not preserve the two raw-primary misses")
    else:
        raise ValueError("unexpected results schema")
    rows, table_rows, points = payload.get("rows"), payload.get("table_rows"), payload.get("figure_points")
    if not isinstance(rows, list) or len(rows) != 80:
        raise ValueError("results must contain exactly 80 rows")
    checked = [_validate_row(row, mode) for row in rows]
    if len({row["id"] for row in checked}) != 80:
        raise ValueError("result row IDs must be unique")
    if {group: sum(row["group"] == group for row in checked) for group in ("core", "figure", "tuned")} != {"core": 28, "figure": 40, "tuned": 12}:
        raise ValueError("results do not retain the 28/40/12 physical row inventory")
    case_counts = {group: len({row["case_id"] for row in checked if row["group"] == group}) for group in ("core", "figure", "tuned")}
    if case_counts != {"core": 7, "figure": 28, "tuned": 6}:
        raise ValueError("results do not retain the 7/28/6 physical case inventory")
    if not isinstance(table_rows, list) or table_rows != rows:
        raise ValueError("table_rows must exactly preserve result rows and metadata")
    source_hash, plan_hash = payload.get("source_manifest_sha256"), payload.get("plan_semantic_sha256")
    if not all(isinstance(item, str) and len(item) == 64 for item in (source_hash, plan_hash)):
        raise ValueError("results provenance hashes are invalid")
    if not isinstance(points, list) or len(points) != 52:
        raise ValueError("results must contain exactly 52 figure_points")
    by_case = {row["case_id"]: [] for row in checked}
    for row in checked:
        by_case[row["case_id"]].append(row)
    if mode == "raw":
        required_point = {"series", "case_id", "n", "classification", "precision_pass", "discretization_pass", "qualification_pass", "source_manifest_sha256", "plan_semantic_sha256", *_POINT_NUMBERS}
        point_booleans = ("precision_pass", "discretization_pass", "qualification_pass")
        point_numbers = _POINT_NUMBERS
        matching_fields = ("estimate", "se", "n", "reference", "classification", "precision_pass", "discretization_pass", "qualification_pass", "b_disc", "b_window", "transient_residual", "b_total")
    else:
        required_point = {"series", "case_id", "n", "classification", "precision_1pct_pass", "stronger_tau_pass", "qualification_pass", "post_result", "estimator_identity", "source_manifest_sha256", "plan_semantic_sha256", *_R_POINT_NUMBERS}
        point_booleans = ("precision_1pct_pass", "stronger_tau_pass", "qualification_pass", "post_result")
        point_numbers = _R_POINT_NUMBERS
        matching_fields = ("estimate", "se", "n", "reference", "classification", "precision_1pct_pass", "stronger_tau_pass", "qualification_pass", "b_r", "b_late", "b_total")
    for point in points:
        if not isinstance(point, dict) or required_point - set(point):
            raise ValueError("figure point is missing required metadata")
        if not isinstance(point["series"], str) or not point["series"] or not isinstance(point["case_id"], str):
            raise ValueError("figure point identity is invalid")
        if isinstance(point["n"], bool) or not isinstance(point["n"], int) or point["n"] < 3:
            raise ValueError("figure point n must be an integer at least 3")
        if point["classification"] not in _STATUS or not all(isinstance(point[key], bool) for key in point_booleans):
            raise ValueError("figure point qualification metadata is invalid")
        for key in point_numbers:
            _finite(point[key], f"figure point {key}")
        if point["se"] < 0:
            raise ValueError("figure point se must be nonnegative")
        if point["source_manifest_sha256"] != source_hash or point["plan_semantic_sha256"] != plan_hash:
            raise ValueError("figure point provenance differs from results")
        if mode == "richardson" and (
            point["post_result"] is not True
            or point["estimator_identity"] != payload["estimator_identity"]
        ):
            raise ValueError("Richardson figure point estimator identity is invalid")
        matching = [row for row in by_case.get(point["case_id"], []) if all(row[key] == point[key] for key in matching_fields)]
        if len(matching) != 1:
            raise ValueError("figure point does not match exactly one result row")
    observed = {(point["case_id"], point["series"], float(point["x"])) for point in points}
    expected = _expected_points(checked)
    if len(observed) != 52 or observed != expected:
        raise ValueError("figure point inventory, series, or x coordinate is invalid")
    return checked, points, mode


def _groups(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    core = [row for row in rows if row["group"] == "core"]
    figure = [row for row in rows if row["group"] == "figure"]
    tuned = [row for row in rows if row["group"] == "tuned"]
    if len(core) + len(figure) + len(tuned) != 80 or not core:
        raise ValueError("rows must retain core, figure-rho, and tuned-M groups")
    def heading(label: str, items: list[dict[str, Any]]) -> str:
        first = items[0]
        if any((row["M"], row["Pe"], row["rho"]) != (first["M"], first["Pe"], first["rho"]) for row in items):
            raise ValueError("parameter heading does not have fixed M, Pe, rho")
        return f"{label}: M = {float(first['M']):g}, Pe = {float(first['Pe']):g}, rho = {float(first['rho']):g}"

    output = [(heading("Reference parameters", core), core)]
    for rho in (0.15, 0.5, 1.5, 6.0):
        subset = [row for row in figure if math.isclose(float(row["rho"]), rho, rel_tol=0.0, abs_tol=1e-12)]
        if not subset:
            raise ValueError(f"missing figure rho group {rho}")
        output.append((heading("Figure parameters", subset), subset))
    for mass in (0.15, 0.35, 0.55):
        subset = [row for row in tuned if math.isclose(float(row["M"]), mass, rel_tol=0.0, abs_tol=1e-12)]
        if not subset:
            raise ValueError(f"missing tuned M group {mass}")
        output.append((heading("Tuned parameters", subset), subset))
    if sum(len(items) for _, items in output) != 80:
        raise ValueError("parameter groups do not retain every result row")
    return output


def _number(value: Any, figures: int) -> str:
    return format(_finite(value, "render value"), f".{figures}g")


def _protocol(row: dict[str, Any], latex: bool) -> str:
    name = str(row["protocol"])
    return "$" + name.replace("Theta", "\\Theta") + "$" if latex else name.replace("Theta", "Θ")


def _tex_number(value: Any, figures: int) -> str:
    number = _number(value, figures)
    if "e" in number:
        mantissa, exponent = number.split("e")
        return mantissa + "\\times10^{" + str(int(exponent)) + "}"
    return number


def _moment(row: dict[str, Any], latex: bool, *, journal: bool = False) -> str:
    mapping = {
        "u_xx": "U_{xx}", "speed": "\\mathrm{Tr}\\,S", "v_x": "\\bar v_x",
        "raw_msd": "\\mathrm{Tr}\\,R", "r_dot_v": "\\mathrm{Tr}\\,C_{rv}",
        "spatial": (
            "s_r^2" if journal else "\\mathcal V"
        ) if row.get("observable_class") == "stationary_variance" else "D_{\\mathrm{eff}}",
    }
    value = mapping[row["observable"]]
    plain = {
        "u_xx": "Uxx", "speed": "Tr S", "v_x": "mean vx",
        "raw_msd": "Tr R", "r_dot_v": "Tr C_rv",
        "spatial": "s_r^2" if journal and row.get("observable_class") == "stationary_variance" else ("Tr Cov(r)" if row.get("observable_class") == "stationary_variance" else "D_eff"),
    }
    return "$" + value + "$" if latex else plain[row["observable"]]


def _status(row: dict[str, Any], mode: str = "raw") -> str:
    return _STATUS[row["classification"]] + (
        "" if mode == "richardson" or row["qualification_pass"] else "*"
    )


def _cells(row: dict[str, Any], latex: bool, mode: str = "raw", *, journal: bool = False) -> list[str]:
    estimate = "$" + _tex_number(row["estimate"], 5) + " \\pm " + _tex_number(row["se"], 2) + "$" if latex else f"{_number(row['estimate'], 5)} ± {_number(row['se'], 2)}"
    se_percent = "$" + format(100 * float(row["se_fraction"]), ".3g") + "$" if latex else f"{100 * float(row['se_fraction']):.3g}%"
    reference = "$" + _tex_number(row["reference"], 5) + "$" if latex else _number(row["reference"], 5)
    count = "$" + str(row["n"]) + "$" if latex else str(row["n"])
    return [_protocol(row, latex), _moment(row, latex, journal=journal), count, reference, estimate, se_percent, _status(row, mode)]


def _markdown(
    groups: list[tuple[str, list[dict[str, Any]]]], result_hash: str,
    mode: str = "raw", *, journal: bool = False,
) -> str:
    if journal:
        lines = [
            f"<!-- S-074 Richardson results SHA-256: {result_hash} -->",
            "# S-074 paired Richardson precision table", "",
            "After inspection of raw-finest bias, paired post-result Richardson "
            "estimates 2X_h - X_2h cancel the leading O(h) Euler-Maruyama bias. "
            "The PV and PTheta spatial-variance rows at M=2, Pe=3, rho=0.5 miss "
            "the stricter design-SE target (SEs 0.024 and 0.032; see Sec. S0.2). "
            "SE percentages use the nonzero reference magnitude, or the parent scale "
            "for a symmetry zero. V means interval containment, not passage of every "
            "precision requirement; U=unresolved and C=contradicted.",
            "", "| Protocol | Moment | N | Reference | Richardson estimate ± paired SE | SE percentage | Interval |",
            "|---|---|---:|---:|---:|---:|:---:|",
        ]
    elif mode == "richardson":
        lines = [f"<!-- S-074 post-result Richardson results SHA-256: {result_hash} -->", "# S-074 post-result Richardson precision table", "", "This table reports the paired post-result Richardson reanalysis adopted after observing the finest-step bias. All 80 raw-primary rows remain preserved. Both raw and extrapolated analyses miss the stricter design-SE target for the two spatial-variance rows identified in Sec.~S0.2. Nonzero-reference scale uses SE/|reference|; symmetry-zero rows use the declared parent scale. Interval: V=contained (validated), U=unresolved, C=contradicted.", "", "| Protocol | Moment | N | Reference | Richardson estimate ± paired SE | SE percentage | Interval |", "|---|---|---:|---:|---:|---:|:---:|"]
    else:
        lines = [f"<!-- S-074 results SHA-256: {result_hash} -->", "# S-074 precision table", "", "Nonzero-reference scale uses SE/|reference|; symmetry-zero rows use the declared parent scale. Interval: V=contained (validated), U=unresolved, C=contradicted; * marks a missed stricter design-SE target or step criterion, separately from interval agreement.", "", "| Protocol | Moment | N | Reference | EM estimate ± SE | SE percentage | Interval |", "|---|---|---:|---:|---:|---:|:---:|"]
    for heading, rows in groups:
        lines.append(f"| **{heading}** |  |  |  |  |  |  |")
        lines.extend("| " + " | ".join(_cells(row, False, mode, journal=journal)) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _latex(
    groups: list[tuple[str, list[dict[str, Any]]]], result_hash: str,
    mode: str = "raw", *, journal: bool = False,
) -> str:
    header = "Protocol & Moment & $N$ & Reference & " + ("Richardson estimate $\\pm$ paired SE" if mode == "richardson" else "EM estimate $\\pm$ SE") + " & SE (\\%) & Interval \\\\"
    opening = (
        "Paired post-result Richardson reanalysis (S-074), adopted after observing the finest-step bias, "
        if mode == "richardson"
        else "Independent Euler--Maruyama estimates (S-074), "
    )
    closing = (
        "Both raw and extrapolated analyses miss the stricter design-SE target for the two spatial-variance rows identified in Sec.~S0.2."
        if mode == "richardson"
        else "An asterisk marks a missed stricter design-SE target or step criterion, separately from interval agreement; see Sec.~S0.2."
    )
    if journal:
        opening = "Paired post-result Richardson estimates $2X_h-X_{2h}$ (S-074), adopted after inspection of raw-finest bias, "
        closing = "Raw-finest analysis contained 80/80 intervals, with 0 contradicted and 78/80 meeting the stricter target; Richardson did not rescue containment. The $PV$ and $P\\Theta$ spatial-variance rows at $M=2$, $\\mathrm{Pe}=3$, $\\rho=0.5$ miss the stricter design-SE target (SEs 0.024 and 0.032; see Sec.~S0.2). V denotes interval containment, not passage of every precision requirement."
    caption = (
        "\\caption{" + opening + "with $U_{xx}=E[\\cos^2\\theta]$, "
        + "$\\operatorname{Tr}S=E[|v|^2]$, $\\operatorname{Tr}C_{rv}=E[r\\cdot v]$, "
        + "$\\operatorname{Tr}R=E[|r|^2]$, $\\bar v_x=E[v_x]$, "
        + ("$s_r^2=\\operatorname{Tr}\\operatorname{Cov}(r)$, and " if journal else "$\\mathcal V=\\operatorname{Tr}\\operatorname{Cov}(r)$, and ")
        + ("$D_{\\mathrm{eff}}=\\tfrac14\\lim_{t\\to\\infty}d s_r^2/dt$. " if journal else "$D_{\\mathrm{eff}}=\\tfrac14\\lim_{t\\to\\infty}d\\mathcal V/dt$. ")
        + "SE percentages use the nonzero reference magnitude, or the declared parent scale for a symmetry zero. "
        + "Interval: V=contained (validated), U=unresolved, C=contradicted. "
        + closing + "}\\label{tab:s074}\\\\"
    )
    lines = [
        f"% S-074 results SHA-256: {result_hash}",
        "\\begingroup", "\\small", "\\setlength{\\tabcolsep}{3pt}",
        "\\begin{longtable}{llrrrrc}",
        caption,
        "\\hline", header, "\\hline", "\\endfirsthead", "\\hline",
        header, "\\hline", "\\endhead",
    ]
    for heading, rows in groups:
        heading_break = r"\\*" if journal else r"\\"
        lines.append(f"\\multicolumn{{7}}{{l}}{{\\textit{{{heading}}}}} " + heading_break)
        lines.extend(" & ".join(_cells(row, True, mode, journal=journal)) + " \\\\" for row in rows)
    lines.extend(["\\hline", "\\end{longtable}", "\\endgroup"])
    return "\n".join(lines) + "\n"


def render(
    results_path: Path | str, output_dir: Path | str | None = None,
    *, presentation: str = "archive",
) -> dict[str, Path]:
    """Render existing results; preserve historical archive output by default."""
    if presentation not in {"archive", "journal"}:
        raise ValueError("unknown presentation; expected archive or journal")
    payload, result_hash = _load(Path(results_path))
    rows, points, mode = _validate(payload)
    journal = presentation == "journal"
    if journal and mode != "richardson":
        raise ValueError("journal presentation requires paired Richardson results")
    groups = _groups(rows)
    destination = Path(output_dir) if output_dir is not None else ROOT / "artifacts/derived"
    destination.mkdir(parents=True, exist_ok=True)
    prefix = "S-074-Richardson" if mode == "richardson" else "S-074"
    outputs = {
        "figure_points": destination / f"{prefix}-figure-points.json",
        "markdown": destination / f"{prefix}-precision-table.md",
        "latex": destination / f"{prefix}-precision-table.tex",
    }
    if mode == "richardson":
        point_payload = {
            "schema": "phasemap.s074.richardson-figure-points.v1",
            "results_sha256": result_hash,
            "source_results_sha256": payload["source_results_sha256"],
            "estimator_identity": payload["estimator_identity"],
            "analysis_timing": payload["analysis_timing"], "points": points,
        }
    else:
        point_payload = {"schema": "phasemap.s074.figure-points.v1", "results_sha256": result_hash, "points": points}
    contents = {
        "figure_points": (json.dumps(point_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "markdown": _markdown(groups, result_hash, mode, journal=journal).encode("utf-8"),
        "latex": _latex(groups, result_hash, mode, journal=journal).encode("utf-8"),
    }
    for key, output in outputs.items():
        content = contents[key]
        if mode == "richardson" and output.exists() and output.read_bytes() != content:
            raise RuntimeError(f"conflicting existing output: {output}")
        output.write_bytes(content)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--presentation", choices=("archive", "journal"), default="archive",
        help="archive preserves historical output; journal changes explanatory text only",
    )
    args = parser.parse_args()
    print(json.dumps({key: str(value) for key, value in render(
        args.results, args.output_dir, presentation=args.presentation,
    ).items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
