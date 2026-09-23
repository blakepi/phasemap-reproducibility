from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_r6b_reporting_preserves_raw_and_richardson_qualification() -> None:
    """Editorial sources disclose raw outcomes without relabelling them as Richardson results."""
    required = (
        "80/80 intervals, with 0 contradicted and 78/80 meeting the stricter target",
        "kinetic-trace convergence ratios were 1.999--2.006",
        "Richardson did not rescue containment",
        "does not establish its cause",
    )
    for relative in (
        "manuscript/PHASEMAP_TECHNICAL_SUPPLEMENT.md",
        "manuscript/journal/PHASEMAP_TECHNICAL_SUPPLEMENT_body.tex",
        "manuscript/journal/fnl/PHASEMAP_FNL_Supplement_body.tex",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for phrase in required:
            assert phrase in text


def test_r6b_journal_caption_discloses_raw_outcomes_only_for_journal_rendering() -> None:
    renderer = (ROOT / "scripts/render_s074_publication.py").read_text(encoding="utf-8")
    assert 'Raw-finest analysis contained 80/80 intervals, with 0 contradicted and 78/80 meeting the stricter target' in renderer
    assert 'presentation: str = "archive"' in renderer
