# CHANGELOG

## Manuscript revision pass — 2026-10-20

Evidence-supported manuscript-only revision per `FINAL_CLOSURE_REPORT.md`
(status READY WITH DISCLOSED LIMITATIONS). New deliverables:
`Final_report_REVISED_20261020.md` + `.pdf`, `MANUSCRIPT_UPDATE_CHANGE_REPORT_20261020.md`,
and the check tooling `manuscript_check_20261020.py`, `pdf_render_check_20261020.py`,
`render_manuscript_pdf.py`. Originals (`Final_report.md`, `Section_3_Updated.md`) and all
source code, checkpoints, datasets, and result CSVs left unchanged; no retraining, no new
experiments.

- **Verified (no edit needed):** the closure report's Table 8 4.2.06 red-channel CNN value
  (4.5648, rounded from 4.564750671) already matches the manuscript's channel-wise RGB
  table (§8.5) and all raw sources; the superseded 4.5647 appears nowhere in manuscript or PDF.
- **Corrected:** four bold "best-value" marks (Tables 1–4, Peppers + RGB 4.2.07 → GAP) and
  the Table-2 "best on every image" sentence; mean-level qualification of the §1/§11/§13
  summary claims (per-image exceptions now cited); RQ4/§8.9 runtime ratios reconciled to the
  measured predictor-only protocol (~80×/~130×/~255×; CNN-7×7 ~1270× vs MED) with
  predictor-only and end-to-end timings never mixed; §10/§13 case-count parenthetical
  (55-case sweep included in the 180); one §8.2 cross-reference.
- **Added:** §8.12 / Table 11 from the regenerated complexity results
  (`results/complexity/complexity_results.csv`: params 46,881/112,417/112,353/112,417/210,721,
  MACs 122,816/340,928/340,128/340,928/668,096, Approx FLOPs = 2×MACs) with scope caveats;
  closure-status header; reproducibility addendum.
- **Checks:** `manuscript_check_20261020.py` → 23 PASS / 0 FAIL / 1 BLOCKED (C7, no
  bibliography exists) over 267 table cells; `pdf_render_check_20261020.pdf` → 0 FAIL over
  68 rendered-PDF checks (21 pages); `pytest tests/ -q` → 16 passed; `validate_section3.sh`
  → 1 pre-existing false-positive FAIL (regex-escaping; equation present at line 433).
  LaTeX toolchains (pandoc/pdflatex/weasyprint) unavailable — PDF via reportlab renderer.
  Open blockers: bibliography/References placeholders and publication declarations.

## Technical closure pass — 2026-10-20

Evidence-driven closure for the manuscript hand-off (details in
`FINAL_CLOSURE_REPORT.md`). Pipeline source, checkpoints, datasets, and all
result CSVs backing the reported tables were left unchanged.

- **Fix — `src/comp.py` (Table 3 producer):** `load_runtime_results()` expected
  the old `Mean(ms)` CSV schema and old method labels and crashed with
  `KeyError: 'Mean(ms)'` against the actual `results/runtime/runtime_results.csv`
  (`Mean_ms`, labels like `CNN-3x3 (v4_patch3)`). Added column fallback + label
  normalization so the script runs unmodified otherwise. Table 3 regenerated to
  `results/complexity/` (params 46,881/112,417/112,353/112,417/210,721 and
  Approx FLOPs 245,632/681,856/680,256/681,856/1,336,192 = 2×MACs per patch,
  all matching the checkpoints and `complexity_analysis.md`).
- **Correction — `Final_report.md` §8.9:** CNN-family speedup ratio for the 5×5
  model was "2.0×"; the fresh 2026-10-18 means give 5484.8/1707.3 = 3.2×.
  Corrected to 3.2× with the ratios spelled out.
- **Correction — `Final_report.md` §8.6 and §11:** both stated the weighted loss
  "helps" / "improves RGB MAE by ~0.06"; the verified tables
  (`ablation_summary.csv`, `b3_ablation_*`) show the plain-L1 checkpoint
  (v3) is the better one on all four aggregate metrics. Direction corrected;
  magnitudes (0.007/0.017 bpp, 0.06 MAE) were already right.
- **Correction — `Section_3_Updated.md` (3 spots):** "CNN-5×5 (full/proposed)"
  designated CNN-5×5 as the proposed configuration, contradicting the
  authoritative record (CNN-3×3 is proposed). Changed to "full" reference
  configuration; CNN-3×3 now named as proposed (§3.2.2, Table 1, §3.7.1).
  The original draft `sec3_deliverable_b_section3_manuscript.md` is preserved.
