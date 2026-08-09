from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import phasemap.simulation.complete_reset_regenerative as regenerative
from phasemap.simulation.complete_reset_regenerative import (
    FINE_STEP,
    PairedTerminalStates,
    covariance_trace_with_jackknife,
    draw_ages,
    kurtosis_with_jackknife,
    mean_with_se,
    paired_jackknife,
    simulate_regenerative_paired,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "experiments/run_s012_complete_reset_regenerative.py"
SPEC = importlib.util.spec_from_file_location("s012_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _plan() -> dict:
    return runner.load(ROOT / runner.PLAN_REL)


def _brute_covariance_trace(sample: np.ndarray) -> float:
    centered = sample - sample.mean(axis=0)
    return float(np.sum(centered * centered) / (len(sample) - 1))


def _brute_k(sample: np.ndarray) -> float:
    radial_second = np.sum(sample * sample, axis=1)
    return float(
        np.mean(radial_second * radial_second)
        / (2.0 * np.mean(radial_second) ** 2)
        - 1.0
    )


def _jackknife_se(values: np.ndarray) -> float:
    return float(
        np.sqrt(
            (len(values) - 1)
            / len(values)
            * np.sum((values - values.mean()) ** 2)
        )
    )


def _fake_result(case_code: int, count: int = 64) -> PairedTerminalStates:
    random = np.random.default_rng(100 + case_code)
    ages = np.linspace(0.01, 2.0, count)
    fine_position = random.normal(size=(count, 2)) + np.array([0.3, -0.1])
    coarse_position = fine_position + random.normal(scale=1e-3, size=(count, 2))
    fine_velocity = random.normal(size=(count, 2)) + np.array([0.2, 0.0])
    coarse_velocity = fine_velocity + random.normal(scale=1e-3, size=(count, 2))
    fine_orientation = random.normal(scale=0.5, size=count)
    coarse_orientation = fine_orientation + random.normal(scale=1e-3, size=count)
    return PairedTerminalStates(
        ages=ages,
        fine_position=fine_position,
        fine_velocity=fine_velocity,
        fine_orientation=fine_orientation,
        coarse_position=coarse_position,
        coarse_velocity=coarse_velocity,
        coarse_orientation=coarse_orientation,
    )


def _synthetic_analysis(
    plan: dict,
    *,
    count: int | None = None,
    base_seed: int | None = None,
) -> dict:
    if count is None:
        count = plan["sampling"]["N0"]
    if base_seed is None:
        base_seed = plan["rng"]["base_seeds"]["pilot"]
    references = {
        case["case_id"]: runner.reference(case) for case in plan["parameters"]
    }
    rows = []
    for config in plan["configurations"]:
        analytic = references[config["case"]][config["observable"]]
        paired = config["comparison_kind"] == "paired_fine_coarse"
        reference = 0.0 if paired else analytic
        estimate = 0.0 if paired else analytic
        scale = runner.characteristic_scale(config, references[config["case"]])
        epsilon = runner.NORMALIZED_FLOOR * scale + runner.RELATIVE_MARGIN * abs(
            reference
        )
        interval, expanded, classification = runner.classify_interval(
            0.0,
            0.0,
            epsilon,
            0.0,
        )
        rows.append(
            {
                "id": config["id"],
                "case": config["case"],
                "observable": config["observable"],
                "comparison_kind": config["comparison_kind"],
                "estimator": config["estimator"],
                "SE_method": config["SE"],
                "scale_rule": config["scale_rule"],
                "fine_estimate": analytic,
                "fine_SE": 0.0,
                "coarse_estimate": analytic,
                "coarse_SE": 0.0,
                "paired_estimate": 0.0,
                "paired_SE": 0.0,
                "estimate": estimate,
                "analytic_reference": analytic,
                "reference": reference,
                "delta": 0.0,
                "SE": 0.0,
                "quantile": runner.Q,
                "characteristic_scale": scale,
                "normalized_floor_fraction": runner.NORMALIZED_FLOOR,
                "relative_margin": runner.RELATIVE_MARGIN,
                "epsilon": epsilon,
                "B_window": 0.0,
                "B_disc": 0.0,
                "interval": interval,
                "expanded_interval": expanded,
                "classification": classification,
            }
        )
    hashes = {
        "ages": "1" * 64,
        "fine_position": "2" * 64,
        "fine_velocity": "3" * 64,
        "fine_orientation": "4" * 64,
        "coarse_position": "5" * 64,
        "coarse_velocity": "6" * 64,
        "coarse_orientation": "7" * 64,
    }
    provenance = {
        case["case_id"]: {
            "count": count,
            "base_seed": base_seed,
            "case_code": case["case_code"],
            "age_summary": {"minimum": 0.0, "maximum": 2.0, "mean": 1.0},
            "array_sha256": hashes,
        }
        for case in plan["parameters"]
    }
    return {
        "rows": rows,
        "references": references,
        "case_provenance": provenance,
        "supporting_only": {
            "id": "passive-raw-r4-supporting-only",
            "case": "passive",
            "observable": "raw_E_abs_r_fourth",
            "gating": False,
            "fine_estimate": 1.0,
            "fine_SE": 0.0,
            "coarse_estimate": 1.0,
            "coarse_SE": 0.0,
            "paired_estimate": 0.0,
            "paired_SE": 0.0,
        },
    }


def _redirect_raw_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    names = {
        "PILOT": "pilot.json",
        "CONFIRM": "confirm.json",
        "FAILURE": "failure.json",
        "PA": "pilot-attempt.json",
        "CA": "confirm-attempt.json",
    }
    for attribute, name in names.items():
        monkeypatch.setattr(runner, attribute, tmp_path / name)


def test_age_stream_is_reproducible_positive_and_case_separated() -> None:
    first = draw_ages(7, 1.0, 20260722301, 1)
    second = draw_ages(7, 1.0, 20260722301, 1)
    other_case = draw_ages(7, 1.0, 20260722301, 2)
    np.testing.assert_array_equal(first, second)
    assert np.all(first > 0.0)
    assert not np.array_equal(first, other_case)
    with pytest.raises(ValueError):
        draw_ages(0, 1.0, 1, 1)
    with pytest.raises(ValueError):
        draw_ages(1, 0.0, 1, 1)


def test_exact_nested_coupling_closes_full_and_short_terminal_singletons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ages = np.array(
        [FINE_STEP, 2 * FINE_STEP, 3 * FINE_STEP, 2.5 * FINE_STEP]
    )

    class OnesGenerator:
        def normal(self, size):
            return np.ones(size, dtype=float)

    monkeypatch.setattr(regenerative, "draw_ages", lambda *args, **kwargs: ages.copy())
    monkeypatch.setattr(regenerative, "_rng", lambda *args, **kwargs: OnesGenerator())
    result = simulate_regenerative_paired(
        inertia=0.8,
        activity=1.2,
        reset_rate=1.0,
        count=4,
        base_seed=7,
        case_code=1,
        chunk_size=4,
    )

    # A one-step terminal singleton is exactly the same EM update at both levels.
    np.testing.assert_array_equal(result.fine_position[0], result.coarse_position[0])
    np.testing.assert_allclose(result.fine_velocity[0], result.coarse_velocity[0])
    assert result.fine_orientation[0] == pytest.approx(result.coarse_orientation[0])

    # For two fine steps, the coarse path consumes the exact sum of two unit
    # fine increments in one update; its position remains at the initial zero.
    expected_coarse_velocity = (
        np.array([1.2, 0.0]) * (2 * FINE_STEP / 0.8)
        + math.sqrt(2.0)
        * np.array([2 * math.sqrt(FINE_STEP), 2 * math.sqrt(FINE_STEP)])
        / 0.8
    )
    np.testing.assert_allclose(result.coarse_velocity[1], expected_coarse_velocity)
    np.testing.assert_array_equal(result.coarse_position[1], np.zeros(2))
    assert not np.array_equal(result.fine_position[1], result.coarse_position[1])

    # Reaching these records without the accumulator guard firing covers both
    # the exact one-full-step final singleton and a shortened residual.
    assert np.isfinite(result.coarse_velocity[2:]).all()


def test_terminal_simulation_shapes_hashes_and_finiteness() -> None:
    result = simulate_regenerative_paired(
        inertia=0.8,
        activity=1.2,
        reset_rate=1.0,
        count=5,
        base_seed=7,
        case_code=1,
        chunk_size=2,
    )
    assert result.fine_position.shape == (5, 2)
    assert result.coarse_velocity.shape == (5, 2)
    assert np.isfinite(result.fine_position).all()
    hashes = result.array_sha256s()
    assert len(hashes) == 7
    assert all(len(value) == 64 for value in hashes.values())
    assert result.age_sha256() == hashes["ages"]


@pytest.mark.parametrize(
    ("function", "brute"),
    [
        (covariance_trace_with_jackknife, _brute_covariance_trace),
        (kurtosis_with_jackknife, _brute_k),
    ],
)
def test_vectorized_jackknives_match_brute_force_delete_one(
    function,
    brute,
) -> None:
    random = np.random.default_rng(5)
    fine = random.normal(size=(8, 2))
    coarse = fine + random.normal(scale=0.1, size=(8, 2))
    estimate, standard_error = function(fine)
    leave = np.array([brute(np.delete(fine, index, axis=0)) for index in range(8)])
    assert estimate == pytest.approx(brute(fine))
    assert standard_error == pytest.approx(_jackknife_se(leave))

    paired_estimate, paired_se = paired_jackknife(fine, coarse, function)
    paired_leave = np.array(
        [
            brute(np.delete(fine, index, axis=0))
            - brute(np.delete(coarse, index, axis=0))
            for index in range(8)
        ]
    )
    assert paired_estimate == pytest.approx(brute(fine) - brute(coarse))
    assert paired_se == pytest.approx(_jackknife_se(paired_leave))


def test_estimators_are_linear_memory_at_large_n_and_reject_invalid_dispatch() -> None:
    random = np.random.default_rng(10)
    fine = random.normal(size=(50_000, 2))
    coarse = fine + random.normal(scale=0.01, size=(50_000, 2))
    for function in (covariance_trace_with_jackknife, kurtosis_with_jackknife):
        estimate, standard_error = function(fine)
        paired_estimate, paired_se = paired_jackknife(fine, coarse, function)
        assert all(
            math.isfinite(value)
            for value in (estimate, standard_error, paired_estimate, paired_se)
        )
    with pytest.raises(ValueError):
        paired_jackknife(fine[:4], coarse[:4], lambda _: (0.0, 0.0))
    with pytest.raises(ValueError):
        mean_with_se(np.array([1.0]))


def test_strict_json_rejects_duplicates_nonfinite_and_nonobject(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        runner.load(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        runner.load(nonfinite)
    overflow = tmp_path / "overflow.json"
    overflow.write_text('{"a": {"b": 1e999}}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        runner.load(overflow)
    nonobject = tmp_path / "list.json"
    nonobject.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root"):
        runner.load(nonobject)
    assert runner._close(math.inf, math.inf) is False


def test_semantic_hash_freezes_every_plan_field() -> None:
    plan = _plan()
    runner.validate(plan)
    assert runner.semantic_sha256(plan) == runner.PLAN_SEMANTIC_SHA256
    mutations = []
    changed = deepcopy(plan)
    changed["parameters"][0]["inertia"] = "9/10"
    mutations.append(changed)
    changed = deepcopy(plan)
    changed["rng"]["base_seeds"]["pilot"] += 1
    mutations.append(changed)
    changed = deepcopy(plan)
    changed["configurations"][0]["scale_rule"] = "wrong"
    mutations.append(changed)
    changed = deepcopy(plan)
    changed["sampling"]["no_polling"] = False
    mutations.append(changed)
    changed = deepcopy(plan)
    changed["outputs"]["pilot"] = "elsewhere.json"
    mutations.append(changed)
    for mutation in mutations:
        with pytest.raises(ValueError, match="semantic"):
            runner.validate(mutation)


def test_exact_characteristic_scale_dispatch_for_all_twenty_rows() -> None:
    plan = _plan()
    references = {
        case["case_id"]: runner.reference(case) for case in plan["parameters"]
    }
    by_key: dict[tuple[str, str], list[float]] = {}
    for config in plan["configurations"]:
        scale = runner.characteristic_scale(config, references[config["case"]])
        by_key.setdefault((config["case"], config["observable"]), []).append(scale)
    assert all(len(values) == 2 and values[0] == values[1] for values in by_key.values())
    active = references["active"]
    assert by_key[("active", "v_x")][0] == pytest.approx(
        math.sqrt(active["vv_xx"])
    )
    assert by_key[("active", "r_x")][0] == pytest.approx(
        math.sqrt(active["rr_xx"])
    )
    assert by_key[("active", "uu_xx")][0] == pytest.approx(abs(active["uu_xx"]))
    assert active["vv_xx"] != pytest.approx(active["mean_squared_speed"] / 2.0)
    bad = deepcopy(plan["configurations"][0])
    bad["scale_rule"] = "u_mean:wrong"
    with pytest.raises(ValueError, match="scale rule"):
        runner.characteristic_scale(bad, active)


def test_interval_classification_boundaries_and_precedence() -> None:
    assert runner.classify_interval(1.0, 0.0, 1.0, 0.0)[2] == "validated"
    assert runner.classify_interval(-1.0, 0.0, 1.0, 0.0)[2] == "validated"
    just_outside = np.nextafter(1.0, math.inf)
    assert runner.classify_interval(just_outside, 0.0, 1.0, 0.0)[2] == "contradicted"
    assert (
        runner.classify_interval(1.5, 1.0, 1.0, 0.0, quantile=1.0)[2]
        == "unresolved"
    )
    with pytest.raises(ValueError):
        runner.classify_interval(0.0, -1.0, 1.0, 0.0)
    assert runner.overall_precedence([{"classification": "validated"}]) == "validated"
    assert runner.overall_precedence([{"classification": "unresolved"}]) == "unresolved"
    assert (
        runner.overall_precedence(
            [{"classification": "unresolved"}, {"classification": "contradicted"}]
        )
        == "contradicted"
    )
    with pytest.raises(ValueError):
        runner.overall_precedence([], expected_count=20)


def test_projection_handles_small_targets_invalid_denominators_and_cap() -> None:
    base = {
        "id": "row",
        "epsilon": 1.0,
        "delta": 0.0,
        "B_window": 0.0,
        "B_disc": 0.0,
        "SE": 0.0,
    }
    projection = runner.projection_for_row(8192, base, 262144)
    assert projection["eligible"] is True
    assert projection["projected_count"] == 0

    invalid = {**base, "delta": 1.0}
    assert runner.projection_for_row(8192, invalid, 262144)["reason"].startswith(
        "nonpositive"
    )
    above = {**base, "SE": 100.0}
    assert runner.projection_for_row(8192, above, 10)["reason"] == "above_cap"

    rows = [{**base, "id": f"row-{index}"} for index in range(20)]
    global_projection = runner.pilot_projection(rows, 8192, 262144)
    assert global_projection["confirmation_eligible"] is True
    assert global_projection["N_target_global"] == 8192
    rows[-1] = {**rows[-1], "delta": 1.0}
    global_projection = runner.pilot_projection(rows, 8192, 262144)
    assert global_projection["confirmation_eligible"] is False
    assert global_projection["N_target_global"] is None


def test_event_trace_requires_adjacent_equal_time_and_exact_zero() -> None:
    valid = SimpleNamespace(
        reset_times=np.array([0.25]),
        times=np.array([0.0, 0.25, 0.25]),
        positions=np.array([[1.0, 1.0], [0.2, 0.3], [0.0, 0.0]]),
        velocities=np.array([[1.0, 1.0], [0.2, 0.3], [0.0, 0.0]]),
        orientations=np.array([0.1, 0.2, 0.0]),
    )
    runner.assert_event_trace(valid)
    missing = deepcopy(valid)
    missing.reset_times = np.array([])
    with pytest.raises(RuntimeError, match="no reset"):
        runner.assert_event_trace(missing)
    separated = deepcopy(valid)
    separated.times = np.array([0.25, 0.0, 0.25])
    with pytest.raises(RuntimeError, match="adjacent"):
        runner.assert_event_trace(separated)
    nonzero = deepcopy(valid)
    nonzero.velocities[-1, 0] = 1e-300
    with pytest.raises(RuntimeError, match="velocity"):
        runner.assert_event_trace(nonzero)


def test_mode_specific_raw_path_states_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_raw_paths(monkeypatch, tmp_path)
    runner.validate_raw_path_state("pilot")
    runner.PILOT.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="all canonical"):
        runner.validate_raw_path_state("pilot")
    runner.PA.write_text("{}", encoding="utf-8")
    runner.validate_raw_path_state("confirm")
    runner.CA.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="state mismatch"):
        runner.validate_raw_path_state("confirm")


def test_clean_head_rejects_dirty_tree_and_returns_full_sha(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_raw_paths(monkeypatch, tmp_path)

    def clean_git(arguments: list[str]) -> str:
        return "" if arguments[0] == "status" else "a" * 40 + "\n"

    monkeypatch.setattr(runner, "_git_output", clean_git)
    assert runner.clean_head("pilot") == "a" * 40
    monkeypatch.setattr(
        runner,
        "_git_output",
        lambda arguments: "?? x\n" if arguments[0] == "status" else "a" * 40,
    )
    with pytest.raises(RuntimeError, match="clean Git"):
        runner.clean_head("pilot")


def test_atomic_reservation_and_publication_never_overwrite(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt.json"
    output = tmp_path / "output.json"
    attempt_hash = runner.reserve(attempt, {"stage": "pilot"})
    assert len(attempt_hash) == 64
    with pytest.raises(FileExistsError):
        runner.reserve(attempt, {"stage": "pilot"})
    output_hash = runner.publish(output, {"ok": True})
    assert len(output_hash) == 64
    assert json.loads(output.read_text(encoding="utf-8")) == {"ok": True}
    with pytest.raises(FileExistsError):
        runner.publish(output, {"ok": False})


def test_analysis_records_all_rows_supporting_r4_and_complete_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()

    def fake_simulator(**kwargs):
        return _fake_result(kwargs["case_code"], kwargs["count"])

    monkeypatch.setattr(runner, "simulate_regenerative_paired", fake_simulator)
    analysis = runner.analyse(plan, 64, 12345)
    assert len(analysis["rows"]) == 20
    assert [row["id"] for row in analysis["rows"]] == [
        config["id"] for config in plan["configurations"]
    ]
    required = {
        "fine_estimate",
        "fine_SE",
        "coarse_estimate",
        "coarse_SE",
        "paired_estimate",
        "paired_SE",
        "interval",
        "expanded_interval",
        "B_disc",
        "epsilon",
        "classification",
    }
    assert all(required <= set(row) for row in analysis["rows"])
    assert analysis["supporting_only"]["gating"] is False
    assert analysis["supporting_only"]["observable"] == "raw_E_abs_r_fourth"
    for record in analysis["case_provenance"].values():
        assert record["count"] == 64
        assert len(record["array_sha256"]) == 7


def test_pilot_authentication_recomputes_target_and_rejects_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_raw_paths(monkeypatch, tmp_path)
    plan = _plan()
    plan_hash = runner.sha256_file(ROOT / runner.PLAN_REL)
    source_commit = "a" * 40
    source_hashes = {"source.py": "b" * 64}
    attempt = runner._attempt_payload(
        "pilot",
        plan,
        plan_hash,
        source_commit,
        source_hashes,
    )
    attempt_hash = runner.reserve(runner.PA, attempt)
    payload = runner.build_pilot_payload(
        plan=plan,
        plan_hash=plan_hash,
        source_commit=source_commit,
        source_hashes=source_hashes,
        attempt_hash=attempt_hash,
        analysis=_synthetic_analysis(plan),
    )
    pilot_hash = runner.publish(runner.PILOT, payload)
    _, target, authenticated = runner.authenticate_pilot(
        plan=plan,
        plan_hash=plan_hash,
        source_commit=source_commit,
        source_hashes=source_hashes,
        cli_sha256=pilot_hash,
    )
    assert target == plan["sampling"]["N0"]
    assert authenticated == pilot_hash

    mutated = deepcopy(payload)
    mutated["rows"][0]["characteristic_scale"] *= 2.0
    runner.PILOT.write_bytes(runner.canonical(mutated))
    mutated_hash = runner.sha256_file(runner.PILOT)
    with pytest.raises(ValueError, match="scale"):
        runner.authenticate_pilot(
            plan=plan,
            plan_hash=plan_hash,
            source_commit=source_commit,
            source_hashes=source_hashes,
            cli_sha256=mutated_hash,
        )


def test_confirm_payload_has_no_fresh_projection_semantics() -> None:
    plan = _plan()
    analysis = _synthetic_analysis(plan)
    payload = runner.build_confirm_payload(
        plan=plan,
        plan_hash="1" * 64,
        source_commit="2" * 40,
        source_hashes={"x": "3" * 64},
        attempt_hash="4" * 64,
        count=8192,
        authenticated_pilot_sha256="5" * 64,
        analysis=analysis,
    )
    assert payload["overall"] == "validated"
    assert payload["data_role"] == "confirmatory-only"
    assert payload["contract_version"] == plan["contract_version"]
    assert payload["validation_registry_schema_version"] == plan[
        "validation_registry_schema_version"
    ]
    assert payload["execution_locks"]["sampling"] == plan["sampling"]
    assert "projection" not in payload
    assert "confirmation_eligible" not in payload
    assert payload["confirmatory_target_from_pilot"] == 8192


def test_execute_pilot_then_confirm_uses_one_clean_source_and_new_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_raw_paths(monkeypatch, tmp_path)
    plan = _plan()
    source_commit = "a" * 40
    source_hashes = {"source.py": "b" * 64}

    def fake_git(arguments: list[str]) -> str:
        return "" if arguments[0] == "status" else source_commit + "\n"

    monkeypatch.setattr(runner, "_git_output", fake_git)
    monkeypatch.setattr(runner, "source_manifest", lambda: source_hashes)
    monkeypatch.setattr(runner, "event_check", lambda: None)
    monkeypatch.setattr(
        runner,
        "analyse",
        lambda current_plan, count, base_seed: _synthetic_analysis(
            current_plan,
            count=count,
            base_seed=base_seed,
        ),
    )

    pilot = runner.execute("pilot", runner.PLAN_REL)
    assert pilot["overall"] == "design-only"
    assert runner.PA.exists() and runner.PILOT.exists()
    pilot_hash = runner.sha256_file(runner.PILOT)
    confirm = runner.execute(
        "confirm",
        runner.PLAN_REL,
        pilot_hash,
    )
    assert confirm["overall"] == "validated"
    assert confirm["authenticated_pilot_sha256"] == pilot_hash
    assert confirm["execution_locks"]["rng"]["stage_base_seed"] == plan["rng"][
        "base_seeds"
    ]["confirmatory"]
    assert runner.CA.exists() and runner.CONFIRM.exists()
    assert not runner.FAILURE.exists()


def test_execute_failure_after_reservation_publishes_fixed_failure_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_raw_paths(monkeypatch, tmp_path)
    source_commit = "a" * 40
    monkeypatch.setattr(
        runner,
        "_git_output",
        lambda arguments: "" if arguments[0] == "status" else source_commit,
    )
    monkeypatch.setattr(runner, "source_manifest", lambda: {"x": "b" * 64})
    monkeypatch.setattr(runner, "event_check", lambda: None)
    monkeypatch.setattr(
        runner,
        "analyse",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic")),
    )
    with pytest.raises(RuntimeError, match="synthetic"):
        runner.execute("pilot", runner.PLAN_REL)
    assert runner.PA.exists()
    assert runner.FAILURE.exists()
    assert not runner.PILOT.exists()
    receipt = runner.load(runner.FAILURE)
    assert receipt["stage"] == "pilot"
    assert receipt["attempt_receipt_sha256"] == runner.sha256_file(runner.PA)


def test_validate_and_import_create_no_canonical_artifacts() -> None:
    before = {
        path: path.exists()
        for path in (runner.PILOT, runner.CONFIRM, runner.FAILURE, runner.PA, runner.CA)
    }
    runner.validate(_plan())
    after = {
        path: path.exists()
        for path in (runner.PILOT, runner.CONFIRM, runner.FAILURE, runner.PA, runner.CA)
    }
    # Before execution all values are false; after the immutable pilot is
    # recorded, PILOT and PA are true.  Validate/import must preserve either
    # legitimate repository state exactly and must never create later-stage
    # or failure artifacts.
    assert before == after
    assert not after[runner.CONFIRM]
    assert not after[runner.CA]
    assert not after[runner.FAILURE]


def test_manifest_covers_required_sources_and_simulator_has_no_theory_import() -> None:
    manifest = runner.source_manifest()
    required = {
        "docs/scientific-contract/CONTRACT.md",
        "docs/scientific-contract/validation_registry.json",
        "docs/scientific-contract/validation_registry.schema.json",
        "artifacts/derived/T-012-complete-reset-baseline.md",
        "experiments/S-012-complete-reset-regenerative-primary-v1.json",
        "experiments/run_s012_complete_reset_regenerative.py",
        "src/phasemap/simulation/complete_reset_regenerative.py",
        "src/phasemap/simulation/integrator.py",
        "src/phasemap/simulation/protocols.py",
        "src/phasemap/common/model.py",
        "src/phasemap/theory/complete_reset_baseline.py",
        "tests/simulation/test_complete_reset_regenerative.py",
    }
    assert set(manifest) == required
    assert all(len(value) == 64 for value in manifest.values())
    simulator_text = (
        ROOT / "src/phasemap/simulation/complete_reset_regenerative.py"
    ).read_text(encoding="utf-8")
    assert "phasemap.theory" not in simulator_text
