#!/usr/bin/env python3
"""Phase D — full-capacity end-to-end sweep across all 5 CNN variants.

For every checkpoint (v4_patch3, v1_full, v2_no_residual, v3_no_weighted_loss,
v5_patch7) and every benchmark image (6 grayscale, 5 genuine RGB), runs the
COMPLETE pipeline with a payload of exactly the measured capacity:

  content_owner_prepare -> sender_embed_encrypt (AES-CTR) ->
  receiver_extract_recover

and checks independently:
  image_exact   = recovered == original (pixel-exact)
  payload_exact = extracted == embedded payload (bit-exact) and
                  len(extracted) == capacity

RGB uses per-channel unique nonces (base_nonce + c + 1).

Outputs under results/final_validation_20261018/:
  d_variants_gray.csv, d_variants_rgb.csv
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from src.rdhei_core import content_owner_prepare, sender_embed_encrypt, receiver_extract_recover
from src.encryption import generate_key, get_channel_nonce
from src.cnn_model import load_model

GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"
MODELS = HERE / "models"
OUT = HERE / "results" / "final_validation_20261018"
OUT.mkdir(parents=True, exist_ok=True)

VARIANTS = [
    ("v4_patch3", "v4_patch3.pth"),
    ("v1_full", "v1_full.pth"),
    ("v2_no_residual", "v2_no_residual.pth"),
    ("v3_no_weighted_loss", "v3_no_weighted_loss.pth"),
    ("v5_patch7", "v5_patch7.pth"),
]

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pgm"}


def load_gray(d: Path):
    for p in sorted(d.iterdir()):
        if p.suffix.lower() in IMG_EXT and not p.name.endswith(":Zone.Identifier"):
            yield p.name, np.array(Image.open(p).convert("L"), dtype=np.uint8)


def load_rgb_genuine(d: Path):
    for p in sorted(d.iterdir()):
        if p.suffix.lower() not in IMG_EXT or p.name.endswith(":Zone.Identifier"):
            continue
        with Image.open(p) as im:
            mode = im.mode
            arr = np.array(im)
        if mode != "RGB" or arr.ndim != 3 or arr.shape[2] != 3:
            continue
        if (np.abs(arr[:, :, 0].astype(np.int16) - arr[:, :, 1].astype(np.int16)).max() == 0
                and np.abs(arr[:, :, 0].astype(np.int16) - arr[:, :, 2].astype(np.int16)).max() == 0):
            continue
        yield p.name, arr


def main() -> int:
    gray_images = list(load_gray(GRAY_DIR))
    rgb_images = list(load_rgb_genuine(COLOR_DIR))
    print(f"gray={len(gray_images)} rgb_genuine={len(rgb_images)}", flush=True)
    gray_rows, rgb_rows = [], []

    for tag, fname in VARIANTS:
        model, patch, residual, n_params = load_model(str(MODELS / fname), device="cpu")
        print(f"\n== {tag} patch={patch} residual={residual} params={n_params:,} ==", flush=True)
        for name, img in gray_images:
            t0 = time.time()
            key = generate_key(32)
            co = content_owner_prepare(image=img, key=key, nonce=0, method="cnn",
                                       model=model, patch_size=patch)
            cap = co["capacity"]
            payload = np.random.RandomState(42).randint(0, 2, size=cap, dtype=np.uint8)
            stego_enc = sender_embed_encrypt(co, payload)
            rx = receiver_extract_recover(stego_enc, key, 0, co["bpp_map"], co["min_e_map"],
                                          co["max_e_map"], co["pred_int"], cap)
            img_ok = bool(np.array_equal(img, rx["recovered"]))
            pay_ok = bool(np.array_equal(rx["extracted"], payload)) and len(rx["extracted"]) == cap
            row = {"variant": tag, "image": name, "method": "cnn", "capacity_bits": cap,
                   "bpp": round(cap / img.size, 9), "image_exact": img_ok, "payload_exact": pay_ok,
                   "status": "PASS" if (img_ok and pay_ok) else "FAIL",
                   "t_total_s": round(time.time() - t0, 3)}
            gray_rows.append(row)
            print(f"  gray {name:14s} bpp={row['bpp']:.4f} {row['status']} ({row['t_total_s']}s)",
                  flush=True)

        for name, img in rgb_images:
            t0 = time.time()
            key = generate_key(32)
            rec = np.zeros_like(img)
            total_cap = total_ext = 0
            ok = True
            for ci, ch in enumerate("RGB"):
                nonce = get_channel_nonce(0, ci)
                ch_img = img[:, :, ci]
                co = content_owner_prepare(image=ch_img, key=key, nonce=nonce, method="cnn",
                                           model=model, patch_size=patch)
                cap = co["capacity"]
                payload = np.random.RandomState(42 + ci).randint(0, 2, size=cap, dtype=np.uint8)
                stego_enc = sender_embed_encrypt(co, payload)
                rx = receiver_extract_recover(stego_enc, key, nonce, co["bpp_map"],
                                              co["min_e_map"], co["max_e_map"],
                                              co["pred_int"], cap)
                rec[:, :, ci] = rx["recovered"]
                total_cap += cap
                total_ext += len(rx["extracted"])
                ok &= (bool(np.array_equal(ch_img, rx["recovered"]))
                       and bool(np.array_equal(rx["extracted"], payload))
                       and len(rx["extracted"]) == cap)
            row = {"variant": tag, "image": name, "method": "cnn", "capacity_total": total_cap,
                   "bpp_per_channel_avg": round(total_cap / (3 * img.shape[0] * img.shape[1]), 9),
                   "image_exact": bool(np.array_equal(img, rec)), "payload_exact": ok,
                   "status": "PASS" if ok else "FAIL", "t_total_s": round(time.time() - t0, 3)}
            rgb_rows.append(row)
            print(f"  rgb  {name:14s} bpp={row['bpp_per_channel_avg']:.4f} {row['status']} "
                  f"({row['t_total_s']}s)", flush=True)

    def write(path, rows):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    write(OUT / "d_variants_gray.csv", gray_rows)
    write(OUT / "d_variants_rgb.csv", rgb_rows)
    gp = sum(1 for r in gray_rows if r["status"] == "PASS")
    rp = sum(1 for r in rgb_rows if r["status"] == "PASS")
    print(f"\nGray {gp}/{len(gray_rows)} PASS, RGB {rp}/{len(rgb_rows)} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
