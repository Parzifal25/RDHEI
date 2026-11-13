# MANUSCRIPT_UPDATE_CHANGE_REPORT_20261020.md

**Manuscript revision pass — 2026-10-20**
Authority: `FINAL_CLOSURE_REPORT.md` (status **READY WITH DISCLOSED LIMITATIONS**) plus the
project evidence it cites. No retraining, no new experiments, no production source-code
changes, no changes to any verified numeric result.

---

## 0. Deliverables and preservation of originals

| File | Role |
|---|---|
| `Final_report_REVISED_20261020.md` | **Revised manuscript source (new file)** |
| `Final_report_REVISED_20261020.pdf` | **Rendered PDF of the revised manuscript (new file, 21 pages)** |
| `manuscript_check_20261020.py` | Table-cell / consistency checker (Tables 1–11 vs authoritative CSVs) |
| `pdf_render_check_20261020.py` | Rendered-PDF string/structure checker (68 checks) |
| `render_manuscript_pdf.py` | Markdown→PDF renderer (reportlab + DejaVu; no LaTeX/pandoc in this environment) |
| `MANUSCRIPT_UPDATE_CHANGE_REPORT_20261020.md` | This report |

Originals `Final_report.md` and `Section_3_Updated.md` are **preserved unchanged**
(`Final_report.md` verified byte-identical to its pre-pass state; the diff between the
original and the revision is reproduced item-by-item in §1 below).

---

## 1. Completed fixes (evidence-supported only)

1. **Closure-status header added (front matter).** One banner paragraph states the technical
   closure status *READY WITH DISCLOSED LIMITATIONS* per `FINAL_CLOSURE_REPORT.md`, and that
   the disclosed limitations and publication blockers remain open and are not presented as
   resolved.
2. **Table 8 (closure-report numbering) — 4.2.06 red-channel CNN value.** The closure report
   resolves 4.5647 vs 4.5648 in favour of **4.5648** (source value 4.564750671, rounded not
   truncated; 5 corroborating raw sources). The manuscript's channel-wise RGB table (captioned
   *Table 5* in this manuscript, §8.5 — the closure report's "Table 8") **already contained
   4.5648**, and the manuscript's source data agree with the report (`b2_rgb_per_channel.csv`,
   `results/rgb/baselines_rgb_results.txt` R=4.5648, `phase_be_run.log` R bpp=4.5648).
   Verified programmatically (check C2): manuscript=4.5648 vs source=4.564750671 → 4.5648.
   The superseded truncation `4.5647` appears **nowhere** in the manuscript or the PDF.
   *No cell edit was needed; the value was confirmed, not changed.*
3. **Bold "best-value" marks corrected (4 cells, Tables 1–4).** Bold now marks the actual
   per-row winner: Peppers BPP → GAP (5.0157), Peppers MAE → GAP (5.1399), RGB 4.2.07 BPP →
   GAP (4.8622), RGB 4.2.07 MAE → GAP (6.3687). Sentence under Table 2 corrected from
   "CNN-3×3 is best on every image" to five of six, naming the Peppers exception.
4. **Mean-level qualification of summary claims (§1, §11 abstract-adjacent summary, §13).**
   "highest capacity / lowest error" now explicitly **mean**-level with per-image exceptions
   pointed to (Tables 1–4, §8.3 channel note, `b3_ablation_*.csv`). This preserves the
   comparative scope and avoids any universal-superiority claim.
5. **Runtime statements reconciled with the measurement protocol (§ intro RQ4, §8.9, §8.10,
   §8.12).** Predictor-only and end-to-end timings are now never mixed: the RQ4 answer cites
   predictor-only ratios (~80× GAP, ~130× CALIC, ~255× MED; CNN-7×7 ~1270× vs MED) and
   points to §8.10 for end-to-end times, which are dominated by Python pixel loops. Every
   runtime table/column is labelled with protocol (Lena 512×512, CPU, warm-up 5, 10 repeats
   for predictor-only; 3 repeats for end-to-end; milliseconds; model loading excluded;
   cross-day measurements never pooled). The previously stale "~250–1270×" RQ4 phrasing and
   "roughly two orders of magnitude" summary phrasing were replaced by the measured ratios.
