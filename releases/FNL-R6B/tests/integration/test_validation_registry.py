from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_validation_registry import (
    CONTRACT_PATH,
    RegistryValidationError,
    admissible_margin,
    characteristic_scale,
    classify_interval,
    load_registry,
    load_schema,
    validate_contract_alignment,
    validate_registry_instance,
    validate_run_configuration,
)


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def schema():
    return load_schema()


def base_run_configuration(**updates):
    configuration = {
        "evidence_tier": "routine_screen",
        "observable_class": "rr",
        "compute_cap": 1000,
        "characteristic_scale": 2.0,
        "normalized_floor_fraction": 0.005,
        "relative_margin": 0.02,
        "systematic_envelopes": {"B_window": 0.0, "B_disc": 0.0},
        "maximum_interim_evaluations": 1,
        "maximum_final_evaluations": 1,
        "continuous_polling_allowed": False,
        "repeated_top_up_allowed": False,
        "stop_at_first_pass_allowed": False,
        "pilot_reused_in_confirmatory_estimate": True,
        "comparison_kind": "direct_reference",
        "valid_coupling_exists": False,
        "paired_paths": False,
        "claimed_zero_crossing": False,
    }
    configuration.update(updates)
    return configuration


def test_registry_validates_against_strict_schema(registry, schema):
    validate_registry_instance(registry, schema)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "$defs" in schema and "run_configuration" in schema["$defs"]


@pytest.mark.parametrize("field", ["evidence_tiers", "observable_classes"])
def test_schema_rejects_unknown_tier_or_observable_class(registry, schema, field):
    mutated = deepcopy(registry)
    mutated[field]["unknown"] = deepcopy(next(iter(mutated[field].values())))
    with pytest.raises(RegistryValidationError, match="unknown property"):
        validate_registry_instance(mutated, schema)


@pytest.mark.parametrize(
    ("field", "value"),
    [("evidence_tier", "unknown"), ("observable_class", "unknown")],
)
def test_run_configuration_rejects_unknown_tier_or_class(registry, schema, field, value):
    configuration = base_run_configuration(**{field: value})
    with pytest.raises(RegistryValidationError, match="not recognized"):
        validate_run_configuration(configuration, registry, schema)


@pytest.mark.parametrize("tier_name", ["primary", "central_disputed"])
def test_gating_tier_rejects_pilot_reuse(registry, schema, tier_name):
    configuration = base_run_configuration(
        evidence_tier=tier_name,
        relative_margin=0.01,
        pilot_reused_in_confirmatory_estimate=True,
    )
    with pytest.raises(RegistryValidationError, match="constant False|design-only"):
        validate_run_configuration(configuration, registry, schema)


def test_routine_screen_allows_single_batch_pilot_reuse(registry, schema):
    validate_run_configuration(base_run_configuration(), registry, schema)
    assert registry["evidence_tiers"]["routine_screen"]["gating"] is False


def test_more_than_one_interim_evaluation_is_rejected(registry, schema):
    configuration = base_run_configuration(maximum_interim_evaluations=2)
    with pytest.raises(RegistryValidationError, match="constant 1|one interim"):
        validate_run_configuration(configuration, registry, schema)


@pytest.mark.parametrize(
    "forbidden_update",
    [
        {"continuous_polling_allowed": True},
        {"repeated_top_up_allowed": True},
        {"stop_at_first_pass_allowed": True},
    ],
)
def test_continuous_polling_repeated_topups_and_first_pass_are_rejected(
    registry, schema, forbidden_update
):
    configuration = base_run_configuration(**forbidden_update)
    with pytest.raises(RegistryValidationError, match="constant False|forbidden"):
        validate_run_configuration(configuration, registry, schema)


def test_exact_tier_quantiles_coverages_and_relative_margins(registry):
    assert registry["evidence_tiers"] == {
        "routine_screen": {
            "gating": False,
            "pointwise_coverage": 0.9545,
            "normal_equivalent_quantile": 2.0,
            "relative_margin": 0.02,
            "pilot_policy": "single_top_up_pilot_may_be_reused",
        },
        "primary": {
            "gating": True,
            "pointwise_coverage": 0.99,
            "normal_equivalent_quantile": 2.5758293035,
            "relative_margin": 0.01,
            "pilot_policy": "design_only_excluded_from_confirmatory_analysis",
        },
        "central_disputed": {
            "gating": True,
            "pointwise_coverage": 0.9973,
            "normal_equivalent_quantile": 3.0,
            "relative_margin": 0.01,
            "pilot_policy": "design_only_excluded_from_confirmatory_analysis",
        },
    }
    assert registry["margin"] == {
        "formula": "normalized_floor_fraction * characteristic_scale + relative_margin * abs(reference)",
        "default_normalized_floor_fraction": 0.005,
    }


