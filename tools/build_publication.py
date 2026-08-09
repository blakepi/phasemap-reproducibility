"""Build journal-facing LaTeX and PDF sources from the locked Markdown files."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript" / "PHASEMAP_MANUSCRIPT.md"
SUPPLEMENT = ROOT / "manuscript" / "PHASEMAP_TECHNICAL_SUPPLEMENT.md"
OUT = ROOT / "manuscript" / "journal"
FIGURES = OUT / "figures"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=OUT)


def extract_main(text: str, doi: str) -> tuple[str, str, str]:
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("manuscript title heading not found")
    title = lines[0][2:].strip()
    try:
        abstract_at = lines.index("## Abstract")
        intro_at = lines.index("## Introduction")
    except ValueError as exc:
        raise ValueError("abstract or introduction heading not found") from exc
    abstract = "\n".join(lines[abstract_at + 1 : intro_at]).strip()
    body = "\n".join(lines[intro_at:]).strip() + "\n"

    repository = "https://github.com/blakepi/phasemap-reproducibility"
    archive = (
        f"[doi:{doi}](https://doi.org/{doi})"
        if doi
        else "DOI TO BE INSERTED AFTER ZENODO RESERVATION"
    )
    data_section = (
        "## Data and code availability\n\n"
        "The code, prespecified plans, deterministic validation records, both "
        "unresolved trajectory-attempt records, raw numerical outputs, figure "
        "sources, and manuscript sources are openly available in the PHASEMAP "
        f"reproducibility archive ({archive}) and at "
        f"[{repository}]({repository}). The archived release is the version of "
        "record for the research materials.\n\n"
    )
    body = re.sub(
        r"## Data and code availability\n.*?(?=\n## References\n)",
        data_section.rstrip(),
        body,
        flags=re.DOTALL,
    )

    declarations = """
## Author contributions

G. Blake Pierpoint: Conceptualization, Methodology, Formal analysis,
Investigation, Project administration, Software, Visualization, Writing -
original draft, and Writing - review and editing. Olivier Bernard:
Methodology, Formal analysis, Validation, and Writing - review and editing.
Yichen Liu: Software, Methodology, Formal analysis, Validation, and Writing -
review and editing.

## Funding

The authors received no specific funding for this work.

## Competing interests

The authors declare no competing interests.

## Ethics statement

This theoretical and computational study involved no human participants,
animals, identifiable personal data, or clinical intervention; institutional
ethics approval was not applicable.

## Use of AI-assisted tools

OpenAI Codex was used to assist with software development, deterministic
consistency checks, document preparation, and language editing. The authors
reviewed the resulting code, analyses, and text and take responsibility for
the content of the work.
""".strip()
    body = body.replace("\n## References\n", f"\n\n{declarations}\n\n## References\n")
    body = body.replace("../figures/", "figures/").replace(".svg)", ".png)")
    body = body.replace(
        "../docs/scientific-contract/CONTRACT.md",
        f"{repository}/blob/v3.1.1/docs/scientific-contract/CONTRACT.md",
    )
    body = body.replace("../artifacts/", f"{repository}/blob/v3.1.1/artifacts/")
    body = body.replace("../src/", f"{repository}/blob/v3.1.1/src/")
    body = body.replace("../docs/briefs/", f"{repository}/blob/v3.1.1/literature-audit/")
    body = body.replace(
        "PHASEMAP_TECHNICAL_SUPPLEMENT.md",
        "PHASEMAP_TECHNICAL_SUPPLEMENT.pdf",
    )
    return title, abstract, body


def convert_markdown(markdown: str, output: Path) -> None:
    source = output.with_suffix(".build.md")
    source.write_text(markdown, encoding="utf-8", newline="\n")
    run(
        [
            "pandoc",
            str(source),
            "--from=markdown+tex_math_single_backslash+pipe_tables+raw_tex",
            "--to=latex",
            "--shift-heading-level-by=-1",
            "--syntax-highlighting=none",
            "--wrap=none",
            "--output",
            str(output),
        ]
    )


def preamble() -> str:
    return r"""\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,bm}
