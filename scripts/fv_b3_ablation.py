#!/usr/bin/env python3
"""Phase B3 — CNN ablation evaluation, fresh measurement.

For each of the 5 available checkpoints:
  v1_full (5x5, residual), v2_no_residual (5x5, no residual),
  v3_no_weighted_loss (5x5, residual; plain-L1 training label),
  v4_patch3 (3x3, residual — PROPOSED), v5_patch7 (7x7, residual)

measured on:
  - 6 grayscale benchmark images
  - 5 genuine 3-channel RGB benchmark images (per channel; per-image value =
    mean over R,G,B)

Metrics: parameter count (from loaded model), prediction MAE
(mean |image - round(pred)|), capacity (generate_label_map_fast sum), BPP.

No retraining. Checkpoints are loaded read-only from models/.

Outputs under results/final_validation_20261018/:
  b3_ablation_gray.csv, b3_ablation_rgb.csv, b3_ablation_params.csv
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from PIL import Image

from src.rdhei_core import generate_label_map_fast, cnn_predict
from src.cnn_model import load_model

GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"
MODELS = HERE / "models"
OUT = HERE / "results" / "final_validation_20261018"
OUT.mkdir(parents=True, exist_ok=True)

VARIANTS = [
    ("v4_patch3", "v4_patch3.pth", 3, True),
    ("v1_full", "v1_full.pth", 5, True),
    ("v2_no_residual", "v2_no_residual.pth", 5, False),
    ("v3_no_weighted_loss", "v3_no_weighted_loss.pth", 5, True),
    ("v5_patch7", "v5_patch7.pth", 7, True),
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


def metrics_for(img: np.ndarray, pred: np.ndarray):
    e = np.abs(img.astype(np.int32) - np.round(pred).astype(np.int32))
    mae = float(e.mean())
    bpp_map, _, _ = generate_label_map_fast(e)
    cap = int(bpp_map.sum())
    return mae, cap, cap / img.size


def main() -> int:
    t0 = time.time()
    gray_images = list(load_gray(GRAY_DIR))
    rgb_images = list(load_rgb_genuine(COLOR_DIR))
    print(f"gray={len(gray_images)} rgb_genuine={len(rgb_images)}")

    gray_rows, rgb_rows, param_rows = [], [], []

    for tag, fname, exp_patch, exp_res in VARIANTS:
        model, patch, residual, n_params = load_model(str(MODELS / fname), device="cpu")
        assert patch == exp_patch and residual == exp_res, f"{tag}: arch mismatch"
        param_rows.append({
            "variant": tag, "checkpoint": fname, "patch": patch,
            "residual": residual, "params": n_params,
            "expected_params": {"v4_patch3": 46881, "v1_full": 112417, "v2_no_residual": 112353,
                                "v3_no_weighted_loss": 112417, "v5_patch7": 210721}[tag],
        })
        print(f"\n== {tag} patch={patch} residual={residual} params={n_params:,} ==")

        for name, img in gray_images:
            mae, cap, bpp = metrics_for(img, cnn_predict(img, model, device="cpu", patch_size=patch))
            gray_rows.append({"variant": tag, "image": name, "mae": round(mae, 6),
                              "capacity_bits": cap, "bpp": round(bpp, 9)})
            print(f"  gray {name:14s} BPP={bpp:.4f} MAE={mae:.4f}", flush=True)

        for name, img in rgb_images:
            ch_res = {}
            for ci, ch in enumerate("RGB"):
                mae, cap, bpp = metrics_for(
                    img[:, :, ci], cnn_predict(img[:, :, ci], model, device="cpu", patch_size=patch))
                ch_res[ch] = (mae, cap, bpp)
                rgb_rows.append({"variant": tag, "image": name, "channel": ch,
                                 "mae": round(mae, 6), "capacity_bits": cap, "bpp": round(bpp, 9)})
            print(f"  rgb {name:14s} BPP={np.mean([ch_res[c][2] for c in 'RGB']):.4f} "
                  f"MAE={np.mean([ch_res[c][0] for c in 'RGB']):.4f}", flush=True)

    def write(path, rows):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    write(OUT / "b3_ablation_gray.csv", gray_rows)
    write(OUT / "b3_ablation_rgb.csv", rgb_rows)
    write(OUT / "b3_ablation_params.csv", param_rows)

    # per-image aggregation for RGB (mean over channels), saved for convenience
    rgb_img_rows = []
    for tag, *_ in VARIANTS:
        for name, img in rgb_images:
            sel = [r for r in rgb_rows if r["variant"] == tag and r["image"] == name]
            rgb_img_rows.append({
                "variant": tag, "image": name,
                "bpp": round(float(np.mean([r["bpp"] for r in sel])), 9),
                "mae": round(float(np.mean([r["mae"] for r in sel])), 6),
                "capacity_total": int(sum(r["capacity_bits"] for r in sel)),
            })
    write(OUT / "b3_ablation_rgb_per_image.csv", rgb_img_rows)

    print(f"\nDone in {time.time()-t0:.1f}s. Outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