@pytest.mark.parametrize(
    ("observable_name", "references", "expected"),
    [
        ("r_mean", {"rr_ii_reference": 9.0}, 3.0),
        ("v_mean", {"vv_ii_reference": 16.0}, 4.0),
        ("u_mean", {"uu_ii_reference": 25.0}, 5.0),
        ("rr", {"rr_ii_reference": 4.0, "rr_jj_reference": 9.0}, 6.0),
        ("vv", {"vv_ii_reference": 4.0, "vv_jj_reference": 16.0}, 8.0),
        ("uu", {"uu_ii_reference": 9.0, "uu_jj_reference": 16.0}, 12.0),
        ("rv", {"rr_ii_reference": 4.0, "vv_jj_reference": 25.0}, 10.0),
        ("ru", {"rr_ii_reference": 9.0, "uu_jj_reference": 16.0}, 12.0),
        ("vu", {"vv_ii_reference": 16.0, "uu_jj_reference": 25.0}, 20.0),
        (
            "r_dot_v",
            {"r_squared_reference": 9.0, "v_squared_reference": 16.0},
            12.0,
        ),
        ("cov_r_trace", {"reference": -7.0}, 7.0),
        ("stationary_variance", {"reference": 11.0}, 11.0),
        ("d_eff", {"reference": 2.0, "declared_class_scale": 3.0}, 3.0),
        ("symmetry_forced_zero", {"parent_scale": 6.0}, 6.0),
        ("zero_crossing", {"parent_scale": 8.0}, 8.0),
    ],
)
def test_characteristic_scale_dispatch(registry, observable_name, references, expected):
    assert characteristic_scale(registry, observable_name, references) == pytest.approx(expected)


def test_interval_classification_is_validated_contradicted_or_unresolved(registry):
    assert classify_interval(registry, -0.2, 0.3, 0.5) == "validated"
    assert classify_interval(registry, 0.8, 1.0, 0.5) == "contradicted"
    assert classify_interval(registry, 0.4, 0.7, 0.5) == "unresolved"
    assert (
        classify_interval(registry, -0.2, 0.3, 0.5, b_window=0.1, b_disc=0.2)
        == "unresolved"
    )
    with pytest.raises(RegistryValidationError, match="nonnegative"):
        classify_interval(registry, -0.2, 0.3, 0.5, b_window=-0.1)


def test_symmetry_zero_uses_parent_scale_and_no_relative_term(registry):
    scale = characteristic_scale(
        registry, "symmetry_forced_zero", {"parent_scale": 4.0}
    )
    margin = admissible_margin(
        registry,
        "symmetry_forced_zero",
        "primary",
        reference=100.0,
        scale=scale,
    )
    assert margin == pytest.approx(0.02)


def test_claimed_zero_crossing_requires_root_location_rule(registry, schema):
    configuration = base_run_configuration(
        observable_class="zero_crossing",
        parent_scale=3.0,
        claimed_zero_crossing=True,
    )
    with pytest.raises(RegistryValidationError, match="root_location_rule|root-location"):
        validate_run_configuration(configuration, registry, schema)
    configuration["root_location_rule"] = {
        "parameter_bracket": [0.5, 1.5],
        "lower_sign": -1,
        "upper_sign": 1,
        "estimator": "linear_interpolation",
        "uncertainty_method": "paired_bootstrap",
        "epsilon_root": 0.05,
    }
    validate_run_configuration(configuration, registry, schema)


def test_naive_ols_standard_error_is_forbidden_for_d_eff(registry, schema):
    configuration = base_run_configuration(
        observable_class="d_eff",
        declared_class_scale=1.0,
        naive_ols_standard_error_allowed=True,
    )
    with pytest.raises(RegistryValidationError, match="constant False|forbidden"):
        validate_run_configuration(configuration, registry, schema)


def test_valid_fine_coarse_coupling_requires_pairing(registry, schema):
    configuration = base_run_configuration(
        comparison_kind="fine_coarse",
        valid_coupling_exists=True,
        paired_paths=False,
    )
    with pytest.raises(RegistryValidationError, match="constant True|paired paths"):
        validate_run_configuration(configuration, registry, schema)
    configuration["paired_paths"] = True
    validate_run_configuration(configuration, registry, schema)


def test_run_configuration_requires_declared_compute_cap(registry, schema):
    configuration = base_run_configuration()
    del configuration["compute_cap"]
    with pytest.raises(RegistryValidationError, match="compute_cap"):
        validate_run_configuration(configuration, registry, schema)


def test_contract_and_registry_disagreement_fails_closed(registry):
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    validate_contract_alignment(contract_text, registry)
    changed = contract_text.replace("q = 2.5758293035", "q = 2.5758", 1)
    assert changed != contract_text
    with pytest.raises(RegistryValidationError, match="BL2"):
        validate_contract_alignment(changed, registry)
