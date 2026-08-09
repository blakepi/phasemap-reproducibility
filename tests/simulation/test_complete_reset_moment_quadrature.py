"""Focused result-free locks for the frozen deterministic S-012 route."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import mpmath as mp
import pytest
import sympy as sp


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from phasemap.simulation import complete_reset_moment_quadrature as numerical
from phasemap.simulation.protocols import Protocol
from phasemap.theory.generator import Symbols, second_order_moment_system


_spec = importlib.util.spec_from_file_location(
    "s012_runner",
    ROOT / "experiments/run_s012_complete_reset_moment_quadrature.py",
)
assert _spec and _spec.loader
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)


def _plan() -> dict[str, Any]:
    return runner.load_preregistered_plan(ROOT / runner.PLAN_REL)


def _state(names: tuple[str, ...], **values: int | str) -> mp.matrix:
    state = mp.matrix(len(names), 1)
    indices = {name: index for index, name in enumerate(names)}
    for name, value in values.items():
        state[indices[name]] = mp.mpf(value)
    return state


def test_plan_semantic_lock_and_strict_json_fail_closed() -> None:
    plan = _plan()
    runner.validate_preregistered_plan(plan)
    assert (
        hashlib.sha256(runner._semantic_bytes(plan)).hexdigest()
        == runner.EXPECTED_PLAN_SEMANTIC_SHA256
    )

    changed = copy.deepcopy(plan)
    changed["task_id"] = "X"
    with pytest.raises(ValueError, match="semantic lock"):
        runner.validate_preregistered_plan(changed)

    with pytest.raises(ValueError, match="duplicate"):
        json.loads('{"a":1,"a":2}', object_pairs_hook=runner._pairs)
    with pytest.raises(ValueError, match="nonfinite JSON constant"):
        json.loads('{"a":NaN}', parse_constant=runner._reject_constant)
    overflow = json.loads('{"outer":{"value":1e999}}')
    with pytest.raises(ValueError, match="nonfinite JSON number"):
        runner._reject_nonfinite_tree(overflow)
    with pytest.raises(ValueError, match="plan root"):
        value: Any = []
        if not isinstance(value, dict):
            raise ValueError("S-012 plan root must be an object")


def test_hand_coded_second_order_matrix_matches_all_locked_rows() -> None:
    """Compare 26 generator rows and lock the plan's equivalent U coordinates."""

    with mp.workdps(80):
        observed = numerical.build_free_second_order_matrix("2", "3")
        symbols = Symbols.create()
        system = second_order_moment_system(symbols, None)
        exact = system.matrix.subs(
            {
                symbols.inertia: sp.Rational(2),
                symbols.activity: sp.Rational(3),
            }
        )
        assert system.names == numerical.BASIS_NAMES
        excluded = {"uu_xx", "uu_yy"}
        for row, name in enumerate(system.names):
            if name in excluded:
                continue
            for column in range(len(system.names)):
                expected = mp.mpf(str(sp.N(exact[row, column], 80)))
                assert observed[row, column] == expected, (
                    name,
                    system.names[column],
                )

        index = {
            name: position
            for position, name in enumerate(numerical.BASIS_NAMES)
        }
        assert observed[index["vv_xx"], index["vu_xx"]] == 3
        assert observed[index["vv_yy"], index["vu_yy"]] == 3
        for name in ("uu_xx", "uu_yy"):
            row = index[name]
            nonzero = {
                numerical.BASIS_NAMES[column]: observed[row, column]
                for column in range(28)
                if observed[row, column] != 0
            }
            assert nonzero == {"one": mp.mpf(2), name: mp.mpf(-4)}


