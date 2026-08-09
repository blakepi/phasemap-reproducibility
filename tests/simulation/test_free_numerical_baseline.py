from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import numpy as np
import pytest

import experiments.run_s011_free_baseline as runner
from phasemap.simulation.free_baseline import (
    OBSERVABLE_NAMES,
    covariance_trace_jackknife,
    simulate_free_paired,
)
from scripts.validate_validation_registry import admissible_margin, classify_interval


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = PROJECT_ROOT / runner.PLAN_REL


def _plan() -> dict[str, Any]:
    return runner.load_preregistered_plan(PLAN_PATH)


def _valid_rows(
    plan: dict[str, Any],
    *,
    direct_delta: float = -0.001,
    paired_delta: float = -0.001,
    standard_error: float = 0.002,
) -> list[dict[str, Any]]:
    registry = runner.load_registry()
    quantile = registry["evidence_tiers"]["primary"][
        "normal_equivalent_quantile"
    ]
    paired_b_disc = 0.0
    direct_b_disc = max(
        runner.B_DISC_FLOOR, abs(paired_delta) + quantile * standard_error
    )
    rows: list[dict[str, Any]] = []
    for entry in plan["run_configurations"]:
        configuration = entry["run_configuration"]
        observable = configuration["observable_class"]
        comparison = configuration["comparison_kind"]
        paired = comparison == "fine_coarse"
        delta = paired_delta if paired else direct_delta
        reference = 0.0 if paired else runner._reference(entry["time"], observable)
        epsilon = admissible_margin(
            registry,
            observable,
            configuration["evidence_tier"],
            reference=reference,
            scale=configuration["characteristic_scale"],
            normalized_floor_fraction=configuration["normalized_floor_fraction"],
        )
        interval = [
            delta - quantile * standard_error,
            delta + quantile * standard_error,
        ]
        b_disc = paired_b_disc if paired else direct_b_disc
        rows.append(
            {
                "id": entry["id"],
                "time": entry["time"],
                "observable_class": observable,
                "comparison_kind": comparison,
                "evidence_tier": configuration["evidence_tier"],
                "reference": reference,
                "delta": delta,
                "standard_error": standard_error,
                "interval": interval,
                "epsilon": epsilon,
                "B_window": 0.0,
                "B_disc": b_disc,
                "classification": classify_interval(
                    registry,
                    interval[0],
                    interval[1],
                    epsilon,
                    b_window=0.0,
                    b_disc=b_disc,
                ),
                "estimator": plan["uncertainty"]["methods"][observable][comparison][
                    "estimator"
                ],
                "standard_error_method": plan["uncertainty"]["methods"][observable][
                    comparison
                ]["standard_error"],
            }
        )
    return rows


def _pilot_payload(environment: dict[str, Any]) -> dict[str, Any]:
    plan = environment["plan"]
    registry = environment["registry"]
    rows = deepcopy(environment["rows"])
    metadata = runner._base_metadata(
        plan,
        mode="pilot",
        plan_hash=environment["plan_hash"],
        commit=environment["commit"],
        manifest=environment["manifest"],
        registry=registry,
    )
    targets = runner._pilot_targets(plan, rows, registry)
    assert all(target is not None for target in targets)
    return {
        **metadata,
        "evidence_role": "design-only",
        "overall": "design-only",
        "count": plan["sampling"]["pilot_size"],
        "seeds": plan["sampling"]["pilot_seeds"],
        "analysis": rows,
        "per_config_n_target": targets,
        "n_target": max(targets),
        "eligible_for_confirmation": True,
    }


