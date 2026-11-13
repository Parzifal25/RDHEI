# RGB_Complexity_Error_Analysis.md

**CNN-Based Reversible Data Hiding in Encrypted Images using Bit-Plane Replacement**
Companion analysis report — 2026-10-19
All artifacts: `results/rgb_complexity_error_analysis_20261019/` (all paths below relative to it)

**Status: PARTIALLY VALIDATED** — all planned analyses were executed and inspected on real
benchmark images; the mandated *independent-model* review was not available in this
environment, so a systematic programmatic self-audit was executed instead and is recorded
in §9. `Final_report.md` (2026-10-18) remains the authoritative technical record; this
report adds no contradictory numbers — every baseline value was independently reproduced.

---

## 1. Executive summary

1. **Baseline fully reproduced.** All 410 per-image/per-channel MAE and BPP values for
   MED, MED-pipeline, GAP, CALIC, CNN-3×3 and the four CNN ablations were recomputed from
   the authoritative `src/` + checkpoints and matched the stored 2026-10-18 CSVs
   (`baseline_reconciliation.csv`; worst |diff| ≈ 1e-6).
2. **CNN-3×3 loses in exactly 5 of 15 genuine-RGB channels** (and in 1 of 6 grayscale
   images): 4.2.06 R/G, 4.2.07 R/G/B, and Peppers (gray), always to GAP
   (`underperformance_diagnosis.csv`). On three of these five channels the CNN has the
   *lower* MAE yet the *lower* BPP — an effect fully explained by the label map's reward
   structure (§5), not by any defect.
3. **No capacity-improving change was found that preserves the method.** Options 1–3 were
   executed: no correctness defect exists; no alternative checkpoint beats GAP where
   CNN-3×3 loses; the only legitimate improvement is a **semantics-preserving
   implementation speedup** (vectorized embedding/recovery/patch extraction, bitwise- or
   output-identical, 88/88 fast-path e2e PASS) that changes no metric, only runtime.
4. **Complexity:** every classical predictor is Θ(HW) with very different constants
   (GAP reads 7 neighbours and runs a 6-deep full-array branch chain; MED reads 3); the
   CNN is Θ(HW·P²·(K²+128)) MACs plus Θ(HW) Python-loop patch extraction; embedding and
   recovery are Θ(HW·C_ch) **Python per-pixel loops** that dominate end-to-end time.
5. **Runtime (clean protocol, 2026-10-19):** CNN-3×3 prediction 2082 ms vs MED 6.4 ms
   per 512×512 (325×); the vectorized predictor cuts it to 1761 ms (−15%), the
   vectorized embedder cuts embed+encrypt 43×, the vectorized receiver cuts
   extract+recover ~2.2×; total pipeline on 4.2.03 RGB with CNN-3×3:
   **15.5 s → 10.3 s** with byte-identical outputs.
6. **Error distributions explain the BPP results:** the CNN concentrates more probability
   mass at small |e| (−18.4% MAE vs GAP on RGB), but capacity is a step function of |e|
   with a 7-bit reward at |e|=0 and a cliff at |e|≥128; GAP's heavier mass at exactly
   |e|=0 is why it wins BPP on some channels despite higher MAE (§5).

---

## 2. Baseline findings (Phase A)

- **RGB benchmark (n=5 genuine):** 4.2.03, 4.2.05, 4.2.06, 4.2.07, lena — all 512×512×3,
  mode RGB, non-identical channels; `images.png` (225×225, mode L) excluded from all RGB
  aggregates, consistent with the authoritative run.
- **Grayscale benchmark (n=6):** Airplane, Baboon, Goldhill, Jetplane, Lena, Peppers.
- Recomputed RGB mean-over-channels BPP: **CNN-3×3 4.8838, GAP 4.7867, MED-pipeline
  4.7175, MED-baseline 4.6984, CALIC 4.6218**; gray: CNN-3×3 5.1897, GAP 5.0266.
  RGB MAE mean: CNN-3×3 6.5558 (−18.4% vs GAP 8.0303); gray: 4.4615 (−24.5% vs GAP 5.9096).
