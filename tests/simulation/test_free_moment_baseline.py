from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import sympy as sp

import experiments.run_s011_free_moment_matrix as runner
import phasemap.simulation.free_moment_baseline as moment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = PROJECT_ROOT / runner.PLAN_REL


def _plan() -> dict[str, Any]:
    return runner.load_preregistered_plan(PLAN_PATH)


def test_frozen_plan_validates_and_any_semantic_mutation_fails() -> None:
    plan = _plan()
    runner.validate_preregistered_plan(plan)

    changed = deepcopy(plan)
    changed["propagation"]["fine_max_step"] = "1/64"
    with pytest.raises(ValueError, match="frozen preregistration"):
        runner.validate_preregistered_plan(changed)


@pytest.mark.parametrize(
    "text, message",
    [
        ('{"plan_id":"a","plan_id":"b"}', "duplicate JSON key"),
        ('{"value":NaN}', "nonfinite JSON value"),
    ],
)
def test_plan_loader_rejects_duplicate_and_nonfinite_json(
    tmp_path: Path,
    text: str,
    message: str,
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        runner.load_preregistered_plan(path)


def test_exact_t010_basis_matrix_and_locked_initial_state() -> None:
    system = moment.build_free_moment_matrix("4/5", "6/5")
    assert system.names == moment.BASIS_NAMES
    assert system.values.shape == (28, 28)
    assert system.values.dtype == np.float64
    assert not system.values.flags.writeable
    assert np.isfinite(system.values).all()

    initial = moment.default_free_moment_state(system.names)
    expected = np.zeros(28, dtype=np.float64)
    index = {name: position for position, name in enumerate(system.names)}
    expected[index["one"]] = 1.0
    expected[index["u_x"]] = 1.0
    expected[index["uu_xx"]] = 1.0
    np.testing.assert_array_equal(initial, expected)


def test_taylor18_step_is_accurate_for_locked_scalar_edge_and_nilpotent() -> None:
    scalar = moment.taylor18_step(np.array([[-16.0]]), np.array([1.0]), 1 / 16)
    assert scalar[0] == pytest.approx(math.exp(-1.0), abs=2e-16)

    nilpotent = np.array([[0.0, 1.0], [0.0, 0.0]])
    state = moment.taylor18_step(nilpotent, np.array([0.0, 1.0]), 0.25)
    np.testing.assert_array_equal(state, np.array([0.25, 1.0]))


def test_zero_time_is_an_exact_no_step_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_step(*args: object, **kwargs: object) -> np.ndarray:
        raise AssertionError("Taylor step must not be called at t=0")

    monkeypatch.setattr(moment, "taylor18_step", forbidden_step)
    initial = np.array([1.0, 2.0])
    result = moment.propagate_free_moment_state(
        np.zeros((2, 2)), initial, "0", "1/32"
    )
    assert result.step_count == 0
    assert result.step_size == 0
    np.testing.assert_array_equal(result.state, initial)
    assert result.state is not initial


def test_propagation_uses_exact_ceiling_and_equal_steps() -> None:
    result = moment.propagate_free_moment_state(
        np.zeros((1, 1)), np.array([2.0]), "3/20", "1/16"
    )
    assert result.step_count == 3
    assert result.step_size == sp.Rational(1, 20)
    np.testing.assert_array_equal(result.state, np.array([2.0]))


def test_numerical_core_fails_closed_on_invalid_inputs() -> None:
    with pytest.raises(TypeError, match="exact rational"):
        moment.build_free_moment_matrix(0.8, "6/5")
    with pytest.raises(ValueError, match="at least 1/8"):
        moment.build_free_moment_matrix("0", "6/5")
    with pytest.raises(ValueError, match="nonnegative"):
        moment.build_free_moment_matrix("4/5", "-1")
    with pytest.raises(ValueError, match="square"):
        moment.taylor18_step(np.zeros((2, 3)), np.zeros(2), 0.1)
    with pytest.raises(FloatingPointError, match="finite"):
        moment.taylor18_step(np.array([[np.nan]]), np.ones(1), 0.1)
    with pytest.raises(ValueError, match="step_size"):
        moment.taylor18_step(np.zeros((1, 1)), np.ones(1), math.inf)
    with pytest.raises(ValueError, match="nonnegative"):
        moment.propagate_free_moment_state(
            np.zeros((1, 1)), np.ones(1), "-1", "1/32"
        )
    with pytest.raises(TypeError, match="exact rational"):
        moment.propagate_free_moment_state(
            np.zeros((1, 1)), np.ones(1), 0.5, "1/32"
        )
    with pytest.raises(ValueError, match="must not exceed 6"):
        moment.propagate_free_moment_state(
            np.zeros((1, 1)), np.ones(1), "7", "1/32"
        )
    with pytest.raises(ValueError, match="exactly 1/16 or 1/32"):
        moment.propagate_free_moment_state(
            np.zeros((1, 1)), np.ones(1), "1", "1/64"
        )


def test_locked_observable_and_invariant_extraction() -> None:
    state = np.arange(28, dtype=np.float64)
    observables = moment.extract_free_observables(moment.BASIS_NAMES, state)
    assert tuple(observables) == moment.OBSERVABLE_NAMES
    assert observables == {
        "orientation_mean_x": 5.0,
        "mean_velocity_x": 3.0,
        "mean_position_x": 1.0,
        "velocity_dot_orientation": 45.0,
        "position_dot_orientation": 37.0,
        "mean_squared_speed": 22.0,
        "mean_position_dot_velocity": 29.0,
        "mean_squared_displacement": 16.0,
        "centered_spatial_variance": 11.0,
    }

    invariants = moment.extract_free_invariants(moment.BASIS_NAMES, state)
    assert invariants["constant"] == 0.0
    assert invariants["orientation_norm"] == 52.0
    zeros = invariants["symmetry_forced_zero"]
    assert isinstance(zeros, dict)
    assert tuple(zeros) == moment.SYMMETRY_ZERO_NAMES
    assert zeros["uu_xy"] == 26.0


def test_locked_classification_and_overall_precedence() -> None:
    validated = runner.classify_values(0.0, 5e-13, 0.0)
    contradicted = runner.classify_values(2e-12, 2.5e-12, 0.0)
    unresolved = runner.classify_values(2e-12, 5e-13, 0.0)
    assert validated["classification"] == "validated"
    assert contradicted["classification"] == "contradicted"
    assert unresolved["classification"] == "unresolved"
    assert runner.aggregate_classifications(["validated"]) == "validated"
    assert (
        runner.aggregate_classifications(["validated"], trend_passed=False)
        == "unresolved"
    )
    assert (
        runner.aggregate_classifications(
            ["unresolved", "contradicted"], trend_passed=False
        )
        == "contradicted"
    )
    with pytest.raises(ValueError, match="invalid or empty"):
        runner.aggregate_classifications([])


def _synthetic_support_rows(plan: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    case_ids = {
        case["inertia"]: case["id"]
        for case in plan["parameter_cases"]
        if case["activity"] == "6/5"
    }
    fine_by_inertia = {"1/2": 13.0, "1/4": 12.0, "1/8": 11.0}
    return {
        (case_ids[inertia], time): {
            "comparisons": [
                {
                    "observable": "mean_squared_displacement",
                    "fine": fine_by_inertia[inertia],
                    "classification": "validated",
                }
            ]
        }
        for inertia in ("1/2", "1/4", "1/8")
        for time in plan["overdamped_support"]["times"]
    }


def test_overdamped_support_uses_only_eligible_fine_msd_and_strict_trend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    rows = _synthetic_support_rows(plan)
    monkeypatch.setattr(
        runner,
        "overdamped_mean_squared_displacement",
        lambda time, activity: sp.Integer(10),
    )
    result = runner.evaluate_overdamped_support(plan, rows)
    assert result["passed"] is True
    assert all(row["eligible"] and row["passed"] for row in result["times"])

    first_time = plan["overdamped_support"]["times"][0]
    final_case = next(
        case["id"]
        for case in plan["parameter_cases"]
        if case["inertia"] == "1/8" and case["activity"] == "6/5"
    )
    rows[(final_case, first_time)]["comparisons"][0]["fine"] = 12.0
    result = runner.evaluate_overdamped_support(plan, rows)
    assert result["passed"] is False


def test_source_manifest_and_atomic_single_publication(tmp_path: Path) -> None:
    manifest = runner.source_manifest()
    assert set(manifest) == {path.as_posix() for path in runner.MANIFEST_PATHS}
    assert all(
        len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
        for digest in manifest.values()
    )
    metadata = runner._float64_metadata()
    assert metadata["bits"] == 64
    assert metadata["eps"] == np.finfo(np.float64).eps

    output = tmp_path / "artifact.json"
    digest = runner._atomic_publish_once(output, {"finite": 1.0})
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError, match="already exists"):
        runner._atomic_publish_once(output, {"finite": 2.0})


def test_result_payload_records_locked_provenance_without_running_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    synthetic_case = {
        "id": "synthetic",
        "inertia": "1",
        "activity": "0",
        "matrix_sha256": "a" * 64,
        "times": [
            {
                "time": "0",
                "coarse": {"step_count": 0},
                "fine": {"step_count": 0},
                "comparisons": [{"classification": "validated"}],
                "invariants": [{"classification": "validated"}],
            }
        ],
        "classification": "validated",
    }
    monkeypatch.setattr(runner, "_case_results", lambda plan: ([synthetic_case], {}))
    monkeypatch.setattr(
        runner,
        "evaluate_overdamped_support",
        lambda plan, rows: {"passed": True, "times": []},
    )
    payload = runner.build_result_payload(
        plan,
        source_commit="b" * 40,
        manifest={"synthetic": "c" * 64},
    )
    assert payload["overall_classification"] == "validated"
    assert payload["source_commit"] == "b" * 40
    assert payload["source_manifest"] == {"synthetic": "c" * 64}
    assert payload["configuration"]["matrix_hashes"] == {"synthetic": "a" * 64}
    assert payload["configuration"]["initial_state_sha256"]
    assert payload["configuration"]["ensemble_size"] == "not_applicable"
    assert payload["environment"]["float64"]["bits"] == 64
    assert "recorded externally" in payload["canonical_artifact_hash_recording"]


def test_numerical_module_has_no_reference_or_stochastic_import() -> None:
    path = PROJECT_ROOT / "src/phasemap/simulation/free_moment_baseline.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert "phasemap.theory.free_baseline" not in imported_modules
    assert "phasemap.simulation.free_baseline" not in imported_modules
    assert imported_modules & {"scipy", "scipy.linalg"} == set()
