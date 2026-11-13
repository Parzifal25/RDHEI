# RGB Audit Report — Final Version

**Date**: 2026-10-13  
**Status**: UPDATED — supersedes `RGB_AUDIT_REPORT.md`  
**Working directory**: `RDHEI_FIXED_V1/`  
**Project root**: `/home/parzifal/RDHEI_Project`  
**Output directory**: `results/rgb_validation_20261013/`

---

## Staleness Notice

This report replaces `RGB_AUDIT_REPORT.md`, which was **stale** at the time of writing:

- The original report stated that **v5_patch7 was "IN PROGRESS"** with 0/5 images tested.
- The uploaded CSVs (`rgb_per_image_per_variant.csv` and `rgb_variant_summary.csv`) **already contain all 25 test results**, including the 5 v5_patch7 entries with `passed=True`.
- The original report therefore **did not reflect the actual state of the evidence** in the output directory at the time it was written.
- This report reconciles the CSVs as the later, more complete record. The original report is preserved unchanged at its original path.

**Do not treat the original report as a consistent historical record.** The CSVs are the authoritative evidence for the 25-test run.

---

## 1. CSV Integrity Confirmation

### 1.1 Row count and uniqueness

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Total rows in `rgb_per_image_per_variant.csv` | 25 | 25 | ✓ |
| Unique `(variant, image)` combinations | 25 | 25 | ✓ |
| Images per variant | 5 | 5 each | ✓ |
| Variants with 5 images | 5 | v1_full, v2_no_residual, v3_no_weighted_loss, v4_patch3, v5_patch7 | ✓ |

**Conclusion**: The CSV contains exactly 25 unique image–variant combinations: 5 images × 5 variants. No duplicate rows.

### 1.2 Images covered

The five images tested are:

| Image | Shape |
|-------|-------|
| 4.2.03.png | 512×512×3 |
| 4.2.05.png | 512×512×3 |
| 4.2.06.png | 512×512×3 |
| 4.2.07.png | 512×512×3 |
| lena.png | 512×512×3 |

All 25 rows report `shape=512x512x3`.

### 1.3 Reconstruction and payload status across all 25 rows

Every row in `rgb_per_image_per_variant.csv` reports:

| Column | Value (all 25 rows) |
|--------|---------------------|
| `exact_rgb` | True |
| `pipeline_perfect` | True |
| `bit_acc` | 100.0 |
| `passed` | True |

No row reports a failure, timeout, or NaN.

---

## 2. Per-Variant Summary Reconciliation

`rgb_variant_summary.csv` records the following. The parameter counts and elapsed times below are taken from that CSV (not recomputed here):

| Variant | Checkpoint | Patch | Residual | Params | Images Tested | Passed | Pass Rate | Total Time (s) |
|---------|------------|-------|----------|--------|---------------|--------|-----------|----------------|
| v1_full | v1_full.pth | 5 | TRUE | 112,417 | 5 | 5 | 100% | 138.1 |
| v2_no_residual | v2_no_residual.pth | 5 | FALSE | 112,353 | 5 | 5 | 100% | 207.6 |
| v3_no_weighted_loss | v3_no_weighted_loss.pth | 5 | TRUE | 112,417 | 5 | 5 | 100% | 188.6 |
| v4_patch3 | v4_patch3.pth | 3 | TRUE | 46,881 | 5 | 5 | 100% | 163.0 |
| v5_patch7 | v5_patch7.pth | 7 | TRUE | 210,721 | 5 | 5 | 100% | 298.3 |

**Cross-check against detailed CSV**:

- Each variant's row count in `rgb_per_image_per_variant.csv` matches `images_tested` in the summary.
- Each variant's `passed` count matches.
- The per-image elapsed times in the detailed CSV sum (per variant) to approximately the totals in the summary CSV (differences are rounding/timing variations; the detailed CSV is the primary record).

No discrepancy was found between the detailed CSV and the summary CSV.

---

## 3. Comparison with the Original Report

The original `RGB_AUDIT_REPORT.md` reported:

- v1_full: 5/5 PASS
- v2_no_residual: 5/5 PASS
- v3_no_weighted_loss: 5/5 PASS
- v4_patch3: 5/5 PASS
- v5_patch7: **IN PROGRESS** (0/5)

The uploaded CSVs report:

- v1_full: 5/5
- v2_no_residual: 5/5
- v3_no_weighted_loss: 5/5
- v4_patch3: 5/5
- v5_patch7: **5/5**

**The CSVs are a later, more complete record.** The original report's "IN PROGRESS" status for v5_patch7 is stale with respect to the CSVs present in the same output directory.

---

## 4. Verification Methodology in the Existing Tests

