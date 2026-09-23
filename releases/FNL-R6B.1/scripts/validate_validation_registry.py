#!/usr/bin/env python3
"""Fail-closed validator and dispatch helpers for CONTRACT.md Section 7."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/scientific-contract/CONTRACT.md"
REGISTRY_PATH = ROOT / "docs/scientific-contract/validation_registry.json"
SCHEMA_PATH = ROOT / "docs/scientific-contract/validation_registry.schema.json"
SECTION_7_SHA256 = "65f1af81e0187de5daf45bf0857d6d757d01a3b9897442493fe22b9e6c69dd60"


class RegistryValidationError(ValueError):
    """Raised when the registry, a run configuration, or contract alignment fails."""


def _reject_nonfinite(value: str) -> None:
    raise RegistryValidationError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryValidationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RegistryValidationError(f"{path} must contain a JSON object")
    return value


def load_registry() -> dict[str, Any]:
    return load_json(REGISTRY_PATH)


def load_schema() -> dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise RegistryValidationError("registry schema must declare JSON Schema 2020-12")
    return schema


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    return left == right


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _matches_type(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": _is_number,
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected not in checks:
        raise RegistryValidationError(f"unsupported schema type {expected!r}")
    return checks[expected](value)


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise RegistryValidationError(f"only local JSON Schema references are supported: {ref}")
    node: Any = root_schema
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise RegistryValidationError(f"unresolvable JSON Schema reference: {ref}")
        node = node[token]
    if not isinstance(node, dict):
        raise RegistryValidationError(f"JSON Schema reference is not an object: {ref}")
    return node


def _schema_errors(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    errors: list[str] = []

    if "$ref" in schema:
        errors.extend(
            _schema_errors(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path)
        )

    for sub_schema in schema.get("allOf", []):
        errors.extend(_schema_errors(value, sub_schema, root_schema, path))

    if "if" in schema:
        condition_errors = _schema_errors(value, schema["if"], root_schema, path)
        branch = schema.get("then") if not condition_errors else schema.get("else")
        if branch is not None:
            errors.extend(_schema_errors(value, branch, root_schema, path))

    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")

    if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
        errors.append(f"{path}: value {value!r} is not recognized")

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    _schema_errors(item, properties[key], root_schema, f"{path}.{key}")
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unknown property {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(
                    _schema_errors(
                        item,
                        schema["additionalProperties"],
                        root_schema,
                        f"{path}.{key}",
                    )
                )

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: requires at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: permits at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items must be unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(
                    _schema_errors(item, schema["items"], root_schema, f"{path}[{index}]")
                )

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: string is shorter than {schema['minLength']}")

    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(
                f"{path}: {value} must be greater than {schema['exclusiveMinimum']}"
            )
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(
                f"{path}: {value} must be less than {schema['exclusiveMaximum']}"
            )

    return errors


def validate_against_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
) -> None:
    root = schema if root_schema is None else root_schema
    errors = _schema_errors(value, schema, root)
    if errors:
        raise RegistryValidationError("; ".join(errors))


def validate_registry_instance(
    registry: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
) -> None:
    registry = load_registry() if registry is None else registry
    schema = load_schema() if schema is None else schema
    validate_against_schema(registry, schema)


def extract_section_7(contract_text: str) -> str:
    match = re.search(
        r"(?ms)^## 7\. Numerical validation\r?\n.*?(?=^## 8\. Publication boundary\r?$)",
        contract_text,
    )
    if not match:
        raise RegistryValidationError("CONTRACT.md Section 7 cannot be located")
    return match.group(0).rstrip("\r\n").replace("\r\n", "\n")


def validate_contract_alignment(
    contract_text: str | None = None,
    registry: dict[str, Any] | None = None,
) -> None:
    contract_text = (
        CONTRACT_PATH.read_text(encoding="utf-8") if contract_text is None else contract_text
    )
    registry = load_registry() if registry is None else registry
    section = extract_section_7(contract_text)
    digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
    if digest != SECTION_7_SHA256:
        raise RegistryValidationError(
            "BL2: CONTRACT.md Section 7 differs from the supplied candidate text"
        )
    version_match = re.search(
        r"^\*\*Contract version:\*\*\s*(.+?)\s*$", contract_text, flags=re.MULTILINE
    )
    if not version_match or version_match.group(1) != registry.get("contract_version"):
        raise RegistryValidationError("BL2: contract and registry versions disagree")
    expected_target = "docs/scientific-contract/CONTRACT.md#7-numerical-validation"
    if registry.get("normative_section") != expected_target:
        raise RegistryValidationError("BL2: registry points to the wrong normative section")


def evidence_tier(registry: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        tier = registry["evidence_tiers"][name]
    except KeyError as exc:
        raise RegistryValidationError(f"unknown evidence tier: {name}") from exc
    return tier


def observable_class(registry: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        observable = registry["observable_classes"][name]
    except KeyError as exc:
        raise RegistryValidationError(f"unknown observable class: {name}") from exc
    return observable


def _positive(value: Any, name: str) -> float:
    if not _is_number(value) or not math.isfinite(value) or value <= 0:
        raise RegistryValidationError(f"{name} must be finite and positive")
    return float(value)


def characteristic_scale(
    registry: dict[str, Any], observable_name: str, references: dict[str, float]
) -> float:
    observable_class(registry, observable_name)

    def ref(name: str) -> float:
        if name not in references:
            raise RegistryValidationError(
                f"observable class {observable_name!r} requires reference {name!r}"
            )
        value = references[name]
        if not _is_number(value) or not math.isfinite(value):
            raise RegistryValidationError(f"reference {name!r} must be finite")
        return float(value)

    dispatch = {
        "r_mean": lambda: math.sqrt(abs(ref("rr_ii_reference"))),
        "v_mean": lambda: math.sqrt(abs(ref("vv_ii_reference"))),
        "u_mean": lambda: math.sqrt(abs(ref("uu_ii_reference"))),
        "rr": lambda: math.sqrt(
            abs(ref("rr_ii_reference") * ref("rr_jj_reference"))
        ),
        "vv": lambda: math.sqrt(
            abs(ref("vv_ii_reference") * ref("vv_jj_reference"))
        ),
        "uu": lambda: math.sqrt(
            abs(ref("uu_ii_reference") * ref("uu_jj_reference"))
        ),
        "rv": lambda: math.sqrt(
            abs(ref("rr_ii_reference") * ref("vv_jj_reference"))
        ),
        "ru": lambda: math.sqrt(
            abs(ref("rr_ii_reference") * ref("uu_jj_reference"))
        ),
        "vu": lambda: math.sqrt(
            abs(ref("vv_ii_reference") * ref("uu_jj_reference"))
        ),
        "r_dot_v": lambda: math.sqrt(
            abs(ref("r_squared_reference") * ref("v_squared_reference"))
        ),
        "cov_r_trace": lambda: abs(ref("reference")),
        "stationary_variance": lambda: abs(ref("reference")),
        "d_eff": lambda: max(
            abs(ref("reference")), _positive(ref("declared_class_scale"), "declared class scale")
        ),
        "symmetry_forced_zero": lambda: _positive(ref("parent_scale"), "parent scale"),
        "zero_crossing": lambda: _positive(ref("parent_scale"), "parent scale"),
    }
    scale = dispatch[observable_name]()
    return _positive(scale, f"characteristic scale for {observable_name}")


def admissible_margin(
    registry: dict[str, Any],
    observable_name: str,
    tier_name: str,
    *,
    reference: float,
    scale: float,
    normalized_floor_fraction: float | None = None,
) -> float:
    tier = evidence_tier(registry, tier_name)
    observable = observable_class(registry, observable_name)
    scale = _positive(scale, "characteristic scale")
    floor = (
        registry["margin"]["default_normalized_floor_fraction"]
        if normalized_floor_fraction is None
        else normalized_floor_fraction
    )
    floor = _positive(floor, "normalized floor fraction")
    relative_margin = _positive(tier["relative_margin"], "relative margin")
    relative_term = 0.0 if observable.get("relative_term_enabled") is False else relative_margin * abs(reference)
    return floor * scale + relative_term


def classify_interval(
    registry: dict[str, Any],
    lower: float,
    upper: float,
    epsilon: float,
    *,
    b_window: float = 0.0,
    b_disc: float = 0.0,
) -> str:
    if lower > upper:
        raise RegistryValidationError("interval lower bound exceeds upper bound")
    epsilon = _positive(epsilon, "epsilon")
    if b_window < 0 or b_disc < 0:
        raise RegistryValidationError("systematic envelopes must be nonnegative")
    expanded_lower = lower - b_window - b_disc
    expanded_upper = upper + b_window + b_disc
    outcomes = registry["comparison_outcomes"]
    if expanded_lower >= -epsilon and expanded_upper <= epsilon:
        return outcomes[0]
    if expanded_upper < -epsilon or expanded_lower > epsilon:
        return outcomes[1]
    return outcomes[2]


def validate_run_configuration(
    configuration: dict[str, Any],
    registry: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
) -> None:
    registry = load_registry() if registry is None else registry
    schema = load_schema() if schema is None else schema
    validate_against_schema(
        configuration, schema["$defs"]["run_configuration"], root_schema=schema
    )
    tier = evidence_tier(registry, configuration["evidence_tier"])
    observable = observable_class(registry, configuration["observable_class"])
    if configuration["normalized_floor_fraction"] != registry["margin"][
        "default_normalized_floor_fraction"
    ]:
        raise RegistryValidationError("run normalized floor disagrees with registry")
    if configuration["relative_margin"] != tier["relative_margin"]:
        raise RegistryValidationError("run relative margin disagrees with evidence tier")
    if tier["gating"] and configuration["pilot_reused_in_confirmatory_estimate"]:
        raise RegistryValidationError("gating-tier pilot data are design-only")
    sequential = registry["sequential_sampling"]
    if configuration["maximum_interim_evaluations"] > sequential[
        "maximum_interim_evaluations"
    ]:
        raise RegistryValidationError("more than one interim evaluation is forbidden")
    if configuration["continuous_polling_allowed"] or configuration[
        "repeated_top_up_allowed"
    ]:
        raise RegistryValidationError("continuous polling and repeated top-ups are forbidden")
    if configuration["observable_class"] == "d_eff":
        if registry["d_eff"]["naive_ols_standard_error_allowed"] is not False:
            raise RegistryValidationError("registry must prohibit naive OLS SE for D_eff")
        if configuration["naive_ols_standard_error_allowed"]:
            raise RegistryValidationError("naive OLS SE is forbidden for D_eff")
    if (
        configuration["comparison_kind"] == "fine_coarse"
        and configuration["valid_coupling_exists"]
        and registry["pairing"]["fine_coarse"] == "paired_when_valid_coupling_exists"
        and not configuration["paired_paths"]
    ):
        raise RegistryValidationError("valid fine/coarse couplings must use paired paths")
    if (
        configuration["claimed_zero_crossing"]
        and observable.get("root_location_rule_required_when_claimed")
        and "root_location_rule" not in configuration
    ):
        raise RegistryValidationError("claimed zero crossing requires a root-location rule")


def validate_repository() -> tuple[dict[str, Any], dict[str, Any]]:
    schema = load_schema()
    registry = load_registry()
    validate_registry_instance(registry, schema)
    validate_contract_alignment(registry=registry)
    return registry, schema


def main() -> int:
    try:
        registry, _ = validate_repository()
    except RegistryValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("PHASEMAP validation registry passed.")
    print(
        f"Validated {len(registry['evidence_tiers'])} evidence tiers and "
        f"{len(registry['observable_classes'])} observable classes."
    )
    print(f"CONTRACT.md Section 7 SHA-256: {SECTION_7_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
