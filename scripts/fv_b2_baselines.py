#!/usr/bin/env python3
"""Phase B2 — proposed CNN-3x3 vs traditional predictors, fresh measurement.

Predictors (all from the authoritative implementation):
  MED        src.baselines.med_predict   (causal MED used by the historical
                                          baseline comparison script)
  GAP        src.baselines.gap_predict
  CALIC      src.baselines.calic_predict
  CNN-3x3    src.rdhei_core.cnn_predict  with models/v4_patch3.pth
  MED-pipe   src.rdhei_core.med_predict  (edge-padded MED actually used by the
                                          full embedding pipeline run_rdhei())

Metrics per image:
  - prediction MAE  = mean |image - round(prediction)|        [bits / pixel-level]
  - capacity        = generate_label_map_fast(|e|).sum()      [bits]
  - BPP             = capacity / (H*W)                        [bits/pixel]

RGB images: per-channel values are kept; the per-image RGB value is the
arithmetic mean of the three channel values (identical to
total_capacity/(H*W*3) because all channels share H*W).
Only the 5 genuine 3-channel RGB images enter the RGB aggregate;
images.png (single-channel) is excluded and listed separately.

Outputs under results/final_validation_20261018/:
  b2_gray_per_image.csv, b2_gray_aggregate.csv,
  b2_rgb_per_image.csv,  b2_rgb_per_channel.csv, b2_rgb_aggregate.csv
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

from src.baselines import med_predict as med_baseline
from src.baselines import gap_predict, calic_predict
from src.rdhei_core import med_predict as med_pipeline, generate_label_map_fast, cnn_predict
from src.cnn_model import load_model

GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"
MODEL_PATH = HERE / "models" / "v4_patch3.pth"
OUT = HERE / "results" / "final_validation_20261018"
OUT.mkdir(parents=True, exist_ok=True)

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
            print(f"  [exclude] {p.name}: mode={mode} shape={arr.shape} — not genuine RGB")
            continue
        # verify channels actually differ (not a converted grayscale file)
        if (np.abs(arr[:, :, 0].astype(np.int16) - arr[:, :, 1].astype(np.int16)).max() == 0
                and np.abs(arr[:, :, 0].astype(np.int16) - arr[:, :, 2].astype(np.int16)).max() == 0):
            print(f"  [exclude] {p.name}: channels identical — not genuine RGB")
            continue
        yield p.name, arr


def pred_metrics(img: np.ndarray, pred: np.ndarray) -> tuple[float, int, float]:
    e = np.abs(img.astype(np.int32) - np.round(pred).astype(np.int32))
    mae = float(e.mean())
    bpp_map, _, _ = generate_label_map_fast(e)
    cap = int(bpp_map.sum())
    return mae, cap, cap / img.size


def main() -> int:
    t0 = time.time()
    model, patch, residual, n_params = load_model(str(MODEL_PATH), device="cpu")
    print(f"Model v4_patch3: patch={patch} residual={residual} params={n_params:,}")

    # ---------------- grayscale ----------------
    gray_rows = []
    print("\n== Grayscale ==")
    for name, img in load_gray(GRAY_DIR):
        row = {"image": name, "height": img.shape[0], "width": img.shape[1]}
        t = time.time()
        for tag, fn in (("MED", med_baseline), ("GAP", gap_predict), ("CALIC", calic_predict),
                        ("MED_pipeline", med_pipeline)):
            mae, cap, bpp = pred_metrics(img, fn(img))
            row[f"{tag}_mae"] = round(mae, 6)
            row[f"{tag}_capacity_bits"] = cap
            row[f"{tag}_bpp"] = round(bpp, 9)
        mae, cap, bpp = pred_metrics(img, cnn_predict(img, model, device="cpu", patch_size=patch))
        row["CNN3x3_mae"] = round(mae, 6)
        row["CNN3x3_capacity_bits"] = cap
        row["CNN3x3_bpp"] = round(bpp, 9)
        gray_rows.append(row)
        print(f"  {name:16s} MED_bpp={row['MED_bpp']:.4f} CNN_bpp={row['CNN3x3_bpp']:.4f} "
              f"CNN_mae={row['CNN3x3_mae']:.4f} ({time.time()-t:.1f}s)")

    with open(OUT / "b2_gray_per_image.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gray_rows[0].keys()))
        w.writeheader(); w.writerows(gray_rows)

    methods = ["MED", "GAP", "CALIC", "MED_pipeline", "CNN3x3"]
    agg = {"n_images": len(gray_rows)}
    for m in methods:
        agg[f"{m}_bpp_mean"] = round(float(np.mean([r[f"{m}_bpp"] for r in gray_rows])), 9)
        agg[f"{m}_bpp_std"] = round(float(np.std([r[f"{m}_bpp"] for r in gray_rows], ddof=1)), 9)
        agg[f"{m}_mae_mean"] = round(float(np.mean([r[f"{m}_mae"] for r in gray_rows])), 6)
        agg[f"{m}_capacity_total"] = int(sum(r[f"{m}_capacity_bits"] for r in gray_rows))
    with open(OUT / "b2_gray_aggregate.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg.keys()))
        w.writeheader(); w.writerows([agg])

    # ---------------- RGB (genuine only) ----------------
    rgb_per_img, rgb_per_ch = [], []
    print("\n== RGB (genuine 3-channel only) ==")
    for name, img in load_rgb_genuine(COLOR_DIR):
        row = {"image": name, "height": img.shape[0], "width": img.shape[1]}
        for m in methods:
            row[f"{m}_bpp"] = None
        for m in methods:
            chans = {}
            for ci, ch_name in enumerate(["R", "G", "B"]):
                if m == "CNN3x3":
                    pred = cnn_predict(img[:, :, ci], model, device="cpu", patch_size=patch)
                elif m == "MED":
                    pred = med_baseline(img[:, :, ci])
                elif m == "MED_pipeline":
                    pred = med_pipeline(img[:, :, ci])
                elif m == "GAP":
                    pred = gap_predict(img[:, :, ci])
                else:
                    pred = calic_predict(img[:, :, ci])
                mae, cap, bpp = pred_metrics(img[:, :, ci], pred)
                chans[ch_name] = (mae, cap, bpp)
                rgb_per_ch.append({
                    "image": name, "method": m, "channel": ch_name,
                    "mae": round(mae, 6), "capacity_bits": cap, "bpp": round(bpp, 9),
                })
            row[f"{m}_bpp"] = round(float(np.mean([chans[c][2] for c in "RGB"])), 9)
            row[f"{m}_mae"] = round(float(np.mean([chans[c][0] for c in "RGB"])), 6)
            row[f"{m}_capacity_total"] = int(sum(chans[c][1] for c in "RGB"))
            for c in "RGB":
                row[f"{m}_{c}_bpp"] = round(chans[c][2], 9)
        rgb_per_img.append(row)
        print(f"  {name:16s} MED_bpp={row['MED_bpp']:.4f} CNN_bpp={row['CNN3x3_bpp']:.4f} "
              f"CNN_mae={row['CNN3x3_mae']:.4f}")

    with open(OUT / "b2_rgb_per_image.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rgb_per_img[0].keys()))
        w.writeheader(); w.writerows(rgb_per_img)
    with open(OUT / "b2_rgb_per_channel.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rgb_per_ch[0].keys()))
        w.writeheader(); w.writerows(rgb_per_ch)

    agg_r = {"n_images": len(rgb_per_img), "aggregation": "mean over images of (mean over R,G,B)"}
    for m in methods:
        agg_r[f"{m}_bpp_mean"] = round(float(np.mean([r[f"{m}_bpp"] for r in rgb_per_img])), 9)
        agg_r[f"{m}_bpp_std"] = round(float(np.std([r[f"{m}_bpp"] for r in rgb_per_img], ddof=1)), 9)
        agg_r[f"{m}_mae_mean"] = round(float(np.mean([r[f"{m}_mae"] for r in rgb_per_img])), 6)
        agg_r[f"{m}_capacity_total"] = int(sum(r[f"{m}_capacity_total"] for r in rgb_per_img))
    with open(OUT / "b2_rgb_aggregate.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg_r.keys()))
        w.writeheader(); w.writerows([agg_r])

    print(f"\nDone in {time.time()-t0:.1f}s. Outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