- **Re-executed checks:** `pytest tests/ -q` 16 passed; Phase A baseline
  410/410 (outputs byte-identical); Phase B fast-path e2e 88/88 PASS
  (acceptance CSVs byte-identical); `review_audit.py` 51/51 (byte-identical);
  `fv_f_reconcile.py` 0 disagreements; `repro_receiver_payload_len.py` and
  `RDHEI_FIXED_V1/test_receiver_fix.py` pass; dataset SHA-256 12/12;
  checkpoint SHA-256 prefixes 5/5; all Final_report Tables 1–10 re-verified
  against source CSVs. Pre-run backups: `results/rgb_complexity_error_analysis_20261019/pre_closure_backup_20261020/`.

---

## Final validation run — 2026-10-18

No production source code was modified during the final validation run. The run
added only validation scripts and outputs:

- New scripts (all under `scripts/`): `fv_b1_inventory.py`, `fv_b2_baselines.py`,
  `fv_b3_ablation.py`, `fv_d_e2e.py`, `fv_d_variants.py`, `fv_e_runtime.py`,
  `fv_f_reconcile.py`, `fv_figures.py`.
- New outputs: `results/final_validation_20261018/**`, `figures/` (report assets),
  `Final_report.md`.
- Existing results, datasets, checkpoints, and prior reports were not modified.
- One script defect was found and fixed *in the validation script itself*
  (`scripts/fv_d_e2e.py` passed a boolean where an image name was expected when
  saving example panels); the pipeline under test was not changed.
- The earlier receiver fix (`receiver_extract_recover` no longer stops the pixel
  loop after `payload_len` bits; commit `05f4e69`) was re-validated on real
  images with empty/short/intermediate/near-max/max payloads (Phase D).

Prior entries below describe the 2026-10-13 implementation repair.

---

## RDHEI_FIXED_V1 — Implementation Repair

**Date**: 2026-10-13  
**Original Project**: CNN-Based Reversible Data Hiding in Encrypted Images using Bit-Plane Replacement (RDHEI)

---

## Summary

Created a repaired copy of the RDHEI project with the following critical fix:

- **Security fix**: Eliminated AES-CTR keystream reuse across RGB channels
- **All tests pass**: Encryption, recovery, mapping, and CNN checkpoints verified

---

## Files Changed

### Modified Files

1. **src/encryption.py** — COMPLETELY REWRITTEN
   - Added `encrypt_rgb_channels()` with unique nonces per channel
   - Added `decrypt_rgb_channels()` with matching derivation
   - Added `get_channel_nonce()` for canonical nonce derivation
   - Added `pack_metadata()` / `unpack_metadata()` for receiver
   - Added comprehensive tests
   - Added detailed documentation

2. **src/rdhei_color.py** — PATCHED
   - Changed to use `encrypt_rgb_channels()` instead of `encrypt_image()`
   - Uses unique nonce per channel: `base_nonce + c + 1`
   - Returns metadata for receiver
   - Added documentation of the security fix

### New Files

1. **tests/test_smoke.py** — Smoke tests for core functionality
2. **tests/test_mapping_ascii.py** — Mapping validation tests
3. **tests/test_cnn_checkpoints.py** — CNN checkpoint validation
4. **FINAL_VALIDATION_REPORT.md** — Comprehensive validation report
5. **MANIFEST.csv** — File inventory with SHA-256 hashes
6. **CHANGELOG.md** — This file

### Copied Files (Unchanged)

