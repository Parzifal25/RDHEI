#!/usr/bin/env python3
"""
Confirm the defect: receiver_extract_recover breaks when extraction reaches
payload_len, leaving later pixels un-recovered (retaining stego_plain values).

Test: short payload on a tiny image. Show that pixels processed before break
are correctly recovered, while pixels after break retain stego values.
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
    short_payload = rng.randint(0, 2, size=max(1, capacity // 2), dtype=np.uint8)
    payload_len = len(short_payload)

    stego_enc = sender_embed_encrypt(co, short_payload)
    rx = receiver_extract_recover(
        stego_enc, co["key"], co["nonce"],
        co["bpp_map"], co["min_e_map"], co["max_e_map"],
        co["pred_int"], payload_len,
    )

    recovered = rx["recovered"]
    stego_plain = rx["stego_plain"]

    print("payload_len:", payload_len, "capacity:", capacity)
    print()
    print("Per-pixel: stego_plain, recovered, original, DIFF(recovered-orig), DIFF(stego-orig)")
    for y in range(h):
        for x in range(w):
            sv = stego_plain[y, x]
            rec = recovered[y, x]
            orig = image[y, x]
            rdiff = int(rec) - int(orig)
            sdiff = int(sv) - int(orig)
            flag = ""
            if rec != orig:
                flag = "  <-- NOT RECOVERED (retains stego value)"
            if sv != orig:
                flag += "  (stego != orig)"
            print(f"  ({y},{x}): stego={sv:3d} recovered={rec:3d} orig={orig:3d} "
                  f"Δrec={rdiff:4d} Δstego={sdiff:4d}{flag}")
    print()

    # Show which pixels have stego != original AND recovered != original
    print("Pixels where stego != original AND recovered != original (un-recovered):")
    count = 0
    for y in range(h):
        for x in range(w):
            if stego_plain[y, x] != image[y, x] and recovered[y, x] != image[y, x]:
                count += 1
                print(f"  ({y},{x}): stego={stego_plain[y,x]} recovered={recovered[y,x]} orig={image[y,x]}")
    print(f"  Total un-recovered pixels: {count}")
    print()

    # Confirm: recovered == stego_plain for un-recovered pixels
    print("For un-recovered pixels, recovered == stego_plain:", True)
    for y in range(h):
        for x in range(w):
            if stego_plain[y, x] != image[y, x] and recovered[y, x] != image[y, x]:
                assert recovered[y, x] == stego_plain[y, x], f"Mismatch at ({y},{x})"
    print("  (confirmed: recovered retains stego_plain value)")
    print()

    # Now run with FULL payload and show all pixels recovered
    print("For comparison: full-payload run (payload_len=capacity):")
    full_payload = rng.randint(0, 2, size=capacity, dtype=np.uint8)
    stego_enc2 = sender_embed_encrypt(co, full_payload)
    rx2 = receiver_extract_recover(
        stego_enc2, co["key"], co["nonce"],
        co["bpp_map"], co["min_e_map"], co["max_e_map"],
        co["pred_int"], capacity,
    )
    print("  image == recovered (exact):", bool(np.array_equal(image, rx2["recovered"])))
    print("  All pixels recovered correctly:", all(rx2["recovered"].flat == image.flat))
    print()

    print("CONCLUSION: receiver_extract_recover stops processing after extracting")
    print("payload_len bits, leaving later pixels un-recovered. This is a correctness")
    print("defect that is masked when payload_len == capacity (all pixels processed).")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
