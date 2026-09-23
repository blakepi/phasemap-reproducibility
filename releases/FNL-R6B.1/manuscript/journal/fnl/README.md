# FNL source package

This directory adapts the official World Scientific *Fluctuation and Noise
Letters* template downloaded on 2026-09-05. `ws-fnl.cls` and `ws-fnl.bst` are
unchanged vendor files; their original copyright notices are retained.

## Entry points

- `PHASEMAP_FNL.tex`: main Letter, using the official `ws-fnl` class.
- `PHASEMAP_FNL_Supplement.tex`: complete technical supplement, retaining
  S-numbered sections.
- `PHASEMAP_FNL_Cover_Letter.tex`: editor-facing cover letter.
- `PHASEMAP_FNL_General_Summary.tex`: one-page, equation-free summary.

The main Letter contains two native LaTeX tables (the seven-protocol decoder and
proper-subsignature classes) and one four-panel transport figure referenced as
`../../../figures/F-080-transport-localization.pdf`; this matches the
repository and source-archive layout with `figures/` at the package root. The
main article retains the exact decoder, kinetic-trace differences, localization
argument, and restricted-observation identities. The supplement contains the
complete derivation, numerical methods and the separately reported trajectory
studies. Build and page-limit assessment
are performed by the repository FNL build workflow; do not alter vendor files.

## Local build

From this directory, run:

```text
latexmk -pdf PHASEMAP_FNL.tex
latexmk -pdf PHASEMAP_FNL_Supplement.tex
latexmk -pdf PHASEMAP_FNL_Cover_Letter.tex
latexmk -pdf PHASEMAP_FNL_General_Summary.tex
```

The official template ZIP was downloaded from
https://www.worldscientific.com/sda/1037/fnl-2e.zip on 2026-09-05 and has
SHA-256 `84d615a2e6ff75b3fce7e036e8925ccccbc8827464fb974b2540242f9efed35c`.
The copied vendor assets were verified
byte-identical to the live template: `ws-fnl.cls`
`1805A267958E42A275886BF742D6FD61F69016ABB1F5B2E30377169EDEB72560` and
`ws-fnl.bst` `DF8EC6E48F75D7218481AB92C4E0F49EDB1191D075C36BC21C70A21B48D14DD3`.
