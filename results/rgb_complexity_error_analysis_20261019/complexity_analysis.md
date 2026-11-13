# Phase C — Theoretical computational complexity

Derived from the **actual implementations** in `src/` (line references below), not from
generic textbook CNN/predictor estimates. Every parameter count and MAC formula in §C2 was
verified programmatically against the four loaded checkpoints (script: inline check recorded
in `phase_c_run.log`; all four `formula == actual`).

Notation: image H×W, C_ch channel count (1 gray, 3 RGB), P patch size (3/5/7), K=32 CNN
channels, n ∈ {0,…,7} replaceable MSBs per pixel. All complexity statements are **algorithmic**
(counts of primitive operations); measured wall-clock numbers are in `runtime_summary.csv`
and §Runtime of the main report, kept strictly separate.

---

## C1. Classical predictors (as implemented in `src/baselines.py`, `src/rdhei_core.py`)

All four classical predictors are **fully vectorised NumPy**: no Python-level pixel loops.
Per-pixel work is O(1) with small constants, so each predictor is **Θ(H·W)** in pure
operation count — but the constant factors differ, and they differ measurably
(`runtime_summary.csv`, predictor-only group): MED 6.7 ms, CALIC 13.1 ms, GAP 21.3 ms on
512×512 (2026-10-18 protocol, reproduced 2026-10-19).

| Predictor | Neighbours read | Distinct array ops per pixel (counting vector passes) | Boundary handling |
|---|---|---|---|
| MED (`baselines.med_predict`, lines 9–31) | N, W, NW (3) | ~6 (2 min/max, 1 where-chain of 3 comparisons, sums) | first row/col predicted 0 |
| MED pipeline (`rdhei_core.med_predict`, lines 11–35) | N, W, NW (3) | ~6 + np.pad cost | edge pad |
| GAP (`baselines.gap_predict`, lines 34–73) | N, W, NW, NE, WW, NN, NNE (7) | ~20 (2 gradient sums of 3 abs-diffs each, base prediction, 6-deep nested where-chain, clip) | edge pad 2/2/0/1 |
| CALIC (`baselines.calic_predict`, lines 76–118) | N, W, NW, NE, WW, NN, NNE, NNW (8) | ~18 (2 gradient sums, 3 candidate predictors, dh/dv comparison, clip) | edge pad 2/0/1 |

Differences that matter and are **not** captured by “all Θ(HW)”:

1. **Gradient computation**: GAP and CALIC each compute two 3-term gradient sums
   (≈6 abs + 4 adds per pixel); MED computes none. This alone is a ~3–5× operation
   difference and matches the measured MED<GAP/CALIC ordering.
2. **Branch structure**: GAP's prediction is a 6-level nested `np.where` (6 full-image
   comparison passes); CALIC's is 2-level plus 3 candidate predictors; MED's is 3-level.
   NumPy evaluates all branches (no short-circuit), so the branch count multiplies
   full-array passes — the dominant constant factor.
3. **Extra memory traffic**: GAP/CALIC allocate the (H+2)×(W+3) padded array plus ~12
   temporary float32 arrays of H×W; MED allocates ~6. Peak temporary memory is Θ(HW) for
   all four, with GAP/CALIC roughly 2× MED's.

Therefore: **equal asymptotic order Θ(HW), measurably different constants**; assigning all
classical predictors one complexity figure would be wrong.

## C2. CNN predictor (`src/cnn_model.py` CNNPredictor + `src/predictor.py` cnn_predict_map)

### Architecture and exact counts (verified against checkpoints)

Per patch (1×P×P input), with K=32:

| Layer | MACs per patch | Parameters |
|---|---|---|
| conv1: Conv2d(1→K, 3×3, pad 1) | K·9·P² | 9K + K = 320 |
| BN + ReLU | — (2K-scale) | 2K = 64 |
| conv2: Conv2d(K→K, 3×3, pad 1) | K²·9·P² | 9K² + K = 9,248 |
| BN + ReLU | — | 64 |
| res: Conv2d(1→K, 1×1) (if residual) | K·P² | K + K = 64 |
| Linear(K·P² → 128) + ReLU | K·P²·128 | 128·K·P² + 128 |
| Linear(128 → 1) + Sigmoid, ×255 | 128 | 129 |

Total parameters (residual on): **46,881 (P=3), 112,417 (P=5), 210,721 (P=7)**; residual off
at P=5: 112,353. All four verified `formula == checkpoint` exactly.

MACs per patch: **122,816 (P=3), 340,928 (P=5), 668,096 (P=7)**; ~30% of every variant's
MACs are in the first Linear layer.

### Complete predictor cost on an H×W image

The model runs **once per pixel** on its masked patch, so:

- forward-pass MACs = H·W · (K·9·P² + K²·9·P² + [K·P²] + 128·K·P² + 128)
  = **Θ(H·W·P²·(K² + 128))** — the P² dependence is quadratic, so 7×7 costs
  668,096/122,816 ≈ **5.4×** the MACs of 3×3, consistent with measured 5.0× runtime ratio.
