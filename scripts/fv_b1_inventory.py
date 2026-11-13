#!/usr/bin/env python3
"""Phase B1 — benchmark dataset validation / inventory.

Inspects EVERY image file in the project's intended benchmark directories and
records: filename, path, sha256, PIL mode, decoded dtype, shape, channel count,
value range (bit depth), whether it qualifies as a genuine 3-channel RGB
benchmark image, and whether it is included in the final RGB aggregate.

Outputs under results/final_validation_20261018/:
  - dataset_inventory.csv
  - dataset_inventory.md
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

DATA = HERE.parent / "data"
GRAY_DIR = DATA / "kodak_gray"
COLOR_DIR = DATA / "kodak_color"
TRAIN_DIR = DATA / "train"

OUT = HERE / "results" / "final_validation_20261018"
OUT.mkdir(parents=True, exist_ok=True)

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pgm"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(path: Path, expect_rgb: bool) -> dict:
    with Image.open(path) as im:
        mode = im.mode
        size = im.size  # (w, h)
        info_bit_depth = im.info.get("bit_depth")
        arr = np.array(im)
    shape = arr.shape
    channels = 1 if arr.ndim == 2 else shape[2]
    vmin = int(arr.min())
    vmax = int(arr.max())

    # Genuine RGB check: decode as RGB explicitly and require that the file's
    # own decoded pixels differ between channels (a grayscale file converted
    # to RGB has identical channels).
    with Image.open(path) as im2:
        as_rgb = np.array(im2.convert("RGB"))
    interchannel_max_diff = int(
        max(
            np.abs(as_rgb[:, :, 0].astype(np.int16) - as_rgb[:, :, 1].astype(np.int16)).max(),
            np.abs(as_rgb[:, :, 0].astype(np.int16) - as_rgb[:, :, 2].astype(np.int16)).max(),
            np.abs(as_rgb[:, :, 1].astype(np.int16) - as_rgb[:, :, 2].astype(np.int16)).max(),
        )
    )
    is_genuine_rgb = bool(mode == "RGB" and channels == 3 and interchannel_max_diff > 0)

    return {
        "file": path.name,
        "dir": str(path.parent),
        "sha256": sha256_of(path),
        "file_bytes": path.stat().st_size,
        "pil_mode": mode,
        "width": size[0],
        "height": size[1],
        "decoded_shape": str(shape),
        "channels": channels,
        "dtype": str(arr.dtype),
        "value_min": vmin,
        "value_max": vmax,
        "assumed_bit_depth": info_bit_depth if info_bit_depth else (8 if vmax <= 255 else 16),
        "interchannel_max_diff": interchannel_max_diff,
        "qualifies_genuine_rgb": is_genuine_rgb,
        "expect_rgb": expect_rgb,
        "included_in_rgb_aggregate": is_genuine_rgb if expect_rgb else "n/a (gray set)",
        "included_in_gray_aggregate": (channels == 1) if not expect_rgb else "n/a (rgb set)",
        "exclusion_reason": (
            ""
            if (is_genuine_rgb if expect_rgb else channels == 1)
            else ("file decodes as single-channel grayscale" if expect_rgb
                  else "not a single-channel image")
        ),
    }


def main() -> int:
    rows = []
    for d, expect_rgb in ((GRAY_DIR, False), (COLOR_DIR, True)):
        if not d.exists():
            print(f"MISSING DIR: {d}")
            return 2
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in IMG_EXT and not p.name.endswith(":Zone.Identifier"):
                rows.append(inspect(p, expect_rgb))

    fieldnames = list(rows[0].keys())
    csv_path = OUT / "dataset_inventory.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Markdown table
    md = ["# Phase B1 — Benchmark dataset inventory", ""]
    md.append(f"- Gray dir: `{GRAY_DIR}`")
    md.append(f"- RGB dir: `{COLOR_DIR}`")
    md.append(f"- Train dir: `{TRAIN_DIR}` (count only, see below)")
    md.append("")
    md.append("| File | Set | Mode | WxH | Channels | Range | Inter-ch max diff | Genuine RGB | In RGB agg | SHA256 (first 16) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        setname = "RGB" if r["expect_rgb"] else "GRAY"
        md.append(
            f"| {r['file']} | {setname} | {r['pil_mode']} | {r['width']}x{r['height']} | "
            f"{r['channels']} | {r['value_min']}..{r['value_max']} | {r['interchannel_max_diff']} | "
            f"{r['qualifies_genuine_rgb']} | {r['included_in_rgb_aggregate']} | `{r['sha256'][:16]}` |"
        )
    n_gray = sum(1 for r in rows if not r["expect_rgb"])
    n_rgb_ok = sum(1 for r in rows if r["expect_rgb"] and r["qualifies_genuine_rgb"])
    n_rgb_bad = sum(1 for r in rows if r["expect_rgb"] and not r["qualifies_genuine_rgb"])
    md += ["", f"- Valid grayscale benchmark images: **{n_gray}**",
           f"- Genuine 3-channel RGB benchmark images: **{n_rgb_ok}**",
           f"- RGB-directory files excluded (not genuine RGB): **{n_rgb_bad}**"]
    if TRAIN_DIR.exists():
        pgms = sorted(TRAIN_DIR.glob("*.pgm"))
        md.append(f"- Training directory `{TRAIN_DIR}`: **{len(pgms)}** .pgm files present on disk")
    md.append("")
    md.append("Training-set note: the confirmed training description (BOSSBase, 10,000 training")
    md.append("images, 20 epochs, trained on another computer) is user-confirmed experimental")
    md.append("information; the local folder does not independently verify it.")
    (OUT / "dataset_inventory.md").write_text("\n".join(md) + "\n")

    print(f"Wrote {csv_path}")
    print(f"gray valid={n_gray}  rgb genuine={n_rgb_ok}  rgb excluded={n_rgb_bad}")
    if TRAIN_DIR.exists():
        print(f"train .pgm count={len(list(TRAIN_DIR.glob('*.pgm')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
