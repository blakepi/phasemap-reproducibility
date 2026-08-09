"""Generate deterministic F-050 and scope-bounded F-070 scientific figures."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIGURES = ROOT / "figures"
MANIFEST = ROOT / "artifacts" / "derived" / "F-050-figure-manifest.md"
F070_MANIFEST = ROOT / "artifacts" / "derived" / "F-070-scientific-figure-manifest.md"
INPUTS = (
    ROOT / "artifacts" / "derived" / "B-040-central-claim.md",
    ROOT / "artifacts" / "derived" / "S-021-validation-matrix.md",
    ROOT / "docs" / "scientific-contract" / "CONTRACT.md",
)
F070_INPUTS = (
    ROOT / "artifacts" / "derived" / "T-070-constrained-moment-frame.md",
    ROOT / "artifacts" / "derived" / "S-073-trajectory-replacement-validation.md",
)


def canonical_text_bytes(path: Path) -> bytes:
    """Return UTF-8 text with platform-independent LF line endings."""
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_text_bytes(path)).hexdigest()


def svg_document(title: str, body: str, *, height: int = 760, description: str = "") -> str:
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#17202a}.title{font-size:30px;font-weight:700}.sub{font-size:17px}.head{font-size:19px;font-weight:700}.label{font-size:16px}.small{font-size:14px}.mono{font-family:monospace;font-size:15px}.note{font-size:13px;fill:#455a64}</style>',
        f"<title>{title}</title>",
    ]
    if description:
        elements.append(f"<desc>{description}</desc>")
    elements.extend((body, "</svg>", ""))
    return "\n".join(elements)


def structural_map() -> str:
    rows = (
        ("P", "yes", "localized", "bounded"),
        ("PV", "yes", "localized", "bounded"),
        ("PTheta", "yes", "localized", "bounded"),
        ("PVTheta", "yes", "localized", "bounded"),
        ("V", "no", "diffusive", "diffusive"),
        ("Theta", "no", "diffusive", "ballistic if Pe*rho>0"),
        ("VTheta", "no", "diffusive", "ballistic if Pe*rho>0"),
    )
    table = [
        '<text x="60" y="55" class="title">All-seven reset-map structural classification</text>',
        '<text x="60" y="84" class="sub">Contract v0.4: complete component-level second-order record, M&gt;0, rho&gt;0, Pe&gt;=0</text>',
        '<rect x="60" y="112" width="1080" height="62" fill="#e8f4f8" stroke="#2471a3"/>',
        '<text x="84" y="143" class="head">Every one of the 21 distinct protocol pairs has a full-record separating witness.</text>',
        '<text x="84" y="165" class="small">The decision tree below is exhaustive and nonoverlapping; restricted identities are not protocol equivalence.</text>',
        '<text x="60" y="218" class="head">Exhaustive witness partition: 12 + 6 + 3 = 21 pairs</text>',
        '<rect x="60" y="235" width="340" height="105" fill="#eaf2f8" stroke="#2471a3"/>',
        '<text x="82" y="265" class="head">12 pairs: different P status</text>',
        '<text x="82" y="293" class="small">Witness: localized versus centered diffusive</text>',
        '<text x="82" y="318" class="note">Valid throughout Pe&gt;=0 at rho&gt;0.</text>',
        '<rect x="430" y="235" width="340" height="105" fill="#f4ecf7" stroke="#7d3c98"/>',
        '<text x="452" y="265" class="head">6 pairs: same P, different Theta</text>',
        '<text x="452" y="293" class="small">Witness: orientation mean or matrix</text>',
        '<text x="452" y="318" class="note">Component-level separation at rho&gt;0.</text>',
        '<rect x="800" y="235" width="340" height="105" fill="#fef9e7" stroke="#b7950b"/>',
        '<text x="822" y="260" class="head">3 pairs: same P and Theta</text>',
        '<text x="822" y="282" class="head">different V</text>',
        '<text x="822" y="307" class="small">Witness: velocity matrix; mean when Pe&gt;0</text>',
        '<text x="822" y="328" class="note">Passive endpoint uses a positive S diagonal.</text>',
        '<rect x="60" y="370" width="1080" height="286" fill="#ffffff" stroke="#90a4ae"/>',
        '<text x="85" y="400" class="head">map</text><text x="255" y="400" class="head">position reset</text><text x="455" y="400" class="head">centered spatial class</text><text x="760" y="400" class="head">raw-MSD class</text>',
    ]
    for index, (protocol, position, centered, raw) in enumerate(rows):
        y = 432 + index * 31
        fill = "#d5f5e3" if position == "yes" else "#fdebd0"
        table.append(f'<rect x="72" y="{y - 20}" width="1050" height="28" fill="{fill}" opacity="0.62"/>')
        table.append(f'<text x="85" y="{y}" class="mono">{protocol}</text><text x="285" y="{y}" class="label">{position}</text><text x="455" y="{y}" class="label">{centered}</text><text x="760" y="{y}" class="label">{raw}</text>')
    table.extend(
        (
            '<rect x="60" y="685" width="1080" height="150" fill="#fdf2e9" stroke="#ca6f1e"/>',
            '<text x="84" y="715" class="head">Primary sector identity (exact scope)</text>',
            '<text x="84" y="744" class="label">PV / V     PTheta / Theta     PVTheta / VTheta</text>',
            '<text x="84" y="772" class="label">Adding position reset preserves the complete internal (v,u) process while changing transport to localization.</text>',
            '<text x="84" y="799" class="note">PV/PVTheta contraction: Tr(S)=E|v|^2, Tr(C)=E[r dot v], and Tr(R)=E|r|^2 are equal.</text>',
            '<text x="84" y="820" class="note">For Pe&gt;0 their centered spatial traces differ; orientation/components distinguish the pair throughout Pe&gt;=0.</text>',
            '<text x="60" y="875" class="note">Analytic source: T-030 witness proposition. S-021 is finite-grid support, not continuum-wide proof.</text>',
        )
    )
    return svg_document(
        "All-seven structural classification", "\n".join(table), height=900
    )


def f070_reset_lattice() -> str:
    body = [
        '<text x="60" y="55" class="title">All-seven reset lattice and exact classifier</text>',
        '<text x="60" y="84" class="sub">Each node is a nonempty reset map over position P, velocity V, and orientation Theta.</text>',
        '<text x="60" y="120" class="head">Reset lattice</text>',
    ]
    nodes = (("P", 210, 180), ("V", 500, 180), ("Theta", 790, 180), ("PV", 355, 310), ("PTheta", 645, 310), ("VTheta", 935, 310), ("PVTheta", 645, 440))
    edges = ((210, 205, 355, 310), (500, 205, 355, 310), (210, 205, 645, 310), (790, 205, 645, 310), (500, 205, 935, 310), (790, 205, 935, 310), (355, 335, 645, 440), (645, 335, 645, 440), (935, 335, 645, 440))
    for x1, y1, x2, y2 in edges:
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#7f8c8d" stroke-width="3"/>')
    for name, x, y in nodes:
        fill = "#d5f5e3" if "P" in name else "#fdebd0"
        body.append(f'<rect x="{x - 70}" y="{y - 25}" width="140" height="50" rx="8" fill="{fill}" stroke="#2471a3" stroke-width="2"/><text x="{x - 20}" y="{y + 7}" class="head">{name}</text>')
    body.extend((
        '<rect x="60" y="510" width="1080" height="166" fill="#eaf2f8" stroke="#2471a3"/>',
        '<text x="84" y="542" class="head">Exact full-record classifier: 12 + 6 + 3 = 21 distinct pairs</text>',
        '<text x="84" y="575" class="label">12: different P status — localized versus centered-diffusive transport.</text>',
        '<text x="84" y="605" class="label">6: same P, different Theta — orientation mean or matrix.</text>',
        '<text x="84" y="635" class="label">3: same P and Theta, different V — velocity matrix; mean when Pe&gt;0.</text>',
        '<text x="84" y="662" class="note">Exact scope: M&gt;0, rho&gt;0, Pe&gt;=0. A restricted identity is not protocol equivalence.</text>',
    ))
    return svg_document("F-070 all-seven reset lattice and classifier", "\n".join(body), height=710, description="Seven reset maps arranged as a lattice, followed by the exact 12 plus 6 plus 3 pair classifier.")


def f070_physical_transport() -> str:
    body = (
        '<text x="60" y="55" class="title">Physical frame, transport, and restricted equalities</text>'
        '<text x="60" y="84" class="sub">The 28 stored coordinates form a redundant frame; physical states obey one=1 and uu_xx+uu_yy=1.</text>'
        '<rect x="60" y="115" width="510" height="190" fill="#eaf2f8" stroke="#2471a3"/>'
        '<text x="84" y="150" class="head">Constrained physical frame</text>'
        '<text x="84" y="183" class="label">P, V, PV preserve the trace residual.</text>'
        '<text x="84" y="213" class="label">Theta, PTheta, VTheta, PVTheta restore it.</text>'
        '<text x="84" y="244" class="note">At M=2, Pe=3, rho=5: rank/nullity P 26/2; PTheta 27/1.</text>'
        '<rect x="630" y="115" width="510" height="190" fill="#fdf2e9" stroke="#ca6f1e"/>'
        '<text x="654" y="150" class="head">Transport quantities are not interchangeable</text>'
        '<text x="654" y="183" class="label">Raw MSD: E|r|^2 includes mean-drift contribution.</text>'
        '<text x="654" y="213" class="label">Centered covariance: Cov(r) measures fluctuations.</text>'
        '<text x="654" y="244" class="note">Never infer centered-covariance equality from raw-MSD equality.</text>'
        '<rect x="60" y="345" width="1080" height="230" fill="#f4f6f7" stroke="#90a4ae"/>'
        '<text x="84" y="382" class="head">Exact sector identities and contracted-observable degeneracy</text>'
        '<text x="84" y="418" class="label">PV / V, PTheta / Theta, and PVTheta / VTheta: complete internal (v,u) sector is identical.</text>'
        '<text x="84" y="449" class="label">Position reset nevertheless changes spatial transport to localization.</text>'
        '<text x="84" y="490" class="label">PV/PVTheta: equal Tr(S)=E|v|^2, Tr(C)=E[r dot v], and Tr(R)=E|r|^2.</text>'
        '<text x="84" y="521" class="note">This is a contracted-observable degeneracy only; centered traces differ for Pe&gt;0 and component/orientation records separate throughout Pe&gt;=0.</text>'
    )
    return svg_document("F-070 physical frame and transport scopes", body, height=620, description="The constrained 28-coordinate frame, a visual distinction between raw MSD and centered covariance, and the exact sector-identity scopes.")


def f070_qualitative_trajectory() -> str:
    body = (
        '<text x="60" y="55" class="title">Trajectory evidence: validated qualitative checks, unresolved quantitative claim</text>'
        '<text x="60" y="84" class="sub">Fixed production attempts were integrity/classification valid but did not close the all-seven quantitative trajectory claim.</text>'
        '<rect x="60" y="115" width="500" height="170" fill="#fdebd0" stroke="#ca6f1e"/>'
        '<text x="84" y="150" class="head">S-071 immutable attempt</text>'
        '<text x="84" y="190" class="title">14 / 46 validated</text>'
        '<text x="84" y="225" class="label">32 unresolved; 0 contradicted</text>'
        '<rect x="640" y="115" width="500" height="170" fill="#fef9e7" stroke="#b7950b"/>'
        '<text x="664" y="150" class="head">S-073 fresh replacement</text>'
        '<text x="664" y="190" class="title">32 / 46 validated</text>'
        '<text x="664" y="225" class="label">14 unresolved; 0 contradicted</text>'
        '<rect x="60" y="325" width="1080" height="205" fill="#eaf2f8" stroke="#2471a3"/>'
        '<text x="84" y="360" class="head">Validated qualitative trajectory evidence from S-073</text>'
        '<text x="84" y="395" class="label">36 / 36 required signs or equalities; 36 / 36 Richardson residual checks.</text>'
        '<text x="84" y="426" class="label">3 / 3 pathwise sector identities; 7 / 7 reference-scope checks.</text>'
        '<text x="84" y="462" class="label">No sign, identity, convergence, provenance, or scientific contradiction was recorded.</text>'
        '<text x="84" y="500" class="note">Boundary: unresolved interval-containment and adequacy gates prohibit a quantitative all-seven trajectory-validation claim; no retry, pooling, or threshold change is represented.</text>'
    )
    return svg_document("F-070 qualitative trajectory evidence and boundary", body, height=570, description="S-071 and S-073 validated counts, qualitative S-073 checks, and an explicit boundary that quantitative all-seven trajectory validation remains unresolved.")


def validation_coverage() -> str:
    protocols = ("P", "V", "Theta", "PV", "PTheta", "VTheta", "PVTheta")
    cells = [
        '<text x="60" y="55" class="title">S-021 all-seven validation coverage</text>',
        '<text x="60" y="84" class="sub">Independent finite-grid numerical support for accepted exact second-order formulas</text>',
        '<rect x="60" y="112" width="1080" height="98" fill="#eaf2f8" stroke="#2471a3"/>',
        '<text x="85" y="145" class="head">91 / 91 numeric gates validated; 15,652 / 15,652 T-022 rows validated</text>',
        '<text x="85" y="175" class="label">13 exact-rational cases per protocol; four precision/horizon cells per record; no unresolved or contradicted result.</text>',
        '<text x="85" y="196" class="note">Locked formula/reference tolerance: 1e-12. This figure does not claim exact inequality from the finite grid.</text>',
        '<text x="87" y="250" class="head">protocol</text>',
    ]
    for case in range(13):
        cells.append(f'<text x="{230 + case * 65}" y="250" class="small">{case + 1}</text>')
    for row, protocol in enumerate(protocols):
        y = 275 + row * 45
        cells.append(f'<text x="87" y="{y + 23}" class="mono">{protocol}</text>')
        for case in range(13):
            x = 215 + case * 65
            cells.append(f'<rect x="{x}" y="{y}" width="48" height="30" rx="3" fill="#27ae60"/><text x="{x + 13}" y="{y + 21}" class="small" fill="#ffffff">PASS</text>')
    cells.extend(
        (
            '<rect x="60" y="620" width="1080" height="70" fill="#f4f6f7" stroke="#90a4ae"/>',
            '<text x="85" y="650" class="label">Complete-reset independent T-012 gate: 754 / 754 rows validated. Passive, rare-reset, frequent-reset, resonance, and overdamped support groups: validated.</text>',
            '<text x="85" y="676" class="note">Canonical raw S-021 artifact hash is recorded in the companion F-050 provenance manifest.</text>',
            '<text x="60" y="725" class="note">Source: S-021 validation matrix. The isolated operator is an independent implementation path; its role is support, not a replacement for the exact witness proof.</text>',
        )
    )
    return svg_document("S-021 validation coverage", "\n".join(cells))


def validate_inputs() -> None:
    claim, matrix, contract = (path.read_text(encoding="utf-8") for path in INPUTS)
    requirements = (
        (claim, "every distinct pair is exactly distinguishable"),
        (claim, "optional higher-order/distributional contrast"),
        (matrix, "All `15,652/15,652` T-022 formula rows validated"),
        (matrix, "All `91/91`"),
        (matrix, "gates validated."),
        (contract, "**Contract version:** 0.4"),
    )
    missing = [needle for text, needle in requirements if needle not in text]
    if missing:
        raise ValueError(f"accepted input validation failed: {missing}")


def validate_f070_inputs() -> None:
    frame, trajectory = (path.read_text(encoding="utf-8") for path in F070_INPUTS)
    requirements = (
        (frame, "implementation-stable 28 stored"),
        (frame, "one = 1"),
        (frame, "uu_xx + uu_yy = 1"),
        (frame, "P` | 26 | 2"),
        (trajectory, "**32** | **14** | **0** | **46**"),
        (trajectory, "All 36 required sign or equality checks validated."),
        (trajectory, "36 matched Richardson"),
        (trajectory, "All three exact internal"),
        (trajectory, "all seven reference-scope checks validated"),
        (trajectory, "validate the planned quantitative all-seven"),
    )
    missing = [needle for text, needle in requirements if needle not in text]
    if missing:
        raise ValueError(f"F-070 accepted input validation failed: {missing}")


def expected_outputs() -> dict[Path, str]:
    validate_inputs()
    validate_f070_inputs()
    structural = FIGURES / "F-050-all-seven-structural-map.svg"
    coverage = FIGURES / "F-050-s021-validation-coverage.svg"
    f050_outputs = {structural: structural_map(), coverage: validation_coverage()}
    f070_outputs = {
        FIGURES / "F-070-reset-lattice-and-classifier.svg": f070_reset_lattice(),
        FIGURES / "F-070-physical-transport-and-degeneracies.svg": f070_physical_transport(),
        FIGURES / "F-070-qualitative-trajectory-evidence.svg": f070_qualitative_trajectory(),
    }
    outputs = {**f050_outputs, **f070_outputs}
    source_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{canonical_text_sha256(path)}` |"
        for path in INPUTS
    )
    figure_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{hashlib.sha256(content.encode()).hexdigest()}` |"
        for path, content in f050_outputs.items()
    )
    script_hash = canonical_text_sha256(Path(__file__))
    outputs[MANIFEST] = f"""# F-050 figure provenance manifest

