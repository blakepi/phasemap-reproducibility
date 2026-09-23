"""Integration tests for the post-result S-074 Richardson reanalysis."""

import hashlib
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from phasemap.simulation.precision_statistics import FeatureAccumulator, build_features


reanalysis = importlib.import_module("scripts.reanalyze_s074_richardson")


def test_reanalysis_entrypoint_exists() -> None:
    """Deleting the authorized CPU-only entrypoint must fail the contract."""

    root = Path(__file__).resolve().parents[2]
    assert (root / "scripts/reanalyze_s074_richardson.py").is_file()


def _state(paths: np.ndarray, times: np.ndarray, mode: str = "localized") -> tuple[dict[str, object], dict[str, object]]:
    features, layout = build_features(paths, times, mode)
    accumulator = FeatureAccumulator().add(features)
    return accumulator.to_dict(), layout


def _row(observable: str) -> dict[str, object]:
    return {
        "id": f"case:{observable}", "case_id": "case", "observable": observable,
        "observable_class": "stationary_variance" if observable == "spatial" else "rv",
        "reference": 0.0, "precision_scale": 2.0, "tau": 0.2, "epsilon": 1.0,
        "q": 2.5758293035, "transient_residual": 0.03,
    }


def _original(observable: str) -> dict[str, object]:
    return {
        **_row(observable), "estimate": 0.2, "se": 0.1, "b_window": 0.04,
        "classification": "validated", "precision_pass": False,
        "discretization_pass": True, "qualification_pass": False,
    }


def _case(layout: dict[str, object]) -> dict[str, object]:
    return {
        "id": "case", "group": "core", "protocol": "V", "M": 0.8,
        "Pe": 1.2, "rho": 1.0, "layout": layout,
    }


def _literal_spatial(sample: np.ndarray, times: np.ndarray, coefficients: tuple[float, float, float]) -> float:
    selected = np.flatnonzero(times >= 0.5 * times[-1])
    total = 0.0
    for level, coefficient in enumerate(coefficients):
        values = []
        for time_index in selected:
            x = sample[level, time_index, :, 0]
            y = sample[level, time_index, :, 1]
            values.append(float(np.var(x, ddof=1) + np.var(y, ddof=1)))
        total += coefficient * float(np.mean(values))
    return total


def test_exact_nonlinear_paired_jackknife_matches_literal_deletions() -> None:
    """Independent-error addition or marginal reconstruction breaks this equality."""

    times = np.arange(4.0)
    paths = np.zeros((3, 4, 6, 5), dtype=float)
    base = np.array([0.0, 1.0, 2.0, 4.0, 7.0, 11.0])
    for level, scale in enumerate((1.0, 0.7, 0.2)):
        paths[level, :, :, 0] = scale * base[None, :] + times[:, None]
        paths[level, :, :, 1] = (scale + 0.3) * base[None, :] - 0.5 * times[:, None]
    state, layout = _state(paths, times)

    result, _ = reanalysis.reanalyze_row(_case(layout), _row("spatial"), _original("spatial"), state)

    expected_value = _literal_spatial(paths, times, (2.0, -1.0, 0.0))
    deleted = np.array([
        _literal_spatial(np.delete(paths, index, axis=2), times, (2.0, -1.0, 0.0))
        for index in range(paths.shape[2])
    ])
    expected_se = math.sqrt((paths.shape[2] - 1) / paths.shape[2] * float(np.sum((deleted - deleted.mean()) ** 2)))
    assert result["estimate"] == pytest.approx(expected_value, abs=1e-12)
    assert result["se"] == pytest.approx(expected_se, abs=1e-12)
    assert result["raw_primary"] == _original("spatial")


def test_linear_richardson_uses_paired_trajectory_covariance() -> None:
    """Replacing paired covariance by independent SE addition changes this literal answer."""

    times = np.arange(4.0)
    paths = np.zeros((3, 4, 7, 5), dtype=float)
    fine = np.array([-2.0, -1.0, 0.0, 0.5, 2.0, 3.0, 5.0])
    paths[0, :, :, 2] = fine[None, :]
    paths[1, :, :, 2] = (0.5 * fine + 1.0)[None, :]
    paths[2, :, :, 2] = (-fine + 2.0)[None, :]
    state, layout = _state(paths, times)

    result, raw_steps = reanalysis.reanalyze_row(_case(layout), _row("v_x"), _original("v_x"), state)

    per_path = 2.0 * fine - (0.5 * fine + 1.0)
    assert result["estimate"] == pytest.approx(float(per_path.mean()))
    assert result["se"] == pytest.approx(float(per_path.std(ddof=1) / math.sqrt(per_path.size)))
    assert len(raw_steps) == 3
    assert raw_steps[0]["richardson_value"] == pytest.approx(result["estimate"])


def test_zero_noise_marks_convergence_ratio_indeterminate() -> None:
    """A negligible fine/coarse bias must not produce a spurious convergence ratio."""

    paths = np.zeros((3, 4, 5, 5), dtype=float)
    paths[:, :, :, 2] = 2.0
    state, layout = _state(paths, np.arange(4.0))
    result, _ = reanalysis.reanalyze_row(_case(layout), _row("v_x"), _original("v_x"), state)
    assert result["se"] == 0.0
    assert result["convergence_ratio"] is None
    assert result["convergence_ratio_status"] == "indeterminate_negligible_fine_gap"


def test_source_result_hash_corruption_is_rejected(tmp_path: Path) -> None:
    """Changing the frozen primary result bytes must stop reanalysis."""

    source = tmp_path / "results.json"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source results SHA-256 mismatch"):
        reanalysis.load_source_results(source, "0" * 64)


def test_direct_cli_entrypoint_imports_repository_modules() -> None:
    """Running the script by path must not depend on an externally set PYTHONPATH."""

    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/reanalyze_s074_richardson.py", "--help"],
        cwd=root, text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_immutable_write_replays_identically_and_rejects_conflict(tmp_path: Path) -> None:
    """A rerun may read back identical bytes but must not overwrite a conflict."""

    target = tmp_path / "artifact.json"
    digest = reanalysis.write_immutable(target, b'{"answer":42}\n')
    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    assert reanalysis.write_immutable(target, b'{"answer":42}\n') == digest
    with pytest.raises(RuntimeError, match="conflicting existing output"):
        reanalysis.write_immutable(target, b'{"answer":43}\n')


def test_generated_reanalysis_inventory_and_checksums() -> None:
    """Dropping rows, points, raw misses, or bytes breaks the published carrier."""

    root = Path(__file__).resolve().parents[2]
    directory = root / "artifacts/derived/S-074-Richardson-2026-09-06"
    payload = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "phasemap.s074.richardson-reanalysis.v1"
    assert payload["source_results_sha256"] == reanalysis.EXPECTED_RESULTS_SHA256
    assert len(payload["rows"]) == 80 and len(payload["figure_points"]) == 52
    assert payload["raw_primary_outcomes"]["qualification_pass"] is False
    assert len(payload["raw_primary_outcomes"]["stricter_target_misses"]) == 2
    assert all(row["raw_primary"]["id"] == row["id"] for row in payload["rows"])
    checksums = json.loads((directory / "checksums.json").read_text(encoding="utf-8"))
    for name, digest in checksums["sha256"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
