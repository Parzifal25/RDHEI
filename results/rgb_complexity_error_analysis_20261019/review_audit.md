# Phase H — programmatic self-audit of RGB_Complexity_Error_Analysis.md

Every numeric claim below was re-derived from the CSV artifacts of this run
(or from the loaded checkpoints for the complexity claims).

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | reconciliation 410/410 | PASS | total=410 match=410 fail=0 |
| 2 | RGB mean BPP CNN 4.8838 | PASS | got 4.8838 |
| 3 | RGB mean BPP GAP 4.7867 | PASS | got 4.7867 |
| 4 | RGB mean rel +2.03% | PASS | got +2.03% |
| 5 | RGB MAE CNN 6.5558 | PASS | got 6.5558 |
| 6 | RGB MAE rel -18.4% | PASS | got -18.36% |
| 7 | gray mean BPP CNN 5.1897 | PASS | got 5.1897 |
| 8 | gray mean rel +3.24% | PASS | got +3.24% |
| 9 | gray MAE rel -24.5% | PASS | got -24.50% |
| 10 | 4.2.03 diff +0.2407 | PASS | +0.2407 |
| 11 | 4.2.05 diff +0.2335 | PASS | +0.2335 |
| 12 | 4.2.06 diff +0.0029 | PASS | +0.0029 |
| 13 | 4.2.07 diff -0.1292 | PASS | -0.1292 |
| 14 | lena diff +0.1374 | PASS | +0.1374 |
| 15 | Peppers gray diff -0.0713 | PASS | -0.0713 |
| 16 | 5 losing channels = 4.2.06 R/G + 4.2.07 R/G/B | PASS | [('4.2.06.png', 'G'), ('4.2.06.png', 'R'), ('4.2.07.png', 'B'), ('4.2.07.png', 'G'), ('4.2.07.png', 'R')] |
| 17 | all best_baseline = GAP | PASS |  |
| 18 | 4.2.07 R: CNN MAE higher (8.593 vs 7.481) | PASS | 8.5931 vs 7.4807 |
| 19 | 4.2.07 B: CNN MAE LOWER (5.300 vs 5.826) but BPP lower | PASS | 5.3003 vs 5.8257 |
| 20 | 4.2.07 B zero-error: GAP 9.93% vs CNN 6.09% | PASS | GAP 9.93 vs CNN 6.09 |
| 21 | pooled n7 (|e|=0) both 8.68% | PASS | GAP 8.68 CNN 8.68 |
| 22 | pooled n0 (|e|>=128): GAP 0.200% vs CNN 0.009% | PASS | GAP 0.200 CNN 0.009 |
| 23 | expected candidates MED 38.3 | PASS | 38.3 |
| 24 | expected candidates GAP 40.1 | PASS | 40.1 |
| 25 | expected candidates CALIC 36.8 | PASS | 36.8 |
| 26 | expected candidates CNN 41.3 | PASS | 41.3 |
| 27 | runtime CNN3x3 2082 ms | PASS | 2082.1703 |
| 28 | runtime vectorized 1761 ms | PASS | 1761.096 |
| 29 | runtime MED 6.40 ms | PASS | 6.3977 |
| 30 | runtime GAP 20.33 ms | PASS | 20.3283 |
| 31 | CNN7x7 15623 ms | PASS | 15623.3691 |
| 32 | TOTAL Airplane MED 4666 | PASS | 4665.7302 |
| 33 | TOTAL fast Airplane MED 1622 | PASS | 1621.9773 |
| 34 | TOTAL 4.2.03 CNN original 15505 | PASS | 15504.5472 |
| 35 | TOTAL 4.2.03 CNN fast 10317 | PASS | 10317.4264 |
| 36 | Airplane MED recover = 75% of total | PASS | 75.4% |
| 37 | 4/4 prediction equivalence bitwise | PASS |  |
| 38 | 8/8 embed/recover equivalence + exactness | PASS |  |
| 39 | fast-path gray 48/48 PASS (6 img x 2 pred x 4 rules) | PASS | rows=48 |
| 40 | fast-path rgb 40/40 PASS (5 img x 2 pred x 4 rules) | PASS | rows=40 |
| 41 | fast-path total 88/88 PASS | PASS |  |
| 42 | embed+encrypt 4.2.03 3635->98.7 | PASS | 3635.2 -> 98.7 |
| 43 | recover 4.2.03 7488->3597 | PASS | 7488.4 -> 3597.1 |
| 44 | v4_patch3.pth params formula == checkpoint | PASS | 46881 |
| 45 | v4_patch3.pth MAC formula | PASS | 122,816 |
| 46 | v1_full.pth params formula == checkpoint | PASS | 112417 |
| 47 | v1_full.pth MAC formula | PASS | 340,928 |
| 48 | v2_no_residual.pth params formula == checkpoint | PASS | 112353 |
| 49 | v2_no_residual.pth MAC formula | PASS | 340,128 |
| 50 | v5_patch7.pth params formula == checkpoint | PASS | 210721 |
| 51 | v5_patch7.pth MAC formula | PASS | 668,096 |

Result: 51/51 PASS, 0 FAIL.

Reviewer note: an independent second model was not available in this
environment; this audit is a systematic self-review and is disclosed as such
in the report (§9).
