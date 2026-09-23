#!/usr/bin/env python3
"""Prospective, resumable S-074 precision-study runner.

Importing this module never samples trajectories. The CLI separates the
deterministic freeze, excluded pilot, fixed allocation, production, final
summary, and validation transactions.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
from typing import Any, Mapping, Sequence
import warnings

import numpy as np

from phasemap.simulation.precision_statistics import (
    FeatureAccumulator,
    bootstrap_se,
    build_features,
    estimate,
    paired_difference,
    project_pilot_size,
)
from phasemap.simulation.protocols import Protocol
from phasemap.theory.nonposition_protocols import (
    NONPOSITION_PROTOCOLS,
    nonposition_protocol_second_moments,
)
from phasemap.theory.position_protocols import (
    POSITION_PROTOCOLS,
    position_protocol_stationary_second_moments,
)
from phasemap.theory.generator import Symbols, second_order_moment_system


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "experiments/S-074-precision-primary-v1.json"
V2_PLAN_PATH = ROOT / "experiments/S-074-precision-primary-v2.json"
CONTRACT_PATH = ROOT / "docs/scientific-contract/CONTRACT.md"
AMENDMENT_PATH = ROOT / "docs/scientific-contract/S-074_VALIDATION_AMENDMENT.md"
RESOURCE_AMENDMENT_PATH = ROOT / "docs/scientific-contract/S-074_RESOURCE_CAP_EXTENSION.md"
REGISTRY_PATH = ROOT / "docs/scientific-contract/validation_registry.json"
EXPECTED_PLAN_SEMANTIC_SHA256 = {
    "S-074-precision-primary-v1":
        "6132a0ee8968b3a812a4bba901527def5ef4182c05d3902d1166d7243907b943",
    "S-074-precision-primary-v2":
        "e00bce97ad4711455fdc1d6337105a78cd37c47e6614763aa28c0260b763c318",
}
PLAN_REVISION_FIELDS = frozenset({
    "plan_id", "version", "output_directory", "maximum_cell_n",
    "maximum_total_n", "pilot_origin_directory", "pilot_origin_freeze_sha256",
    "resource_amendment",
})
COMMON_NUMERICAL_SOURCES = (
    "src/phasemap/simulation/gpu_trajectories.py",
    "src/phasemap/simulation/precision_statistics.py",
    "src/phasemap/simulation/protocols.py",
    "src/phasemap/theory/generator.py",
    "src/phasemap/theory/position_protocols.py",
    "src/phasemap/theory/nonposition_protocols.py",
)
EXPECTED_V2_REQUIRED_TOTAL = 23_519_232
EXPECTED_V2_REQUIRED_MAX = 1_146_880
WINDOW_FRACTIONS = (0.5, 2.0 / 3.0, 0.75)
LEVEL_COEFFICIENTS = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)
SOURCE_PATHS = (
    "experiments/run_s074_precision.py",
    "experiments/S-074-precision-primary-v1.json",
    "experiments/S-074-precision-primary-v2.json",
    "docs/scientific-contract/S-074_VALIDATION_AMENDMENT.md",
    "docs/scientific-contract/S-074_RESOURCE_CAP_EXTENSION.md",
    "docs/scientific-contract/CONTRACT.md",
    "docs/scientific-contract/validation_registry.json",
    "docs/scientific-contract/validation_registry.schema.json",
    "scripts/validate_validation_registry.py",
    "src/phasemap/simulation/gpu_trajectories.py",
    "src/phasemap/simulation/precision_statistics.py",
    "src/phasemap/simulation/protocols.py",
    "src/phasemap/theory/generator.py",
    "src/phasemap/theory/position_protocols.py",
    "src/phasemap/theory/nonposition_protocols.py",
    "tests/simulation/test_s074_gpu_trajectories.py",
    "tests/simulation/test_s074_precision_statistics.py",
    "tests/simulation/test_s074_precision_study.py",
    "requirements/s074-gpu-lock.txt",
)


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load JSON object {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _semantic_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_text_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def load_plan(path: Path | str = PLAN_PATH) -> dict[str, Any]:
    """Load the prospective plan without performing any work."""

    return _load_json(Path(path))


def _extract_section_7(text: str) -> str:
    match = re.search(
        r"(?ms)^## 7\. Numerical validation\r?\n.*?(?=^## 8\. Publication boundary\r?$)",
        text,
    )
    if match is None:
        raise ValueError("CONTRACT.md Section 7 cannot be located")
    return match.group(0).rstrip("\r\n").replace("\r\n", "\n")


def _registry_context() -> tuple[dict[str, Any], str]:
    registry = _load_json(REGISTRY_PATH)
    section_hash = _sha256_bytes(
        _extract_section_7(CONTRACT_PATH.read_text(encoding="utf-8")).encode("utf-8")
    )
    if (
        registry.get("schema_version") != "1.0.0"
        or registry.get("contract_version") != "0.4"
        or registry.get("status") != "approved"
        or registry.get("normative_section")
        != "docs/scientific-contract/CONTRACT.md#7-numerical-validation"
    ):
        raise ValueError("contract Section 7 registry identity changed")
    primary = registry.get("evidence_tiers", {}).get("primary", {})
    if (
        primary.get("normal_equivalent_quantile") != 2.5758293035
        or primary.get("relative_margin") != 0.01
        or registry.get("margin", {}).get("default_normalized_floor_fraction")
        != 0.005
    ):
        raise ValueError("primary-tier registry rules changed")
    return registry, section_hash


def validate_plan(plan: Mapping[str, Any]) -> None:
    """Fail closed on any change to the reviewed prospective design."""

    if not isinstance(plan, Mapping):
        raise ValueError("plan must be a mapping")
    expected_hash = EXPECTED_PLAN_SEMANTIC_SHA256.get(str(plan.get("plan_id")))
    if expected_hash is None or _sha256_bytes(_semantic_bytes(dict(plan))) != expected_hash:
        raise ValueError("S-074 plan differs from its reviewed semantic identity")
    registry, section_hash = _registry_context()
    if plan.get("contract_section_7_sha256") != section_hash:
        raise ValueError("S-074 contract Section 7 identity changed")
    if (
        plan.get("contract_version") != registry["contract_version"]
        or plan.get("amendment")
        != "docs/scientific-contract/S-074_VALIDATION_AMENDMENT.md"
        or not AMENDMENT_PATH.is_file()
    ):
        raise ValueError("S-074 contract/amendment identity changed")
    if plan.get("pilot_reuse") is not False:
        raise ValueError("the design pilot must remain excluded")
    if plan.get("result_dependent_stopping") is not False:
        raise ValueError("result-dependent stopping is prohibited")
    if plan.get("pilot_seed") == plan.get("production_seed"):
        raise ValueError("pilot and production seeds must be disjoint")
    if plan.get("plan_id") == "S-074-precision-primary-v2" and (
        plan.get("resource_amendment")
        != "docs/scientific-contract/S-074_RESOURCE_CAP_EXTENSION.md"
        or not RESOURCE_AMENDMENT_PATH.is_file()
    ):
        raise ValueError("S-074 v2 resource amendment is missing or changed")


def _plan_scientific_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key not in PLAN_REVISION_FIELDS}


def _expected_plan_hash(plan: Mapping[str, Any]) -> str:
    validate_plan(plan)
    return EXPECTED_PLAN_SEMANTIC_SHA256[str(plan["plan_id"])]


def _slug(value: float) -> str:
    return format(value, ".12g").replace("-", "m").replace(".", "p")


def _tuned_activity(mass: float) -> float:
    numerator = 27.0 * mass * (mass + 6.0) * (3.0 * mass + 2.0)
    denominator = 2.0 * (
        44.0 - 9.0 * mass - 80.0 * mass**2 - 12.0 * mass**3
    )
    if denominator <= 0.0:
        raise ValueError("tuned activity is outside its positive domain")
    return math.sqrt(numerator / denominator)


def make_cases(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand the reviewed parameter design into exactly 41 cells."""

    validate_plan(plan)
    cases: list[dict[str, Any]] = []
    core = plan["core"]
    for protocol in Protocol:
        cases.append(
            {
                "id": f"core-{protocol.value}",
                "group": "core",
                "protocol": protocol.value,
                "M": float(core["M"]),
                "Pe": float(core["Pe"]),
                "rho": float(core["rho"]),
                "mode": "localized"
                if protocol in POSITION_PROTOCOLS
                else "diffusive",
            }
        )
    figure = plan["figure"]
    for rho in figure["rho"]:
        for protocol in Protocol:
            cases.append(
                {
                    "id": f"figure-rho{_slug(float(rho))}-{protocol.value}",
                    "group": "figure",
                    "protocol": protocol.value,
                    "M": float(figure["M"]),
                    "Pe": float(figure["Pe"]),
                    "rho": float(rho),
                    "mode": "localized"
                    if protocol in POSITION_PROTOCOLS
                    else "diffusive",
                }
            )
    tuned = plan["tuned"]
    for mass in tuned["M"]:
        for protocol in (Protocol.V, Protocol.THETA):
            cases.append(
                {
                    "id": f"tuned-M{_slug(float(mass))}-{protocol.value}",
                    "group": "tuned",
                    "protocol": protocol.value,
                    "M": float(mass),
                    "Pe": _tuned_activity(float(mass)),
                    "rho": float(tuned["rho"]),
                    "mode": "diffusive",
                }
            )
    if len(cases) != 41 or len({case["id"] for case in cases}) != 41:
        raise RuntimeError("reviewed S-074 design did not expand to 41 unique cells")
    return cases


