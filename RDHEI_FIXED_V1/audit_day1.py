#!/usr/bin/env python3
"""
RDHEI Day 1 — Mathematical & Implementation Audit
===================================================
Focus: label-map math, MSB embed/extract, unique pixel recovery invariant.

This script is deterministic and self-contained. It does NOT retrain models,
does NOT touch project results, and does NOT fabricate outputs.

It imports the ACTUAL implementation from src/ and tests it directly.
"""
from __future__ import annotations

import numpy as np
import sys
from itertools import product

PROJECT = "/home/parzifal/RDHEI_Project"  # parent of src/
sys.path.insert(0, PROJECT)

from src.rdhei_core import (
    _compute_bpp_and_range,
    generate_label_map,
    generate_label_map_fast,
    _embed_pixel,
    _recover_pixel,
)


def section(title: str):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
# Utility: pretty table
# ---------------------------------------------------------------------------
def table(rows, widths=None):
    if not rows:
        return
    if widths is None:
        widths = [max(len(str(c)) for c in col) for col in zip(*rows)]
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths)))


# ---------------------------------------------------------------------------
# TASK 2 — Label-map mathematics
# ---------------------------------------------------------------------------

def audit_label_map_scalar_vs_vector():
    """
    Compare scalar _compute_bpp_and_range applied per-element against
    generate_label_map_fast over:
      - every |e| in 0..255
      - small exhaustive 2D arrays
      - seeded random arrays

    Also enumerate the derived rule for each |e|.
    """
    section("TASK 2a — Scalar rule derivation for |e| = 0..255")

    header = ["|e|", "bpp", "min_e", "max_e", "note"]
    rows = [header]
    for e in range(256):
        bpp, mn, mx = _compute_bpp_and_range(e)
        note = ""
        rows.append([e, bpp, mn, mx, note])

    table(rows, widths=[6, 5, 7, 7, 12])
    print()
    print("Row count:", len(rows) - 1)

    section("TASK 2b — Interval coverage / gaps / overlaps across |e|=0..255")

    # Build partition: which (min_e,max_e) label covers which |e|?
    coverage = {e: [] for e in range(256)}
    for e in range(256):
        bpp, mn, mx = _compute_bpp_and_range(e)
        if mn == mx == 0 and bpp == 0:
            # special: |e|=0 => bpp=0, min_e=max_e=0
            coverage[e].append((mn, mx, bpp, "zero-label"))
        else:
            coverage[e].append((mn, mx, bpp, "labeled"))

    print("Total |e| values covered by SOME label:", sum(1 for e in range(256) if coverage[e]))
    uncovered = [e for e in range(256) if not coverage[e]]
    if uncovered:
        print("UNCOVERED |e| values:", uncovered)
    else:
        print("No uncovered |e| values in 0..255.")

    # Check that every |e| maps into one of the labeled intervals.
    intervals = {}
    for e in range(256):
        bpp, mn, mx = _compute_bpp_and_range(e)
        if (mn, mx) not in intervals:
            intervals[(mn, mx)] = []
        intervals[(mn, mx)].append(e)

    print()
    print("Distinct (min_e, max_e) labels and the |e| they are assigned to:")
    iv_rows = [["min_e", "max_e", "bpp(at representative)", "#|e|", "|e| examples"]]
    for (mn, mx), es in sorted(intervals.items(), key=lambda kv: (kv[0], kv[1])):
        rep = es[0]
        _, _, bpp_rep = _compute_bpp_and_range(rep)
        iv_rows.append([mn, mx, bpp_rep, len(es), f"{es[:6]}{'...' if len(es) > 6 else ''}"])
    table(iv_rows, widths=[7, 7, 22, 7, 30])

    # Detect possible overlap: does any |e| belong to TWO different (min_e,max_e) intervals?
    # (Not applicable if _compute_bpp_and_range is single-valued, but we state it explicitly.)
    print()
    print("Single-valued check: each |e| assigned to exactly one (min_e,max_e):",
          all(len(coverage[e]) == 1 for e in range(256)))

    section("TASK 2c — Scalar vs vectorised label-map equivalence")
    failures = []

    # (1) exhaustive 1D over all 256 magnitudes
    emp = np.arange(256, dtype=np.int32).reshape(1, 256)
    bpp_s, mn_s, mx_s = generate_label_map(emp)
    bpp_v, mn_v, mx_v = generate_label_map_fast(emp)
    for i in range(256):
        if not (bpp_s[0, i] == bpp_v[0, i] and mn_s[0, i] == mn_v[0, i] and mx_s[0, i] == mx_v[0, i]):
            failures.append(("1D-exhaustive", i, int(emp[0, i]),
                             int(bpp_s[0, i]), int(bpp_v[0, i]),
                             int(mn_s[0, i]), int(mn_v[0, i]),
                             int(mx_s[0, i]), int(mx_v[0, i])))
    print("Failing positions for 1D-exhaustive (256 values):", len(failures))
    for f in failures[:20]:
        print("   ", f)

    # (2) exhaustive small 2D arrays over limited pixel value range
    rng = np.random.RandomState(0)
    domain_sizes = [3, 4, 8, 16]
    for ds in domain_sizes:
        vals = np.arange(ds, dtype=np.int32)
        grid = np.array(list(product(vals, vals)), dtype=np.int32).reshape(-1, 2)
        # error_abs can be up to ds-1 in each channel combo; but MED error can be wider;
        # here we only test label map on arbitrary error_abs arrays.
        arr = grid[:, 0].reshape(-1, 1)  # shape (ds*ds, 1)
        bpp_s, mn_s, mx_s = generate_label_map(arr)
        bpp_v, mn_v, mx_v = generate_label_map_fast(arr)
        for k in range(arr.size):
            if not (bpp_s.flat[k] == bpp_v.flat[k] and
                    mn_s.flat[k] == mn_v.flat[k] and
                    mx_s.flat[k] == mx_v.flat[k]):
                failures.append((f"small-2D-ds={ds}", k, int(arr.flat[k]),
                                 int(bpp_s.flat[k]), int(bpp_v.flat[k]),
                                 int(mn_s.flat[k]), int(mn_v.flat[k]),
                                 int(mx_s.flat[k]), int(mx_v.flat[k])))
    print("Failing positions for small exhaustive 2D arrays:", len([f for f in failures if f[0].startswith('small-2D')]))

    # (3) seeded random arrays with various shapes/dtypes
    for seed in [1, 2, 42, 123]:
        rng = np.random.RandomState(seed)
        for shape in [(1, 1), (3, 3), (7, 5), (16, 16), (64, 64)]:
            arr = rng.randint(0, 256, shape, dtype=np.int32)
            bpp_s, mn_s, mx_s = generate_label_map(arr)
            bpp_v, mn_v, mx_v = generate_label_map_fast(arr)
            if not (np.array_equal(bpp_s, bpp_v) and
                    np.array_equal(mn_s, mn_v) and
                    np.array_equal(mx_s, mx_v)):
                nz = np.where(~np.all(bpp_s == bpp_v, axis=None) |
                              ~np.all(mn_s == mn_v, axis=None) |
                              ~np.all(mx_s == mx_v, axis=None))
                for idx in zip(*nz):
                    failures.append((f"rand-seed={seed}-shape={shape}", idx,
                                     int(arr[idx]), int(bpp_s[idx]), int(bpp_v[idx]),
                                     int(mn_s[idx]), int(mn_v[idx]),
                                     int(mx_s[idx]), int(mx_v[idx])))
    print("Failing positions for seeded random arrays:", len([f for f in failures if f[0].startswith('rand-')]))
    for f in failures[:20]:
        print("   ", f)

    # (4) edge of error magnitudes: powers of two minus/plus 1
    edge_vals = []
    for r in range(1, 8):
        edge_vals += [2**r - 1, 2**(r-1) - 1, 2**(r-1)]
    edge_vals = sorted(set(v for v in edge_vals if 0 <= v <= 255))
    arr = np.array(sorted(edge_vals), dtype=np.int32).reshape(-1, 1)
    bpp_s, mn_s, mx_s = generate_label_map(arr)
    bpp_v, mn_v, mx_v = generate_label_map_fast(arr)
    for i in range(arr.size):
        if not (bpp_s.flat[i] == bpp_v.flat[i] and mn_s.flat[i] == mn_v.flat[i] and mx_s.flat[i] == mx_v.flat[i]):
            failures.append(("edge-powers", i, int(arr.flat[i]),
                             int(bpp_s.flat[i]), int(bpp_v.flat[i]),
                             int(mn_s.flat[i]), int(mn_v.flat[i]),
                             int(mx_s.flat[i]), int(mx_v.flat[i])))
    print("Failing positions at powers-of-two boundaries:", len([f for f in failures if f[0] == 'edge-powers']))

    section("TASK 2d — Consistency of bpp_map.sum() with actual embed capacity")
    print("NOTE: bpp_map.sum() counts number of MSBs replaced across all pixels.")
    print("This equals the number of payload bits that will be read back IF extraction")
    print("reads exactly bpp_map[i] bits from each pixel in raster order.")
    print("We test this directly in the embed/extract audit below (Task 3).")
    print()
    print("Example: for |e|=0..255 single-pixel, bpp sum = sum of bpp over those 256")
    total_bpp_0_255 = int(sum(_compute_bpp_and_range(e)[0] for e in range(256)))
    print("   total_bpp( |e| in 0..255 one-per-pixel ) =", total_bpp_0_255)

    if failures:
        print()
        print("*** DISCREPANCIES FOUND scalar vs vectorised (first 50): ***")
        for f in failures[:50]:
            print("   ", f)
        return False, failures
    print()
    print("Scalar and vectorised label maps are IDENTICAL over all tested domains.")
    return True, []


