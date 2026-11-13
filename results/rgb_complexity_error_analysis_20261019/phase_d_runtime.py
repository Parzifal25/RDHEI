#!/usr/bin/env python3
"""Phase D — runtime benchmarking (predictor-only, stage-wise, end-to-end).

D1 Predictor-only (same protocol as the validated fv_e_runtime.py):
   image Lena.png 512x512 grayscale, CPU, warm-up 5, 10 timed repeats,
   time.perf_counter(); mean/std/min/max/median. Model loading is done
   BEFORE timing (steady-state inference only).
   Methods: MED, GAP, CALIC, 5 CNN checkpoints, plus the vectorized
   CNN-3x3 inference (option-3 variant) under the identical protocol.

D2 Stage-wise (Airplane gray + 4.2.03 RGB, full-capacity payload, 3 repeats):
   prediction | label-map | embed | encrypt | decrypt | extract+recover | total.
   Timing boundaries are disjoint: embed = sender embed loop only (no AES),
   encrypt/decrypt = AES-CTR only, extract+recover = receiver loop only.
   CNN stage timings also recorded with the vectorized predictor (labeled).

D3 Outputs:
   runtime_raw.csv     — every timed sample (machine readable)
   runtime_summary.csv — aggregated statistics
   figures/fig_runtime_predictor.png, fig_runtime_stages.png
"""
from __future__ import annotations

import csv
import platform
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ra_common as rac
import fast_impl as fi

from src.baselines import med_predict, gap_predict, calic_predict
from src.rdhei_core import (content_owner_prepare, sender_embed_encrypt,
                            receiver_extract_recover, cnn_predict,
                            generate_label_map_fast)
from src.encryption import encrypt_image, decrypt_image, generate_key

OUT = HERE
FIG = HERE / "figures"
WARMUP, REPEATS = 5, 10


def bench_stats(samples_ms):
    a = np.array(samples_ms)
    return {"mean_ms": a.mean(), "std_ms": a.std(ddof=1), "min_ms": a.min(),
            "max_ms": a.max(), "median_ms": np.median(a), "n": len(a)}