def _numeric(expression: Any) -> float:
    value = (
        float(expression.evalf(17))
        if hasattr(expression, "evalf")
        else float(expression)
    )
    if not math.isfinite(value):
        raise ValueError("non-finite exact reference")
    return value


def _reference_data(case: Mapping[str, Any]) -> dict[str, float]:
    protocol = Protocol(case["protocol"])
    M, Pe, rho = case["M"], case["Pe"], case["rho"]
    if protocol in POSITION_PROTOCOLS:
        moments = position_protocol_stationary_second_moments(
            protocol, M, Pe, rho
        )
        return {
            "u_xx": _numeric(moments.orientation_second[0, 0]),
            "speed": _numeric(moments.mean_squared_speed),
            "v_x": _numeric(moments.velocity_mean[0]),
            "vv_xx": _numeric(moments.velocity_second[0, 0]),
            "raw_msd": _numeric(moments.mean_squared_displacement),
            "r_dot_v": _numeric(moments.mean_position_dot_velocity),
            "spatial": _numeric(moments.centered_spatial_variance),
        }
    moments = nonposition_protocol_second_moments(protocol, M, Pe, rho)
    return {
        "u_xx": _numeric(moments.orientation_second[0, 0]),
        "speed": _numeric(moments.stationary_mean_squared_speed),
        "v_x": _numeric(moments.velocity_mean[0]),
        "vv_xx": _numeric(moments.velocity_second[0, 0]),
        "spatial": _numeric(moments.effective_diffusion),
    }


def _row(
    case: Mapping[str, Any], observable: str, data: Mapping[str, float]
) -> dict[str, Any]:
    reference = float(data[observable])
    if observable == "spatial":
        if case["mode"] == "localized":
            observable_class = "stationary_variance"
            characteristic_scale = abs(reference)
        else:
            observable_class = "d_eff"
            characteristic_scale = max(abs(reference), 1.0)
    elif observable == "v_x":
        characteristic_scale = math.sqrt(abs(data["vv_xx"]))
        observable_class = (
            "symmetry_forced_zero" if reference == 0.0 else "v_mean"
        )
    elif observable == "u_xx":
        observable_class, characteristic_scale = "uu", abs(reference)
    elif observable == "speed":
        observable_class, characteristic_scale = "vv", abs(reference)
    elif observable == "raw_msd":
        observable_class, characteristic_scale = "rr", abs(reference)
    elif observable == "r_dot_v":
        observable_class = "r_dot_v"
        characteristic_scale = math.sqrt(
            abs(data["raw_msd"] * data["speed"])
        )
    else:
        raise ValueError(f"unknown observable {observable!r}")
    if not characteristic_scale > 0.0:
        raise ValueError(
            f"nonpositive characteristic scale for {case['id']} {observable}"
        )
    precision_scale = abs(reference) if reference != 0.0 else characteristic_scale
    relative = (
        0.0
        if observable_class == "symmetry_forced_zero"
        else 0.01 * abs(reference)
    )
    return {
        "id": f"{case['id']}:{observable}",
        "case_id": case["id"],
        "observable": observable,
        "observable_class": observable_class,
        "reference": reference,
        "characteristic_scale": characteristic_scale,
        "precision_scale": precision_scale,
        "epsilon": 0.005 * characteristic_scale + relative,
    }