All other files copied from original project:
- src/baselines.py
- src/cnn_model.py
- src/comp.py
- src/embedding.py (legacy, not used)
- src/error_maps.py
- src/extraction.py (legacy, not used)
- src/histograms.py
- src/metrics.py
- src/plot_results.py
- src/predictor.py
- src/report_visualizer.py
- src/train.py
- src/utils.py
- src/visualize.py
- models/*.pth (all checkpoints)
- requirements.txt

---

## Detailed Changes

### Change 1: Encryption Module Rewrite

**File**: `src/encryption.py`

**Original Behavior**:
- `encrypt_image()` encrypts 2D grayscale images
- `decrypt_image()` decrypts (same as encrypt for CTR mode)
- No RGB-specific functions
- Original `rdhei_color.py` called `encrypt_image()` for each channel with same nonce

**Identified Defect**:
- Same key + same nonce = same keystream for all 3 channels
- XORing two encrypted channels reveals plaintext XOR
- Complete break of confidentiality

**New Behavior**:
- `encrypt_image()` — unchanged (for grayscale)
- `encrypt_rgb_channels()` — NEW, uses unique nonce per channel
- `decrypt_rgb_channels()` — NEW, matches encryption
- `get_channel_nonce()` — NEW, canonical derivation
- `pack_metadata()` / `unpack_metadata()` — NEW, for receiver

**Nonce Derivation**:
```python
def get_channel_nonce(base_nonce, channel_index):
    return base_nonce + channel_index + 1
```
- R channel (index 0): base_nonce + 1
- G channel (index 1): base_nonce + 2
- B channel (index 2): base_nonce + 3

**Tests Added**:
- Grayscale encrypt/decrypt round-trip
- Unique nonce derivation verification
- RGB encrypt/decrypt round-trip
- No keystream reuse verification

### Change 2: RGB Pipeline Patch

**File**: `src/rdhei_color.py`

**Original Behavior**:
```python
for c, ch_name in enumerate(channel_names):
    channel = image_rgb[:, :, c]
    r = run_rdhei(
        image=channel,
        key=key,
        nonce=nonce,  # SAME nonce for all channels
        ...
    )
```

**New Behavior**:
```python
for c, ch_name in enumerate(channel_names):
    channel = image_rgb[:, :, c]
    channel_nonce = get_channel_nonce(base_nonce, c)  # UNIQUE per channel
    r = run_rdhei(
        image=channel,
        key=key,
        nonce=channel_nonce,  # UNIQUE nonce
        ...
    )
```

**Additional Changes**:
- Added `base_nonce` parameter (renamed from `nonce` for clarity)
- Returns `metadata` field with packed base_nonce
- Returns `per_channel[].nonce_used` for debugging
- Added documentation of the security fix

---

## Test Results Summary

### Encryption Tests
```
[PASS] Grayscale encrypt/decrypt
[PASS] Unique nonce derivation
[PASS] RGB encrypt/decrypt with unique nonces
[PASS] No keystream reuse
```

### Smoke Tests
```
[PASS] Encryption unique nonces
[PASS] Grayscale round-trip (perfect recovery)
[PASS] RGB round-trip (perfect recovery, unique nonces)
[PASS] Metadata pack/unpack
[PASS] Edge cases (constant, gradient, extreme values)
```

### Mapping Validation
```
[PASS] Boundary values (12/12 correct)
[PASS] Recovery random samples (750 cases, 0 failures)
[PASS] Ambiguity check (191 collisions, all recover correctly)
```

### CNN Checkpoint Validation
```
[PASS] Parameter counts (5/5 match)
[PASS] Checkpoint loading (5/5 load correctly)
```

---

## Security Assessment

### Before Fix
**Severity**: CRITICAL  
**Issue**: AES-CTR keystream reuse across RGB channels  
**Impact**: Complete loss of confidentiality  
**CVE-style description**: CWE-323: Reusing a Nonce, Key Pair in Encryption

### After Fix
**Severity**: NONE (for the identified issue)  
**Remaining Risks**:
- No authentication (CTR mode limitation)
- Sequential nonces (acceptable for this use case)
- Single key for all channels (acceptable for this use case)

**Verification**:
- Nonces are unique: R=base+1, G=base+2, B=base+3
- No reuse within the scope of a single encrypted image
- Receiver can reconstruct correct nonces

---

## Backward Compatibility

**BREAKING CHANGE**: Files encrypted with the OLD code cannot be decrypted with the NEW code.

**Reason**: Old code used same nonce for all channels. New code uses unique nonces.

**Migration Path**:
1. Old encrypted files should be considered compromised (keystream reuse)
2. Re-encrypt any data that needs to be preserved
3. Use new code for all future encryption

**For Research Purposes**:
- Clearly state in paper that encryption uses unique nonces per channel
- Document the nonce derivation scheme
- Note that old results may have used the buggy version

---

## Known Issues Not Addressed

1. **Runtime benchmark syntax error** (`run_anal_v2.py`) — Not fixed in this version
2. **Hardcoded metrics in main.py** — Not fixed in this version
3. **Legacy embedding.py/extraction.py** — Not removed (marked as legacy)
4. **Training provenance** — Not documented (checkpoints used as-is)
5. **Experimental results** — Not regenerated (requires running experiments)

These issues were identified in the audit but are not critical for the security fix.

---

## Sign-off

**Repair Completed**: 2026-10-13  
**Security Fix**: VERIFIED  
**All Tests**: PASSING  
**Original Project**: PRESERVED (unchanged)
