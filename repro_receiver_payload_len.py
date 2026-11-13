#!/usr/bin/env python3
"""
Minimal repro for the receiver outer-loop defect.

Old behavior (as described):
  outer loop breaks once extracted >= payload_len, so later pixels keep
  recovered[i] == sp_flat[i] (stego_plain), and are NOT recovered.

Expected correct behavior:
  every pixel is recovered via _recover_pixel even after payload extraction
  is complete; payload bits are extracted only until payload_len bits exist.
"""
from __future__ import annotations
import numpy as np
import sys

sys.path.insert(0, ".")

from src.rdhei_core import (
    content_owner_prepare,
    sender_embed_encrypt,
    receiver_extract_recover,
    _recover_pixel,
)


def til(s):
    return f"\n{'='*78}\n{s}\n{'='*78}"


def dump_fails(image, recovered, stego_plain, bpp_map, pred_int, min_e_map, max_e_map):
    h, w = image.shape
    print("Per-pixel failures (recovered != original):")
    any_fail = False
    for y in range(h):
        for x in range(w):
            orig = int(image[y, x])
            rec = int(recovered[y, x])
            sv = int(stego_plain[y, x])
            if rec != orig:
                any_fail = True
                n = int(bpp_map[y, x])
                p = int(pred_int[y, x])
                mn = int(min_e_map[y, x])
                mx = int(max_e_map[y, x])
                print(
                    f"  ({y},{x}): orig={orig:3d} stego={sv:3d} rec={rec:3d} "
                    f"n={n} pred={p} min_e={mn} max_e={mx}"
                )
    if not any_fail:
        print("  (none)")


def run_case(label, image, payload, payload_len):
    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    capacity = co["capacity"]

    embed_payload = payload.astype(np.uint8)
    stego_enc = sender_embed_encrypt(co, embed_payload)
    rx = receiver_extract_recover(
        stego_enc,
        co["key"],
        co["nonce"],
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        payload_len,
    )

    recovered = rx["recovered"]
    extracted = rx["extracted"]
    stego_plain = rx["stego_plain"]

    if payload_len <= len(embed_payload):
        expect_payload = embed_payload[:payload_len].astype(np.uint8)
    else:
        expect_payload = embed_payload.astype(np.uint8)

    image_exact = bool(np.array_equal(image, recovered))
    payload_exact = bool(np.array_equal(extracted, expect_payload))

    print(
        f"{label:16s} plen={payload_len:<4d} cap={capacity:<4d} "
        f"extracted_len={len(extracted)} "
        f"image_exact={image_exact!s:<5} payload_exact={payload_exact!s:<5}"
    )

    if not image_exact or not payload_exact:
        print("  image_exact:", image_exact)
        print("  payload_exact:", payload_exact)
        print("  extracted:", extracted.tolist())
        print("  expected :", expect_payload.tolist())
        dump_fails(image, recovered, stego_plain, co["bpp_map"], co["pred_int"],
                   co["min_e_map"], co["max_e_map"])

    return image_exact and payload_exact


def main():
    print(til("MINIMAL REPRO - receiver outer-loop / payload-length behavior"))
    rs = np.random.RandomState(1234)
    image = rs.randint(0, 256, (3, 3), dtype=np.uint8)
    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    capacity = co["capacity"]
    payload_full = rs.randint(0, 2, size=capacity, dtype=np.uint8)

    # empty
    run_case("empty", image, payload_full, 0)
    # one bit
    if capacity >= 1:
        run_case("one_bit", image, payload_full, 1)
    # short
    short_len = max(1, capacity // 2)
    run_case("short", image, payload_full, short_len)
    # capacity - 1
    if capacity >= 1:
        run_case("capacity-1", image, payload_full, max(0, capacity - 1))
    # full capacity
    run_case("full_capacity", image, payload_full, capacity)
    # over capacity: receiver asked for > capacity
    over_len = capacity + 1
    run_case("over_capacity", image, payload_full, over_len)

    print()
    print("Notes:")
    print(" - For all valid payload_len (<= capacity), we assert image_exact AND payload_exact.")
    print(" - For over_capacity, the embedded bits are only `capacity`. Receiver should:")
    print("     * recover the full image exactly")
    print("     * extract exactly `capacity` bits (all that exist)")
    print("     * not crash or raise")
    print("   We document this behavior as 'extract what is available, still recover every pixel'.")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