def _write_pilot(environment: dict[str, Any], payload: dict[str, Any]) -> tuple[Path, str]:
    path = environment["root"] / runner.PILOT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(runner._json_text(payload), encoding="utf-8", newline="")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def execution_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    destination = tmp_path / runner.PLAN_REL
    destination.parent.mkdir(parents=True)
    destination.write_bytes(PLAN_PATH.read_bytes())
    commit = "a" * 40
    manifest = {path: hashlib.sha256(path.encode()).hexdigest() for path in runner.MANIFEST}
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_clean_commit", lambda: commit)
    monkeypatch.setattr(runner, "source_manifest", lambda: manifest)
    plan = runner.load_preregistered_plan(Path(runner.PLAN_REL))
    registry = runner.load_registry()
    yield {
        "root": tmp_path,
        "commit": commit,
        "manifest": manifest,
        "plan": plan,
        "registry": registry,
        "rows": _valid_rows(plan),
        "plan_hash": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def test_free_paired_baseline_is_seed_reproducible() -> None:
    kwargs = dict(
        inertia=0.8,
        activity=1.2,
        end_time=0.2,
        fine_step=0.01,
        ensemble_size=64,
        seed=20260722011,
    )
    first = simulate_free_paired(**kwargs)
    second = simulate_free_paired(**kwargs)
    assert tuple(first.fine.values) == OBSERVABLE_NAMES
    for name in OBSERVABLE_NAMES:
        assert first.fine.values[name] == second.fine.values[name]
        assert first.coarse.values[name] == second.coarse.values[name]
        assert np.isfinite(first.paired_standard_errors[name])


def test_free_paired_requires_even_fine_steps() -> None:
    with pytest.raises(ValueError):
        simulate_free_paired(
            inertia=1.0,
            activity=0.0,
            end_time=0.03,
            fine_step=0.01,
            ensemble_size=4,
            seed=1,
        )


def test_free_paired_requires_three_trajectories_for_covariance_jackknife() -> None:
    with pytest.raises(ValueError, match="at least three"):
        simulate_free_paired(
            inertia=1.0,
            activity=0.0,
            end_time=0.02,
            fine_step=0.01,
            ensemble_size=2,
            seed=1,
        )


def test_free_simulator_is_exact_rho_zero_route() -> None:
    assert "rho=0" in (simulate_free_paired.__doc__ or "")
    assert "rho -> 0" not in (simulate_free_paired.__doc__ or "")


def test_v2_plan_is_strict_registry_valid_and_declares_canonical_outputs() -> None:
    plan = _plan()
    runner.validate_preregistered_plan(plan)
    assert plan["outputs"] == runner.OUTPUTS
    assert plan["uncertainty"] == runner.UNCERTAINTY
    assert not set(plan["sampling"]["pilot_seeds"]) & set(
        plan["sampling"]["confirmatory_seeds"]
    )
    assert len(plan["run_configurations"]) == 8
    assert runner.MANIFEST == [
        "docs/scientific-contract/CONTRACT.md",
        "docs/scientific-contract/validation_registry.json",
        "docs/scientific-contract/validation_registry.schema.json",
        "scripts/validate_validation_registry.py",
        "experiments/run_s011_free_baseline.py",
        "src/phasemap/__init__.py",
        "src/phasemap/simulation/__init__.py",
        "src/phasemap/simulation/free_baseline.py",
        "src/phasemap/theory/__init__.py",
        "src/phasemap/theory/free_baseline.py",
        runner.PLAN_REL,
    ]


PlanMutation = Callable[[dict[str, Any]], None]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan.update(contract_version="x"),
        lambda plan: plan.update(status="executed"),
        lambda plan: plan.update(rho_limit_claimed=0),
        lambda plan: plan["outputs"].update(pilot="pilot.json"),
        lambda plan: plan["outputs"].update(extra="artifact.json"),
        lambda plan: plan["parameters"].update(reset_rate=0.1),
        lambda plan: plan["parameters"].update(reset_rate=False),
        lambda plan: plan.update(fine_step=0.003),
        lambda plan: plan["sampling"].update(pilot_size=1),
        lambda plan: plan["sampling"].update(
            confirmatory_seeds=plan["sampling"]["pilot_seeds"]
        ),
        lambda plan: plan["sampling"].update(maximum_interim_evaluations=True),
        lambda plan: plan["sampling"].update(
            pilot_reused_in_confirmatory_estimate=0
        ),
        lambda plan: plan["sampling"].update(continuous_polling_allowed=0),
        lambda plan: plan.update(validation_times=[3.0, 1.5]),
        lambda plan: plan["uncertainty"]["interval"].update(quantile=2.0),
        lambda plan: plan["uncertainty"]["methods"]["r_dot_v"][
            "direct_reference"
        ].update(standard_error="generic_standard_error"),
        lambda plan: plan["uncertainty"]["systematic_envelopes"].update(
            B_disc_estimator="abs(delta)"
        ),
        lambda plan: plan["uncertainty"]["systematic_envelopes"].update(
            B_window=False
        ),
        lambda plan: plan["uncertainty"]["systematic_envelopes"][
            "phase_policy"
        ].update(pilot_values_enter_confirmatory_interval_or_classification=0),
        lambda plan: plan.update(pairing_policy="unpaired"),
        lambda plan: plan["run_configurations"].pop(),
        lambda plan: plan["run_configurations"].__setitem__(
            1, deepcopy(plan["run_configurations"][0])
        ),
        lambda plan: plan["run_configurations"][0].update(id="wrong-id"),
        lambda plan: plan["run_configurations"][0]["run_configuration"].update(
            evidence_tier="routine_screen"
        ),
        lambda plan: plan["run_configurations"][1]["run_configuration"].update(
            paired_paths=False
        ),
        lambda plan: plan["run_configurations"][0]["run_configuration"].update(
            maximum_interim_evaluations=True
        ),
        lambda plan: plan["run_configurations"][1]["run_configuration"][
            "systematic_envelopes"
        ].update(B_window=False),
        lambda plan: plan["run_configurations"][0]["run_configuration"].update(
            characteristic_scale=float("nan")
        ),
        lambda plan: plan["run_configurations"][0]["reference_inputs"].update(
            r_squared_reference=99.0
        ),
    ],
)
def test_v2_plan_rejects_locked_contract_departures(mutate: PlanMutation) -> None:
    plan = _plan()
    mutate(plan)
    with pytest.raises(ValueError, match="invalid S-011 v2 plan"):
        runner.validate_preregistered_plan(plan)


