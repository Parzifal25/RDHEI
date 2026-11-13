# Phase D — End-to-end payload-matrix results (real images)

- Started (UTC): 2026-10-18T18:41:54.867161+00:00
- Checkpoint: v4_patch3.pth (patch=3, residual=True, params=46,881)
- Grayscale images tested: 6; genuine RGB images tested: 5
- Grayscale cases: 85 (PASS 84, FAIL 0, documented 1)
- RGB cases: 40 (PASS 40, FAIL 0)

PASS = recovered pixels identical to original AND extracted bits identical to
embedded payload AND extracted length equals requested length (checked outside the pipeline).

Over-capacity behavior: the current sender interface zero-pads nothing beyond
capacity — it silently embeds only what capacity allows; the receiver extracts
only capacity bits. This is documented behavior, recorded as DOCUMENTED, not PASS.

Per-case data: d_e2e_gray.csv, d_e2e_rgb.csv