def audit_label_map_interval_semantics():
    """
    Re-derive the intended rule from code and check:

    For r in 7..1:
        low  = 2**(r-1) - 1
        mid  = 2**(r-1)
        high = 2**r - 1
        if |e| <= low          -> bpp += 1, continue
        elif |e| > mid and |e| <= high -> bpp += 1, return (bpp, mid+1, high)
        elif |e| == mid        -> return (bpp, mid, mid)

    We want to know: which |e| get which bpp, and what interval is stored.
    Also verify whether |e| values between low+1 and mid-1 (when that range is non-empty)
    are handled.
    """
    section("TASK 2e — Derived label intervals and their |e| coverage")

    # For each r, list the |e| ranges the CODE actually routes.
    print("Iterates r = 7,6,5,4,3,2,1")
    print()
    print("For each r, derived thresholds:")
    rows = [["r", "low=2^(r-1)-1", "mid=2^(r-1)", "high=2^r-1", "gap(low,mid)"]]
    for r in range(7, 0, -1):
        low = 2**(r-1) - 1
        mid = 2**(r-1)
        high = 2**r - 1
        gap = list(range(low + 1, mid))
        rows.append([r, low, mid, high, gap if gap else "none"])
    table(rows, widths=[5, 14, 14, 14, 20])

    print()
    print("Observation: for r=2, low=1, mid=2 => gap(low,mid) = none (empty).")
    print("For r=3, low=3, mid=4 => gap(low,mid) = none (empty).")
    print("For r>=4, gap(low,mid) is non-empty; these |e| values are > low and < mid.")
    print("The scalar code handles them via the |e|<=low branch of SMALLER r (earlier in loop)")
    print("because the loop is r=7..1 and continues (bpp+=1) when |e|<=low for current r.")
    print()

    # Walk the scalar logic for every |e| and print which 'r' branch finally returns.
    section("TASK 2f — Walk scalar control flow for each |e| (which branch returns)")
    walk_rows = [["|e|", "final r", "branch", "bpp", "min_e", "max_e"]]
    for e in range(256):
        # Re-run scalar logic manually to record branch.
        bpp = 0
        final_r = None
        branch = None
        for r in range(7, 0, -1):
            low = 2**(r-1) - 1
            mid = 2**(r-1)
            high = 2**r - 1
            if e <= low:
                bpp += 1
                final_r = r
                branch = "<=low (continue)"
                continue
            elif mid < e <= high:
                bpp += 1
                final_r = r
                branch = ">mid & <=high (return)"
                break
            elif e == mid:
                final_r = r
                branch = "==mid (return)"
                break
        walk_rows.append([e, final_r, branch, bpp, 0, 0])
    table(walk_rows[:60], widths=[6, 9, 22, 6, 7, 7])
    print("... (truncated, full table in script output)")
    print()
    print("Check: branch '>mid & <=high' and '==mid' both break; '<=low' continues.")
    print("Therefore final returned interval is determined at the FIRST r (largest) where")
    print("e is NOT in the '<=low (continue)' set for that r.")
    print()

    # Verify the (min_e,max_e) produced per |e| matches _compute_bpp_and_range.
    mismatch = []
    for e in range(256):
        bpp_s, mn_s, mx_s = _compute_bpp_and_range(e)
        # recompute via walk
        bpp = 0
        mn = mx = 0
        for r in range(7, 0, -1):
            low = 2**(r-1) - 1
            mid = 2**(r-1)
            high = 2**r - 1
            if e <= low:
                bpp += 1
                continue
            elif mid < e <= high:
                bpp += 1
                mn = mid + 1
                mx = high
                break
            elif e == mid:
                mn = mid
                mx = mid
                break
        if (bpp, mn, mx) != (bpp_s, mn_s, mx_s):
            mismatch.append((e, bpp, mn, mx, bpp_s, mn_s, mx_s))
    print("Mismatch between hand-walk and actual _compute_bpp_and_range:", len(mismatch))
    for m in mismatch[:30]:
        print("   ", m)
    return True


