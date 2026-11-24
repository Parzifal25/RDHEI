# EDR2 manuscript package

## Canonical JISA submission source

The **current submission-oriented manuscript** is in `manuscript/jisa/`:

- `EDR2_JISA_Main.tex` — complete Elsevier `elsarticle` manuscript, with formal proposition/proof, protocol, equations, experiments, 10 tables, four vector figures and a cited related-work section.
- `EDR2_JISA_References.bib` — bibliography (34 entries; 34 keys are cited in the manuscript).
- `Highlights.txt` — five Elsevier/JISA-style highlights.
- `Graphical_Abstract.tex` — separate vector graphical abstract.
- `figures/EDR2_Architecture_Diagram.tex` — editable TikZ architecture diagram used by the main manuscript.
- `JISA_Submission_Readiness.md` — fit and acceptance-risk note.
- `../.github/workflows/build-jisa-manuscript.yml` — citation/highlight checks, LaTeX/BibTeX compilation and PDF/source-package build.

The workflow uploads a compiled main PDF, graphical abstract PDF and full editable source package as an Actions artifact. The package build must pass before the manuscript is treated as typeset-ready.

## Supporting audit and reproducibility files

The earlier Markdown working draft is retained for reference, but the JISA LaTeX source above is the canonical paper for journal review.

- `EDR2_EVIDENCE_PROVENANCE.md` — raw evaluation artifact IDs, hashes, source branches and key metrics.
- `EDR2_TECHNICAL_AUDIT.md` — evidence audit, novelty boundary and remaining submission blockers.
- `EDR2_EXACT_ACTION_CHECKLIST.md` — precise remaining tasks before submission.
- `EDR2_MANUSCRIPT_WORKING_DRAFT.md` — concise project status.

## Important status

The JISA source reports the final native grayscale curation as **232 natural-labelled plus 11 constructed texture mosaics (243 total)**. It keeps the matched-grid predictor ablation separate from native EDR2 and reports Multi-MSB+Huffman and corrected PPMR as same-corpus native-protocol reproductions, not identical packet-cost/security comparisons.

The EDR2 pooled usable rate is 0.09550 bpp, substantially below the two reproduced methods. That gap is stated directly. The paper does not claim high capacity or state-of-the-art performance.

The manuscript is still a draft. The frozen checkpoint training manifest, author/affiliation details, funding and conflict declarations, figure-use permissions, independent cryptographic review, persistent code/data DOI, final citation screening, target-journal final-format review and supervisor approval remain outstanding.

No model retraining is proposed. The repository `main` branch remains unchanged by the manuscript work.
