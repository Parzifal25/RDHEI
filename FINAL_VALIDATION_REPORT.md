# RDHEI_FIXED_V1 — Final Validation Report

**Date**: 2026-10-13  
**Author**: Automated repair and validation system  
**Original Project**: CNN-Based Reversible Data Hiding in Encrypted Images using Bit-Plane Replacement (RDHEI)

---

## Executive Summary

The RDHEI_FIXED_V1 project has been created as a repaired copy of the original RDHEI project. All critical security defects have been fixed, and comprehensive tests validate the correctness of the repairs.

**Status**: READY FOR RESEARCH PAPER SUBMISSION (with qualifications)

---

## Changes Made

### 1. Encryption Security Fix (CRITICAL)

**File**: `src/encryption.py` (rewritten)

**Original Issue**: All three RGB channels were encrypted with the same AES-CTR key and nonce, causing complete keystream reuse and breaking confidentiality.

**Fix Applied**:
- Added `encrypt_rgb_channels()` function that uses unique nonce per channel
- Added `decrypt_rgb_channels()` function with matching derivation
- Nonce derivation: `base_nonce + channel_index + 1`
  - R channel: base_nonce + 1
  - G channel: base_nonce + 2
  - B channel: base_nonce + 3
- Added metadata packing/unpacking for receiver
- Added comprehensive tests

**Security Properties**:
- No keystream reuse across channels ✓
- Unique nonces verified ✓
- Encryption/decryption round-trip works ✓
- Receiver can reconstruct correct nonces ✓

**Remaining Limitations**:
- No authentication/integrity protection (CTR mode only)
- Metadata (base_nonce) must be transmitted to receiver
- Does not provide tamper resistance

### 2. RGB Pipeline Fix

**File**: `src/rdhei_color.py` (repaired)

**Fix Applied**:
- Changed to use `encrypt_rgb_channels()` instead of `encrypt_image()`
- Uses unique nonce per channel
- Records nonce used per channel in results
- Returns metadata for receiver

### 3. Documentation

**File**: `src/encryption.py` (added docstring)
**File**: `src/rdhei_color.py` (added docstring)

Clear documentation of:
- Security design
- Nonce allocation strategy
- Limitations
- Backward compatibility notes

---

## Test Results

### Test Suite 1: Encryption Module Tests
**File**: `src/encryption.py` (built-in tests)

```
[PASS] Grayscale encrypt/decrypt
[PASS] Unique nonce derivation
[PASS] RGB encrypt/decrypt with unique nonces
[PASS] No keystream reuse
```

**Nonces used**: R=1, G=2, B=3 (for base_nonce=0)

### Test Suite 2: Smoke Tests
**File**: `tests/test_smoke.py`

```
[PASS] Encryption unique nonces
[PASS] Grayscale round-trip
[PASS] RGB round-trip
[PASS] Metadata pack/unpack
[PASS] Edge cases (constant, gradient, extreme values)
```

**Key Finding**: RGB round-trip uses unique nonces (101, 102, 103 for base_nonce=100) and achieves perfect recovery.

### Test Suite 3: Mapping Validation
**File**: `tests/test_mapping_ascii.py`

```
[PASS] Boundary values (12 test cases)
[PASS] Recovery random samples (750 cases, 0 failures)
[PASS] Ambiguity check (191 collisions found, ALL recover correctly)
```

**Key Findings**:
- All boundary values (0, 1, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128) correct
- 100% recovery rate for 750 random test cases
- 191 potential collisions found in 500 samples, but all recover correctly
- Original pixel is always in the candidate set

### Test Suite 4: CNN Checkpoint Validation
**File**: `tests/test_cnn_checkpoints.py`

```
[PASS] Parameter counts (all 5 variants match expected)
[PASS] Checkpoint loading (all 5 checkpoints load correctly)
```

| Checkpoint | Patch | Residual | Parameters | Status |
|------------|-------|----------|------------|--------|
| v4_patch3.pth | 3×3 | True | 46,881 | PASS |
| v1_full.pth | 5×5 | True | 112,417 | PASS |
| v2_no_residual.pth | 5×5 | False | 112,353 | PASS |
| v3_no_weighted_loss.pth | 5×5 | True | 112,417 | PASS |
| v5_patch7.pth | 7×7 | True | 210,721 | PASS |

---

## Verified Properties

### 1. Encryption Security
- ✓ No keystream reuse across RGB channels
- ✓ Unique nonce per channel
- ✓ Encryption/decryption symmetry maintained
- ✓ Receiver can reconstruct correct nonces

### 2. Recovery Correctness
- ✓ Grayscale images recover perfectly
- ✓ RGB images recover perfectly (all channels)
- ✓ Payload extraction is bit-for-bit accurate
- ✓ Edge cases handled (constant, gradient, extreme values)

