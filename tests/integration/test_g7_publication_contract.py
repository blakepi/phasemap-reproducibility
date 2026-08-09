from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "manuscript" / "PHASEMAP_MANUSCRIPT.md"
SUPPLEMENT = ROOT / "manuscript" / "PHASEMAP_TECHNICAL_SUPPLEMENT.md"
STRUCTURAL_FIGURE = ROOT / "figures" / "F-050-all-seven-structural-map.svg"
FIGURE_GENERATOR = ROOT / "src" / "phasemap" / "analysis" / "generate_final_figures.py"


def test_manuscript_defines_temporal_record_and_restricted_identity_scopes():
    text = MANUSCRIPT.read_text(encoding="utf-8")
    required = (
        r"\mathcal R_2(q;M,\mathrm{Pe},\rho)",
        "fixed temporal meaning",
        "stationary long-time limits",
        "long-time polynomial record",
        r"\mathrm{TrS}:=\operatorname{Tr}S",
        r"\mathrm{TrC}:=\operatorname{Tr}C",
        r"\mathrm{TrR}:=\operatorname{Tr}R",
        r"\rho=\frac12",
        r"0<M<M_\star",
        r"44-9M-80M^2-12M^3=0",
        "S-021 did not sample this tuned curve",
        "a transient path-space topology",
        "the reverse order, or a joint reset-rate limit",
    )
    for needle in required:
        assert needle in text
    assert "named scalar triple" not in text
    assert "A tuned analytic curve can equalize" not in text


def test_structural_figure_shows_exact_witness_partition_and_contraction_scope():
    figure = STRUCTURAL_FIGURE.read_text(encoding="utf-8")
    generator = FIGURE_GENERATOR.read_text(encoding="utf-8")
    for text in (figure, generator):
        assert "12 + 6 + 3 = 21 pairs" in text
        assert "12 pairs: different P status" in text
        assert "6 pairs: same P, different Theta" in text
        assert "3 pairs: same P and Theta" in text
        assert "Tr(S)=E|v|^2" in text
        assert "For Pe&gt;0 their centered spatial traces differ" in text
        assert "equal speed" not in text


def test_technical_supplement_is_self_contained_for_theorem_review():
    text = SUPPLEMENT.read_text(encoding="utf-8")
    required_sections = (
        "28-coordinate",
        "redundant moment frame",
        r"\operatorname{Tr}U=U_{xx}+U_{yy}=1",
        "physical invariant manifold",
        "no unrestricted ambient-space",
        "backward generator",
        "moment hierarchy",
        "21-pair",
        "12 + 6 + 3",
        "mandatory limits",
    )
    for needle in required_sections:
        assert needle.lower() in text.lower()
    for frame_name in (
        "one",
        "r_x",
        "r_y",
        "v_x",
        "v_y",
        "u_x",
        "u_y",
        "rr_xx",
        "rr_xy",
        "rr_yy",
        "vv_xx",
        "vv_xy",
        "vv_yy",
        "rv_xx",
        "rv_xy",
        "rv_yx",
        "rv_yy",
        "ru_xx",
        "ru_xy",
        "ru_yx",
        "ru_yy",
        "vu_xx",
        "vu_xy",
        "vu_yx",
        "vu_yy",
        "uu_xx",
        "uu_xy",
        "uu_yy",
    ):
        assert frame_name in text
    for pair in (
        "P/PV",
        r"P\Theta/PV\Theta",
        r"\Theta/V\Theta",
    ):
        assert pair in text
    assert r"0<M<M_\star" in text
    assert r"44-9M-80M^2-12M^3=0" in text
    assert r"2\operatorname{Tr}(U)I-4U" in text
    assert r"M=\rho=1\) and \(\mathrm{Pe}=6/5" in text
    assert r"D_\Theta=D_{V\Theta}\longrightarrow" not in text
    assert "finite-\\(M\\) stationary position moments" in text
    assert "transient path-space topology" in text
    assert "Ordered 28-state basis" not in text
    assert "three independent\ncomponents" not in text


def test_claim_map_links_the_technical_supplement():
    claim_map = (ROOT / "manuscript" / "CLAIM_EVIDENCE_MAP.md").read_text(
        encoding="utf-8"
    )
    assert "PHASEMAP_TECHNICAL_SUPPLEMENT.md" in claim_map
