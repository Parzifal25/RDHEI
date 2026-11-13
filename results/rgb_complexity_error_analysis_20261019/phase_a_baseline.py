#!/usr/bin/env python3
"""Phase A — recompute the RGB/gray baseline tables from the authoritative
implementation and reconcile them with the existing raw CSVs.

Outputs (under results/rgb_complexity_error_analysis_20261019/):
  baseline_reconciliation.csv    — every recomputed value vs. the stored CSV value
  rgb_per_image_comparison.csv   — fresh per-image RGB table (all predictors)
  rgb_per_channel_comparison.csv — fresh per-channel RGB table (all predictors)
  gray_per_image_comparison.csv  — fresh gray table (all predictors)
  phase_a_log.md                 — reconciliation summary

Predictors: MED (baseline), MED_pipeline, GAP, CALIC, CNN-3x3, plus the four
CNN ablation checkpoints (recomputed too, from the real checkpoints).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ra_common as rac

REF = HERE.parent / "final_validation_20261018"
OUT = HERE

ALL_PRED = rac.CLASSICAL + list(rac.CNN_CHECKPOINTS.keys())

TOL = 1e-4  # agreement tolerance vs stored CSVs (which carry ~9 decimals)


def main() -> int:
    recon = []   # reconciliation rows
    rgb_ch_rows = []
    rgb_img_rows = []
    gray_rows = []

    # ------------------------------------------------------------------
    # Grayscale
    # ------------------------------------------------------------------
    for name in rac.GRAY_IMAGES:
        img = rac.load_gray(name)
        row = {"image": name, "height": img.shape[0], "width": img.shape[1]}
        for m in ALL_PRED:
            pred = rac.predict(img, m)
            ch = rac.channel_metrics(img, pred)
            row[f"{m}_bpp"] = ch["bpp"]
            row[f"{m}_mae"] = ch["mae"]
            row[f"{m}_capacity"] = ch["capacity_bits"]
        gray_rows.append(row)
        print(f"[gray] {name}: done", flush=True)

    # ------------------------------------------------------------------
    # RGB (genuine 3-channel)
    # ------------------------------------------------------------------
    for name in rac.RGB_IMAGES:
        rgb = rac.load_rgb(name)
        h, w, _ = rgb.shape
        img_row = {"image": name, "height": h, "width": w}
        for c, ch_name in enumerate(rac.CHANNELS):
            chan = rgb[:, :, c]
            for m in ALL_PRED:
                pred = rac.predict(chan, m)
                chm = rac.channel_metrics(chan, pred)
                rgb_ch_rows.append({
                    "image": name, "channel": ch_name, "method": m,
                    "mae": chm["mae"], "capacity_bits": chm["capacity_bits"],
                    "bpp": chm["bpp"],
                })
                img_row[f"{m}_{ch_name}_bpp"] = chm["bpp"]
                img_row[f"{m}_{ch_name}_mae"] = chm["mae"]
        for m in ALL_PRED:
            bpps = [img_row[f"{m}_{c}_bpp"] for c in rac.CHANNELS]
            maes = [img_row[f"{m}_{c}_mae"] for c in rac.CHANNELS]
            img_row[f"{m}_bpp"] = float(np.mean(bpps))   # RGB convention: mean over channels
            img_row[f"{m}_mae"] = float(np.mean(maes))
        rgb_img_rows.append(img_row)
        print(f"[rgb] {name}: done", flush=True)

    # ------------------------------------------------------------------
    # Reconcile against the stored fresh CSVs (results/final_validation_20261018)
    # ------------------------------------------------------------------
    # 1) b2_rgb_per_channel.csv: image,method,channel,mae,capacity_bits,bpp
    ref_ch = {}
    with open(REF / "b2_rgb_per_channel.csv") as f:
        for r in csv.DictReader(f):
            ref_ch[(r["image"], r["method"], r["channel"])] = r

    method_alias = {"CNN3x3": "CNN3x3", "MED": "MED", "GAP": "GAP",
                    "CALIC": "CALIC", "MED_pipeline": "MED_pipeline"}
    for r in rgb_ch_rows:
        if r["method"] not in method_alias:
            continue
        key = (r["image"], r["method"], r["channel"])
        if key not in ref_ch:
            recon.append({"source": "b2_rgb_per_channel", "image": r["image"],
                          "method": r["method"], "channel": r["channel"],
                          "metric": "ALL", "stored": "MISSING", "recomputed": "",
                          "abs_diff": "", "match": "MISSING"})
            continue
        ref = ref_ch[key]
        for metric, refkey in (("mae", "mae"), ("capacity_bits", "capacity_bits"), ("bpp", "bpp")):
            stored = float(ref[refkey])
            rec = float(r[metric])
            d = abs(stored - rec)
            recon.append({
                "source": "b2_rgb_per_channel", "image": r["image"],
                "method": r["method"], "channel": r["channel"], "metric": metric,
                "stored": f"{stored:.9f}", "recomputed": f"{rec:.9f}",
                "abs_diff": f"{d:.2e}",
                "match": "YES" if (d <= TOL or d <= 1e-6 * max(1.0, abs(stored))) else "NO",
            })

    # 2) b2_rgb_per_image.csv (bpp columns) and b2_gray_per_image.csv
    def check_per_image(fname, rows, methods, suffix_cols):
        p = REF / fname
        if not p.exists():
            return
        with open(p) as f:
            stored = {r["image"]: r for r in csv.DictReader(f)}
        for row in rows:
            ref = stored.get(row["image"])
            if ref is None:
                continue
            for m in methods:
                for metric, col in suffix_cols:
                    key = f"{m}_{col}"
                    if col not in metric and key not in ref:
                        continue
                    if key not in ref:
                        continue
                    sv = float(ref[key]); rv = float(row[f"{m}_{metric}"])
                    d = abs(sv - rv)
                    recon.append({
                        "source": fname, "image": row["image"], "method": m,
                        "channel": "mean", "metric": metric,
                        "stored": f"{sv:.9f}", "recomputed": f"{rv:.9f}",
                        "abs_diff": f"{d:.2e}",
                        "match": "YES" if (d <= TOL or d <= 1e-6 * max(1.0, abs(sv))) else "NO",
                    })

    b2_methods = ["MED", "GAP", "CALIC", "MED_pipeline", "CNN3x3"]
    check_per_image("b2_rgb_per_image.csv", rgb_img_rows, b2_methods,
                    [("bpp", "bpp"), ("mae", "mae")])
    check_per_image("b2_gray_per_image.csv", gray_rows, b2_methods,
                    [("bpp", "bpp"), ("mae", "mae")])

    # 3) b3_ablation_rgb_per_image.csv: variant,image,bpp,mae,capacity_total (per-image)
    p3 = REF / "b3_ablation_rgb_per_image.csv"
    variant_alias = {"v4_patch3": "CNN3x3", "v1_full": "CNN5x5",
                     "v2_no_residual": "CNNNoResidual",
                     "v3_no_weighted_loss": "CNNNoWeighted",
                     "v5_patch7": "CNN7x7"}
    if p3.exists():
        with open(p3) as f:
            for r in csv.DictReader(f):
                m = variant_alias.get(r["variant"])
                if m is None:
                    continue
                mine = next((x for x in rgb_img_rows if x["image"] == r["image"]), None)
                if mine is None:
                    continue
                for metric, col in (("bpp", "bpp"), ("mae", "mae"),
                                    ("capacity_bits", "capacity_total")):
                    sv = float(r[col])
                    if metric == "capacity_bits":
                        rv = sum(x["capacity_bits"] for x in rgb_ch_rows
                                 if x["image"] == r["image"] and x["method"] == m)
                    else:
                        rv = mine[f"{m}_{metric}"]
                    d = abs(sv - rv)
                    recon.append({
                        "source": "b3_ablation_rgb_per_image", "image": r["image"],
                        "method": r["variant"], "channel": "mean", "metric": metric,
                        "stored": f"{sv:.9f}", "recomputed": f"{rv:.9f}",
                        "abs_diff": f"{d:.2e}",
                        "match": "YES" if (d <= TOL or d <= 1e-6 * max(1.0, abs(sv))) else "NO",
                    })

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    def write_csv(path, rows):
        if not rows:
            return
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write_csv(OUT / "baseline_reconciliation.csv", recon)
    write_csv(OUT / "rgb_per_channel_comparison.csv", rgb_ch_rows)
    write_csv(OUT / "rgb_per_image_comparison.csv", rgb_img_rows)
    write_csv(OUT / "gray_per_image_comparison.csv", gray_rows)

    n = len(recon)
    n_match = sum(1 for r in recon if r["match"] == "YES")
    n_mismatch = sum(1 for r in recon if r["match"] == "NO")
    n_missing = sum(1 for r in recon if r["match"] == "MISSING")
    worst = max((float(r["abs_diff"]) for r in recon if r["match"] in ("YES", "NO")), default=0.0)

    lines = [
        "# Phase A — baseline reconciliation log",
        "",
        f"- Stored reference: `results/final_validation_20261018/` (fresh run of 2026-10-18).",
        f"- Recomputed from: authoritative `src/` implementation + `models/*.pth` checkpoints.",
        f"- Checks: {n} | match: {n_match} | mismatch: {n_mismatch} | missing-in-reference: {n_missing}",
        f"- Largest absolute difference among matched checks: {worst:.3e}",
        "",
        "All RGB aggregates use the project convention: per-image RGB value = arithmetic",
        "mean of the three per-channel values. `images.png` (single-channel) is excluded",
        "from all RGB aggregates, consistent with the reference run.",
        "",
    ]
    if n_mismatch:
        lines.append("## MISMATCHES (must be investigated before use)")
        lines.append("")
        for r in recon:
            if r["match"] == "NO":
                lines.append(f"- {r}")
    else:
        lines.append("No mismatches. The stored reference CSVs are fully reproduced by")
        lines.append("the authoritative implementation and checkpoints on this host.")
    (OUT / "phase_a_log.md").write_text("\n".join(lines) + "\n")
    print(f"\nreconciliation: {n_match}/{n} match, {n_mismatch} mismatch, {n_missing} missing")
    return 0 if n_mismatch == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
