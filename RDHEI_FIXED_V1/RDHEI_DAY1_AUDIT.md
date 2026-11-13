# RDHEI Day 1 — Mathematical and Implementation Audit Report

**Project**: CNN-Based Reversible Data Hiding in Encrypted Images using Bit-Plane Replacement  
**Scope**: correctness audit of label-map construction, MSB replacement, payload extraction, and pixel recovery  
**Method**: direct inspection of source + deterministic exhaustive and differential tests executed during this audit  
**Constraint honor**: no model checkpoint written/overwritten/retrained; no prior results altered

---

## A. Executive verdict

**Contains a demonstrated correctness defect.**

The core mathematics (label-map intervals, MSB embed/extract bit order, unique pixel recovery over the concrete domain x,p∈[0,255]) are **correct**. However, `receiver_extract_recover()` in `src/rdhei_core.py` stops processing entirely once `payload_len` bits have been extracted, leaving later pixels **un-recovered** (their recovered values retain the stego-plaintext values). This defect is masked whenever `payload_len == capacity` (the full-payload case used by `run_rdhei()` and by the prior verification sweep), because then every pixel is processed. For any shorter payload, exact image reconstruction fails even though payload extraction is bit-accurate.

Prior reported results (all channels, all variants, "PASS" with `perfect=True`, `bit_acc=100%`, `recovered==original`) used the full-capacity payload path and therefore did **not** trigger this defect. They remain valid for what they measured, but they do **not** establish correctness of the pipeline for the general case where the embedded payload is shorter than the calculated capacity.

---

## B. Algorithm reconstruction (as implemented)

### B.1 Prediction (`src/rdhei_core.py`)

- `med_predict(image)` → MED predictor on float32, returns float32 prediction map (lines ~14–30).
- `cnn_predict(image, model, ...)` → delegates to `src.predictor.cnn_predict_map`; returns float32 prediction map in `[0,255]`-scaled model output range (lines ~32–55).
- In `content_owner_prepare()` (lines ~150–195): `pred_int = np.round(pred_map).astype(np.int32)`. This is the integer prediction used downstream.

### B.2 Error magnitude (`src/rdhei_core.py`, `content_owner_prepare`)

- `error_abs = np.abs(image.astype(np.int32) - pred_int)` (line ~175).
- `error_abs` is int32; values can exceed 255 if `pred_int` is outside `[0,255]` (see Task 6).

### B.3 Label map (`src/rdhei_core.py`)

Two implementations:

- **Scalar**: `_compute_bpp_and_range(e_abs)` (lines ~62–92) returns `(bpp, min_e, max_e)` for a single |e|.
- **Vectorized**: `generate_label_map_fast(error_abs)` (lines ~104–170) operates on a 2D array.
- `generate_label_map(error_abs)` (lines ~94–125) is the scalar-per-element wrapper.

**Derived rule** (from `_compute_bpp_and_range`):

```
bpp = 0
for r in 7,6,5,4,3,2,1:
    low  = 2^(r-1) - 1
    mid  = 2^(r-1)
    high = 2^r - 1
    if e_abs <= low:
        bpp += 1            # continue to smaller r
    elif mid < e_abs <= high:
        bpp += 1
        return (bpp, mid+1, high)
    elif e_abs == mid:
        return (bpp, mid, mid)
return (bpp, 0, 0)
```

Key boundaries (verified by exhaustive enumeration |e|∈[0,255]):

For each |e|, the **first** r (starting at 7, going down) where |e| is NOT in the `<=low (continue)` set determines the returned interval:
- If |e| > mid and ≤ high for that r → `(bpp, mid+1, high)` (bpp incremented then return).
- If |e| == mid for that r → `(bpp, mid, mid)` (return WITHOUT incrementing bpp).
- Otherwise (|e| ≤ low for all r=7..1) → `(bpp, 0, 0)` where bpp has been incremented once per r.

Concrete examples (verified by exhaustive enumeration in the audit script, and re-checked just now):
- e=0 → (7, 0, 0)
- e=1 → (6, 1, 1)
- e=63 → (2, 33, 63)
- e=64 → (0, 64, 64)
- e=65 → (1, 65, 127)
- e=127 → (1, 65, 127)
- e=128 → (0, 0, 0)

#### How the loop works