def reference_rows(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the fixed paper-facing rows for one cell."""

    protocol = Protocol(case["protocol"])
    if case["group"] == "core":
        names = ["u_xx", "speed", "spatial"]
        if protocol in NONPOSITION_PROTOCOLS:
            names.append("v_x")
        if protocol in (Protocol.PV, Protocol.PV_THETA):
            names.extend(("raw_msd", "r_dot_v"))
    elif case["group"] == "figure":
        names = ["spatial"]
        if protocol in NONPOSITION_PROTOCOLS:
            names.append("v_x")
    elif case["group"] == "tuned":
        names = ["spatial", "v_x"]
    else:
        raise ValueError("unknown S-074 case group")
    data = _reference_data(case)
    return [_row(case, name, data) for name in names]


def step_for_case(case: Mapping[str, Any], plan: Mapping[str, Any]) -> float:
    """Return the largest inverse power-of-two no greater than the fixed bound."""

    limit = min(
        1.0 / int(plan["step_minimum_inverse"]),
        float(case["M"]) / float(plan["step_rate_factor"]),
        1.0 / (float(plan["step_rate_factor"]) * float(case["rho"])),
    )
    inverse = 1 << max(0, math.ceil(math.log2(1.0 / limit)))
    return 1.0 / inverse


def record_times(horizon: float, plan: Mapping[str, Any]) -> np.ndarray:
    """Return the fixed inclusive record grid."""

    value = float(horizon)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("horizon must be finite and positive")
    count = int(plan["record_count"])
    if count < 2:
        raise ValueError("record_count must be at least two")
    return np.linspace(0.0, value, count, dtype=np.float64)


@lru_cache(maxsize=64)
def _numeric_generator(
    protocol_value: str, M: float, Pe: float, rho: float
) -> tuple[np.ndarray, tuple[str, ...]]:
    symbols = Symbols.create()
    system = second_order_moment_system(symbols, Protocol(protocol_value))
    substitutions = {
        symbols.inertia: M,
        symbols.activity: Pe,
        symbols.reset_rate: rho,
    }
    matrix = np.asarray(system.matrix.subs(substitutions), dtype=np.float64)
    return matrix, system.names


def propagate_reference_moments(
    case: Mapping[str, Any], times: Sequence[float] | np.ndarray
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Propagate the exact closed 28-moment system from the declared state."""

    from scipy.linalg import expm

    clock = np.asarray(times, dtype=np.float64)
    if clock.ndim != 1 or clock.size == 0 or np.any(~np.isfinite(clock)):
        raise ValueError("times must be a finite nonempty vector")
    if np.any(clock < 0.0) or np.any(np.diff(clock) < 0.0):
        raise ValueError("times must be nonnegative and nondecreasing")
    matrix, names = _numeric_generator(
        str(case["protocol"]),
        float(case["M"]),
        float(case["Pe"]),
        float(case["rho"]),
    )
    initial = np.zeros(len(names), dtype=np.float64)
    initial[names.index("one")] = 1.0
    initial[names.index("u_x")] = 1.0
    initial[names.index("uu_xx")] = 1.0
    propagated = np.vstack([expm(matrix * value) @ initial for value in clock])
    if np.any(~np.isfinite(propagated)):
        raise RuntimeError(f"non-finite moment propagation for {case['id']}")
    return propagated, names


def _finite_functionals(
    case: Mapping[str, Any], times: np.ndarray, moments: np.ndarray, names: Sequence[str],
    window_fraction: float = WINDOW_FRACTIONS[0],
) -> dict[str, float]:
    index = {name: position for position, name in enumerate(names)}
    window = np.flatnonzero(times >= window_fraction * times[-1])
    linear = {
        "u_xx": moments[:, index["uu_xx"]],
        "speed": moments[:, index["vv_xx"]] + moments[:, index["vv_yy"]],
        "v_x": moments[:, index["v_x"]],
        "raw_msd": moments[:, index["rr_xx"]] + moments[:, index["rr_yy"]],
        "r_dot_v": moments[:, index["rv_xx"]] + moments[:, index["rv_yy"]],
    }
    output = {name: float(values[window].mean()) for name, values in linear.items()}
    centered_msd = (
        linear["raw_msd"]
        - moments[:, index["r_x"]] ** 2
        - moments[:, index["r_y"]] ** 2
    )
    if case["mode"] == "localized":
        output["spatial"] = float(centered_msd[window].mean())
    else:
        selected = times[window]
        centered = selected - selected.mean()
        output["spatial"] = float(
            0.25 * np.dot(centered, centered_msd[window]) / np.dot(centered, centered)
        )
    return output


def freeze_case(case: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Expand one cell and deterministically qualify its finite horizon."""

    rows = reference_rows(case)
    initial = max(64.0, 24.0 / float(case["rho"]), 16.0 * float(case["M"]))
    horizon = float(2 * math.ceil(initial / 2.0))
    maximum = float(plan["maximum_horizon"])
    q = float(_registry_context()[0]["evidence_tiers"]["primary"]["normal_equivalent_quantile"])
    while True:
        times = record_times(horizon, plan)
        moments, names = propagate_reference_moments(case, times)
        finite_windows = [
            _finite_functionals(case, times, moments, names, fraction)
            for fraction in WINDOW_FRACTIONS
        ]
        frozen_rows: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["q"] = q
            item["tau"] = min(
                float(plan["target_relative_se"]) * item["precision_scale"],
                item["epsilon"] / (float(plan["interval_se_budget_divisor"]) * q),
            )
            item["finite_horizon_values"] = [
                values[item["observable"]] for values in finite_windows
            ]
            item["transient_residuals"] = [
                abs(value - item["reference"])
                for value in item["finite_horizon_values"]
            ]
            item["finite_horizon_value"] = item["finite_horizon_values"][0]
            item["transient_residual"] = max(item["transient_residuals"])
            frozen_rows.append(item)
        if all(
            row["transient_residual"]
            <= row["epsilon"] / float(plan["transient_margin_divisor"])
            for row in frozen_rows
        ):
            break
        if horizon * 2.0 > maximum:
            raise RuntimeError(
                f"{case['id']} cannot meet the deterministic transient budget by T={maximum:g}"
            )
        horizon *= 2.0
    dummy = np.zeros((3, times.size, 3, 5), dtype=np.float64)
    _, layout = build_features(dummy, times, str(case["mode"]))
    return {
        **dict(case),
        "step": step_for_case(case, plan),
        "horizon": horizon,
        "record_times": times.tolist(),
        "rows": frozen_rows,
        "layout": layout,
        "layout_sha256": _sha256_bytes(_semantic_bytes(layout)),
    }


def classify_row(
    row: Mapping[str, Any], *, value: float, se: float, b_disc: float, b_window: float,
    transient: float = 0.0,
) -> dict[str, Any]:
    """Apply the fixed pointwise expanded-interval rule and separate precision rule."""

    values = (value, se, b_disc, b_window, transient)
    if any(not math.isfinite(float(item)) for item in values) or any(
        float(item) < 0.0 for item in values[1:]
    ):
        raise ValueError("classification inputs must be finite and envelopes nonnegative")
    q = float(row.get("q", 2.5758293035))
    discrepancy = float(value) - float(row["reference"])
    b_late = max(float(b_window), float(transient))
    b_total = float(b_disc) + b_late
    lower = discrepancy - q * float(se) - b_total
    upper = discrepancy + q * float(se) + b_total
    epsilon = float(row["epsilon"])
    if lower >= -epsilon and upper <= epsilon:
        classification = "validated"
    elif upper < -epsilon or lower > epsilon:
        classification = "contradicted"
    else:
        classification = "unresolved"
    precision_pass = float(se) <= min(
        0.01 * float(row["precision_scale"]), epsilon / (3.0 * q)
    )
    return {
        "classification": classification,
        "precision_pass": precision_pass,
        "discrepancy": discrepancy,
        "interval": [lower, upper],
        "b_late": b_late,
        "b_total": b_total,
    }


def source_manifest() -> dict[str, str]:
    """Hash only the reviewed normalized-text scientific implementation surface."""

    manifest: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"required source is missing: {relative}")
        manifest[relative] = _sha256_bytes(_canonical_text_bytes(path))
    return manifest


def source_manifest_digest(manifest: Mapping[str, str] | None = None) -> str:
    return _sha256_bytes(_semantic_bytes(dict(manifest or source_manifest())))


def _atomic_replace(path: Path, writer: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_npz_immutable(path: Path | str, arrays: Mapping[str, Any]) -> str:
    """Atomically create an NPZ or verify an identical existing artifact."""

    target = Path(path)
    normalized = {name: np.asarray(value) for name, value in arrays.items()}
    if target.exists():
        try:
            with np.load(target, allow_pickle=False) as archive:
                identical = set(archive.files) == set(normalized) and all(
                    archive[name].dtype == value.dtype
                    and archive[name].shape == value.shape
                    and np.array_equal(archive[name], value)
                    for name, value in normalized.items()
                )
        except Exception as error:
            raise RuntimeError(f"immutable artifact is corrupt: {target}: {error}") from error
        if not identical:
            raise RuntimeError(f"immutable artifact differs: {target}")
        return _file_sha256(target)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.candidate")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("wb") as handle:
            np.savez(handle, **normalized)
            handle.flush()
            os.fsync(handle.fileno())
        candidate_hash = _file_sha256(temporary)
        os.replace(temporary, target)
        return candidate_hash
    finally:
        if temporary.exists():
            temporary.unlink()


def _save_json_immutable(path: Path | str, payload: Any) -> str:
    target = Path(path)
    content = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    digest = _sha256_bytes(content)
    if target.exists():
        if _file_sha256(target) != digest:
            raise RuntimeError(f"immutable artifact differs: {target}")
        return digest
    _atomic_replace(target, lambda handle: handle.write(content))
    return digest


def merge_accumulator_states(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Merge independent Chan accumulator states without path materialization."""

    if not states:
        raise ValueError("at least one accumulator state is required")
    total: FeatureAccumulator | None = None
    for state in states:
        current = FeatureAccumulator(int(state["n"]), state["mean"], state["m2"])
        if total is None:
            total = FeatureAccumulator(current.n, current.mean.copy(), current.m2.copy())
            continue
        if total.mean.shape != current.mean.shape:
            raise ValueError("accumulator feature widths differ")
        delta = current.mean - total.mean
        count = total.n + current.n
        total.m2 += current.m2 + np.outer(delta, delta) * (total.n * current.n / count)
        total.mean += delta * (current.n / count)
        total.n = count
    assert total is not None
    return {"n": total.n, "mean": total.mean, "m2": total.m2}


def allocate_cell(
    plan: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], diagnostics: Mapping[str, Any]
) -> dict[str, Any]:
    """Project one fixed production count from pilot SE only."""

    q = 2.5758293035
    diagnostic_ids = [item["id"] for item in diagnostics["rows"]]
    expected_ids = [row["id"] for row in rows]
    if len(set(diagnostic_ids)) != len(diagnostic_ids) or set(diagnostic_ids) != set(expected_ids):
        raise ValueError("pilot diagnostic row identities do not match the frozen rows")
    by_id = {item["id"]: item for item in diagnostics["rows"]}
    errors: list[float] = []
    targets: list[float] = []
    for row in rows:
        errors.append(float(by_id[row["id"]]["fine"]["se"]))
        targets.append(
            min(
                float(plan["target_relative_se"]) * float(row["precision_scale"]),
                float(row["epsilon"])
                / (float(plan["interval_se_budget_divisor"]) * q),
            )
        )
    projected = project_pilot_size(
        int(plan["pilot_n"]), errors, targets,
        target_fraction=1.0,
        inflation=float(plan["sample_inflation"]),
        chunk=int(plan["batch_n"]),
        min_n=int(plan["minimum_cell_n"]),
        max_n=int(plan["maximum_cell_n"]),
    )
    qualified = bool(diagnostics.get("qualification_pass", False))
    if not qualified:
        projected = {**projected, "feasible": False, "n": None}
    return {**projected, "targets": targets, "qualification_pass": qualified}


def _environment_manifest() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy": np.__version__,
    }
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="CUDA path could not be detected.*")
            import cupy as cp

        device = cp.cuda.Device()
        properties = cp.cuda.runtime.getDeviceProperties(device.id)
        result.update(
            {
                "cupy": cp.__version__,
                "cuda_runtime": int(cp.cuda.runtime.runtimeGetVersion()),
                "cuda_driver": int(cp.cuda.runtime.driverGetVersion()),
                "gpu_device_id": int(device.id),
                "gpu_name": properties["name"].decode()
                if isinstance(properties["name"], bytes)
                else str(properties["name"]),
                "gpu_total_memory": int(properties["totalGlobalMem"]),
            }
        )
    except Exception as error:  # pragma: no cover - exercised on CPU-only hosts
        result["cuda_probe_error"] = f"{type(error).__name__}: {error}"
    return result


