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
| Native grayscale EDR2 four-phase corpus | [Run #71](https://github.com/Parzifal25/RDHEI/actions/runs/43579225461) | 243 native TIFFs; 163 positive; 978/978 exact round-trips; two decoded-pixel duplicates removed |
| Matched grayscale predictors and ablations | [Run #63](https://github.com/Parzifal25/RDHEI/actions/runs/43694973838) | 243 identical decoded-pixel hashes; common step-4 / 16-phase comparison; 133/243 v4 positive |
| Native RGB end-to-end and adaptive phase evaluation | [Run #79](https://github.com/Parzifal25/RDHEI/actions/runs/43825299870) | 51 images; four blends; 4,896 phase scores; 162/162 exact receiver trials among positive image/blend cases |
| Predictor complexity/runtime/memory | [Run #90](https://github.com/Parzifal25/RDHEI/actions/runs/43858892804) | 512×512 synthetic CPU predictor benchmark; 5 warmups and 10 timed repeats per method |
| Active native-image EDR2 end-to-end runtime/memory | [Run #102](https://github.com/Parzifal25/RDHEI/actions/runs/43885495308) | Native 5.2.08.tiff; 10 repeats; 10/10 exact recoveries; mean 2.506 s; sampled RSS increment 16.59 MiB |
| Adversarial grayscale parser campaign | [Run #98](https://github.com/Parzifal25/RDHEI/actions/runs/43884570447) | 20,000 Atheris coverage-guided inputs; no crash artifact reported; 121 coverage counters / 188 feature counters |
| External native-protocol grayscale baselines | [Run #44717673688](https://github.com/Parzifal25/RDHEI/actions/runs/44717673688) | Multi-MSB+Huffman and corrected PPMR on the same 243 hash-verified images; 243/243 exact payload and host recovery for each; PPMR 40/40 shards; final paired comparison and 29-cluster bootstrap |
| Expanded deterministic tamper/parser regression | [Run #93](https://github.com/Parzifal25/RDHEI/actions/runs/43875481127) | Grayscale and RGB protocol regression tests passed |
| Final rerun batch | [Run #103](https://github.com/Parzifal25/RDHEI/actions/runs/43907455905) | Native grayscale, matched grayscale, RGB, parser fuzz and complexity jobs triggered; see live job/artifact status before citing any updated output |

Run #79 evidence artifacts:
- raw RGB evidence: `14208375193`, source archive SHA-256 `e5418d3ed62772eb906841d979782032eecb263f4b2edcd0899ac1aa8507e154`
- RGB paper analysis: `14208320308`, source archive SHA-256 `6d197ab410c0ef8bf9f1077241e26dd7f13c74918d327ef8e50805bbc250775a`

Run #90 complexity artifact: `14222102560`. Run #98 fuzz artifact: `14233618728`. Run #102 active E2E artifact: `14233328717`.

The final native and matched grayscale manifests contain the same 243 decoded-pixel SHA-256 values, although the earlier matched-run curation labels differed. The committed stratification CSV has been recomputed using the final native allowlist labels; the 29-cluster bootstrap still uses the provenance clusters from the matched run. All final summaries must be read with that note.

GitHub Actions artifacts have finite retention. The closure package separately archives the evidence ZIPs used for this record; the raw Run #79 artifact is preserved unchanged, and its erroneous top-level source-access counter is corrected only in the derived per-case audit.

## External-baseline evidence

The full external-baseline evidence archive is `external-rdhei-243-image-final-publication-evidence.zip` in the conversation deliverables. The comparison is publication-ready as a matched-corpus, native-protocol experiment, not a same-packet-cost leaderboard. It records the native rate formula for each method, all 243 per-image rows, final 239-natural/4-constructed labels, the preserved 29 correlation clusters, paired bootstrap intervals, the corrected PPMR source patch hashes, and the 256×256 exact-roundtrip smoke record. The PPMR upstream repository was pinned to `21f397890289049798ced0f98d1482d629f93b06`; four compatibility corrections were confined to a temporary checkout. No model was retrained and no EDR2 checkpoint was modified.

## Important scope boundaries

1. Native grayscale EDR2 (243 images, four-phase step-2 lattice) is distinct from the matched predictor comparison (243 images, common step-4/16-phase grid). Do not merge their positive counts.
2. The CALIC comparator is a simplified CALIC-style predictor implementation, not a verified full canonical CALIC implementation.
3. Histogram shifting is a separate plaintext-before-AES reference; it is not a same-protocol encrypted-domain hider.
4. RGB CC-EDR2 is a research prototype with sparse positive-capacity coverage. Its 162/162 success denominator contains only payload trials for positive-capacity image/blend pairs.
5. The receiver source-read check is guarded Python file I/O, not an OS sandbox.
6. The Run #90 512×512 complexity benchmark uses a deterministic synthetic input; Run #102 is a separate warmed, native-image end-to-end measurement. They measure different scopes and should not be merged.
7. No independent cryptographic audit or formal security proof has been completed.
8. Two external baseline source implementations have now been reproduced on the same 243-image grayscale corpus. ACBP, the asymmetric-CNN/adaptive-mean, pixel-level masked-autoencoder and BCAGC methods remain without a full matched-corpus reproduction. PPMR's four temporary compatibility corrections must be disclosed in any paper or supplement.

## Reproduction

The exact protocol and active code are in:
- `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md`
- `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2_RGB.md`
- `final_rdhei_protocol_gate_20261022/run_gate.py`
- `final_rdhei_protocol_gate_20261022/run_rgb_gate.py`
- `final_rdhei_protocol_gate_20261022/run_complexity_benchmark.py`

Do not use legacy `src/encryption.py` as evidence for the active authenticated EDR2 packet protocol.

- `final_rdhei_protocol_gate_20261022/run_edr2_e2e_benchmark.py`: complete in-memory prepare, reserve/encrypt, encrypted-domain embedding, authentication, extraction and reconstruction timing with sampled process RSS.
- `tests/test_edr2_adversarial_packets.py`: deterministic malformed-header, authenticated malformed-compression, wrong-key/nonce and tamper mutation regression tests.

The Run #102 end-to-end timing workflow uses native USC-SIPI image 5.2.08.tiff (512×512), full-net payload insertion, two warmups and ten measured repeats. It is reported separately from predictor-only timing, process startup and deployment I/O. Run #96 is an earlier synthetic-fixture smoke benchmark and is superseded for native-image timing by Run #102.


The nine committed SVGs include the adaptive 24-phase assignment-gain figure. Compact per-image phase-gain records are saved as CSV. The full 4,896 assignment-score ledger and the full per-case receiver evidence remain in the linked Run #79 raw evidence archive; the original Action artifact is preserved without editing. The familiar six legacy PNG controls (Airplane, Baboon, Goldhill, Jetplane, Lena and Peppers) are not present in either full-corpus manifest and are not included in the 243-image USC-SIPI corpus; the 2026-11-16 runs record all six as missing. Historical Airplane/Goldhill/Jetplane/Lena receiver outputs in repository evidence folders do not constitute restoration of the original six source PNGs.