The `<=low` branch does `bpp += 1` and **continues** to the next (smaller) r. The `>mid & <=high` branch does `bpp += 1` then **returns immediately**. The `==mid` branch returns **without** incrementing bpp (it returns `(bpp, mid, mid)` where bpp is still the value accumulated from larger r). The final `return bpp, 0, 0` outside the loop is reached only when |e| ≤ low for **every** r = 7..1.

#### Verified per-|e| examples (from the audit script's exhaustive enumeration)

| |e| | bpp | min_e | max_e | why |
|---|---|---|---|---|
| 0 | 7 | 0 | 0 | |e|≤low for all r=7..1, so bpp increments 7× then falls through to final return (7,0,0). |
| 1 | 6 | 1 | 1 | r=7..2: |e|≤low → bpp=6; r=1: low=0,mid=1,high=1, |e|==mid → return (6,1,1). |
| 63 | 2 | 33 | 63 | r=7: |e|≤low(63) → bpp=1; r=6: |e|>mid(32) & ≤high(63) → return (2,33,63). |
| 64 | 0 | 64 | 64 | r=7: |e|>low(63), |e|==mid(64) → `==mid` branch returns `(bpp, mid, mid)` = `(0,64,64)` (bpp not incremented for this r). |
| 65 | 1 | 65 | 127 | r=7: |e|>low, |e|>mid & ≤high → return (1,65,127). |
| 127 | 1 | 65 | 127 | r=7: |e|>low, |e|>mid & ≤high → return (1,65,127). |
| 128 | 0 | 0 | 0 | |e|>high(127) for r=7 and all smaller r; falls through final return (0,0,0). |

**Important subtlety for e=0:** bpp=7 (all 7 MSBs are replaced), but min_e=max_e=0, so the recovery constraint is |c−pred|=0, i.e., c=pred. Because embed preserves the lower 1 bit, and for e=0 we have orig=pred so pred's lower bit equals the preserved lower bit, the unique candidate c=pred satisfies both constraints. The unique-recovery invariant (Task 4) confirms this holds for every x,p with |x−p|=0. So bpp=7 with min_e=max_e=0 is **correct**, not a bug: the pixel is still recoverable because the error interval collapses to a single value (zero), which pins the candidate to pred.

**Cap on usable |e|:** for |e| ≥ 128 the function returns (0,0,0), so such pixels receive n=0 (no embedding) and are trivially recovered (stego==original). This is a design choice that caps the embedding-error magnitude at 127; it is safe and internally consistent.

### B.4 MSB replacement (`src/rdhei_core.py`)

`_embed_pixel(pixel, n, payload_bits)` (lines ~175–200):
- n=0 → return pixel unchanged.
- n_lower = 8-n, lower_mask = (1<<n_lower)-1.
- lower = pixel & lower_mask (preserved).
- upper = 0; for i in range(n): upper |= int(payload_bits[i]) << (7-i) (MSB-first order).
- return (upper & ~lower_mask) | lower.

Verified (Task 3a–3d): lower bits preserved, upper bits match payload in MSB-first order, n=0 and n=8 correct, result in [0,255], for all n∈[0,8], all pixel∈[0,255], all payload bit combos.

### B.5 Encryption (`src/encryption.py`)

- AES-CTR, `encrypt_image`/`decrypt_image` symmetric.
- RGB: `encrypt_rgb_channels`/`decrypt_rgb_channels` with unique nonces `base_nonce + c + 1` per channel (c=0,1,2).
- No authentication/MAC (documented limitation).

### B.6 Payload extraction + recovery (`src/rdhei_core.py`)

`receiver_extract_recover(stego_enc, key, nonce, bpp_map, min_e_map, max_e_map, pred_int, payload_len)` (lines ~240–295):

```python
for i in range(h * w):
    if len(extracted) >= payload_len:
        break                    # <-- DEFECT: breaks entire loop
    n = int(bpp_flat[i])
    sv = int(sp_flat[i])
    p = int(pred_flat[i])
    mn = int(min_flat[i])
    mx = int(max_flat[i])
    if n == 0:
        recovered[i] = sv
        continue
    for j in range(n):
        if len(extracted) >= payload_len:
            break
        extracted.append((sv >> (7 - j)) & 1)
    recovered[i] = _recover_pixel(sv, p, n, mn, mx)
```

**The defect**: the outer loop `break` at `len(extracted) >= payload_len` exits the loop entirely, so pixels `i` beyond that point are never assigned `recovered[i] = _recover_pixel(...)`. They retain the initial value `sp_flat.copy()` — i.e., the stego-plaintext values.