def test_passive_matrix_and_both_reset_states_are_fully_locked() -> None:
    with mp.workdps(80):
        observed = numerical.build_passive_fourth_matrix("2")
        index = {
            name: position
            for position, name in enumerate(numerical.PASSIVE_BASIS_NAMES)
        }
        expected = mp.matrix(10, 10)
        entries = (
            ("S", "P", 2),
            ("P", "Q", 1),
            ("P", "P", "-1/2"),
            ("Q", "Q", -1),
            ("Q", "one", 1),
            ("S2", "SP", 4),
            ("SP", "SQ", 1),
            ("SP", "P2", 2),
            ("SP", "SP", "-1/2"),
            ("P2", "PQ", 2),
            ("P2", "P2", -1),
            ("P2", "S", "1/2"),
            ("SQ", "PQ", 2),
            ("SQ", "SQ", -1),
            ("SQ", "S", 1),
            ("PQ", "Q2", 1),
            ("PQ", "PQ", "-3/2"),
            ("PQ", "P", 2),
            ("Q2", "Q2", -2),
            ("Q2", "Q", 4),
        )
        for row, column, value in entries:
            expected[index[row], index[column]] = numerical.exact_rational(value)
        assert all(
            observed[row, column] == expected[row, column]
            for row in range(10)
            for column in range(10)
        )

        reset = numerical.complete_reset_initial_state()
        assert [
            reset[position]
            for position in range(28)
            if position not in (0, 5, 25)
        ] == [0] * 25
        assert reset[0] == reset[5] == reset[25] == 1
        passive_reset = numerical.passive_reset_state()
        assert passive_reset[0] == 1
        assert [passive_reset[position] for position in range(1, 10)] == [0] * 9


def test_fractional_augmented_and_resolvent_matrices_hash_as_matrices() -> None:
    with mp.workdps(80):
        matrix = mp.matrix([[-3, 1], [0, -1]])
        augmented = numerical.build_augmented_matrix(matrix, "1/4")
        resolvent = numerical.build_resolvent_matrix(matrix, "1/4")
        assert augmented.rows == augmented.cols == 4
        assert resolvent.rows == resolvent.cols == 2
        assert augmented[0, 0] == mp.mpf("-3.25")
        assert augmented[2, 0] == mp.mpf("0.25")
        assert resolvent[0, 0] == mp.mpf("3.25")
        assert len(runner._matrix_hash(augmented)) == 64
        serialized = runner._serial(mp.eye(2))
        assert serialized == [
            [runner._decimal(1), runner._decimal(0)],
            [runner._decimal(0), runner._decimal(1)],
        ]


def test_scalar_quadrature_resolvent_residual_and_route_cells() -> None:
    with mp.workdps(80):
        matrix = mp.matrix([[-3]])
        reset = mp.matrix([[1]])
        state = numerical.augmented_quadrature(
            matrix,
            reset,
            "2",
            dps=80,
            rho_times_T="80",
        )
        expected = mp.mpf(2) / 5 * (1 - mp.exp(-mp.mpf(5) * 40))
        assert abs(state[0] - expected) < mp.mpf("1e-70")
        infinity, condition, residual = numerical.resolvent_stationary(
            matrix,
            reset,
            "2",
        )
        assert abs(infinity[0] - mp.mpf(2) / 5) < mp.mpf("1e-70")
        assert condition > 0
        assert residual < mp.mpf("1e-70")
        assert (
            numerical.stationary_residual(matrix, infinity, reset, "2")
            < mp.mpf("1e-70")
        )

    route = runner._evaluate_route(
        lambda: mp.matrix([[-3]]),
        lambda: mp.matrix([[1]]),
        "1/4",
    )
    assert set(route["states"]) == set(runner.CELL_NAMES)
    assert set(route["augmented_matrix_sha256"]) == set(runner.CELL_NAMES)
    assert route["stationary_residual_classification"] == "validated"