### 4.1 Smoke test (`scripts/rgb_smoke_test.py`)

The smoke test performs **direct payload comparison** using `np.array_equal()`:

- For each channel R, G, B, it calls `run_rdhei()` independently.
- It then checks:
  - `np.array_equal(channel_original, channel_result['recovered'])`
  - `np.array_equal(channel_result['payload'], channel_result['extracted'])`

This is **one image × one variant (v4_patch3)**, with **direct payload bit-for-bit comparison** for all three channels.

### 4.2 Variant tests (`scripts/rgb_variant_test.py`, `scripts/rgb_variant_test_fast.py`)

The 5-variant tests do **not** perform a direct `np.array_equal(payload, extracted)` comparison for each of the 25 cases.

Instead, they verify:

1. `np.array_equal(image_rgb, result['recovered'])` — exact RGB reconstruction (direct comparison).
2. `result['perfect'] == True` — pipeline-reported all-channels-perfect flag.
3. `result['bit_acc'] == 100.0` — pipeline-reported bit accuracy.
4. Per-channel `perfect` and `bit_acc` from `result['per_channel']`.

The pipeline itself computes bit accuracy internally as:

```python
total_correct += int(np.sum(r["extracted"] == r["payload"]))
bit_acc = (total_correct / total_capacity * 100)
```

This is an elementwise `==` comparison of `extracted` and `payload`, reported as `bit_acc`. It is **not** a call to `np.array_equal()` in the test harness for the 25 variant rows.

### 4.3 What this means

- **Smoke test**: direct `np.array_equal(payload, extracted)` for 1 image × 3 channels. Verified in code.
- **25 variant rows**: exact image reconstruction verified with `np.array_equal()`. Payload correctness inferred from pipeline `perfect=True` and `bit_acc=100.0`, which are computed from an elementwise `extracted == payload` comparison inside the pipeline.

For a full accounting of direct `np.array_equal(payload, extracted)` calls across all 25 cases, see **Task 2 verification** below.

---

## 5. Short-Payload RGB Verification

To close the gap noted in the original report ("Short-payload RGB verification not yet performed"), a targeted short-payload test was run using existing checkpoints and genuine RGB inputs.

- **Directory**: `results/rgb_validation_20261013_short_payload/`
- **Image**: `data/kodak_color/4.2.03.png` (genuine RGB, 512×512×3)
- **Checkpoint**: `models/v4_patch3.pth`
- **Payload**: a payload **shorter than channel capacity** (not full-capacity)
- **Verification**:
  - `np.array_equal(original_rgb, recovered_rgb)` — exact image reconstruction
  - `np.array_equal(payload, extracted)` — bit-for-bit payload recovery

Results are recorded in the short-payload directory. All prior results in `results/rgb_validation_20261013/` are preserved unchanged.

---

## 6. Dataset Provenance

### 6.1 What is on disk

- Directory: `/home/parzifal/RDHEI_Project/data/kodak_color/`
- Files: `4.2.03.png`, `4.2.05.png`, `4.2.06.png`, `4.2.07.png`, `lena.png`, `images.png`

### 6.2 What is verified

- All five test images load as 3-channel RGB PIL images with genuine colour variation (max inter-channel difference > 0).
- `images.png` loads as a single-channel grayscale image and is excluded.

### 6.3 What remains uncertain

- No dataset README, manifest, or license file was found in `data/` or `data/kodak_color/`.
- The filenames `4.2.0x.png` are **consistent with** the USC-SIPI image database colour set naming convention, and `lena.png` is a widely used test image also associated with that corpus. This is **circumstantial**, not proof of origin.
- The directory name `kodak_color` suggests a Kodak-derived set, but this has not been independently confirmed from accompanying documentation.
- The report does **not** assert a definitive dataset origin based solely on filenames.

**Verdict**: Provenance is **unverified**. The images are genuine RGB test images; their exact source dataset is not documented in this repository.

---

## 7. Artifacts

### 7.1 Original (preserved)

- `results/rgb_validation_20261013/RGB_AUDIT_REPORT.md` — original report (stale; preserved unchanged)
- `results/rgb_validation_20261013/rgb_per_image_per_variant.csv` — 25 rows
- `results/rgb_validation_20261013/rgb_variant_summary.csv` — 5 variant rows
- `results/rgb_validation_20261013/rgb_smoke_test_results.csv`
- `results/rgb_validation_20261013/rgb_dataset_inventory.csv`

### 7.2 This report

- `results/rgb_validation_20261013/RGB_AUDIT_REPORT_FINAL.md` — this file

### 7.3 Short-payload verification

- `results/rgb_validation_20261013_short_payload/` — see Task 2 artifacts

---

*End of RGB Audit Report — Final Version*
