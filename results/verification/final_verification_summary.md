# Final Verification Summary

**Run**: `cd RDHEI_FIXED_V1 && python3 FINAL_VERIFY_FULL_PIPELINE.py`  
**Stage**: full-pipeline perfect-recovery verification across all 5 CNN variants  
**Artifacts**: `results/verification/*`

## Result table

| Variant | Checkpoint | Patch | Residual | Params | Grayscale | RGB | Variant wall time (s) | Overall |
|---|---|---|---|---|---|---|---|---|
| v1_full | v1_full.pth | 5 | yes | 112,417 | 6/6 PASS | 0/6 SKIPPED | 70.75 | PARTIAL |
| v2_no_residual | v2_no_residual.pth | 5 | no | 112,353 | 6/6 PASS | 0/6 SKIPPED | 61.95 | PARTIAL |
| v3_no_weighted_loss | v3_no_weighted_loss.pth | 5 | yes | 112,417 | 6/6 PASS | 0/6 SKIPPED | 68.21 | PARTIAL |
| v4_patch3 | v4_patch3.pth | 3 | yes | 46,881 | 6/6 PASS | 0/6 SKIPPED | 45.47 | PARTIAL |
| v5_patch7 | v5_patch7.pth | 7 | yes | 210,721 | 6/6 PASS | 0/6 SKIPPED | 98.03 | PARTIAL |

## What each PASS means

For every attempted image, the COMPLETE pipeline was exercised and verified:

- predict -> embed -> encrypt -> decrypt -> extract -> recover
- `recovered == original` (exact image reconstruction)
- `extracted == embedded_payload` (bit-for-bit payload recovery)
- pipeline-reported `perfect=True` and `bit_acc=100.0`

An image is PASS only if all three conditions hold.

## Grayscale images used

- Airplane.png
- Baboon.png
- Goldhill.png
- Jetplane.png
- Lena.png
- Peppers.png

All grayscale runs passed with perfect image recovery and bit-accurate payload recovery.

## RGB images

The supplied `data/kodak_color/*` files are not 3-channel RGB arrays. When loaded, they appear as 2-D arrays, so `run_rdhei_color()` rejects them on its `image_rgb.shape[2] == 3` assertion. Therefore, RGB verification was SKIPPED for every variant, with the exact skipped shapes recorded per image in the per-variant logs.

This is documented as a dataset/conversion limitation, not as a pipeline correctness failure.

## Why overall is PARTIAL, not PASS

Overall is PARTIAL because the required RGB channel could not be attempted on the available dataset. Every attempted image in every required channel that could be run is PASS.

## Constraints honored

- No model checkpoint was written, overwritten, or retrained.
- Existing raw results, tables, figures, and logs were not touched; only `results/verification/` was added.
- Execution was bounded per image and per variant, with timeouts and explicit skip/failure reasons.

## Reproduction

```bash
cd RDHEI_FIXED_V1
python3 FINAL_VERIFY_FULL_PIPELINE.py
```

If a usable 3-channel RGB dataset is substituted for `data/kodak_color/`, re-run the same command to verify RGB for all variants.
