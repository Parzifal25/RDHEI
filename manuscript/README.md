# EDR2 manuscript package

This directory contains the EDR2 research-paper working draft and its reproducibility support files.

- **`EDR2_FULL_PAPER_DRAFT.md`** — complete academic paper draft, including abstract, formal method, protocol, results, limitations and IEEE-style references.
- **`EDR2_REFERENCES.bib`** — BibTeX database for the manuscript's 24 references.
- **`EDR2_EVIDENCE_PROVENANCE.md`** — raw evaluation artifact IDs, hashes, source branches and key metrics.
- **`EDR2_TECHNICAL_AUDIT.md`** — evidence audit, novelty boundary and remaining submission blockers.
- **`EDR2_EXACT_ACTION_CHECKLIST.md`** — exact remaining tasks before submission.
- **`EDR2_MANUSCRIPT_WORKING_DRAFT.md`** — short working-status note.

## Important status

This is a full research manuscript draft, not yet a journal-formatted submission. The final checkpoint training manifest, image-use permissions for any reproduced figures, final independent DOI/retraction screening, target-journal selection, and author/supervisor review remain outstanding.

The draft reports the corpus as **232 natural-labelled plus 11 constructed images (243 total)**, based on the final run's `input_manifest.json` and `run_summary.json`. It distinguishes the matched-grid predictor experiment from native EDR2 and treats Multi-MSB+Huffman / corrected PPMR as native-protocol same-corpus replications rather than identical-cost or identical-security comparisons.

No model retraining is proposed. The existing `main` branch was not modified by this manuscript work.
