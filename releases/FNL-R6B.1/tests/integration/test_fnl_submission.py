from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from scripts.build_fnl_submission import validate_relative_sources, write_source_zip
from scripts.build_manuscript_pdf import normalize_chromium_pdf
from scripts import build_fnl_submission

FNL = Path(__file__).resolve().parents[2] / "manuscript/journal/fnl"


def test_kinetic_explanation_follows_definitions_and_avoids_matrix_collision():
    root = FNL.parents[2]
    for name in (
        "manuscript/PHASEMAP_MANUSCRIPT.md",
        "manuscript/journal/PHASEMAP_MANUSCRIPT_body.tex",
        "manuscript/journal/fnl/PHASEMAP_FNL_body.tex",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert text.index("C&=") < text.index("The free value") < text.index("Orientation reset reduces")
        assert r"C_{rv}=E[rv^\mathsf T]" in text
        assert r"(r,Q,C_{rv},R)" in text
        assert r"C=E[rv^\mathsf T]" not in text
        assert r"C-A=\frac{\mathrm{Pe}^2M\rho(M\rho-1)}{(1+M)(1+\rho)D_\star}" in text
        assert "This competition concerns only velocity-retaining protocols" in text
        assert "all four velocity-reset protocols share the complete-reset kinetic trace" in text
        assert "mandatory-limit checks" not in text
        assert "three scalars for three bits" not in text
        discussion = text.index("Discussion and conclusion")
        assert text.index("does not exclude a different two-observable family") > discussion


def test_submission_sources_preserve_reference_order_and_short_front_matter():
    main = (FNL / "PHASEMAP_FNL.tex").read_text(encoding="utf-8")
    body = (FNL / "PHASEMAP_FNL_body.tex").read_text(encoding="utf-8")
    keys = re.findall(r"\\bibitem\{([^}]+)\}", main)
    cited = list(dict.fromkeys(
        key.strip() for group in re.findall(r"\\cite\{([^}]+)\}", body)
        for key in group.split(",")
    ))
    assert len(keys) >= 20
    assert keys == cited
    assert "PhysRevModPhys" not in main
    assert r"\keywords{" in main
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main, re.S)
    assert abstract is not None
    assert len(abstract.group(1).split()) < 200
    summary = (FNL / "PHASEMAP_FNL_General_Summary.tex").read_text(encoding="utf-8")
    visible = summary.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    assert len(visible.split()) <= 200
    assert re.findall(r"\\section\*\{([^}]+)\}", visible) == [
        "Introduction", "Main Results", "Broader Implications",
    ]
    assert "$" not in visible and r"\[" not in visible and r"\(" not in visible


def test_fnl_sources_preserve_unresolved_evidence_and_supplement_labels():
    body = (FNL / "PHASEMAP_FNL_body.tex").read_text(encoding="utf-8")
    supplement = (FNL / "PHASEMAP_FNL_Supplement_body.tex").read_text(encoding="utf-8")
    wrapper = (FNL / "PHASEMAP_FNL_Supplement.tex").read_text(encoding="utf-8")
    # The authorized editorial revision moves historical disclosure to S0.1.
    assert "historical S-071 and S-073" in supplement
    assert "Neither study supports a quantitative trajectory-validation claim" in supplement
    assert "S-071" not in body and "S-073" not in body
    assert "categorical" in body
    assert r"\setcounter{section}{-1}" in wrapper
    for phrase in ("S-071 validated 14 of 46", "left 32 unresolved",
                   "S-073 validated 32 of 46", "left 14 unresolved"):
        assert phrase in " ".join(supplement.split())
    for phrase in ("not disagreement", "minority of insufficiently precise",
                   "failure modes of any smaller record"):
        assert phrase not in body + supplement