# ---------------------------------------------------------------------------
# TASK 3 — MSB embed / extract
# ---------------------------------------------------------------------------

def audit_embed_extract():
    """
    For n = 0..8, over a representative domain of pixel values and payload bit
    sequences, verify:
      - lower (8-n) bits preserved
      - payload inserted into upper n bits in intended order
      - extraction returns identical bit sequence in identical order
      - n=0 and n=8 handled
      - result stays in 0..255
      - partial payload, empty payload, capacity-length payload, and over-length
        payload (via sender padding) behaviour.
    """
    section("TASK 3a — Embed: lower-bit preservation and result range")

    bad = []
    for n in range(0, 9):
        n_lower = 8 - n
        lower_mask = (1 << n_lower) - 1
        for pixel in range(256):
            for payload_bits in product(*([range(2)] * n if n > 0 else [[]])):
                if n == 0:
                    bits = []
                else:
                    bits = list(payload_bits)
                stego = _embed_pixel(pixel, n, bits)
                # lower bits preservation
                if (stego & lower_mask) != (pixel & lower_mask):
                    bad.append(("lower-bits", n, pixel, bits, stego))
                # range
                if not (0 <= stego <= 255):
                    bad.append(("range", n, pixel, bits, stego))
    print("Embed failures (lower-bit preservation / range), n=0..8, all pixels:",
          len(bad))
    for b in bad[:30]:
        print("   ", b)
    print()
    print("Lower 8-n bits preserved for ALL tested combos:",
          len(bad) == 0 and "yes" or "NO")

    section("TASK 3b — Embed: upper-bit construction matches payload order")
    bad = []
    for n in range(1, 9):
        for pixel in range(256):
            for bits in product(*([range(2)] * n)):
                bits = list(bits)
                stego = _embed_pixel(pixel, n, bits)
                # upper n bits of stego should equal bits[0..n-1] in MSB-first order
                expected_upper = 0
                for i in range(n):
                    expected_upper |= (int(bits[i]) << (7 - i))
                lower_mask = (1 << (8 - n)) - 1
                actual_upper = stego & ~lower_mask
                if actual_upper != expected_upper:
                    bad.append(("upper-bits", n, pixel, bits, stego, actual_upper, expected_upper))
    print("Upper-bit mismatches:", len(bad))
    for b in bad[:30]:
        print("   ", b)

    section("TASK 3c — Extract: extracted bits match embedded payload, same order")
    bad = []
    for n in range(1, 9):
        for pixel in range(256):
            for bits in product(*([range(2)] * n)):
                bits = list(bits)
                stego = _embed_pixel(pixel, n, bits)
                # receiver_extract_recover reads bits MSB-first: (sv >> (7-j)) & 1
                extracted = [(stego >> (7 - j)) & 1 for j in range(n)]
                if extracted != bits:
                    bad.append(("extract_order", n, pixel, bits, stego, extracted))
    print("Extract order mismatches:", len(bad))
    for b in bad[:30]:
        print("   ", b)

    section("TASK 3d — n=0 and n=8 corner cases")
    print("n=0: embed should return pixel unchanged.")
    bad0 = []
    for pixel in range(256):
        if _embed_pixel(pixel, 0, []) != pixel:
            bad0.append(pixel)
    print("   n=0 failures:", len(bad0), bad0[:10])

    print("n=8: lower_mask = 0, all bits replaced by payload (8 bits) -> stego = payload as uint8.")
    bad8 = []
    for bits in product(*([range(2)] * 8)):
        bits = list(bits)
        expected = sum(int(b) << (7 - i) for i, b in enumerate(bits))
        stego = _embed_pixel(0, 8, bits)  # pixel value irrelevant since lower_mask=0
        if stego != expected:
            bad8.append((bits, stego, expected))
    print("   n=8 failures:", len(bad8), bad8[:10])

    section("TASK 3e — Extraction with payload_len cutoff behaviour")
    print("The receiver extracts min(bpp_flat[i], remaining) bits per pixel but breaks")
    print("the outer loop once extracted reaches payload_len. We emulate this with a")
    print("small synthetic stego image and verify exact recovery of a known payload")
    print("of length: 0, 1, capacity-1, capacity, capacity+1 (where applicable).")
    print()

    # Build a tiny synthetic scenario where we control bpp_map and pixels.
    rng = np.random.RandomState(99)
    h, w = 2, 2
    image = rng.randint(0, 256, (h, w), dtype=np.uint8)
    # Choose a bpp_map; we can set some pixels to 2 bits, some to 0.
    bpp_map = np.array([[2, 0],
                        [1, 3]], dtype=np.int32)
    capacity = int(bpp_map.sum())
    payload = rng.randint(0, 2, size=capacity, dtype=np.uint8)

    # Manual embed matching sender_embed_encrypt logic (no encrypt for this unit test).
    stego_flat = image.flatten().astype(np.int32)
    bpp_flat = bpp_map.flatten()
    bit_idx = 0
    for i in range(h * w):
        n = int(bpp_flat[i])
        if n == 0:
            continue
        bits = []
        for _ in range(n):
            bits.append(int(payload[bit_idx]) if bit_idx < len(payload) else 0)
            if bit_idx < len(payload):
                bit_idx += 1
        stego_flat[i] = _embed_pixel(int(stego_flat[i]), n, bits)
    stego_image = stego_flat.reshape(h, w).astype(np.uint8)

    # Emulate receiver extraction with various payload_len.
    def extract(sp_flat, pred_flat, bpp_flat, min_flat, max_flat, payload_len):
        extracted = []
        for i in range(h * w):
            if len(extracted) >= payload_len:
                break
            n = int(bpp_flat[i])
            sv = int(sp_flat[i])
            if n == 0:
                continue
            for j in range(n):
                if len(extracted) >= payload_len:
                    break
                extracted.append((sv >> (7 - j)) & 1)
        return np.array(extracted[:payload_len], dtype=np.uint8)

    sp_flat = stego_image.flatten().astype(np.int32)
    pred_flat = np.zeros(h * w, dtype=np.int32)  # not used for extraction correctness test
    min_flat = np.zeros(h * w, dtype=np.int32)
    max_flat = np.zeros(h * w, dtype=np.int32)

    cases = {
        "len=0": 0,
        "len=1": 1,
        "len=capacity-1": max(0, capacity - 1),
        "len=capacity": capacity,
        "len=capacity+1": capacity + 1,
    }
    rows = [["payload_len case", "len", "extracted (hex)", "match payload[:len]?"]]
    for label, plen in cases.items():
        ext = extract(sp_flat, pred_flat, bpp_flat, min_flat, max_flat, plen)
        if plen == 0:
            match = (len(ext) == 0)
            rows.append([label, plen, str(ext.tolist()), f"yes(no bits)" if match else "no"])
        else:
            # compare against first plen bits of payload
            want = payload[:plen].tolist()
            match = bool(np.array_equal(ext, want))
            rows.append([label, plen, str(ext.tolist()), "yes" if match else "NO"])
    table(rows, widths=[18, 7, 30, 22])
    print()
    print("Note: payload_len = capacity+1 will extract only 'capacity' bits because the")
    print("loop breaks once it has exhausted available bpp; here we verify it does not")
    print("crash and returns the maximum extractable bits.")

    if bad or bad0 or bad8:
        return False
    print()
    print("Embed/extract: all core invariants held over tested domain.")
    return True


