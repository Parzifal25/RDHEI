#!/usr/bin/env python3
"""Phase E — runtime and computational-cost measurements.

Part 1 — predictor-only benchmark, same protocol as the historical run:
  image: Lena.png 512x512 grayscale, device CPU, warmup=5, repeats=10,
  mean/std/min/max/median over per-run wall-clock timings.
  Methods: MED, GAP, CALIC (src/baselines.py) and the 5 CNN checkpoints via
  src/predictor.cnn_predict_map.

Part 2 — end-to-end pipeline runtime (small controlled benchmark):
  full pipeline content_owner_prepare -> sender_embed_encrypt (AES-CTR) ->
  receiver_extract_recover, split into prepare (prediction+label maps),
  embed+encrypt, decrypt+extract+recover, and total.
  Images: Airplane.png (gray, 512x512), 4.2.03.png (RGB, 512x512x3, per channel
  aggregated). Methods: MED and CNN-3x3 (v4_patch3). Repeats: 3.

Outputs under results/final_validation_20261018/:
  e_runtime_predictor.csv, e_runtime_predictor.md,
  e_runtime_e2e.csv, e_runtime_e2e.md
"""
from __future__ import annotations

import csv
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from src.baselines import med_predict, gap_predict, calic_predict
from src.rdhei_core import content_owner_prepare, sender_embed_encrypt, receiver_extract_recover
from src.encryption import generate_key
from src.cnn_model import load_model

GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"
MODELS = HERE / "models"
OUT = HERE / "results" / "final_validation_20261018"
OUT.mkdir(parents=True, exist_ok=True)

WARMUP, REPEATS = 5, 10

CNN_VARIANTS = [
    ("CNN-3x3 (v4_patch3)", "v4_patch3.pth"),
    ("CNN-5x5 (v1_full)", "v1_full.pth"),
    ("CNN-NoResidual (v2)", "v2_no_residual.pth"),
    ("CNN-NoWeightedLoss (v3)", "v3_no_weighted_loss.pth"),
    ("CNN-7x7 (v5_patch7)", "v5_patch7.pth"),
]


