from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "manuscript" / "PHASEMAP_MANUSCRIPT.md"
SUPPLEMENT = ROOT / "manuscript" / "PHASEMAP_TECHNICAL_SUPPLEMENT.md"
CLAIM_MAP = ROOT / "manuscript" / "CLAIM_EVIDENCE_MAP.md"
JOURNAL_MAIN = ROOT / "manuscript" / "journal" / "PHASEMAP_MANUSCRIPT.tex"
JOURNAL_BODY = ROOT / "manuscript" / "journal" / "PHASEMAP_MANUSCRIPT_body.tex"
JOURNAL_SUPPLEMENT = (
    ROOT / "manuscript" / "journal" / "PHASEMAP_TECHNICAL_SUPPLEMENT_body.tex"
)
def test_main_article_leads_with_physics_and_preserves_scope() -> None:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    for required in (
        # physics-led framing
        "Coordinate-selective resetting",
        "localization switch",
        "sector invariance",
        "Information loss under restricted observation",
        # exact decoder content
        r"\Sigma(q)=(G(q),U_{xx}(q),\operatorname{Tr}S(q))",
        r"M>0",
        r"\rho>0",
        r"\mathrm{Pe}\ge0",
        "exactly decodes all seven protocols",
        "diffusive",
        # scope stays explicit, stated once in ordinary prose
        "matched parameters",
        "does not exclude a different two-observable family",
        "F-080-transport-localization.svg",
    ):
        assert required in text


def test_main_article_reads_as_physics_not_project_documentation() -> None:
    for path in (MANUSCRIPT, JOURNAL_BODY):
        text = path.read_text(encoding="utf-8")
        for banned in (
            "S-071",
            "S-073",
            "T-080",
            "predeclared",
            "fail-closed",
            "scope-labeled",
            "validation registry",
            "validation gate",
            "provisional novelty",
        ):
            assert banned not in text, f"{path.name} contains {banned!r}"


def test_trajectory_attempts_remain_quantitatively_unresolved() -> None:
    for path in (SUPPLEMENT, JOURNAL_SUPPLEMENT):
        # collapse hard wrapping so phrase checks are layout-independent
        text = " ".join(path.read_text(encoding="utf-8").split())
        for required in (
            # the counts and the zero-contradiction fact stay on the record
            "S-071 validated 14 of 46",
            "left 32 unresolved",
            "S-073 validated 32 of 46",
            "left 14 unresolved",
            "had 0 contradicted",
            # the article must draw no quantitative conclusion from either study
            "Neither study supports a quantitative trajectory-validation claim",
            # An unresolved interval cannot establish absence of discrepancy.
            r"q\,\mathrm{SE}\leq0.5\epsilon",
            r"q\,\mathrm{SE}+B\leq0.75\epsilon",
            "All 14 S-073 unresolved rows missed at least one precision requirement",
            "seven also failed containment",
        ):
            assert required in text, f"{path.name} lacks {required!r}"
        assert "not disagreement" not in text
        assert "65 equally spaced records" in text
        for window in ('[T/2,T]', '[2T/3,T]', '[3T/4,T]'):
            assert window in text
        for internal_language in ("each exactly once", "gating item", "all-or-nothing", "is authorized"):
            assert internal_language not in text
    for path in (MANUSCRIPT, JOURNAL_BODY, SUPPLEMENT, JOURNAL_SUPPLEMENT):
        text = " ".join(path.read_text(encoding="utf-8").split()).lower()
        for forbidden in (
            "quantitatively validated all seven",
            "trajectory validation confirms",
            "simulations confirm",
        ):
            assert forbidden not in text, f"{path.name} overclaims: {forbidden!r}"


def test_technical_supplement_is_self_contained_for_theorem_review() -> None:
    text = SUPPLEMENT.read_text(encoding="utf-8")
    for required in (
        "three-branch argument",
        "28-coordinate",
        "redundant moment frame",
        r"\operatorname{Tr}U=U_{xx}+U_{yy}=1",
        "physical invariant manifold",
        "no unrestricted ambient-space",
        "backward generator",
        "moment hierarchy",
        "21-pair",
        "12 + 6 + 3",
        "Physical baselines and limiting regimes",
        "transient path-space topology",
    ):
        assert required.lower() in text.lower()
    for frame_name in (
        "one", "r_x", "r_y", "v_x", "v_y", "u_x", "u_y",
        "rr_xx", "rr_xy", "rr_yy", "vv_xx", "vv_xy", "vv_yy",
        "rv_xx", "rv_xy", "rv_yx", "rv_yy", "ru_xx", "ru_xy",
        "ru_yx", "ru_yy", "vu_xx", "vu_xy", "vu_yx", "vu_yy",
        "uu_xx", "uu_xy", "uu_yy",
    ):
        assert frame_name in text
    assert r"0<M<M_\star" in text
    assert r"44-9M-80M^2-12M^3=0" in text
    assert r"2\operatorname{Tr}(U)I-4U" in text


def test_journal_sources_are_complete_publication_facing_and_clean() -> None:
    main = JOURNAL_MAIN.read_text(encoding="utf-8")
    body = JOURNAL_BODY.read_text(encoding="utf-8")
    supplement = JOURNAL_SUPPLEMENT.read_text(encoding="utf-8")
    assert "F-080-transport-localization.pdf" in body
    assert body.count(r"\begin{table}") == 2
    # scholarly bibliography: canonical resetting and active-matter anchors
    # plus the direct protocol-level prior art, each with stable metadata
    for citation in (
        "doi:10.1103/PhysRevLett.106.160601",
        "doi:10.1088/1751-8121/ab7cfe",
        "doi:10.1103/RevModPhys.88.045006",
        "doi:10.1063/1.5134455",
        "doi:10.1103/PhysRevE.102.052129",
        "doi:10.1103/xvkg-qcjq",
        "doi:10.1088/1742-5468/ab054a",
        "doi:10.1088/1361-648X/ada336",
    ):
        assert citation in main
    assert main.count("\\bibitem") >= 20
    assert "T-080" not in body + supplement
    assert "repository traceability" not in (body + supplement).lower()
    assert "Centered covariance, rather than raw mean-squared displacement" in body
    for text in (main, body, supplement):
        assert "�" not in text
        assert not any(ord(character) < 32 and character not in "\n\r\t" for character in text)


def test_claim_map_binds_each_publication_claim_to_accepted_evidence() -> None:
    claim_map = CLAIM_MAP.read_text(encoding="utf-8")
    for required in (
        "T-080-exact-observability-theorem.md",
        "F-080-observability-figure-manifest.md",
        "PHASEMAP_TECHNICAL_SUPPLEMENT.md",
        "S-021-validation-matrix.md",
        "S-071-trajectory-validation.md",
        "S-073-trajectory-replacement-validation.md",
        "S-071: 14/46 validated, 32 unresolved, 0 contradicted",
        "S-073: 32/46 validated, 14 unresolved, 0 contradicted",
        "No quantitative trajectory-validation claim",
    ):
        assert required in claim_map