6. **Complexity discussion and Table 11 added from the regenerated complexity results
   (§8.12).** New section presents the 2026-10-20 regeneration (`src/comp.py` →
   `results/complexity/complexity_results.csv` / `complexity_report.txt`, captioned the
   paper's *Table 3*): parameters 0/0/0/46,881/112,417/112,353/112,417/210,721; MACs per
   patch 122,816/340,928/340,128/340,928/668,096; Approx FLOPs = 2×MACs (ptflops absent —
   analytic path documented); model sizes; predictor-only runtime column tied to Table 9.
   Caveats stated in-section: per-patch MACs are per pixel (Θ(H·W) forward passes;
   ≈3.22×10^10 MACs for one 512×512 image under CNN-3×3), classical FLOP constants are
   hard-coded scale indicators, model size is the fp32 footprint, and *complexity is not
   speed*. §8.8 now cross-references the verified counts (5/5 match).
7. **§10/§13 reversibility case-count parenthetical corrected.** The five-checkpoint
   full-capacity sweep (55 cases) is now shown to be already included in the 180 combined
   cases (85 gray + 40 RGB + 55 sweep), instead of implying an additional 180+55.
8. **Cross-reference tightened (§8.2 figure/table note).** §8.5/Table 5 caption reference
   and §8.2 best-value note now point to sections that actually contain the referenced
   statements.
9. **Reproducibility appendix extended.** Added: closure-pass complexity output location
   (`results/complexity/`) and a revision addendum recording this pass, its check script,
   its result (0 mismatches), and the closure finding F3 (the 62/62 and 109/109 manuscript
   check scripts cited in earlier task briefs are absent from this repository and were
   **not** re-executed).

---

## 2. Verification checks run (results)

| Check | Command | Result |
|---|---|---|
| Table-cell consistency vs authoritative CSVs | `python3 manuscript_check_20261020.py Final_report_REVISED_20261020.md` | **23 PASS / 0 WARN / 0 FAIL / 1 BLOCKED — 267 numeric cells (Tables 1–11) match at printed precision** |
| Rendered-PDF check | `python3 pdf_render_check_20261020.py Final_report_REVISED_20261020.pdf` | **0 FAIL / 0 WARN over 68 checks** (title, status, all 11 sections, Tables 1–11 markers, Figures 1–11, key values, limitation strings, `4.5648` present, `4.5647` absent, no missing-glyph chars) |
| Section-3 validator | `bash validate_section3.sh` | 10 OK / **1 FAIL — pre-existing false positive**: the validator's escaped regex does not match the lower-bit equation, but the equation is present verbatim at `Section_3_Updated.md:433` (fixed-string grep confirms). `Section_3_Updated.md` was not modified in this pass. |
| Project test suite | `python3 -m pytest tests/ -q` | **16 passed, 0 failed** (11 warnings, pre-existing) |
| Bare `python3 -m pytest` (repo root) | — | **Pre-existing collection error**, not caused by this pass: `tests/test_smoke.py` resolves `src.encryption` to the outer tree `/home/parzifal/RDHEI_Project/src/encryption.py`, which lacks `encrypt_rgb_channels` (present in this tree's `src/encryption.py:75`). Unrelated to manuscript files; the canonical invocation `pytest tests/ -q` passes. |
| References section preserved verbatim | §15 extracted from both files and byte-compared | **identical (1,498 B = 1,498 B); placeholders unchanged** |
| Equations / notation preserved | delimiter audit of original vs revised | 0 `equation` environments, 0 `\(`/`\)`, one `$$…$$` block and 0 inline `$` in both files — **counts identical, the `$$` block byte-identical**; Section-3 equations covered by `validate_section3.sh` (26/26 balanced) |
| Bibliography source search (project-wide, incl. parent tree) | `find` for `*.bib`/`*.ris`/`*.enl`/`*.nbib`/CSL JSON + heading scan | **none found** — confirms C7 BLOCKED status is real, not assumed |
| Citation ↔ reference cross-check (C7) | `manuscript_check_20261020.py` | **BLOCKED — see §4.** |

Checks that **cannot be run in this environment** (clearly labelled):
- **LaTeX-based rendering / compilation** — no `pdflatex`, `xelatex`, `pandoc`,
  `wkhtmltopdf`, or `weasyprint` installed. The PDF was produced with a project-local
  renderer (`render_manuscript_pdf.py`, reportlab + DejaVu fonts) and verified afterwards
  by text extraction (`pdf_render_check_20261020.py`).
- **Bibliography/citation verification (C7)** — no `.bib`, reference-list source file, or
  citation database exists in the repository (see §4).
- **The 62/62 and 109/109 manuscript check scripts** cited in earlier task briefs are
  absent from this repository (closure finding F3) and were **not** re-executed; their
  coverage is replaced as far as possible by C10 + C3 + C6 equivalents in
  `manuscript_check_20261020.py`.

---

## 3. Remaining limitations (retained explicitly — NOT presented as resolved)

- **Training provenance:** checkpoint training runs are not fully traceable (no training
  logs/configs for all five variants); retained in §7.4 / §10.7 / §16.6.
- **Dataset provenance:** benchmark-image provenance and licence documentation are
  incomplete; `images.png` is grayscale and excluded from RGB aggregates — retained.
- **Historical manuscript timings:** earlier manuscript runtime numbers are historical and
  not pooled with the 2026-10-18 measurements — retained; only labelled protocol tables are
  cited.
- **Reproducibility:** exact end-to-end reproduction of every published number is not
  guaranteed from this repository alone (missing check scripts — F3; dual MED average BPP
  values 4.9575 vs 4.977483; RGB image-set ambiguity 6 vs 5 images in raw aggregates —
  documented in `FINAL_RESULTS_SOURCE_MAP.md`); retained in the reproducibility appendix.
- **Environment:** no `ptflops` in this environment (FLOPs from the documented analytic
  path, 2×MACs); CPU-only timings.

## 4. Submission blockers (open)

1. **Bibliography (publication declaration).** No verified bibliography exists in the
   repository: the References section contains **placeholder entries only**, and citation
   verification could not be run (check C7 = BLOCKED). This is a hard blocker: the paper
   cannot be described as submission-ready until a real bibliography is supplied and every
   in-text citation is verified against it.
2. **Publication declarations** (author info, funding, conflict-of-interest, data-availability
   statement, ethics) are not present/completed in the manuscript.
3. Related open items that must ship with any submission: the disclosed limitations of §3
   above, and the closure report's `READY WITH DISCLOSED LIMITATIONS` status itself.

## 5. What was deliberately NOT changed

- No new experiments, no retraining, no alteration of any verified numeric result
  (all 267 checked cells match their source CSVs at printed precision).
- No production source code, checkpoints, datasets, or result CSVs modified by this pass
  (the pre-existing working-tree edit in `src/rdhei_core.py` predates this revision pass and
  was not touched).
- Bibliography/References section preserved unchanged (placeholders retained, not invented).
- Original manuscript files preserved (`Final_report.md`, `Section_3_Updated.md`).
- Paper scope unchanged: comparative evaluation of CNN predictor configurations for RDHEI —
  no real-time, universal-superiority, or all-RDHEI-methods superiority claims
  (overclaim pattern scan C8: clean).

---
*Generated 2026-10-20 by the manuscript revision pass.*