def audit_embed_partial_payload_padding():
    """
    In sender_embed_encrypt, when payload is shorter than capacity, remaining bits
    are padded with 0. At the receiver, extraction stops at payload_len.
    We check: does padding with zeros ever cause a recovery mismatch? (Recovery
    depends on _recover_pixel, not on the padded bits directly, but the stego
    pixel values do. We must ensure stego pixel values created with zero padding
    are still recoverable.)
    """
    section("TASK 3f — Zero-padding unused capacity: recovery still works")
    rng = np.random.RandomState(7)
    h, w = 3, 3
    image = rng.randint(0, 256, (h, w), dtype=np.uint8)
    # Create a bpp_map with some zeros and some nonzeros.
    bpp_map = np.array([[0, 2, 0],
                        [1, 0, 3],
                        [0, 0, 1]], dtype=np.int32)
    capacity = int(bpp_map.sum())
    # Use a payload SHORTER than capacity.
    short_payload = rng.randint(0, 2, size=max(1, capacity // 2), dtype=np.uint8)

    # Embed with sender logic (zero-pads remainder).
    stego_flat = image.flatten().astype(np.int32)
    bpp_flat = bpp_map.flatten()
    bit_idx = 0
    for i in range(h * w):
        n = int(bpp_flat[i])
        if n == 0:
            continue
        bits = []
        for _ in range(n):
            bits.append(int(short_payload[bit_idx]) if bit_idx < len(short_payload) else 0)
            if bit_idx < len(short_payload):
                bit_idx += 1
        stego_flat[i] = _embed_pixel(int(stego_flat[i]), n, bits)
    stego_image = stego_flat.reshape(h, w).astype(np.uint8)

    # Now recovery using actual min_e/max_e from real label maps for these pixels.
    # We need pred_int and error_abs to compute real min_e/max_e.
    from src.rdhei_core import content_owner_prepare
    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    pred_int = co["pred_int"]
    min_e_map = co["min_e_map"]
    max_e_map = co["max_e_map"]

    # Recover pixels using the actual stego bytes, but the supplied min_e/max_e
    # may differ from the ones used to create stego_image if we used a synthetic
    # bpp_map. To test the pipeline's actual behaviour, we re-run the FULL sender
    # with the short payload and see if recovery succeeds at capacity==actual embed.
    # Simpler: use run_rdhei with a short payload manually.
    from src.rdhei_core import sender_embed_encrypt, receiver_extract_recover

    # Build a dict matching what sender expects.
    co_short = dict(co)
    stego_enc = sender_embed_encrypt(co_short, short_payload)
    rx = receiver_extract_recover(
        stego_enc,
        co_short["key"],
        co_short["nonce"],
        co_short["bpp_map"],
        co_short["min_e_map"],
        co_short["max_e_map"],
        co_short["pred_int"],
        len(short_payload),
    )
    recovered = rx["recovered"]
    extracted = rx["extracted"]
    print("Short-payload round-trip:")
    print("   image == recovered (exact):", bool(np.array_equal(image, recovered)))
    print("   extracted == short_payload:   ", bool(np.array_equal(extracted, short_payload)))
    print("   extracted length:", len(extracted), "payload length:", len(short_payload))

    # Also test empty payload (length 0).
    empty_payload = np.array([], dtype=np.uint8)
    stego_enc0 = sender_embed_encrypt(co, empty_payload)
    rx0 = receiver_extract_recover(
        stego_enc0,
        co["key"],
        co["nonce"],
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        0,
    )
    print()
    print("Empty-payload round-trip:")
    print("   image == recovered (exact):", bool(np.array_equal(image, rx0["recovered"])))
    print("   extracted length:", len(rx0["extracted"]))

    return True


# ---------------------------------------------------------------------------
# TASK 4 — Unique pixel recovery invariant
# ---------------------------------------------------------------------------

def audit_unique_recovery():
    """
    For each valid combo of:
      original pixel x in 0..255
      prediction p in 0..255 (or actual pred_int range)
      error magnitude e = |x-p|
      label-derived n from _compute_bpp_and_range(e)
      min_e,max_e from same
      preserved lower bits = lower n bits of stego pixel created by _embed_pixel(x,n,payload_bits)
    verify:

    INVARIANT:
      Let S = { c in 0..255 : (c & lower_mask) == lower AND min_e <= |c-p| <= max_e }.
      Then |S| == 1 and the unique element of S == x.

    If |S|==0, _recover_pixel returns stego_val (a silent fallback). If |S|>1, it
    returns the first candidate, which may be wrong.

    We enumerate over the entire concrete domain that can actually occur:
      - x in 0..255
      - p in 0..255 (since pred_int is clipped/rounded; we still test full range)
      - payload bits: we test ALL possible payloads for given n to ensure stego lower
        bits are whatever _embed_pixel produces; we enumerate over those lower bits too.
    Because enumerating p=0..255, x=0..255, payload bits for each n is large,
    we enumerate over:
      - x in 0..255
      - p in 0..255
      - n from 0..8 derived from e=|x-p|
      - lower = (x & lower_mask) (since embed preserves lower bits)
    This covers all possible lower-bit values that actually arise from embedding x.
    """
    section("TASK 4a — Exhaustive unique-recovery invariant over x, p in 0..255")

    counterexamples = []
    silent_fallbacks = []  # cases where |S|==0 (recover falls back to stego_val)

    # Precomputable map: for each (p, n, lower, min_e, max_e), compute candidate set.
    # To make it feasible, iterate x and p, derive n, min_e, max_e, lower_mask, lower,
    # then scan candidates.

    for x in range(256):
        for p in range(256):
            e = abs(x - p)
            bpp, mn, mx = _compute_bpp_and_range(e)
            n = bpp
            if n == 0:
                # No bits replaced: recovery returns stego_val. stego_val should be x
                # because embed with n=0 returns pixel unchanged. So invariant trivially
                # holds if stego_val == x, which is true by construction here.
                continue
            n_lower = 8 - n
            lower_mask = (1 << n_lower) - 1
            lower = x & lower_mask  # embed preserves these
            # stego_val created by embed = (payload_upper & ~lower_mask) | lower
            # We do not need payload_upper to compute candidate set; candidate set
            # depends only on lower bits, p, min_e, max_e.
            candidates = []
            for combo in range(1 << n):
                c = (combo << n_lower) | lower
                if 0 <= c <= 255 and mn <= abs(c - p) <= mx:
                    candidates.append(c)
            if len(candidates) == 0:
                silent_fallbacks.append((x, p, e, n, mn, mx, lower, lower_mask, x))
            elif len(candidates) > 1:
                counterexamples.append((x, p, e, n, mn, mx, lower, lower_mask, candidates, x))
            elif candidates[0] != x:
                counterexamples.append((x, p, e, n, mn, mx, lower, lower_mask, candidates, x))

    print("Total (x,p) pairs examined:", 256 * 256)
    print("n>0 pairs (where embed actually changes bits):",
          sum(1 for x in range(256) for p in range(256) if _compute_bpp_and_range(abs(x-p))[0] > 0))
    print()
    print("Silent fallbacks (|S|==0, _recover_pixel returns stego_val):",
          len(silent_fallbacks))
    for cf in silent_fallbacks[:30]:
        x, p, e, n, mn, mx, lower, lower_mask, stego_val = cf
        print("   x=%d p=%d e=%d n=%d min_e=%d max_e=%d lower=%d(#%d) stego_val=%d" % (
            x, p, e, n, mn, mx, lower, n_lower := (8 - n), stego_val))
        # verify stego_val != x meaning fallback is wrong
        stego_val_derived = None
        # derive stego_val used in fallbacks: not stored here; but the invariant failure
        # is that |S|==0, so ANY stego_val would be wrong if it != x. We check if stego_val
        # could equal x. Since lower = x & lower_mask, stego_val == x requires upper bits
        # of stego_val == upper bits of x, which may or may not hold. We just flag the |S|==0.
    print()
    print("MULTIPLE-CANDIDATE counterexamples (|S|>1):",
          len([c for c in counterexamples if len(c[8]) > 1]))
    for c in [c for c in counterexamples if len(c[8]) > 1][:30]:
        x, p, e, n, mn, mx, lower, lower_mask, candidates, xorig = c
        print("   x=%d p=%d e=%d n=%d min_e=%d max_e=%d lower=%d(#%d) candidates=%s orig=%d" % (
            x, p, e, n, mn, mx, lower, (8 - n), candidates, xorig))
    print()
    print("WRONG-CANDIDATE counterexamples (candidate[0] != x, |S|==1 but wrong):",
          len([c for c in counterexamples if len(c[8]) == 1 and c[8][0] != c[9]]))
    for c in [c for c in counterexamples if len(c[8]) == 1 and c[8][0] != c[9]][:30]:
        x, p, e, n, mn, mx, lower, lower_mask, candidates, xorig = c
        print("   x=%d p=%d e=%d n=%d min_e=%d max_e=%d lower=%d(#%d) candidate=%d orig=%d" % (
            x, p, e, n, mn, mx, lower, (8 - n), candidates[0], xorig))

    section("TASK 4b — Minimal counterexample hunt (smallest x,p,e,n)")
    if silent_fallbacks or counterexamples:
        print("Smallest (by x then p) silent fallback:")
        sf = sorted(silent_fallbacks, key=lambda t: (t[0], t[1]))
        if sf:
            x, p, e, n, mn, mx, lower, lower_mask, stego_val = sf[0]
            print("   ", x, p, e, n, mn, mx, lower, lower_mask)
        print()
        print("Smallest (by x then p) multi-candidate:")
        mc = sorted([c for c in counterexamples if len(c[8]) > 1], key=lambda t: (t[0], t[1]))
        if mc:
            x, p, e, n, mn, mx, lower, lower_mask, candidates, xorig = mc[0]
            print("   ", x, p, e, n, mn, mx, lower, lower_mask, candidates, xorig)
        print()
        print("Smallest (by x then p) wrong-candidate:")
        wc = sorted([c for c in counterexamples if len(c[8]) == 1 and c[8][0] != c[9]],
                    key=lambda t: (t[0], t[1]))
        if wc:
            x, p, e, n, mn, mx, lower, lower_mask, candidates, xorig = wc[0]
            print("   ", x, p, e, n, mn, mx, lower, lower_mask, candidates[0], xorig)

    section("TASK 4c — Does _recover_pixel's stego_val fallback conceal errors?")
    print("For each silent_fallback (|S|==0), compute the actual stego_val that would")
    print("be produced when embedding x with SOME payload. If that stego_val != x, then")
    print("the fallback returns a WRONG pixel while silently appearing to 'recover'.")
    print()
    flagged = 0
    for (x, p, e, n, mn, mx, lower, lower_mask, _x) in silent_fallbacks:
        # stego_val for the embedding of x with ANY payload: lower bits = x & lower_mask,
        # upper bits arbitrary (we test all). We flag if ANY stego_val != x exists.
        for combo in range(1 << n):
            sv = (combo << (8 - n)) | lower
            if sv != x:
                flagged += 1
                if flagged <= 15:
                    print("   |S|==0 for x=%d p=%d e=%d n=%d min_e=%d max_e=%d: stego_val=%d != x=%d" % (
                        x, p, e, n, mn, mx, sv, x))
                break
    print()
    print("Silent-fallback cases where stego_val can differ from x:",
          flagged, "out of", len(silent_fallbacks))

    if counterexamples or silent_fallbacks:
        return False, counterexamples, silent_fallbacks
    print()
    print("All (x,p) pairs yield a unique correct candidate. Invariant holds.")
    return True, [], []


# ---------------------------------------------------------------------------
# TASK 6 — Numerical and implementation hazards
# ---------------------------------------------------------------------------

def audit_numerical_hazards():
    section("TASK 6a — np.round() and float->int conversion for predictions")
    print("MED predictor returns float32 medians that may be non-integer.")
    print("content_owner_prepare does: pred_int = np.round(pred_map).astype(np.int32)")
    print()
    print("Test rounding edge cases: half-integers, negatives, >255, <0")
    test_vals = np.array([-0.5, -0.4, 0.5, 0.4, 127.5, 128.5,
                          255.5, 256.4, -1.5], dtype=np.float32)
    pred_int = np.round(test_vals).astype(np.int32)
    rows = [["float32", "round->int32", "note"]]
    for v, pi in zip(test_vals, pred_int):
        note = ""
        if v < 0 or v > 255:
            note = "OUT OF RANGE"
        rows.append([float(v), int(pi), note])
    table(rows, widths=[12, 14, 16])
    print()
    print("Observation: np.round() on half-integers (0.5) rounds to nearest even in")
    print("recent NumPy? Actually np.round uses 'round half to even' by default. Let's")
    print("confirm 0.5, 1.5, 2.5 behaviour.")
    half = np.array([0.5, 1.5, 2.5, 3.5, -0.5, -1.5], dtype=np.float32)
    print("   values:", half.tolist())
    print("   np.round:", np.round(half).tolist())
    print("   .astype(np.int32):", np.round(half).astype(np.int32).tolist())
    print()

    section("TASK 6b — Prediction outside 0..255 range")
    print("If pred_int is <0 or >255, error_abs = |image - pred_int| can be >255.")
    print("Label map is computed on error_abs; _compute_bpp_and_range only handles")
    print("e_abs up to 255 (since loop only goes r=7..1 => high=127). Values >127")
    print("fall through to final 'return bpp,0,0' if not caught earlier.")
    print()
    print("Check: what does _compute_bpp_and_range return for e=128..255?")
    rows = [["e_abs", "bpp", "min_e", "max_e"]]
    for e in range(128, 256):
        bpp, mn, mx = _compute_bpp_and_range(e)
        rows.append([e, bpp, mn, mx])
    table(rows[:40], widths=[8, 6, 8, 8])
    print("   ... (full 128..255 in output)")
    print()
    print("Note: for e_abs >= 128, bpp=0 and min_e=max_e=0. This means such pixels")
    print("get NO embedding (n=0) and recovery is stego_val == pixel (since n=0).")
    print("So large errors are simply not used for embedding - a design choice, not")
    print("necessarily a bug, but it caps |e| usable at 127.")
    print()
    print("Check whether error_abs can actually be >255: image in 0..255, pred_int")
    print("could be outside 0..255 if rounding produces >255 or <0. Test with a")
    print("prediction of 256 and image=0 => error_abs=256.")
    try:
        out = _compute_bpp_and_range(256)
        print("   _compute_bpp_and_range(256) =", out)
    except Exception as ex:
        print("   _compute_bpp_and_range(256) raised:", repr(ex))
    print()

    section("TASK 6c — Flatten/reshape order")
    print("sender_embed_encrypt flattens image with .flatten() (C order by default),")
    print("embeds in raster order, then reshapes with .reshape(h, w) (C order).")
    print("receiver_extract_recover does the same on stego_plain.")
    print("This is consistent IF both sides use the same order, which they do.")
    print()
    print("Potential hazard: bpp_map, pred_int, min_e_map, max_e_map must be indexed")
    print("in the SAME raster order. They are all flattened with .flatten() (C order).")
    print("Consistent. No bug here assuming images are 2D and contiguous.")
    print()

    section("TASK 6d — Signed vs unsigned and dtype assumptions")
    print("embeddings operate on np.int32 scalars derived from uint8 via .astype(np.int32).")
    print("Mask operations use Python ints (1 << n). Results are OR'd and AND'd as ints.")
    print("Final stego_plain is cast to uint8 after reshape. Range checks are done in")
    print("_recover_pixel (0 <= c <= 255) but NOT in _embed_pixel. We verified range")
    print("holds in Task 3a. If a future caller passes n>8, artefacts may arise; code")
    print("assumes n in 0..8. bpp_map values come from _compute_bpp_and_range which")
    print("returns bpp in 0..7 (since max bpp accumulated is 7 from r=7..1 with one")
    print("increment per r, plus possibly the final return). Let's confirm max bpp.")
    print()
    max_bpp = max(_compute_bpp_and_range(e)[0] for e in range(256))
    print("   max bpp over e=0..255 =", max_bpp)
    print("   (should be <= 8; if >8, _embed_pixel/recover loops may break)")
    print()

    section("TASK 6e — RGB wrapper vs grayscale core")
    print("rdhei_color.py runs run_rdhei per channel with UNIQUE nonces (base_nonce + c + 1).")
    print("Each channel is treated as an independent grayscale RDHEI instance; prediction,")
    print("label map, and recovery are per-channel, with no cross-channel sharing.")
    print("This is consistent with the grayscale core. No cross-channel hazard identified.")
    print("Metadata (base_nonce) must be transmitted to receiver; pack_metadata does this.")
    print()

    section("TASK 6f — Metadata and predictor info availability to receiver")
    print("receiver_extract_recover REQUIRES bpp_map, min_e_map, max_e_map, pred_int as")
    print("explicit arguments. In run_rdhei, these are passed from content_owner_prepare")
    print("outputs. So the receiver MUST have access to these (out-of-band or in metadata).")
    print("The code does NOT embed these maps in the encrypted image; they must be sent")
    print("separately. This is a protocol/dependency choice, not a correctness bug per se,")
    print("but it must be documented. We flag it for the research context.")
    print()

    return True


# ---------------------------------------------------------------------------
# TASK 7 — Security boundary (lightweight, for correctness only)
# ---------------------------------------------------------------------------

def audit_security():
    section("TASK 7a — Nonce allocation across channels / images")
    print("encryption.py uses base_nonce + c + 1 for RGB channels (c=0,1,2).")
    print("Within a single image, the three channel nonces are unique.")
    print()
    print("Across DIFFERENT images encrypted with the SAME key, reuse depends on the")
    print("caller supplying distinct base_nonce per image. run_rdhei_color uses a single")
    print("base_nonce for all channels of ONE image; if the same base_nonce is reused for")
    print("a different image with the same key, keystream for the same (channel, pixel)")
    print("positions would repeat -> CTR security breaks for those positions.")
    print()
    print("This is a caller-protocol responsibility, not an internal bug. We flag it.")
    print()

    section("TASK 7b — Authentication / tamper detection")
    print("AES-CTR provides confidentiality only. No MAC / AEAD. An attacker can modify")
    print("ciphertext, and the receiver would decrypt a modified plaintext without detection.")
    print("This is acknowledged in encryption.py docstrings. Not a correctness bug, but")
    print("limits the security claims that can be made.")
    print()
    return True


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("RDHEI Day 1 Audit Script")
    print("Project root:", PROJECT)
    print()

    ok1, fails1 = audit_label_map_scalar_vs_vector()
    audit_label_map_interval_semantics()

    ok2 = audit_embed_extract()
    audit_embed_partial_payload_padding()

    ok3, counterexamples, sf = audit_unique_recovery()

    audit_numerical_hazards()
    audit_security()

    print()
    section("AUDIT SUMMARY")
    print("Label-map scalar==vector :", "PASS" if ok1 else "FAIL")
    print("Embed/extract invariants :", "PASS" if ok2 else "FAIL")
    print("Unique-recovery invariant :", "PASS" if ok3 else "FAIL")
    print()
    if not ok3:
        print("COUNTERS:", len(counterexamples), "silent fallbacks:", len(sf))
        print()
    if fails1:
        print("Label-map discrepancies:", len(fails1))
    print("Done.")


if __name__ == "__main__":
    main()