def _output_path(plan: Mapping[str, Any], output_dir: Path | str | None) -> Path:
    return Path(output_dir) if output_dir is not None else ROOT / str(plan["output_directory"])


def freeze_plan(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None
) -> dict[str, Any]:
    """Create the immutable expanded pre-sampling carrier."""

    plan = load_plan(plan_path)
    validate_plan(plan)
    sources = source_manifest()
    environment = _environment_manifest()
    required_gpu_fields = {
        "cupy", "cuda_runtime", "cuda_driver", "gpu_device_id", "gpu_name",
        "gpu_total_memory",
    }
    if "cuda_probe_error" in environment or not required_gpu_fields <= set(environment):
        raise RuntimeError("cannot freeze a GPU production carrier without a live GPU identity")
    registry, section_hash = _registry_context()
    cases = [freeze_case(case, plan) for case in make_cases(plan)]
    if len(cases) != 41 or sum(len(case["rows"]) for case in cases) != 80:
        raise RuntimeError("expanded freeze does not contain 41 cells and 80 rows")
    core = {
        "schema": "phasemap.s074.freeze.v1",
        "plan": dict(plan),
        "plan_semantic_sha256": _sha256_bytes(_semantic_bytes(dict(plan))),
        "source_manifest": sources,
        "source_manifest_sha256": source_manifest_digest(sources),
        "environment": environment,
        "environment_sha256": _sha256_bytes(_semantic_bytes(environment)),
        "execution_backend": "gpu",
        "contract_section_7_sha256": section_hash,
        "amendment_sha256": _sha256_bytes(_canonical_text_bytes(AMENDMENT_PATH)),
        "registry_sha256": _sha256_bytes(_canonical_text_bytes(REGISTRY_PATH)),
        "registry_schema_sha256": _sha256_bytes(
            _canonical_text_bytes(ROOT / "docs/scientific-contract/validation_registry.schema.json")
        ),
        "registry_identity": {
            "schema_version": registry["schema_version"],
            "contract_version": registry["contract_version"],
            "status": registry["status"],
            "normative_section": registry["normative_section"],
        },
        "seed_domains": {
            "pilot": int(plan["pilot_seed"]),
            "production": int(plan["production_seed"]),
            "bootstrap": int(plan["bootstrap_seed"]),
        },
        "batch_schedule": {
            "pilot_n": int(plan["pilot_n"]),
            "production_batch_n": int(plan["batch_n"]),
            "pilot_reuse": False,
            "result_dependent_stopping": False,
        },
        "cases": cases,
    }
    payload = {**core, "freeze_identity_sha256": _sha256_bytes(_semantic_bytes(core))}
    target = _output_path(plan, output_dir) / "freeze.json"
    file_hash = _save_json_immutable(target, payload)
    return {**payload, "freeze_file_sha256": file_hash}


def _load_freeze(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None
) -> tuple[dict[str, Any], Path, str]:
    plan = load_plan(plan_path)
    validate_plan(plan)
    path = _output_path(plan, output_dir) / "freeze.json"
    freeze = _load_json(path)
    identity = freeze.pop("freeze_identity_sha256", None)
    actual_identity = _sha256_bytes(_semantic_bytes(freeze))
    freeze["freeze_identity_sha256"] = identity
    if identity != actual_identity:
        raise RuntimeError("freeze identity is corrupt")
    if freeze.get("plan_semantic_sha256") != _expected_plan_hash(plan):
        raise RuntimeError("freeze plan identity changed")
    current_sources = source_manifest()
    if freeze.get("source_manifest") != current_sources:
        raise RuntimeError("scientific source differs from the immutable freeze")
    if freeze.get("source_manifest_sha256") != source_manifest_digest(current_sources):
        raise RuntimeError("freeze source manifest identity is corrupt")
    if len(freeze.get("cases", [])) != 41 or sum(
        len(case.get("rows", [])) for case in freeze.get("cases", [])
    ) != 80:
        raise RuntimeError("freeze cell/row expansion is corrupt")
    return freeze, path.parent, _file_sha256(path)


def _freeze_identity(freeze: Mapping[str, Any]) -> str:
    core = {key: value for key, value in freeze.items() if key != "freeze_identity_sha256"}
    return _sha256_bytes(_semantic_bytes(core))


def _pilot_evidence_context(
    freeze: Mapping[str, Any], base: Path, freeze_hash: str,
) -> tuple[dict[str, Any], Path, str]:
    """Resolve either this plan's pilot or v2's pinned read-only origin."""

    plan = freeze["plan"]
    origin_directory = plan.get("pilot_origin_directory")
    if origin_directory is None:
        return dict(freeze), base, freeze_hash
    origin_path = (ROOT / str(origin_directory) / "freeze.json").resolve()
    try:
        origin_path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise RuntimeError("pilot origin escapes the repository") from error
    expected_hash = str(plan.get("pilot_origin_freeze_sha256", ""))
    if not origin_path.is_file() or _file_sha256(origin_path) != expected_hash:
        raise RuntimeError("pinned pilot-origin freeze hash mismatch")
    origin = _load_json(origin_path)
    if origin.get("freeze_identity_sha256") != _freeze_identity(origin):
        raise RuntimeError("pinned pilot-origin internal identity is corrupt")
    origin_plan = origin.get("plan")
    if not isinstance(origin_plan, dict):
        raise RuntimeError("pinned pilot-origin plan is missing")
    validate_plan(origin_plan)
    if origin.get("plan_semantic_sha256") != _expected_plan_hash(origin_plan):
        raise RuntimeError("pinned pilot-origin plan identity is corrupt")
    if _plan_scientific_payload(plan) != _plan_scientific_payload(origin_plan):
        raise RuntimeError("v2 changes a scientific field outside the resource allowlist")
    if origin.get("environment") != freeze.get("environment") or origin.get(
        "environment_sha256"
    ) != freeze.get("environment_sha256"):
        raise RuntimeError("v2 producer environment differs from its pilot origin")
    if origin.get("cases") != freeze.get("cases"):
        raise RuntimeError("v2 cells, layouts, rows, steps, or horizons differ from pilot origin")
    origin_sources = origin.get("source_manifest")
    active_sources = freeze.get("source_manifest")
    if not isinstance(origin_sources, dict) or not isinstance(active_sources, dict):
        raise RuntimeError("pilot-origin source manifests are missing")
    if origin.get("source_manifest_sha256") != source_manifest_digest(origin_sources):
        raise RuntimeError("pilot-origin source manifest identity is corrupt")
    allowed_source_changes = {
        "experiments/run_s074_precision.py",
        "tests/simulation/test_s074_precision_study.py",
        "experiments/S-074-precision-primary-v1.json",
        "experiments/S-074-precision-primary-v2.json",
    }
    for relative, digest in origin_sources.items():
        if relative not in allowed_source_changes and active_sources.get(relative) != digest:
            raise RuntimeError(f"source differs from pilot origin: {relative}")
    if any(relative not in origin_sources for relative in COMMON_NUMERICAL_SOURCES):
        raise RuntimeError("pilot-origin numerical source inventory is incomplete")
    if len(origin.get("cases", [])) != 41 or sum(
        len(case.get("rows", [])) for case in origin.get("cases", [])
    ) != 80:
        raise RuntimeError("pilot-origin freeze is not the exact 41-cell/80-row design")
    return origin, origin_path.parent, expected_hash


def _case_map(freeze: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case["id"]): dict(case) for case in freeze["cases"]}


def _enforce_producer_environment(freeze: Mapping[str, Any], backend: str) -> None:
    if backend != freeze.get("execution_backend") or backend != "gpu":
        raise RuntimeError("scientific sampling requires the frozen GPU backend")
    current = _environment_manifest()
    if _sha256_bytes(_semantic_bytes(current)) != freeze.get("environment_sha256"):
        raise RuntimeError("producer environment differs from the immutable freeze")