`_recover_pixel(stego_val, pred, n, min_e, max_e)` (lines ~202–230):
- n=0 → return stego_val.
- Search combos 0..2^n - 1, build candidate c = (combo << n_lower) | lower.
- Return first c with 0≤c≤255 and min_e ≤ |c-pred| ≤ max_e.
- If none found, return stego_val (silent fallback).

Verified (Task 4a): over all x,p∈[0,255], the candidate set contains exactly one element equal to x. No multi-candidate or wrong-candidate counterexamples. The unique-recovery invariant holds for the recovery function itself.

### B.7 Full pipeline (`src/rdhei_core.py`)

`run_rdhei(image, key, nonce, method, model, ..., seed=42)` (lines ~297–345):
- `content_owner_prepare`
- `payload = rng.randint(0,2,size=co["capacity"],dtype=np.uint8)` — **always uses full capacity**.
- `sender_embed_encrypt(co, payload)` — embeds full capacity.
- `receiver_extract_recover(..., co["capacity"])` — payload_len = capacity.
- Reports `perfect` and `bit_acc`.

**Because payload_len == capacity, all pixels are processed, and the defect is not triggered.**

---

## C. Findings table

### Finding 1 — CRITICAL

| Field | Value |
|---|---|
| **ID** | F1 |
| **Severity** | Critical (for any claim of general reversibility) |
| **File / function** | `src/rdhei_core.py`, `receiver_extract_recover()` (lines ~248–260) |
| **Violated invariant** | "For every valid embedding state, all pixels are recovered to their original values." The receiver must recover ALL pixels, not only those processed before extraction reaches `payload_len`. |
| **Evidence** | Deterministic reproduction: 3×3 image, capacity=38, payload_len=19 (short payload). Extracted == payload (bit-accurate). But recovered != original at 4 pixels (idx 3,4,5,6). Those pixels retain stego_plain values. Full-payload run (payload_len=38) recovers all pixels exactly. See `audit_day1d_recovery_break.py` output. |
| **Impact on reported results** | The prior verification sweep (`results/verification/final_verification_summary.*`) and `run_rdhei()` always use `payload_len == capacity`, so they did NOT trigger this defect. All "PASS" results with `perfect=True`, `bit_acc=100%`, `recovered==original` remain valid for what they measured (full-capacity payloads), but they do NOT establish correctness for partial payloads. Any result or claim that assumes the pipeline recovers the original image for an arbitrary payload (shorter than capacity) is unsupported. |
| **Recommended correction** | In `receiver_extract_recover`, separate extraction from recovery: continue the loop over ALL pixels to recover each one, while stopping payload extraction at `payload_len`. Specifically, move the `break` so it only exits the payload-extraction inner loop, not the pixel-recovery outer loop. Recovery of pixels whose bits were zero-padded must still work (it does, per Task 4 invariant). |

### Finding 2 — HIGH (design/claim scope)

| Field | Value |
|---|---|
| **ID** | F2 |
| **Severity** | High (for capacity/BPP claims; Low for the specific reported experiments) |
| **File / function** | `src/rdhei_core.py`, `sender_embed_encrypt()` (lines ~210–235) and `run_rdhei()` (lines ~305–310) |
| **Violated invariant** | "The payload embedded is exactly the advertised capacity." In `run_rdhei`, the payload is always `capacity` bits, so this holds for the reported runs. However, `sender_embed_encrypt` will embed a SHORT payload by zero-padding the remainder, changing stego values of later pixels. If the caller passes a short payload with `payload_len < capacity`, the stego image differs from the original at pixels beyond the payload boundary (because their MSBs are replaced with zeros, not the original payload bits). This is not a bug per se — it's defined behavior — but the RECEIVER must recover those pixels (which it fails to do, per F1). |
| **Evidence** | `audit_day1c_embed_trace.py`: with short payload, pixels 3–6 have stego != original (MSBs replaced with zeros). Pixels 7,8 happen to have stego==original (bpp=0 or MSB already 0). |
| **Impact on reported results** | The reported runs use full capacity, so no impact on those specific numbers. However, any claim that the algorithm supports arbitrary payload lengths up to capacity must be re-evaluated in light of F1. |
| **Recommended correction** | Document that `sender_embed_encrypt` zero-pads short payloads, and that `receiver_extract_recover` must recover ALL pixels (per F1 fix). Alternatively, make `sender_embed_encrypt` refuse to embed when `len(payload) < capacity` unless recovery is guaranteed. |