def test_strict_json_rejects_duplicate_keys_and_nonfinite_constants(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"value": 1, "value": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        runner._json_load(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="nonfinite JSON constant"):
        runner._json_load(nonfinite)


@pytest.mark.parametrize(
    "command",
    [
        [
            sys.executable,
            "experiments/run_s011_free_baseline.py",
            "validate",
            runner.PLAN_REL,
        ],
        [sys.executable, "-m", "experiments.run_s011_free_baseline", "validate", runner.PLAN_REL],
    ],
)
def test_direct_and_module_cli_validate_only(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "S-011 v2 plan valid"


def test_primary_projection_accepts_signed_discrepancy_and_uses_new_batch() -> None:
    common = dict(
        pilot_size=2048,
        quantile=runner.PRIMARY_QUANTILE,
        pilot_standard_error=0.01,
        epsilon=0.1,
        b_window=0.0,
        b_disc=0.01,
        compute_cap=131072,
    )
    positive = runner.project_confirmatory_size(pilot_discrepancy=0.02, **common)
    negative = runner.project_confirmatory_size(pilot_discrepancy=-0.02, **common)
    assert positive == negative == 278


def test_zero_standard_error_is_unresolved_in_fixed_projection() -> None:
    assert (
        runner.project_confirmatory_size(
            pilot_size=2048,
            quantile=runner.PRIMARY_QUANTILE,
            pilot_standard_error=0.0,
            epsilon=0.1,
            pilot_discrepancy=0.0,
            b_window=0.0,
            b_disc=0.01,
            compute_cap=131072,
        )
        is None
    )


def test_projection_rejects_target_two_and_handles_huge_finite_se() -> None:
    assert (
        runner.project_confirmatory_size(
            pilot_size=3,
            quantile=1.0,
            pilot_standard_error=math.sqrt(0.5),
            epsilon=1.0,
            pilot_discrepancy=0.0,
            b_window=0.0,
            b_disc=0.0,
            compute_cap=10,
        )
        is None
    )
    assert (
        runner.project_confirmatory_size(
            pilot_size=2048,
            quantile=runner.PRIMARY_QUANTILE,
            pilot_standard_error=sys.float_info.max,
            epsilon=1.0,
            pilot_discrepancy=0.0,
            b_window=0.0,
            b_disc=0.0,
            compute_cap=131072,
        )
        is None
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("pilot_standard_error", -0.1),
        ("pilot_standard_error", float("nan")),
        ("pilot_discrepancy", float("inf")),
        ("b_window", -0.1),
        ("b_disc", float("nan")),
        ("epsilon", 0.0),
        ("quantile", -1.0),
        ("pilot_size", 2),
        ("pilot_size", True),
    ],
)
def test_projection_rejects_bad_values(field: str, value: Any) -> None:
    arguments = dict(
        pilot_size=2048,
        quantile=runner.PRIMARY_QUANTILE,
        pilot_standard_error=0.01,
        epsilon=0.1,
        pilot_discrepancy=-0.02,
        b_window=0.0,
        b_disc=0.01,
        compute_cap=131072,
    )
    arguments[field] = value
    with pytest.raises(ValueError, match="invalid projection inputs"):
        runner.project_confirmatory_size(**arguments)


def test_pilot_rows_accept_signed_negative_discrepancies() -> None:
    plan = _plan()
    rows = _valid_rows(plan)
    assert all(row["delta"] < 0 for row in rows)
    assert runner._validate_analysis_rows(plan, rows, runner.load_registry()) == rows


def test_phase_local_b_disc_uses_only_each_phases_matching_pairs() -> None:
    plan = _plan()
    registry = runner.load_registry()
    pilot_rows = _valid_rows(plan, paired_delta=-0.001)
    confirm_rows = _valid_rows(plan, paired_delta=0.006)
    runner._validate_analysis_rows(plan, pilot_rows, registry)
    runner._validate_analysis_rows(plan, confirm_rows, registry)
    pilot_direct = [
        row["B_disc"]
        for row in pilot_rows
        if row["comparison_kind"] == "direct_reference"
    ]
    confirm_direct = [
        row["B_disc"]
        for row in confirm_rows
        if row["comparison_kind"] == "direct_reference"
    ]
    assert pilot_direct == [runner.B_DISC_FLOOR] * 4
    assert all(value > runner.B_DISC_FLOOR for value in confirm_direct)
    assert confirm_direct != pilot_direct


RowMutation = Callable[[list[dict[str, Any]]], None]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows.pop(),
        lambda rows: rows.reverse(),
        lambda rows: rows.__setitem__(1, deepcopy(rows[0])),
        lambda rows: rows[0].update(id="wrong-id"),
        lambda rows: rows[0].update(time=3.0),
        lambda rows: rows[0].update(observable_class="cov_r_trace"),
        lambda rows: rows[0].update(comparison_kind="fine_coarse"),
        lambda rows: rows[0].update(evidence_tier="routine_screen"),
        lambda rows: rows[0].update(reference=99.0),
        lambda rows: rows[0].update(estimator="generic"),
        lambda rows: rows[0].update(standard_error_method="generic"),
        lambda rows: rows[0].update(standard_error=-0.1),
        lambda rows: rows[0].update(delta=float("nan")),
        lambda rows: rows[0].update(interval=[-1.0, 1.0]),
        lambda rows: rows[0].update(epsilon=99.0),
        lambda rows: rows[0].update(B_window=-0.1),
        lambda rows: rows[0].update(B_disc=0.02),
        lambda rows: rows[1].update(B_disc=0.01),
        lambda rows: rows[0].update(classification="unresolved"),
    ],
)
def test_pilot_row_semantic_mutations_are_rejected(mutate: RowMutation) -> None:
    plan = _plan()
    rows = _valid_rows(plan)
    mutate(rows)
    with pytest.raises(ValueError, match="pilot output"):
        runner._validate_analysis_rows(plan, rows, runner.load_registry())