def _select_cases(
    freeze: Mapping[str, Any], requested: Sequence[str] | None
) -> list[dict[str, Any]]:
    cases = _case_map(freeze)
    if not requested:
        return list(cases.values())
    missing = [case_id for case_id in requested if case_id not in cases]
    if missing:
        raise ValueError(f"unknown cell ids: {missing}")
    if len(set(requested)) != len(requested):
        raise ValueError("cell ids must not repeat")
    return [cases[case_id] for case_id in requested]


def _stats_dict(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "n": int(state["n"]),
        "mean": np.asarray(state["mean"], dtype=np.float64).tolist(),
        "m2": np.asarray(state["m2"], dtype=np.float64).tolist(),
    }


def _state_arrays(accumulator: FeatureAccumulator | Mapping[str, Any]) -> dict[str, np.ndarray]:
    if isinstance(accumulator, FeatureAccumulator):
        state = {"n": accumulator.n, "mean": accumulator.mean, "m2": accumulator.m2}
    else:
        state = accumulator
    return {
        "n": np.asarray(int(state["n"]), dtype=np.int64),
        "mean": np.asarray(state["mean"], dtype=np.float64),
        "m2": np.asarray(state["m2"], dtype=np.float64),
    }


def _load_state(path: Path) -> dict[str, Any]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"n", "mean", "m2"}:
                raise ValueError("unexpected accumulator arrays")
            state = {
                "n": int(np.asarray(archive["n"]).item()),
                "mean": np.asarray(archive["mean"], dtype=np.float64),
                "m2": np.asarray(archive["m2"], dtype=np.float64),
            }
        FeatureAccumulator(state["n"], state["mean"], state["m2"])
        return state
    except Exception as error:
        raise RuntimeError(f"corrupt accumulator {path}: {error}") from error


def _paired(
    stats: Mapping[str, Any], layout: Mapping[str, Any], observable: str,
    coefficients: Sequence[float], window: int = 0,
) -> dict[str, float]:
    return paired_difference(
        dict(stats), dict(layout),
        [{"observable": observable, "window": window, "level_coeffs": coefficients}],
    )


def _diagnostics(
    case: Mapping[str, Any], state: Mapping[str, Any], features: np.ndarray | None,
    plan: Mapping[str, Any], *, bootstrap: bool,
) -> dict[str, Any]:
    stats = _stats_dict(state)
    layout = dict(case["layout"])
    q = 2.5758293035
    rows: list[dict[str, Any]] = []
    qualification_pass = True
    for row in case["rows"]:
        estimates = [
            [estimate(stats, layout, row["observable"], window, coeffs)
             for window in range(3)]
            for coeffs in LEVEL_COEFFICIENTS
        ]
        first = _paired(stats, layout, row["observable"], (1.0, -1.0, 0.0))
        second = _paired(stats, layout, row["observable"], (1.0, -1.5, 0.5))
        first_envelope = abs(first["value"]) + q * first["se"]
        second_envelope = abs(second["value"]) + q * second["se"]
        first_limit = float(row["epsilon"]) / float(plan["step_bias_margin_divisor"])
        second_limit = float(row["epsilon"]) / float(plan["richardson_residual_margin_divisor"])
        first_pass = bool(first_envelope <= first_limit)
        second_pass = bool(second_envelope <= second_limit)
        row_pass = first_pass and second_pass
        item: dict[str, Any] = {
            "id": row["id"],
            "observable": row["observable"],
            "fine": estimates[0][0],
            "level_window_estimates": estimates,
            "b1": {**first, "envelope": first_envelope, "limit": first_limit,
                   "pass": first_pass},
            "b2": {**second, "envelope": second_envelope, "limit": second_limit,
                   "pass": second_pass},
            "step_qualification_pass": row_pass,
        }
        if bootstrap and row["observable"] == "spatial":
            if features is None:
                raise ValueError("pilot bootstrap requires retained features")
            boot = bootstrap_se(
                features, layout, "spatial", reps=int(plan["bootstrap_replicates"]),
                seed=int(plan["bootstrap_seed"]),
            )
            jackknife_se = float(estimates[0][0]["se"])
            ratio = jackknife_se / boot["se"] if boot["se"] > 0.0 else math.inf
            lower, upper = (float(value) for value in plan["bootstrap_ratio_bounds"])
            half_tolerance = float(plan["bootstrap_half_relative_tolerance"])
            bootstrap_pass = bool(
                lower <= ratio <= upper
                and abs(boot["first_half_se"] / boot["se"] - 1.0) <= half_tolerance
                and abs(boot["second_half_se"] / boot["se"] - 1.0) <= half_tolerance
            )
            item["bootstrap"] = {
                **boot, "jackknife_se": jackknife_se, "jackknife_bootstrap_ratio": ratio,
                "pass": bootstrap_pass,
            }
            row_pass = row_pass and bootstrap_pass
        item["qualification_pass"] = row_pass
        qualification_pass = qualification_pass and row_pass
        rows.append(item)
    return {
        "schema": "phasemap.s074.diagnostics.v1",
        "phase": "pilot" if bootstrap else "production",
        "case_id": case["id"],
        "n": int(state["n"]),
        "rows": rows,
        "qualification_pass": qualification_pass,
    }


def _simulate_features(
    case: Mapping[str, Any], *, n: int, seed: int, path_offset: int, backend: str
) -> np.ndarray:
    from phasemap.simulation.gpu_trajectories import simulate_paths

    paths = simulate_paths(
        float(case["M"]), float(case["Pe"]), float(case["rho"]),
        Protocol(case["protocol"]), n=n, seed=seed, path_offset=path_offset,
        end_time=float(case["horizon"]), step=float(case["step"]),
        record_times=np.asarray(case["record_times"], dtype=np.float64), backend=backend,
    )
    features, layout = build_features(paths, case["record_times"], case["mode"])
    if layout != case["layout"] or _sha256_bytes(_semantic_bytes(layout)) != case["layout_sha256"]:
        raise RuntimeError(f"feature layout drift for {case['id']}")
    return features


def _receipt_expected(
    *, phase: str, case: Mapping[str, Any], seed: int, offset: int, n: int,
    freeze_hash: str, source_hash: str, environment_hash: str, backend: str,
) -> dict[str, Any]:
    return {
        "schema": "phasemap.s074.batch-receipt.v1",
        "phase": phase,
        "case_id": case["id"],
        "seed": int(seed),
        "path_offset": int(offset),
        "n": int(n),
        "freeze_file_sha256": freeze_hash,
        "source_manifest_sha256": source_hash,
        "environment_sha256": environment_hash,
        "execution_backend": backend,
        "layout_sha256": case["layout_sha256"],
    }


def _verify_receipt(
    receipt_path: Path, expected: Mapping[str, Any], artifacts: Mapping[str, Path]
) -> dict[str, Any] | None:
    if not receipt_path.exists():
        return None
    receipt = _load_json(receipt_path)
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise RuntimeError(f"receipt metadata mismatch at {receipt_path}: {key}")
    declared = receipt.get("artifacts")
    if not isinstance(declared, dict) or set(declared) != set(artifacts):
        raise RuntimeError(f"receipt artifact inventory mismatch at {receipt_path}")
    for name, path in artifacts.items():
        if not path.is_file() or _file_sha256(path) != declared[name]:
            raise RuntimeError(f"receipt artifact hash mismatch: {path}")
    return receipt


def _pilot_paths(base: Path, case_id: str) -> dict[str, Path]:
    directory = base / "pilot" / case_id
    return {
        "features": directory / "features.npz",
        "accumulator": directory / "accumulator.npz",
        "layout": directory / "layout.json",
        "diagnostics": directory / "diagnostics.json",
        "receipt": directory / "receipt.json",
    }


def _validate_pilot_inventory(paths: Mapping[str, Path]) -> None:
    directory = paths["receipt"].parent
    if not directory.exists():
        return
    allowed = {path.name for path in paths.values()}
    for path in directory.iterdir():
        if path.name in allowed:
            continue
        if re.fullmatch(
            r"\.(?:features|accumulator)\.npz\.\d+\.candidate"
            r"|\.(?:layout|diagnostics|receipt)\.json\.\d+\.tmp",
            path.name,
        ):
            continue
        raise RuntimeError(f"unexpected pilot artifact: {path}")


