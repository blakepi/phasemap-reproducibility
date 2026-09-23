"""Generate deterministic F-050 and scope-bounded F-070 scientific figures."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIGURES = ROOT / "figures"
MANIFEST = ROOT / "artifacts" / "derived" / "F-050-figure-manifest.md"
F070_MANIFEST = ROOT / "artifacts" / "derived" / "F-070-scientific-figure-manifest.md"
F080_MANIFEST = ROOT / "artifacts" / "derived" / "F-080-observability-figure-manifest.md"
INPUTS = (
    ROOT / "artifacts" / "derived" / "B-040-central-claim.md",
    ROOT / "artifacts" / "derived" / "S-021-validation-matrix.md",
    ROOT / "docs" / "scientific-contract" / "CONTRACT.md",
)
F070_INPUTS = (
    ROOT / "artifacts" / "derived" / "T-070-constrained-moment-frame.md",
    ROOT / "artifacts" / "derived" / "S-073-trajectory-replacement-validation.md",
)
F080_INPUTS = (
    ROOT / "artifacts" / "derived" / "T-080-exact-observability-theorem.md",
    ROOT / "artifacts" / "derived" / "S-071-trajectory-validation.md",
    ROOT / "artifacts" / "derived" / "S-073-trajectory-replacement-validation.md",
)


def canonical_text_bytes(path: Path) -> bytes:
    """Return UTF-8 text with platform-independent LF line endings."""
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_text_bytes(path)).hexdigest()


def svg_document(
    title: str,
    body: str,
    *,
    height: int = 760,
    width: int = 1200,
    font_scale: float = 1.0,
    min_px: float = 0.0,
    description: str = "",
) -> str:
    # min_px raises small labels without inflating the headings. At five-inch
    # width, 24 px on a 1200 px canvas prints at 7.2 pt; inspect the final PDF
    # at its intended size rather than inferring a publisher requirement.
    def px(base: float) -> str:
        value = max(base * font_scale, min_px)
        return f"{value:g}"

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<style>text{{font-family:Arial,sans-serif;fill:#17202a}}.title{{font-size:{px(30)}px;font-weight:700}}.sub{{font-size:{px(17)}px}}.head{{font-size:{px(19)}px;font-weight:700}}.label{{font-size:{px(16)}px}}.small{{font-size:{px(14)}px}}.mono{{font-family:monospace;font-size:{px(15)}px}}.note{{font-size:{px(13)}px;fill:#455a64}}</style>',
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


def f080_three_coordinate_decoder() -> str:
    rho_fraction = "(<tspan font-style=\"italic\">ρ</tspan>+2)/(<tspan font-style=\"italic\">ρ</tspan>+4)"
    theta = '<tspan font-style="italic">Θ</tspan>'
    rows = (
        ("P", "localized", "1/2", "A"), ("PV", "localized", "1/2", "B"),
        (f"P{theta}", "localized", rho_fraction, "C"),
        (f"PV{theta}", "localized", rho_fraction, "B"),
        ("V", "diffusive", "1/2", "B"), (theta, "diffusive", rho_fraction, "C"),
        (f"V{theta}", "diffusive", rho_fraction, "B"),
    )
    body = [
        '<text x="60" y="55" class="title">Three-observable decoder for reset masks</text>',
        '<text x="60" y="84" class="sub">Exact matched-parameter result for M&gt;0, Pe&gt;=0, <tspan font-style="italic">ρ</tspan>&gt;0; G is the centered spatial growth class.</text>',
        '<rect x="60" y="112" width="1080" height="84" fill="#eaf2f8" stroke="#2471a3"/>',
        '<text x="84" y="147" class="head">Decoder: <tspan font-style="italic">Σ</tspan> = (G, U<tspan baseline-shift="sub" font-size="75%">xx</tspan>, Tr S) recovers P, <tspan font-style="italic">Θ</tspan>, then V.</text>',
        '<text x="84" y="174" class="label">Localized/diffusive → orientation-reset status → velocity-reset status.</text>',
        '<text x="78" y="238" class="head">map</text><text x="230" y="238" class="head">G</text><text x="490" y="238" class="head">U<tspan baseline-shift="sub" font-size="75%">xx</tspan></text><text x="770" y="238" class="head">Tr S</text>',
    ]
    for index, (name, growth, uxx, trace) in enumerate(rows):
        y = 270 + index * 47
        fill = "#d5f5e3" if growth == "localized" else "#fdebd0"
        body.append(f'<rect x="60" y="{y - 26}" width="1080" height="38" fill="{fill}" opacity="0.65"/>')
        body.append(f'<text x="78" y="{y}" class="mono">{name}</text><text x="230" y="{y}" class="label">{growth}</text><text x="490" y="{y}" class="label">{uxx}</text><text x="770" y="{y}" class="label">{trace}</text>')
    body.extend((
        '<rect x="60" y="620" width="1080" height="110" fill="#fdf2e9" stroke="#ca6f1e"/>',
        '<text x="84" y="653" class="head">Exact strict gaps</text>',
        '<text x="84" y="683" class="label">(<tspan font-style="italic">ρ</tspan>+2)/(<tspan font-style="italic">ρ</tspan>+4) - 1/2 = <tspan font-style="italic">ρ</tspan>/[2(<tspan font-style="italic">ρ</tspan>+4)] &gt; 0; A-B &gt; 0; C-B &gt; 0.</text>',
        '<text x="84" y="712" class="note">The decoder remains injective at the passive point Pe=0 and on the resonance M<tspan font-style="italic">ρ</tspan>=1.</text>',
    ))
    return svg_document("F-080 exact three-coordinate reset-mask decoder", "\n".join(body), height=755, min_px=27, description="Exact seven-row signatures showing how centered spatial growth, orientation alignment, and velocity-energy trace jointly decode each reset mask. Sigma = (G, Uxx, Tr S); the decoder remains injective at the passive point Pe=0 and on the resonance Mrho=1.")


def f080_strict_subsignatures() -> str:
    # bits: 2 = recovered, 1 = recovered only when velocity is retained, 0 = lost.
    rows = (
        ("G only", (2, 0, 0), 2, "P status"),
        ("Uₓₓ only", (0, 2, 0), 2, "Θ status"),
        ("Tr S only", (0, 1, 2), 3, "P | Θ | V status"),
        ("(G, Uₓₓ)", (2, 2, 0), 4, "P/Θ combinations"),
        ("(Uₓₓ, Tr S)", (0, 2, 2), 4, "Θ/V combinations"),
        ("(G, Tr S)", (2, 1, 2), 5, "P/V combinations"),
        ("Σ = (G, Uₓₓ, Tr S)", (2, 2, 2), 7, "all seven distinct"),
    )
    accent, faint, rule = "#0072B2", "#d6dde2", "#9aa7b0"
    body = [
        '<text x="34" y="44" class="title">Proper subsignatures lose reset bits</text>',
        '<text x="34" y="72" class="sub">Matched parameters; generic class counts with exceptions below.</text>',
        '<text x="34" y="118" class="head">observed</text>',
        '<text x="258" y="118" class="head">bits read</text>',
        '<text x="410" y="118" class="head">distinguishable classes (of 7)</text>',
        '<text x="34" y="140" class="note">P</text><text x="258" y="140" class="note">P</text>',
        f'<line x1="34" y1="152" x2="1010" y2="152" stroke="{rule}" stroke-width="2"/>',
    ]
    # column sub-labels for the three bit markers
    body[5] = (
        '<text x="252" y="140" class="note">P</text>'
        '<text x="292" y="140" class="note">Θ</text>'
        '<text x="332" y="140" class="note">V</text>'
    )
    for index, (label, bits, classes, merged) in enumerate(rows):
        y = 176 + index * 62
        final = index == len(rows) - 1
        if final:
            body.append(f'<rect x="26" y="{y - 26}" width="992" height="56" fill="#e8f1f8" stroke="{accent}" stroke-width="2" rx="4"/>')
        elif index % 2 == 0:
            body.append(f'<rect x="26" y="{y - 26}" width="992" height="56" fill="#f6f8f9"/>')
        weight = ' font-weight="700"' if final else ""
        body.append(f'<text x="34" y="{y + 6}" class="label"{weight}>{label}</text>')
        for slot, state in enumerate(bits):
            cx = 252 + slot * 40
            if state == 2:
                body.append(f'<circle cx="{cx}" cy="{y}" r="10" fill="{accent}"/>')
            elif state == 1:
                body.append(f'<circle cx="{cx}" cy="{y}" r="10" fill="none" stroke="{accent}" stroke-width="2"/>')
                body.append(f'<path d="M {cx} {y - 10} A 10 10 0 0 1 {cx} {y + 10} Z" fill="{accent}"/>')
            else:
                body.append(f'<circle cx="{cx}" cy="{y}" r="10" fill="none" stroke="{rule}" stroke-width="2"/>')
        for cell in range(7):
            cx = 410 + cell * 22
            fill = accent if cell < classes else faint
            body.append(f'<rect x="{cx}" y="{y - 11}" width="16" height="22" fill="{fill}" rx="2"/>')
        body.append(f'<text x="577" y="{y + 6}" class="label"{weight}>{classes}</text>')
        body.append(f'<text x="616" y="{y + 5}" class="note">{merged}</text>')
    body.extend((
        f'<line x1="34" y1="612" x2="1010" y2="612" stroke="{rule}" stroke-width="2"/>',
        '<text x="34" y="644" class="note">Filled = bit recovered; half = velocity-retained condition; open = lost.</text>',
        '<text x="34" y="680" class="head">Passive and resonant exception</text>',
        '<text x="34" y="710" class="label">At Pe=0 or Mρ=1, Tr S merges {P,Θ,PΘ} and (G, Tr S) merges {P,PΘ}.</text>',
        '<text x="34" y="738" class="note">The G, Uₓₓ, (G, Uₓₓ) and (Uₓₓ, Tr S) rows are unaffected.</text>',
        '<text x="34" y="766" class="note">The full three-coordinate decoder remains injective. Domain: M&gt;0, ρ&gt;0, Pe&gt;=0.</text>',
    ))
    return svg_document(
        "F-080 strict subsignature equivalence classes",
        "\n".join(body),
        height=820,
        width=1044,
        min_px=24,
        description="Irredundancy of the three-observable decoder: each proper projection of the signature collapses the seven reset masks into fewer classes, while the full signature separates all seven.",
    )


def _f080_points(values: tuple[tuple[float, float], ...], x: float, y: float, width: float, height: float, ymax: float) -> str:
    xmin, xmax = values[0][0], values[-1][0]
    return " ".join(
        f"{x + width * (value_x - xmin) / (xmax - xmin):.2f},{y + height * (1 - value_y / ymax):.2f}"
        for value_x, value_y in values
    )


def _f080_axes(body: list[str], x: float, y: float, width: float, height: float, xmin: float, xmax: float, ymax: float, xlabel: str, ylabel: str, *, ticks: int = 5) -> None:
    """Add a zero-based numeric axis with color-independent grid lines."""

    body.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#ffffff" stroke="#607d8b"/>')
    for index in range(ticks):
        fraction = index / (ticks - 1)
        tick_x = x + width * fraction
        tick_y = y + height * (1 - fraction)
        x_value = xmin + (xmax - xmin) * fraction
        y_value = ymax * fraction
        body.append(f'<line x1="{tick_x:.1f}" y1="{y + height}" x2="{tick_x:.1f}" y2="{y + height + 6}" stroke="#17202a"/>')
        x_label = f"{x_value:.2g}" if abs(x_value) < 10 else f"{x_value:.0f}"
        y_label = f"{y_value:.2g}" if abs(y_value) < 10 else f"{y_value:.0f}"
        body.append(f'<text x="{tick_x - 10:.1f}" y="{y + height + 23}" class="note" text-anchor="middle">{x_label}</text>')
        body.append(f'<line x1="{x - 6}" y1="{tick_y:.1f}" x2="{x}" y2="{tick_y:.1f}" stroke="#17202a"/>')
        body.append(f'<line x1="{x}" y1="{tick_y:.1f}" x2="{x + width}" y2="{tick_y:.1f}" stroke="#d5d8dc"/>')
        body.append(f'<text x="{x - 14}" y="{tick_y + 4:.1f}" class="note" text-anchor="end">{y_label}</text>')
    body.append(f'<text x="{x + width / 2 - 55:.1f}" y="{y + height + 47}" class="note">{xlabel}</text>')
    body.append(f'<text x="{x - 58}" y="{y + height / 2:.1f}" class="note" transform="rotate(-90 {x - 58} {y + height / 2})">{ylabel}</text>')


def f080_physics_series() -> dict[str, tuple[tuple[float, float], ...]]:
    """Evaluate accepted scalar formulas without a plotting/runtime dependency."""

    def internal(M: float, Pe: float, rho: float, velocity_reset: bool, orientation_reset: bool) -> tuple[float, float, float, float, float, float]:
        ux = rho / (rho + 1) if orientation_reset else 0.0
        uxx = (rho + 2) / (rho + 4) if orientation_reset else 0.5
        uyy = 2 / (rho + 4) if orientation_reset else 0.5
        velocity_decay = 1 + M * rho if velocity_reset else 1.0
        vx = Pe * ux / velocity_decay
        if orientation_reset and not velocity_reset:
            vu_xx = (Pe * uxx + M * rho * vx) / (1 + M * (1 + rho))
            vu_yy = Pe * uyy / (1 + M * (1 + rho))
        else:
            vu_decay = 1 + M * (1 + rho) if velocity_reset else 1 + M
            vu_xx, vu_yy = Pe * uxx / vu_decay, Pe * uyy / vu_decay
        vv_decay = 2 + M * rho if velocity_reset else 2.0
        vv_xx = (2 * Pe * vu_xx + 2 / M) / vv_decay
        vv_yy = (2 * Pe * vu_yy + 2 / M) / vv_decay
        return ux, vx, vu_xx, vu_yy, vv_xx, vv_yy

    def stationary_variance(M: float, Pe: float, rho: float, velocity_reset: bool, orientation_reset: bool) -> float:
        _, vx, vu_xx, vu_yy, vv_xx, vv_yy = internal(M, Pe, rho, velocity_reset, orientation_reset)
        ru_xx, ru_yy = vu_xx / (rho + 1), vu_yy / (rho + 1)
        rv_xx = (M * vv_xx + Pe * ru_xx) / (1 + M * rho)
        rv_yy = (M * vv_yy + Pe * ru_yy) / (1 + M * rho)
        return 2 * (rv_xx + rv_yy) / rho - (vx / rho) ** 2

    def transport(M: float, Pe: float, rho: float, velocity_reset: bool, orientation_reset: bool) -> tuple[float, float]:
        ux, vx, vu_xx, vu_yy, vv_xx, vv_yy = internal(M, Pe, rho, velocity_reset, orientation_reset)
        orientation_decay = 1 + rho if orientation_reset else 1.0
        velocity_decay = 1 + M * rho if velocity_reset else 1.0
        vu_cov_xx = vu_xx - vx * ux
        rv_xx = (M * (vv_xx - vx**2) + Pe * vu_cov_xx / orientation_decay) / velocity_decay
        rv_yy = (M * vv_yy + Pe * vu_yy / orientation_decay) / velocity_decay
        return (rv_xx + rv_yy) / 2, vx

    M, Pe = 2.0, 3.0
    # Keep every prior formula node, densify the drawing, and evaluate the
    # exact curve at each measured abscissa rather than interpolating there.
    rhos = tuple(sorted(
        {0.15 * index for index in range(1, 42)}
        | {0.15 * (index / 8) for index in range(8, 329)}
        | {0.15, 0.5, 1.5, 6.0}
    ))
    position = (("P", False, False), ("PV", True, False), ("PTheta", False, True), ("PVTheta", True, True))
    nonposition = (("V", True, False), ("Theta", False, True), ("VTheta", True, True))
    series: dict[str, tuple[tuple[float, float], ...]] = {}
    for name, velocity_reset, orientation_reset in position:
        series[f"variance_{name}"] = tuple((rho, stationary_variance(M, Pe, rho, velocity_reset, orientation_reset)) for rho in rhos)
    for name, velocity_reset, orientation_reset in nonposition:
        values = tuple((rho, *transport(M, Pe, rho, velocity_reset, orientation_reset)) for rho in rhos)
        series[f"diffusion_{name}"] = tuple((rho, diffusion) for rho, diffusion, _ in values)
        series[f"drift_{name}"] = tuple((rho, drift) for rho, _, drift in values)
    tuned_masses = tuple(sorted(
        {0.1 + index / 100 for index in range(51)}
        | {0.1 + index / 800 for index in range(401)}
        | {0.15, 0.35, 0.55}
    ))
    for name, velocity_reset, orientation_reset in (("V", True, False), ("Theta", False, True)):
        series[f"tuned_diffusion_{name}"] = tuple(
            (mass, transport(mass, math.sqrt(27 * mass * (mass + 6) * (3 * mass + 2) / (2 * (44 - 9 * mass - 80 * mass**2 - 12 * mass**3))), 0.5, velocity_reset, orientation_reset)[0])
            for mass in tuned_masses
        )
    series["tuned_theta_drift"] = tuple(
        (mass, transport(mass, math.sqrt(27 * mass * (mass + 6) * (3 * mass + 2) / (2 * (44 - 9 * mass - 80 * mass**2 - 12 * mass**3))), 0.5, False, True)[1])
        for mass in tuned_masses
    )
    return series


def f080_transport_consequences(points: list[dict] | None = None) -> str:
    """Four caption-led panels; optional S-074 symbols are actual estimates.

    Static journal figure contract: exact rate/mass curves plus independent
    trajectory estimates, with +/- one SE bars. Protocol identity uses color,
    dash and marker shape. Panel d has a shared full-width mass axis, diffusion
    on the left and drift on the right. No global title, subtitle or scope box.
    Rate axes are logarithmic in a-c; variance is logarithmic in a. Tick marks
    identify the sampled rates/masses. Positive log intervals are never clipped.
    Prior qualitative figures, formulas and existing curve nodes are unchanged;
    additional exact drawing nodes include every S-074 sampling abscissa.
    """
    import json
    from html import escape

    point_path = ROOT / "artifacts/derived/S-074-figure-points.json"
    symbol_estimator = "independent-trajectory"
    if points is None:
        points = []
        if point_path.exists():
            payload = json.loads(point_path.read_text(encoding="utf-8"))
            if (not isinstance(payload, dict)
                    or payload.get("schema") not in ("phasemap.s074.figure-points.v1", "phasemap.s074.richardson-figure-points.v1")
                    or not isinstance(payload.get("points"), list)
                    or len(payload["points"]) != 52
                    or not isinstance(payload.get("results_sha256"), str)
                    or len(payload["results_sha256"]) != 64):
                raise ValueError("invalid S-074 measured-symbol file; expected all 52 points")
            points = payload["points"]
            if payload["schema"] == "phasemap.s074.richardson-figure-points.v1":
                if (payload.get("estimator_identity") != "paired_first_order_richardson_post_result"
                        or payload.get("analysis_timing") != "post_result_after_observing_finest_step_bias"
                        or not isinstance(payload.get("source_results_sha256"), str)
                        or len(payload["source_results_sha256"]) != 64
                        or any(p.get("post_result") is not True for p in points)):
                    raise ValueError("invalid S-074 measured-symbol post-result provenance")
                symbol_estimator = "post-result paired Richardson independent-trajectory"
            if len({(p.get("case_id"), p.get("series")) for p in points}) != 52:
                raise ValueError("duplicate S-074 measured-symbol identity")
    data = f080_physics_series()
    data["tuned_drift_V"] = tuple((mass, 0.0) for mass, _ in data["tuned_theta_drift"])
    colors = {"P": "#0072B2", "PV": "#D55E00", "PTheta": "#009E73",
              "PVTheta": "#CC79A7", "V": "#0072B2", "Theta": "#D55E00", "VTheta": "#009E73"}
    labels = {"P": "P", "PV": "PV", "PTheta": "PΘ", "PVTheta": "PVΘ",
              "V": "V", "Theta": "Θ", "VTheta": "VΘ"}
    dashes = {"P": "", "PV": "9 5", "PTheta": "2 5", "PVTheta": "9 4 2 4",
              "V": "", "Theta": "9 5", "VTheta": "2 5"}
    order = ("P", "PV", "PTheta", "PVTheta")
    transport = ("V", "Theta", "VTheta")
    for point in points:
        if point.get("series") not in data:
            raise ValueError("unknown S-074 figure series")
        if any(not math.isfinite(float(point[name])) for name in ("x", "estimate", "se", "n")):
            raise ValueError("nonfinite S-074 figure point")
        if point["se"] < 0 or point["n"] < 3:
            raise ValueError("invalid S-074 uncertainty or sample count")
        domain = data[point["series"]]
        if not domain[0][0] <= point["x"] <= domain[-1][0]:
            raise ValueError("S-074 point outside its declared curve domain")
    body: list[str] = []
    panels = {
        "a": (100, 65, 410, 320, [f"variance_{p}" for p in order], "ρ", "Tr Cov(r)", False),
        "b": (665, 65, 410, 320, [f"diffusion_{p}" for p in transport], "ρ", 'D<tspan baseline-shift="sub" font-size="75%">eff</tspan>', False),
        "c": (100, 580, 410, 320, [f"drift_{p}" for p in transport], "ρ", "⟨vₓ⟩", True),
        "d": (665, 580, 410, 320, ["tuned_diffusion_V", "tuned_diffusion_Theta"], "M", 'D<tspan baseline-shift="sub" font-size="75%">eff</tspan>', False),
        "d-right": (665, 580, 410, 320, ["tuned_drift_V", "tuned_theta_drift"], "M", "⟨vₓ⟩", True),
    }
    transforms = {}
    for panel, (x, y, w, h, series, xlabel, ylabel, signed) in panels.items():
        values = [v for name in series for _, v in data[name]]
        observed = [p for p in points if p["series"] in series]
        values += [float(p["estimate"]) + float(p["se"]) for p in observed]
        ymax = max(values) * 1.08
        ymin = min([0.0] + [float(p["estimate"]) - float(p["se"]) for p in observed])
        logx, logy = panel in ("a", "b", "c"), panel == "a"
        if logy:
            lower = min(values + [float(p["estimate"]) - float(p["se"]) for p in observed])
            if lower <= 0:
                raise ValueError("nonpositive variance interval cannot be shown on a log axis")
            ymin = lower / 1.08
        if signed:
            ymin = min(ymin * 1.2, -0.035 * ymax)
        xmin, xmax = data[series[0]][0][0], data[series[0]][-1][0]
        def xy(a, b, x=x, y=y, w=w, h=h, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, logx=logx, logy=logy):
            fx = math.log(a / xmin) / math.log(xmax / xmin) if logx else (a-xmin)/(xmax-xmin)
            fy = math.log(b / ymin) / math.log(ymax / ymin) if logy else (b-ymin)/(ymax-ymin)
            return x+w*fx, y+h*(1-fy)
        for name in series:
            transforms[name] = xy
        if panel == "d-right":
            body.append('<g id="panel-d-right-axis">')
            body.append(f'<line x1="{x+w}" y1="{y}" x2="{x+w}" y2="{y+h}" stroke="#17202a"/>')
            for tick in range(5):
                val = ymax*tick/4
                _, yy = xy(xmin, val)
                body.append(f'<line x1="{x+w}" y1="{yy:.2f}" x2="{x+w+6}" y2="{yy:.2f}" stroke="#17202a"/>')
                body.append(f'<text x="{x+w+12}" y="{yy+7:.2f}" class="note">{val:.2g}</text>')
            body.append(f'<text x="{x+w+93}" y="{y+h/2}" text-anchor="middle" class="note" transform="rotate(-90 {x+w+93} {y+h/2})">{ylabel}</text></g>')
        else:
            body.append(f'<rect class="numeric-panel" data-panel="{panel}" data-xscale="{"log" if logx else "linear"}" data-yscale="{"log" if logy else "linear"}" data-xmin="{xmin}" data-xmax="{xmax}" data-ymin="{ymin}" data-ymax="{ymax}" x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="#607d8b"/>')
            yvalues = ([10.0**power for power in range(math.ceil(math.log10(ymin)), math.floor(math.log10(ymax))+1)]
                       if logy else [ymax*tick/4 for tick in range(5)])
            for yv in yvalues:
                _, yy = xy(xmin, yv)
                body.append(f'<line x1="{x}" y1="{yy:.2f}" x2="{x+w}" y2="{yy:.2f}" stroke="#e1e3e5"/>')
                y_label = f"{yv:.0f}" if abs(yv) >= 10 else f"{yv:.2g}"
                body.append(f'<text x="{x-12}" y="{yy+7:.2f}" text-anchor="end" class="note">{y_label}</text>')
            xvalues = (0.15, 0.5, 1.5, 6.0) if logx else (0.15, 0.35, 0.55)
            for xv in xvalues:
                xx, _ = xy(xv, ymin)
                body.append(f'<line x1="{xx:.2f}" y1="{y+h}" x2="{xx:.2f}" y2="{y+h+6}" stroke="#17202a"/>')
                body.append(f'<text data-panel="{panel}" data-axis="x" data-value="{xv}" x="{xx:.2f}" y="{y+h+29}" text-anchor="middle" class="note">{xv:.2g}</text>')
            body.append(f'<text x="{x+w/2}" y="{y+h+63}" text-anchor="middle" class="label">{xlabel}</text>')
            body.append(f'<text x="{x-66}" y="{y+h/2}" text-anchor="middle" class="note" transform="rotate(-90 {x-66} {y+h/2})">{ylabel}</text>')
            body.append(f'<text x="{x-34}" y="{y-27}" class="head">({panel})</text>')
        for name in series:
            protocol = "Theta" if name == "tuned_theta_drift" else name.rsplit("_", 1)[1]
            dash = "2 5" if name.startswith("tuned_") and "drift" in name else dashes[protocol]
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            curve = " ".join(f"{a:.2f},{b:.2f}" for a, b in (xy(u, v) for u, v in data[name]))
            body.append(f'<polyline data-series="{name}" points="{curve}" fill="none" stroke="{colors[protocol]}" stroke-width="3"{dash_attr}/>')
    def marker_shape(protocol, xx, yy):
        if protocol in ("P", "V"):
            return f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="5"/>'
        if protocol in ("PV", "Theta"):
            return f'<rect x="{xx-5:.2f}" y="{yy-5:.2f}" width="10" height="10"/>'
        if protocol in ("PTheta", "VTheta"):
            return f'<path d="M {xx:.2f},{yy-6:.2f} L {xx+6:.2f},{yy+5:.2f} L {xx-6:.2f},{yy+5:.2f} Z"/>'
        return f'<path d="M {xx:.2f},{yy-6:.2f} L {xx+6:.2f},{yy:.2f} L {xx:.2f},{yy+6:.2f} L {xx-6:.2f},{yy:.2f} Z"/>'

    for point in points:
        name = point["series"]
        protocol = "Theta" if name == "tuned_theta_drift" else name.rsplit("_", 1)[1]
        color = colors[protocol]
        xy = transforms[name]
        xx, yy = xy(point["x"], point["estimate"])
        _, low = xy(point["x"], point["estimate"] - point["se"])
        _, high = xy(point["x"], point["estimate"] + point["se"])
        body.append(f'<g data-case="{escape(str(point["case_id"]), quote=True)}" data-series="{name}" data-estimate="{point["estimate"]}" data-se="{point["se"]}" data-n="{point["n"]}" stroke="{color}" stroke-width="2" fill="none">')
        body.append(f'<line x1="{xx:.2f}" y1="{low:.2f}" x2="{xx:.2f}" y2="{high:.2f}"/>')
        for cap in (low, high):
            body.append(f'<line x1="{xx-4:.2f}" y1="{cap:.2f}" x2="{xx+4:.2f}" y2="{cap:.2f}"/>')
        body.append(marker_shape(protocol, xx, yy))
        body.append('</g>')
    def legend(keys, x, y, spacing):
        for index, key in enumerate(keys):
            xx = x + spacing*index
            dash = f' stroke-dasharray="{dashes[key]}"' if dashes[key] else ""
            body.append(f'<line x1="{xx}" y1="{y-7}" x2="{xx+30}" y2="{y-7}" stroke="{colors[key]}" stroke-width="3"{dash}/><text x="{xx+39}" y="{y}" class="note">{labels[key]}</text>')
            if points:
                body.append(f'<g class="protocol-legend-marker" data-protocol="{key}" stroke="{colors[key]}" stroke-width="2" fill="none">{marker_shape(key, xx+15, y-7)}</g>')
    legend(order, 100, 492, 107)
    legend(transport, 685, 492, 125)
    legend(transport, 120, 1006, 125)
    legend(("V", "Theta"), 705, 1006, 130)
    return svg_document(
        "Transport and localization", "\n".join(body), height=1040, min_px=24,
        description=f"Localized protocols: centered variance; D_eff (dimensionless); mean drift ⟨vₓ⟩ (dimensionless); tuned V-Theta diffusion coincidence with separate mean drift. Logarithmic rate axes in a-c and logarithmic variance in a; sampled rates and masses are labeled. Curves are exact. Symbols, when present, are S-074 {symbol_estimator} estimates with one-standard-error bars. Parameters and scientific scope are in the caption."
    )


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


def validate_f080_inputs() -> None:
    theorem, s071, s073 = (path.read_text(encoding="utf-8") for path in F080_INPUTS)
    requirements = (
        (theorem, "is injective on"),
        (theorem, "stationary/localized"),
        (theorem, "strictly diffusive"),
        (theorem, "A-B="),
        (theorem, "C-B="),
        (theorem, "Complete strict-subsignature map"),
        (s071, "classification `unresolved`"),
        (s073, "aggregate classification `unresolved`"),
        (s073, "every gating item to validate"),
    )
    missing = [needle for text, needle in requirements if needle not in text]
    if missing:
        raise ValueError(f"F-080 accepted input validation failed: {missing}")


def expected_outputs() -> dict[Path, str]:
    validate_inputs()
    validate_f070_inputs()
    validate_f080_inputs()
    structural = FIGURES / "F-050-all-seven-structural-map.svg"
    coverage = FIGURES / "F-050-s021-validation-coverage.svg"
    f050_outputs = {structural: structural_map(), coverage: validation_coverage()}
    f070_outputs = {
        FIGURES / "F-070-reset-lattice-and-classifier.svg": f070_reset_lattice(),
        FIGURES / "F-070-physical-transport-and-degeneracies.svg": f070_physical_transport(),
        FIGURES / "F-070-qualitative-trajectory-evidence.svg": f070_qualitative_trajectory(),
    }
    f080_outputs = {
        FIGURES / "F-080-three-coordinate-decoder.svg": f080_three_coordinate_decoder(),
        FIGURES / "F-080-strict-subsignature-classes.svg": f080_strict_subsignatures(),
        FIGURES / "F-080-transport-localization.svg": f080_transport_consequences(),
    }
    outputs = {**f050_outputs, **f070_outputs, **f080_outputs}
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
    f080_source_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{canonical_text_sha256(path)}` |"
        for path in F080_INPUTS
    )
    s074_points = ROOT / "artifacts/derived/S-074-figure-points.json"
    s074_source = (
        f"S-074 measured-symbol source: `{s074_points.relative_to(ROOT).as_posix()}`; "
        f"canonical-LF SHA-256 `{canonical_text_sha256(s074_points)}`."
        if s074_points.exists() else
        "S-074 measured symbols are not yet available; this intermediate rendering contains theory curves only."
    )
    if s074_points.exists():
        import json
        point_metadata = json.loads(s074_points.read_text(encoding="utf-8"))
        if point_metadata.get("schema") == "phasemap.s074.richardson-figure-points.v1":
            s074_source += (
                "\nThe displayed estimator is the explicitly post-result paired Richardson "
                "reanalysis, adopted after observing finest-step bias. "
                f"Reanalysis results SHA-256 `{point_metadata['results_sha256']}`; "
                f"immutable raw-primary results SHA-256 `{point_metadata['source_results_sha256']}`. "
                "Both original stricter planning-SE misses remain disclosed."
            )
    f080_figure_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | `{hashlib.sha256(content.encode()).hexdigest()}` |"
        for path, content in f080_outputs.items()
    )
    outputs[F080_MANIFEST] = f"""# F-080 observability figure manifest