- Full tables: `rgb_per_image_comparison.csv`, `rgb_per_channel_comparison.csv`,
  `gray_per_image_comparison.csv`; reconciliation: `baseline_reconciliation.csv`,
  `phase_a_log.md` (410/410 match, 0 mismatch, 0 missing).
- The example cited in the task brief was verified: on 4.2.07, GAP = 4.8622 >
  CNN-3×3 = 4.7330 (mean over channels), reproduced from source and from the stored CSV.

Per-image RGB BPP difference (CNN-3×3 − GAP): 4.2.03 **+0.2407** (+6.05%), 4.2.05
**+0.2335** (+4.32%), 4.2.06 **+0.0029** (+0.06%), 4.2.07 **−0.1292** (−2.66%), lena
**+0.1374** (+2.70%). Mean **+0.0971** (+2.03%). The CNN wins 4/5 images; the mean-level
advantage is **not** universal superiority (see §8).

---

## 3. CNN ablations (Options 2, recomputed)

All five checkpoints were re-evaluated on all 15 RGB channels with identical definitions
(rows in `prediction_error_statistics.csv` with method CNN5x5/CNNNoResidual/CNNNoWeighted/
CNN7x7). CNN-3×3 remains best in mean RGB BPP (4.8838) and MAE (6.5558); the stored
ranking of `Final_report.md` §8.7 is reproduced. **On each of the five channels where
CNN-3×3 loses to GAP, every alternative CNN checkpoint also loses to GAP** (e.g. 4.2.07 G:
GAP 4.9630 vs best-CNN 4.8425). No silent substitution was made; CNN-3×3 stays the
proposed configuration.

---

## 4. Legitimate RGB improvement opportunities — outcomes (Phase B)

| Option | What was checked | Outcome |
|---|---|---|
| 1. Correctness audit | RGB channel handling, normalization/rounding (`np.round(pred)`), reflect padding, label-map generation (fast vs reference, tests/), aggregation convention, checkpoint loading, dtype conversions, boundary conditions | **No defect found.** The two MED variants and the first-row/col zero convention of the *baseline script* are documented differences, not defects. No source change made. |
| 2. Existing checkpoints | 5 checkpoints × 15 channels, identical definitions | CNN-3×3 is the best CNN everywhere aggregate; no checkpoint fixes the losing channels (§3). No replacement made. |
| 3. Implementation improvements | Vectorized patch extraction; vectorized MSB embedding; vectorized candidate recovery | **Improvement found and validated** (below). Predictions bitwise-identical; stego/extracted/recovered outputs identical; 88/88 fast-path e2e PASS. |
| 4. New method variant | — | **Not pursued.** After Options 1–3, no defensible capacity gain was available that does not require retraining (which requires approval and was not requested). |

### 3-vs-original fair comparison (identical images, payloads, aggregation, hardware)

| Metric | Original CNN-3×3 | Vectorized variant | Difference |
|---|---|---|---|
| RGB mean BPP | 4.8838 | 4.8838 (same label maps; same predictions bitwise) | 0 |
| RGB prediction MAE | 6.5558 | 6.5558 | 0 |
| Per-image/channel BPP | as §2 | identical | 0 |
| Exact image recovery | tested | **88/88 PASS** (6 gray + 5 RGB × 2 predictors × 4 payload rules) | pass |
| Exact payload recovery | tested | **88/88 PASS** (bit-exact, length-checked, independent of pipeline flags) | pass |
| Predictor runtime (Lena) | 2082.2 ± 186.6 ms | 1761.1 ± 230.3 ms | −321.1 ms (−15.4%) |
| Embed+encrypt (4.2.03 RGB, full payload) | 3635.2 ms | 98.7 ms | −97.3% |
| Decrypt+extract+recover (4.2.03 RGB) | 7488.4 ms | 3597.1 ms | −52.0% |
| TOTAL pipeline (4.2.03 RGB, CNN-3×3) | 15 504.5 ms | 10 317.4 ms | −33.5% |
| TOTAL pipeline (Airplane gray, MED) | 4665.7 ms | 1622.0 ms | −65.2% |
| Parameters | 46 881 | 46 881 (unchanged) | 0 |

