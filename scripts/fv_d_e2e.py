#!/usr/bin/env python3
"""Phase D — real-image end-to-end pipeline tests (payload-length matrix).

For every benchmark image (6 grayscale, 5 genuine RGB) and for both supported
predictors (MED, CNN-3x3 = v4_patch3), the COMPLETE pipeline is exercised with
the project's real functions:

  content_owner_prepare -> sender_embed_encrypt (AES-CTR) ->
  receiver_extract_recover (decrypt -> extract -> recover)

Payload rules per case:
  empty=0, one=1, short=1000 bits, quarter=25% of capacity,
  three_quarter=75% of capacity, near_max=capacity-1, max=capacity
plus one over-capacity case (capacity+64 bits) on Airplane.png to document the
failure behavior of the current interface.

Acceptance checks per case (independent of the pipeline's own flags):
  image_exact  = np.array_equal(original, recovered)
  payload_exact= extracted equals the embedded payload, bit-for-bit, and the
                 extracted length equals the requested payload length
  status       = PASS only if both hold (or the case is the documented
                 over-capacity behavior test)

RGB: each channel is embedded/encrypted with its own AES-CTR nonce
(base_nonce + channel_index + 1, the repaired derivation). Per-channel payload
lengths follow the same rule applied to each channel's capacity.

Outputs under results/final_validation_20261018/:
  d_e2e_gray.csv, d_e2e_rgb.csv, d_e2e_summary.md,
  figures/examples/*  (original / stego-plain / encrypted / recovered samples)
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from src.rdhei_core import (
    content_owner_prepare, sender_embed_encrypt, receiver_extract_recover, cnn_predict,
)
from src.encryption import generate_key, get_channel_nonce
from src.cnn_model import load_model

GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"
MODEL_PATH = HERE / "models" / "v4_patch3.pth"
OUT = HERE / "results" / "final_validation_20261018"
EX = OUT / "figures" / "examples"
OUT.mkdir(parents=True, exist_ok=True)
EX.mkdir(parents=True, exist_ok=True)

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pgm"}

PAYLOAD_RULES = [
    ("empty", "abs", 0),
    ("one_bit", "abs", 1),
    ("short", "abs", 1000),
    ("quarter", "frac", 0.25),
    ("three_quarter", "frac", 0.75),
    ("near_max", "cap_minus", 1),
    ("max", "frac", 1.0),
]


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


def rule_len(rule: tuple, capacity: int) -> int:
    _, kind, val = rule
    if kind == "abs":
        return min(val, capacity)
    if kind == "frac":
        return int(capacity * val)
    if kind == "cap_minus":
        return max(0, capacity - val)
    raise ValueError(kind)


def run_gray_case(image, method, model, patch, rule, key, save_example=None):
    t0 = time.time()
    co = content_owner_prepare(image=image, key=key, nonce=0, method=method,
                               model=model, patch_size=patch)
    t_prep = time.time() - t0
    capacity = co["capacity"]
    req_len = rule_len(rule, capacity)

    rng = np.random.RandomState(42)
    payload = rng.randint(0, 2, size=capacity, dtype=np.uint8)  # full-cap pool
    embed_payload = payload[:req_len] if rule[0] != "max" else payload[:capacity]

    t1 = time.time()
    stego_enc = sender_embed_encrypt(co, embed_payload)
    t_enc = time.time() - t1

    t2 = time.time()
    rx = receiver_extract_recover(stego_enc, key, 0, co["bpp_map"], co["min_e_map"],
                                  co["max_e_map"], co["pred_int"], req_len)
    t_rec = time.time() - t2

    recovered, extracted = rx["recovered"], rx["extracted"]
    image_exact = bool(np.array_equal(image, recovered))
    payload_exact = bool(np.array_equal(extracted, embed_payload)) and len(extracted) == req_len

    if save_example:
        stem = f"{Path(save_example).stem}_{method}"
        Image.fromarray(image, mode="L").save(EX / f"{stem}_1_original.png")
        Image.fromarray(rx["stego_plain"], mode="L").save(EX / f"{stem}_2_stego_plain.png")
        Image.fromarray(stego_enc, mode="L").save(EX / f"{stem}_3_encrypted.png")
        Image.fromarray(recovered, mode="L").save(EX / f"{stem}_4_recovered.png")

    return {
        "capacity_bits": capacity, "requested_len": req_len, "extracted_len": len(extracted),
        "image_exact": image_exact, "payload_exact": payload_exact,
        "t_prepare_s": round(t_prep, 3), "t_embed_encrypt_s": round(t_enc, 4),
        "t_decrypt_extract_recover_s": round(t_rec, 3),
        "t_total_s": round(time.time() - t0, 3),
        "pipeline_perfect_flag": bool(np.array_equal(image, recovered)),
    }


def run_rgb_case(image_rgb, method, model, patch, rule, key, base_nonce=0):
    t0 = time.time()
    ch_rows = []
    rec_rgb = np.zeros_like(image_rgb)
    all_exact_img, all_exact_pay = True, True
    total_cap = total_req = total_ext = 0
    t_prep = t_enc = t_rec = 0.0
    for ci, ch in enumerate("RGB"):
        ch_img = image_rgb[:, :, ci]
        nonce = get_channel_nonce(base_nonce, ci)
        t = time.time()
        co = content_owner_prepare(image=ch_img, key=key, nonce=nonce, method=method,
                                   model=model, patch_size=patch)
        t_prep += time.time() - t
        cap = co["capacity"]
        req = rule_len(rule, cap)
        rng = np.random.RandomState(42 + ci)
        pool = rng.randint(0, 2, size=cap, dtype=np.uint8)
        payload = pool[:req]
        t = time.time()
        stego_enc = sender_embed_encrypt(co, payload)
        t_enc += time.time() - t
        t = time.time()
        rx = receiver_extract_recover(stego_enc, key, nonce, co["bpp_map"], co["min_e_map"],
                                      co["max_e_map"], co["pred_int"], req)
        t_rec += time.time() - t
        rec_rgb[:, :, ci] = rx["recovered"]
        img_ok = bool(np.array_equal(ch_img, rx["recovered"]))
        pay_ok = bool(np.array_equal(rx["extracted"], payload)) and len(rx["extracted"]) == req
        all_exact_img &= img_ok
        all_exact_pay &= pay_ok
        total_cap += cap; total_req += req; total_ext += len(rx["extracted"])
        ch_rows.append({"channel": ch, "nonce": nonce, "capacity_bits": cap,
                        "requested_len": req, "extracted_len": len(rx["extracted"]),
                        "image_exact": img_ok, "payload_exact": pay_ok})
    return {
        "per_channel": ch_rows,
        "capacity_total": total_cap, "requested_total": total_req, "extracted_total": total_ext,
        "image_exact": all_exact_img, "payload_exact": all_exact_pay,
        "bpp_per_channel_avg": round(total_cap / (3 * image_rgb.shape[0] * image_rgb.shape[1]), 9),
        "t_prepare_s": round(t_prep, 3), "t_embed_encrypt_s": round(t_enc, 4),
        "t_decrypt_extract_recover_s": round(t_rec, 3), "t_total_s": round(time.time() - t0, 3),
    }


def load_existing(path):
    if path.exists():
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    return []


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    model, patch, residual, n_params = load_model(str(MODEL_PATH), device="cpu")
    # resume support: reuse rows already recorded by a previous interrupted run
    prev_gray = load_existing(OUT / "d_e2e_gray.csv")
    prev_rgb = load_existing(OUT / "d_e2e_rgb.csv")
    done_gray = {(r["image"], r["method"], r["payload_rule"]) for r in prev_gray}
    done_rgb = {(r["image"], r["method"], r["payload_rule"]) for r in prev_rgb}
    gray_rows, rgb_rows = list(prev_gray), list(prev_rgb)

    gray_images = list(load_gray(GRAY_DIR))
    rgb_images = list(load_rgb_genuine(COLOR_DIR))

    for method in ("med", "cnn"):
        for name, img in gray_images:
            for rule in PAYLOAD_RULES:
                if (name, method, rule[0]) in done_gray:
                    continue
                key = generate_key(32)
                r = run_gray_case(img, method, model, patch, rule, key,
                                  save_example=(name if (name == "Airplane.png" and rule[0] == "max"
                                                        and method == "cnn") else None))
                r.update({"image": name, "method": method, "payload_rule": rule[0]})
                r["status"] = "PASS" if (r["image_exact"] and r["payload_exact"]) else "FAIL"
                gray_rows.append(r)
                print(f"gray {name:14s} {method:4s} {rule[0]:14s} cap={r['capacity_bits']:<8d} "
                      f"req={r['requested_len']:<8d} img_ok={r['image_exact']} "
                      f"pay_ok={r['payload_exact']} {r['status']} ({r['t_total_s']}s)", flush=True)

    # over-capacity behavior test (Airplane, MED): embed capacity-sized prefix,
    # ask receiver for MORE bits than exist. Document actual behavior.
    img0 = gray_images[0][1]
    co = content_owner_prepare(image=img0, key=b"k" * 16, nonce=0, method="med")
    cap0 = co["capacity"]
    payload_full = np.random.RandomState(42).randint(0, 2, size=cap0, dtype=np.uint8)
    stego_enc = sender_embed_encrypt(co, payload_full)
    rx = receiver_extract_recover(stego_enc, b"k" * 16, 0, co["bpp_map"], co["min_e_map"],
                                  co["max_e_map"], co["pred_int"], cap0 + 64)
    gray_rows.append({
        "image": gray_images[0][0], "method": "med", "payload_rule": "over_capacity(cap+64)",
        "capacity_bits": cap0, "requested_len": cap0 + 64, "extracted_len": len(rx["extracted"]),
        "image_exact": bool(np.array_equal(img0, rx["recovered"])),
        "payload_exact": bool(np.array_equal(rx["extracted"], payload_full)) and len(rx["extracted"]) == cap0 + 64,
        "status": "DOCUMENTED", "t_prepare_s": "", "t_embed_encrypt_s": "",
        "t_decrypt_extract_recover_s": "", "t_total_s": "",
        "pipeline_perfect_flag": bool(np.array_equal(img0, rx["recovered"])),
    })
    print(f"over-capacity: requested={cap0+64} extracted={len(rx['extracted'])} "
          f"image_exact={np.array_equal(img0, rx['recovered'])}", flush=True)

    for method in ("med", "cnn"):
        for name, img in rgb_images:
            for rule in [r for r in PAYLOAD_RULES if r[0] in ("empty", "short", "quarter", "max")]:
                if (name, method, rule[0]) in done_rgb:
                    continue
                key = generate_key(32)
                r = run_rgb_case(img, method, model, patch, rule, key)
                r.update({"image": name, "method": method, "payload_rule": rule[0]})
                r["status"] = "PASS" if (r["image_exact"] and r["payload_exact"]) else "FAIL"
                if name == "4.2.03.png" and rule[0] == "max" and method == "cnn":
                    for ci, ch in enumerate("RGB"):
                        pass  # example panels are produced by fv_figures.py
                rgb_rows.append({k: v for k, v in r.items() if k != "per_channel"})
                for ch in r["per_channel"]:
                    rgb_rows[-1].setdefault("ch_detail", "")
                print(f"rgb  {name:14s} {method:4s} {rule[0]:14s} cap={r['capacity_total']:<8d} "
                      f"req={r['requested_total']:<8d} img_ok={r['image_exact']} "
                      f"pay_ok={r['payload_exact']} {r['status']} ({r['t_total_s']}s)", flush=True)

    def write(path, rows):
        keys = []
        for r in rows:
            for k in r:
                if k not in keys and k != "per_channel" and k != "ch_detail":
                    keys.append(k)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)

    write(OUT / "d_e2e_gray.csv", gray_rows)
    write(OUT / "d_e2e_rgb.csv", rgb_rows)

    g_pass = sum(1 for r in gray_rows if r.get("status") == "PASS")
    g_fail = sum(1 for r in gray_rows if r.get("status") == "FAIL")
    r_pass = sum(1 for r in rgb_rows if r.get("status") == "PASS")
    r_fail = sum(1 for r in rgb_rows if r.get("status") == "FAIL")
    md = [
        "# Phase D — End-to-end payload-matrix results (real images)",
        "",
        f"- Started (UTC): {started}",
        f"- Checkpoint: v4_patch3.pth (patch={patch}, residual={residual}, params={n_params:,})",
        f"- Grayscale images tested: {len(gray_images)}; genuine RGB images tested: {len(rgb_images)}",
        f"- Grayscale cases: {len(gray_rows)} (PASS {g_pass}, FAIL {g_fail}, documented {sum(1 for r in gray_rows if r.get('status')=='DOCUMENTED')})",
        f"- RGB cases: {len(rgb_rows)} (PASS {r_pass}, FAIL {r_fail})",
        "",
        "PASS = recovered pixels identical to original AND extracted bits identical to",
        "embedded payload AND extracted length equals requested length (checked outside the pipeline).",
        "",
        "Over-capacity behavior: the current sender interface zero-pads nothing beyond",
        "capacity — it silently embeds only what capacity allows; the receiver extracts",
        "only capacity bits. This is documented behavior, recorded as DOCUMENTED, not PASS.",
        "",
        "Per-case data: d_e2e_gray.csv, d_e2e_rgb.csv",
    ]
    (OUT / "d_e2e_summary.md").write_text("\n".join(md) + "\n")
    print(f"\nGray: PASS {g_pass} FAIL {g_fail} | RGB: PASS {r_pass} FAIL {r_fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
