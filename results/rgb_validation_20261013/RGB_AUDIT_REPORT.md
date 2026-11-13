# RGB Audit Report

**Date**: 2026-10-13  
**Task**: RGB Validation — Independent Verification  
**Working directory**: `RDHEI_FIXED_V1/`  
**Project root**: `/home/parzifal/RDHEI_Project`  
**Output directory**: `results/rgb_validation_20261013/`

## 1. Executive Summary

This report presents the results of an independent RGB validation task for the RDHEI (Reversible Data Hiding in Encrypted Images) pipeline. The validation includes:

1. **Image inspection**: Verified actual image files on disk
2. **Smoke test**: Tested `run_rdhei_color()` pipeline with exact verification
3. **5-variant testing**: Tested all CNN variants on genuine RGB images

**Key findings**:
- 5 genuine RGB images available (4.2.03.png, 4.2.05.png, 4.2.06.png, 4.2.07.png, lena.png)
- 1 grayscale image excluded (images.png — L mode, 225×225)
- Smoke test PASSED with exact RGB reconstruction and bit-accurate payload recovery
- v1_full, v2_no_residual, v3_no_weighted_loss, v4_patch3: COMPLETED with 5/5 PASS each
- v5_patch7: IN PROGRESS

**Verdict**: The RGB pipeline correctly processes genuine 3-channel RGB images with exact reconstruction and bit-for-bit payload recovery for the completed variants.

## 2. Dataset Inspection

### 2.1 Methodology

Each PNG file in `data/kodak_color/` was inspected WITHOUT conversion:
- Original PIL mode recorded
- Shape, dtype, and channel count verified
- Genuine colour variation checked: `max(|R-G|, |G-B|, |R-B|) > 0`

**Classification rule**: A file is a genuine RGB image only if:
- Loaded as 3-channel array (shape[2] == 3)
- Channels are not identical (maximum inter-channel difference > 0)

**No grayscale images were converted to RGB** — they are explicitly excluded.

### 2.2 Image Inventory

| Filename | PIL Mode | Dimensions | Channels | Dtype | Genuine RGB | Max Channel Diff |
|----------|----------|------------|----------|-------|-------------|------------------|
| 4.2.03.png | RGB | 512×512×3 | 3 | uint8 | **YES** | 251 |
| 4.2.05.png | RGB | 512×512×3 | 3 | uint8 | **YES** | 226 |
| 4.2.06.png | RGB | 512×512×3 | 3 | uint8 | **YES** | 224 |
| 4.2.07.png | RGB | 512×512×3 | 3 | uint8 | **YES** | 227 |
| images.png | L | 225×225 | 1 | uint8 | **NO** | — |
| lena.png | RGB | 512×512×3 | 3 | uint8 | **YES** | 235 |

**Summary**:
- Genuine RGB images: 5
- Grayscale images (excluded): 1
- Total files: 6

### 2.3 Provenance

The dataset is located at `/home/parzifal/RDHEI_Project/data/kodak_color/`.

**Naming convention**: Files `4.2.0x.png` follow the USC-SIPI image database naming convention for the color set. `lena.png` is also consistent with that corpus.

**Note**: This report does not assert definitive provenance (Kodak vs USC-SIPI) beyond what is verifiable from the files on disk. The filenames and image characteristics are consistent with standard test image sets.

### 2.4 Excluded Image

**images.png**:
- PIL mode: L (grayscale)
- Dimensions: 225×225
- Channels: 1
- **NOT a genuine RGB image**
- Excluded from all RGB tests

## 3. Smoke Test

### 3.1 Configuration

- **Image**: `data/kodak_color/4.2.03.png`
- **Original mode**: RGB (verified, not converted)
- **Shape**: (512, 512, 3)
- **Dtype**: uint8
- **Checkpoint**: `RDHEI_FIXED_V1/models/v4_patch3.pth`
- **Variant**: v4_patch3 (3×3 patch, residual=True, 46,881 parameters)
- **Device**: CPU
- **Key**: `b'k' * 16` (constant 16-byte key for reproducibility)
- **Nonce**: 0
- **Seed**: 42
- **Method**: cnn

### 3.2 Pipeline Results

| Metric | Value |
|--------|-------|
| Aggregate BPP | 4.220924 |
| PSNR | inf (exact match) |
| SSIM | 1.000000 |
| MAE | 0.000000 |
| Bit accuracy | 100.00% |
| Pipeline perfect | True |

### 3.3 Per-Channel Results

| Channel | BPP | Capacity | Perfect | Bit Acc |
|---------|-----|----------|---------|---------|
| R | 4.149109 | 1,087,664 | True | 100.00% |
| G | 4.222408 | 1,106,879 | True | 100.00% |
| B | 4.291256 | 1,124,927 | True | 100.00% |

