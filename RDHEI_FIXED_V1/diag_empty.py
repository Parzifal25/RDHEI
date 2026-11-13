#!/usr/bin/env python3
"""Diagnose empty-payload failure: does recovery produce the original image?"""
from __future__ import annotations
import numpy as np, sys
sys.path.insert(0, "/home/parzifal/RDHEI_Project")
from src.rdhei_core import content_owner_prepare, sender_embed_encrypt, receiver_extract_recover

rs = np.random.RandomState(1234)
image = rs.randint(0, 256, (3, 3), dtype=np.uint8)
co = content_owner_prepare(image=image, key=b"k"*16, nonce=0, method="med")
capacity = co["capacity"]
print("image:\n", image)
print("pred_int:\n", co["pred_int"])
print("bpp_map:\n", co["bpp_map"])
print("capacity:", capacity)
print()

# empty payload embedded
payload = np.array([], dtype=np.uint8)
stego_enc = sender_embed_encrypt(co, payload)
rx = receiver_extract_recover(
    stego_enc, co["key"], co["nonce"],
    co["bpp_map"], co["min_e_map"], co["max_e_map"],
    co["pred_int"], 0,
)
print("recovered:\n", rx["recovered"])
print("image == recovered:", bool(np.array_equal(image, rx["recovered"])))
print()
print("per-pixel:")
for y in range(3):
    for x in range(3):
        sv = rx["stego_plain"][y,x]
        rec = rx["recovered"][y,x]
        orig = image[y,x]
        n = int(co["bpp_map"][y,x])
        p = int(co["pred_int"][y,x])
        mn = int(co["min_e_map"][y,x])
        mx = int(co["max_e_map"][y,x])
        ok = "OK" if rec==orig else "FAIL"
        print(f"  ({y},{x}): orig={orig:3d} stego={sv:3d} rec={rec:3d} n={n} pred={p} min_e={mn} max_e={mx} {ok}")
print()

# What does _recover_pixel produce for each pixel?
from src.rdhei_core import _recover_pixel
print("_recover_pixel results:")
for y in range(3):
    for x in range(3):
        sv = int(rx["stego_plain"][y,x])
        n = int(co["bpp_map"][y,x])
        if n==0:
            print(f"  ({y},{x}): n=0 -> stego={sv} (no recovery needed)")
            continue
        p = int(co["pred_int"][y,x])
        mn = int(co["min_e_map"][y,x])
        mx = int(co["max_e_map"][y,x])
        rec = _recover_pixel(sv, p, n, mn, mx)
        orig = int(image[y,x])
        print(f"  ({y},{x}): sv={sv} n={n} pred={p} min_e={mn} max_e={mx} -> rec={rec} orig={orig} {'OK' if rec==orig else 'FAIL'}")