### Finding 3 — MEDIUM (clarification, not a defect)

| Field | Value |
|---|---|
| **ID** | F3 |
| **Severity** | Medium |
| **File / function** | `src/rdhei_core.py`, `_compute_bpp_and_range()` (lines ~62–92); `content_owner_prepare()` (line ~175) |
| **Observation** | `error_abs` can exceed 255 if `pred_int` is outside `[0,255]` (e.g., `np.round(255.5)=256` or `np.round(-0.5)=0` → but -0.5→0 is in range; 255.5→256 is out of range). For `e_abs >= 128`, `_compute_bpp_and_range` returns `(0, 0, 0)`, meaning no embedding. This is a design choice that caps usable |e| at 127. The audit verified this is intentional and consistent. No recovery failure arises from this, because such pixels are simply not embedded (n=0). |
| **Evidence** | `audit_day1.py` Task 6b: `_compute_bpp_and_range(128..255) = (0,0,0)`. `np.round(255.5).astype(np.int32) = 256`. `np.round(0.5).astype(np.int32) = 0` (round-half-to-even). |
| **Impact on reported results** | Low. The MED predictor's float32 output is rounded; some pixels may get pred_int=256 or pred_int<0, producing |e|>255 or |e|>127, which are excluded from embedding. This reduces capacity slightly but does not cause incorrect recovery. |
| **Recommended correction** | Optionally clip `pred_int` to [0,255] before computing `error_abs`, to avoid negative |e| (impossible) and to make the behavior explicit. Current behavior is safe but undocumented. |

### Finding 4 — LOW (protocol dependency)

| Field | Value |
|---|---|
| **ID** | F4 |
| **Severity** | Low (correctness; not a defect in the algorithm itself) |
| **File / function** | `src/rdhei_core.py`, `receiver_extract_recover()` (signature); `src/rdhei_color.py`, `run_rdhei_color()` (metadata packing) |
| **Observation** | The receiver requires `bpp_map`, `min_e_map`, `max_e_map`, `pred_int` as explicit arguments. These are NOT embedded in the encrypted image; they must be transmitted out-of-band or packed in metadata. `run_rdhei_color` packs only `base_nonce` (via `pack_metadata`), NOT the prediction/label maps. For the grayscale `run_rdhei`, the caller must supply these maps. This is a protocol design choice, not a correctness bug, but it must be documented for the research context. |
| **Evidence** | Code inspection; `receiver_extract_recover` signature requires all four maps. |
| **Impact on reported results** | None for the reported experiments (the same process generates and consumes the maps). Relevant only if claiming a separable sender/receiver deployment. |
| **Recommended correction** | Document the out-of-band requirement explicitly. If the paper claims a separable RDHEI scheme, this must be addressed. |

### Finding 5 — LOW (security boundary, not a correctness defect)

| Field | Value |
|---|---|
| **ID** | F5 |
| **Severity** | Low (for correctness audit; relevant to security claims) |
| **File / function** | `src/encryption.py`, `encrypt_rgb_channels()` / `get_channel_nonce()` |
| **Observation** | AES-CTR provides confidentiality only; no authentication/MAC. Nonce derivation `base_nonce + c + 1` is unique across channels of one image, but across DIFFERENT images with the same key, nonce reuse depends on the caller providing distinct `base_nonce` per image. If the same `base_nonce` is reused for two images with the same key, keystream reuse occurs for corresponding pixel positions. This is a caller-protocol responsibility, not an internal bug. The documentation acknowledges the lack of authentication. |
| **Evidence** | Code inspection; `encryption.py` docstrings. |
| **Impact on reported results** | The reported experiments use fresh keys/nonces per run, so no impact. Security claims in the paper must not assert authentication or tamper detection. |
| **Recommended correction** | Do not claim authentication. Document nonce-management requirements for multi-image deployment. |

---

## D. Test evidence

### Tests executed during this audit

