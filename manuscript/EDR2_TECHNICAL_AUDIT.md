# EDR2 technical audit — refreshed 23 November 2026

**Scope:** EDR2 publication-hardening source branch, native grayscale final-evaluation artifact, corrected external-baseline reproduction artifact, and optimized E2E runtime artifact. This report supersedes the earlier provisional audit written before these files were located. It does not describe EDR1.

## 1. Evidence now located and checked

| Claim area | Evidence examined | Status |
|---|---|---|
| Protocol identity | EDR2 protocol specification, `wire.py`, `predictor.py`, test and workflow history on `research/edr2-publication-hardening` | Verified for EDR2 |
| Four-phase step-2 lattice | Protocol and predictor implementation; phase-specific capacity records | Verified |
| Masked predictor input invariance | Code geometry and radius-one patch definition | Mathematical proposition follows from the stated assumptions |
| Authentication | EDR2 HKDF domains, AES-256-CTR, HMAC-SHA256 path; receiver verifies before decompression/inference | Verified implementation behaviour; not a formal security proof |
| Grayscale corpus | 243-row `corpus.json`, `input_manifest.json`, `capacity_summary.csv`, source and pixel hashes | Verified; **232 natural + 11 constructed**, not 239 + 4 |
| Capacity | 243 per-image rows; 163 positive, 80 non-positive | Recomputed |
| Exact recovery | Six receiver trials per positive-capacity image; 978/978 exact image and payload results | Verified in ledger |
| Algebraic inversion | `algebra.json`: 65,536 original/prediction pairs, 396,032 payload words, zero failures | Verified exhaustive finite-domain result |
| External baselines | Corrected 243-image PPMR merge, Multi-MSB+Huffman outputs, paired per-image table, merge-validation record | Verified same-corpus native-protocol comparisons |
| Parser robustness | EDR2 fuzz artifact: 20,000-input campaign, no crashes reported | Verified as an implementation test, not a proof |
| Predictor runtime | Predictor-only timing artifact | Verified within its original 4-thread comparison harness |
| Optimized E2E runtime | Run #118; vectorized patch extraction and 10 full-capacity exact E2E repeats | Verified on one 512 × 512 CPU image |
| RGB extension | 51-image exploratory artifact, all 24 channel-phase assignments | Verified as exploratory only |

## 2. Canonical quantitative results

### Native grayscale EDR2

- Images: 243; source hashes and decoded-pixel hashes are recorded.
- Curation classes: 232 natural-labelled and 11 constructed texture mosaics.
- Positive net capacity: 163/243 (67.08%).
- Non-positive net capacity: 80/243.
- Mean signed net rate: 0.110540 bpp.
- Pooled signed net rate: 0.059821 bpp.
- Mean usable net rate across all images: 0.143220 bpp.
- Pooled usable net rate: 0.095496 bpp.
- Median usable rate: 0.047054 bpp; Q1 0; Q3 0.194965 bpp.
- Cluster bootstrap: 29 provenance/correlation clusters, 10,000 replicates, seed 20261119; mean-usable 95% interval 0.061387–0.250383 bpp; positive-coverage interval 0.501854–0.823922.
- Exact receiver trials: 978/978 over six payload-size cases for each of 163 accepted images.

### Matched-grid predictor study

This is a distinct step-4/16-phase, common-grid experiment; it is not the native EDR2 step-2/four-phase protocol.

- CNN-3×3 EDR2 checkpoint: MAE 4.8130; positive-net outcomes 133/243.
- CNN-5×5 no-weighted-loss ablation: MAE 4.6233; positive-net outcomes 140/243.
- CNN-5×5 no-weighted-loss is better on these two measures. The 3×3 checkpoint is justified as a receptive-field/protocol-complexity trade-off, not as the best predictor.
- MED: MAE 7.9503; GAP: 7.8408; simplified CALIC-style baseline: 8.2021.

### External native-protocol replications

| Method | Positive-net | Mean usable bpp | Pooled usable bpp | Exact image/payload |
|---|---:|---:|---:|---:|
| EDR2 | 163/243 | 0.143220 | 0.095496 | 978/978 accepted-image trials |
| Multi-MSB+Huffman | 243/243 | 2.088477 | 1.973505 | 243/243 |
| Corrected PPMR | 238/243 | 2.228173 | 2.118172 | 243/243 |

