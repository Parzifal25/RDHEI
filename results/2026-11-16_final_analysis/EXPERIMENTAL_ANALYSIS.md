# Experimental analysis — EDR2 grayscale and CC-EDR2-RGB

**Analysis date:** 2026-11-16  
**Checkpoint:** frozen CNN v4_patch3, 46,881 parameters  
**Model training/fine-tuning during the reported evaluation:** none.

## 1. Experimental design and scope control

Three datasets/experiment gates contribute to this report. They answer different questions and are not pooled into a single score.

| Gate | Corpus | Predictor/protocol comparison | Primary purpose |
|---|---:|---|---|
| Native grayscale EDR2 | 243 native grayscale USC-SIPI images | Frozen proposed 3×3 CNN under four-phase step-2 safe lattice | End-to-end EDR2 feasibility and exact recovery |
| Matched grayscale predictor evaluation | Same 243 curated grayscale images | MED, GAP, simplified CALIC-style, five CNN checkpoints, and separate histogram-shift reference; common step-4 / 16-phase comparison grid | Predictor baseline and CNN ablation comparison |
| Native RGB CC-EDR2-RGB | 51 native 8-bit RGB images | Four spatial/cross-channel blend settings × 24 ordered phase assignments | Exploratory RGB feasibility and blend/phase ablation |

The native grayscale EDR2 run uses the active four-phase maximum-density safe lattice (step 2, predictor radius 1). The matched predictor comparison uses a more conservative common step-4, 16-phase grid so all predictor variants can be compared under the same candidate geometry. The resulting positive-image counts (163 and 133 for v4 respectively) are different estimands and must remain attached to their respective experiment definitions.

## 2. Native grayscale EDR2 end-to-end evaluation

The curated grayscale corpus contains 243 unique native 8-bit grayscale images from 250 TIFF candidates. Five candidates were excluded under the documented catalogue rules and two decoded-pixel duplicates were removed. The final hash-pinned native EDR2 allowlist classifies 239 records as natural and four as constructed texture mosaics. The earlier matched-predictor run used the same exact set of 243 decoded-pixel hashes but an earlier curation-label version (232 natural / 11 constructed); the source image set is identical, and the matched-predictor stratification has now been recomputed against the final native allowlist. The 243 images are not 243 independent samples: the matched-run provenance manifest retains 29 correlation clusters covering texture families and image sequences.

| Measure | Result |
|---|---:|
| Native grayscale images | 243 |
| Positive signed net capacity | 163/243 (67.1%) |
| Nonpositive signed net capacity | 80/243 |
| Exact image and payload round-trips | 978/978 |
| Round-trip failures | 0 |
| Pooled signed net capacity | 0.059821 bpp |
| Unweighted mean per-image signed net capacity | 0.110540 bpp |

The pooled bpp is total signed net payload divided by total pixels across the corpus. The unweighted per-image mean gives every image equal weight. They are not interchangeable. Signed net capacity includes negative outcomes; a negative value means protocol overhead exceeds available ordinary payload slots for that image. The 978/978 round-trip result is conditional on accepted positive-capacity cases and does not turn the 80 nonpositive cases into successful payload carriers.

The native run records no training or model change and verifies the frozen checkpoint SHA-256 shown above.

## 3. Matched grayscale baselines

All predictors in this comparison use the same 243 input images and the same conservative step-4 / 16-phase comparison grid. Positive-net coverage is the fraction of corpus images for which the method yields a positive signed net payload after the method's stated overhead accounting. MAE is averaged over the candidate predictions under the matched comparison protocol. The reported signed net bpp is averaged across the valid per-image rows, including negative capacities.

| Method | Positive images | Coverage | Mean signed net bpp | Mean candidate MAE |
|---|---:|---:|---:|---:|
| MED | 49/243 | 20.2% | -0.013890 | 7.9503 |
| GAP | 58/243 | 23.9% | -0.013760 | 7.8408 |
| Simplified CALIC-style | 49/243 | 20.2% | -0.015780 | 8.2021 |
| CNN v1, 5×5 full | 138/243 | 56.8% | 0.025344 | 4.6324 |
| CNN v2, 5×5 no residual | 139/243 | 57.2% | 0.023831 | 4.6573 |
| CNN v3, 5×5 no weighted loss | 140/243 | 57.6% | 0.025864 | **4.6233** |
| **CNN v4, proposed 3×3** | **133/243** | **54.7%** | **0.021603** | **4.8130** |
| CNN v5, 7×7 | 140/243 | 57.6% | 0.025029 | 4.6882 |
| Histogram-shift reference | 235/243 | 96.7% | 0.025019 | N/A |

