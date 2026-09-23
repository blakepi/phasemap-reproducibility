# Journal source

`fnl/` is the current FNL submission-source entry. The REVTeX sources in this
directory are retained as the extended manuscript source.

Run `python scripts/build_manuscript_pdf.py` from the repository root. The
builder converts each required `../../figures/F-080-*.svg` to a same-stem
vector PDF, compiles both REVTeX 4.2 sources with `latexmk -pdf`, rejects
rasterized figure PDFs and Type 3 or unembedded document fonts, verifies text
extraction, and renders every page for visual inspection. The old
collision-prone table is absent.
