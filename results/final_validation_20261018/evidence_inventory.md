# Phase A — Evidence inventory

Produced during the final validation run of 2026-10-18. "Authoritative implementation"
is `RDHEI_FIXED_V1/src/` (repaired RGB encryption with per-channel nonces + fixed
receiver loop; parent `../src/rdhei_color.py` is the pre-repair version).

| Artifact | Path | Purpose | Current status | Used as final evidence? |
|---|---|---|---|---|
| Core RDHEI pipeline | `RDHEI_FIXED_V1/src/rdhei_core.py` | predict→embed→encrypt→decrypt→extract→recover | Authoritative; includes receiver short-payload fix (commit 05f4e69) | Yes |
| RGB pipeline wrapper | `RDHEI_FIXED_V1/src/rdhei_color.py` | per-channel RDHEI with unique nonces | Authoritative (repaired); `rdhei_color.py.bak` is the pre-repair copy | Yes |
| Encryption | `RDHEI_FIXED_V1/src/encryption.py` | AES-CTR, key/nonce helpers, metadata packing | Authoritative | Yes |
| CNN model | `RDHEI_FIXED_V1/src/cnn_model.py` | CNNPredictor + checkpoint loader with arch inference | Authoritative | Yes |
| Predictor map | `RDHEI_FIXED_V1/src/predictor.py` | CNN patch inference; vectorized MED | Authoritative | Yes |
| Baseline predictors | `RDHEI_FIXED_V1/src/baselines.py` | MED/GAP/CALIC (baseline-script definitions) | Authoritative for baseline tables | Yes |
| Metrics | `RDHEI_FIXED_V1/src/metrics.py` | BPP/PSNR/MAE/SSIM | Authoritative | Yes |
| Training script | `RDHEI_FIXED_V1/src/train.py` | Weighted-L1 CNN training (5×5 default) | Exists; cannot train 3×3/7×7 as written | Documented only |
| Legacy PEE modules | `RDHEI_FIXED_V1/src/embedding.py`, `extraction.py` | Older threshold-PEE scheme with 32-bit header | Not used by the authoritative pipeline | No (documented) |
| Grayscale benchmark | `../data/kodak_gray/*.png` (6 files) | Gray test images (mode L) | Valid; SHA256 recorded in dataset_inventory.csv | Yes |
| RGB benchmark | `../data/kodak_color/*.png` (6 files) | 5 genuine RGB + images.png (mode L, excluded) | Valid after B1 audit | Yes (5 genuine only) |
| Training images | `../data/train/*.pgm` (200 files) | Local BOSSbase-style folder | Present; does not verify 10,000-image claim | Context only |
| CNN checkpoints | `RDHEI_FIXED_V1/models/v1..v5*.pth` | 5 ablation checkpoints | Load + arch verified; hashes recorded | Yes |
| Extra checkpoints | `models/cnn_model.pth`, `models/_smoketest.pth` | Non-ablation checkpoints | Load OK; not part of the 5-variant set | No |
| Grayscale baseline txt | `results/gray/baselines_results.txt` | MED/GAP/CALIC/HistShift/CNN BPP+MAE (6 images) | Reproduced exactly by fresh run | Yes (reproduced) |
| RGB baseline txt | `results/rgb/baselines_rgb_results.txt` | RGB BPP/MAE incl. images.png | Per-image values reproduced; aggregate superseded (images.png excluded) | Partially |
| Raw pipeline CSVs | `results/raw/per_image_gray.csv`, `per_image_rgb.csv`, `aggregate_raw.csv`, `raw_metrics.csv` | Full-pipeline MED/CNN results | Gray reproduced; RGB aggregate included images.png → superseded | Partially |
| Ablation CSVs | `results/ablation/ablation_summary.csv`, `ablation_per_image.csv` | 5-variant gray+color BPP/MPE | Gray reproduced; color included images.png → superseded | Partially |
| Verification sweep | `results/verification/*` | 5-variant full-pipeline gray PASS; RGB SKIPPED | Gray PASS retained; RGB SKIPPED caused by grayscale loader defect | Gray yes; RGB no |
| RGB validation 25-run | `results/rgb_validation_20261013/rgb_per_image_per_variant.csv` | 5 variants × 5 genuine RGB full pipeline | All 25 rows passed; payload equality inferred from pipeline flags | Corroborating |
| RGB audit reports | `results/rgb_validation_20261013/RGB_AUDIT_REPORT*.md`, `RDHEI_FIXED_V1/results/rgb_audit_20261013T100000/RGB_AUDIT_REPORT.md` | RGB audit trail | Consistent with CSVs (original report was stale, superseded by FINAL) | Corroborating |
| Day-1 math audit | `RDHEI_FIXED_V1/RDHEI_DAY1_AUDIT.md` + audit_day1*.py | Correctness audit; found receiver F1 defect | Findings verified; F1 fix present in code | Yes |
| Runtime artifacts | `results/runtime/runtime_results.csv`, `runtime_report.txt` | Historical predictor-only benchmark | Protocol documented; fresh rerun produced same order of magnitude | Corroborating |
| Manuscript-quoted runtime | task text (MED 11.578 ms etc.) | Historical manuscript values | NOT traceable to any artifact in the repo | No (superseded) |
| Closure docs (parent) | `../FINAL_RESULTS_SOURCE_MAP.md`, `../FINAL_RESULTS_RECONCILIATION.csv`, `../FINAL_PROJECT_CLOSURE_REPORT.md` | Prior reconciliation work | Consistent with this audit | Yes (cross-checked) |
| Sec3 deliverables | `sec3_deliverable_a..d_*.md`, `Section_3_Updated.md` | Manuscript + audit deliverables | Consistent with this audit | Yes (cross-checked) |
| Prior experiment report | `FINAL_EXPERIMENT_REPORT.md` | Stage report of 2026-10-13 | Mostly consistent; its "RGB 6/6 PASS in results/verification" claim contradicts the artifacts in that directory (root cause: grayscale loader) → corrected here | Partially |
| Fresh final-validation run | `results/final_validation_20261018/*` | This validation run (B1–F scripts `scripts/fv_*.py`) | New authoritative evidence | Yes |