The 3×3 v4 model substantially improves matched prediction MAE and positive-capacity coverage relative to the three classical predictor implementations. The approximate reduction in mean candidate MAE versus MED, GAP and simplified CALIC-style is 39.5%, 38.6% and 41.3%, respectively. It does not lead the CNN ablation table: v3 has the lowest MAE (4.6233), the highest CNN positive count (140), and the highest mean signed net bpp (0.025864) in this matched comparison. v4 is retained as the proposed configuration because it is a smaller 3×3 model with a more favourable compute footprint, not because it is the best predictor on every reported metric.

The histogram-shift result is a separate plaintext-before-AES reference, with a different embedding construction and overhead path. Its 235/243 positive count is context only; it is not a like-for-like encrypted-domain predictor baseline. Likewise, the CALIC implementation is simplified CALIC-style, not a claim of testing the full canonical CALIC algorithm.

### 3.1 Cluster-aware inference

To reduce pseudo-replication from repeated texture series and image sequences, the matched comparison was additionally analysed using a cluster bootstrap over the 29 curator-defined provenance/correlation clusters. Ten thousand bootstrap resamples were generated with seed 20261116. The bootstrap resamples clusters as blocks rather than treating all images as independent observations. These intervals are exploratory and conditional on the correctness and granularity of the curator-defined clusters.

**Difference in positive-capacity coverage: v4 minus comparator**

| Comparator | Difference | 95% cluster-bootstrap interval |
|---|---:|---:|
| MED | +0.3457 | [+0.2038, +0.5263] |
| GAP | +0.3086 | [+0.1698, +0.4926] |
| Simplified CALIC-style | +0.3457 | [+0.2028, +0.5305] |
| CNN v3 no weighted loss | -0.0288 | [-0.0878, +0.0258] |

The cluster-bootstrap intervals support a positive coverage difference for v4 against MED, GAP and the simplified CALIC-style implementation. They do not establish a positive coverage difference against v3. The v4–v3 interval includes zero.

**Paired candidate-MAE difference: v4 minus comparator**

| Comparator | Mean paired difference | 95% cluster-bootstrap interval |
|---|---:|---:|
| MED | -3.1373 | [-4.1318, -2.3638] |
| GAP | -3.0277 | [-3.9985, -2.2447] |
| Simplified CALIC-style | -3.3890 | [-4.4264, -2.5763] |
| CNN v3 no weighted loss | +0.1897 | [+0.1017, +0.2735] |

Negative means v4 has lower MAE. The positive v4-minus-v3 interval indicates v3 has lower MAE than v4 under this comparison. Avoid presenting ordinary image-level paired tests as cluster-adjusted; the recorded Wilcoxon/McNemar tests are unadjusted image-level supplements and should not be the headline inferential evidence.

## 4. Grayscale dataset stratification

The following v4 strata are descriptive. The corpus contains correlated groups and small strata; these summaries do not demonstrate that a specific image property causes positive capacity.

### 4.1 Natural versus constructed labels

| Corpus label | Images | Positive-net v4 images | Coverage | Mean candidate MAE | Mean signed net bpp |
|---|---:|---:|---:|---:|---:|
| Natural-image records | 232 | 130 | 56.0% | 4.5921 | 0.023646 |
| Constructed texture mosaics | 11 | 3 | 27.3% | 9.4725 | -0.021485 |

“Natural” includes sequences and texture families, not solely independent photographic scenes. The natural/constructed distinction is a catalogue label rather than a randomized treatment.

### 4.2 Provenance groups and resolution

The following subgroup values are recalculated from the matched per-image v4 results after joining by decoded-pixel SHA-256 to the final native EDR2 manifest:

| Final native-manifest group | Images | Positive | Coverage | Mean MAE | Mean signed net bpp |
|---|---:|---:|---:|---:|---:|
| Rotated texture series | 91 | 78 | 85.7% | 3.2107 | 0.033632 |
| Texture scans and mosaics (natural-labelled) | 58 | 15 | 25.9% | 8.4192 | -0.018010 |
| Monochrome sequence frames | 67 | 26 | 38.8% | 3.2924 | 0.048552 |
| Miscellaneous monochrome | 22 | 14 | 63.6% | 4.3335 | 0.009681 |
| Monochrome aerial | 1 | 0 | 0.0% | 6.2384 | -0.017888 |
| Constructed texture mosaics | 4 | 0 | 0.0% | 16.7278 | -0.053614 |