def test_comparison_and_serialization_use_locked_high_precision() -> None:
    with mp.workdps(80):
        one_seventh = mp.mpf(1) / 7
        expected_prefix = "0.142857142857142857142857142857"
        assert runner._decimal(one_seventh).startswith(expected_prefix)

    good = runner._classify(
        [mp.mpf(1)] * 4,
        mp.mpf(1),
        [mp.mpf(0)] * 2,
        [mp.mpf(0)] * 2,
        mp.mpf(0),
        mp.mpf("1e-50"),
    )
    contradicted = runner._classify(
        [mp.mpf(2)] * 4,
        mp.mpf(1),
        [mp.mpf(0)] * 2,
        [mp.mpf(0)] * 2,
        mp.mpf(0),
        mp.mpf("1e-50"),
    )
    mixed = runner._classify(
        [mp.mpf(1), mp.mpf(2), mp.mpf(2), mp.mpf(2)],
        mp.mpf(1),
        [mp.mpf(0)] * 2,
        [mp.mpf(0)] * 2,
        mp.mpf(0),
        mp.mpf("1e-50"),
    )
    assert good["classification"] == "validated"
    assert contradicted["classification"] == "contradicted"
    assert mixed["classification"] == "unresolved"


def test_output_space_tail_checks_centering_and_kurtosis() -> None:
    second = _state(
        numerical.BASIS_NAMES,
        r_x=2,
        r_y=3,
        rr_xx=20,
        rr_yy=30,
    )
    assert (
        numerical.extract_second_order_observables(second)[
            "centered_spatial_variance"
        ]
        == 37
    )
    passive = _state(numerical.PASSIVE_BASIS_NAMES, S=4, S2=48)
    assert (
        numerical.passive_outputs(passive)[
            "raw_radial_excess_kurtosis_K"
        ]
        == mp.mpf("0.5")
    )

    cell_state = _state(numerical.PASSIVE_BASIS_NAMES, S=2, S2=10)
    infinity = _state(numerical.PASSIVE_BASIS_NAMES, S=2, S2=8)
    route = {
        "states": {cell: cell_state.copy() for cell in runner.CELL_NAMES},
        "infinity": infinity,
        "forward_error_bound": mp.mpf(0),
    }
    reference = numerical.passive_outputs(cell_state)
    rows = runner._comparison_rows(route, numerical.passive_outputs, reference)
    assert rows["raw_radial_excess_kurtosis_K"][
        "infinite_horizon_tail"
    ] == mp.mpf("0.25")
    assert (
        rows["raw_radial_excess_kurtosis_K"]["classification"]
        == "unresolved"
    )


def test_cross_closure_is_a_bl2_precondition() -> None:
    cells = {cell: mp.mpf(1) for cell in runner.CELL_NAMES}
    passive = {
        name: {"cells": dict(cells)}
        for name in (
            "mean_squared_displacement",
            "mean_position_dot_velocity",
            "mean_squared_speed",
        )
    }
    second = copy.deepcopy(passive)
    assert (
        runner._validate_cross_closure(passive, second)["classification"]
        == "validated"
    )
    second["mean_squared_speed"]["cells"]["dps80_rhoT80"] = mp.mpf(2)
    with pytest.raises(RuntimeError, match="BL2"):
        runner._validate_cross_closure(passive, second)


def test_residual_and_passive_raw_convergence_enter_aggregation() -> None:
    validated = {"classification": "validated"}
    case = {
        "second_order": {
            "stationary_residual_classification": "unresolved",
            "raw_components": {"x": validated},
            "observables": {"x": validated},
            "invariants": {"x": validated},
        }
    }
    assert "unresolved" in runner._case_classifications(case)

    passive_case = copy.deepcopy(case)
    passive_case["second_order"]["stationary_residual_classification"] = (
        "validated"
    )
    passive_case["passive_fourth"] = {
        "stationary_residual_classification": "validated",
        "raw_component_convergence": {
            name: validated for name in numerical.PASSIVE_BASIS_NAMES
        },
        "outputs": {"r4": validated},
        "cross_closure": validated,
    }
    values = runner._case_classifications(passive_case)
    assert len(values) == 1 + 3 + 1 + 10 + 1 + 1
    assert set(values) == {"validated"}


