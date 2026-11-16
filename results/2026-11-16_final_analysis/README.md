# Final experimental analysis and manuscript workspace

**Prepared:** 2026-11-16  
**Branch:** `research/edr2-rgb-extension`  
**Frozen proposed checkpoint:** `models/v4_patch3.pth`, SHA-256 `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`  
**Training/fine-tuning in the reported experiments:** none.

This directory consolidates the evidence-backed analysis and a new manuscript draft. It does not overwrite the earlier project report or the earlier RGB experiment packages.

## Files

- `EXPERIMENTAL_ANALYSIS.md`: baseline comparison, ablations, corpus stratification, RGB blend analysis, complexity and limitations.
- `SECURITY_REVIEW.md`: implementation-level security review, threat model and open verification work.
- `MANUSCRIPT_DRAFT.md`: current paper draft aligned to the active EDR2 and CC-EDR2-RGB protocol implementations.
- `RELATED_WORK_POSITIONING.md`: closest prior-art matrix, novelty boundary and required head-to-head comparisons.
- `tables/`: compact summary tables, stratification, per-image capacity ledgers, phase scores, receiver audit and complexity records.
- `figures/`: nine publication-oriented, editable SVG charts derived from the committed CSV summaries.

## Primary experiment provenance

| Evidence | Workflow | Status |
|---|---|---|
| Native grayscale EDR2 corpus | [Run #76 (repository workflow history)](https://github.com/Parzifal25/RDHEI/actions) | 243 inputs; 163 positive net; 978/978 exact round-trips |
| Matched grayscale predictors and ablations | [Run #63](https://github.com/Parzifal25/RDHEI/actions) | 243 inputs; common conservative step-4 / 16-phase comparison |
| Native RGB end-to-end | [Run #79](https://github.com/Parzifal25/RDHEI/actions/runs/43825299870) | 51 inputs; 4 blends; 24 assignments; 162/162 exact round-trips on positive cases |
| Corrected complexity benchmark | [Run #90](https://github.com/Parzifal25/RDHEI/actions/runs/43858892804) | successful CPU benchmark; 5 warmups, 10 measured runs per method |

Run #79 original evidence artifact IDs:
- raw RGB evidence: `14208375193`, SHA-256 `e5418d3ed62772eb906841d979782032eecb263f4b2edcd0899ac1aa8507e154`
- RGB paper analysis: `14208320308`, SHA-256 `6d197ab410c0ef8bf9f1077241e26dd7f13c74918d327ef8e50805bbc250775a`

Run #90 complexity artifact ID: `14222102560`, SHA-256 `1c3c56f0c1b61d45a39c614b1f4486addc3baa114ad42960cf30146927c319e1`.

The Actions artifacts are the authoritative full raw evidence archives; GitHub Actions artifacts have finite retention and are not a substitute for archiving the raw data permanently. This directory commits compact audited summaries and SVG figures. The original raw Run #79 evidence has not been edited.

## Important scope boundaries

1. Native grayscale EDR2 (243 images, four-phase step-2 lattice) is distinct from the matched predictor comparison (243 images, common step-4/16-phase grid). Do not merge their positive counts.
2. The CALIC comparator is a simplified CALIC-style predictor implementation, not a verified full canonical CALIC implementation.
3. Histogram shifting is a separate plaintext-before-AES reference; it is not a same-protocol encrypted-domain hider.
4. RGB CC-EDR2 is a research prototype with sparse positive-capacity coverage. Its 162/162 success denominator contains only payload trials for positive-capacity image/blend pairs.
5. The receiver source-read check is guarded Python file I/O, not an OS sandbox.
6. The 512×512 complexity benchmark uses a deterministic synthetic input and is not directly comparable to the earlier Lena/WSL runtime benchmark.
7. No independent cryptographic audit or formal security proof has been completed.

## Reproduction

The exact protocol and active code are in:
- `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md`
- `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2_RGB.md`
- `final_rdhei_protocol_gate_20261022/run_gate.py`
- `final_rdhei_protocol_gate_20261022/run_rgb_gate.py`
- `final_rdhei_protocol_gate_20261022/run_complexity_benchmark.py`

Do not use legacy `src/encryption.py` as evidence for the active authenticated EDR2 packet protocol.


The nine committed SVGs include the adaptive 24-phase assignment-gain figure. Compact per-image phase-gain records are saved as CSV. The full 4,896 assignment-score ledger and the full per-case receiver evidence remain in the linked Run #79 raw evidence archive; the original Action artifact is preserved without editing.