The comparisons use the same source and decoded pixel arrays but retain each method's native carrier, encryption order, metadata and rate definitions. Do not present them as an identical packet-cost or same-security-model leaderboard.

PPMR's corrected reproduction has four disclosed changes (two bit-plane 7/8 control-flow repairs and two active-bit-plane extraction-order corrections). Multi-MSB+Huffman is pinned to upstream commit `1e69ae2713dededa56595ff09255cda1e17896d9`; its adapter passes the actual returned embedded bit count to the decoder. The comparison merge validation contains 243 unique rows, 243 exact image passes and 243 exact payload passes, with no missing, duplicate or unexpected image IDs.

### Runtime and memory

- Original predictor-only benchmark: CNN-3×3 708.479 ms vs MED 3.826 ms on the same original 4-thread harness, approximately 185.2× slower. Do not imply this comparison uses the later optimized patch-extraction path.
- Later optimization: vectorized `sliding_window_view` patch extraction; extracted arrays identical to the original path and zero rounded-prediction mismatches under the validated settings. Active runtime configuration: CPU, two threads, batch 2,048.
- Optimized run #118, one 512 × 512 USC-SIPI image, two warm-ups, ten measured repeats, 39,655 bits per run (0.151272 bpp), ten distinct nonces, 10/10 exact recovery. Mean 1.114019 s, SD 0.058079 s, median 1.120437 s. Sampled RSS increment 10.87 MiB (5 ms sampling).
- This is a single-image CPU E2E measurement, not a multi-resolution scalability study.

## 3. Novelty boundary after literature review

Prior work already uses checkerboard prediction, CNN or masked predictors, MSB replacement, prediction-error compression, adaptive partitioning, in-band location maps, net-capacity accounting, and authentication in RDHEI. Recent 2026 papers further strengthen the prior-art boundary:
- D4 symmetry + bidirectional pixel shifting + context-aware recovery, dynamic block partitioning, in-band location map, and explicit net-rate accounting;
- MSB sharing with overlapping sawtooth or block partitions;
- adaptive bit-plane classification and group coding;
- dual-stage bit-plane compression plus CP-ABE recovery authorization;
- horizontal/vertical pixel shifting with dynamic 2×2/4×4 partitioning;
- context-aware adaptive prediction and pixel classification;
- cross-domain neural prediction in a collusion-resistant RDHEI design.

**Defensible EDR2 centre of gravity:** a precise, implementation-matched non-interference proposition for a centre-masked radius-one predictor, using a step-2 carrier-centre set whose pairwise Chebyshev separation prevents all other mutable carriers from entering a candidate's 3×3 patch. The four-phase scoring and authenticated packet are components of the implemented protocol composition, not standalone first-of-kind claims.

## 4. Remaining submission blockers

1. **Training provenance:** the evaluation artifact gives the checkpoint SHA-256 and records that no training was performed during final evaluation. The final checkpoint's full training manifest must still be attached: source dataset/image hashes, image-level train/validation split, random seed, loss, optimizer, schedule/epochs, selection criterion, and validation record.
2. **Figure rights:** check per-image USC-SIPI reuse permissions before embedding any image in the submitted manuscript. Use schematic figures where rights are uncertain.
3. **Artifact and code citation:** add immutable links/commit SHAs and, where venue permits, a data/code availability statement. Keep the exact evidence artifact IDs and hashes in the supplement.
4. **Reference validation:** bibliographic metadata and DOI links have been assembled and publisher-level checks performed for the recent works cited. The Scite MCP account is on a free inactive plan with zero MCP calls; it could not perform DOI/retraction/citation-context screening. Re-run Scite verification when access is enabled, or manually cross-check all final references against publisher/Crossref records before submission.
5. **Final writing checks:** rerun citation consistency, paragraph logic and British-English review on the final full manuscript after the last citations are frozen.
6. **Journal selection:** verify the target journal's current aims/scope, coverage years/indexing, article type, word/figure limits, access route, fee schedule and review policy before formatting or submission.

## 5. Decisions

- Do not retrain or fine-tune the CNN.
- Do not run new speculative capacity tuning.
- Keep EDR1 data out of this EDR2 paper.
- Keep predictor-only results distinct from native EDR2 results.
- Keep native-protocol external comparison caveats prominent.
- Keep RGB results in a clearly marked exploratory appendix or supplement.
- Do not claim SOTA capacity, superior predictor accuracy, formal security proof, independent cryptographic certification, malicious-hider resistance or multi-resolution scalability.