**Task result:** reproducible exact-theory curves and source-bound measured symbols when available
**Generation command:** `python src/phasemap/analysis/generate_final_figures.py`
**Verification command:** `python src/phasemap/analysis/generate_final_figures.py --check`

## Accepted immutable inputs

| Source | Canonical-LF SHA-256 |
|---|---|
{f080_source_rows}

| Generator | Canonical-LF SHA-256 |
|---|---|
| `src/phasemap/analysis/generate_final_figures.py` | `{canonical_text_sha256(Path(__file__))}` |

## Generated panels

| Figure | SHA-256 |
|---|---|
{f080_figure_rows}

## Claim scope

| Figure | Allowed claim and boundary |
|---|---|
| `F-080-three-coordinate-decoder.svg` | Exact matched-parameter injectivity of `(G, Uxx, Tr S)` on the seven nonempty reset maps for `M>0`, `Pe>=0`, `rho>0`. It is not a finite-time, noisy, cross-parameter, or global-minimality claim. |
| `F-080-strict-subsignature-classes.svg` | Exact equality classes of proper observable projections. These are not protocol, full-record, or process equivalences. The passive/resonant `Tr S` degeneracy does not defeat the full decoder. |
| `F-080-transport-localization.svg` | Exact stationary centered-variance curves for localized protocols, plus exact `D_eff` and mean-drift curves for non-position protocols. The tuned `V`/`Theta` diffusion coincidence is broken by mean drift. S-074 symbols, when available, are measured estimates with one-standard-error bars, not sampled theory values. |

S-071 and S-073 are immutable, unresolved quantitative trajectory attempts;
they are provenance-only and are not represented in any visible panel. They
are not pooled with the separately authorized S-074 precision study.
{s074_source}
The S-074 pointwise precision and agreement results are reported in its study
record; symbols do not imply simultaneous coverage or parameter inference.
Every measured abscissa is an exact theory-curve node. The drawing grid is
densified while preserving all earlier formula nodes and their exact values;
no measured estimate or uncertainty is moved to improve visual agreement.
Every SVG has accessible title/description metadata and color-independent
labels. The paper's transport figure has no visible global title, subtitle,
or scope box; parameters and scope belong to its caption. Panel d uses a
shared mass axis, diffusion on the left and drift on the right. Negative
measured drift and its uncertainty are retained rather than clipped to zero.
Rate axes in panels a-c and the variance axis in a are logarithmic; sampled
rates and masses are labeled explicitly without changing the theory arrays.
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
        print("PASS: F-050 figures; F-070 figures; and F-080 figures and provenance manifests are reproducible.")
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print("PASS: regenerated F-050 figures; F-070 figures; and F-080 figures and provenance manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