\usepackage{graphicx}
\usepackage{booktabs,longtable,array,calc}
\usepackage[margin=1in]{geometry}
\usepackage{authblk}
\usepackage{etoolbox}
\usepackage{xurl}
\usepackage[colorlinks=true,allcolors=blue]{hyperref}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{\resizebox{\linewidth}{!}{#1}}
\newcounter{none}
\AtBeginEnvironment{longtable}{\footnotesize\setlength{\tabcolsep}{3pt}}
\setlength{\LTpre}{4pt}
\setlength{\LTpost}{8pt}
\renewcommand{\arraystretch}{1.12}
"""


def main_tex(title: str, abstract: str) -> str:
    return rf"""\documentclass[12pt]{{article}}
{preamble()}
\begin{{document}}
\title{{{title}}}
\author[1]{{G. Blake Pierpoint\thanks{{Corresponding author: \href{{mailto:gpierpo1@jh.edu}}{{gpierpo1@jh.edu}}; ORCID: \href{{https://orcid.org/0000-0001-8288-8549}}{{0000-0001-8288-8549}}}}}}
\author[2,3]{{Olivier Bernard\thanks{{ORCID: \href{{https://orcid.org/0009-0007-0177-1607}}{{0009-0007-0177-1607}}}}}}
\author[4,3]{{Yichen Liu\thanks{{ORCID: \href{{https://orcid.org/0009-0005-2367-1493}}{{0009-0005-2367-1493}}}}}}
\affil[1]{{Department of Biomedical Engineering, Whiting School of Engineering, Johns Hopkins University, 3400 North Charles Street, Baltimore, Maryland 21218, USA}}
\affil[2]{{UFR PhITEM (Physics, Engineering, Earth, Environment, Mechanics), Universit\'e Grenoble Alpes, 230 rue de la Physique, 38400 Saint-Martin-d'H\`eres, France}}
\affil[3]{{Weyl Center for Mathematical Physics, 1235 Pennsylvania Avenue SE, Unit 1294, Washington, DC 20003, USA}}
\affil[4]{{Department of Computer Science and Engineering, Shanghai Jiao Tong University, 800 Dongchuan Road, Shanghai 200240, China}}
\date{{August 8, 2026}}
\maketitle
\begin{{abstract}}
{abstract}
\end{{abstract}}
\noindent\textbf{{Keywords:}} stochastic resetting; active Brownian particle; inertial active matter; moment closure; statistical physics
\input{{PHASEMAP_MANUSCRIPT_body.tex}}
\end{{document}}
"""


def supplement_tex() -> str:
    return rf"""\documentclass[12pt]{{article}}
{preamble()}
\begin{{document}}
\title{{Supplemental Material for ``Exact classification of moments through second order for deterministic reset maps of an inertial active particle''}}
\author[1]{{G. Blake Pierpoint\thanks{{Corresponding author: \href{{mailto:gpierpo1@jh.edu}}{{gpierpo1@jh.edu}}}}}}
\author[2,3]{{Olivier Bernard}}
\author[4,3]{{Yichen Liu}}
\affil[1]{{Department of Biomedical Engineering, Whiting School of Engineering, Johns Hopkins University, 3400 North Charles Street, Baltimore, Maryland 21218, USA}}
\affil[2]{{UFR PhITEM, Universit\'e Grenoble Alpes, 230 rue de la Physique, 38400 Saint-Martin-d'H\`eres, France}}
\affil[3]{{Weyl Center for Mathematical Physics, 1235 Pennsylvania Avenue SE, Unit 1294, Washington, DC 20003, USA}}
\affil[4]{{Department of Computer Science and Engineering, Shanghai Jiao Tong University, 800 Dongchuan Road, Shanghai 200240, China}}
\date{{August 8, 2026}}
\maketitle
\input{{PHASEMAP_TECHNICAL_SUPPLEMENT_body.tex}}
\end{{document}}
"""


def build(doi: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome.exists():
        raise FileNotFoundError("Google Chrome is required to render the SVG figures")
    for svg in sorted((ROOT / "figures").glob("*.svg")):
        root = ET.parse(svg).getroot()
        width = int(float(root.attrib.get("width", "1200").replace("px", "")))
        height = int(float(root.attrib.get("height", "900").replace("px", "")))
        png = FIGURES / f"{svg.stem}.png"
        subprocess.run(
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=2",
                f"--window-size={width},{height}",
                f"--screenshot={png}",
                svg.resolve().as_uri(),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    title, abstract, body = extract_main(MANUSCRIPT.read_text(encoding="utf-8"), doi)
    convert_markdown(body, OUT / "PHASEMAP_MANUSCRIPT_body.tex")
    supplement = SUPPLEMENT.read_text(encoding="utf-8")
    supplement = "\n".join(supplement.splitlines()[1:]).strip() + "\n"
    supplement = supplement.replace(
        r"\(P/V,\ P/\Theta,\ P/V\Theta;\ PV/V,\ PV/\Theta,\ PV/V\Theta;\ P\Theta/V,\ P\Theta/\Theta,\ P\Theta/V\Theta;\ PV\Theta/V,\ PV\Theta/\Theta,\ PV\Theta/V\Theta\)",
        r"\(P/V\), \(P/\Theta\), \(P/V\Theta\); \(PV/V\), \(PV/\Theta\), \(PV/V\Theta\); \(P\Theta/V\), \(P\Theta/\Theta\), \(P\Theta/V\Theta\); \(PV\Theta/V\), \(PV\Theta/\Theta\), \(PV\Theta/V\Theta\)",
    )
    supplement = supplement.replace(
        r"\(P/P\Theta,\ P/PV\Theta,\ PV/P\Theta,\ PV/PV\Theta,\ V/\Theta,\ V/V\Theta\)",
        r"\(P/P\Theta\), \(P/PV\Theta\), \(PV/P\Theta\), \(PV/PV\Theta\), \(V/\Theta\), \(V/V\Theta\)",
    )
    supplement = supplement.replace(
        r"\(P/PV,\ P\Theta/PV\Theta,\ \Theta/V\Theta\)",
        r"\(P/PV\), \(P\Theta/PV\Theta\), \(\Theta/V\Theta\)",
    )
    supplement = supplement.replace("../figures/", "figures/").replace(".svg)", ".png)")
    supplement = supplement.replace(
        "../docs/scientific-contract/CONTRACT.md",
        "https://github.com/blakepi/phasemap-reproducibility/blob/v3.1.1/docs/scientific-contract/CONTRACT.md",
    )
    supplement = supplement.replace(
        "../artifacts/",
        "https://github.com/blakepi/phasemap-reproducibility/blob/v3.1.1/artifacts/",
    )
    supplement = supplement.replace(
        "../src/",
        "https://github.com/blakepi/phasemap-reproducibility/blob/v3.1.1/src/",
    )
    convert_markdown(supplement, OUT / "PHASEMAP_TECHNICAL_SUPPLEMENT_body.tex")
    (OUT / "PHASEMAP_MANUSCRIPT.tex").write_text(main_tex(title, abstract), encoding="utf-8", newline="\n")
    (OUT / "PHASEMAP_TECHNICAL_SUPPLEMENT.tex").write_text(supplement_tex(), encoding="utf-8", newline="\n")

    for tex in (OUT / "PHASEMAP_MANUSCRIPT.tex", OUT / "PHASEMAP_TECHNICAL_SUPPLEMENT.tex"):
        latexmk = shutil.which("latexmk")
        if latexmk:
            run([latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name])
            continue
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            raise FileNotFoundError("latexmk or pdflatex is required to compile the publication PDFs")
        for _ in range(2):
            run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex.name])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doi", default="", help="Zenodo DOI without https://doi.org/")
    args = parser.parse_args()
    build(args.doi.strip())


if __name__ == "__main__":
    main()