def main() -> int:
    raw_rows = []
    sum_rows = []

    def timed(name, group, fn, warmup=WARMUP, repeats=REPEATS):
        for _ in range(warmup):
            fn()
        s = []
        for _ in range(repeats):
            t = time.perf_counter()
            fn()
            s.append((time.perf_counter() - t) * 1000.0)
        st = bench_stats(s)
        for i, v in enumerate(s):
            raw_rows.append({"group": group, "method": name, "sample": i, "ms": v})
        sum_rows.append({"group": group, "method": name,
                         **{k: (round(v, 4) if isinstance(v, float) else v)
                            for k, v in st.items()}})
        print(f"  [{group}] {name:34s} mean={st['mean_ms']:9.3f} ms", flush=True)
        return st

    # ------------------------------------------------------------------
    # D1 — predictor-only, Lena 512x512, identical protocol for all methods
    # ------------------------------------------------------------------
    lena = rac.load_gray("Lena.png")
    print("D1 predictor-only benchmark (Lena 512x512, warmup 5, repeats 10)")
    timed("MED", "predictor_only", lambda: med_predict(lena))
    timed("GAP", "predictor_only", lambda: gap_predict(lena))
    timed("CALIC", "predictor_only", lambda: calic_predict(lena))
    for variant, (fname, _) in rac.CNN_CHECKPOINTS.items():
        model, patch, _, _ = rac.get_model(variant)
        timed(f"{variant} ({fname})", "predictor_only",
              lambda: cnn_predict(lena, model, device="cpu", patch_size=patch))
    model3, patch3, _, _ = rac.get_model("CNN3x3")
    timed("CNN-3x3 vectorized (option 3)", "predictor_only",
          lambda: fi.fast_cnn_predict_map(lena, model3, device="cpu", patch_size=patch3))

    # ------------------------------------------------------------------
    # D2 — stage-wise, Airplane gray + 4.2.03 RGB, full capacity, 3 repeats
    # ------------------------------------------------------------------
    print("D2 stage-wise benchmark")
    for imgname in ("Airplane.png", "4.2.03.png"):
        if imgname.startswith("4"):
            img = rac.load_rgb(imgname)
            chans = [img[:, :, c] for c in range(3)]
        else:
            chans = [rac.load_gray(imgname)]

        for method in ("MED", "CNN3x3"):
            preds = []
            for ch in chans:
                if method == "CNN3x3":
                    preds.append(cnn_predict(ch, model3, device="cpu", patch_size=patch3))
                else:
                    preds.append(med_predict(ch).astype(np.float32))
            pred_ints = [np.round(p).astype(np.int32) for p in preds]
            e_abs = [np.abs(ch.astype(np.int32) - pi) for ch, pi in zip(chans, pred_ints)]
            labs = [generate_label_map_fast(e) for e in e_abs]
            caps = [int(l[0].sum()) for l in labs]
            payload = [np.random.RandomState(3).randint(0, 2, size=c, dtype=np.uint8)
                       for c in caps]
            keys = [generate_key(32) for _ in chans]

            label = f"{imgname} {method}"

            timed(f"label_map {label}", "stage",
                  lambda: [generate_label_map_fast(e) for e in e_abs],
                  warmup=1, repeats=3)

            stego_plain = [fi.embed_msb_vectorized(ch, l[0], p)
                           for ch, l, p in zip(chans, labs, payload)]
            timed(f"embed {label}", "stage",
                  lambda: [fi.embed_msb_vectorized(ch, l[0], p)
                           for ch, l, p in zip(chans, labs, payload)],
                  warmup=1, repeats=3)

            enc = [encrypt_image(sp, k, 7) for sp, k in zip(stego_plain, keys)]
            timed(f"encrypt {label}", "stage",
                  lambda: [encrypt_image(sp, k, 7) for sp, k in zip(stego_plain, keys)],
                  warmup=1, repeats=3)

            timed(f"decrypt {label}", "stage",
                  lambda: [decrypt_image(e, k, 7) for e, k in zip(enc, keys)],
                  warmup=1, repeats=3)

            dec = [decrypt_image(e, k, 7) for e, k in zip(enc, keys)]
            timed(f"extract+recover {label}", "stage",
                  lambda: [receiver_extract_recover(
                      en, k, 7, l[0], l[1], l[2], pi, c)
                      for en, k, l, pi, c in zip(enc, keys, labs, pred_ints, caps)],
                  warmup=1, repeats=3)

            # total pipeline (original code path end to end)
            def total_once():
                out = []
                for ch, k in zip(chans, keys):
                    co = content_owner_prepare(ch, k, nonce=7,
                                               method=method if method != "CNN3x3" else "cnn",
                                               model=model3 if method == "CNN3x3" else None)
                    se = sender_embed_encrypt(co, payload[0][:co["capacity"]])
                    rx = receiver_extract_recover(se, k, 7, co["bpp_map"], co["min_e_map"],
                                                  co["max_e_map"], co["pred_int"],
                                                  co["capacity"])
                    out.append(rx)
                return out
            timed(f"TOTAL(original) {label}", "stage", total_once, warmup=1, repeats=3)

            # total with option-3 fast prediction + fast embed/recover
            def total_fast():
                out = []
                for ci, (ch, k, l, p) in enumerate(zip(chans, keys, labs, payload)):
                    pred_f = fi.fast_cnn_predict_map(ch, model3, device="cpu", patch_size=patch3) \
                        if method == "CNN3x3" else med_predict(ch).astype(np.float32)
                    pi_f = np.round(pred_f).astype(np.int32)
                    sp = fi.embed_msb_vectorized(ch, l[0], p)
                    en = encrypt_image(sp, k, 7)
                    de = decrypt_image(en, k, 7)
                    out.append(fi.recover_vectorized(
                        de, pi_f, l[0], l[1], l[2], len(p)))
                return out
            timed(f"TOTAL(fast-variant) {label}", "stage", total_fast, warmup=1, repeats=3)

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    with open(OUT / "runtime_raw.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        w.writeheader(); w.writerows(raw_rows)
    with open(OUT / "runtime_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sum_rows[0].keys()))
        w.writeheader(); w.writerows(sum_rows)

    meta = {
        "host": platform.processor() or platform.machine(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "torch": __import__("torch").__version__,
        "device": "cpu",
    }

    # Fig: predictor-only (log scale)
    pred_rows = [r for r in sum_rows if r["group"] == "predictor_only"]
    fig, ax = plt.subplots(figsize=(10, 5))
    names = [r["method"] for r in pred_rows]
    means = [r["mean_ms"] for r in pred_rows]
    stds = [r["std_ms"] for r in pred_rows]
    ax.bar(names, means, yerr=stds, capsize=3)
    ax.set_yscale("log")
    ax.set_ylabel("ms per 512x512 prediction map (log, mean +- std, n=10)")
    ax.set_title(f"Predictor-only runtime — Lena 512x512, CPU ({meta['host']})")
    plt.xticks(rotation=30, ha="right")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "fig_runtime_predictor.png", dpi=140)
    plt.close(fig)

    # Fig: stage-wise grouped bars
    stage_rows = [r for r in sum_rows if r["group"] == "stage"]
    stages = ["label_map", "embed", "encrypt", "decrypt", "extract+recover"]
    scenarios = sorted({r["method"].split(" ", 2)[2] if len(r["method"].split(" ", 2)) > 2
                        else r["method"] for r in stage_rows})
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    for ax, scen in zip(axes, ("Airplane.png MED", "Airplane.png CNN3x3")):
        xs = np.arange(len(stages))
        for variant in ("original", "fast-variant"):
            vals = []
            for s in stages:
                key = f"{s} {scen}"
                m = next((r["mean_ms"] for r in stage_rows
                          if r["method"] == key), None)
                if m is None and variant == "original":
                    m = next((r["mean_ms"] for r in stage_rows
                              if r["method"].startswith(s) and scen in r["method"]
                              and "TOTAL" not in r["method"]), None)
                vals.append(m if m is not None else 0.0)
            ax.bar(xs + (0.0 if variant == "original" else 0.35), vals, width=0.35, label=variant)
        tot_o = next((r["mean_ms"] for r in stage_rows if r["method"] == f"TOTAL(original) {scen}"), None)
        tot_f = next((r["mean_ms"] for r in stage_rows if r["method"] == f"TOTAL(fast-variant) {scen}"), None)
        ax.set_xticks(xs + 0.17)
        ax.set_xticklabels(stages, rotation=20)
        ax.set_title(f"{scen}: stage-wise runtime (full-capacity payload)\n"
                     f"TOTAL original={tot_o:.0f} ms, fast-variant={tot_f:.0f} ms")
        ax.set_ylabel("ms (mean of 3 repeats)")
        ax.legend()
        ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "fig_runtime_stages.png", dpi=140)
    plt.close(fig)

    (OUT / "runtime_meta.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