def _run_pilot_case(
    case: Mapping[str, Any], plan: Mapping[str, Any], base: Path, freeze_hash: str,
    source_hash: str, environment_hash: str, backend: str,
) -> dict[str, Any]:
    paths = _pilot_paths(base, str(case["id"]))
    _validate_pilot_inventory(paths)
    expected = _receipt_expected(
        phase="pilot", case=case, seed=int(plan["pilot_seed"]), offset=0,
        n=int(plan["pilot_n"]), freeze_hash=freeze_hash, source_hash=source_hash,
        environment_hash=environment_hash, backend="gpu",
    )
    verified = _verify_receipt(
        paths["receipt"], expected,
        {name: paths[name] for name in ("features", "accumulator", "layout", "diagnostics")},
    )
    if verified is not None:
        return _load_json(paths["diagnostics"])
    # A missing receipt denotes an interrupted transaction. Recompute with the
    # identical stream and let immutable saves verify any completed components.
    features = _simulate_features(
        case, n=int(plan["pilot_n"]), seed=int(plan["pilot_seed"]),
        path_offset=0, backend=backend,
    )
    accumulator = FeatureAccumulator().add(features)
    state = {"n": accumulator.n, "mean": accumulator.mean, "m2": accumulator.m2}
    diagnostics = _diagnostics(case, state, features, plan, bootstrap=True)
    hashes = {
        "features": save_npz_immutable(paths["features"], {"features": features}),
        "accumulator": save_npz_immutable(paths["accumulator"], _state_arrays(state)),
        "layout": _save_json_immutable(paths["layout"], case["layout"]),
        "diagnostics": _save_json_immutable(paths["diagnostics"], diagnostics),
    }
    _save_json_immutable(paths["receipt"], {**expected, "artifacts": hashes})
    return diagnostics


def run_pilot(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None,
    *, cell_ids: Sequence[str] | None = None, backend: str = "gpu",
) -> list[dict[str, Any]]:
    freeze, base, freeze_hash = _load_freeze(plan_path, output_dir)
    if freeze["plan"].get("pilot_origin_directory") is not None:
        origin, origin_base, origin_hash = _pilot_evidence_context(
            freeze, base, freeze_hash
        )
        selected_ids = {case["id"] for case in _select_cases(freeze, cell_ids)}
        outputs: list[dict[str, Any]] = []
        failed: list[str] = []
        total_rows = 0
        for case in freeze["cases"]:
            diagnostics = _verified_origin_pilot_diagnostics(
                case, origin, origin_base, origin_hash
            )
            total_rows += len(diagnostics["rows"])
            if not diagnostics["qualification_pass"]:
                failed.append(case["id"])
            if case["id"] in selected_ids:
                outputs.append(diagnostics)
            print(f"pilot origin verified: {case['id']}", flush=True)
        if total_rows != 80 or failed:
            raise RuntimeError(
                f"pinned pilot origin is incomplete or unqualified: rows={total_rows}, failed={failed}"
            )
        return outputs
    _enforce_producer_environment(freeze, backend)
    plan = freeze["plan"]
    outputs: list[dict[str, Any]] = []
    failed: list[str] = []
    for case in _select_cases(freeze, cell_ids):
        diagnostics = _run_pilot_case(
            case, plan, base, freeze_hash, freeze["source_manifest_sha256"],
            freeze["environment_sha256"], backend,
        )
        outputs.append(diagnostics)
        if not diagnostics["qualification_pass"]:
            failed.append(case["id"])
        print(f"pilot complete: {case['id']}", flush=True)
    if failed:
        raise RuntimeError(f"pilot qualification failed with preserved data: {failed}")
    return outputs


def _verified_pilot_diagnostics(
    case: Mapping[str, Any], plan: Mapping[str, Any], base: Path, freeze_hash: str,
    source_hash: str, environment_hash: str,
) -> dict[str, Any]:
    paths = _pilot_paths(base, str(case["id"]))
    _validate_pilot_inventory(paths)
    expected = _receipt_expected(
        phase="pilot", case=case, seed=int(plan["pilot_seed"]), offset=0,
        n=int(plan["pilot_n"]), freeze_hash=freeze_hash, source_hash=source_hash,
        environment_hash=environment_hash, backend="gpu",
    )
    receipt = _verify_receipt(
        paths["receipt"], expected,
        {name: paths[name] for name in ("features", "accumulator", "layout", "diagnostics")},
    )
    if receipt is None:
        raise RuntimeError(f"missing completed pilot for {case['id']}")
    diagnostics = _load_json(paths["diagnostics"])
    if diagnostics.get("case_id") != case["id"] or diagnostics.get("n") != int(plan["pilot_n"]):
        raise RuntimeError(f"pilot diagnostics metadata mismatch for {case['id']}")
    row_ids = [row.get("id") for row in diagnostics.get("rows", [])]
    expected_ids = [row["id"] for row in case["rows"]]
    if row_ids != expected_ids or len(set(row_ids)) != len(row_ids):
        raise RuntimeError(f"pilot diagnostic rows differ from the freeze for {case['id']}")
    return diagnostics


def _verified_origin_pilot_diagnostics(
    case: Mapping[str, Any], origin: Mapping[str, Any], origin_base: Path,
    origin_hash: str,
) -> dict[str, Any]:
    return _verified_pilot_diagnostics(
        case, origin["plan"], origin_base, origin_hash,
        origin["source_manifest_sha256"], origin["environment_sha256"],
    )


def _verified_pilot_set(
    freeze: Mapping[str, Any], base: Path, freeze_hash: str,
) -> dict[str, dict[str, Any]]:
    origin, origin_base, origin_hash = _pilot_evidence_context(
        freeze, base, freeze_hash
    )
    diagnostics: dict[str, dict[str, Any]] = {}
    total_rows = 0
    require_qualified = freeze["plan"].get("pilot_origin_directory") is not None
    for case in freeze["cases"]:
        item = _verified_origin_pilot_diagnostics(
            case, origin, origin_base, origin_hash
        )
        if require_qualified and item.get("qualification_pass") is not True:
            raise RuntimeError(f"pilot qualification failed for {case['id']}")
        diagnostics[case["id"]] = item
        total_rows += len(item["rows"])
    if len(diagnostics) != 41 or total_rows != 80:
        raise RuntimeError("pilot evidence is not exactly 41 qualified cells and 80 rows")
    return diagnostics


def allocate_production(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None
) -> dict[str, Any]:
    """Freeze per-cell production counts from every excluded pilot."""

    freeze, base, freeze_hash = _load_freeze(plan_path, output_dir)
    plan = freeze["plan"]
    pilot_diagnostics = _verified_pilot_set(freeze, base, freeze_hash)
    allocations: list[dict[str, Any]] = []
    total = 0
    feasible = True
    for case in freeze["cases"]:
        diagnostics = pilot_diagnostics[case["id"]]
        outcome = allocate_cell(plan, case["rows"], diagnostics)
        item = {"case_id": case["id"], **outcome}
        allocations.append(item)
        feasible = feasible and bool(outcome["feasible"])
        if outcome["n"] is not None:
            total += int(outcome["n"])
    if total > int(plan["maximum_total_n"]):
        feasible = False
    if plan["plan_id"] == "S-074-precision-primary-v2":
        required = [int(item["required_n"]) for item in allocations]
        if sum(required) != EXPECTED_V2_REQUIRED_TOTAL or max(required) != EXPECTED_V2_REQUIRED_MAX:
            raise RuntimeError("v2 pilot projection differs from its authorized allocation identity")
    payload = {
        "schema": "phasemap.s074.allocation.v1",
        "freeze_file_sha256": freeze_hash,
        "source_manifest_sha256": freeze["source_manifest_sha256"],
        "pilot_excluded": True,
        "fixed_before_production": True,
        "total_n": total,
        "maximum_total_n": int(plan["maximum_total_n"]),
        "feasible": feasible,
        "cells": allocations,
    }
    _save_json_immutable(base / "allocation.json", payload)
    if not feasible:
        raise RuntimeError("fixed S-074 allocation is infeasible; allocation data preserved")
    return payload


