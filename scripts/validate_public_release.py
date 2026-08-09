"""Fail-closed checks for the curated PHASEMAP public release."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "README.md",
    "LICENSE",
    "LICENSE-DATA.md",
    "LICENSES.md",
    "AUTHORS.md",
    "CITATION.cff",
    ".zenodo.json",
    "RELEASE_PROVENANCE.md",
    "manuscript/PHASEMAP_MANUSCRIPT.md",
    "manuscript/PHASEMAP_TECHNICAL_SUPPLEMENT.md",
    "manuscript/journal/PHASEMAP_MANUSCRIPT.pdf",
    "manuscript/journal/PHASEMAP_TECHNICAL_SUPPLEMENT.pdf",
    "docs/scientific-contract/CONTRACT.md",
    "docs/scientific-contract/validation_registry.json",
    "docs/scientific-contract/validation_registry.schema.json",
    "artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.json",
    "artifacts/raw/S-071-all-seven-trajectory-validation-primary-v1.attempt.json",
    "artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.json",
    "artifacts/raw/S-073-all-seven-trajectory-replacement-primary-v1.attempt.json",
)

TEXT_SUFFIXES = {
    ".cff", ".csv", ".json", ".md", ".py", ".tex", ".toml", ".txt", ".yml", ".yaml"
}
FORBIDDEN = (
    re.compile(r"(?i)c:[\\/]users[\\/][^\\/\s]+"),
    re.compile(r"(?i)\\users\\[^\\\s]+"),
    re.compile(r"(?i)\.codex[\\/]"),
)


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"missing required release files: {missing}")

    metadata = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    names = [creator["name"] for creator in metadata["creators"]]
    if names != ["Pierpoint, G. Blake", "Bernard, Olivier", "Liu, Yichen"]:
        raise SystemExit(f"incorrect author order: {names}")

    manuscript = (ROOT / "manuscript/PHASEMAP_MANUSCRIPT.md").read_text(encoding="utf-8")
    boundary = (
        "S-071 validated 14 of 46 required items and left 32 unresolved",
        "S-073 validated 32 of 46 and left 14 unresolved",
        "neither contradicted an item",
        "They are therefore not quantitative validation of the trajectory claim",
    )
    for statement in boundary:
        if statement not in manuscript:
            raise SystemExit(f"missing scientific evidence boundary: {statement}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "without pooling, retrying, top-up, or reinterpretation" not in readme:
        raise SystemExit("missing no-pooling/no-retry/no-top-up release boundary")

    leaks: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", ".venv", "tmp"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in FORBIDDEN):
            leaks.append(path.relative_to(ROOT).as_posix())
    if leaks:
        raise SystemExit(f"private-workspace path leakage: {leaks}")

    print("PHASEMAP public-release validation passed.")


if __name__ == "__main__":
    main()
