import os
import numpy as np
import matplotlib
matplotlib.use("Agg")           # non-interactive backend (safe for servers)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


def save_comparison_panel(original: np.ndarray,
                          encrypted: np.ndarray,
                          stego: np.ndarray,
                          recovered: np.ndarray,
                          metrics: dict,
                          save_path: str,
                          title: str = "RDHEI Results"):
    """
    Save a 2x2 panel: Original | Encrypted | Stego (enc) | Recovered.
    Annotates with BPP, PSNR, MAE, SSIM.
    """
    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    panels = [
        (original,   "Original"),
        (encrypted,  "Encrypted"),
        (stego,      "Stego (Encrypted)"),
        (recovered,  "Recovered"),
    ]

    for ax, (img, label) in zip(axes, panels):
        ax.imshow(img, cmap="gray", vmin=0, vmax=255)
        ax.set_title(label, fontsize=11)
        ax.axis("off")

    metric_str = (
        f"BPP={metrics.get('bpp', 0):.4f}  "
        f"PSNR={metrics.get('psnr', 0):.2f} dB  "
        f"MAE={metrics.get('mae', 0):.4f}  "
        f"SSIM={metrics.get('ssim', 0):.4f}"
    )
    fig.text(0.5, 0.01, metric_str, ha="center", fontsize=10,
             color="darkblue", fontstyle="italic")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Panel saved → {save_path}")


def save_error_map(original: np.ndarray,
                   reconstructed: np.ndarray,
                   save_path: str,
                   amplify: float = 10.0):
    """
    Save a colour-mapped error/difference image (amplified for visibility).
    """
    diff = np.abs(original.astype(np.float32) -
                  reconstructed.astype(np.float32)) * amplify
    diff = np.clip(diff, 0, 255).astype(np.uint8)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].imshow(original, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("Original", fontsize=11)
    axes[0].axis("off")

    im = axes[1].imshow(diff, cmap="hot", vmin=0, vmax=255)
    axes[1].set_title(f"Error Map (×{amplify:.0f})", fontsize=11)
    axes[1].axis("off")
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Error map saved → {save_path}")


def save_bpp_psnr_curve(results: list, save_path: str,
                         method_label: str = "CNN"):
    """
    Plot BPP vs PSNR curve.

    Args:
        results: list of dicts with keys 'bpp' and 'psnr'.
        save_path: output file path.
        method_label: legend label.
    """
    bpps  = [r["bpp"]  for r in results]
    psnrs = [r["psnr"] for r in results if r["psnr"] != float("inf")]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(bpps[:len(psnrs)], psnrs, "o-", label=method_label, linewidth=2)
    ax.set_xlabel("BPP (bits per pixel)", fontsize=12)
    ax.set_ylabel("PSNR (dB)", fontsize=12)
    ax.set_title("Embedding Capacity vs Image Quality", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] BPP-PSNR curve saved → {save_path}")