By resolution:
- 256×256: 18/62 positive (29.0%), mean signed net 0.026177 bpp, median -0.013206 bpp;
- 512×512: 105/152 positive (69.1%), mean signed net 0.024963 bpp, median 0.022926 bpp;
- 1024×1024: 10/29 positive (34.5%), mean signed net -0.005787 bpp, median -0.008533 bpp.

Resolution bins and corpus groups are descriptive; neither establishes a causal relationship with capacity. The natural/constructed labels are now tied to the final hash-pinned allowlist, while the cluster-bootstrap analysis still resamples the 29 provenance clusters from the same exact pixel-hash set.

## 5. Native RGB CC-EDR2-RGB evaluation

The RGB corpus comprises 51 native uint8 RGB images: 37 aerial-colour images and 14 miscellaneous-colour images. All 51 source and decoded-pixel hashes were distinct. No inputs were skipped or silently converted, cropped or resized. The fixed grayscale v4 checkpoint was reused independently on R, G and B; no RGB retraining occurred.

For each image and each cross-channel blend setting, all 24 ordered assignments of three distinct safe-grid phases to R/G/B were evaluated; the remaining fourth phase was reserved for calibration. This yields 204 image/blend rows and 4,896 assignment scores.

### 5.1 Blend ablation and capacity coverage

| Cross-channel contribution | Directory-fit images | Positive-net images | Nonpositive among fits | No directory fit | Mean signed net bpp among fit images |
|---|---:|---:|---:|---:|---:|
| 0/4 (spatial only) | 3 | 3 | 0 | 48 | 1.556988 |
| 1/4 | 3 | 3 | 0 | 48 | 0.803504 |
| 2/4 | 6 | 5 | 1 | 45 | 0.404195 |
| 3/4 | 8 | 7 | 1 | 43 | 0.367307 |

Seven of 51 images achieved positive capacity under at least one blend; 44 had no positive-net configuration. The 0/4 condition has the highest fit-only mean net bpp, but it is based on just three images. The 3/4 setting reaches the broadest positive coverage (7 images), while its fit-only average signed net bpp is lower. Each mean is conditional on bootstrap-directory fit; images without a fitting directory have no numeric capacity row and are not set to zero.

This is a coverage-versus-conditional-capacity trade-off. The results do not support the claim that increasing cross-channel blend uniformly improves payload capacity. The 3/4 setting brings additional images into the feasible set but has a lower mean capacity among its fit images.

### 5.2 Adaptive 24-phase assignment versus the fixed assignment

For each image/blend pair whose encrypted bootstrap directory fitted, the 24 ordered R/G/B phase permutations were compared with the fixed assignment \((q_R,q_G,q_B)=(0,1,2)\). The adaptive choice is the feasible assignment with the largest signed net capacity. The comparison is per image and blend; it is not an aggregate claim that every image gains capacity.

| Blend | Directory-fit pairs | Positive-net pairs | Mean gain over fixed assignment | Median gain | Maximum gain |
|---|---:|---:|---:|---:|---:|
| 0/4 | 3 | 3 | 970.3 bits | 963 bits | 1,550 bits |
| 1/4 | 3 | 3 | 1,223.3 bits | 928 bits | 2,315 bits |
| 2/4 | 6 | 5 | 567.2 bits | 415.5 bits | 1,445 bits |
| 3/4 | 8 | 7 | 1,543.1 bits | 1,077.5 bits | 4,520 bits |

The 24-assignment search improved or preserved the fixed assignment's net capacity for every directory-fit image/blend pair in this audit. At 2/4 and 3/4, one directory-fit pair in each blend remained nonpositive after adaptive selection; an improved negative signed net is still not a payload-carrying outcome. The 44 images without any directory fit remain feasibility failures, not zero-capacity observations. The complete assignment-level scores are retained in the Run #79 raw evidence; the committed summary table records the per-blend paired comparison.


### 5.3 RGB stratification

All positive-net RGB cases occurred in the 14-image miscellaneous-colour group. None of the 37 aerial-colour images yielded a positive-net packet under any tested blend. At 3/4, 7/14 miscellaneous-colour images (50%) were positive, compared with 0/37 aerials.