Equivalence evidence: predictions bitwise-equal (max |Δ| = 0) on 4 real channels incl.
4.2.07 G; encrypted stego, extracted bits, and recovered image all identical vs the
authoritative loops on 4 images × {max, quarter} payloads (`improvement_experiments.csv`).
The variant lives only in this analysis directory (`fast_impl.py`); `src/` is untouched,
so this is a *proposal*, ready to be adopted after the student's own review.

---

## 5. Prediction-error distributions and how they determine BPP (Phases B1+E)

Signed error convention, verified against the implementation: `e = I − round(Î)`;
capacity uses only `|e|` through `generate_label_map_fast`.

Files: `prediction_error_statistics.csv` (159 rows: mean signed error, MAE, median, std,
p75/p90/p95/p99, max, frac zero, frac ≥128, per-label fractions, boundary masses),
`histogram_bins.csv` (122 271 rows, fixed width-1 bins), `label_histograms.csv`
(per-channel n=0..7 counts), figures `fig_err_*.png`, `fig_label_counts_pooled_rgb.png`.

### The label map's reward structure (measured, per pixel)

| \|e\| | 0 | 1 | 2–3 | 4–7 | 8–15 | 16–31 | 32–63 | 64 | 65–127 | ≥128 |
|---|---|---|---|---|---|---|---|---|---|---|
| label n (bits) | 7 | 6 | 5 | 4 | 3 | 2 | 1 (+1 accumulated) | **0** | 1 | **0** |

So capacity is a **staircase with a 7-bit bonus for exact prediction and two dead zones**
(|e| = 64 and |e| ≥ 128). Two consequences, both confirmed by the data:

1. **Lower MAE does not imply higher BPP.** On 4.2.07 B, CNN-3×3 MAE 5.300 < GAP 5.826,
   yet BPP 4.940 < 4.971: GAP puts 9.93% of pixels at exactly |e|=0 (n=7) while the CNN
   puts only 6.09%; the CNN's errors are tighter overall but rarely *exactly* zero. Same
   pattern on 4.2.06 R/G. Pooled over the 15 RGB channels, GAP and CNN both reach 8.68% at
   |e|=0 — the CNN's wins come from converting GAP's mid-range mass (|e|=8..63) into
   |e|=4..7 and from eliminating the n=0 tail (|e|≥128: 0.20% GAP vs **0.009%** CNN).
2. **Where the CNN genuinely predicts worse, it loses honestly.** On 4.2.07 R the CNN has
   both higher MAE (8.593 vs 7.481) and lower BPP (−0.236); its label mass shifts from
   n=5/6 into n=4. No boundary artifact is involved (mass at |e|=63/64/65 is ≤0.006% for
   all predictors — the |e|=64 dead zone is real but practically negligible here).

Per-image figures: `fig_err_perimage_4_2_07_png.png` (CNN loses), 
`fig_err_perimage_4_2_05_png.png` (CNN wins clearly); pooled per-channel signed
histograms and ECDFs: `fig_err_signed_rgb_pooled.png`, `fig_err_ecdf_rgb_pooled.png`;
ablation comparison on 4.2.07 R: `fig_err_ablation_4207_R.png`. Channels are always
shown separately or explicitly labelled as pooled — never silently merged.

### Recovery cost link

Expected candidate tests per pixel under the observed label distributions (Σ frac(n)·2ⁿ):
MED 38.3, GAP 40.1, CALIC 36.8, **CNN-3×3 41.3** — against a worst case of 128. The CNN's
higher n=7 fraction slightly *increases* per-pixel recovery work; the capacity winner is
also the most recovery-expensive of the four, by ~8% over MED.

---

## 6. Theoretical complexity (Phase C) — `complexity_analysis.md`

Verified against the checkpoints: parameter formulas reproduce 46 881 / 112 417 / 112 353 /
210 721 exactly; MACs per patch 122 816 / 340 928 / 668 096 (P=3/5/7), ~30% in the first
Linear layer. Highlights:

- Classical predictors: all Θ(HW) but with measured, materially different constants —
  MED reads 3 neighbours; GAP reads 7, computes two 3-term gradients and a 6-deep
  full-array `np.where` chain; CALIC reads 8 neighbours. Measured 6.4 / 20.3 / 11.0 ms.
