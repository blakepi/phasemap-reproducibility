"""Synthetic-only tests for deterministic S-074 publication rendering."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import render_s074_publication as renderer


def _payload() -> dict[str, object]:
    """Return a deliberately non-scientific 80-row results-schema fixture."""
    rows: list[dict[str, object]] = []
    position = {"P", "PV", "PTheta", "PVTheta"}

    def add(case_id: str, group: str, protocol: str, mass: float, rho: float, observables: list[str]) -> None:
        for observable in observables:
            index = len(rows)
            rows.append({
                "id": f"synthetic-{index:02d}", "case_id": case_id, "group": group,
                "protocol": protocol, "M": mass, "Pe": 1.2, "rho": rho,
                "observable": observable,
                "observable_class": "stationary_variance" if observable == "spatial" and protocol in position else ("d_eff" if observable == "spatial" else "direct"),
                "reference": 10.0 + index, "estimate": 10.25 + index,
                "se": 0.01 + index / 10000, "n": 4096, "se_fraction": 0.001,
                "precision_pass": True, "discretization_pass": True,
                "qualification_pass": index != 0,
                "classification": ("validated", "unresolved", "contradicted")[index % 3],
                "b_disc": 0.02, "b_window": 0.03, "transient_residual": 0.04,
                "b_total": 0.09,
            })

    protocols = ("P", "V", "Theta", "PV", "PTheta", "VTheta", "PVTheta")
    for protocol in protocols:
        names = ["u_xx", "speed", "spatial"] + (["v_x"] if protocol not in position else [])
        if protocol in {"PV", "PVTheta"}:
            names.extend(("raw_msd", "r_dot_v"))
        add(f"core-{protocol}", "core", protocol, 0.8, 1.0, names)
    for rho in (0.15, 0.5, 1.5, 6.0):
        for protocol in protocols:
            add(f"figure-{rho:g}-{protocol}", "figure", protocol, 2.0, rho, ["spatial"] + (["v_x"] if protocol not in position else []))
    for mass in (0.15, 0.35, 0.55):
        for protocol in ("V", "Theta"):
            add(f"tuned-{mass:g}-{protocol}", "tuned", protocol, mass, 0.5, ["spatial", "v_x"])

    points = []
    for row in rows:
        if row["group"] == "figure":
            series, x = (f"{'variance' if row['protocol'] in position else 'diffusion'}_{row['protocol']}", row["rho"]) if row["observable"] == "spatial" else (f"drift_{row['protocol']}", row["rho"])
        elif row["group"] == "tuned":
            series, x = (f"tuned_diffusion_{row['protocol']}", row["M"]) if row["observable"] == "spatial" else ("tuned_drift_V" if row["protocol"] == "V" else "tuned_theta_drift", row["M"])
        else:
            continue
        points.append({
            "series": series, "x": x, "estimate": row["estimate"], "se": row["se"],
            "n": row["n"], "case_id": row["case_id"],
            "source_manifest_sha256": "a" * 64, "plan_semantic_sha256": "b" * 64,
            "reference": row["reference"], "classification": row["classification"],
            "precision_pass": True, "discretization_pass": True,
            "qualification_pass": row["qualification_pass"], "b_disc": row["b_disc"],
            "b_window": row["b_window"], "transient_residual": row["transient_residual"],
            "b_total": row["b_total"],
        })
    return {
        "schema": "phasemap.s074.results.v1", "rows": rows,
        "table_rows": copy.deepcopy(rows), "figure_points": points,
        "source_manifest_sha256": "a" * 64, "plan_semantic_sha256": "b" * 64,
    }


def _write(path: Path, payload: dict[str, object]) -> bytes:
    raw = json.dumps(payload, sort_keys=True, allow_nan=True).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _assert_table_rows_equal_except_spatial_label(
    before: str, after: str, *, prefix: str,
) -> None:
    """Permit only the authorized journal label change within table rows."""

    before_rows = [line for line in before.splitlines() if line.startswith(prefix)]
    after_rows = [line for line in after.splitlines() if line.startswith(prefix)]
    assert len(after_rows) == len(before_rows)
    for archived, journal in zip(before_rows, after_rows, strict=True):
        if prefix == "$":
            archived_cells = archived.split(" & ")
            journal_cells = journal.split(" & ")
            archived_label, journal_label = archived_cells[1], journal_cells[1]
            expected_label = r"$s_r^2$" if archived_label == r"$\mathcal V$" else archived_label
        else:
            archived_cells = [cell.strip() for cell in archived.strip("|").split("|")]
            journal_cells = [cell.strip() for cell in journal.strip("|").split("|")]
            archived_label, journal_label = archived_cells[1], journal_cells[1]
            expected_label = "s_r^2" if archived_label == "Tr Cov(r)" else archived_label
        assert journal_label == expected_label
        assert journal_cells[:1] + journal_cells[2:] == archived_cells[:1] + archived_cells[2:]


def _richardson_payload() -> dict[str, object]:
    payload = _payload()
    payload.update({
        "schema": "phasemap.s074.richardson-reanalysis.v1",
        "estimator_identity": "paired_first_order_richardson_post_result",
        "analysis_timing": "post_result_after_observing_finest_step_bias",
        "source_results_sha256": "c" * 64,
        "raw_primary_outcomes": {
            "precision_pass": False, "qualification_pass": False,
            "stricter_target_misses": [
                "figure-rho0p5-PV:spatial",
                "figure-rho0p5-PTheta:spatial",
            ],
        },
    })
    for index, row in enumerate(payload["rows"]):
        row.update({
            "post_result": True, "estimator_identity": payload["estimator_identity"],
            "precision_1pct_pass": True, "stronger_tau_pass": True,
            "b_r": row["b_disc"], "b_late": max(row["b_window"], row["transient_residual"]),
            "raw_primary": {
                "id": row["id"], "precision_pass": index >= 2,
                "qualification_pass": index >= 2,
            },
        })
    for point in payload["figure_points"]:
        point.update({
            "post_result": True, "estimator_identity": payload["estimator_identity"],
            "precision_1pct_pass": True, "stronger_tau_pass": True,
            "b_r": point["b_disc"], "b_late": max(point["b_window"], point["transient_residual"]),
        })
    payload["table_rows"] = copy.deepcopy(payload["rows"])
    return payload


def test_renderer_preserves_all_synthetic_rows_and_points(tmp_path: Path) -> None:
    # Filtering rows or rewriting values breaks publication evidence identity.
    payload = _payload()
    results = tmp_path / "results.json"
    raw = _write(results, payload)
    rendered = renderer.render(results, tmp_path / "derived")
    points = json.loads(rendered["figure_points"].read_text(encoding="utf-8"))
    markdown = rendered["markdown"].read_text(encoding="utf-8")
    latex = rendered["latex"].read_text(encoding="utf-8")
    assert points["results_sha256"] == hashlib.sha256(raw).hexdigest()
    assert points["points"] == payload["figure_points"]
    table_lines = [line for line in markdown.splitlines() if line.startswith("|")]
    assert sum(not line.startswith("|---") and "Protocol" not in line and "**" not in line for line in table_lines) == 80
    assert markdown.count("**") == 16
    assert "nonzero-reference scale" in markdown.lower()
    assert "V*" in markdown
    assert "\\begin{longtable}{llrrrrc}" in latex and "\\setlength{\\tabcolsep}{3pt}" in latex
    assert "$\\pm$" in latex and "SE (\\%)" in latex
    assert "$P\\Theta$" in latex and "$\\Theta$" in latex
    assert "E[|v|^2]" in latex and "E[r\\cdot v]" in latex and "E[|r|^2]" in latex
    assert "\\mathsf{Theta}" not in latex
    assert renderer._tex_number(0.0000021, 2) == r"2.1\times10^{-6}"


@pytest.mark.parametrize("mutation, message", [
    (lambda payload: payload["rows"].__setitem__(1, {**payload["rows"][1], "id": "synthetic-00"}), "unique"),
    (lambda payload: payload.__setitem__("figure_points", payload["figure_points"][:-1]), "52"),
    (lambda payload: payload["table_rows"][0].__setitem__("classification", "contradicted"), "table_rows"),
    (lambda payload: payload["figure_points"][0].__setitem__("series", "wrong_series"), "inventory"),
    (lambda payload: payload["figure_points"][0].__setitem__("x", 99.0), "inventory"),
    (lambda payload: payload["figure_points"].__setitem__(1, copy.deepcopy(payload["figure_points"][0])), "inventory"),
    (lambda payload: payload["figure_points"][0].__setitem__("se", -0.1), "nonnegative"),
])
def test_renderer_rejects_synthetic_inventory_and_relabel_tampering(tmp_path: Path, mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)
    results = tmp_path / "results.json"
    _write(results, payload)
    with pytest.raises(ValueError, match=message):
        renderer.render(results, tmp_path / "derived")


def test_renderer_rejects_nonfinite_synthetic_json_and_cli_writes_outputs(tmp_path: Path) -> None:
    payload = _payload()
    payload["rows"][0]["estimate"] = float("nan")
    results = tmp_path / "bad.json"
    _write(results, payload)
    with pytest.raises(ValueError, match="non-finite"):
        renderer.render(results, tmp_path / "derived")
    payload = _payload()
    results = tmp_path / "results.json"
    _write(results, payload)
    completed = subprocess.run(
        [sys.executable, "scripts/render_s074_publication.py", "--results", str(results), "--output-dir", str(tmp_path / "cli")],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, check=True,
    )
    assert "S-074-figure-points.json" in completed.stdout
    assert (tmp_path / "cli/S-074-precision-table.tex").is_file()


def test_renderer_labels_post_result_richardson_without_erasing_raw_misses(tmp_path: Path) -> None:
    """Treating the new schema as raw or hiding the two historical misses breaks disclosure."""

    results = tmp_path / "richardson.json"
    _write(results, _richardson_payload())
    rendered = renderer.render(results, tmp_path / "derived")
    markdown = rendered["markdown"].read_text(encoding="utf-8")
    latex = rendered["latex"].read_text(encoding="utf-8")
    points = json.loads(rendered["figure_points"].read_text(encoding="utf-8"))
    disclosure = "Both raw and extrapolated analyses miss the stricter design-SE target for the two spatial-variance rows identified in Sec.~S0.2."
    assert "post-result Richardson" in markdown
    assert disclosure in markdown
    assert "Richardson estimate ± paired SE" in markdown
    assert "V*" not in markdown
    assert "post-result Richardson" in latex
    assert disclosure in latex
    assert "asterisk" not in markdown.lower()
    assert "asterisk" not in latex.lower()
    assert "asterisks. with" not in latex.lower()
    assert points["estimator_identity"] == "paired_first_order_richardson_post_result"
    assert rendered["markdown"].name == "S-074-Richardson-precision-table.md"


def test_renderer_rejects_wrong_raw_primary_miss_identities(tmp_path: Path) -> None:
    """Two arbitrary misses must not substitute for the preserved raw-primary rows."""

    payload = _richardson_payload()
    payload["raw_primary_outcomes"]["stricter_target_misses"][0] = "wrong:spatial"
    results = tmp_path / "richardson.json"
    _write(results, payload)
    with pytest.raises(ValueError, match="two raw-primary misses"):
        renderer.render(results, tmp_path / "derived")


def test_journal_cli_preserves_numerical_rows_provenance_and_archival_rendering(tmp_path: Path) -> None:
    """Editorial rendering must not change inputs, points, row order or archive bytes."""

    payload = _richardson_payload()
    results = tmp_path / "richardson.json"
    raw = _write(results, payload)
    archived = renderer.render(results, tmp_path / "archive")
    archived_bytes = {key: path.read_bytes() for key, path in archived.items()}
    completed = subprocess.run(
        [sys.executable, "scripts/render_s074_publication.py", "--results", str(results),
         "--output-dir", str(tmp_path / "journal"), "--presentation", "journal"],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    rendered = {key: Path(value) for key, value in json.loads(completed.stdout).items()}
    assert results.read_bytes() == raw
    assert rendered["figure_points"].read_bytes() == archived_bytes["figure_points"]
    assert json.loads(rendered["figure_points"].read_text())["points"] == payload["figure_points"]
    for key, prefix in (("latex", "$"), ("markdown", "|")):
        before = archived_bytes[key].decode("utf-8")
        after = rendered[key].read_text(encoding="utf-8")
        assert after != before
        _assert_table_rows_equal_except_spatial_label(before, after, prefix=prefix)
    replayed = renderer.render(results, tmp_path / "archive")
    assert {key: path.read_bytes() for key, path in replayed.items()} == archived_bytes
    # A parameter heading must stay with its first observation after pagination.
    journal_headings = [
        line for line in rendered["latex"].read_text(encoding="utf-8").splitlines()
        if line.startswith(r"\multicolumn")
    ]
    assert len(journal_headings) == 8
    assert all(line.endswith(r"\\*") for line in journal_headings)
    archive_headings = [
        line for line in archived_bytes["latex"].decode("utf-8").splitlines()
        if line.startswith(r"\multicolumn")
    ]
    assert all(line.endswith(r"\\") for line in archive_headings)


@pytest.mark.parametrize("presentation,payload_factory,message", [
    ("unknown", _richardson_payload, "presentation"),
    ("journal", _payload, "Richardson"),
])
def test_journal_renderer_rejects_invalid_modes_before_writing(
    tmp_path: Path, presentation: str, payload_factory, message: str,
) -> None:
    """Raw primary estimates cannot accidentally acquire Richardson method labels."""

    results = tmp_path / "results.json"
    _write(results, payload_factory())
    destination = tmp_path / "derived"
    with pytest.raises(ValueError, match=message):
        renderer.render(results, destination, presentation=presentation)
    assert not destination.exists()


def test_published_table_copies_preserve_all_rows_and_archived_outcomes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    directory = root / "artifacts/derived/S-074-Richardson-2026-09-06"
    archived = (directory / "S-074-Richardson-precision-table.tex").read_text(encoding="utf-8")
    rendered = renderer.render(directory / "results.json", tmp_path, presentation="journal")
    canonical = rendered["latex"].read_text(encoding="utf-8")
    for relative in (
        "manuscript/journal/PHASEMAP_S074_Table.tex",
        "manuscript/journal/fnl/PHASEMAP_FNL_S074_Table.tex",
    ):
        assert (root / relative).read_text(encoding="utf-8") == canonical
    _assert_table_rows_equal_except_spatial_label(archived, canonical, prefix="$")
    assert "V* " not in canonical
    raw_table = (root / "artifacts/derived/S-074-precision-table.tex").read_text(encoding="utf-8")
    assert raw_table.count("V* ") == 2
    markdown = (directory / "S-074-Richardson-precision-table.md").read_text(encoding="utf-8")
    supplement = (root / "manuscript/PHASEMAP_TECHNICAL_SUPPLEMENT.md").read_text(encoding="utf-8")
    for row in markdown.splitlines():
        if row.startswith("|"):
            assert row in supplement
