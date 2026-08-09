"""Contract locks for the scope-bounded F-070 figure set."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "src" / "phasemap" / "analysis" / "generate_final_figures.py"
MANIFEST = ROOT / "artifacts" / "derived" / "F-070-scientific-figure-manifest.md"
FIGURES = {
    "lattice": ROOT / "figures" / "F-070-reset-lattice-and-classifier.svg",
    "transport": ROOT / "figures" / "F-070-physical-transport-and-degeneracies.svg",
    "trajectory": ROOT / "figures" / "F-070-qualitative-trajectory-evidence.svg",
}


def test_f070_figures_are_accessible_and_scope_bounded():
    contents = {name: path.read_text(encoding="utf-8") for name, path in FIGURES.items()}
    for text in contents.values():
        assert "<title>" in text
        assert "<desc>" in text

    assert "12 + 6 + 3 = 21 distinct pairs" in contents["lattice"]
    assert "one=1 and uu_xx+uu_yy=1" in contents["transport"]
    assert "Raw MSD: E|r|^2" in contents["transport"]
    assert "Centered covariance: Cov(r)" in contents["transport"]
    assert "14 / 46 validated" in contents["trajectory"]
    assert "32 / 46 validated" in contents["trajectory"]
    assert "0 contradicted" in contents["trajectory"]
    assert "36 / 36 required signs or equalities" in contents["trajectory"]
    assert "36 / 36 Richardson residual checks" in contents["trajectory"]
    assert "quantitative all-seven trajectory-validation claim" in contents["trajectory"]
    assert "trajectory validation remains unresolved" in contents["trajectory"]


def test_f070_manifest_records_boundary_and_reproducibility():
    text = MANIFEST.read_text(encoding="utf-8")
    assert "14/46 gating items remain unresolved" in text
    assert "do not represent a retry, pooling, threshold change" in text
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "F-070 figures" in result.stdout
