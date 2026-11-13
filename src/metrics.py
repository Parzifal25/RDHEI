import numpy as np
from typing import Union


# ---------------------------------------------------------------------------
# BPP
# ---------------------------------------------------------------------------

def bpp(payload_bits: int, image: np.ndarray) -> float:
    """
    Bits Per Pixel embedding capacity.

    Args:
        payload_bits: Number of bits successfully embedded.
        image:        2D numpy array (used for H x W).
    Returns:
        bpp value (float).
    """
    h, w = image.shape[:2]
    return payload_bits / (h * w)


# ---------------------------------------------------------------------------
# PSNR
# ---------------------------------------------------------------------------

def psnr(original: np.ndarray, reconstructed: np.ndarray,
         max_val: float = 255.0) -> float:
    """
    Peak Signal-to-Noise Ratio.

    Args:
        original:      2D uint8 reference image.
        reconstructed: 2D uint8 reconstructed image.
        max_val:       Maximum pixel value (255 for uint8).
    Returns:
        PSNR in dB. Returns inf if images are identical.
    """
    mse = np.mean((original.astype(np.float64) -
                   reconstructed.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * np.log10(max_val ** 2 / mse)


# ---------------------------------------------------------------------------
# MAE
# ---------------------------------------------------------------------------

def mae(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """
    Mean Absolute Error.

    Args:
        original:      2D uint8 reference image.
        reconstructed: 2D uint8 reconstructed image.
    Returns:
        MAE value (float).
    """
    return np.mean(np.abs(original.astype(np.float64) -
                           reconstructed.astype(np.float64)))


# ---------------------------------------------------------------------------
# SSIM
# ---------------------------------------------------------------------------

def ssim(original: np.ndarray, reconstructed: np.ndarray,
         window_size: int = 11,
         C1: float = (0.01 * 255) ** 2,
         C2: float = (0.03 * 255) ** 2) -> float:
    """
    Structural Similarity Index (simplified, pure-numpy implementation).

    Args:
        original:      2D uint8 reference image.
        reconstructed: 2D uint8 reconstructed image.
        window_size:   Gaussian window size.
        C1, C2:        Stability constants.
    Returns:
        SSIM score in [-1, 1].
    """
    from scipy.ndimage import uniform_filter

    x = original.astype(np.float64)
    y = reconstructed.astype(np.float64)

    mu_x = uniform_filter(x, size=window_size)
    mu_y = uniform_filter(y, size=window_size)

    mu_x2 = mu_x ** 2
    mu_y2 = mu_y ** 2
    mu_xy = mu_x * mu_y

    sig_x2 = uniform_filter(x ** 2, size=window_size) - mu_x2
    sig_y2 = uniform_filter(y ** 2, size=window_size) - mu_y2
    sig_xy  = uniform_filter(x * y,  size=window_size) - mu_xy

    numerator   = (2 * mu_xy + C1) * (2 * sig_xy + C2)
    denominator = (mu_x2 + mu_y2 + C1) * (sig_x2 + sig_y2 + C2)

    ssim_map = numerator / (denominator + 1e-10)
    return float(np.mean(ssim_map))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def evaluate_all(original: np.ndarray,
                 reconstructed: np.ndarray,
                 payload_bits: int) -> dict:
    """
    Compute all metrics at once.

    Returns:
        dict with keys: bpp, psnr, mae, ssim
    """
    return {
        "bpp":  bpp(payload_bits, original),
        "psnr": psnr(original, reconstructed),
        "mae":  mae(original, reconstructed),
        "ssim": ssim(original, reconstructed),
    }


def print_metrics(metrics: dict):
    """Pretty-print metric results."""
    print("=" * 40)
    print(f"  BPP  : {metrics['bpp']:.4f} bits/pixel")
    psnr_val = metrics['psnr']
    if psnr_val == float("inf"):
        print(f"  PSNR : ∞ dB  (perfect recovery)")
    else:
        print(f"  PSNR : {psnr_val:.2f} dB")
    print(f"  MAE  : {metrics['mae']:.4f}")
    print(f"  SSIM : {metrics['ssim']:.4f}")
    print("=" * 40)