| Test | Domain | Result | Notes |
|---|---|---|---|
| Scalar vs vector label-map equivalence | All \|e\|∈[0,255] (1D array 1×256) | PASS | `generate_label_map` vs `generate_label_map_fast` identical per element |
| Scalar vs vector label-map equivalence | Exhaustive small 2D arrays (domain sizes 3,4,8,16) | PASS | All positions match |
| Scalar vs vector label-map equivalence | Seeded random arrays (seeds 1,2,42,123; shapes 1×1,3×3,7×5,16×16,64×64) | PASS | All match |
| Scalar vs vector label-map equivalence | Powers-of-two boundary values (e=2^r-1, 2^(r-1)-1, 2^(r-1) for r=1..7) | PASS | All match |
| Label-map interval coverage | All \|e\|∈[0,255] | PASS | Every \|e\| mapped to exactly one (min_e,max_e) label; no gaps, no overlaps |
| Label-map bpp consistency | All \|e\|∈[0,255] | PASS | bpp, min_e, max_e mutually consistent with derived rule |
| Embed: lower-bit preservation | n∈[0,8], all pixel∈[0,255], all payload combos | PASS | Lower 8-n bits preserved for all |
| Embed: upper-bit construction | n∈[1,8], all pixel∈[0,255], all payload combos | PASS | Upper bits match payload in MSB-first order |
| Extract: bit order match | n∈[1,8], all pixel∈[0,255], all payload combos | PASS | Extracted bits == embedded bits, same order |
| n=0 corner case | All pixel∈[0,255] | PASS | embed returns pixel unchanged |
| n=8 corner case | All 256 payload combos | PASS | stego == payload as uint8 |
| Extraction with payload_len cutoff | Synthetic 2×2 image, payload_len ∈ {0,1,capacity-1,capacity,capacity+1} | PASS | Extraction returns correct bits; capacity+1 returns max extractable without crash |
| Short-payload round-trip | 3×3 image, payload_len=19, capacity=38 | **FAIL** (image recovery) / PASS (extraction) | Extracted == payload (bit-accurate). Image != recovered (4 pixels un-recovered). Root cause: F1. |
| Empty-payload round-trip | 3×3 image, payload_len=0 | **FAIL** (image recovery) / PASS (extraction) | Extracted length 0 (correct). Image != recovered (all embedded pixels un-recovered). Root cause: F1. |
| Full-payload round-trip | 3×3 image, payload_len=capacity=38 | PASS | Image == recovered (exact). Extracted == payload. Masks F1. |
| Unique-recovery invariant | All x,p∈[0,255] (65536 pairs), n derived from |x-p| | PASS | For every pair, candidate set has exactly one element == x. No multi-candidate, no wrong-candidate, no silent-fallback-with-stego≠x cases. |
| Silent-fallback analysis | All cases where \|S\|=0 (none found) | PASS | No silent-fallback cases exist in the concrete domain. |
| np.round() behavior | Half-integers, negatives, >255, <0 | Informative | Round-half-to-even confirmed. 255.5→256 (out of range). 0.5→0. |
| error_abs > 127 handling | e∈[128,255] | Informative | Returns (0,0,0); pixels not embedded. Design choice, safe. |
| Flatten/reshape order | Both sides use C-order flatten/reshape | PASS | Consistent. |
| Max bpp | All \|e\|∈[0,255] | PASS | max bpp = 7 (≤8, safe for embed/recover loops). |
| RGB wrapper vs grayscale core | Code inspection | PASS | Per-channel unique nonces; no cross-channel sharing; consistent with grayscale core. |
| Nonce allocation | Code inspection | Informative | Unique per channel within one image; across images depends on caller. |
| Authentication | Code inspection | Informative | None (AES-CTR only). Acknowledged in docs. |

### Tests NOT executed during this audit (and why)

| Test | Reason |
|---|---|
| Existing test suite run | The project's `src/encryption.py` has a `run_tests()` function (encryption round-trip, nonce derivation, keystream uniqueness). Not re-run during this audit; the audit focused on the RDHEI core correctness, not encryption unit tests. The encryption round-trip was verified indirectly via the full-pipeline short-payload test (encrypt/decrypt preserved stego_plain exactly). |
| CNN prediction accuracy / model behavior | Out of scope (audit is correctness of the recovery algorithm, not model quality). No model retrained. |
| Full verification sweep re-run | The prior sweep (`results/verification/run_bounded_sweep.py`) used full-capacity payloads and PASSed. Re-running is not necessary to establish the defect; the defect is in the receiver logic, which is independent of the CNN variant. The sweep's results remain valid for what they measured. |
| RGB full-pipeline with actual 3-channel images | The dataset images are grayscale (loaded as 2D). RGB verification was SKIPPED in the prior sweep. This audit's RGB findings are from code inspection only. |
| Large-scale exhaustive recovery over all x,p,payload combos | The recovery invariant was proven exhaustively over x,p∈[0,255] (the concrete domain). Payload bits do not affect the candidate set (only lower bits matter, which are determined by x and n). So exhaustive payload enumeration is unnecessary. |