**Task result:** PASS
**Contract:** v0.4
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Canonical source hashes

All text hashes below are calculated from UTF-8 bytes after normalizing line
endings to LF, so they are stable across Git checkouts.

| Accepted source | SHA-256 |
|---|---|
{source_rows}

| Generation script | SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `{script_hash}` |

## Generated figure hashes

| Figure | SHA-256 |
|---|---|
{figure_rows}

## Claim map

| Figure | Allowed claim | Scope and evidence boundary |
|---|---|---|
| `F-050-all-seven-structural-map.svg` | Every distinct pair is exactly distinguishable on the complete component-level second-order record. | `M>0`, `rho>0`, `Pe>=0`; the displayed nonoverlapping `12 + 6 + 3` analytic witness partition supports the claim. Position-toggle matches are sector identities, not protocol equivalence. |
| `F-050-all-seven-structural-map.svg` | Position-reset toggles preserve the complete internal `(v,u)` process while spatial transport changes to localization. | `PV/V`, `PTheta/Theta`, and `PVTheta/VTheta`; no internal higher-order discriminator is implied. |
| `F-050-all-seven-structural-map.svg` | `PV/PVTheta` have equal `Tr(S)=E|v|^2`, `Tr(C)=E[r dot v]`, and `Tr(R)=E|r|^2`. | Contracted-observable degeneracy only. Their centered spatial traces differ for `Pe>0`; orientation and component records separate the pair throughout `Pe>=0`. |
| `F-050-s021-validation-coverage.svg` | The locked independent finite-grid matrix validated all 91 numeric gates and 15,652 formula rows. | S-021 supports accepted exact theory but does not prove continuum-wide equality/inequality or establish a higher-order claim. |

