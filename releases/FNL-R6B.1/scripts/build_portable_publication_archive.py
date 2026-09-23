#!/usr/bin/env python3
"""Build a deterministic, allowlisted successor publication archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "LICENSE-DATA.md",
    "LICENSES.md",
    "pyproject.toml",
    "VERSION",
    "CITATION.cff",
)
REQUIRED_GLOBS = (
    "requirements/*.txt",
    "docs/release/REPRODUCTION.md",
    "docs/release/S074_REPRODUCTION.md",
    "docs/release/PORTABLE_PUBLICATION_ARCHIVE.md",
    "docs/release/FNL_R6B1_PACKAGING_README.md",
    "docs/release/TESTED_CONSTRAINTS.txt",
    "docs/scientific-contract/CONTRACT.md",
    "docs/scientific-contract/validation_registry.json",
    "docs/scientific-contract/validation_registry.schema.json",
    "docs/scientific-contract/S-074_VALIDATION_AMENDMENT.md",
    "docs/scientific-contract/S-074_RESOURCE_CAP_EXTENSION.md",
    "docs/scientific-contract/S-074_RICHARDSON_REANALYSIS.md",
    "experiments/S-074-precision-primary-v1.json",
    "experiments/S-074-precision-primary-v2.json",
    "experiments/run_s074_precision.py",
    "manuscript/PHASEMAP_MANUSCRIPT.md",
    "manuscript/PHASEMAP_TECHNICAL_SUPPLEMENT.md",
    "manuscript/CLAIM_EVIDENCE_MAP.md",
    "manuscript/README.md",
    "manuscript/journal/*.tex",
    "manuscript/journal/README.md",
    "manuscript/journal/fnl/*.tex",
    "manuscript/journal/fnl/*.cls",
    "manuscript/journal/fnl/*.bst",
    "manuscript/journal/fnl/*.md",
    "figures/*.svg",
    "figures/F-080-*.pdf",
    "src/phasemap/**/*.py",
    "scripts/build_portable_publication_archive.py",
    "scripts/build_manuscript_pdf.py",
    "scripts/build_fnl_submission.py",
    "scripts/render_s074_publication.py",
    "scripts/reanalyze_s074_richardson.py",
    "scripts/validate_validation_registry.py",
    "tests/simulation/test_simulator_smoke.py",
    "tests/simulation/test_s074_gpu_trajectories.py",
    "tests/simulation/test_s074_precision_statistics.py",
    "tests/simulation/test_s074_precision_study.py",
    "tests/theory/*.py",
    "tests/integration/test_validation_registry.py",
    "tests/integration/test_g7_publication_contract.py",
    "tests/integration/test_submission_archive.py",
    "tests/integration/test_fnl_submission.py",
    "tests/integration/test_s074_publication.py",
    "tests/integration/test_s074_richardson.py",
    "tests/integration/test_fnl_r6b_reporting.py",
    "tests/integration/test_r6b_diffusion_reporting.py",
    "docs/release/FNL_R6B_PUBLIC_RELEASE_README.md",
    "artifacts/derived/B-040-central-claim.md",
    "artifacts/derived/Q-030-target-lock.md",
    "artifacts/derived/F-050-figure-manifest.md",
    "artifacts/derived/F-070-scientific-figure-manifest.md",
    "artifacts/derived/S-021-validation-matrix.md",
    "artifacts/derived/S-071-trajectory-validation.md",
    "artifacts/derived/S-073-trajectory-replacement-validation.md",
    "artifacts/derived/S-074-precision-validation.md",
    "artifacts/derived/S-074-precision-table.md",
    "artifacts/derived/S-074-precision-table.tex",
    "artifacts/derived/S-074-figure-points.json",
    "artifacts/derived/S-074-Richardson-2026-09-06/*",
    "artifacts/derived/T-020-position-protocols.md",
    "artifacts/derived/T-021-nonposition-protocols.md",
    "artifacts/derived/T-030-memory-channel-proposition.md",
    "artifacts/derived/T-070-constrained-moment-frame.md",
    "artifacts/derived/T-080-exact-observability-theorem.md",
    "artifacts/derived/V-020-equivalence-map.md",
    "artifacts/derived/F-080-observability-figure-manifest.md",
)
PUBLIC_EXCLUDED_PATHS = frozenset({
    "manuscript/journal/fnl/PHASEMAP_FNL_Cover_Letter.tex",
    "docs/release/SUBMISSION_METADATA_DRAFT.md",
    "docs/release/FNL_SUBMISSION_METADATA.md",
})
REQUIRED_ENTRY_POINTS = (
    "README.md", "LICENSE", "pyproject.toml", "VERSION", "docs/release/REPRODUCTION.md",
    "docs/release/PORTABLE_PUBLICATION_ARCHIVE.md", "requirements/dev.txt",
    "scripts/build_portable_publication_archive.py", "scripts/build_manuscript_pdf.py",
    "manuscript/journal/PHASEMAP_MANUSCRIPT.tex",
    "manuscript/journal/PHASEMAP_TECHNICAL_SUPPLEMENT.tex",
    "tests/simulation/test_simulator_smoke.py", "tests/theory",
)
FORBIDDEN_PREFIXES = (
    ".git/", ".venv/", ".pytest_cache/", "dist/", "docs/exec/", "docs/status/",
    "docs/governance/", "docs/briefs/", "literature-audit/", ".codex/", "tmp/",
    "artifacts/raw/", "artifacts/derived/P-080-", "AGENTS.md", "ARCHITECTURE.md",
    "ORCHESTRATOR_PROMPT.md", "RUNBOOK.md", "START_HERE.md", "README_FIRST.md",
)
PORTABLE_TEST_ARGS = (
    "tests/integration/test_fnl_r6b_reporting.py",
    "tests/integration/test_r6b_diffusion_reporting.py",
    "tests/simulation/test_simulator_smoke.py", "tests/theory",
    "tests/simulation/test_s074_gpu_trajectories.py",
    "tests/simulation/test_s074_precision_statistics.py",
    "tests/simulation/test_s074_precision_study.py",
    "tests/integration/test_validation_registry.py",
    "tests/integration/test_g7_publication_contract.py",
    "tests/integration/test_submission_archive.py",
    "tests/integration/test_fnl_submission.py",
    "tests/integration/test_s074_publication.py",
    "tests/integration/test_s074_richardson.py",
)
MARKDOWN_LINK = re.compile(r"(!?\[[^]]*\])\(([^)\s]+)(?:\s+[^)]*)?\)")
TEXT_SUFFIXES = frozenset({".bst", ".cff", ".cls", ".csv", ".json", ".md", ".py", ".svg", ".tex", ".toml", ".txt"})
TEXT_BASENAMES = frozenset({"LICENSE", "VERSION"})
BINARY_SUFFIXES = frozenset({".pdf"})


def allowlisted_paths(root: Path) -> list[Path]:
    paths = [root / item for item in ROOT_FILES]
    for pattern in REQUIRED_GLOBS:
        matches = sorted(root.glob(pattern))
        if not matches:
            raise RuntimeError(f"required publication path missing: {pattern}")
        paths.extend(path for path in matches if path.is_file())
    unique = sorted(
        path for path in set(paths)
        if path.relative_to(root).as_posix() not in PUBLIC_EXCLUDED_PATHS
    )
    missing = [path.relative_to(root).as_posix() for path in unique if not path.is_file()]
    if missing:
        raise RuntimeError("required publication files missing: " + ", ".join(missing))
    return unique


def tracked_paths_if_repository(root: Path) -> set[str] | None:
    """Return tracked paths when *root* is a Git checkout, else ``None``.

    Portable archives intentionally contain no Git metadata, so an extracted
    archive remains a supported build root.  When metadata is present at the
    exact root, however, the publication payload must not silently absorb an
    untracked file matched by one of the recursive allowlist globs.
    """
    metadata_present = (root / ".git").exists()
    try:
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
        )
    except (OSError, UnicodeError) as exc:
        if metadata_present:
            raise RuntimeError("unable to inspect Git metadata for publication payload") from exc
        return None
    if top_level.returncode:
        if metadata_present:
            raise RuntimeError(
                "unable to inspect Git metadata for publication payload: "
                + top_level.stderr.strip()
            )
        return None
    if Path(top_level.stdout.strip()).resolve() != root.resolve():
        return None
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
    )
    if tracked.returncode:
        raise RuntimeError(
            "unable to enumerate tracked publication sources: "
            + tracked.stderr.decode("utf-8", errors="replace").strip()
        )
    try:
        return {
            name
            for name in tracked.stdout.decode("utf-8", errors="strict").split("\0")
            if name
        }
    except UnicodeError as exc:
        raise RuntimeError("tracked publication source path is not valid UTF-8") from exc


def require_tracked_sources(root: Path, paths: list[Path]) -> None:
    tracked = tracked_paths_if_repository(root)
    if tracked is None:
        return
    untracked = sorted(
        path.relative_to(root).as_posix()
        for path in paths
        if path.relative_to(root).as_posix() not in tracked
    )
    if untracked:
        raise RuntimeError(
            "refusing untracked publication payload paths: " + ", ".join(untracked)
        )


def canonical_payload_bytes(name: str, data: bytes) -> bytes:
    """Return checkout-independent bytes for one declared payload member."""
    member = PurePosixPath(name)
    suffix = member.suffix.lower()
    if suffix in BINARY_SUFFIXES:
        return data
    if suffix not in TEXT_SUFFIXES and member.name not in TEXT_BASENAMES:
        raise RuntimeError(f"unsupported publication payload type: {name}")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise RuntimeError(f"publication text payload is not valid UTF-8: {name}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def is_external_or_anchor(target: str) -> bool:
    return target.startswith(("#", "http://", "https://", "mailto:", "doi:"))


def resolved_member(source: str, target: str) -> str | None:
    path = target.split("#", 1)[0]
    if not path:
        return source
    candidate = (PurePosixPath(source).parent / PurePosixPath(path)).as_posix()
    normalized = posixpath.normpath(candidate)
    return None if normalized == ".." or normalized.startswith("../") else normalized


def markdown_link_errors(members: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    for name, payload in members.items():
        if not name.endswith(".md"):
            continue
        for match in MARKDOWN_LINK.finditer(payload.decode("utf-8")):
            target = match.group(2)
            if not is_external_or_anchor(target):
                resolved = resolved_member(name, target)
                if resolved not in members:
                    errors.append(f"{name}: {target}")
    return errors


def archive_payload(root: Path) -> dict[str, bytes]:
    paths = allowlisted_paths(root)
    require_tracked_sources(root, paths)
    payload = {
        path.relative_to(root).as_posix(): canonical_payload_bytes(
            path.relative_to(root).as_posix(), path.read_bytes()
        )
        for path in paths
    }
    for name, data in list(payload.items()):
        if not name.endswith(".md"):
            continue
        text = data.decode("utf-8")
        def retain_or_unlink(match: re.Match[str]) -> str:
            target = match.group(2)
            resolved = resolved_member(name, target)
            return match.group(0) if is_external_or_anchor(target) or resolved in payload else match.group(1)
        payload[name] = MARKDOWN_LINK.sub(retain_or_unlink, text).encode("utf-8")
    errors = markdown_link_errors(payload)
    if errors:
        raise RuntimeError("broken Markdown links: " + "; ".join(errors))
    return payload


def collected_test_count(root: Path) -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", *PORTABLE_TEST_ARGS], cwd=root, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    match = re.search(r"(?:collected\s+(\d+)\s+items|(?:\d+)\s+tests?\s+collected)", result.stdout + result.stderr)
    if not match:
        raise RuntimeError("pytest collection completed without a test-count summary")
    return int(match.group(1) or re.search(r"(\d+)", match.group(0)).group(1))


def archive_manifest(payload: dict[str, bytes], test_count: int) -> bytes:
    return (json.dumps({"archive_format": 2, "entry_points": list(REQUIRED_ENTRY_POINTS), "portable_test_suite": {"command": "python -m pytest -q " + " ".join(PORTABLE_TEST_ARGS), "collected_test_count": test_count, "count_provenance": "Generated from the portable validator command by pytest --collect-only during archive construction."}, "files": sorted(payload)}, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_zip(root: Path, output: Path, test_count: int) -> str:
    payload = archive_payload(root)
    for entry in REQUIRED_ENTRY_POINTS:
        if entry not in payload and not any(name.startswith(entry + "/") for name in payload):
            raise RuntimeError(f"archive entry point missing: {entry}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
        info = zipfile.ZipInfo("ARCHIVE_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
        archive.writestr(info, archive_manifest(payload, test_count))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", type=Path, default=ROOT / "dist" / "PHASEMAP-portable-publication-archive.zip"); args = parser.parse_args()
    count = collected_test_count(ROOT)
    if count < 1: raise SystemExit("refusing to archive an empty test suite")
    digest = write_zip(ROOT, args.output.resolve(), count)
    print(f"archive={args.output.resolve()}\nsha256={digest}\ncollected_test_count={count}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