- CNN: Θ(HW·P²·(K²+128)) MACs **plus** Θ(HW) Python-loop patch extraction — the latter is
  a cost the classical predictors do not have, and it is what the Option-3 vectorization
  removes (bitwise-identical, −15% predictor time; the forward pass, not extraction,
  dominates the remaining 1.76 s).
- Embedding/extraction/recovery are Python per-pixel loops: Θ(HW·C_ch) loop iterations
  with Σn_i bit operations and Σ2^{n_i} candidate tests. Recovery's per-pixel bound is
  2⁷=128 but the *measured* expectation is ~36–41 tests/pixel (§5).
- A smaller parameter count does not imply lower runtime: runtime tracks MACs (P² scaling:
  measured 2082 / 5321 / 15623 ms for P=3/5/7), not the 2.4×/4.5× parameter ratios.

---

## 7. Runtime measurement (Phase D)

Protocol identical to the validated `fv_e_runtime.py`: Lena 512×512 gray, CPU, warm-up 5,
10 timed repeats, `perf_counter`, model loading excluded; stage-wise: Airplane gray +
4.2.03 RGB, full-capacity payload, 3 repeats, disjoint boundaries
(label_map | embed | encrypt | decrypt | extract+recover | TOTAL).

Predictor-only (this host, 2026-10-19; `runtime_summary.csv`, `runtime_raw.csv`):

| Method | mean ms | std | vs CNN-3×3 |
|---|---:|---:|---|
| MED | 6.40 | 0.89 | 325× faster |
| CALIC | 10.97 | 1.42 | 190× |
| GAP | 20.33 | 3.43 | 102× |
| CNN-3×3 | 2082.2 | 186.6 | 1× |
| CNN-3×3 vectorized | 1761.1 | 230.3 | 0.85× |
| CNN-NoResidual (5×5) | 3257.7 | 150.5 | 1.56× |
| CNN-5×5 | 5320.8 | 2054.8 | 2.56× |
| CNN-NoWeighted (5×5) | 6184.6 | 1945.2 | 2.97× |
| CNN-7×7 | 15623.4 | 3482.6 | 7.50× |

Stage-wise totals (mean of 3): Airplane MED 4666 ms (recover 3517 ms = **75%** of it);
Airplane CNN-3×3 8044 ms; 4.2.03 MED 7803 ms; 4.2.03 CNN-3×3 15505 ms. With the
vectorized variant: 1622 / 4325 / 3030 / 10317 ms. AES-CTR is negligible (≤4 ms even on
three 512×512 channels); **the Python pixel loops, not the CNN, dominate the prototype's
end-to-end time**, so switching predictors moves the total far less than the
predictor-only benchmark suggests — and the accuracy/capacity win costs real time only in
the prediction stage.

Figures: `figures/fig_runtime_predictor.png`, `figures/fig_runtime_stages.png`;
host metadata: `runtime_meta.txt`. These 2026-10-19 numbers are **not** pooled with the
2026-10-18 artifacts (`results/final_validation_20261018/e_runtime_*.csv`); ordering and
magnitudes agree (e.g. CNN-3×3 1707 ms then vs 2082 ms now — same protocol, load/thermal
variation on a laptop-class CPU). One measurement in `improvement_experiments.csv`
(CNN-3×3 orig vs fast predictor) was taken while the host was concurrently loaded and is
superseded by the clean Phase-D rows; it is kept for traceability and flagged here.

---

## 8. Per-image exceptions and statistical limits (Phase F)

- **RGB channels where CNN-3×3 loses to the best classical predictor** (all GAP):
  4.2.06 R (−0.0405 bpp), 4.2.06 G (−0.0255), 4.2.07 R (−0.2360), 4.2.07 G (−0.1205),
  4.2.07 B (−0.0310) — `underperformance_diagnosis.csv`. **Grayscale:** Peppers
  (−0.0713 vs GAP).
- Consistency: the CNN wins 4/5 RGB images and 5/6 gray images at image level; the
  4.2.06 image-level margin (+0.0029) is smaller than the per-channel wins/losses within
  it — a mean-level advantage, emphatically not universal superiority.