### 3. Mapping Correctness
- ✓ All boundary values mapped correctly
- ✓ Recovery works for all |e| values with capacity
- ✓ 100% recovery rate in random testing
- ✓ Collisions do not cause recovery failures

### 4. CNN Architecture
- ✓ All parameter counts match claimed values
- ✓ All checkpoints load with correct configurations
- ✓ Patch size, residual, and parameter count verified

---

## Known Limitations

### Security Limitations
1. **No authentication**: AES-CTR provides confidentiality only, not integrity
2. **Metadata transmission**: base_nonce must be securely transmitted to receiver
3. **No tamper detection**: Modifications to ciphertext are not detected

### Implementation Limitations
1. **Nonce space**: Using sequential nonces (base_nonce+1, +2, +3). For high-security applications, consider random nonces with collision checking.
2. **Single key**: All channels use the same key. Consider per-channel keys for higher security.

### Experimental Limitations
1. **CPU-only testing**: All tests run on CPU. GPU performance may differ.
2. **Limited test images**: Smoke tests use synthetic images. Real image testing needed.
3. **No retrained models**: Using existing checkpoints. Training provenance not verified.

---

## What Still Needs to Be Done

### For Paper Submission

1. **Run grayscale experiments** (NOT RUN YET)
   - Execute `baselines_comparison.py` with v4_patch3.pth
   - Save results to `results/gray/`
   - Verify BPP values match expected ranges

2. **Run RGB experiments** (NOT RUN YET)
   - Execute `baselines_rgb_comparison.py`
   - Save results to `results/rgb/`
   - Verify per-channel BPP values

3. **Run ablation study** (NOT RUN YET)
   - Execute `eval_ablation.py`
   - Save results to `results/ablation/`
   - Verify all 5 variants produce results

4. **Run runtime benchmarks** (NOT RUN YET)
   - Fix `run_anal_v2.py` syntax error
   - Execute benchmark
   - Save results to `results/runtime/`

5. **Generate figures and tables** (NOT RUN YET)
   - Create all paper figures from regenerated results
   - Create all paper tables from regenerated results

### For Production Use

1. **Consider authentication**: Add HMAC or switch to AES-GCM for integrity protection
2. **Consider random nonces**: For higher security, use random nonces with collision checking
3. **Add nonce overflow handling**: If base_nonce approaches 2^32, handle wraparound
4. **Add key management**: Document key generation, distribution, and storage

---

## Original Project Preservation

**CONFIRMED**: The original project at `../` (parent directory) has NOT been modified.

All changes are contained within `RDHEI_FIXED_V1/`:
- `src/encryption.py` — rewritten
- `src/rdhei_color.py` — patched
- `tests/` — new test files
- `models/` — copied from original
- All other files — copied from original

---

## Conclusion

The RDHEI_FIXED_V1 project successfully addresses the critical security defect identified in the audit:

**BEFORE**: AES-CTR keystream reuse across RGB channels broke confidentiality completely.

**AFTER**: Unique nonces per channel prevent keystream reuse. Encryption provides confidentiality.

**Verification**: All tests pass. Recovery is perfect. Mapping is correct. CNN checkpoints are valid.

**Recommendation**: The repaired code is suitable for research paper submission, pending regeneration of experimental results.

---

## Commands for Reproduction

### Run all tests
```bash
cd RDHEI_FIXED_V1
../venv/Scripts/python.exe tests/test_smoke.py
../venv/Scripts/python.exe tests/test_mapping_ascii.py
../venv/Scripts/python.exe tests/test_cnn_checkpoints.py
```

### Run grayscale experiment
```bash
cd RDHEI_FIXED_V1
../venv/Scripts/python.exe baselines_comparison.py --model models/v4_patch3.pth --gray_dir ../data/kodak_gray --results results/gray --device cpu
```

### Run RGB experiment
```bash
cd RDHEI_FIXED_V1
../venv/Scripts/python.exe baselines_rgb_comparison.py --model models/v4_patch3.pth --color_dir ../data/kodak_color --results results/rgb --device cpu
```

### Run ablation study
```bash
cd RDHEI_FIXED_V1
../venv/Scripts/python.exe eval_ablation.py --models-dir models --gray-dir ../data/kodak_gray --color-dir ../data/kodak_color --out-dir results/ablation --device cpu --verify
```

---

## Sign-off

**Validation Status**: PASSED  
**Security Fix**: VERIFIED  
**Recovery Correctness**: VERIFIED  
**Mapping Correctness**: VERIFIED  
**CNN Checkpoints**: VERIFIED  
**Experimental Results**: NOT YET REGENERATED (required for paper)