Resolution-specific positives at 3/4 were 5/8 for 256×256, 2/18 for 512×512, 0/24 for 1024×1024 and 0/1 for 2250×2250. This is a sample-specific pattern; resolution is confounded with corpus group and image content. It is not evidence of a general resolution law.

### 5.4 Exact receiver recovery

For each positive image/blend pair, nine payload sizes were tested: empty, 1, 7, 8, 9, 37 and 137 bits, near capacity, and full capacity. Across the four blends:
- 162/162 image and payload round-trips passed exactly;
- 162 independent receiver subprocesses were used;
- 162 unique deterministic experiment nonces were recorded;
- no round-trip failures occurred;
- independently reparsed per-case receiver evidence shows zero forbidden source reads.

The 162/162 denominator is 162 tests over positive-capacity image/blend pairs (3 + 3 + 5 + 7 pairs × 9 payloads); it is not 162 independent corpus images. The guarded Python open audit is not an OS sandbox.

### 5.4 Audit-counter correction

The original Run #79 top-level summary recorded 162 receiver source-access violations. The per-case receiver audit CSV stores `source_reads` as a serialized JSON array. The original aggregator applied Python `bool()` to the nonempty string `"[]"`, which evaluates to true. Independent parsing of all 162 raw case records found `source_access=false` and `source_reads=[]` in every case. The corrected count is zero.

The original artifact remains unchanged. The corrected summary and analysis are separate normalized outputs committed with this report. The runner and report aggregation logic were corrected after Run #79. This correction fixes an aggregation error; it does not weaken or reinterpret any actual receiver case record.

## 6. Reproducible complexity and runtime

The corrected Run #90 benchmark ran on a CPU-only Linux CI runner with four threads. The input was a deterministic 512×512 uint8 synthetic grayscale image (seed 20261116; SHA-256 `72d617e07df21265e3ffe6703b613b1988d0c88084cab5e098781780562d9c25`). Each method used five warmups and ten timed repetitions in a fresh worker process.

| Method | Parameters | MACs/patch | FLOPs/patch | Mean full-map predictor ms | Sampled peak RSS delta MiB |
|---|---:|---:|---:|---:|---:|
| MED | 0 | N/A | N/A | 3.826 | 4.383 |
| GAP | 0 | N/A | N/A | 11.242 | 10.414 |
| CALIC | 0 | N/A | N/A | 7.257 | 8.691 |
| CNN 3×3 v4 | 46,881 | 122,816 | 245,632 | 708.479 | 23.898 |
| CNN 5×5 v1 | 112,417 | 340,928 | 681,856 | 1,427.148 | 48.633 |
| CNN 5×5 v2 | 112,353 | 340,128 | 680,256 | 1,275.584 | 29.934 |
| CNN 5×5 v3 | 112,417 | 340,928 | 681,856 | 1,437.796 | 36.148 |
| CNN 7×7 v5 | 210,721 | 668,096 | 1,336,192 | 3,041.136 | 103.086 |

The CNN FLOP count includes Conv2d and Linear layers only, with one MAC counted as two FLOPs. It excludes bias additions, BatchNorm, nonlinearities, output scaling, patch extraction and memory copies, NumPy preprocessing and Python overhead. It is a declared analytical count, not a total hardware instruction count.

For a complete 512×512 prediction map, v4 computes 64,390,955,008 counted FLOPs. The EDR2 safe-lattice accounting is separate: 65,025 candidates per phase, 7,986,110,400 MACs for one phase and 31,944,441,600 MACs (63,888,883,200 counted FLOPs) for four phases. The step-2 lattice calculation applies to the 3×3 predictor only.

The v4 predictor takes 708.479 ms per full map in this benchmark, compared with 3.826 ms for MED (approximately 185.2× slower). It is the least expensive of the CNN checkpoints but is not lightweight relative to the classical predictors. It uses 58.3% fewer parameters than the 5×5 v1/v3 models and 77.8% fewer than the 7×7 v5 model. RSS is sampled every 5 ms relative to the post-warmup baseline and may miss short-lived peaks.

These timings are predictor-only: embedding, AES, extraction and recovery are excluded. They include the repository predictor's patch extraction/preprocessing path. The deterministic synthetic CI benchmark must not be directly compared with earlier Lena/WSL timings.