def test_overall_confirmatory_outcome_has_fail_closed_precedence() -> None:
    assert runner._overall([{"classification": "validated"}] * 2) == "validated"
    assert (
        runner._overall(
            [{"classification": "validated"}, {"classification": "unresolved"}]
        )
        == "unresolved"
    )
    assert (
        runner._overall(
            [{"classification": "unresolved"}, {"classification": "contradicted"}]
        )
        == "contradicted"
    )


PilotMutation = Callable[[dict[str, Any]], None]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda pilot: pilot.update(source_commit="b" * 40),
        lambda pilot: pilot.update(
            source_manifest={**pilot["source_manifest"], "extra": "hash"}
        ),
        lambda pilot: pilot.update(seeds=list(reversed(pilot["seeds"]))),
        lambda pilot: pilot.update(count=1),
        lambda pilot: pilot.update(evidence_role="primary"),
        lambda pilot: pilot.update(overall="validated"),
        lambda pilot: pilot.update(
            interval_construction={
                **pilot["interval_construction"],
                "quantile": 2.0,
            }
        ),
        lambda pilot: pilot.update(count=2048.0),
        lambda pilot: pilot["per_config_n_target"].__setitem__(0, 999),
        lambda pilot: pilot["per_config_n_target"].__setitem__(
            0, float(pilot["per_config_n_target"][0])
        ),
        lambda pilot: pilot.update(n_target=999),
        lambda pilot: pilot.update(eligible_for_confirmation=False),
    ],
)
def test_full_pilot_metadata_and_projection_mutations_are_rejected(
    execution_environment: dict[str, Any], mutate: PilotMutation
) -> None:
    pilot = _pilot_payload(execution_environment)
    mutate(pilot)
    with pytest.raises(ValueError, match="pilot"):
        runner._validate_pilot_artifact(
            pilot,
            execution_environment["plan"],
            plan_hash=execution_environment["plan_hash"],
            commit=execution_environment["commit"],
            manifest=execution_environment["manifest"],
            registry=execution_environment["registry"],
        )