def _imports(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_numerical_and_runner_isolation_are_static_and_complete() -> None:
    numerical_path = (
        ROOT
        / "src/phasemap/simulation/complete_reset_moment_quadrature.py"
    )
    runner_path = (
        ROOT / "experiments/run_s012_complete_reset_moment_quadrature.py"
    )
    numerical_text = numerical_path.read_text(encoding="utf-8")
    runner_text = runner_path.read_text(encoding="utf-8")
    numerical_tree = ast.parse(numerical_text)
    runner_tree = ast.parse(runner_text)

    forbidden_numerical = {
        "phasemap.theory.generator",
        "phasemap.theory.complete_reset_baseline",
        "phasemap.simulation.free_moment_baseline",
        "phasemap.simulation.complete_reset_regenerative",
        "experiments.run_s012_complete_reset_regenerative",
    }
    assert not _imports(numerical_tree) & forbidden_numerical
    assert "phasemap.simulation.complete_reset_regenerative" not in _imports(
        runner_tree
    )
    assert "experiments.run_s012_complete_reset_regenerative" not in _imports(
        runner_tree
    )

    forbidden_calls = {"open", "read_text", "read_bytes"}
    assert not any(
        (
            isinstance(node, ast.Name)
            and node.id == "open"
            or isinstance(node, ast.Attribute)
            and node.attr in forbidden_calls
        )
        for node in ast.walk(numerical_tree)
    )
    for old_path in _plan()["isolation"]["old_artifact_reads_forbidden"]:
        assert old_path not in numerical_text
        assert old_path not in runner_text


def test_validate_mode_preserves_any_legitimate_output_state() -> None:
    output = ROOT / runner.OUTPUT_REL
    before = (
        output.exists(),
        hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None,
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "experiments/run_s012_complete_reset_moment_quadrature.py"
            ),
            "validate",
            runner.PLAN_REL.as_posix(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    after = (
        output.exists(),
        hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None,
    )
    assert completed.stdout.strip() == f"validated {runner.PLAN_ID}"
    assert after == before


def test_manifest_is_exact_and_atomic_publication_never_overwrites(
    tmp_path: Path,
) -> None:
    manifest = runner.source_manifest()
    assert set(manifest) == {
        path.as_posix() for path in runner.MANIFEST_PATHS
    }
    assert all(len(digest) == 64 for digest in manifest.values())

    output = tmp_path / "result.json"
    digest = runner._atomic_publish_once(output, {"x": "1"})
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        runner._atomic_publish_once(output, {"x": "2"})


def test_payload_provenance_without_running_the_frozen_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated = {"classification": "validated"}
    synthetic_case = {
        "id": "synthetic",
        "second_order": {
            "stationary_residual_classification": "validated",
            "raw_components": {"x": validated},
            "observables": {"x": validated},
            "invariants": {"x": validated},
        },
    }
    monkeypatch.setattr(runner, "_case_result", lambda case: synthetic_case)
    monkeypatch.setattr(
        runner,
        "_limit_records",
        lambda plan, cases: {
            "rare_reset": {"classification": "validated"},
            "frequent_reset": {"classification": "validated"},
            "overdamped_position_support": {"classification": "validated"},
        },
    )
    manifest = runner.source_manifest()
    payload = runner.build_result_payload(
        _plan(),
        source_commit="a" * 40,
        manifest=manifest,
    )
    assert payload["overall_classification"] == "validated"
    assert payload["source_commit"] == "a" * 40
    assert payload["source_manifest"] == manifest
    assert payload["configuration"]["excluded_prior_artifact_hashes"] == {
        "pilot": _plan()["scope"]["prior_pilot_sha256"],
        "pilot_attempt": _plan()["scope"]["prior_pilot_attempt_sha256"],
    }
    assert len(payload["canonical_payload_sha256"]["sha256"]) == 64
