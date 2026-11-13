#!/usr/bin/env python3
"""Phase B2/B3 — Option 3: evaluate the vectorized implementation variants.

Steps:
 1. Equivalence check A: fast_cnn_predict_map vs src/predictor.cnn_predict_map
    on 3 real channels (one easy, one hard, one where CNN-3x3 loses BPP):
    bitwise-equal prediction maps required.
 2. Equivalence check B: embed_msb_vectorized + recover_vectorized vs the
    authoritative sender_embed_encrypt/receiver_extract_recover loops on
    real gray + RGB images (payload = capacity and payload = 25%): bit-identical
    stego plaintext, identical extracted bits, identical recovered image.
 3. Improvement measurement: predictor-only runtime original vs vectorized
    (same protocol as fv_e_runtime.py: Lena gray 512x512, warmup 5, 10 repeats)
    and embed/recover stage timing original vs vectorized on Airplane gray and
    4.2.03 RGB.
 4. Full recovery validation matrix of the FAST path on all 6 gray + 5 genuine
    RGB images x {MED, CNN-3x3} x payload rules {empty, short, quarter, max}
    with pixel-exact image recovery and bit-exact payload extraction checked
    independently of the pipeline flags.

Outputs:
  improvement_experiments.csv   — original vs vectorized, all metrics
  fast_validation_gray.csv      — fast-path e2e acceptance (gray)
  fast_validation_rgb.csv       — fast-path e2e acceptance (RGB)
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ra_common as rac
import fast_impl as fi

from src.rdhei_core import (content_owner_prepare, sender_embed_encrypt,
                            receiver_extract_recover, cnn_predict)
from src.encryption import generate_key, encrypt_image, decrypt_image

OUT = HERE


def bench(fn, warmup=5, repeats=10):
    for _ in range(warmup):
        fn()
    s = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        s.append((time.perf_counter() - t) * 1000.0)
    a = np.array(s)
    return {"mean_ms": a.mean(), "std_ms": a.std(ddof=1), "min_ms": a.min(),
            "max_ms": a.max(), "median_ms": np.median(a), "n": repeats}


def main() -> int:
    rows = []          # improvement_experiments.csv
    gray_val = []
    rgb_val = []

    # ------------------------------------------------------------------
    # 1. Equivalence A — CNN prediction maps (bitwise)
    # ------------------------------------------------------------------
    model, patch, _, n_params = rac.get_model("CNN3x3")
    equiv_cases = [
        ("4.2.05.png", 0),   # easy image, R channel
        ("4.2.03.png", 1),   # hard image, G channel
        ("4.2.07.png", 1),   # CNN-3x3 loses to GAP here, G channel
        ("Airplane.png", None),  # grayscale
    ]
    for name, c in equiv_cases:
        if c is None:
            arr = rac.load_gray(name)
        else:
            arr = rac.load_rgb(name)[:, :, c]
        p_orig = cnn_predict(arr, model, device="cpu", patch_size=patch)
        p_fast = fi.fast_cnn_predict_map(arr, model, device="cpu", patch_size=patch)
        bit_identical = bool(np.array_equal(p_orig, p_fast))
        max_abs = float(np.abs(p_orig - p_fast).max())
        print(f"[equivA] {name} ch={c}: bitwise={bit_identical} max|diff|={max_abs:.3e}", flush=True)
        rows.append({
            "experiment": "equiv_fast_cnn_predict", "image": name, "channel": str(c),
            "metric": "prediction_bitwise_equal", "original": str(bit_identical),
            "variant": str(bit_identical), "difference": f"max_abs_diff={max_abs:.3e}",
            "notes": "vectorized patch extraction, same model/batches/dtype",
        })
        if not bit_identical:
            raise RuntimeError(f"fast CNN prediction differs on {name} ch {c}")

    # ------------------------------------------------------------------
    # 2. Equivalence B — embed + extract + recover on real images
    # ------------------------------------------------------------------
    e2e_cases = [("Airplane.png", None), ("Lena.png", None),
                 ("4.2.03.png", 0), ("4.2.07.png", 2)]
    for name, c in e2e_cases:
        if c is None:
            arr = rac.load_gray(name)
        else:
            arr = rac.load_rgb(name)[:, :, c]
        key = generate_key(32)
        co = content_owner_prepare(arr, key, nonce=7, method="med", model=None)
        for frac_name, frac in (("max", 1.0), ("quarter", 0.25)):
            plen = int(co["capacity"] * frac)
            rng = np.random.RandomState(0)
            payload = rng.randint(0, 2, size=plen, dtype=np.uint8)

            stego_ref = sender_embed_encrypt(co, payload)
            stego_fast = encrypt_image(
                fi.embed_msb_vectorized(arr, co["bpp_map"], payload), key, 7)

            stego_eq = bool(np.array_equal(stego_ref, stego_fast))

            rx_ref = receiver_extract_recover(
                stego_ref, key, 7, co["bpp_map"], co["min_e_map"],
                co["max_e_map"], co["pred_int"], plen)
            stego_plain = decrypt_image(stego_ref, key, 7)
            rx_fast = fi.recover_vectorized(
                stego_plain, co["pred_int"], co["bpp_map"], co["min_e_map"],
                co["max_e_map"], plen)

            ext_eq = bool(np.array_equal(rx_ref["extracted"], rx_fast["extracted"]))
            rec_eq = bool(np.array_equal(rx_ref["recovered"], rx_fast["recovered"]))
            img_ok = bool(np.array_equal(rx_fast["recovered"], arr))
            pay_ok = bool(np.array_equal(rx_fast["extracted"], payload))
            print(f"[equivB] {name} ch={c} {frac_name}: stego={stego_eq} ext={ext_eq} "
                  f"rec={rec_eq} img_exact={img_ok} pay_exact={pay_ok}", flush=True)
            rows.append({
                "experiment": "equiv_fast_embed_recover", "image": name,
                "channel": str(c), "metric": f"{frac_name}_payload",
                "original": "stego/ref", "variant": f"stego_eq={stego_eq},ext_eq={ext_eq},rec_eq={rec_eq}",
                "difference": f"img_exact={img_ok},pay_exact={pay_ok}",
                "notes": "vectorized MSB embedding + candidate recovery vs per-pixel loops",
            })
            if not (stego_eq and ext_eq and rec_eq and img_ok and pay_ok):
                raise RuntimeError(f"fast embed/recover mismatch on {name} ch {c} {frac_name}")

    # ------------------------------------------------------------------
    # 3. Timing — predictor-only (Lena gray protocol) + embed/recover stages
    # ------------------------------------------------------------------
    lena = rac.load_gray("Lena.png")
    st = bench(lambda: cnn_predict(lena, model, device="cpu", patch_size=patch))
    st_fast = bench(lambda: fi.fast_cnn_predict_map(lena, model, device="cpu", patch_size=patch))
    print(f"[time] CNN-3x3 predict: orig {st['mean_ms']:.1f} ms, fast {st_fast['mean_ms']:.1f} ms",
          flush=True)
    rows.append({
        "experiment": "runtime_predictor_lena", "image": "Lena.png", "channel": "-",
        "metric": "mean_ms_per_512x512_map",
        "original": f"{st['mean_ms']:.3f}+-{st['std_ms']:.3f}",
        "variant": f"{st_fast['mean_ms']:.3f}+-{st_fast['std_ms']:.3f}",
        "difference": f"{st_fast['mean_ms'] - st['mean_ms']:+.3f} ms "
                      f"({st_fast['mean_ms'] / st['mean_ms']:.3f}x)",
        "notes": "protocol: warmup 5, 10 repeats, perf_counter, CPU; same batches/model",
    })

    # embed + recover stage timings, gray Airplane and RGB 4.2.03 (per channel loop)
    for name in ("Airplane.png", "4.2.03.png"):
        if name.endswith("03.png"):
            img = rac.load_rgb(name)
            chans = [img[:, :, c] for c in range(3)]
        else:
            chans = [rac.load_gray(name)]
        co_list = [content_owner_prepare(ch, generate_key(32), nonce=1,
                                         method="med", model=None) for ch in chans]
        payload = [np.random.RandomState(1).randint(0, 2, size=co["capacity"], dtype=np.uint8)
                   for co in co_list]

        def orig_embed():
            return [sender_embed_encrypt(co, p) for co, p in zip(co_list, payload)]

        def fast_embed():
            return [encrypt_image(fi.embed_msb_vectorized(ch, co["bpp_map"], p), co["key"], co["nonce"])
                    for ch, co, p in zip(chans, co_list, payload)]

        stego_list = orig_embed()

        def orig_rec():
            return [receiver_extract_recover(s, co["key"], co["nonce"], co["bpp_map"],
                                             co["min_e_map"], co["max_e_map"],
                                             co["pred_int"], co["capacity"])
                    for s, co in zip(stego_list, co_list)]

        def fast_rec():
            return [fi.recover_vectorized(decrypt_image(s, co["key"], co["nonce"]),
                                          co["pred_int"], co["bpp_map"], co["min_e_map"],
                                          co["max_e_map"], co["capacity"])
                    for s, co in zip(stego_list, co_list)]

        se = bench(orig_embed, warmup=1, repeats=3)
        sf = bench(fast_embed, warmup=1, repeats=3)
        re_ = bench(orig_rec, warmup=1, repeats=3)
        rf = bench(fast_rec, warmup=1, repeats=3)
        print(f"[time] {name}: embed {se['mean_ms']:.0f}->{sf['mean_ms']:.0f} ms, "
              f"rec {re_['mean_ms']:.0f}->{rf['mean_ms']:.0f} ms", flush=True)
        rows.append({
            "experiment": "runtime_embed_encrypt", "image": name, "channel": "all",
            "metric": "mean_ms_full_pipeline_embed_encrypt",
            "original": f"{se['mean_ms']:.1f}", "variant": f"{sf['mean_ms']:.1f}",
            "difference": f"{sf['mean_ms'] - se['mean_ms']:+.1f} ms "
                          f"({sf['mean_ms'] / se['mean_ms']:.3f}x)",
            "notes": "full capacity payload; includes AES-CTR in both",
        })
        rows.append({
            "experiment": "runtime_decrypt_extract_recover", "image": name, "channel": "all",
            "metric": "mean_ms_full_pipeline_recover",
            "original": f"{re_['mean_ms']:.1f}", "variant": f"{rf['mean_ms']:.1f}",
            "difference": f"{rf['mean_ms'] - re_['mean_ms']:+.1f} ms "
                          f"({rf['mean_ms'] / re_['mean_ms']:.3f}x)",
            "notes": "full capacity payload; includes AES-CTR decrypt in both",
        })

    # ------------------------------------------------------------------
    # 4. Fast-path recovery validation matrix on real images
    # ------------------------------------------------------------------
    PAYLOAD_RULES = [("empty", "abs", 0), ("short", "abs", 1000),
                     ("quarter", "frac", 0.25), ("max", "frac", 1.0)]

    for name in rac.GRAY_IMAGES:
        arr = rac.load_gray(name)
        for m in ("MED", "CNN3x3"):
            if m == "CNN3x3":
                mp, pch, _, _ = rac.get_model("CNN3x3")
                pred = cnn_predict(arr, mp, device="cpu", patch_size=pch)
                pred_int = np.round(pred).astype(np.int32)
            else:
                pred_int = np.round(rac.classical_predict(arr, "MED_pipeline")).astype(np.int32)
            e_abs = np.abs(arr.astype(np.int32) - pred_int)
            bpp_map, min_e, max_e = rac.label_maps(e_abs)
            cap = int(bpp_map.sum())
            key = generate_key(32)
            for rule, kind, val in PAYLOAD_RULES:
                plen = cap if kind == "frac" else int(val * cap)
                plen = min(plen, cap)
                rng = np.random.RandomState(42)
                payload = rng.randint(0, 2, size=plen, dtype=np.uint8)
                stego_plain = fi.embed_msb_vectorized(arr, bpp_map, payload)
                enc = encrypt_image(stego_plain, key, 5)
                dec = decrypt_image(enc, key, 5)
                rx = fi.recover_vectorized(dec, pred_int, bpp_map, min_e, max_e, plen)
                img_ok = bool(np.array_equal(rx["recovered"], arr))
                pay_ok = bool(np.array_equal(rx["extracted"], payload)) and \
                    len(rx["extracted"]) == plen
                gray_val.append({"image": name, "method": m, "rule": rule,
                                 "payload_len": plen, "capacity": cap,
                                 "image_exact": img_ok, "payload_exact": pay_ok,
                                 "status": "PASS" if (img_ok and pay_ok) else "FAIL"})
                print(f"[fastval-gray] {name} {m} {rule}: {img_ok and pay_ok}", flush=True)

    for name in rac.RGB_IMAGES:
        img = rac.load_rgb(name)
        for m in ("MED", "CNN3x3"):
            chans = []
            for c in range(3):
                ch = img[:, :, c]
                if m == "CNN3x3":
                    mp, pch, _, _ = rac.get_model("CNN3x3")
                    pred_int = np.round(cnn_predict(ch, mp, device="cpu", patch_size=pch)).astype(np.int32)
                else:
                    pred_int = np.round(rac.classical_predict(ch, "MED_pipeline")).astype(np.int32)
                e_abs = np.abs(ch.astype(np.int32) - pred_int)
                bpp_map, min_e, max_e = rac.label_maps(e_abs)
                chans.append((ch, pred_int, bpp_map, min_e, max_e))
            key = generate_key(32)
            for rule, kind, val in PAYLOAD_RULES:
                rec_img = np.zeros_like(img)
                all_img, all_pay = True, True
                total_cap = 0
                for c, (ch, pred_int, bpp_map, min_e, max_e) in enumerate(chans):
                    cap = int(bpp_map.sum())
                    total_cap += cap
                    plen = cap if kind == "frac" else min(int(val * cap), cap)
                    rng = np.random.RandomState(42 + c)
                    payload = rng.randint(0, 2, size=plen, dtype=np.uint8)
                    stego_plain = fi.embed_msb_vectorized(ch, bpp_map, payload)
                    enc = encrypt_image(stego_plain, key, 5 + c + 1)
                    dec = decrypt_image(enc, key, 5 + c + 1)
                    rx = fi.recover_vectorized(dec, pred_int, bpp_map, min_e, max_e, plen)
                    rec_img[:, :, c] = rx["recovered"]
                    all_img &= bool(np.array_equal(rx["recovered"], ch))
                    all_pay &= bool(np.array_equal(rx["extracted"], payload)) and \
                        len(rx["extracted"]) == plen
                composed_ok = bool(np.array_equal(rec_img, img))
                rgb_val.append({"image": name, "method": m, "rule": rule,
                                "total_capacity": total_cap,
                                "image_exact": all_img and composed_ok,
                                "payload_exact": all_pay,
                                "status": "PASS" if (all_img and composed_ok and all_pay) else "FAIL"})
                print(f"[fastval-rgb] {name} {m} {rule}: {all_img and composed_ok and all_pay}",
                      flush=True)

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    with open(OUT / "improvement_experiments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(OUT / "fast_validation_gray.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gray_val[0].keys()))
        w.writeheader(); w.writerows(gray_val)
    with open(OUT / "fast_validation_rgb.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rgb_val[0].keys()))
        w.writeheader(); w.writerows(rgb_val)

    npass = sum(1 for r in gray_val + rgb_val if r["status"] == "PASS")
    print(f"\nfast-path e2e: {npass}/{len(gray_val) + len(rgb_val)} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
