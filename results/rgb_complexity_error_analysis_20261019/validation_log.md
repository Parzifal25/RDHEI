# validation_log.md — rgb_complexity_error_analysis_20261019

Environment (all measurements on this host, 2026-10-19):
Python 3.10.12; torch 2.14.0+cu130 (CPU device, no CUDA used); numpy 2.2.6;
Pillow 12.3.0; pycryptodome 3.24.1; matplotlib 3.10.9; Linux WSL2 6.6.114;
CPU Intel i5-8265U (4C/8T). All timings via `time.perf_counter()`.

## Pre-existing evidence (read-only inputs)

- `results/final_validation_20261018/` — the fresh 2026-10-18 validation CSVs
  (b2/b3/d/e/f families): authoritative per-image, per-channel, ablation, e2e,
  runtime, and reconciliation data.
- `Final_report.md` (2026-10-18), `models/*.pth` (5 checkpoints), `src/` (authoritative
  implementation), `../data/kodak_gray`, `../data/kodak_color` (benchmark images).
- Baseline test suite: `python3 -m pytest tests/ -q` → **16 passed** (pre-change
  regression baseline, 42 s).

## Commands executed (run from RDHEI_FIXED_V1 project root, 2026-10-19)

```bash
python3 -m pytest tests/ -q                                   # 16 passed (regression baseline)
cd results/rgb_complexity_error_analysis_20261019
python3 phase_a_baseline.py                                   # Phase A: 410/410 reconciliation checks match
python3 phase_be_errors.py                                    # Phase B1+E: 159 stat rows, 7 figures, 5 underperformance rows
python3 phase_b_improvement.py                                # Phase B2-B4: equivalence + fast-path e2e 88/88 PASS
python3 phase_d_runtime.py                                    # Phase D: predictor-only + stage-wise runtime
```

## Phase A — baseline reconciliation

- Recomputed every per-image/per-channel MAE and BPP value for
  MED, MED-pipeline, GAP, CALIC, CNN-3x3 and the four CNN ablations **from the
  authoritative src/ + checkpoints** (not from stored CSVs).
- Compared 410 values against `results/final_validation_20261018/`
  (`b2_rgb_per_channel.csv`, `b2_rgb_per_image.csv`, `b2_gray_per_image.csv`,
  `b3_ablation_rgb_per_image.csv`): **410/410 match**, max |diff| ≤ 1e-4 tolerance
  (actual worst ≈ 1e-6 level, consistent with stored decimal rounding).
- Conclusion: the manuscript-facing numbers in `Final_report.md` are fully
  reproducible from source on this host. The 4.2.07 statement (GAP 4.8622 >
  CNN-3x3 4.7330 mean-over-channels) was verified from the source CSV and by fresh
  recomputation.

## Phase B1/E — error analysis

- 159 image/channel/method statistic rows; 122,271 histogram-bin rows (fixed bins);
  7 figures. Sign convention verified against `content_owner_prepare()`:
  e = image − round(pred) (asserted in code).
- **5 channels where CNN-3x3 BPP < best classical**: 4.2.06 R/G, 4.2.07 R/G/B
  (see `underperformance_diagnosis.csv`). On 4.2.06 R, 4.2.06 G and 4.2.07 B the
  CNN has **lower MAE but lower BPP** — explained by the label map's reward for
  exact predictions (n=7): GAP puts 9.9–10.5% of pixels at |e|=0 on 4.2.07 G/B vs
  5.4–6.1% for CNN-3×3; those pixels carry 7 bits each.

## Phase B2–B4 — improvement experiments

1. **Option 1 (correctness audit)**: no defect found in RGB channel handling,
   label-map generation, aggregation, dtype conversion, or checkpoint loading.
   The two MED variants and the zero-prediction first row/col convention of the
   baseline script are documented differences, not defects. No source change made.
2. **Option 2 (ablation analysis)**: recomputed all 5 checkpoints on all 15 RGB
   channels; CNN-3×3 remains best in mean RGB BPP and MAE. On the 5 losing
   channels no alternative checkpoint beats GAP either (checked in
   `prediction_error_statistics.csv` rows for CNN5x5/NoResidual/NoWeighted/7x7).
   No silent substitution made.
3. **Option 3 (implementation improvement, semantics-preserving)**:
   - `fast_cnn_predict_map`: patch extraction vectorized via sliding windows.
     **Bitwise-identical** predictions (max |diff| = 0) on 4 real channels
     (incl. 4.2.07 G where CNN loses BPP) + Airplane gray.
   - `embed_msb_vectorized` / `recover_vectorized`: **output-identical** to the
     authoritative loops — identical encrypted stego, extracted bits, recovered
     image on 4 real images × {max, quarter} payloads.
   - **Fast-path e2e recovery matrix: 88/88 PASS** (6 gray + 5 genuine RGB ×
     {MED, CNN-3×3} × {empty, 1000-bit, quarter, max} payloads; RGB per-channel
     nonces 6/7/8; pixel-exact image + bit-exact payload verified by direct
     array comparison, independent of pipeline flags).
   - Measured effect (3 repeats, full-capacity payloads):
     embed+encrypt Airplane 1501.6→34.3 ms; 4.2.03 3635.2→98.7 ms.
     decrypt+extract+recover Airplane 3778.3→1677.3 ms; 4.2.03 7488.4→3597.1 ms.
     CNN predictor-only timing in `improvement_experiments.csv`
     (orig 2329 ms vs 3129 ms) was measured **while the analysis host was
     concurrently loaded** and is superseded by the clean Phase-D protocol numbers
     in `runtime_summary.csv`; the forward pass dominates (~1.6 s of the ~1.7 s),
     patch extraction is ~40–90 ms, so the extraction vectorization is a small
     single-digit-percent predictor-level gain, not a slowdown (recorded honestly).

## Phase D — runtime

- Protocol identical to the validated `fv_e_runtime.py`: Lena 512×512, CPU,
  warm-up 5, 10 timed repeats, model loading excluded; stage-wise: Airplane gray
  and 4.2.03 RGB, full-capacity payload, 3 repeats, disjoint timing boundaries
  (label_map | embed | encrypt | decrypt | extract+recover | TOTAL-original |
  TOTAL-fast-variant). Raw samples in `runtime_raw.csv`; aggregates in
  `runtime_summary.csv`; host metadata in `runtime_meta.txt`.

## What was NOT done (explicitly)

- No retraining; no change to checkpoints; no new prediction algorithm introduced
  (Option 4 would require approval — none was deemed necessary after Options 1–3).
- No edits to `src/`, `models/`, `tests/`, `Final_report.md`, or any existing
  `results/` subdirectory.
- No benchmark membership change: 5 genuine RGB images (+ the documented
  single-channel exclusion of `images.png`) and 6 grayscale images throughout.
