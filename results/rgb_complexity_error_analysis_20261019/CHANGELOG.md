# CHANGELOG — rgb_complexity_error_analysis_20261019

Scope: changes made during the 2026-10-19 RGB/complexity/error-distribution analysis.
The authoritative implementation (`src/`, `models/`, `tests/`, `configs/`) was **NOT
modified**. All new code lives in this directory. Existing results under
`results/final_validation_20261018/` and earlier were read-only inputs.

## New files (all under `results/rgb_complexity_error_analysis_20261019/`)

| File | Purpose |
|---|---|
| `ra_common.py` | Shared helpers: image loading, predictors, disk-cached prediction maps, label-map metrics |
| `fast_impl.py` | Option-3 vectorized drop-ins: `fast_cnn_predict_map` (patch extraction), `embed_msb_vectorized`, `recover_vectorized`. Semantics-preserving only; equivalence proven experimentally (bitwise) before use |
| `phase_a_baseline.py` | Phase A: recompute baseline tables from src+checkpoints; reconcile vs stored CSVs |
| `phase_be_errors.py` | Phase B1+E: error statistics, label-map distributions, histograms/figures, underperformance diagnosis |
| `phase_b_improvement.py` | Phase B2–B4: equivalence checks, timing of fast variants, fast-path e2e recovery matrix |
| `phase_d_runtime.py` | Phase D: predictor-only + stage-wise runtime benchmark (same protocol as fv_e_runtime.py) |
| `complexity_analysis.md` | Phase C: theoretical complexity derived from the actual code |

## Bug fixes during this analysis (validation scripts only)

1. `phase_a_baseline.py` — reconciliation loop assumed per-channel rows in
   `b3_ablation_rgb_per_image.csv`; that reference CSV is per-image. Fixed to
   per-image comparison incl. capacity_total. (Pre-fix outputs: none — the script
   aborted before writing CSVs.)
2. `phase_be_errors.py` — absolute-error histogram bin edges produced 257 bins vs a
   256-point x-axis. Fixed edge construction (257 edges → 256 bins). Pre-fix outputs:
   `fig_err_ecdf_rgb_pooled.png`, `fig_err_signed_rgb_pooled.png` (regenerated; only
   signed-error figures existed and were unaffected in content, but were overwritten
   by the corrected run for consistency).
3. `fast_impl.py` — `embed_msb_vectorized` initially assigned per-bit value array back
   into per-pixel index positions (shape mismatch). Fixed to per-pixel
   `lower | upper` via `np.add.at` scatter. Caught by the Phase-B equivalence test
   itself (crash, no wrong output produced).

## Semantics-affecting changes

None. No change was made to prediction, embedding, extraction, or recovery semantics
of the authoritative pipeline. The fast variants were verified bitwise-identical
(predictions) and output-identical (stego ciphertext, extracted bits, recovered image)
against the authoritative loops on real gray and RGB benchmark images before being
used for any measurement (see `improvement_experiments.csv`, `fast_validation_*.csv`).
