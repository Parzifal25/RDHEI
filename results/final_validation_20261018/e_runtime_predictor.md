# Phase E — predictor-only runtime

- Started (UTC): 2026-10-18T18:29:30.835635+00:00
- Host CPU: x86_64; OS: Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.35
- Python 3.10.12; torch CPU inference
- Protocol: image Lena.png 512x512 grayscale; warm-up 5 runs; 10 timed repeats;
  wall-clock per run; aggregation = arithmetic statistics over the 10 runs.
- Scope: PREDICTOR ONLY (no label map, embedding, encryption, extraction, recovery).

| Method | Params | Mean ms | Std ms | Min ms | Max ms | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| MED | 0 | 6.709 | 0.769 | 5.562 | 7.778 | 6.567 |
| GAP | 0 | 21.254 | 6.125 | 15.374 | 33.197 | 19.630 |
| CALIC | 0 | 13.119 | 2.160 | 11.687 | 18.368 | 12.210 |
| CNN-3x3 (v4_patch3) | 46,881 | 1707.289 | 89.740 | 1557.485 | 1878.796 | 1699.917 |
| CNN-5x5 (v1_full) | 112,417 | 5484.759 | 742.568 | 4829.528 | 6944.924 | 5302.459 |
| CNN-NoResidual (v2) | 112,353 | 3466.277 | 93.592 | 3369.038 | 3668.984 | 3457.180 |
| CNN-NoWeightedLoss (v3) | 112,417 | 4573.040 | 300.977 | 4215.129 | 5119.934 | 4463.222 |
| CNN-7x7 (v5_patch7) | 210,721 | 8518.924 | 599.253 | 7571.210 | 9616.377 | 8440.789 |
