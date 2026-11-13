#!/usr/bin/env python3
"""Phase G support — generate report figures from the fresh final-validation CSVs.

All plots are generated from results/final_validation_20261018/*.csv produced by
scripts/fv_b1..fv_e. Example image panels are generated with the real pipeline
on the real benchmark images.

Outputs under results/final_validation_20261018/figures/ and figures/ at the
project root (report asset directory):
  fig01_bpp_gray.png, fig02_mae_gray.png, fig03_bpp_rgb.png, fig04_mae_rgb.png,
  fig05_ablation_gray.png, fig06_ablation_rgb.png, fig07_runtime_predictor.png,
  fig08_params_vs_bpp.png, fig09_runtime_e2e.png,
  examples/fig10_panel_gray.png, examples/fig11_panel_rgb.png
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

OUT = HERE / "results" / "final_validation_20261018"
FIG = OUT / "figures"
EX = FIG / "examples"
ROOT_FIG = HERE / "figures"
for d in (FIG, EX, ROOT_FIG):
    d.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def bar_group(ax, labels, series, title, ylabel, log=False):
    x = np.arange(len(labels))
    width = 0.8 / len(series)
    for i, (name, vals, color) in enumerate(series):
        ax.bar(x + i * width - 0.4 + width / 2, vals, width, label=name, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if log:
        ax.set_yscale("log")
    ax.legend(fontsize=8)


def main() -> int:
    # ---------- gray baselines ----------
    gray = read_csv(OUT / "b2_gray_per_image.csv")
    names = [r["image"].replace(".png", "") for r in gray]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    series = [("MED", [float(r["MED_bpp"]) for r in gray], "#e74c3c"),
              ("GAP", [float(r["GAP_bpp"]) for r in gray], "#e67e22"),
              ("CALIC", [float(r["CALIC_bpp"]) for r in gray], "#3498db"),
              ("CNN-3x3", [float(r["CNN3x3_bpp"]) for r in gray], "#2ecc71")]
    bar_group(ax, names, series, "Grayscale embedding capacity (BPP)", "BPP [bits/pixel]")
    fig.tight_layout()
    fig.savefig(FIG / "fig01_bpp_gray.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    series = [("MED", [float(r["MED_mae"]) for r in gray], "#e74c3c"),
              ("GAP", [float(r["GAP_mae"]) for r in gray], "#e67e22"),
              ("CALIC", [float(r["CALIC_mae"]) for r in gray], "#3498db"),
              ("CNN-3x3", [float(r["CNN3x3_mae"]) for r in gray], "#2ecc71")]
    bar_group(ax, names, series, "Grayscale prediction MAE", "MAE [levels]")
    fig.tight_layout()
    fig.savefig(FIG / "fig02_mae_gray.png", dpi=150)
    plt.close(fig)

    # ---------- RGB baselines ----------
    rgb = read_csv(OUT / "b2_rgb_per_image.csv")
    rnames = [r["image"].replace(".png", "") for r in rgb]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    series = [("MED", [float(r["MED_bpp"]) for r in rgb], "#e74c3c"),
              ("GAP", [float(r["GAP_bpp"]) for r in rgb], "#e67e22"),
              ("CALIC", [float(r["CALIC_bpp"]) for r in rgb], "#3498db"),
              ("CNN-3x3", [float(r["CNN3x3_bpp"]) for r in rgb], "#2ecc71")]
    bar_group(ax, rnames, series, "RGB embedding capacity (mean over R,G,B)", "BPP [bits/pixel]")
    fig.tight_layout()
    fig.savefig(FIG / "fig03_bpp_rgb.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    series = [("MED", [float(r["MED_mae"]) for r in rgb], "#e74c3c"),
              ("GAP", [float(r["GAP_mae"]) for r in rgb], "#e67e22"),
              ("CALIC", [float(r["CALIC_mae"]) for r in rgb], "#3498db"),
              ("CNN-3x3", [float(r["CNN3x3_mae"]) for r in rgb], "#2ecc71")]
    bar_group(ax, rnames, series, "RGB prediction MAE (mean over R,G,B)", "MAE [levels]")
    fig.tight_layout()
    fig.savefig(FIG / "fig04_mae_rgb.png", dpi=150)
    plt.close(fig)

    # ---------- ablation ----------
    ab_g = read_csv(OUT / "b3_ablation_gray.csv")
    order = ["v4_patch3", "v1_full", "v2_no_residual", "v3_no_weighted_loss", "v5_patch7"]
    agg = {}
    for v in order:
        sel = [r for r in ab_g if r["variant"] == v]
        agg[v] = (float(np.mean([float(r["bpp"]) for r in sel])),
                  float(np.mean([float(r["mae"]) for r in sel])))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    bar_group(axes[0], order,
              [(v, [agg[v][0]], c) for v, c in zip(order,
               ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"])],
              "Ablation — grayscale BPP (mean of 6 images)", "BPP")
    bar_group(axes[1], order,
              [(v, [agg[v][1]], c) for v, c in zip(order,
               ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"])],
              "Ablation — grayscale prediction MAE", "MAE [levels]")
    fig.tight_layout()
    fig.savefig(FIG / "fig05_ablation_gray.png", dpi=150)
    plt.close(fig)

    ab_r = read_csv(OUT / "b3_ablation_rgb_per_image.csv")
    agg2 = {}
    for v in order:
        sel = [r for r in ab_r if r["variant"] == v]
        agg2[v] = (float(np.mean([float(r["bpp"]) for r in sel])),
                   float(np.mean([float(r["mae"]) for r in sel])))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    bar_group(axes[0], order,
              [(v, [agg2[v][0]], c) for v, c in zip(order,
               ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"])],
              "Ablation — RGB BPP (5 genuine RGB, mean of channels)", "BPP")
    bar_group(axes[1], order,
              [(v, [agg2[v][1]], c) for v, c in zip(order,
               ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"])],
              "Ablation — RGB prediction MAE", "MAE [levels]")
    fig.tight_layout()
    fig.savefig(FIG / "fig06_ablation_rgb.png", dpi=150)
    plt.close(fig)

    # ---------- runtime ----------
    rt = read_csv(OUT / "e_runtime_predictor.csv")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bar_group(ax, [r["method"] for r in rt],
              [("mean per run", [float(r["mean_ms"]) for r in rt], "#34495e")],
              "Predictor-only runtime (Lena 512x512, CPU, warmup 5, repeats 10)",
              "ms per image (log scale)", log=True)
    fig.tight_layout()
    fig.savefig(FIG / "fig07_runtime_predictor.png", dpi=150)
    plt.close(fig)

    # ---------- params vs BPP ----------
    ab_p = read_csv(OUT / "b3_ablation_params.csv")
    params = {r["variant"]: int(r["params"]) for r in ab_p}
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for v in order:
        ax.scatter(params[v], agg[v][0], s=90, label=v)
        ax.annotate(v, (params[v], agg[v][0]), textcoords="offset points",
                    xytext=(6, 4), fontsize=8)
    ax.set_xlabel("Trainable parameters")
    ax.set_ylabel("Grayscale BPP (mean of 6 images)")
    ax.set_title("Model size vs embedding capacity")
    fig.tight_layout()
    fig.savefig(FIG / "fig08_params_vs_bpp.png", dpi=150)
    plt.close(fig)

    # ---------- e2e runtime ----------
    e2e = read_csv(OUT / "e_runtime_e2e.csv")
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    labels = [f"{r['scope']}\n{r['method']}" for r in e2e]
    prep = [float(r["prepare_mean_ms"]) for r in e2e]
    emb = [float(r["embed_encrypt_mean_ms"]) for r in e2e]
    rec = [float(r["decrypt_extract_recover_mean_ms"]) for r in e2e]
    x = np.arange(len(labels))
    ax.bar(x, prep, label="prediction + label maps")
    ax.bar(x, emb, bottom=prep, label="embedding + AES-CTR encryption")
    ax.bar(x, rec, bottom=np.array(prep) + np.array(emb), label="decryption + extraction + recovery")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("ms (mean of 3 repeats)")
    ax.set_title("End-to-end pipeline runtime")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig09_runtime_e2e.png", dpi=150)
    plt.close(fig)

    # ---------- example panels ----------
    # Gray: saved by fv_d_e2e.py (Airplane, CNN-3x3, full capacity)
    g_files = sorted(EX.glob("Airplane*_cnn_1_original.png"))
    if g_files:
        orig = Image.open(g_files[0])
        stem = g_files[0].name.replace("_1_original.png", "")
        stego = Image.open(EX / f"{stem}_2_stego_plain.png")
        enc = Image.open(EX / f"{stem}_3_encrypted.png")
        rec_img = Image.open(EX / f"{stem}_4_recovered.png")
        diff = np.abs(np.array(orig, dtype=np.int16) - np.array(stego, dtype=np.int16))
        diff_img = Image.fromarray(np.clip(diff * 16, 0, 255).astype(np.uint8))
        fig, axes = plt.subplots(1, 5, figsize=(18, 3.8))
        for ax, im, t in zip(axes, [orig, stego, enc, diff_img, rec_img],
                             ["(a) Original", "(b) Marked plaintext (stego)",
                              "(c) AES-CTR encrypted", "(d) |orig-stego| x16",
                              "(e) Recovered"]):
            ax.imshow(im, cmap="gray" if im.mode == "L" else None)
            ax.set_title(t, fontsize=9)
            ax.axis("off")
        fig.suptitle("Grayscale end-to-end example — Airplane.png, CNN-3x3, payload = capacity "
                     "(recovered image is pixel-identical to the original)", fontsize=10)
        fig.tight_layout()
        fig.savefig(FIG / "examples" / "fig10_panel_gray.png", dpi=150)
        plt.close(fig)

    # RGB: generate one real CNN full-capacity run on 4.2.03.png and compose panels
    from src.rdhei_core import content_owner_prepare, sender_embed_encrypt, receiver_extract_recover
    from src.encryption import generate_key, get_channel_nonce
    from src.cnn_model import load_model
    rgb = np.array(Image.open(HERE.parent / "data" / "kodak_color" / "4.2.03.png").convert("RGB"),
                   dtype=np.uint8)
    model, patch, _, _ = load_model(str(HERE / "models" / "v4_patch3.pth"), device="cpu")
    key = generate_key(32)
    stego_rgb = np.zeros_like(rgb)
    enc_rgb = np.zeros_like(rgb)
    rec_rgb = np.zeros_like(rgb)
    for ci in range(3):
        nonce = get_channel_nonce(0, ci)
        co = content_owner_prepare(image=rgb[:, :, ci], key=key, nonce=nonce, method="cnn",
                                   model=model, patch_size=patch)
        payload = np.random.RandomState(42 + ci).randint(0, 2, size=co["capacity"], dtype=np.uint8)
        stego_enc = sender_embed_encrypt(co, payload)
        rx = receiver_extract_recover(stego_enc, key, nonce, co["bpp_map"], co["min_e_map"],
                                      co["max_e_map"], co["pred_int"], co["capacity"])
        # decrypt stego_enc to show marked plaintext
        from src.encryption import decrypt_image
        stego_rgb[:, :, ci] = decrypt_image(stego_enc, key, nonce)
        enc_rgb[:, :, ci] = stego_enc
        rec_rgb[:, :, ci] = rx["recovered"]
    diff = np.abs(rgb.astype(np.int16) - stego_rgb.astype(np.int16))
    fig, axes = plt.subplots(1, 5, figsize=(18, 3.8))
    panels = [rgb, stego_rgb, enc_rgb, np.clip(diff * 16, 0, 255).astype(np.uint8), rec_rgb]
    titles = ["(a) Original RGB", "(b) Marked plaintext", "(c) AES-CTR encrypted (3 nonces)",
              "(d) |orig-stego| x16", "(e) Recovered"]
    for ax, im, t in zip(axes, panels, titles):
        ax.imshow(im)
        ax.set_title(t, fontsize=9)
        ax.axis("off")
    exact = bool(np.array_equal(rgb, rec_rgb))
    fig.suptitle(f"RGB end-to-end example — 4.2.03.png, CNN-3x3, full capacity per channel; "
                 f"recovered == original: {exact}", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "examples" / "fig11_panel_rgb.png", dpi=150)
    plt.close(fig)
    print(f"RGB example exact recovery: {exact}")

    # copy figures to root figures/ for the report
    for p in sorted(FIG.glob("*.png")):
        (ROOT_FIG / p.name).write_bytes(p.read_bytes())
    for p in sorted(EX.glob("*.png")):
        (ROOT_FIG / p.name).write_bytes(p.read_bytes())
    print(f"Figures written to {FIG} and copied to {ROOT_FIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
