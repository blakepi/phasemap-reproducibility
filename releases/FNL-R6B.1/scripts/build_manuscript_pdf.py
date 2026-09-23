#!/usr/bin/env python3
"""Build and quality-check the PHASEMAP journal PDFs and vector figures."""
from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOURNAL_DIR = ROOT / "manuscript" / "journal"
FIGURE_STEMS = (
    "F-080-three-coordinate-decoder",
    "F-080-strict-subsignature-classes",
    "F-080-transport-localization",
)
DOCUMENTS = (
    ("PHASEMAP_MANUSCRIPT.tex", "PHASEMAP_Main_Manuscript.pdf", "PHASEMAP_Main_Manuscript_pages"),
    (
        "PHASEMAP_TECHNICAL_SUPPLEMENT.tex",
        "PHASEMAP_Supplemental_Material.pdf",
        "PHASEMAP_Supplemental_Material_pages",
    ),
)
MIKTEX_BIN = Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64"
FIXED_PDF_DATE = b"D:19800101000000+00'00'"
PDF_DATE = re.compile(rb"D:\d{14}[+-]\d{2}'\d{2}'")
PDF_TRAILER_ID = re.compile(
    rb"(/ID\s*\[\s*<)[0-9A-Fa-f]{32}(>\s*<)[0-9A-Fa-f]{32}(>\s*\])"
)
CHROMIUM_VERSION = re.compile(
    rb"(?P<prefix>(?:Chrome|Chromium|Microsoft Edge)(?:/| )?)(?P<version>\d+(?:\.\d+)+)"
)
CHROMIUM_SKIA_VERSION = re.compile(rb"(?P<prefix>Skia/PDF m)(?P<version>\d+)")


def require(command: str) -> str:
    found = shutil.which(command)
    if not found:
        raise RuntimeError(f"required executable not found on PATH: {command}")
    return found


def preferred_executable(command: str) -> str:
    direct = MIKTEX_BIN / f"{command}.exe"
    return str(direct) if direct.is_file() else require(command)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(
            "command failed: "
            + " ".join(command)
            + "\n"
            + result.stdout
            + result.stderr
        )
    return result.stdout


