#!/usr/bin/env python3
"""Phase B1 + Phase E — prediction-error statistics, label-map analysis, histograms.

For every genuine-RGB image/channel and every predictor (MED, MED_pipeline,
GAP, CALIC, CNN-3x3, plus the 4 CNN ablations for the per-variant figures),
computes from the ACTUAL authoritative predictions:

  error statistics:
    mean signed error, MAE, median abs error, std, p75/p90/p95/p99 of |e|,
    max |e|, fraction |e|==0, fraction |e|>=128
  label map (implemented generate_label_map_fast):
    counts of each n in 0..7, fraction n==0, mean BPP from label map,
    bits contributed by each n, error mass at exact power-of-two boundaries

Sign convention check: signed error = image - round(pred), matching
content_owner_prepare() in src/rdhei_core.py.

Outputs:
  prediction_error_statistics.csv   — one row per image/channel/method
  histogram_bins.csv                — signed + absolute error histogram bins/counts
  label_histograms.csv              — n=0..7 pixel counts per image/channel/method
  underperformance_diagnosis.csv    — every channel where CNN3x3 is not best in BPP
  figures/fig_err_*.png             — histograms, per-channel RGB, ECDFs, label counts
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ra_common as rac

OUT = HERE
FIG = HERE / "figures"

MAIN_PRED = ["MED", "GAP", "CALIC", "CNN3x3"]
ALL_PRED = rac.CLASSICAL + list(rac.CNN_CHECKPOINTS.keys())


def error_stats(signed: np.ndarray, e_abs: np.ndarray, bpp_map: np.ndarray) -> dict:
    h, w = signed.shape
    n_px = h * w
    absf = e_abs.flatten().astype(np.float64)
    counts = np.bincount(bpp_map.flatten(), minlength=8)
    cap = int(bpp_map.sum())
    # error mass at label-map boundaries (0,1,2,4,8,16,32,64,128) and 63/65
    boundary_vals = [0, 1, 2, 3, 4, 8, 16, 32, 63, 64, 65, 127, 128]
    bm = {f"pct_e{v}": float((absf == v).mean() * 100.0) for v in boundary_vals}
    return {
        "mean_signed_error": float(signed.mean()),
        "mae": float(absf.mean()),
        "median_ae": float(np.median(absf)),
        "std_signed": float(signed.std()),
        "max_ae": float(absf.max()),
        "p75_ae": float(np.percentile(absf, 75)),
        "p90_ae": float(np.percentile(absf, 90)),
        "p95_ae": float(np.percentile(absf, 95)),
        "p99_ae": float(np.percentile(absf, 99)),
        "frac_zero_error": float((absf == 0).mean()),
        "frac_ae_ge_128": float((absf >= 128).mean()),
        "bpp_from_labelmap": cap / n_px,
        "capacity_bits": cap,
        **{f"n{n}_count": int(counts[n]) for n in range(8)},
        **{f"n{n}_frac": float(counts[n] / n_px) for n in range(8)},
        "frac_n0": float(counts[0] / n_px),
        **bm,
    }


def main() -> int:
    FIG.mkdir(exist_ok=True)
    stats_rows = []
    label_rows = []
    hist_rows = []

    # bin definitions (shared across all predictors for direct comparison)
    signed_edges = np.arange(-256, 258, 1)      # width 1, covers [-256, 257)
    abs_edges = np.arange(-0.5, 256.0, 1)       # 257 edges -> 256 bins, |e| = 0..255

    datasets = []  # (label, arr, method)

    # --- grayscale (used for ECDF + per-image panels) ---
    for name in rac.GRAY_IMAGES:
        img = rac.load_gray(name)
        for m in MAIN_PRED:
            datasets.append((("gray", name, "Y"), img, m))

    # --- genuine RGB, per channel ---
    for name in rac.RGB_IMAGES:
        rgb = rac.load_rgb(name)
        for c, ch in enumerate(rac.CHANNELS):
            chan = rgb[:, :, c]
            for m in ALL_PRED:
                datasets.append(((name, name, ch), chan, m))

    for (setname, imgname, ch), arr, m in datasets:
        pred = rac.predict(arr, m)
        signed, e_abs, pred_int = rac.error_maps(arr, pred)

        # --- verify sign convention matches the implementation ---
        assert np.array_equal(pred_int, np.round(pred).astype(np.int32))

        bpp_map, _, _ = rac.label_maps(e_abs)
        st = error_stats(signed, e_abs, bpp_map)
        stats_rows.append({
            "set": setname, "image": imgname, "channel": ch, "method": m,
            "height": arr.shape[0], "width": arr.shape[1], **st,
        })
        label_rows.append({
            "set": setname, "image": imgname, "channel": ch, "method": m,
            **{f"n{n}_count": st[f"n{n}_count"] for n in range(8)},
        })

        sh, _ = np.histogram(signed.flatten(), bins=signed_edges)
        ah, _ = np.histogram(e_abs.flatten(), bins=abs_edges)
        for i in range(len(sh)):
            hist_rows.append({"set": setname, "image": imgname, "channel": ch,
                              "method": m, "kind": "signed", "bin_left": int(signed_edges[i]),
                              "bin_right": int(signed_edges[i + 1]), "count": int(sh[i])})
        for i in range(len(ah)):
            hist_rows.append({"set": setname, "image": imgname, "channel": ch,
                              "method": m, "kind": "abs", "bin_left": float(abs_edges[i]),
                              "bin_right": float(abs_edges[i + 1]), "count": int(ah[i])})
        print(f"[stats] {imgname} {ch} {m}: mae={st['mae']:.4f} bpp={st['bpp_from_labelmap']:.4f}",
              flush=True)

    # ------------------------------------------------------------------
    # Underperformance diagnosis: every image/channel where CNN3x3 is not
    # the best BPP among {MED, GAP, CALIC, CNN3x3}.
    # ------------------------------------------------------------------
    diag_rows = []
    idx = {(r["image"], r["channel"], r["method"]): r for r in stats_rows if r["set"] != "gray"}
    for name in rac.RGB_IMAGES:
        for ch in rac.CHANNELS:
            cnn = idx[(name, ch, "CNN3x3")]
            best_base = max(("MED", "GAP", "CALIC"),
                            key=lambda b: idx[(name, ch, b)]["bpp_from_labelmap"])
            bb = idx[(name, ch, best_base)]
            if cnn["bpp_from_labelmap"] >= bb["bpp_from_labelmap"]:
                continue
            diag_rows.append({
                "image": name, "channel": ch,
                "cnn_bpp": f"{cnn['bpp_from_labelmap']:.6f}",
                "best_baseline": best_base,
                "baseline_bpp": f"{bb['bpp_from_labelmap']:.6f}",
                "bpp_gap": f"{cnn['bpp_from_labelmap'] - bb['bpp_from_labelmap']:.6f}",
                "cnn_mae": f"{cnn['mae']:.4f}", "baseline_mae": f"{bb['mae']:.4f}",
                "cnn_median_ae": f"{cnn['median_ae']:.2f}",
                "baseline_median_ae": f"{bb['median_ae']:.2f}",
                "cnn_p90": f"{cnn['p90_ae']:.1f}", "baseline_p90": f"{bb['p90_ae']:.1f}",
                "cnn_p99": f"{cnn['p99_ae']:.1f}", "baseline_p99": f"{bb['p99_ae']:.1f}",
                "cnn_max_ae": f"{cnn['max_ae']:.0f}", "baseline_max_ae": f"{bb['max_ae']:.0f}",
                "cnn_frac_n0": f"{cnn['frac_n0']:.5f}", "baseline_frac_n0": f"{bb['frac_n0']:.5f}",
                "cnn_frac_ae_ge_128": f"{cnn['frac_ae_ge_128']:.5f}",
                "baseline_frac_ae_ge_128": f"{bb['frac_ae_ge_128']:.5f}",
                "cnn_pct_e64": f"{cnn['pct_e64']:.4f}", "baseline_pct_e64": f"{bb['pct_e64']:.4f}",
            })

    # ------------------------------------------------------------------
    # Figures
    # ------------------------------------------------------------------
    def write_csv(path, rows):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write_csv(OUT / "prediction_error_statistics.csv", stats_rows)
    write_csv(OUT / "histogram_bins.csv", hist_rows)
    write_csv(OUT / "label_histograms.csv", label_rows)
    write_csv(OUT / "underperformance_diagnosis.csv", diag_rows)

    # Fig 1: signed error histograms, pooled over the 5 genuine RGB images,
    # separated per channel (never pooled across channels silently).
    pooled = {m: {ch: np.zeros(513, dtype=np.int64) for ch in rac.CHANNELS} for m in MAIN_PRED}
    for name in rac.RGB_IMAGES:
        rgb = rac.load_rgb(name)
        for c, ch in enumerate(rac.CHANNELS):
            chan = rgb[:, :, c]
            for m in MAIN_PRED:
                pred = rac.predict(chan, m)
                signed, e_abs, _ = rac.error_maps(chan, pred)
                sh, _ = np.histogram(signed.flatten(), bins=signed_edges)
                pooled[m][ch] += sh
    centers = np.arange(-256, 257)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for i, ch in enumerate(rac.CHANNELS):
        ax = axes[i]
        for m in MAIN_PRED:
            y = pooled[m][ch]
            # log scale shows tail behaviour; clip at 0.5 for log validity
            ax.plot(centers, np.clip(y, 0.5, None), label=m, lw=1.0)
        ax.set_yscale("log")
        ax.set_xlim(-128, 128)
        ax.set_xlabel("signed prediction error  e = I - round(pred)  [gray levels]")
        ax.set_title(f"channel {ch} — pooled over 5 genuine RGB images")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("pixel count (log)")
    axes[0].legend()
    fig.suptitle("Signed prediction-error histograms (fixed bins, width 1; per channel)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_err_signed_rgb_pooled.png", dpi=140)
    plt.close(fig)

    # Fig 2: absolute error ECDF per channel, pooled.
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for i, ch in enumerate(rac.CHANNELS):
        ax = axes[i]
        for m in MAIN_PRED:
            y = pooled[m][ch]
            cdf = np.cumsum(y) / max(y.sum(), 1)
            ax.plot(np.arange(0, 257), cdf[:257], label=m, lw=1.2)
        ax.set_xlabel("|e|  [gray levels]")
        ax.set_title(f"channel {ch}")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("cumulative fraction of pixels")
    axes[0].legend()
    fig.suptitle("Absolute prediction-error ECDF (pooled over 5 genuine RGB images, per channel)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_err_ecdf_rgb_pooled.png", dpi=140)
    plt.close(fig)

    # Fig 3: per-image per-channel comparison for 4.2.07 (CNN loses in BPP)
    # and 4.2.05 (CNN wins clearly).
    for imgname in ("4.2.07.png", "4.2.05.png"):
        rgb = rac.load_rgb(imgname)
        fig, axes = plt.subplots(2, 3, figsize=(15, 7.5))
        for c, ch in enumerate(rac.CHANNELS):
            chan = rgb[:, :, c]
            ax_s = axes[0, c]
            ax_a = axes[1, c]
            for m in MAIN_PRED:
                pred = rac.predict(chan, m)
                signed, e_abs, _ = rac.error_maps(chan, pred)
                sh, _ = np.histogram(signed.flatten(), bins=signed_edges)
                ah, _ = np.histogram(e_abs.flatten(), bins=abs_edges)
                ax_s.plot(centers, np.clip(sh, 0.5, None), label=m, lw=1.0)
                ax_a.plot(np.arange(256), np.clip(ah, 0.5, None), label=m, lw=1.0)
            ax_s.set_yscale("log"); ax_s.set_xlim(-128, 128)
            ax_a.set_yscale("log"); ax_a.set_xlim(-1, 130)
            ax_s.set_title(f"{imgname} ch {ch}: signed error")
            ax_a.set_title(f"{imgname} ch {ch}: absolute error (bins at label boundaries)")
            ax_a.set_xlabel("|e|")
            for ax in (ax_s, ax_a):
                ax.grid(alpha=0.3)
        axes[0, 0].legend()
        axes[1, 0].legend()
        fig.suptitle(f"Per-channel prediction-error histograms — {imgname}")
        fig.tight_layout()
        fig.savefig(FIG / f"fig_err_perimage_{imgname.replace('.', '_')}.png", dpi=140)
        plt.close(fig)

    # Fig 4: label-count distributions (n=0..7) per channel for 4.2.07 + pooled RGB.
    pooled_n = {m: np.zeros(8, dtype=np.int64) for m in MAIN_PRED}
    for name in rac.RGB_IMAGES:
        rgb = rac.load_rgb(name)
        for c in range(3):
            for m in MAIN_PRED:
                pred = rac.predict(rgb[:, :, c], m)
                _, e_abs, _ = rac.error_maps(rgb[:, :, c], pred)
                bpp_map, _, _ = rac.label_maps(e_abs)
                pooled_n[m] += np.bincount(bpp_map.flatten(), minlength=8)
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.2
    xs = np.arange(8)
    for i, m in enumerate(MAIN_PRED):
        ax.bar(xs + (i - 1.5) * width, pooled_n[m] / pooled_n[m].sum() * 100,
               width=width, label=m)
    ax.set_xticks(xs)
    ax.set_xlabel("label n = number of replaceable MSBs assigned by generate_label_map_fast")
    ax.set_ylabel("% of pixels (pooled over 15 channels)")
    ax.set_title("Embedding-label distribution per predictor (pooled genuine RGB)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "fig_label_counts_pooled_rgb.png", dpi=140)
    plt.close(fig)

    # Fig 5: absolute error histograms pooled over RGB channels (single figure,
    # clearly labelled as pooled) + gray Lena panel for the four predictors.
    pooled_a = {m: np.zeros(256, dtype=np.int64) for m in MAIN_PRED}
    for name in rac.RGB_IMAGES:
        rgb = rac.load_rgb(name)
        for c in range(3):
            for m in MAIN_PRED:
                pred = rac.predict(rgb[:, :, c], m)
                _, e_abs, _ = rac.error_maps(rgb[:, :, c], pred)
                ah, _ = np.histogram(e_abs.flatten(), bins=abs_edges)
                pooled_a[m] += ah
    fig, ax = plt.subplots(figsize=(9, 5))
    for m in MAIN_PRED:
        ax.plot(np.arange(256), np.clip(pooled_a[m], 0.5, None), label=m, lw=1.1)
    ax.set_yscale("log")
    ax.set_xlim(-1, 130)
    ax.set_xlabel("|e| [gray levels]")
    ax.set_ylabel("pixel count (log)")
    ax.set_title("Absolute prediction-error histograms — pooled over all 15 genuine-RGB channels")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig_err_abs_rgb_pooled.png", dpi=140)
    plt.close(fig)

    # Fig 6: CNN ablation comparison — signed error + label counts on 4.2.07 R.
    chan = rac.load_rgb("4.2.07.png")[:, :, 0]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for m in rac.CNN_CHECKPOINTS:
        pred = rac.predict(chan, m)
        signed, e_abs, _ = rac.error_maps(chan, pred)
        sh, _ = np.histogram(signed.flatten(), bins=signed_edges)
        axes[0].plot(centers, np.clip(sh, 0.5, None), label=m, lw=1.0)
        bpp_map, _, _ = rac.label_maps(e_abs)
        cnt = np.bincount(bpp_map.flatten(), minlength=8) / bpp_map.size * 100
        axes[1].plot(np.arange(8), cnt, marker="o", label=m, lw=1.0)
    axes[0].set_yscale("log"); axes[0].set_xlim(-128, 128)
    axes[0].set_title("4.2.07 R: signed error, CNN ablations")
    axes[0].set_xlabel("e [gray levels]")
    axes[1].set_title("4.2.07 R: label distribution, CNN ablations")
    axes[1].set_xlabel("n (replaceable MSBs)")
    axes[1].set_ylabel("% of pixels")
    for ax in axes:
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig_err_ablation_4207_R.png", dpi=140)
    plt.close(fig)

    print(f"\nwrote {len(stats_rows)} stat rows, {len(hist_rows)} histogram rows, "
          f"{len(diag_rows)} underperformance rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