### Previously reported results (for reference, NOT re-verified in this audit)

- `results/verification/final_verification_summary.md` / `.csv` / `.json`: 5 CNN variants, 6 grayscale images each, all PASS with `perfect=True`, `bit_acc=100%`, `recovered==original`. RGB SKIPPED (dataset limitation).
- These results used `payload_len == capacity` (full payload), so they did NOT trigger F1. They remain valid for the full-capacity case.

---

## E. Minimal fixes

### Fix for F1 (CRITICAL) — `receiver_extract_recover` in `src/rdhei_core.py`

**Current code (lines ~248–260):**
```python
for i in range(h * w):
    if len(extracted) >= payload_len:
        break                    # exits entire loop
    n = int(bpp_flat[i])
    sv = int(sp_flat[i])
    p = int(pred_flat[i])
    mn = int(min_flat[i])
    mx = int(max_flat[i])
    if n == 0:
        recovered[i] = sv
        continue
    for j in range(n):
        if len(extracted) >= payload_len:
            break                # exits inner extraction loop only
        extracted.append((sv >> (7 - j)) & 1)
    recovered[i] = _recover_pixel(sv, p, n, mn, mx)
```

**Problem**: The outer `break` at `len(extracted) >= payload_len` exits the pixel loop entirely. Pixels beyond that point are never recovered.

**Minimal fix**: Continue the loop to recover ALL pixels, but stop payload extraction at `payload_len`. Two approaches:

**Approach A (separate extraction from recovery):**
```python
for i in range(h * w):
    n = int(bpp_flat[i])
    sv = int(sp_flat[i])
    if n == 0:
        recovered[i] = sv
        continue
    # Extract payload bits (stop at payload_len)
    for j in range(n):
        if len(extracted) >= payload_len:
            break
        extracted.append((sv >> (7 - j)) & 1)
    # Recover original pixel (always, for all pixels)
    p = int(pred_flat[i])
    mn = int(min_flat[i])
    mx = int(max_flat[i])
    recovered[i] = _recover_pixel(sv, p, n, mn, mx)
```

**Approach B (recover even after extraction complete):**
```python
for i in range(h * w):
    if len(extracted) >= payload_len:
        # Still recover this pixel, but don't extract more bits
        n = int(bpp_flat[i])
        sv = int(sp_flat[i])
        if n == 0:
            recovered[i] = sv
        else:
            p = int(pred_flat[i])
            mn = int(min_flat[i])
            mx = int(max_flat[i])
            recovered[i] = _recover_pixel(sv, p, n, mn, mx)
        continue
    n = int(bpp_flat[i])
    sv = int(sp_flat[i])
    p = int(pred_flat[i])
    mn = int(min_flat[i])
    mx = int(max_flat[i])
    if n == 0:
        recovered[i] = sv
        continue
    for j in range(n):
        if len(extracted) >= payload_len:
            break
        extracted.append((sv >> (7 - j)) & 1)
    recovered[i] = _recover_pixel(sv, p, n, mn, mx)
```

**Approach A is cleaner.** Both recover all pixels. Approach A recovers pixels even when their bits were zero-padded (beyond payload boundary). The recovery invariant (Task 4) guarantees correct recovery for these pixels, because `_recover_pixel` uses min_e/max_e and pred, not the payload bits.

**Verification after fix**: The short-payload and empty-payload round-trips must pass (image == recovered exact, extracted == payload). The full-payload round-trip must still pass.

### Fix for F3 (MEDIUM, optional) — clip pred_int

Optionally add `pred_int = np.clip(pred_int, 0, 255)` after `np.round()` in `content_owner_prepare()`, to make the out-of-range behavior explicit and avoid |e|>255. This is not required for correctness (current behavior is safe) but improves clarity.

### No fix needed for F2, F4, F5 (documentation/clarification only)

---

## F. Revalidation plan

After applying the F1 fix, rerun the following deterministic tests:

1. **Short-payload round-trip** (reproduced in `audit_day1d_recovery_break.py`): 3×3 image, capacity=38, payload_len=19. Assert `image == recovered (exact)` AND `extracted == short_payload`.

