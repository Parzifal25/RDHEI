# EDR2 evidence provenance and reproduction map

**Date checked:** 23 November 2026  
**Paper:** `manuscript/EDR2_FULL_PAPER_DRAFT.md`  
**Status:** Evidence map for manuscript review. This document points to the immutable run outputs that support the paper's results; it is not a new experimental report.

## 1. Source-code branches and fixed revisions

| Purpose | Repository branch / revision | Use in manuscript |
|---|---|---|
| EDR2 protocol, full-corpus gate and tests | `research/edr2-publication-hardening` | Four step-2 phases, header probing, HKDF domains, AES-CTR, HMAC, label mapping and final grayscale evaluation |
| Optimized CPU patch extraction | `research/edr2-runtime-optimization`, optimization commit `dceed5cbb3ec4b0e0b15cf7eb559aa58d50689b7` | Vectorized sliding-window patch extraction, equivalence check, two-thread runtime |
| External baseline reproduction | `research/external-baseline-reproduction` | Pinned Multi-MSB+Huffman and corrected PPMR reproductions |

Baseline source pins:
- Multi-MSB+Huffman upstream revision: `1e69ae2713dededa56595ff09255cda1e17896d9`.
- PPMR upstream revision: `21f397890289049798ced0f98d1482d629f93b06`.
- PPMR compatibility patch: four narrow fixes; see the reproduction branch's patch and raw CSV. Do not call the corrected run an unmodified upstream execution.

## 2. Primary evidence artifacts

| Evidence | GitHub Actions artifact ID | Downloaded artifact filename | SHA-256 of ZIP |
|---|---:|---|---|
| Native EDR2 grayscale full-corpus evaluation | 14250120410 | `edr2-native-grayscale-final-harmonized-evidence.zip` | `d42cdb65218e5467ac5057301f091d0d10f4bf6baccbe423dff6ddcd02a3afbb` |
| Corrected 243-image external comparison | 14633736009 | `external-rdhei-243-image-corrected-comparison.zip` | `767f81cc3a8dfb468434db7042bc3cba0a2602da3302b262ca15afbcca73ff0e` |
| Optimized EDR2 E2E benchmark, Run #118 | 14316686389 | `edr2-e2e-optimized-run118.zip` | `794ad6fdfaf1a40b71e055bbfe58cd911f2ce26cc5256be350f9e67860f02f5d` |
| Predictor complexity benchmark | 14222102560 | `edr2-complexity-benchmark.zip` | `1c3c56f0c1b61d45a39c614b1f4486addc3baa114ad42960cf30146927c319e1` |

The artifact IDs are the GitHub Actions artifact identifiers for the linked repository; the SHA-256 values above were calculated from the downloaded ZIP bytes during this review.

## 3. Key files inside the evidence artifacts

### Native grayscale EDR2

- `capacity_summary.csv`: one row per accepted evaluation image; includes gross capacity, bootstrap opportunity cost, stored metadata, backup, signed net bits, usable bpp and chosen phase.
- `roundtrip_summary.csv`: six receiver cases per positive-capacity image; 978 exact image/payload trials.
- `corpus.json`: canonical 243-image evaluation list with classification, source path, dimensions, and source/pixel hashes.
- `input_manifest.json`: curation and classification counts; records 232 natural-labelled and 11 constructed images and two duplicate decoded-pixel files removed from 245 accepted inputs.
- `natural_image_allowlist.json`: catalogue-based source inclusion, exclusion and classification policy.
- `integrity.json`: frozen checkpoint hash and no-training/no-model-change flags for this evaluation.
- `algebra.json`: exhaustive reconstruction mapping result (65,536 prediction/original pairs; 396,032 payload words; zero failures).
- `run_summary.json`: aggregate metrics, clustering, exact receiver counts and bootstrap intervals.

### Corrected external comparison

- `native_protocol_comparison.json`: native-protocol aggregate results and paired differences.
- `native_protocol_paired_per_image.csv`: paired comparison at the same 243 image IDs.
- `native_protocol_group_summary.csv`: method summaries.
- `ppmr_corrected_raw.csv`: corrected PPMR raw rows.
- `merge_validation.json`: verifies 243 unique images, no missing/duplicate/unexpected IDs, and 243 exact image and payload passes.

### Optimized E2E runtime

- Run #118 report records the 512 × 512 USC-SIPI image, ten measured full-capacity repeats, distinct nonces, exact image/payload recovery, timing by stage, and sampled RSS.
- The patch-extraction validation compares vectorized patches with the original implementation and records zero patch/prediction mismatches under the selected configuration.

### Complexity benchmark

- `complexity_benchmark_report.md` and `benchmark_environment.json` record the predictor-only CPU comparison, parameter count, MAC count and RSS sampling scope.

## 4. Core numbers recomputed from raw rows

Native EDR2:
- 243 images; 232 natural-labelled and 11 constructed.
- 163 positive-net images (67.08%).
- Mean signed net bpp 0.110540; pooled signed net bpp 0.059821.
- Mean usable net bpp 0.143220; pooled usable net bpp 0.095496.
- Median usable net bpp 0.047054; Q1 0; Q3 0.194965.
- 978/978 exact image and payload receiver trials.

External same-corpus native-protocol replications:
- Multi-MSB+Huffman: mean usable 2.088477 bpp; pooled usable 1.973505 bpp; 243/243 exact.
- Corrected PPMR: mean usable 2.228173 bpp; pooled usable 2.118172 bpp; 243/243 exact; 238/243 positive-net images.

Optimized single-image CPU E2E:
- 39,655 bits (0.151272 bpp) per full-capacity run.
- Ten warm-up/measurement design: two warm-ups, ten measured repetitions.
- Mean 1.114019 s, SD 0.058079 s, median 1.120437 s.
- Ten distinct nonces and 10/10 exact recoveries.
- Sampled RSS increase 10.87 MiB at 5 ms sampling.

## 5. Important interpretation constraints

1. The 243-image classification is 232 natural-labelled + 11 constructed; a previous draft's 239/4 statement was wrong and has been corrected.
2. The matched-grid predictor comparison uses a step-4/16-phase grid. It is not the native step-2/four-phase EDR2 capacity experiment.
3. The external comparison is matched by source and decoded pixel arrays, not identical protocol, packet, encryption order, authentication, or metadata cost. The rates are native-protocol results, not a same-cost leaderboard.
4. The predictor-only 708.479 ms CNN comparison is the original four-thread harness. The 1.114 s E2E result is the later optimized two-thread end-to-end run; they are different scopes.
5. One 512 × 512 E2E run does not establish multi-resolution scalability.
6. Successful parser and recovery tests are implementation evidence, not a formal cryptographic proof or independent audit.
7. The checkpoint training provenance manifest is still required for submission even though final evaluation performed no retraining.