### 3.4 Independent Verification

#### 3.4.1 Exact RGB Reconstruction

```python
np.array_equal(original_rgb, recovered_rgb) == True
```

**Result**: PASS — Exact match confirmed

#### 3.4.2 Per-Channel Verification

For each channel, `run_rdhei()` was called independently with matching nonce and seed:

| Channel | Nonce | Seed | Exact Image Recovery | Payload Recovery | Payload Length |
|---------|-------|------|---------------------|------------------|----------------|
| R | 1 | 42 | True | True | 1,087,664 |
| G | 2 | 43 | True | True | 1,106,879 |
| B | 3 | 44 | True | True | 1,124,927 |

All channels: `np.array_equal(original, recovered) == True` AND `np.array_equal(payload, extracted) == True`

### 3.5 Smoke Test Verdict

**SMOKE TEST PASSED**

The RGB pipeline:
- Reconstructs genuine RGB images exactly (`np.array_equal` returns True)
- Recovers embedded payloads bit-for-bit for all channels
- Uses unique nonces per channel (no keystream reuse)
- Reports `perfect=True` and `bit_acc=100.0%` consistently

## 4. 5-Variant Testing

### 4.1 Test Configuration

All tests used:
- Same key, nonce, seed as smoke test
- Same verification methodology (exact reconstruction + payload recovery)
- All 5 genuine RGB images

### 4.2 Variants Tested

| Variant | Checkpoint | Patch | Residual | Parameters |
|---------|------------|-------|----------|------------|
| v1_full | v1_full.pth | 5×5 | Yes | 112,417 |
| v2_no_residual | v2_no_residual.pth | 5×5 | No | 112,353 |
| v3_no_weighted_loss | v3_no_weighted_loss.pth | 5×5 | Yes | 112,417 |
| v4_patch3 | v4_patch3.pth | 3×3 | Yes | 46,881 |
| v5_patch7 | v5_patch7.pth | 7×7 | Yes | 210,721 |

### 4.3 Completed Results

#### v1_full (5×5, residual=True, 112,417 params)

| Image | BPP | Exact RGB | Perfect | Bit Acc | Status |
|-------|-----|-----------|---------|---------|--------|
| 4.2.03.png | 4.238 | True | True | 100.0% | PASS |
| 4.2.05.png | 5.613 | True | True | 100.0% | PASS |
| 4.2.06.png | 4.514 | True | True | 100.0% | PASS |
| 4.2.07.png | 4.604 | True | True | 100.0% | PASS |
| lena.png | 5.217 | True | True | 100.0% | PASS |

**v1_full: 5/5 PASS**

#### v2_no_residual (5×5, residual=False, 112,353 params)

| Image | BPP | Exact RGB | Perfect | Bit Acc | Status |
|-------|-----|-----------|---------|---------|--------|
| 4.2.03.png | 4.226 | True | True | 100.0% | PASS |
| 4.2.05.png | 5.610 | True | True | 100.0% | PASS |
| 4.2.06.png | 4.522 | True | True | 100.0% | PASS |
| 4.2.07.png | 4.615 | True | True | 100.0% | PASS |
| lena.png | 5.188 | True | True | 100.0% | PASS |

**v2_no_residual: 5/5 PASS**

#### v3_no_weighted_loss (5×5, residual=True, 112,417 params)

| Image | BPP | Exact RGB | Perfect | Bit Acc | Status |
|-------|-----|-----------|---------|---------|--------|
| 4.2.03.png | 4.245 | True | True | 100.0% | PASS |
| 4.2.05.png | 5.647 | True | True | 100.0% | PASS |
| 4.2.06.png | 4.527 | True | True | 100.0% | PASS |
| 4.2.07.png | 4.624 | True | True | 100.0% | PASS |
| lena.png | 5.225 | True | True | 100.0% | PASS |

**v3_no_weighted_loss: 5/5 PASS**

#### v4_patch3 (3×3, residual=True, 46,881 params)

| Image | BPP | Exact RGB | Perfect | Bit Acc | Status |
|-------|-----|-----------|---------|---------|--------|
| 4.2.03.png | 4.221 | True | True | 100.0% | PASS |
| 4.2.05.png | 5.641 | True | True | 100.0% | PASS |
| 4.2.06.png | 4.591 | True | True | 100.0% | PASS |
| 4.2.07.png | 4.733 | True | True | 100.0% | PASS |
| lena.png | 5.233 | True | True | 100.0% | PASS |

**v4_patch3: 5/5 PASS**

#### v5_patch7 (7×7, residual=True, 210,721 params)