A second predictor-only rerun in final closure Run #103 measured MED at 4.224 ms and v4 at 1,111.136 ms. The v4 sample standard deviation was 380.44 ms, including a 2,166 ms outlier. This corresponds to approximately 263× MED runtime in that run. Run #90 and Run #103 are retained separately rather than averaged because the v4 timings vary materially; see tables/complexity_repeat_comparison.csv. This reinforces the need for profiling, optimisation and additional repeated measurements.

## 7. Overall findings and claims allowed

Evidence supports the following carefully scoped statements:

1. The native grayscale EDR2 implementation achieved positive signed net payload on 163/243 curated grayscale inputs and exact recovery in all 978 attempted positive-capacity round-trip trials.
2. In the separate matched predictor comparison, the 3×3 CNN has substantially greater positive-net coverage and lower prediction MAE than MED, GAP and the simplified CALIC-style implementation.
3. The 3×3 v4 model is not the top CNN variant by prediction accuracy or matched positive count; v3 is better on those measures. v4 is the smaller CNN configuration with lower counted model compute.
4. The RGB extension demonstrates successful authenticated packet round-trips on positive-capacity samples, but positive coverage is sparse (7/51 images under at least one tested blend).
5. Adaptive 24-assignment search and blend ratio are fully enumerated in the RGB experiment, but blend fusion did not demonstrate uniformly higher per-image net capacity than spatial-only prediction.
6. The benchmark exposes a major CPU-runtime cost for CNN inference relative to the classical methods.
7. The implementation includes authenticated packet checks and domain-separated key derivation, but the project does not yet possess an independent cryptographic security audit or formal proof.

## 8. External literature comparison gap

The current predictor comparison is limited to MED, GAP, a simplified CALIC-style implementation and five CNN checkpoints. It omits the closest checkerboard ACBP, asymmetric-CNN/adaptive-mean RDHEI, pixel-level masked-autoencoder RDHEI and BCAGC methods. This is a material gap.

Yi and Zhou's 2018 ACBP predicts three-quarters of pixels from a one-quarter reference set and uses adaptive bit-level embedding; the 4.5 bpp point is at ε=255, whereas exact reversibility is reported at ε=1. Ping et al. (2024) already use an asymmetric CNN predictor for RDHEI. Cheng et al. (2025) use a pixel-level masked autoencoder in VRAE RDHEI. Zhou et al. (2026) report 4.1472, 4.0565 and 3.4465 bpp on BOSSbase, BOWS-2 and UCID for BCAGC. Peng et al. (2026) describe a further RRBE design using prediction errors, dual-stage bit-plane compression, adaptive hierarchical block variable-length coding, capacity-aware block rearrangement and CP-ABE recovery authorization, also evaluated on BOSSBase, BOWS-2 and UCID. The numeric results for Peng et al. must be extracted from the full article before comparison. Published rates cannot be directly compared with our signed-net measurements without reconciling datasets, embedding/encryption order and every header, directory, backup and authentication cost. The large numerical gap makes normalized replication a high-priority requirement.

The narrow novelty candidate is deterministic local inference-input invariance of the frozen centre-masked 3×3 CNN under a separated step-2 phase, together with explicit four-phase net-overhead selection. The quarter-grid/checkerboard idea, bit replacement, CNN predictors for RDHEI and masked-pixel prediction are prior art. A first-of-kind or state-of-the-art claim is unsupported by current evidence.

## 9. Remaining experimental work before submission

- Produce a locked manuscript dataset table that includes image-size distribution, source/provenance family, grayscale/RGB exclusions and licences/copyright checks.
- Run an externally reviewed security assessment covering custom key derivation, nonce management, authentication order, tampering, hider key custody and failure behaviour.
- Add adversarial robustness tests: truncated/oversized packet fields, malformed zlib streams, corrupted tag/header/directory, payload length boundaries, phase ambiguity, wrong key/nonce, and mutation of every authenticated region.
- Quantify end-to-end throughput and memory for the active EDR2 protocol, separately from full-map predictor-only timing.
- Conduct a true paired RGB fixed-versus-adaptive ablation report with per-image paired deltas and uncertainty estimates; preserve failure cases and report feasibility, not only conditional means.
- Confirm canonical baseline implementations and describe simplifications; ideally add a full CALIC implementation or rename the comparison explicitly throughout.
- Verify image rights and citation requirements before reproducing USC-SIPI source imagery.