def chromium() -> str:
    candidates = (
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    raise RuntimeError("vector SVG conversion requires Google Chrome or Microsoft Edge")


def svg_dimensions(source: Path) -> tuple[float, float]:
    root = ET.parse(source).getroot()
    width = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(?:px)?", root.attrib.get("width", ""))
    height = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(?:px)?", root.attrib.get("height", ""))
    if not width or not height:
        raise RuntimeError(f"SVG requires explicit pixel width and height: {source}")
    return float(width.group(1)), float(height.group(1))


def normalize_chromium_pdf(path: Path) -> None:
    data = path.read_bytes()
    normalized, count = PDF_DATE.subn(FIXED_PDF_DATE, data)
    if count < 1:
        raise RuntimeError(f"Chromium PDF did not contain a normalizable date: {path}")
    # Chromium embeds its browser version in /Creator or /Producer. Replace
    # each digit in place, preserving every object offset and xref entry even
    # when a browser release changes the textual version length.
    normalized = CHROMIUM_VERSION.sub(
        lambda match: match.group("prefix") + re.sub(rb"\d", b"0", match.group("version")),
        normalized,
    )
    normalized = CHROMIUM_SKIA_VERSION.sub(
        lambda match: match.group("prefix") + re.sub(rb"\d", b"0", match.group("version")),
        normalized,
    )
    if len(normalized) != len(data):
        raise RuntimeError(f"Chromium normalization changed PDF length: {path}")
    path.write_bytes(normalized)


def normalize_pdf_trailer_id(path: Path) -> None:
    """Replace pdfTeX's volatile trailer ID with a content-derived stable ID."""

    data = path.read_bytes()
    zeroed, count = PDF_TRAILER_ID.subn(
        rb"\g<1>00000000000000000000000000000000"
        rb"\g<2>00000000000000000000000000000000\g<3>",
        data,
    )
    if count != 1:
        raise RuntimeError(f"expected exactly one PDF trailer ID in {path}, found {count}")
    identifier = hashlib.sha256(zeroed).hexdigest()[:32].upper().encode("ascii")
    normalized, count = PDF_TRAILER_ID.subn(
        lambda match: match.group(1)
        + identifier
        + match.group(2)
        + identifier
        + match.group(3),
        zeroed,
    )
    if count != 1 or len(normalized) != len(data):
        raise RuntimeError(f"failed to normalize PDF trailer ID in {path}")
    path.write_bytes(normalized)


def vector_pdf_qa(pdf: Path) -> None:
    image_listing = run([preferred_executable("pdfimages"), "-list", str(pdf)])
    rows = [line for line in image_listing.splitlines() if re.match(r"^\s*\d+\s+\d+\s+", line)]
    if rows:
        raise RuntimeError(f"vector figure contains raster image objects: {pdf}")
    font_listing = run([preferred_executable("pdffonts"), str(pdf)])
    rows = [
        line
        for line in font_listing.splitlines()
        if line.strip() and not line.lstrip().startswith("name") and "---" not in line
    ]
    if not rows or any("Type 3" in line or " yes " not in f" {line} " for line in rows):
        raise RuntimeError(f"vector figure fonts are not embedded non-Type-3 fonts: {pdf}")


def svg_to_vector_pdf(source: Path, output: Path) -> str:
    width, height = svg_dimensions(source)
    with tempfile.TemporaryDirectory(prefix="phasemap-svg-pdf-") as temporary:
        temporary_path = Path(temporary)
        html_path = temporary_path / "figure.html"
        raw_pdf = temporary_path / "figure.pdf"
        profile = temporary_path / "chrome-profile"
        html_path.write_text(
            "<!doctype html><meta charset='utf-8'><style>"
            f"@page{{size:{width:g}px {height:g}px;margin:0}}"
            f"html,body{{margin:0;width:{width:g}px;height:{height:g}px;overflow:hidden}}"
            f"img{{display:block;width:{width:g}px;height:{height:g}px}}"
            "</style><img alt='' src='"
            + html.escape(source.resolve().as_uri(), quote=True)
            + "'>",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                chromium(),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={raw_pdf}",
                html_path.resolve().as_uri(),
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        for _ in range(100):
            if raw_pdf.is_file() and raw_pdf.stat().st_size:
                break
            time.sleep(0.05)
        if not raw_pdf.is_file() or not raw_pdf.stat().st_size:
            raise RuntimeError(f"Chromium did not create vector PDF for {source}")
        normalize_chromium_pdf(raw_pdf)
        vector_pdf_qa(raw_pdf)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raw_pdf, output)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def qa_pdf(pdf: Path, render_dir: Path) -> tuple[int, str]:
    info = run([preferred_executable("pdfinfo"), str(pdf)])
    metadata = {
        key.strip(): value.strip()
        for line in info.splitlines()
        if ":" in line
        for key, _, value in (line.partition(":"),)
    }
    missing_metadata = [
        field for field in ("Title", "Author", "Subject", "Keywords") if not metadata.get(field)
    ]
    if missing_metadata:
        raise RuntimeError(
            f"PDF QA requires nonempty metadata fields {missing_metadata}: {pdf}"
        )
    fonts = run([preferred_executable("pdffonts"), str(pdf)])
    font_rows = [
        line
        for line in fonts.splitlines()
        if line.strip() and not line.lstrip().startswith("name") and "---" not in line
    ]
    embedded = re.compile(r"\s(?:yes)\s+(?:yes)\s+(?:yes|no)\s+\d+\s+\d+\s*$", re.I)
    if not font_rows or any("Type 3" in line or not embedded.search(line) for line in font_rows):
        raise RuntimeError(f"PDF QA requires embedded non-Type-3 fonts: {pdf}")
    extracted = run([preferred_executable("pdftotext"), "-enc", "UTF-8", str(pdf), "-"])
    if not extracted.strip():
        raise RuntimeError(f"PDF text extraction was empty: {pdf}")
    render_dir.mkdir(parents=True, exist_ok=True)
    for stale in render_dir.glob("page-*.png"):
        stale.unlink()
    prefix = render_dir / "page"
    run(
        [preferred_executable("pdftoppm"), "-png", "-r", "150", str(pdf), str(prefix)],
        timeout=240,
    )
    rendered = sorted(render_dir.glob("page-*.png"))
    if not rendered:
        raise RuntimeError(f"PDF page rendering produced no PNG files: {pdf}")
    return len(rendered), hashlib.sha256(pdf.read_bytes()).hexdigest()


def compile_document(source: Path, output: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"journal source missing: {source}")
    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = "1786579200"
    environment["FORCE_SOURCE_DATE"] = "1"
    with tempfile.TemporaryDirectory(prefix="phasemap-latex-") as temporary:
        build_dir = Path(temporary)
        run(
            [
                require("latexmk"),
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={build_dir}",
                source.name,
            ],
            cwd=source.parent,
            env=environment,
            timeout=300,
        )
        built = build_dir / source.with_suffix(".pdf").name
        if not built.is_file():
            raise RuntimeError(f"latexmk did not produce {built.name}")
        final_log = (build_dir / source.with_suffix(".log").name).read_text(
            encoding="utf-8", errors="replace"
        )
        if re.search(r"(?:Citation|Reference).*undefined|There were undefined references", final_log):
            raise RuntimeError(f"unresolved citation or cross-reference in {source.name}")
        normalize_pdf_trailer_id(built)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(built, output)
        output.with_suffix(".build.log").write_text(final_log, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--figures-only", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()

    for stem in FIGURE_STEMS:
        source = ROOT / "figures" / f"{stem}.svg"
        output = ROOT / "figures" / f"{stem}.pdf"
        digest = svg_to_vector_pdf(source, output)
        print(f"vector_figure={output}")
        print(f"vector_figure_sha256={digest}")

    if args.figures_only:
        return 0

    for source_name, output_name, pages_name in DOCUMENTS:
        source = JOURNAL_DIR / source_name
        output = output_dir / output_name
        render_dir = output_dir / pages_name
        compile_document(source, output)
        pages, digest = qa_pdf(output, render_dir)
        print(f"pdf={output}")
        print(f"pdf_sha256={digest}")
        print(f"render_dir={render_dir}")
        print(f"rendered_pages={pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