- **No inferential statistics are claimed.** n=5 RGB and n=6 gray images do not justify
  significance testing; pixels are not independent experimental units. All differences
  are reported as absolute per-image/per-channel values plus descriptive means.
  No generalization to all natural images or to other RDHEI methods is claimed; the
  comparisons cover the four implemented predictors under one shared label map.

---

## 9. Reversibility validation and independent review (Phase H)

- **Fast-path e2e matrix: 88/88 PASS** (`fast_validation_gray.csv`,
  `fast_validation_rgb.csv`): 6 gray + 5 genuine RGB × {MED, CNN-3×3} ×
  {empty, 1000-bit, quarter, max} payloads; RGB per-channel nonces; pixel-exact image
  recovery and bit-exact payload extraction verified by direct array comparison,
  independent of pipeline flags. Plus 8/8 bitwise-equivalence cases
  (`improvement_experiments.csv`).
- **Regression:** `python3 -m pytest tests/ -q` → 16 passed before and after (no `src/`
  change; the fast variants are separate modules).
- **Independent review:** no second model is available in this environment (same
  limitation as `Final_report.md` §14). A systematic programmatic self-audit was executed
  instead: every numeric claim in this report was re-derived from the CSVs listed in §10
  (scripted checks recorded in `review_audit.md`); runtime boundaries, complexity
  formulas (re-verified against checkpoints), histogram provenance (all from actual
  prediction arrays), and the label-map explanation were each checked against code and
  data. Findings and resolutions: `review_audit.md`.

---

## 10. Artifact index (all under `results/rgb_complexity_error_analysis_20261019/`)

| Deliverable | File |
|---|---|
| Baseline reconciliation | `baseline_reconciliation.csv`, `phase_a_log.md` |
| RGB per-image / per-channel tables | `rgb_per_image_comparison.csv`, `rgb_per_channel_comparison.csv`, `gray_per_image_comparison.csv` |
| Improvement experiments | `improvement_experiments.csv`, `fast_validation_gray.csv`, `fast_validation_rgb.csv` |
| Complexity analysis | `complexity_analysis.md` |
| Runtime | `runtime_raw.csv`, `runtime_summary.csv`, `runtime_meta.txt` |
| Error statistics / histograms | `prediction_error_statistics.csv`, `histogram_bins.csv`, `label_histograms.csv`, `underperformance_diagnosis.csv` |
| Figures (9) | `figures/fig_err_*.png` (6), `figures/fig_runtime_*.png` (2), pooled label counts |
| Scripts (reproducible) | `ra_common.py`, `fast_impl.py`, `phase_a_baseline.py`, `phase_be_errors.py`, `phase_b_improvement.py`, `phase_d_runtime.py`, `regen_stage_figure.py` |
| Logs | `validation_log.md`, `phase_a_run.log`, `phase_be_run.log`, `phase_b_run.log`, `phase_d_run.log` |
| Change record | `CHANGELOG.md` |
| Review | `review_audit.md` |

Reproduce with:
```bash
python3 -m pytest tests/ -q                    # 16 passed
cd results/rgb_complexity_error_analysis_20261019
python3 phase_a_baseline.py                    # ~10 min (first run; predictions cached after)
python3 phase_be_errors.py                     # histograms + diagnosis
python3 phase_b_improvement.py                 # equivalence + fast-path e2e (~20 min)
python3 phase_d_runtime.py                     # runtime (~25 min)
python3 regen_stage_figure.py                  # stage figure from runtime_summary.csv
```

## 11. Limitations and unresolved issues

1. Independent-model review unavailable; self-audit disclosed (§9).
2. n=5 RGB + n=6 gray images: descriptive comparisons only (§8).
3. The Option-3 variant is validated but **not adopted** in `src/`; adoption is a
   separate, reviewed change.
4. Runtime host is a laptop-class CPU under WSL2; absolute times vary run to run
   (std up to ~30% for some CNN rows); cross-day comparisons are labeled, never pooled.
5. The label-map dead zones (|e| = 64, |e| ≥ 128) are a property of the shared embedding
   algebra, untouched here; changing them would be a new method (Option 4, requires
   approval).
6. Training provenance and dataset provenance remain unverified (inherited from
   `Final_report.md` §15/§16; out of this task's scope).