def test_chromium_metadata_normalization_is_length_preserving_and_idempotent(tmp_path: Path):
    def valid_pdf(version: bytes) -> bytes:
        object_bytes = b"1 0 obj<</CreationDate(D:20260905123456+00'00')/Creator(Chrome " + version + b")/Producer(Skia/PDF m151; Microsoft Edge/99.12)>>endobj\n"
        header = b"%PDF-1.4\n"
        prefix = header + object_bytes
        xref_offset = len(prefix)
        return (prefix + b"xref\n0 2\n0000000000 65535 f \n" + f"{len(header):010d}".encode() + b" 00000 n \ntrailer<</Size 2>>\nstartxref\n" + str(xref_offset).encode() + b"\n%%EOF\n")

    pdf = tmp_path / "figure.pdf"
    pdf.write_bytes(valid_pdf(b"151.0.7339.1"))
    original_length = pdf.stat().st_size
    normalize_chromium_pdf(pdf)
    first = pdf.read_bytes()
    normalize_chromium_pdf(pdf)
    assert pdf.read_bytes() == first
    assert pdf.stat().st_size == original_length
    assert b"Chrome 000.0.0000.0" in first
    assert b"Microsoft Edge/00.00" in first
    assert b"Skia/PDF m000" in first
    assert b"xref" in first and b"startxref" in first
    assert int(first.split(b"startxref\n", 1)[1].splitlines()[0]) == first.index(b"xref\n")
    assert int(first.split(b"xref\n0 2\n", 1)[1].splitlines()[1][:10]) == first.index(b"1 0 obj")

    same_length_version = tmp_path / "same-length-version.pdf"
    same_length_version.write_bytes(valid_pdf(b"152.0.7339.1"))
    normalize_chromium_pdf(same_length_version)
    assert same_length_version.read_bytes() == first


def test_source_zip_is_deterministic_and_preserves_extractable_repo_layout(tmp_path: Path):
    root = tmp_path / "root"
    fnl = root / "manuscript" / "journal" / "fnl"
    figure = root / "figures" / "F-080-panel.pdf"
    fnl.mkdir(parents=True)
    figure.parent.mkdir()
    source = fnl / "PHASEMAP_FNL.tex"
    text = "\\documentclass{ws-fnl}\n\\includegraphics{../../../figures/F-080-panel}\n\\begin{document}x\\end{document}\n"
    source.write_text(text, encoding="utf-8", newline="\r\n")
    figure.write_bytes(b"%PDF-1.4\n%%EOF\n")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    write_source_zip(first, [source], [figure], root=root)
    source.write_text(text, encoding="utf-8", newline="\n")
    write_source_zip(second, [source], [figure], root=root)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == {"manuscript/journal/fnl/PHASEMAP_FNL.tex", "figures/F-080-panel.pdf"}


def test_fnl_sources_reject_absolute_paths(tmp_path: Path):
    source = tmp_path / "bad.tex"
    source.write_text(r"\input{C:\\Users\\unsafe.tex}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="absolute path"):
        validate_relative_sources([source])


def test_source_figures_include_only_referenced_publication_assets(tmp_path: Path, monkeypatch):
    root = tmp_path / "publication"
    fnl = root / "manuscript" / "journal" / "fnl"
    figures = root / "figures"
    fnl.mkdir(parents=True)
    figures.mkdir()
    body = fnl / "body.tex"
    body.write_text(r"\includegraphics{../../../figures/F-080-transport}", encoding="utf-8")
    used = figures / "F-080-transport.pdf"
    unused = figures / "F-080-historical-infographic.pdf"
    for path in (used, unused):
        path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setattr(build_fnl_submission, "ROOT", root)
    assert build_fnl_submission.figure_pdfs([body]) == [used.resolve()]


def test_fnl_sources_reject_missing_or_outside_local_dependencies(tmp_path: Path):
    source = tmp_path / "bad.tex"
    source.write_text(r"\input{missing}\includegraphics{/outside/figure}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="absolute path"):
        validate_relative_sources([source])
