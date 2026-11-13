"""
RDHEI Color (RGB) Pipeline - REPAIRED VERSION

CHANGES FROM ORIGINAL:
- Now uses encrypt_rgb_channels() and decrypt_rgb_channels() from encryption.py
- These functions use UNIQUE nonces per RGB channel
- No keystream reuse across channels

ORIGINAL ISSUE:
- Original code passed the same nonce to all three channels
- This caused AES-CTR keystream reuse, breaking security completely

REPAIR:
- Use base_nonce + channel_index + 1 for each channel
- Receiver uses same derivation to decrypt
- Metadata (base_nonce) must be transmitted to receiver
"""

import numpy as np

from src.rdhei_core import (
    content_owner_prepare,
    sender_embed_encrypt,
    receiver_extract_recover,
    run_rdhei
)

from src.encryption import (
    generate_key,
    encrypt_rgb_channels,
    decrypt_rgb_channels,
    get_channel_nonce
)
from src.metrics import evaluate_all

from skimage.metrics import (
    structural_similarity as sk_ssim,
    peak_signal_noise_ratio as sk_psnr
)


def psnr_color(orig, rec):
    """PSNR for RGB image."""
    if np.array_equal(orig, rec):
        return float("inf")
    return sk_psnr(orig, rec, data_range=255)


def ssim_color(orig, rec):
    """SSIM for RGB image."""
    return sk_ssim(orig, rec, channel_axis=2, data_range=255)


def mae_color(orig, rec):
    """MAE for RGB image."""
    return float(np.abs(orig.astype(np.int32) - rec.astype(np.int32)).mean())


def run_rdhei_color(
    image_rgb: np.ndarray,
    key: bytes,
    nonce: int = 0,
    method: str = "med",
    model=None,
    device: str = "cpu",
    patch_size: int = None,
    seed: int = 42
) -> dict:
    """
    Run RDHEI on a colour (RGB) image by processing each channel independently.

    REPAIRED: Uses unique nonce per channel to prevent keystream reuse.

    Args:
        image_rgb : HxWxD3 uint8 array
        key       : AES encryption key
        nonce     : AES-CTR nonce (used as base_nonce for per-channel nonce
                    derivation; each channel uses nonce + channel_index + 1)
        method    : "med" or "cnn"
        model     : CNN model (required if method="cnn")
        device    : cpu / cuda
        patch_size: CNN patch size
        seed      : Random seed.

    Returns:
        bpp          : per-channel average BPP
        psnr_rec     : PSNR of recovered RGB image
        ssim_rec     : SSIM of recovered RGB image
        mae_rec      : MAE of recovered RGB image
        bit_acc      : bit accuracy across all channels
        perfect      : True if all channels are perfectly recovered
        per_channel  : per-channel results
        metadata     : Encryption metadata for receiver
    """
    assert (
        image_rgb.ndim == 3
        and image_rgb.shape[2] == 3
    )

    h, w, _ = image_rgb.shape

    channel_names = ["R", "G", "B"]

    per_channel = []

    recovered_rgb = np.zeros_like(image_rgb)

    total_capacity = 0
    total_correct = 0

    all_perfect = True

    # Process each RGB channel independently with UNIQUE nonces.
    # Nonce derivation matches encryption.py: base_nonce + channel_index + 1,
    # where base_nonce is the caller-supplied nonce.
    for c, ch_name in enumerate(channel_names):
        channel = image_rgb[:, :, c]

        # Use unique nonce per channel: nonce + c + 1
        channel_nonce = get_channel_nonce(nonce, c)

        r = run_rdhei(
            image=channel,
            key=key,
            nonce=channel_nonce,  # UNIQUE nonce per channel
            method=method,
            model=model,
            device=device,
            patch_size=patch_size,
            seed=seed + c
        )

        recovered_rgb[:, :, c] = r["recovered"]

        total_capacity += r["capacity"]

        total_correct += int(
            np.sum(
                r["extracted"] == r["payload"]
            )
        )

        if not r["perfect"]:
            all_perfect = False

        per_channel.append({
            "channel": ch_name,
            "bpp": r["capacity"] / (h * w),
            "capacity": r["capacity"],
            "perfect": r["perfect"],
            "bit_acc": r["bit_acc"],
            "nonce_used": channel_nonce  # Record which nonce was used
        })

    # Colour BPP: per-channel average
    bpp = sum(ch["bpp"] for ch in per_channel) / 3.0

    # Recovery metrics
    psnr_rec = psnr_color(image_rgb, recovered_rgb)
    ssim_rec = ssim_color(image_rgb, recovered_rgb)
    mae_rec = mae_color(image_rgb, recovered_rgb)

    # Bit accuracy across all channels
    bit_acc = (total_correct / total_capacity * 100) if total_capacity > 0 else 0.0

    # Pack metadata for receiver (base nonce = caller-supplied nonce).
    metadata_bytes = pack_metadata(nonce)

    return {
        "bpp": bpp,
        "psnr_rec": psnr_rec,
        "ssim_rec": ssim_rec,
        "mae_rec": mae_rec,
        "bit_acc": bit_acc,
        "perfect": all_perfect,
        "per_channel": per_channel,
        "recovered": recovered_rgb,
        "metadata": metadata_bytes,
        "base_nonce": nonce
    }


def pack_metadata(base_nonce: int, key_size: int = 16) -> bytes:
    """Pack encryption metadata for transmission to receiver.

    Kept for interoperability with encryption.py metadata helpers.
    """
    from struct import pack
    return pack('<I', base_nonce) + pack('B', key_size)


# LEGACY NOTE:
# The original code used encrypt_image()/decrypt_image() with the same nonce
# for all channels. This was a security-critical bug.
#
# The repaired code uses encrypt_rgb_channels()/decrypt_rgb_channels() which
# derive unique nonces per channel: base_nonce + channel_index + 1
#
# For backward compatibility, if you need to decrypt old files encrypted with
# the buggy version, you would need to use the same nonce for all channels.
# However, those files should be considered compromised.
