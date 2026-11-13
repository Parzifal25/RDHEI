# Phase A — baseline reconciliation log

- Stored reference: `results/final_validation_20261018/` (fresh run of 2026-10-18).
- Recomputed from: authoritative `src/` implementation + `models/*.pth` checkpoints.
- Checks: 410 | match: 410 | mismatch: 0 | missing-in-reference: 0
- Largest absolute difference among matched checks: 7.470e-07

All RGB aggregates use the project convention: per-image RGB value = arithmetic
mean of the three per-channel values. `images.png` (single-channel) is excluded
from all RGB aggregates, consistent with the reference run.

No mismatches. The stored reference CSVs are fully reproduced by
the authoritative implementation and checkpoints on this host.
