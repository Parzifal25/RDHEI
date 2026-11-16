# Figure index — final analysis set

All figures are editable SVG files and are derived from the CSV tables in `../tables/`. The images intentionally avoid depicting source USC-SIPI images, so dataset imagery rights do not block use of these charts.

| Figure | File | Purpose and interpretation |
|---|---|---|
| 1 | `fig01_gray_positive_net_coverage.svg` | Positive-net coverage for MED, GAP, simplified CALIC-style and five CNN variants on the matched grayscale step-4 / 16-phase comparison grid. |
| 2 | `fig02_gray_candidate_mae.svg` | Mean candidate MAE under that same matched predictor comparison; lower is better. v3 is lower than v4. |
| 3 | `fig03_gray_cluster_bootstrap_coverage.svg` | Cluster-bootstrap intervals for coverage difference (v4 minus comparator), over 29 curator-defined provenance clusters. |
| 4 | `fig04_rgb_positive_coverage_by_blend.svg` | Positive-net image count by RGB cross-channel blend, out of 51. |
| 5 | `fig05_rgb_conditional_net_bpp.svg` | Fit-only mean signed net bpp by blend; directory-fit sample count shown in labels. |
| 6 | `fig06_predictor_runtime.svg` | Full-map predictor-only runtime from Run #90, 512×512 CPU benchmark. |
| 7 | `fig07_cnn_parameters_vs_runtime.svg` | Parameter count against predictor runtime for five CNN checkpoints. |
| 8 | `fig08_gray_stratified_coverage.svg` | Descriptive v4 coverage by natural/constructed grouping and image resolution; the grouping dimensions are distinct. |
| 9 | `fig09_rgb_adaptive_phase_gain.svg` | Mean gain from adaptive 24-phase assignment relative to fixed `(0,1,2)`, conditional on directory fit. |

**Plotting cautions:** Figure 5 is not a whole-corpus mean. Figure 8 is descriptive and confounded by content/provenance. Figure 9 is a paired descriptive mean over small, varying denominators (3, 3, 6 and 8), not a confidence interval. Figure 6 is predictor-only rather than end-to-end RDHEI latency.
