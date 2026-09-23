from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pytest

import scripts.build_portable_publication_archive as archive_builder
from scripts.build_portable_publication_archive import FORBIDDEN_PREFIXES, markdown_link_errors
from scripts.build_manuscript_pdf import normalize_pdf_trailer_id

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts" / "build_portable_publication_archive.py"
PDF_BUILDER = ROOT / "scripts" / "build_manuscript_pdf.py"


def build(archive: Path) -> None:
    result = subprocess.run([sys.executable, str(BUILDER), "--output", str(archive)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def read_bundle(archive: Path) -> tuple[set[str], dict[str, bytes], dict[str, object]]:
    with zipfile.ZipFile(archive) as bundle:
        payload = {name: bundle.read(name) for name in bundle.namelist() if name != "ARCHIVE_MANIFEST.json"}
        return set(bundle.namelist()), payload, json.loads(bundle.read("ARCHIVE_MANIFEST.json"))


def test_portable_archive_is_allowlisted_link_clean_and_reproducible(tmp_path: Path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    build(first); build(second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    names, payload, manifest = read_bundle(first)
    for entry in manifest["entry_points"]:
        assert entry in names or any(name.startswith(entry + "/") for name in names)
    assert manifest["portable_test_suite"]["collected_test_count"] > 0
    assert "CITATION.cff" in names
    assert "LICENSE" in names
    assert "CHANGELOG.md" in names
    assert "artifacts/derived/T-080-exact-observability-theorem.md" in names
    assert "artifacts/derived/F-080-observability-figure-manifest.md" in names
    assert "manuscript/journal/PHASEMAP_MANUSCRIPT.tex" in names
    assert "manuscript/journal/PHASEMAP_TECHNICAL_SUPPLEMENT.tex" in names
    assert "figures/F-080-three-coordinate-decoder.pdf" in names
    for public_source in (
        "manuscript/journal/fnl/PHASEMAP_FNL.tex",
        "manuscript/journal/fnl/PHASEMAP_FNL_Supplement.tex",
        "manuscript/journal/fnl/PHASEMAP_FNL_General_Summary.tex",
    ):
        assert public_source in names
    for private_submission_path in (
        "manuscript/journal/fnl/PHASEMAP_FNL_Cover_Letter.tex",
        "docs/release/SUBMISSION_METADATA_DRAFT.md",
        "docs/release/FNL_SUBMISSION_METADATA.md",
    ):
        assert private_submission_path not in names
    assert b"../figures/F-080-transport-localization.svg" in payload[
        "manuscript/PHASEMAP_MANUSCRIPT.md"
    ]
    assert b"../artifacts/derived/T-080-exact-observability-theorem.md" in payload[
        "manuscript/CLAIM_EVIDENCE_MAP.md"
    ]
    assert markdown_link_errors(payload) == []
    assert not any(name.startswith(FORBIDDEN_PREFIXES) or name == "AGENTS.md" for name in names)
    assert "artifacts/derived/P-080-portable-publication-archive.md" not in names


def test_archive_bytes_are_independent_of_checkout_line_endings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    lf_root, crlf_root = tmp_path / "lf", tmp_path / "crlf"
    binary = b"%PDF-1.4\r\n\x00binary\rpayload\n"
    members = ("README.md", "src/example.py", "figure.pdf")
    for root, newline in ((lf_root, b"\n"), (crlf_root, b"\r\n")):
        (root / "src").mkdir(parents=True)
        (root / "README.md").write_bytes(newline.join((b"heading", b"body", b"")))
        (root / "src" / "example.py").write_bytes(newline.join((b"x = 1", b"")))
        (root / "figure.pdf").write_bytes(binary)

    monkeypatch.setattr(
        archive_builder,
        "allowlisted_paths",
        lambda root: [root / member for member in members],
    )
    monkeypatch.setattr(archive_builder, "REQUIRED_ENTRY_POINTS", ())
    first, second = tmp_path / "lf.zip", tmp_path / "crlf.zip"
    archive_builder.write_zip(lf_root, first, test_count=1)
    archive_builder.write_zip(crlf_root, second, test_count=1)

    assert first.read_bytes() == second.read_bytes()
    _, payload, _ = read_bundle(first)
    assert payload["README.md"] == b"heading\nbody\n"
    assert payload["src/example.py"] == b"x = 1\n"
    assert payload["figure.pdf"] == binary


def test_portable_archive_preserves_every_frozen_s074_source():
    from experiments.run_s074_precision import SOURCE_PATHS, source_manifest

    payload = archive_builder.archive_payload(ROOT)
    identities = source_manifest()
    for name in SOURCE_PATHS:
        assert name in payload, f"missing frozen S-074 source: {name}"
        assert hashlib.sha256(payload[name]).hexdigest() == identities[name], name
    assert not any(name.startswith("artifacts/raw/") for name in payload)


def test_extracted_archive_preserves_figure_provenance_and_reproduces_figures(
    tmp_path: Path,
):
    archive = tmp_path / "portable.zip"
    build(archive)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)

    for name in (
        "artifacts/derived/B-040-central-claim.md",
        "artifacts/derived/Q-030-target-lock.md",
        "artifacts/derived/T-070-constrained-moment-frame.md",
        "artifacts/derived/T-080-exact-observability-theorem.md",
        "artifacts/derived/S-071-trajectory-validation.md",
        "artifacts/derived/S-073-trajectory-replacement-validation.md",
        "artifacts/derived/F-050-figure-manifest.md",
    ):
        assert (extracted / name).read_bytes() == archive_builder.canonical_payload_bytes(
            name, (ROOT / name).read_bytes()
        ), name
    for private_submission_path in archive_builder.PUBLIC_EXCLUDED_PATHS:
        assert not (extracted / private_submission_path).exists()

    result = subprocess.run(
        [sys.executable, "src/phasemap/analysis/generate_final_figures.py", "--check"],
        cwd=extracted,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_archive_rejects_unsafe_text_and_unknown_payload_types():
    with pytest.raises(RuntimeError, match="not valid UTF-8"):
        archive_builder.canonical_payload_bytes("README.md", b"\xff")
    with pytest.raises(RuntimeError, match="unsupported publication payload type"):
        archive_builder.canonical_payload_bytes("payload.bin", b"opaque")


def test_portable_reanalysis_entrypoints_are_included_without_raw_mutation():
    expected = {
        'docs/scientific-contract/S-074_RICHARDSON_REANALYSIS.md',
        'scripts/reanalyze_s074_richardson.py',
        'tests/integration/test_s074_richardson.py',
        'artifacts/derived/S-074-Richardson-2026-09-06/*',
    }
    assert expected <= set(archive_builder.REQUIRED_GLOBS)
    assert 'tests/integration/test_s074_richardson.py' in archive_builder.PORTABLE_TEST_ARGS
    assert archive_builder.canonical_payload_bytes('diagnostics.csv', b'x,y\r\n1,2\r\n') == b'x,y\n1,2\n'


def test_archive_rejects_untracked_allowlisted_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    tracked = tmp_path / "README.md"
    untracked = tmp_path / "src" / "injected.py"
    untracked.parent.mkdir()
    tracked.write_text("tracked\n", encoding="utf-8")
    untracked.write_text("injected = True\n", encoding="utf-8")
    monkeypatch.setattr(
        archive_builder,
        "allowlisted_paths",
        lambda root: [tracked, untracked],
    )
    monkeypatch.setattr(
        archive_builder,
        "tracked_paths_if_repository",
        lambda root: {"README.md"},
    )

    with pytest.raises(RuntimeError, match=r"untracked.*src/injected\.py"):
        archive_builder.archive_payload(tmp_path)


def test_pdf_builder_requires_vector_figures_pdflatex_and_explicit_qa():
    text = PDF_BUILDER.read_text(encoding="utf-8")
    for required in (
        "latexmk",
        "-pdf",
        "pdfimages",
        "pdfinfo",
        "pdffonts",
        "pdftotext",
        "pdftoppm",
        "Type 3",
        "-png",
        "SOURCE_DATE_EPOCH",
        "normalize_pdf_trailer_id",
        "PHASEMAP_Main_Manuscript.pdf",
        "PHASEMAP_Supplemental_Material.pdf",
    ):
        assert required in text


def test_journal_sources_declare_required_pdf_metadata():
    for name in ("PHASEMAP_MANUSCRIPT.tex", "PHASEMAP_TECHNICAL_SUPPLEMENT.tex"):
        text = (ROOT / "manuscript" / "journal" / name).read_text(encoding="utf-8")
        for field in ("pdftitle=", "pdfauthor=", "pdfsubject=", "pdfkeywords="):
            assert field in text


def test_pdf_trailer_id_normalization_is_content_derived_and_stable(tmp_path: Path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    template = b"%%PDF-1.5\n1 0 obj<<>>endobj\n/ID [<%s> <%s>]\n%%%%EOF\n"
    first.write_bytes(template % (b"A" * 32, b"A" * 32))
    second.write_bytes(template % (b"B" * 32, b"B" * 32))
    normalize_pdf_trailer_id(first)
    normalize_pdf_trailer_id(second)
    assert first.read_bytes() == second.read_bytes()
    assert b"A" * 32 not in first.read_bytes()


def test_candidate_citation_metadata_has_required_cff_fields_and_valid_links():
    # Exercise the exported citation, not merely a source-file spelling.
    text = archive_builder.archive_payload(ROOT)["CITATION.cff"].decode("utf-8")
    for field in ("cff-version: 1.2.0", "title:", "version: 3.2.0rc2", "authors:", "repository-code:"):
        assert field in text
    assert 'doi: "10.5281/zenodo.22924890"' in text
    assert "Unreleased successor candidate" not in text
    assert "zenodo.22581850" not in text
    assert 'repository-code: "https://github.com/blakepi/phasemap-reproducibility"' in text
    assert 'https://github.com/blakepi/PHASEMAP' not in text
    for value in re.findall(r'"(https?://[^"]+)"', text):
        parsed = urlparse(value)
        assert parsed.scheme == "https" and parsed.netloc
