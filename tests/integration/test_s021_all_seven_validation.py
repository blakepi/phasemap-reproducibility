"""Result-free tests for the frozen S-021 all-seven validation route."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import mpmath as mp
import pytest


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    ROOT / "experiments/S-021-all-seven-moment-validation-primary-v1.json"
)
OPERATOR_PATH = ROOT / "experiments/s021_all_seven_operator.py"
ADAPTER_PATH = ROOT / "experiments/s021_formula_adapter.py"
RUNNER_PATH = ROOT / "experiments/run_s021_all_seven_validation.py"
CANONICAL_OUTPUT = (
    ROOT / "artifacts/raw/S-021-all-seven-moment-validation-primary-v1.json"
)

EXPECTED_PLAN_RAW_SHA256 = (
    "c648a3863c85767f43c49a6e315ccf8b599105c3f81c0c5fc4678522f91f1aeb"
)
EXPECTED_PLAN_SEMANTIC_SHA256 = (
    "56106349142a6710a6dc32f5af6d76356d132655367020cda6ec4f5cf2198422"
)
EXPECTED_BASIS = (
    "one",
    "r_x",
    "r_y",
    "v_x",
    "v_y",
    "u_x",
    "u_y",
    "rr_xx",
    "rr_xy",
    "rr_yy",
    "vv_xx",
    "vv_xy",
    "vv_yy",
    "rv_xx",
    "rv_xy",
    "rv_yx",
    "rv_yy",
    "ru_xx",
    "ru_xy",
    "ru_yx",
    "ru_yy",
    "vu_xx",
    "vu_xy",
    "vu_yx",
    "vu_yy",
    "uu_xx",
    "uu_xy",
    "uu_yy",
)
EXPECTED_PROTOCOLS = (
    "P",
    "V",
    "Theta",
    "PV",
    "PTheta",
    "VTheta",
    "PVTheta",
)
EXPECTED_MANIFEST_PATHS = (
    Path("docs/scientific-contract/CONTRACT.md"),
    Path("docs/scientific-contract/validation_registry.json"),
    Path("docs/scientific-contract/validation_registry.schema.json"),
    Path("artifacts/derived/T-012-complete-reset-baseline.md"),
    Path("artifacts/derived/T-020-position-protocols.md"),
    Path("artifacts/derived/T-021-nonposition-protocols.md"),
    Path("artifacts/derived/T-022-formula-registry.md"),
    Path("artifacts/derived/S-020-protocol-registry.md"),
    Path("src/phasemap/theory/complete_reset_baseline.py"),
    Path("src/phasemap/theory/formula_registry.py"),
    Path("src/phasemap/theory/position_protocols.py"),
    Path("src/phasemap/theory/nonposition_protocols.py"),
    Path("experiments/S-021-all-seven-moment-validation-primary-v1.json"),
    Path("experiments/s021_all_seven_operator.py"),
    Path("experiments/s021_formula_adapter.py"),
    Path("experiments/run_s021_all_seven_validation.py"),
    Path("tests/integration/test_s021_all_seven_validation.py"),
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


operator = _load_module("s021_operator_under_test", OPERATOR_PATH)
adapter = _load_module("s021_adapter_under_test", ADAPTER_PATH)
runner = _load_module("s021_runner_under_test", RUNNER_PATH)


def _semantic_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expected_reset_state(
    state: mp.matrix,
    flags: tuple[int, int, int],
) -> mp.matrix:
    p, v, h = flags
    kp, kv, kh = 1 - p, 1 - v, 1 - h
    result = mp.zeros(28, 1)
    result[0] = state[0]
    result[1] = kp * state[1]
    result[2] = kp * state[2]
    result[3] = kv * state[3]
    result[4] = kv * state[4]
    result[5] = kh * state[5] + h * state[0]
    result[6] = kh * state[6]
    result[7] = kp * state[7]
    result[8] = kp * state[8]
    result[9] = kp * state[9]
    result[10] = kv * state[10]
    result[11] = kv * state[11]
    result[12] = kv * state[12]
    result[13] = kp * kv * state[13]
    result[14] = kp * kv * state[14]
    result[15] = kp * kv * state[15]
    result[16] = kp * kv * state[16]
    result[17] = kp * kh * state[17] + kp * h * state[1]
    result[18] = kp * kh * state[18]
    result[19] = kp * kh * state[19] + kp * h * state[2]
    result[20] = kp * kh * state[20]
    result[21] = kv * kh * state[21] + kv * h * state[3]
    result[22] = kv * kh * state[22]
    result[23] = kv * kh * state[23] + kv * h * state[4]
    result[24] = kv * kh * state[24]
    result[25] = kh * state[25] + h * state[0]
    result[26] = kh * state[26]
    result[27] = kh * state[27]
    return result


def _expected_ito_operator(M: mp.mpf, Pe: mp.mpf) -> mp.matrix:
    expected = mp.zeros(28, 28)
    inverse_M = 1 / M
    entries = {
        (1, 3): 1,
        (2, 4): 1,
        (3, 3): -inverse_M,
        (3, 5): Pe * inverse_M,
        (4, 4): -inverse_M,
        (4, 6): Pe * inverse_M,
        (5, 5): -1,
        (6, 6): -1,
        (7, 13): 2,
        (8, 14): 1,
        (8, 15): 1,
        (9, 16): 2,
        (10, 0): 2 * inverse_M**2,
        (10, 10): -2 * inverse_M,
        (10, 21): 2 * Pe * inverse_M,
        (11, 11): -2 * inverse_M,
        (11, 22): Pe * inverse_M,
        (11, 23): Pe * inverse_M,
        (12, 0): 2 * inverse_M**2,
        (12, 12): -2 * inverse_M,
        (12, 24): 2 * Pe * inverse_M,
        (13, 10): 1,
        (13, 13): -inverse_M,
        (13, 17): Pe * inverse_M,
        (14, 11): 1,
        (14, 14): -inverse_M,
        (14, 18): Pe * inverse_M,
        (15, 11): 1,
        (15, 15): -inverse_M,
        (15, 19): Pe * inverse_M,
        (16, 12): 1,
        (16, 16): -inverse_M,
        (16, 20): Pe * inverse_M,
        (17, 17): -1,
        (17, 21): 1,
        (18, 18): -1,
        (18, 22): 1,
        (19, 19): -1,
        (19, 23): 1,
        (20, 20): -1,
        (20, 24): 1,
        (21, 21): -(1 + inverse_M),
        (21, 25): Pe * inverse_M,
        (22, 22): -(1 + inverse_M),
        (22, 26): Pe * inverse_M,
        (23, 23): -(1 + inverse_M),
        (23, 26): Pe * inverse_M,
        (24, 24): -(1 + inverse_M),
        (24, 27): Pe * inverse_M,
        (25, 0): 2,
        (25, 25): -4,
        (26, 26): -4,
        (27, 0): 2,
        (27, 27): -4,
    }
    for (row, column), value in entries.items():
        expected[row, column] = value
    return expected


def test_plan_raw_and_semantic_locks_are_exact() -> None:
    raw = PLAN_PATH.read_bytes()
    plan = runner.load_preregistered_plan(PLAN_PATH)
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_PLAN_RAW_SHA256
    assert _semantic_hash(plan) == EXPECTED_PLAN_SEMANTIC_SHA256
    assert runner.EXPECTED_PLAN_RAW_SHA256 == EXPECTED_PLAN_RAW_SHA256
    assert (
        runner.EXPECTED_PLAN_SEMANTIC_SHA256
        == EXPECTED_PLAN_SEMANTIC_SHA256
    )
    runner.validate_preregistered_plan(plan)


@pytest.mark.parametrize(
    "invalid_json",
    (
        '{"duplicate":1,"duplicate":2}',
        '{"nonfinite":NaN}',
        '{"nested":{"nonfinite":1e999}}',
        "[]",
    ),
)
def test_strict_plan_loader_rejects_invalid_json(
    invalid_json: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path("plan.json")
    (tmp_path / relative).write_text(invalid_json, encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "PLAN_REL", relative)
    with pytest.raises(ValueError):
        runner.load_preregistered_plan(tmp_path / relative)


def test_basis_is_exact_and_unique() -> None:
    assert operator.BASIS_NAMES == EXPECTED_BASIS
    assert len(operator.BASIS_NAMES) == len(set(operator.BASIS_NAMES)) == 28
    assert tuple(operator.INDEX) == EXPECTED_BASIS


def test_hand_coded_ito_stencil_is_exact() -> None:
    with mp.workdps(80):
        M = operator.parse_rational("3/2")
        Pe = operator.parse_rational("2/3")
        actual = operator.build_ito_operator(M, Pe)
        expected = _expected_ito_operator(M, Pe)
        assert operator.max_abs(actual - expected) == 0


def test_all_reset_images_and_idempotence_are_exact() -> None:
    assert tuple(operator.PROTOCOL_FLAGS) == EXPECTED_PROTOCOLS
    assert all(
        len(operator.RESET_IMAGE_TERMS[protocol]) == 28
        for protocol in EXPECTED_PROTOCOLS
    )
    for protocol in EXPECTED_PROTOCOLS:
        pullback = operator.reset_pullback(protocol)
        assert operator.max_abs(pullback * pullback - pullback) == 0
        for column in range(28):
            basis_state = mp.zeros(28, 1)
            basis_state[column] = 1
            expected = _expected_reset_state(
                basis_state,
                operator.PROTOCOL_FLAGS[protocol],
            )
            assert operator.max_abs(pullback * basis_state - expected) == 0


def test_orientation_reset_retained_q_and_w_terms_are_exact() -> None:
    theta = operator.reset_pullback("Theta")
    assert theta[17, 1] == theta[19, 2] == 1
    assert theta[21, 3] == theta[23, 4] == 1

    p_theta = operator.reset_pullback("PTheta")
    assert all(p_theta[row, column] == 0 for row in range(17, 21) for column in range(28))
    assert p_theta[21, 3] == p_theta[23, 4] == 1

    v_theta = operator.reset_pullback("VTheta")
    assert v_theta[17, 1] == v_theta[19, 2] == 1
    assert all(v_theta[row, column] == 0 for row in range(21, 25) for column in range(28))


def test_rho_zero_recovers_ito_operator_for_all_protocols() -> None:
    with mp.workdps(60):
        ito = operator.build_ito_operator("3/2", "2/3")
        for protocol in EXPECTED_PROTOCOLS:
            combined = operator.build_operator(protocol, "3/2", "2/3", "0")
            assert operator.max_abs(combined - ito) == 0


def test_default_initial_state_is_exact() -> None:
    state = operator.initial_state()
    expected = mp.zeros(28, 1)
    expected[0] = expected[5] = expected[25] = 1
    assert operator.max_abs(state - expected) == 0


@pytest.mark.parametrize(
    ("protocol", "inertia", "rho", "expected"),
    (
        ("P", "4/5", "1/4", "1/4"),
        ("V", "4/5", "1/4", "1"),
        ("Theta", "4/5", "1/4", "5/4"),
        ("PV", "4/5", "1/4", "1/4"),
        ("PTheta", "4/5", "1/4", "1/4"),
        ("VTheta", "4/5", "1/4", "5/4"),
        ("PVTheta", "4/5", "1/4", "1/4"),
        ("Theta", "2", "3", "1/2"),
        ("V", "2", "3", "1"),
        ("VTheta", "2", "3", "7/2"),
    ),
)
def test_exact_slow_rate_rule(
    protocol: str,
    inertia: str,
    rho: str,
    expected: str,
) -> None:
    with mp.workdps(60):
        assert operator.slow_rate(protocol, inertia, rho) == (
            operator.parse_rational(expected)
        )


def test_noncanonical_position_stationary_solution_and_fields() -> None:
    with mp.workdps(100):
        matrix = operator.build_operator("PTheta", "3/2", "2/3", "5/7")
        state = operator.solve_position_stationary(matrix)
        residual = operator.stationary_residual(matrix, state)
        isolated = operator.flatten_formula_fields(
            operator.stationary_formula_fields(state)
        )
        reference = adapter.t022_reference(
            "PTheta",
            "3/2",
            "2/3",
            "5/7",
            None,
            100,
        )
        assert residual < mp.mpf("1e-90")
        assert tuple(isolated) == tuple(reference)
        assert max(
            abs(isolated[key] - reference[key])
            for key in isolated
            if isolated[key] is not None
        ) < mp.mpf("1e-90")


def test_noncanonical_transport_recurrence_and_fields() -> None:
    with mp.workdps(100):
        matrix = operator.build_operator("VTheta", "3/2", "2/3", "5/7")
        solution = operator.solve_transport_polynomial(matrix)
        residuals = operator.transport_polynomial_residuals(
            matrix,
            solution,
            ("0", "7/5", "3"),
        )
        isolated = operator.flatten_formula_fields(
            operator.reconstruct_transport_formula_fields(solution, "7/5")
        )
        reference = adapter.t022_reference(
            "VTheta",
            "3/2",
            "2/3",
            "5/7",
            "7/5",
            100,
        )
        assert max(residuals.values()) < mp.mpf("1e-90")
        assert tuple(isolated) == tuple(reference)
        assert max(
            abs(isolated[key] - reference[key]) for key in isolated
        ) < mp.mpf("1e-90")


def test_raw_to_centered_field_extraction_is_explicit() -> None:
    state = mp.matrix(list(range(1, 29)))
    state[0] = 1
    fields = operator.stationary_formula_fields(state)
    r = mp.matrix([state[1], state[2]])
    v = mp.matrix([state[3], state[4]])
    u = mp.matrix([state[5], state[6]])
    assert operator.max_abs(fields["Cov_r"] - (fields["R"] - r * r.T)) == 0
    assert operator.max_abs(fields["C_centered"] - (fields["C"] - r * v.T)) == 0
    assert operator.max_abs(fields["Q_centered"] - (fields["Q"] - r * u.T)) == 0
    assert operator.max_abs(fields["Sigma_v"] - (fields["S"] - v * v.T)) == 0
    assert operator.max_abs(fields["Sigma_u"] - (fields["U"] - u * u.T)) == 0
    assert operator.max_abs(fields["K"] - (fields["W"] - v * u.T)) == 0


def test_operator_ast_isolation_and_no_file_access() -> None:
    source = OPERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(OPERATOR_PATH))
    imports: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
    assert not any(
        name.startswith(("phasemap", "sympy", "numpy", "scipy"))
        for name in imports
    )
    assert not imports.intersection({"pathlib", "os", "io", "subprocess"})
    assert not called_names.intersection(
        {
            "open",
            "Path",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "unlink",
            "replace",
            "rename",
        }
    )
    assert "artifacts/raw/S-011" not in source
    assert "artifacts/raw/S-012" not in source
    assert "artifacts/raw/S-021" not in source


def test_adapter_t022_t012_self_check_is_exact() -> None:
    check = adapter.reference_self_check("3/2", "2/3", "5/7", 100)
    assert check == {
        "protocol": "PVTheta",
        "non_null_components": 58,
        "null_fields": 7,
        "max_abs_discrepancy": "0.0",
    }


def test_adapter_probe_and_null_semantics() -> None:
    stationary = adapter.t022_reference(
        "P",
        "3/2",
        "2/3",
        "5/7",
        None,
    )
    transport = adapter.t022_reference(
        "V",
        "3/2",
        "2/3",
        "5/7",
        "7/5",
    )
    assert {key for key, value in stationary.items() if value is None} == {
        "D",
        "b",
        "raw_rr_quadratic",
        "raw_rr_linear",
        "raw_ru_linear",
        "raw_rv_linear",
        "D_eff",
    }
    assert all(value is not None and mp.isfinite(value) for value in transport.values())
    with pytest.raises(ValueError):
        adapter.t022_reference("P", "3/2", "2/3", "5/7", "0")
    with pytest.raises(ValueError):
        adapter.t022_reference("V", "3/2", "2/3", "5/7", None)
    with pytest.raises(ValueError):
        adapter.t022_reference("V", "1.5", "2/3", "5/7", "0")
    with pytest.raises(ValueError):
        adapter.t022_reference("P", "3/2", "2/3", "0", None)


def test_classification_boundaries() -> None:
    zero = mp.mpf("0")
    tolerance = mp.mpf("1e-12")
    residual_tolerance = mp.mpf("1e-30")
    base = {
        "precision": [tolerance],
        "horizon": [tolerance],
        "algebraic": [tolerance],
        "invariants": [tolerance],
        "residuals": [residual_tolerance],
    }
    assert runner.classify(cell_errors=[tolerance], **base) == "validated"
    assert (
        runner.classify(
            cell_errors=[tolerance + mp.mpf("1e-20")],
            **base,
        )
        == "contradicted"
    )
    assert (
        runner.classify(
            cell_errors=[zero, tolerance + mp.mpf("1e-20")],
            **base,
        )
        == "unresolved"
    )
    assert (
        runner.classify(
            cell_errors=[zero],
            precision=[tolerance + mp.mpf("1e-20")],
            horizon=base["horizon"],
            algebraic=base["algebraic"],
            invariants=base["invariants"],
            residuals=base["residuals"],
        )
        == "unresolved"
    )
    assert (
        runner.classify(
            cell_errors=[zero],
            precision=base["precision"],
            horizon=base["horizon"],
            algebraic=base["algebraic"],
            invariants=base["invariants"],
            residuals=[residual_tolerance + mp.mpf("1e-40")],
        )
        == "unresolved"
    )


def test_decimal_serialization_preserves_retained_high_precision() -> None:
    with mp.workdps(100):
        one_seventh = mp.mpf(1) / 7
    with mp.workdps(15):
        serialized = runner._decimal(one_seventh)
    assert serialized == (
        "0.14285714285714285714285714285714285714285714285714"
    )


def test_limit_trend_dispatch_does_not_accept_tiny_flat_sequences() -> None:
    assert runner._strictly_decreasing(
        [mp.mpf("3e-12"), mp.mpf("2e-12"), mp.mpf("1e-12")]
    )
    assert not runner._strictly_decreasing(
        [mp.mpf("1e-50"), mp.mpf("1e-50"), mp.mpf("1e-50")]
    )
    assert runner._strict_or_numerical_identity(
        [mp.mpf("1e-60"), mp.mpf("2e-60"), mp.mpf("3e-60")]
    )
    assert not runner._strict_or_numerical_identity(
        [mp.mpf("1e-20"), mp.mpf("1e-20"), mp.mpf("1e-20")]
    )


def test_limit_outcome_fails_closed_on_record_classification() -> None:
    assert (
        runner._limit_outcome(["validated", "contradicted"], True)
        == "contradicted"
    )
    assert (
        runner._limit_outcome(["validated", "unresolved"], True)
        == "unresolved"
    )
    assert (
        runner._limit_outcome(["validated", "validated"], False)
        == "unresolved"
    )


def test_source_manifest_is_exact() -> None:
    assert tuple(runner.MANIFEST_PATHS) == EXPECTED_MANIFEST_PATHS
    manifest = runner.source_manifest()
    assert tuple(Path(path) for path in manifest) == EXPECTED_MANIFEST_PATHS
    assert all(
        len(digest) == 64
        and set(digest) <= set("0123456789abcdef")
        for digest in manifest.values()
    )


def test_validate_mode_preserves_canonical_output_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = (
        CANONICAL_OUTPUT.read_bytes()
        if CANONICAL_OUTPUT.exists()
        else None
    )

    def forbidden_publish(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("validate mode attempted to publish output")

    monkeypatch.setattr(runner, "_atomic_publish_once", forbidden_publish)
    result = runner.validate()
    assert result["status"] == "validated"
    after = (
        CANONICAL_OUTPUT.read_bytes()
        if CANONICAL_OUTPUT.exists()
        else None
    )
    assert after == before


def test_atomic_publish_never_overwrites(tmp_path: Path) -> None:
    output = tmp_path / "nested/result.json"
    first_hash = runner._atomic_publish_once(
        output,
        {"scientific_value": mp.mpf("1.25")},
    )
    original = output.read_bytes()
    assert first_hash == hashlib.sha256(original).hexdigest()
    with pytest.raises(FileExistsError):
        runner._atomic_publish_once(
            output,
            {"scientific_value": mp.mpf("9.5")},
        )
    assert output.read_bytes() == original


def test_synthetic_payload_does_not_call_canonical_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = getattr(runner, "build_synthetic_payload", None)
    if builder is None:
        pytest.skip("runner exposes no synthetic payload builder")

    def forbidden_grid(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("synthetic payload attempted the canonical grid")

    for name in ("compute_isolated_grid", "_compute_isolated_grid"):
        if hasattr(runner, name):
            monkeypatch.setattr(runner, name, forbidden_grid)
    payload = builder()
    assert isinstance(payload, dict)
    assert payload.get("synthetic") is True
    assert payload.get("canonical_grid_evaluated") is False