No optional higher-order/distributional result is represented. Raw MSD and centered covariance are distinct throughout.
"""
    f070_source_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{canonical_text_sha256(path)}` |"
        for path in F070_INPUTS
    )
    f070_figure_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{hashlib.sha256(content.encode()).hexdigest()}` |"
        for path, content in f070_outputs.items()
    )
    outputs[F070_MANIFEST] = f"""# F-070 scientific figure provenance manifest

**Task result:** PASS — scope-bounded qualitative trajectory evidence only
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Accepted inputs

| Accepted source | Canonical-LF SHA-256 |
|---|---|
{f070_source_rows}

| Generation script | Canonical-LF SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `{canonical_text_sha256(Path(__file__))}` |

## Generated figure hashes

| Figure | SHA-256 |
|---|---|
{f070_figure_rows}

## Scientific scope and accessibility

| Figure | Allowed claim and boundary |
|---|---|
| `F-070-reset-lattice-and-classifier.svg` | The seven nonempty maps and exact full-record `12 + 6 + 3` witness partition. Scope: `M>0`, `rho>0`, `Pe>=0`; restricted identities are not protocol equivalence. |
| `F-070-physical-transport-and-degeneracies.svg` | The physical 28-coordinate frame and exact transport/identity scopes. Raw `E|r|^2` and centered `Cov(r)` are distinct quantities. |
| `F-070-qualitative-trajectory-evidence.svg` | S-071 reached 14/46 and S-073 reached 32/46 validated items, with neither contradicted. It displays only validated signs/equalities, Richardson convergence, sector identities, and reference scope. |

Every SVG has a title and plain-language description. The S-073 fixed attempt
is integrity/classification valid but scientifically unresolved for the
quantitative all-seven trajectory claim: 14/46 gating items remain unresolved.
The figures do not represent a retry, pooling, threshold change, or quantitative
all-seven trajectory validation.
"""
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify generated files without writing")
    args = parser.parse_args()
    outputs = expected_outputs()
    mismatches = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if mismatches:
            print("FAIL: generated outputs differ: " + ", ".join(str(path.relative_to(ROOT)) for path in mismatches))
            return 1
        print("PASS: F-050 and F-070 figures and provenance manifests are reproducible.")
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print("PASS: regenerated F-050 and F-070 figures and provenance manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