def _load_allocation(
    freeze: Mapping[str, Any], base: Path, freeze_hash: str
) -> dict[str, Any]:
    allocation = _load_json(base / "allocation.json")
    if (
        allocation.get("schema") != "phasemap.s074.allocation.v1"
        or allocation.get("freeze_file_sha256") != freeze_hash
        or allocation.get("source_manifest_sha256") != freeze["source_manifest_sha256"]
        or allocation.get("pilot_excluded") is not True
        or allocation.get("fixed_before_production") is not True
        or allocation.get("feasible") is not True
    ):
        raise RuntimeError("allocation is missing, infeasible, or bound to another freeze")
    case_ids = [case["id"] for case in freeze["cases"]]
    cells = allocation.get("cells", [])
    if [item.get("case_id") for item in cells] != case_ids:
        raise RuntimeError("allocation cell order/identity differs from the freeze")
    total = 0
    for item in cells:
        n = item.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or n < int(freeze["plan"]["minimum_cell_n"]):
            raise RuntimeError("invalid fixed allocation count")
        if n % int(freeze["plan"]["batch_n"]):
            raise RuntimeError("fixed allocation is not batch aligned")
        total += n
    if total != allocation.get("total_n") or total > int(freeze["plan"]["maximum_total_n"]):
        raise RuntimeError("fixed allocation total is invalid")
    return allocation


def _production_paths(base: Path, case_id: str, batch_index: int) -> tuple[Path, Path]:
    directory = base / "production" / case_id
    stem = f"batch-{batch_index:06d}"
    return directory / f"{stem}.npz", directory / f"{stem}.json"


def _batch_expected(
    case: Mapping[str, Any], plan: Mapping[str, Any], allocation_n: int,
    batch_index: int, freeze_hash: str, source_hash: str, environment_hash: str,
) -> dict[str, Any]:
    batch_n = int(plan["batch_n"])
    batches = allocation_n // batch_n
    if not 0 <= batch_index < batches:
        raise ValueError(f"batch index {batch_index} is outside 0..{batches - 1}")
    return _receipt_expected(
        phase="production", case=case, seed=int(plan["production_seed"]),
        offset=batch_index * batch_n, n=batch_n, freeze_hash=freeze_hash,
        source_hash=source_hash, environment_hash=environment_hash, backend="gpu",
    ) | {"batch_index": batch_index, "allocation_n": allocation_n}


def _verified_production_batch(
    base: Path, case: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, Any] | None:
    data_path, receipt_path = _production_paths(base, str(case["id"]), int(expected["batch_index"]))
    receipt = _verify_receipt(receipt_path, expected, {"accumulator": data_path})
    if receipt is None:
        return None
    state = _load_state(data_path)
    if state["n"] != expected["n"]:
        raise RuntimeError(f"batch count mismatch at {data_path}")
    return state


def _production_indices(base: Path, case_id: str) -> tuple[set[int], set[int]]:
    directory = base / "production" / case_id
    data: set[int] = set()
    receipts: set[int] = set()
    if not directory.exists():
        return data, receipts
    for path in directory.iterdir():
        if re.fullmatch(
            r"\.batch-\d{6}\.(?:npz\.\d+\.candidate|json\.\d+\.tmp)", path.name
        ):
            # A process may die between fsync and rename. Only these private,
            # uncommitted names are ignored; published names remain exact.
            continue
        match = re.fullmatch(r"batch-(\d{6})\.(npz|json)", path.name)
        if match is None:
            raise RuntimeError(f"unexpected production artifact: {path}")
        (data if match.group(2) == "npz" else receipts).add(int(match.group(1)))
    return data, receipts


def _validate_production_prefix(
    base: Path, case: Mapping[str, Any], plan: Mapping[str, Any], allocation_n: int,
    freeze_hash: str, source_hash: str, environment_hash: str, *, require_complete: bool,
) -> int:
    count = allocation_n // int(plan["batch_n"])
    allowed = set(range(count))
    data, receipts = _production_indices(base, str(case["id"]))
    if not data <= allowed or not receipts <= allowed:
        raise RuntimeError(f"unexpected extra production batch for {case['id']}")
    if receipts - data:
        raise RuntimeError(f"production receipt without accumulator for {case['id']}")
    completed = 0
    while completed in receipts:
        expected = _batch_expected(
            case, plan, allocation_n, completed, freeze_hash, source_hash, environment_hash
        )
        _verified_production_batch(base, case, expected)
        completed += 1
    if any(index >= completed for index in receipts):
        raise RuntimeError(f"gap or overlap in completed production batches for {case['id']}")
    # One data-only file at the next expected index is an allowed interrupted batch.
    incomplete = data - receipts
    if incomplete and incomplete != ({completed} if completed < count else set()):
        raise RuntimeError(f"unexpected incomplete production batches for {case['id']}")
    if require_complete and completed != count:
        raise RuntimeError(f"production is incomplete for {case['id']}: {completed}/{count} batches")
    return completed


def _run_production_batch(
    case: Mapping[str, Any], plan: Mapping[str, Any], base: Path, allocation_n: int,
    batch_index: int, freeze_hash: str, source_hash: str, environment_hash: str,
    backend: str,
) -> None:
    expected = _batch_expected(
        case, plan, allocation_n, batch_index, freeze_hash, source_hash, environment_hash
    )
    if _verified_production_batch(base, case, expected) is not None:
        return
    data_path, receipt_path = _production_paths(base, str(case["id"]), batch_index)
    features = _simulate_features(
        case, n=int(expected["n"]), seed=int(expected["seed"]),
        path_offset=int(expected["path_offset"]), backend=backend,
    )
    accumulator = FeatureAccumulator().add(features)
    data_hash = save_npz_immutable(data_path, _state_arrays(accumulator))
    _save_json_immutable(receipt_path, {**expected, "artifacts": {"accumulator": data_hash}})


