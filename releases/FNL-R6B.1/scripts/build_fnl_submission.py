#!/usr/bin/env python3
"""Build the four-file FNL submission set and deterministic source archive."""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

try:  # Support both ``python scripts/...`` and package import in tests.
    from scripts.build_manuscript_pdf import ROOT, compile_document, qa_pdf
except ModuleNotFoundError:  # pragma: no cover - exercised by CLI invocation
    from build_manuscript_pdf import ROOT, compile_document, qa_pdf


FNL_DIR = ROOT / "manuscript" / "journal" / "fnl"
DOCUMENTS = (
    ("PHASEMAP_FNL.tex", 10),
    ("PHASEMAP_FNL_Supplement.tex", None),
    ("PHASEMAP_FNL_Cover_Letter.tex", None),
    ("PHASEMAP_FNL_General_Summary.tex", 1),
)
FIGURE_PATTERN = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
INPUT_PATTERN = re.compile(r"\\(?:input|include)\{([^}]+)\}")
WINDOWS_ABSOLUTE = re.compile(r"(?:\b[A-Za-z]:[\\/]|(?<![A-Za-z])file:)", re.I)


def source_files() -> list[Path]:
    required = [FNL_DIR / name for name, _ in DOCUMENTS]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("FNL source missing: " + ", ".join(missing))
    return sorted({*required, *FNL_DIR.rglob("*.tex"), *FNL_DIR.rglob("*.cls"), *FNL_DIR.rglob("*.bst"), *FNL_DIR.glob("*.md")})


def validate_relative_sources(paths: list[Path]) -> None:
    for path in paths:
        if path.suffix != ".tex":
            continue
        text = path.read_text(encoding="utf-8")
        if WINDOWS_ABSOLUTE.search(text) or re.search(r"(?:^|\{)/", text):
            raise RuntimeError(f"FNL source contains an absolute path: {path}")
        for value in INPUT_PATTERN.findall(text):
            candidate = (path.parent / value).with_suffix(".tex").resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.is_file():
                raise RuntimeError(f"FNL source input is missing or outside the submission root: {value}")
        for value in FIGURE_PATTERN.findall(text):
            candidate = (path.parent / value).with_suffix(".pdf").resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.is_file():
                raise RuntimeError(f"FNL source figure is missing or outside the submission root: {value}")


def figure_pdfs(paths: list[Path]) -> list[Path]:
    requested = set()
    for path in paths:
        if path.suffix != ".tex":
            continue
        for value in FIGURE_PATTERN.findall(path.read_text(encoding="utf-8")):
            candidate = (path.parent / value).with_suffix(".pdf").resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.is_file():
                raise RuntimeError(f"FNL source figure is missing or outside the submission root: {value}")
            requested.add(candidate)
    return sorted(requested)


def write_source_zip(output: Path, paths: list[Path], figures: list[Path], *, root: Path = ROOT) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    members = [*paths, *figures]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(members, key=lambda item: item.relative_to(root).as_posix()):
            name = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            data = path.read_bytes()
            if path.suffix in {".tex", ".cls", ".bst", ".md"}:
                data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def build(output_dir: Path, qa_dir: Path, *, sources_only: bool) -> list[tuple[Path, int, str]]:
    paths = source_files()
    validate_relative_sources(paths)
    figures = figure_pdfs(paths)
    archive = output_dir / "PHASEMAP_FNL_Source.zip"
    digest = write_source_zip(archive, paths, figures)
    print(f"source_zip={archive}")
    print(f"source_zip_sha256={digest}")
    if sources_only:
        return []
    results = []
    for source_name, maximum_pages in DOCUMENTS:
        source = FNL_DIR / source_name
        output = output_dir / source.with_suffix(".pdf").name
        compile_document(source, output)
        pages, pdf_digest = qa_pdf(output, qa_dir / source.stem)
        if maximum_pages is not None and pages > maximum_pages:
            raise RuntimeError(f"FNL page limit exceeded for {source_name}: {pages}>{maximum_pages}")
        results.append((output, pages, pdf_digest))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "FNL_SUBMISSION")
    parser.add_argument("--qa-dir", type=Path, default=ROOT / "dist" / "FNL_QA")
    parser.add_argument("--sources-only", action="store_true", help="write only the reproducible source ZIP")
    parser.add_argument("--skip-figures", action="store_true", help="accepted for automation; legacy figure PDFs are never rewritten")
    args = parser.parse_args()
    results = build(args.output_dir.resolve(), args.qa_dir.resolve(), sources_only=args.sources_only)
    for output, pages, digest in results:
        print(f"pdf={output}")
        print(f"pdf_sha256={digest}")
        print(f"rendered_pages={pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
