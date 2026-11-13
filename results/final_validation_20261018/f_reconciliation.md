# Phase F — final result reconciliation (single source of truth)

Every row states the fresh value measured in this validation run, the historical
value, its source artifact, and the reconciliation status.

| Group | Metric | Subject | Fresh | Historical | Historical source | Status |
|---|---|---|---|---|---|---|
| gray_baselines | per-image BPP | MED/GAP/CALIC/CNN-3x3 (6 gray images) | max diff vs historical = 0.000046 | identical | results/gray/baselines_results.txt | **REPRODUCED** |
| gray_baselines | avg BPP | MED (baseline script definition) | 4.9575 | 4.9575 | results/gray/baselines_results.txt | **RECONCILED** |
| gray_baselines | avg BPP | MED (pipeline definition) | 4.9775 | 4.9775 | results/raw/aggregate_raw.csv | **RECONCILED** |
| gray_baselines | avg BPP | CNN-3x3 | 5.1897 | 5.1897 | results/gray/baselines_results.txt + results/raw/aggregate_raw.csv | **RECONCILED** |
| gray_baselines | avg prediction MAE | CNN-3x3 | 4.4615 | 4.4615 | results/gray/baselines_results.txt | **RECONCILED** |
| gray_baselines | avg prediction MAE | MED | 6.3174 | 6.3174 | results/gray/baselines_results.txt | **RECONCILED** |
| rgb_baselines | image set | genuine RGB count | 5 | 6 files (incl. images.png) | results/raw/per_image_rgb.csv; results/rgb/baselines_rgb_results.txt | **CORRECTED** |
| rgb_baselines | avg BPP | CNN-3x3 (5 genuine RGB) | 4.8838 | 5.0113 | results/rgb/baselines_rgb_results.txt (6 files incl. images.png) | **CORRECTED** |
| rgb_baselines | avg BPP | MED (5 genuine RGB) | 4.6984 | 4.7876 | results/rgb/baselines_rgb_results.txt (6 files incl. images.png) | **CORRECTED** |
| rgb_baselines | avg BPP | GAP (5 genuine RGB) | 4.7867 | 4.8488 | results/rgb/baselines_rgb_results.txt (6 files incl. images.png) | **CORRECTED** |
| rgb_baselines | avg BPP | CALIC (5 genuine RGB) | 4.6218 | 4.7183 | results/rgb/baselines_rgb_results.txt (6 files incl. images.png) | **CORRECTED** |
| rgb_baselines | per-image BPP | all predictors, 5 genuine images | max diff vs historical <= 0.0001 | identical | results/rgb/baselines_rgb_results.txt | **REPRODUCED** |
| ablation | gray BPP | v1_full | 5.1653 | 5.1653 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | gray MAE | v1_full | 4.5244 | 4.5244 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | RGB BPP (5 genuine) | v1_full | 4.8372 | 4.9686 | results/ablation/ablation_summary.csv (6 files incl. images.png) | **CORRECTED** |
| ablation | gray BPP | v2_no_residual | 5.1567 | 5.1567 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | gray MAE | v2_no_residual | 4.5515 | 4.5515 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | RGB BPP (5 genuine) | v2_no_residual | 4.8322 | 4.9567 | results/ablation/ablation_summary.csv (6 files incl. images.png) | **CORRECTED** |
| ablation | gray BPP | v3_no_weighted_loss | 5.1727 | 5.1727 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | gray MAE | v3_no_weighted_loss | 4.513 | 4.513 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | RGB BPP (5 genuine) | v3_no_weighted_loss | 4.8537 | 4.9851 | results/ablation/ablation_summary.csv (6 files incl. images.png) | **CORRECTED** |
| ablation | gray BPP | v4_patch3 | 5.1897 | 5.1897 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | gray MAE | v4_patch3 | 4.4615 | 4.4615 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | RGB BPP (5 genuine) | v4_patch3 | 4.8838 | 5.0113 | results/ablation/ablation_summary.csv (6 files incl. images.png) | **CORRECTED** |
| ablation | gray BPP | v5_patch7 | 5.1386 | 5.1386 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | gray MAE | v5_patch7 | 4.6977 | 4.6977 | results/ablation/ablation_summary.csv | **REPRODUCED** |
| ablation | RGB BPP (5 genuine) | v5_patch7 | 4.8185 | 4.9492 | results/ablation/ablation_summary.csv (6 files incl. images.png) | **CORRECTED** |
| ablation | params | all 5 variants | v4_patch3=46881,v1_full=112417,v2_no_residual=112353,v3_no_weighted_loss=112417,v5_patch7=210721 | 46881/112417/112353/112417/210721 | FINAL_EXPERIMENT_REPORT.md table | **VERIFIED** |
| pipeline | capacity bits | MED+CNN, 6 gray images | 12/12 exact match | results/raw/per_image_gray.csv | results/raw/per_image_gray.csv | **REPRODUCED** |
| pipeline | exact recovery | payload matrix (MED+CNN x 7 rules x 6 gray + 4 rules x 5 RGB) | 84/84 gray PASS | full-capacity only (historical) | results/verification/*; results/rgb_validation_20261013/* | **NEW EVIDENCE** |
| verification | RGB full-pipeline evidence | 5 variants x 5 genuine RGB | fresh sweep: see d_variants_rgb.csv | results/verification: SKIPPED (harness loaded images via convert('L')); results/rgb_validation_20261013: 25/25 PASS (genuine RGB) | results/verification/final_verification_summary.md + results/rgb_validation_20261013/* | **RESOLVED** |
| runtime | predictor-only ms | MED/GAP/CALIC/CNN (Lena 512x512) | see e_runtime_predictor.csv | 11.578/46.368/32.844/2877.455 ms (task-quoted historical) | historical manuscript values | **SUPERSEDED** |

Statuses: REPRODUCED (fresh run reproduces historical value), RECONCILED (difference explained and both values sourced), CORRECTED (historical value was wrong/inconsistent; fresh value supersedes it), RESOLVED (conflicting artifacts explained by a identified root cause), VERIFIED (checked directly), SUPERSEDED (historical value has no traceable source; replaced by measured artifact), NEW EVIDENCE (fresh measurement not previously available).

Notes per row are in f_reconciliation.csv.
