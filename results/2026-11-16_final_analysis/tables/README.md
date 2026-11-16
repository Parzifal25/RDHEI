# Final analysis result tables

| Table | Description | Evidence scope |
|---|---|---|
| `grayscale_native_edr2_audit_summary.csv` | Native grayscale full EDR2 end-to-end audit | 243-image native step-2 / four-phase EDR2 |
| `grayscale_matched_predictor_summary.csv` | Classical and CNN predictor comparison, including separate histogram-shift reference | 243 images, common step-4 / 16-phase comparison |
| `grayscale_*_cluster_bootstrap.csv` | Cluster-bootstrap coverage and paired-MAE differences | 29 provenance clusters, 10,000 resamples |
| `grayscale_v4_dataset_stratification.csv` | v4 results by natural/constructed label, provenance group and resolution | Matched step-4 / 16-phase grid |
| `rgb_blend_ablation_summary_corrected.csv` | Corrected per-blend feasibility, net capacity and exact round-trip counts | Run #79, 51 native RGB inputs |
| `rgb_dataset_stratification.csv` | RGB outcomes by corpus group and (for 3/4) resolution | Run #79 |
| `rgb_adaptive_phase_gain_*.csv` | Adaptive 24-assignment selection relative to fixed (0,1,2) | 20 directory-fit image/blend pairs |
| `rgb_receiver_audit_summary_corrected.csv` | Reparsed source-read and receiver pass counts | 162 independent receiver subprocesses |
| `complexity_benchmark_run90.csv` | Reproducible CPU predictor runtime, model compute, storage and sampled RSS | Run #90 |

Full raw phase-assignment scores (4,896 rows) and per-case receiver records remain in the linked Run #79 evidence archive; the compact per-image adaptive-gain ledger is committed here. The original Run #79 raw files are not rewritten to conceal the earlier summary counter defect.

Interpretation and explicit comparability boundaries are documented in `../EXPERIMENTAL_ANALYSIS.md`.