@pytest.mark.parametrize(
    "alias",
    [
        Path("artifacts/raw/../raw/S-011-free-baseline-primary-v2-pilot.json"),
        Path("pilot.json"),
    ],
)
def test_executor_rejects_canonical_aliases_before_reservation(
    execution_environment: dict[str, Any], alias: Path
) -> None:
    canonical = execution_environment["root"] / runner.PILOT_REL
    with pytest.raises(ValueError, match="canonical"):
        runner.execute(Path(runner.PLAN_REL), "pilot", output=alias)
    assert not canonical.exists()


def test_pilot_reservation_is_visible_before_analysis_and_single_use(
    execution_environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = execution_environment["root"] / runner.PILOT_REL
    calls = 0

    def mocked_analysis(plan: dict[str, Any], n: int, seeds: list[int]):
        nonlocal calls
        calls += 1
        assert canonical.exists()
        assert canonical.read_bytes() == b""
        assert n == plan["sampling"]["pilot_size"]
        assert seeds == plan["sampling"]["pilot_seeds"]
        return deepcopy(execution_environment["rows"])

    monkeypatch.setattr(runner, "_analysis", mocked_analysis)
    result = runner.execute(Path(runner.PLAN_REL), "pilot")
    assert result["evidence_role"] == "design-only"
    assert result["overall"] == "design-only"
    assert result["eligible_for_confirmation"] is True
    assert isinstance(result["n_target"], int)
    assert runner._json_load(canonical) == result
    with pytest.raises(FileExistsError):
        runner.execute(Path(runner.PLAN_REL), "pilot")
    assert calls == 1


def test_mocked_stochastic_failure_writes_one_valid_receipt(
    execution_environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = execution_environment["root"] / runner.PILOT_REL

    def fail_after_reservation(*_args, **_kwargs):
        assert canonical.exists()
        assert canonical.read_bytes() == b""
        raise RuntimeError("mocked stochastic failure")

    monkeypatch.setattr(runner, "_analysis", fail_after_reservation)
    with pytest.raises(RuntimeError, match="mocked stochastic failure"):
        runner.execute(Path(runner.PLAN_REL), "pilot")
    receipt = runner._json_load(canonical)
    assert receipt["status"] == "failed-after-reservation"
    assert receipt["exception"] == {
        "type": "RuntimeError",
        "message": "mocked stochastic failure",
    }
    assert json.loads(canonical.read_text(encoding="utf-8")) == receipt


def test_nonfinite_success_is_never_partially_written(
    execution_environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = execution_environment["root"] / runner.PILOT_REL
    rows = deepcopy(execution_environment["rows"])
    rows[0]["delta"] = float("nan")
    monkeypatch.setattr(runner, "_analysis", lambda *_args, **_kwargs: rows)
    monkeypatch.setattr(
        runner,
        "_validate_analysis_rows",
        lambda _plan, supplied, _registry: supplied,
    )
    monkeypatch.setattr(runner, "_pilot_targets", lambda *_args: [2] * 8)
    with pytest.raises(ValueError, match="Out of range float"):
        runner.execute(Path(runner.PLAN_REL), "pilot")
    receipt = runner._json_load(canonical)
    assert receipt["status"] == "failed-after-reservation"
    assert "NaN" not in canonical.read_text(encoding="utf-8")


def test_tampered_pilot_is_rejected_before_confirm_reservation_or_analysis(
    execution_environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    pilot = _pilot_payload(execution_environment)
    pilot["analysis"][0]["reference"] += 1.0
    _, pilot_hash = _write_pilot(execution_environment, pilot)
    confirm = execution_environment["root"] / runner.CONFIRM_REL
    called = False

    def forbidden_analysis(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("confirm analysis must not run")

    monkeypatch.setattr(runner, "_analysis", forbidden_analysis)
    with pytest.raises(ValueError, match="pilot output"):
        runner.execute(
            Path(runner.PLAN_REL),
            "confirm",
            pilot_output=Path(runner.PILOT_REL),
            expected_pilot_sha256=pilot_hash,
        )
    assert called is False
    assert not confirm.exists()


def test_pilot_hash_mismatch_does_not_reserve_confirm_output(
    execution_environment: dict[str, Any]
) -> None:
    _write_pilot(execution_environment, _pilot_payload(execution_environment))
    confirm = execution_environment["root"] / runner.CONFIRM_REL
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        runner.execute(
            Path(runner.PLAN_REL),
            "confirm",
            pilot_output=Path(runner.PILOT_REL),
            expected_pilot_sha256="0" * 64,
        )
    assert not confirm.exists()


def test_mocked_confirm_reports_joint_overall_and_canonical_provenance(
    execution_environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    pilot_payload = _pilot_payload(execution_environment)
    _, pilot_hash = _write_pilot(execution_environment, pilot_payload)
    confirm = execution_environment["root"] / runner.CONFIRM_REL
    confirm_rows = _valid_rows(execution_environment["plan"], paired_delta=0.006)

    def mocked_analysis(plan: dict[str, Any], n: int, seeds: list[int]):
        assert confirm.exists()
        assert confirm.read_bytes() == b""
        assert seeds == plan["sampling"]["confirmatory_seeds"]
        assert n == pilot_payload["n_target"]
        return deepcopy(confirm_rows)

    monkeypatch.setattr(runner, "_analysis", mocked_analysis)
    result = runner.execute(
        Path(runner.PLAN_REL),
        "confirm",
        pilot_output=Path(runner.PILOT_REL),
        expected_pilot_sha256=pilot_hash,
    )
    assert result["evidence_role"] == "confirmatory"
    assert result["overall"] == "validated"
    assert result["pilot_output_hash"] == pilot_hash
    assert result["source_manifest"] == execution_environment["manifest"]
    assert result["interval_construction"] == runner.UNCERTAINTY["interval"]
    assert all("standard_error_method" in row for row in result["analysis"])
    pilot_direct_b_disc = [
        row["B_disc"]
        for row in pilot_payload["analysis"]
        if row["comparison_kind"] == "direct_reference"
    ]
    confirm_direct_b_disc = [
        row["B_disc"]
        for row in result["analysis"]
        if row["comparison_kind"] == "direct_reference"
    ]
    assert confirm_direct_b_disc != pilot_direct_b_disc
    assert all(value > runner.B_DISC_FLOOR for value in confirm_direct_b_disc)
    assert runner._json_load(confirm) == result


def test_unbiased_covariance_trace_jackknife_small_sample() -> None:
    points = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 2.0]])
    value, standard_error = runner._cov_jackknife(points)
    assert value == pytest.approx(8 / 3)
    assert standard_error == pytest.approx(4 / 3)
    paired, paired_standard_error = runner._cov_jackknife(points, points * 2)
    assert paired == pytest.approx(-8.0)
    assert paired_standard_error == pytest.approx(4.0)


def test_public_paired_result_exposes_unbiased_jackknife_covariance_trace() -> None:
    result = simulate_free_paired(
        inertia=0.8,
        activity=1.2,
        end_time=0.2,
        fine_step=0.01,
        ensemble_size=8,
        seed=4,
    )
    value, standard_error = covariance_trace_jackknife(result.fine_positions)
    paired, paired_standard_error = covariance_trace_jackknife(
        result.fine_positions, result.coarse_positions
    )
    assert result.fine.values["centered_spatial_variance"] == pytest.approx(value)
    assert result.fine.standard_errors["centered_spatial_variance"] == pytest.approx(
        standard_error
    )
    assert (
        result.fine.values["centered_spatial_variance"]
        - result.coarse.values["centered_spatial_variance"]
    ) == pytest.approx(paired)
    assert result.paired_standard_errors[
        "centered_spatial_variance"
    ] == pytest.approx(paired_standard_error)