def run_production(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None,
    *, cell_ids: Sequence[str] | None = None, batch_index: int | None = None,
    backend: str = "gpu",
) -> None:
    freeze, base, freeze_hash = _load_freeze(plan_path, output_dir)
    _enforce_producer_environment(freeze, backend)
    plan = freeze["plan"]
    allocation = _load_allocation(freeze, base, freeze_hash)
    allocations = {item["case_id"]: int(item["n"]) for item in allocation["cells"]}
    selected = _select_cases(freeze, cell_ids)
    if batch_index is not None and len(selected) != 1:
        raise ValueError("--batch-index requires exactly one --cell")
    for case in selected:
        allocation_n = allocations[case["id"]]
        completed = _validate_production_prefix(
            base, case, plan, allocation_n, freeze_hash,
            freeze["source_manifest_sha256"], freeze["environment_sha256"],
            require_complete=False,
        )
        indices = [batch_index] if batch_index is not None else list(
            range(completed, allocation_n // int(plan["batch_n"]))
        )
        for index in indices:
            if index > completed:
                raise RuntimeError("cannot create a production gap")
            _run_production_batch(
                case, plan, base, allocation_n, int(index), freeze_hash,
                freeze["source_manifest_sha256"], freeze["environment_sha256"], backend,
            )
            completed = max(completed, int(index) + 1)
            print(f"production batch complete: {case['id']} {int(index):06d}", flush=True)
        if completed == allocation_n // int(plan["batch_n"]):
            print(f"production cell complete: {case['id']}", flush=True)


def _merged_production_state(
    case: Mapping[str, Any], plan: Mapping[str, Any], base: Path, allocation_n: int,
    freeze_hash: str, source_hash: str, environment_hash: str,
) -> dict[str, Any]:
    _validate_production_prefix(
        base, case, plan, allocation_n, freeze_hash, source_hash, environment_hash,
        require_complete=True,
    )
    states: list[Mapping[str, Any]] = []
    for index in range(allocation_n // int(plan["batch_n"])):
        expected = _batch_expected(
            case, plan, allocation_n, index, freeze_hash, source_hash, environment_hash
        )
        state = _verified_production_batch(base, case, expected)
        assert state is not None
        states.append(state)
    merged = merge_accumulator_states(states)
    if merged["n"] != allocation_n:
        raise RuntimeError(f"merged production count differs for {case['id']}")
    return merged


def _figure_point(
    case: Mapping[str, Any], row: Mapping[str, Any], result: Mapping[str, Any],
    freeze: Mapping[str, Any], n: int,
) -> dict[str, Any] | None:
    if case["group"] == "figure":
        if row["observable"] == "spatial":
            prefix = "variance" if case["mode"] == "localized" else "diffusion"
        elif row["observable"] == "v_x":
            prefix = "drift"
        else:
            return None
        series = f"{prefix}_{case['protocol']}"
        x = float(case["rho"])
    elif case["group"] == "tuned":
        if row["observable"] == "spatial":
            series = f"tuned_diffusion_{case['protocol']}"
        elif row["observable"] == "v_x":
            series = "tuned_drift_V" if case["protocol"] == "V" else "tuned_theta_drift"
        else:
            return None
        x = float(case["M"])
    else:
        return None
    return {
        "series": series,
        "x": x,
        "estimate": float(result["estimate"]),
        "se": float(result["se"]),
        "n": int(n),
        "case_id": case["id"],
        "source_manifest_sha256": freeze["source_manifest_sha256"],
        "plan_semantic_sha256": freeze["plan_semantic_sha256"],
        "reference": float(row["reference"]),
        "classification": result["classification"],
        "precision_pass": bool(result["precision_pass"]),
        "discretization_pass": bool(result["discretization_pass"]),
        "qualification_pass": bool(result["qualification_pass"]),
        "b_disc": float(result["b_disc"]),
        "b_window": float(result["b_window"]),
        "transient_residual": float(result["transient_residual"]),
        "b_total": float(result["b_total"]),
    }


def summarize_results(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None,
    *, raise_on_qualification: bool = True,
) -> dict[str, Any]:
    """Perform the one fixed final reduction over production accumulators."""

    freeze, base, freeze_hash = _load_freeze(plan_path, output_dir)
    plan = freeze["plan"]
    allocation = _load_allocation(freeze, base, freeze_hash)
    allocation_by_case = {item["case_id"]: int(item["n"]) for item in allocation["cells"]}
    all_rows: list[dict[str, Any]] = []
    table_rows: list[dict[str, Any]] = []
    figure_points: list[dict[str, Any]] = []
    for case in freeze["cases"]:
        n = allocation_by_case[case["id"]]
        state = _merged_production_state(
            case, plan, base, n, freeze_hash, freeze["source_manifest_sha256"],
            freeze["environment_sha256"],
        )
        diagnostics = _diagnostics(case, state, None, plan, bootstrap=False)
        by_id = {item["id"]: item for item in diagnostics["rows"]}
        for frozen_row in case["rows"]:
            diagnostic = by_id[frozen_row["id"]]
            estimates = diagnostic["level_window_estimates"]
            estimate_value = float(diagnostic["fine"]["value"])
            se = float(diagnostic["fine"]["se"])
            b_disc = float(diagnostic["b1"]["envelope"])
            b_window = max(
                abs(float(estimates[0][window]["value"]) - estimate_value)
                for window in (1, 2)
            )
            classified = classify_row(
                frozen_row, value=estimate_value, se=se, b_disc=b_disc,
                b_window=b_window, transient=float(frozen_row["transient_residual"]),
            )
            discretization_pass = bool(
                diagnostic["b1"]["pass"] and diagnostic["b2"]["pass"]
            )
            result = {
                "id": frozen_row["id"],
                "case_id": case["id"],
                "group": case["group"],
                "protocol": case["protocol"],
                "M": float(case["M"]),
                "Pe": float(case["Pe"]),
                "rho": float(case["rho"]),
                "observable": frozen_row["observable"],
                "observable_class": frozen_row["observable_class"],
                "reference": float(frozen_row["reference"]),
                "estimate": estimate_value,
                "se": se,
                "n": n,
                "se_fraction": se / float(frozen_row["precision_scale"]),
                "tau": float(frozen_row["tau"]),
                "epsilon": float(frozen_row["epsilon"]),
                "b_disc": b_disc,
                "b1": diagnostic["b1"],
                "b2": diagnostic["b2"],
                "b_window": b_window,
                "transient_residual": float(frozen_row["transient_residual"]),
                "level_window_estimates": estimates,
                "discretization_pass": discretization_pass,
                **classified,
            }
            result["qualification_pass"] = bool(
                result["precision_pass"] and result["discretization_pass"]
            )
            all_rows.append(result)
            table_rows.append(dict(result))
            point = _figure_point(case, frozen_row, result, freeze, n)
            if point is not None:
                figure_points.append(point)
    if len(all_rows) != 80:
        raise RuntimeError("final reduction did not produce 80 rows")
    counts = {
        label: sum(row["classification"] == label for row in all_rows)
        for label in ("validated", "contradicted", "unresolved")
    }
    payload = {
        "schema": "phasemap.s074.results.v1",
        "freeze_file_sha256": freeze_hash,
        "source_manifest_sha256": freeze["source_manifest_sha256"],
        "plan_semantic_sha256": freeze["plan_semantic_sha256"],
        "pilot_excluded": True,
        "primary_estimator": "raw_finest_em",
        "classification_counts": counts,
        "precision_pass": all(row["precision_pass"] for row in all_rows),
        "method_qualification_pass": all(row["discretization_pass"] for row in all_rows),
        "discretization_pass": all(row["discretization_pass"] for row in all_rows),
        "qualification_pass": all(row["qualification_pass"] for row in all_rows),
        "scientific_validation_pass": all(
            row["classification"] == "validated" for row in all_rows
        ),
        "rows": all_rows,
        "table_rows": table_rows,
        "figure_points": figure_points,
    }
    _save_json_immutable(base / "results.json", payload)
    if raise_on_qualification and not payload["qualification_pass"]:
        raise RuntimeError(
            f"production qualification failed with preserved results: {base / 'results.json'}"
        )
    return payload


def validate_outputs(
    plan_path: Path | str = PLAN_PATH, output_dir: Path | str | None = None
) -> dict[str, Any]:
    """Fail closed on provenance, resumption, count, and result corruption."""

    freeze, base, freeze_hash = _load_freeze(plan_path, output_dir)
    plan = freeze["plan"]
    _verified_pilot_set(freeze, base, freeze_hash)
    allocation = _load_allocation(freeze, base, freeze_hash)
    allocation_by_case = {item["case_id"]: int(item["n"]) for item in allocation["cells"]}
    for case in freeze["cases"]:
        _validate_production_prefix(
            base, case, plan, allocation_by_case[case["id"]], freeze_hash,
            freeze["source_manifest_sha256"], freeze["environment_sha256"],
            require_complete=True,
        )
    results_path = base / "results.json"
    results = summarize_results(plan_path, output_dir, raise_on_qualification=False)
    if (
        results.get("schema") != "phasemap.s074.results.v1"
        or results.get("freeze_file_sha256") != freeze_hash
        or results.get("source_manifest_sha256") != freeze["source_manifest_sha256"]
        or results.get("plan_semantic_sha256") != _expected_plan_hash(plan)
        or results.get("pilot_excluded") is not True
        or len(results.get("rows", [])) != 80
    ):
        raise RuntimeError("final result identity or row inventory is invalid")
    row_ids = [row["id"] for row in results["rows"]]
    frozen_ids = [row["id"] for case in freeze["cases"] for row in case["rows"]]
    if row_ids != frozen_ids or len(set(row_ids)) != 80:
        raise RuntimeError("final result rows differ from the freeze")
    return {
        "status": "PASS",
        "freeze_file_sha256": freeze_hash,
        "results_sha256": _file_sha256(results_path),
        "cells": 41,
        "rows": 80,
        "production_n": int(allocation["total_n"]),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("freeze")
    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--cell", action="append", dest="cells")
    pilot.add_argument("--backend", choices=("cpu", "gpu"), default="gpu")
    subparsers.add_parser("allocate")
    produce = subparsers.add_parser("produce")
    produce.add_argument("--cell", action="append", dest="cells")
    produce.add_argument("--batch-index", type=int)
    produce.add_argument("--backend", choices=("cpu", "gpu"), default="gpu")
    subparsers.add_parser("summarize")
    subparsers.add_parser("validate")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "freeze":
        freeze = freeze_plan(args.plan, args.output_dir)
        print(json.dumps({"status": "PASS", "cells": len(freeze["cases"]), "rows": 80}))
    elif args.command == "pilot":
        run_pilot(args.plan, args.output_dir, cell_ids=args.cells, backend=args.backend)
    elif args.command == "allocate":
        allocation = allocate_production(args.plan, args.output_dir)
        print(json.dumps({"status": "PASS", "total_n": allocation["total_n"]}))
    elif args.command == "produce":
        run_production(
            args.plan, args.output_dir, cell_ids=args.cells,
            batch_index=args.batch_index, backend=args.backend,
        )
    elif args.command == "summarize":
        results = summarize_results(args.plan, args.output_dir)
        print(json.dumps({"status": "PASS", "rows": len(results["rows"])}))
    else:
        print(json.dumps(validate_outputs(args.plan, args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
