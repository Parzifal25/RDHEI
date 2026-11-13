#!/usr/bin/env python3
"""
Reproduce the short-payload failure where:
  - extracted == short_payload (bit-accurate)  PASS
  - image == recovered (exact)                 FAIL

We print the stego_plain, recovered, original, and the pixel deltas to
identify WHICH pixels fail and whether it is a recovery failure or an
embed/encrypt/decrypt mismatch.
"""
from __future__ import annotations

import numpy as np
import sys

PROJECT = "/home/parzifal/RDHEI_Project"
sys.path.insert(0, PROJECT)

from src.rdhei_core import (
    content_owner_prepare,
    sender_embed_encrypt,
    receiver_extract_recover,
)


def main():
    rng = np.random.RandomState(7)
    h, w = 3, 3
    image = rng.randint(0, 256, (h, w), dtype=np.uint8)

    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    capacity = co["capacity"]
    print("image:\n", image)
    print("pred_int:\n", co["pred_int"])
    print("bpp_map:\n", co["bpp_map"])
    print("capacity:", capacity)
    print()

    # Short payload: half capacity
    short_payload = rng.randint(0, 2, size=max(1, capacity // 2), dtype=np.uint8)
    print("short_payload len:", len(short_payload), "capacity:", capacity)
    print()

    stego_enc = sender_embed_encrypt(co, short_payload)
    rx = receiver_extract_recover(
        stego_enc,
        co["key"],
        co["nonce"],
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        len(short_payload),
    )

    recovered = rx["recovered"]
    extracted = rx["extracted"]
    stego_plain = rx["stego_plain"]

    print("stego_plain (decrypted, before recovery):\n", stego_plain)
    print("recovered:\n", recovered)
    print("original:\n", image)
    print()
    print("image == recovered (exact):", bool(np.array_equal(image, recovered)))
    print("extracted == short_payload:  ", bool(np.array_equal(extracted, short_payload)))
    print()

    delta = (recovered.astype(np.int32) - image.astype(np.int32))
    print("pixel deltas (recovered - original):")
    print(delta)
    print()
    print("nonzero delta positions:", list(zip(*np.where(delta != 0))))
    print()

    # Show stego_plain vs original too
    delta_stego = (stego_plain.astype(np.int32) - image.astype(np.int32))
    print("stego_plain - original deltas:")
    print(delta_stego)
    print()
    print("nonzero stego_plain deltas:", list(zip(*np.where(delta_stego != 0))))
    print()

    # Compare stego_plain vs the stego we would embed with FULL payload
    full_stego_enc = sender_embed_encrypt(co, co["payload"] if "payload" in co else
                                          rng.randint(0, 2, size=capacity, dtype=np.uint8))
    rx_full = receiver_extract_recover(
        full_stego_enc,
        co["key"],
        co["nonce"],
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        capacity,
    )
    print("For reference, full-payload run (capacity bits embedded):")
    print("  image == recovered (exact):", bool(np.array_equal(image, rx_full["recovered"])))
    print("  extracted == full_payload:  ", bool(np.array_equal(rx_full["extracted"],
                                                               rx_full["payload"] if "payload" in rx_full else
                                                               rng.randint(0, 2, size=capacity, dtype=np.uint8))))
    print()

    # Diagnose: if stego_plain already differs from original at non-embeddable pixels,
    # then the problem is encrypt/decrypt or embed. If stego_plain == original but
    # recovered differs, it's _recover_pixel failing on some pixels.
    if np.array_equal(stego_plain, image):
        print(" stego_plain == original  => recovery is the failing stage.")
    else:
        print(" stego_plain != original => embed/encrypt/decrypt is the failing stage.")
        # Which pixels differ?
        diff_idx = np.where(delta_stego != 0)
        for y, x in zip(*diff_idx):
            print(f"   ({y},{x}): orig={image[y,x]} stego_plain={stego_plain[y,x]} "
                  f"bpp={co['bpp_map'][y,x]} min_e={co['min_e_map'][y,x]} "
                  f"max_e={co['max_e_map'][y,x]} pred={co['pred_int'][y,x]}")
    print()

    # Diagnose per-pixel recovery failure on the stego_plain that differs
    sp_flat = stego_plain.flatten().astype(np.int32)
    pred_flat = co["pred_int"].flatten().astype(np.int32)
    bpp_flat = co["bpp_map"].flatten().astype(np.int32)
    min_flat = co["min_e_map"].flatten().astype(np.int32)
    max_flat = co["max_e_map"].flatten().astype(np.int32)

    print("Per-pixel recovery attempt (using stego_plain values) vs original:")
    for i in range(h * w):
        n = int(bpp_flat[i])
        sv = int(sp_flat[i])
        p = int(pred_flat[i])
        mn = int(min_flat[i])
        mx = int(max_flat[i])
        x_orig = int(image.flat[i])
        rec = _recover_pixel(sv, p, n, mn, mx)
        if rec != x_orig:
            print(f"  idx={i} n={n} sv={sv} pred={p} min_e={mn} max_e={mx} "
                  f"orig={x_orig} recovered={rec} match={rec==x_orig}")
    print()

    # Now do the same but using the FULL-PIPELINE's own recovered output
    print("Per-pixel in recovered (from rx) vs original:")
    for y in range(h):
        for x in range(w):
            if recovered[y, x] != image[y, x]:
                print(f"  ({y},{x}): orig={image[y,x]} recovered={recovered[y,x]} "
                      f"bpp={co['bpp_map'][y,x]} min_e={co['min_e_map'][y,x]} "
                      f"max_e={co['max_e_map'][y,x]} pred={co['pred_int'][y,x]} "
                      f"sv(plain)={stego_plain[y,x]}")

    print()
    print("Done.")


def _recover_pixel(stego_val, pred, n, min_e, max_e):
    if n == 0:
        return stego_val
    n_lower = 8 - n
    lower_mask = (1 << n_lower) - 1
    lower = stego_val & lower_mask
    for combo in range(1 << n):
        c = (combo << n_lower) | lower
        if 0 <= c <= 255 and min_e <= abs(c - pred) <= max_e:
            return c
    return stego_val


if __name__ == "__main__":
    main()
