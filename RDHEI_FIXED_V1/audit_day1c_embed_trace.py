#!/usr/bin/env python3
"""
Trace sender_embed_encrypt for the short-payload case where stego_plain != original.

Key observation from audit_day1b:
  - pixels with bpp=7, min_e=0, max_e=0 (perfect prediction) are corrupted
  - these are the |e|=0 pixels
  - under short payload, capacity=38, payload_len=19
  - extraction is bit-accurate for the 19 bits
  - but stego_plain already differs from original at those pixels

This script replays the embed loop and prints what each pixel received, and
whether bytes written to stego buffer match what decrypt_image returns.
"""
from __future__ import annotations

import numpy as np
import sys

PROJECT = "/home/parzifal/RDHEI_Project"
sys.path.insert(0, PROJECT)

from src.rdhei_core import (
    content_owner_prepare,
    _embed_pixel,
)
from src.encryption import encrypt_image, decrypt_image


def main():
    rng = np.random.RandomState(7)
    h, w = 3, 3
    image = rng.randint(0, 256, (h, w), dtype=np.uint8)

    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    capacity = co["capacity"]
    bpp_map = co["bpp_map"]
    bpp_flat = bpp_map.flatten()

    short_payload = rng.randint(0, 2, size=max(1, capacity // 2), dtype=np.uint8)
    payload_len = len(short_payload)

    print("capacity:", capacity, "payload_len:", payload_len)
    print("bpp_flat:", bpp_flat.tolist())
    print("short_payload bits:", short_payload.tolist())
    print()

    # Replay sender_embed_encrypt logic but with full visibility
    stego = image.flatten().astype(np.int32).copy()
    bit_idx = 0
    print("Replaying embed loop:")
    print("idx  orig  bpp  payload_bits_used  bit_idx_after  stego_before->after")
    for i in range(h * w):
        n = int(bpp_flat[i])
        orig_val = int(image.flat[i])
        if n == 0:
            print(f"{i:3d}  {orig_val:3d}  {n:2d}  (none)            {bit_idx:3d}       {orig_val} -> {stego[i]}")
            continue
        bits = []
        for _ in range(n):
            val = int(short_payload[bit_idx]) if bit_idx < len(short_payload) else 0
            bits.append(val)
            if bit_idx < len(short_payload):
                bit_idx += 1
        stego_before = int(stego[i])
        stego[i] = _embed_pixel(stego_before, n, bits)
        print(f"{i:3d}  {orig_val:3d}  {n:2d}  {bits}  {bit_idx:3d}       {stego_before} -> {stego[i]}")
    print()

    stego_plain_sent = stego.reshape(h, w).astype(np.uint8)
    print("stego_plain (pre-encrypt):\n", stego_plain_sent)
    print()

    # Now encrypt/decrypt and compare bytes
    stego_enc = encrypt_image(stego_plain_sent, co["key"], co["nonce"])
    stego_plain_received = decrypt_image(stego_enc, co["key"], co["nonce"])
    print("After encrypt/decrypt:")
    print("stego_plain_received:\n", stego_plain_received)
    print()
    print("stego_plain_sent == stego_plain_received:",
          bool(np.array_equal(stego_plain_sent, stego_plain_received)))
    print()

    delta = (stego_plain_received.astype(np.int32) - image.astype(np.int32))
    print("delta (received stego - original):")
    print(delta)
    print()

    # Check: is the corruption present BEFORE encrypt/decrypt?
    stego_plain_sent_delta = (stego_plain_sent.astype(np.int32) - image.astype(np.int32))
    print("delta (sent stego - original):")
    print(stego_plain_sent_delta)
    print()

    if np.array_equal(stego_plain_sent, image):
        print(" stego_plain_sent == original  => embed wrote wrong values.")
    elif np.array_equal(stego_plain_received, stego_plain_sent):
        print(" stego_plain_received == stego_plain_sent  => encrypt/decrypt OK, embed wrote wrong values.")
    else:
        print(" stego_plain_received != stego_plain_sent  => encrypt/decrypt introduced corruption.")
        diff_idx = np.where(stego_plain_received.flatten() != stego_plain_sent.flatten())
        for idx in zip(*diff_idx):
            print(f"   byte idx {idx}: sent={stego_plain_sent.flat[idx]} recv={stego_plain_received.flat[idx]}")
    print()

    # For each corrupted pixel, show what the embed loop put vs original
    print("Corrupted pixel details (received stego != original):")
    for y in range(h):
        for x in range(w):
            if stego_plain_received[y, x] != image[y, x]:
                i = y * w + x
                n = int(bpp_flat[i])
                bits_used = []
                # recompute bits that WOULD have been used in the embed loop
                # (replay)
                bit_idx2 = 0
                for j in range(i + 1):
                    nj = int(bpp_flat[j])
                    if j < i:
                        bit_idx2 += nj if bit_idx2 < payload_len else 0
                    else:
                        pass
                # simpler: just recompute using same logic
                bit_idx3 = 0
                for j in range(i):
                    njj = int(bpp_flat[j])
                    if bit_idx3 < payload_len:
                        bit_idx3 += njj
                n_here = n
                bits_here = []
                for _ in range(n_here):
                    val = int(short_payload[bit_idx3]) if bit_idx3 < payload_len else 0
                    bits_here.append(val)
                    if bit_idx3 < payload_len:
                        bit_idx3 += 1
                print(f"  ({y},{x}) orig={image[y,x]} bpp={n_here} bits_used={bits_here} "
                      f"sent_stego={stego_plain_sent[y,x]} recv_stego={stego_plain_received[y,x]}")
    print()

    # Show what the receiver extracted from these pixels
    # (replay extraction)
    print("Receiver extraction replay (showing bits extracted per pixel):")
    sp_flat = stego_plain_received.flatten().astype(np.int32)
    extracted = []
    bit_idx4 = 0
    for i in range(h * w):
        n = int(bpp_flat[i])
        sv = int(sp_flat[i])
        if n == 0:
            continue
        for j in range(n):
            if len(extracted) >= payload_len:
                break
            b = (sv >> (7 - j)) & 1
            extracted.append(b)
            if len(extracted) < payload_len:
                bit_idx4 += 1
        print(f"  idx={i} sv={sv} n={n} extracted_bits={extracted[-n:] if n else []}")
    print()
    print("Extracted total:", extracted)
    print("Expected (short_payload):", short_payload.tolist())
    print("Match:", extracted == short_payload.tolist())
    print()

    # Diagnose: under short payload, the FIRST 19 bits are correct, the rest are zero-padded.
    # The embed loop pads with 0 for indices beyond payload_len. That means stego_plain_sent has
    # zeros in the upper bits of pixels beyond the payload boundary.
    # But the corruption is in pixels WITHIN the first 19 bits too. Let's identify the exact
    # payload boundary index.
    print("Identifying the payload boundary (where bit_idx reaches payload_len):")
    bit_idx5 = 0
    for i in range(h * w):
        n = int(bpp_flat[i])
        if n == 0:
            continue
        before = bit_idx5
        after = bit_idx5 + n
        if after >= payload_len:
            print(f"  pixel idx={i} bpp={n} bit_idx before={before} after={after} "
                  f"(payload_len={payload_len})  <-- boundary")
            print(f"     original pixel = {image.flat[i]}")
            print(f"     bits for this pixel: payload bits {short_payload[before:min(after,payload_len)].tolist()} "
                  f"+ padding { [0]*(after-payload_len) if after>payload_len else [] }")
            break
        bit_idx5 = after
    print()

    # Now check: are the corrupted pixels BEFORE or AFTER this boundary?
    print("Corrupted pixel indices vs boundary:")
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if stego_plain_received[y, x] != image[y, x]:
                n = int(bpp_flat[i])
                # find bit_idx at start of this pixel
                bit_idx_here = 0
                for j in range(i):
                    bit_idx_here += int(bpp_flat[j])
                print(f"  ({y},{x}) idx={i} bpp={n} bit_idx_at_start={bit_idx_here} "
                      f"within_payload={bit_idx_here < payload_len}")
    print()

    print("Done.")


if __name__ == "__main__":
    main()