- **Patch extraction** (the Python double loop in `cnn_predict_map`, lines 68–88): H·W
  iterations of slice+`.copy()`+append, then one `np.asarray` of the (HW)×P×P array.
  Θ(H·W·P²) in memory writes but with a large per-iteration Python overhead (~µs each).
  This is *work the classical predictors do not have at all*, and measurement (Phase B,
  `improvement_experiments.csv`) shows it is a sizeable share of total CNN time — it can be
  removed by vectorised patch extraction **without changing any arithmetic** (verified
  bitwise-identical predictions on 4 real channels, including the CNN-losing 4.2.07 G).
- **Batching**: batches of 2,048 patches; torch CPU GEMM/conv overhead per batch;
  Θ(H·W/2048) batches. Intermediate activation memory per batch: 2048·K·P²·4 B
  = 2.4 MB (P=3) … 16 MB (P=7); full patch buffer H·W·P²·4 B = 9.4 MB (P=3) … 51.4 MB (P=7).

**Distinguishing the four cost layers** (as required): (1) forward-pass cost
Θ(H·W·P²·(K²+128)) MACs; (2) patch-extraction/preprocessing Θ(H·W·P²) copies plus
Θ(H·W) Python-loop iterations; (3) complete predictor = (1)+(2)+normalisation;
(4) end-to-end RDHEI = predictor + label map + embedding + AES + extraction + recovery
(§C3), of which the per-pixel Python loops typically dominate.

**A smaller parameter count does not imply lower runtime**: parameters count weights, while
runtime is dominated by H·W repeated applications of those weights (MACs) plus Python-loop
overhead; both scale with P², and the Linear layer's 30% MAC share is invisible in a
parameter-only comparison. Measured order (1.71 s / 5.48 s / 8.52 s for P=3/5/7 on 512×512)
tracks MACs, not parameter counts (2.4×/4.5× params vs 3.2×/5.0× runtime from P=3).

## C3. Embedding, encryption, extraction, recovery (`src/rdhei_core.py`, `src/encryption.py`)

Let N = H·W·C_ch pixels, and n_i ∈ {0,…,7} the label of pixel i from
`generate_label_map_fast` (which itself is **vectorised**: 7 full-array passes → Θ(N) with
a ~7× constant, measured in `runtime_summary.csv` stage group).

| Stage | Implemented as | Complexity | Practical bound |
|---|---|---|---|
| Label map (`generate_label_map_fast`, lines 130–213) | 7 vectorised passes | Θ(7·N) | no Python loop; ~10–30 ms per 512×512 channel |
| Embedding (`sender_embed_encrypt`, lines 300–340) | **Python loop over N pixels**; per embedded pixel a further loop over its n_i bits (`_embed_pixel`) | Θ(N + Σ n_i) Python iterations | Σ n_i ≈ 4.9·N bits on the benchmark; ~3.4 s per 512×512 gray image measured |
| AES-CTR encrypt/decrypt (`encryption.py`, PyCryptodome C impl) | whole-array | Θ(N) bytes, C-speed | ~50–150 ms per 512×512 channel |
| Extraction (`receiver_extract_recover`, lines 380–430) | Python loop; per pixel with n_i>0 reads n_i bits until payload_len collected | Θ(N + payload_len) | extraction stops early once payload_len reached, but the pixel loop **continues** (post-fix `05f4e69`) |
| Recovery (`_recover_pixel`, lines 258–296) | per pixel with n_i>0, enumerate 2^{n_i} candidates | Θ(Σ_{i: n_i>0} 2^{n_i}) | **worst-case per pixel 2⁷ = 128**; but 2^{n_i} ≤ 2·(n_i+1)·…, and the observed label distribution (`label_histograms.csv`) is concentrated at n=4..6, so practical per-pixel work ≈ 16–64 candidate tests; overall ~3.7 s per 512×512 gray image measured |

Two structural observations:

1. **The 2^n candidate scan is not uniformly 128**: pixels with n=7 (|e|=0) do enumerate
   128 candidates, but such pixels are only ~4–10% (CNN/GAP), and |e|≥128 pixels (n=0) do
   **zero** extra work. The expected candidate count is Σ_n frac(n)·2^n, computable from
   `label_histograms.csv` (e.g., ~25 candidates/pixel for CNN-3×3 pooled RGB — an order of
   magnitude below the 128 worst case). The fallback (no valid candidate → return stego
   value) never fires for embedded pixels (exhaustive Day-1 audit).
2. **RGB multiplies everything by C_ch=3 with no cross-channel sharing**: three independent
   prediction maps, three label maps, three payloads, three nonces; complexity is exactly
   3× grayscale for every stage, and the per-pixel Python loops run 3× as many iterations.
   This is a constant-factor change (C_ch is bounded), so the asymptotic per-stage orders
   above carry over to RGB unchanged.

**Asymptotic summary**: every stage is Θ(N) (N = H·W·C_ch) with constant factors spanning
three orders of magnitude — vectorised NumPy (label map, classical prediction), C library
(AES), and Python per-pixel loops (embedding, extraction, recovery) — plus the CNN's
Θ(N·P²·(K²+128)) MAC term. End-to-end runtime is therefore **not** predicted by predictor
choice alone; measurement of each stage separately (Phase D) is required, which is what
`runtime_summary.csv` provides.