def bench(fn, warmup=WARMUP, repeats=REPEATS):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000.0)
    s = np.array(samples)
    return {"mean_ms": s.mean(), "std_ms": s.std(ddof=1), "min_ms": s.min(),
            "max_ms": s.max(), "median_ms": np.median(s), "n": repeats, "warmup": warmup}


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    lena = np.array(Image.open(GRAY_DIR / "Lena.png").convert("L"), dtype=np.uint8)
    print(f"Predictor-only benchmark on Lena.png {lena.shape} CPU", flush=True)

    rows = []
    for name, fn in (("MED", med_predict), ("GAP", gap_predict), ("CALIC", calic_predict)):
        st = bench(lambda: fn(lena))
        rows.append({"method": name, "params": 0, **{k: (round(v, 3) if isinstance(v, float) else v)
                                                     for k, v in st.items()}})
        print(f"  {name:8s} mean={st['mean_ms']:.3f} ms", flush=True)

    for tag, fname in CNN_VARIANTS:
        model, patch, residual, n_params = load_model(str(MODELS / fname), device="cpu")
        from src.predictor import cnn_predict_map
        st = bench(lambda: cnn_predict_map(lena, model, device="cpu", patch_size=patch))
        rows.append({"method": tag, "params": n_params,
                     **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()}})
        print(f"  {tag:26s} mean={st['mean_ms']:.3f} ms params={n_params:,}", flush=True)

    with open(OUT / "e_runtime_predictor.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    md = ["# Phase E — predictor-only runtime", "",
          f"- Started (UTC): {started}",
          f"- Host CPU: {platform.processor() or platform.machine()}; OS: {platform.platform()}",
          f"- Python {platform.python_version()}; torch CPU inference",
          "- Protocol: image Lena.png 512x512 grayscale; warm-up 5 runs; 10 timed repeats;",
          "  wall-clock per run; aggregation = arithmetic statistics over the 10 runs.",
          "- Scope: PREDICTOR ONLY (no label map, embedding, encryption, extraction, recovery).",
          "",
          "| Method | Params | Mean ms | Std ms | Min ms | Max ms | Median ms |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| {r['method']} | {r['params']:,} | {r['mean_ms']:.3f} | {r['std_ms']:.3f} "
                  f"| {r['min_ms']:.3f} | {r['max_ms']:.3f} | {r['median_ms']:.3f} |")
    (OUT / "e_runtime_predictor.md").write_text("\n".join(md) + "\n")

    # ---------------- end-to-end ----------------
    print("\nEnd-to-end pipeline runtime benchmark", flush=True)
    gray = np.array(Image.open(GRAY_DIR / "Airplane.png").convert("L"), dtype=np.uint8)
    rgb = np.array(Image.open(COLOR_DIR / "4.2.03.png").convert("RGB"), dtype=np.uint8)
    model, patch, residual, n_params = load_model(str(MODELS / "v4_patch3.pth"), device="cpu")

    e2e_rows = []

    def time_gray(img, method, mdl, ps):
        key = generate_key(32)
        t = time.perf_counter()
        co = content_owner_prepare(image=img, key=key, nonce=0, method=method, model=mdl,
                                   patch_size=ps)
        t_prep = time.perf_counter() - t
        payload = np.random.RandomState(42).randint(0, 2, size=co["capacity"], dtype=np.uint8)
        t = time.perf_counter()
        stego_enc = sender_embed_encrypt(co, payload)
        t_emb = time.perf_counter() - t
        t = time.perf_counter()
        rx = receiver_extract_recover(stego_enc, key, 0, co["bpp_map"], co["min_e_map"],
                                      co["max_e_map"], co["pred_int"], co["capacity"])
        t_rec = time.perf_counter() - t
        return t_prep, t_emb, t_rec, co["capacity"]

    def time_rgb(img_rgb, method, mdl, ps):
        key = generate_key(32)
        tp = te = tr = 0.0
        cap = 0
        for ci in range(3):
            ch = img_rgb[:, :, ci]
            nonce = 1 + ci  # base_nonce 0 -> 1,2,3
            t = time.perf_counter()
            co = content_owner_prepare(image=ch, key=key, nonce=nonce, method=method,
                                       model=mdl, patch_size=ps)
            tp += time.perf_counter() - t
            payload = np.random.RandomState(42 + ci).randint(0, 2, size=co["capacity"],
                                                             dtype=np.uint8)
            t = time.perf_counter()
            stego_enc = sender_embed_encrypt(co, payload)
            te += time.perf_counter() - t
            t = time.perf_counter()
            receiver_extract_recover(stego_enc, key, nonce, co["bpp_map"], co["min_e_map"],
                                     co["max_e_map"], co["pred_int"], co["capacity"])
            tr += time.perf_counter() - t
            cap += co["capacity"]
        return tp, te, tr, cap

    for scope, img, tfunc in (("gray Airplane 512x512", gray, time_gray),
                              ("rgb 4.2.03 512x512x3 (3 ch)", rgb, time_rgb)):
        for method, mdl in (("med", None), ("cnn", model)):
            samples = []
            for _ in range(3):
                tp, te, tr, cap = tfunc(img, method, mdl, patch)
                samples.append((tp, te, tr, tp + te + tr))
            arr = np.array(samples) * 1000.0
            row = {
                "scope": scope, "method": method,
                "capacity_bits": cap,
                "prepare_mean_ms": round(arr[:, 0].mean(), 1),
                "embed_encrypt_mean_ms": round(arr[:, 1].mean(), 1),
                "decrypt_extract_recover_mean_ms": round(arr[:, 2].mean(), 1),
                "total_mean_ms": round(arr[:, 3].mean(), 1),
                "total_std_ms": round(arr[:, 3].std(ddof=1), 1),
                "repeats": 3,
            }
            e2e_rows.append(row)
            print(f"  {scope:30s} {method:4s} total={row['total_mean_ms']:.1f} ms "
                  f"(prep {row['prepare_mean_ms']:.1f}, emb+enc {row['embed_encrypt_mean_ms']:.1f}, "
                  f"rec {row['decrypt_extract_recover_mean_ms']:.1f})", flush=True)

    with open(OUT / "e_runtime_e2e.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(e2e_rows[0].keys()))
        w.writeheader(); w.writerows(e2e_rows)

    md2 = ["# Phase E — end-to-end pipeline runtime", "",
           f"- Started (UTC): {started}",
           "- Scope: FULL PIPELINE = prediction + label maps + MSB embedding + AES-CTR",
           "  encryption + decryption + extraction + recovery.",
           "- Repeats: 3 per (image, method); values are arithmetic means over repeats.",
           "- CNN = v4_patch3 (proposed). Grayscale payload = full capacity; RGB = full",
           "  capacity on each of the 3 channels with unique per-channel nonces.",
           "",
           "| Image | Method | Capacity (bits) | Prepare ms | Embed+Encrypt ms | Decrypt+Extract+Recover ms | Total ms | Std ms |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in e2e_rows:
        md2.append(f"| {r['scope']} | {r['method']} | {r['capacity_bits']:,} "
                   f"| {r['prepare_mean_ms']:.1f} | {r['embed_encrypt_mean_ms']:.1f} "
                   f"| {r['decrypt_extract_recover_mean_ms']:.1f} "
                   f"| {r['total_mean_ms']:.1f} | {r['total_std_ms']:.1f} |")
    (OUT / "e_runtime_e2e.md").write_text("\n".join(md2) + "\n")
    print(f"\nDone. Outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