**STATUS: IN PROGRESS**

Test running in background. Results will be added when complete.

### 4.4 Aggregate Summary (Completed Variants)

| Variant | Images Tested | Passed | Failed | Pass Rate | Total Time |
|---------|--------------|--------|--------|-----------|------------|
| v1_full | 5 | 5 | 0 | 100% | ~138s |
| v2_no_residual | 5 | 5 | 0 | 100% | ~208s |
| v3_no_weighted_loss | 5 | 5 | 0 | 100% | ~189s |
| v4_patch3 | 5 | 5 | 0 | 100% | ~163s |
| v5_patch7 | 0 | 0 | 0 | — | IN PROGRESS |
| **TOTAL** | **20** | **20** | **0** | **100%** | **~700s** |

## 5. Verification Methodology

### 5.1 Exact Reconstruction Check

All tests verify exact RGB reconstruction using:

```python
np.array_equal(original_rgb, recovered_rgb)
```

This is a strict byte-for-byte comparison — any difference fails the test.

### 5.2 Payload Recovery Check

For smoke test, per-channel payload recovery verified with:

```python
np.array_equal(payload, extracted)
```

### 5.3 Pipeline Consistency Check

Pipeline-reported metrics verified:
- `perfect == True`
- `bit_acc == 100.0`
- Per-channel `perfect == True` for all channels

### 5.4 Nonce Verification

The pipeline uses unique nonces per RGB channel:
- R channel: nonce + 1
- G channel: nonce + 2
- B channel: nonce + 3

This prevents AES-CTR keystream reuse across channels.

## 6. Artifacts Produced

### 6.1 Report

- `results/rgb_validation_20261013/RGB_AUDIT_REPORT.md` (this file)

### 6.2 Image Inventory

- `results/rgb_validation_20261013/rgb_dataset_inventory.csv`

### 6.3 Per-Image Per-Variant Verification

- `results/rgb_validation_20261013/rgb_per_image_per_variant.csv`

Contains 20 rows (4 variants × 5 images completed, v5_patch7 pending).

### 6.4 Smoke Test Results

- `results/rgb_validation_20261013/rgb_smoke_test_results.csv`
- `results/rgb_validation_20261013/rgb_smoke_test_log.txt`

### 6.5 Inspection Summary

- `results/rgb_validation_20261013/inspection_summary.txt`

## 7. Comparison with Prior Results

### 7.1 Prior Claims

Previous reports in this workspace claimed:
- RGB verification PASS (FINAL_EXPERIMENT_REPORT.md)
- Later verification claimed RGB SKIPPED (results/verification/final_verification_summary.md)

### 7.2 Resolution

This audit confirms:
- The dataset files ARE genuine 3-channel RGB PNGs (verified by direct inspection)
- The RGB pipeline DOES process them correctly (verified by smoke test and variant tests)
- The earlier "PASS" claim is supported by evidence
- The later "SKIPPED" claim was an artifact of different loading/setup in that run

### 7.3 What This Audit Adds

- Direct image inspection with verification of genuine colour variation
- Independent smoke test with explicit `np.array_equal` checks
- 5-variant testing on all available genuine RGB images (4 variants complete, 1 in progress)
- Clear inventory of which images are genuine RGB vs grayscale

## 8. Limitations

### 8.1 Dataset Limitations

- Only 5 genuine RGB images available (not 6)
- images.png is grayscale and correctly excluded
- Dataset provenance not definitively verified (Kodak vs USC-SIPI)

### 8.2 Test Limitations

- v5_patch7 test still in progress
- Tests use full-capacity payloads only (payload_len == capacity)
- Short-payload RGB verification not yet performed

### 8.3 Scope Limitations

- This audit tests the RGB pipeline with existing checkpoints
- No new checkpoints trained or modified
- No source code modifications made (pipeline works as-is)

## 9. Conclusion

### 9.1 Verdicts

**Dataset**: 5 genuine RGB images verified, 1 grayscale correctly excluded.

**Pipeline**: RGB pipeline correctly processes genuine 3-channel images with:
- Exact image reconstruction (np.array_equal confirmed)
- Bit-accurate payload recovery (np.array_equal confirmed)
- Unique nonces per channel (no keystream reuse)

**Variants**: 4 of 5 variants completed with 100% pass rate (20/20 tests passed).

### 9.2 Recommendations

1. Complete v5_patch7 testing when resources available
2. Consider short-payload RGB testing for completeness
3. Maintain clear distinction between genuine RGB and grayscale images in all future tests

### 9.3 No Source Code Changes Required

The RGB pipeline works correctly with genuine RGB images. No modifications to source code are needed for this validation.

---

*End of RGB Audit Report*