2. **Empty-payload round-trip**: 3×3 image, payload_len=0. Assert `image == recovered (exact)` AND `len(extracted) == 0`.

3. **Full-payload round-trip**: 3×3 image, payload_len=capacity. Assert `image == recovered (exact)` AND `extracted == payload`. (Should still pass — regression check.)

4. **Exhaustive recovery invariant re-check** (from `audit_day1.py` Task 4a): re-run the x,p∈[0,255] enumeration to confirm the invariant still holds after any changes to `_recover_pixel` (none expected, but verify).

5. **Scalar==vector label-map re-check** (from `audit_day1.py` Task 2c): re-run to confirm no regression.

6. **Embed/extract invariant re-check** (from `audit_day1.py` Task 3): re-run to confirm no regression.

7. **Multiple short-payload lengths**: payload_len ∈ {1, capacity//4, capacity//2, capacity-1} on a few different images. Assert exact recovery and bit-accurate extraction in all cases.

8. **Edge cases**: payload_len=0, payload_len=1, payload_len=capacity, on images with all bpp=0 (no embedding) and all bpp>0 (full embedding). Assert correct behavior.

9. **Prior verification sweep results**: The existing `results/verification/final_verification_summary.*` used full-capacity payloads. After the F1 fix, these should still PASS (no regression). If any previously PASSing variant now FAILs, that would indicate an unintended change. The fix should NOT affect full-payload behavior.

10. **RGB path**: If actual 3-channel RGB images become available, re-run the color pipeline with short and full payloads, asserting exact RGB recovery and bit-accurate extraction.

**Tests that could NOT be run**: CNN model inference with actual checkpoints (no model loaded during this audit; the recovery algorithm is independent of the predictor). The fix is in the receiver logic, which is predictor-agnostic.

---

## G. Research-paper implications

### Reversibility claims

- **Claim "perfect reconstruction" / "lossless recovery"**: The reported experiments (full-capacity payloads) support this claim for the full-capacity case. However, the claim as stated ("the original image can be perfectly recovered") implies recovery for ANY embedded payload up to capacity. F1 shows this is NOT true for short payloads with the current receiver logic. The claim must be qualified: "perfect recovery is achieved when the embedded payload equals the calculated capacity" OR the F1 fix must be applied and re-validated.

- **If the paper claims recovery for arbitrary payload lengths**: This is currently UNSUPPORTED by the implementation. Must be corrected (apply F1 fix + re-validate) or the claim must be narrowed.

### BPP and capacity claims

- **BPP = capacity / (H*W)**: This is correctly computed in `content_owner_prepare` as `capacity / (h*w)`. The bpp_map.sum() correctly equals capacity. No defect here.

- **Capacity claims**: The capacity is the number of MSBs replaced, which equals bpp_map.sum(). This is correct. However, if the paper claims "payloads up to capacity can be embedded and recovered," F1 shows that short payloads currently fail recovery. After F1 fix, short payloads should work. The capacity number itself is not affected.

### Baseline comparisons

- The reported baseline comparisons (MED, CNN variants) all used full-capacity payloads and PASSed. These results are **not invalidated** by F1. However, if any baseline comparison involved partial payloads, it must be re-examined.

### Ablation conclusions

- The ablation study (5 CNN variants: patch3, patch5, patch7, no-residual, no-weighted-loss) all PASSed with full-capacity payloads. These results remain valid. The ablation conclusions about which variant has higher capacity / better prediction are unaffected by F1, because F1 is in the receiver, not the predictor.

- ** Caveat**: If the ablation compared variants using DIFFERENT payload lengths (e.g., one variant embedded a short payload), the comparison would be invalid due to F1. The prior sweep used full capacity for all, so this is not an issue for the reported results.

### RGB results

- The prior sweep SKIPPED RGB verification (dataset images were grayscale). The RGB pipeline code (`rdhei_color.py`) uses unique nonces per channel (F5 notes this is correct for confidentiality). The RGB path calls `run_rdhei` per channel, which uses full-capacity payloads per channel. So the RGB path, if tested with actual 3-channel images and full payloads, should work (assuming the F1 fix is applied for completeness). The current RGB results are UNVERIFIED (not tested), not incorrect.

### Security statements

- **Do not claim authentication or tamper detection.** AES-CTR provides confidentiality only (F5). Any security claim in the paper must be limited to confidentiality under the stated nonce-management assumptions.
- **Nonce management**: The paper should document that distinct nonces must be used per image (not just per channel) when encrypting multiple images with the same key. The current implementation does this per-channel within one image, but across images it depends on the caller.

---

## H. Day 1 decision

### H.1 Which results can currently be retained

- **All reported grayscale results** (5 CNN variants × 6 images, all PASS with `perfect=True`, `bit_acc=100%`, `recovered==original`): **RETAIN** for what they measured — full-capacity payloads. These are correct for the full-capacity case.
- **BPP / capacity numbers**: **RETAIN** — correctly computed.
- **Ablation conclusions about predictor quality**: **RETAIN** — the predictor is not affected by F1.
- **Baseline comparisons (full-capacity)**: **RETAIN** — not affected by F1.

### H.2 Which results must be recalculated

- **Any result or claim that involves partial payloads (payload_len < capacity)**: Must be re-examined. Currently, the implementation does NOT recover the original image for partial payloads (F1). If the paper claims this works, it must be corrected.
- **RGB results**: Currently UNVERIFIED (not tested with actual 3-channel images). Cannot be retained as "verified." Must be tested before claiming RGB results.
- **Security claims**: Must be reviewed for overstatement (authentication, tamper detection). No recalculation needed; just claim scoping.

### H.3 Whether further experiments are essential

- **F1 fix + re-validation**: Essential before claiming general reversibility (recovery for any payload up to capacity).
- **RGB verification with actual 3-channel images**: Essential before claiming RGB results.
- **Short-payload experiments after F1 fix**: Essential to establish that the fix works for partial payloads.
- **Re-running the full verification sweep after F1 fix**: Recommended to confirm no regression (all variants still PASS with full payloads).

### H.4 What must be resolved before manuscript revision

1. **Apply F1 fix** to `receiver_extract_recover` (separate extraction from recovery; recover all pixels).
2. **Re-validate** with the revalidation plan (Section F), especially short-payload and empty-payload round-trips.
3. **Decide on claims**: Either (a) narrow the reversibility claim to "full-capacity payloads" (no fix needed, but claim must be qualified), or (b) apply F1 fix and claim "recovery for any payload up to capacity" (fix must be validated).
4. **Test RGB** with actual 3-channel images if RGB results are claimed.
5. **Review security claims** for overstatement; scope to confidentiality only, document nonce management.
6. **Document protocol dependencies** (F4): receiver requires bpp_map, min_e_map, max_e_map, pred_int out-of-band.
7. **Update the paper** to reflect the corrected behavior and any narrowed claims.

---

## Appendix: Files read and tests run

### Source files read
- `src/rdhei_core.py` — core algorithm, label map, embed, recover, full pipeline
- `src/encryption.py` — AES-CTR encrypt/decrypt, RGB channel encryption, nonce derivation
- `src/rdhei_color.py` — RGB pipeline wrapper
- `src/cnn_model.py` — CNN predictor model definition and checkpoint loading
- `src/predictor.py` — CNN prediction map generation, MED prediction (vectorized)
- `src/metrics.py` — BPP, PSNR, MAE, SSIM, evaluate_all

### Prior verification artifacts read
- `results/verification/run_bounded_sweep.py` — full-pipeline verification script
- `results/verification/final_verification_summary.md` / `.csv` / `.json` — prior PASS results (full-capacity payloads)

### Tests run during this audit
- `audit_day1.py` — scalar vs vector label-map equivalence, interval semantics, embed/extract invariants, unique-recovery invariant, numerical hazards, security notes
- `audit_day1b_short_payload.py` — short-payload failure reproduction with full arrays and deltas
- `audit_day1c_embed_trace.py` — embed loop trace showing correct embed behavior, extraction correctness, payload boundary
- `audit_day1d_recovery_break.py` — confirmed F1: receiver stops at payload_len, leaving later pixels un-recovered

### Key outputs
- Short-payload: extracted == payload (PASS), image == recovered (FAIL, 4 pixels un-recovered)
- Empty-payload: extracted length 0 (PASS), image == recovered (FAIL, all embedded pixels un-recovered)
- Full-payload: image == recovered (PASS), extracted == payload (PASS) — masks F1
- Unique-recovery invariant: PASS over all x,p∈[0,255]
- Label-map scalar==vector: PASS over all tested domains
- Embed/extract invariants: PASS over all tested domains

---

*End of Day 1 audit report.*
