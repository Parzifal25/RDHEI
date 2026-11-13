"""Option 3 — inference/embedding implementation improvements (no semantic change).

Two drop-in equivalents of authoritative code paths:

1. `fast_cnn_predict_map` — identical CNN inference as
   `src/predictor.cnn_predict_map`, but patch extraction is vectorized with
   numpy sliding windows instead of a Python double loop over pixels.
   The math is unchanged: same reflect padding, same [0,1] normalization,
   same center masking (center set to 0.0), same batch size and batch
   traversal order, same model, same dtype (float32). The model forward pass
   is executed with the exact same tensors in the exact same order, so the
   output must be numerically identical (verified in phase_c_improvement.py).

2. `sender_embed_encrypt_fast` / `receiver_extract_recover_fast` —
   vectorized equivalents of sender_embed_encrypt() and
   receiver_extract_recover() in src/rdhei_core.py:
     - embedding: payload bits are placed into the top n MSBs of each pixel
       with n>0 in raster order, exactly as the per-pixel loop does
       (including zero-padding beyond payload_len);
     - extraction: the first payload_len bits are read MSB-first from pixels
       with n>0 in raster order;
     - recovery: for each pixel with n>0 the unique candidate c with
       min_e <= |c - pred| <= max_e among the 2^n upper-bit combinations is
       found. The vectorized version enumerates ALL 2^n candidates per pixel
       as a candidate matrix (n <= 7 so 128 candidates max), applies the
       same validity mask, takes the first valid candidate in the same
       combo=0..2^n-1 order as _recover_pixel(), and falls back to the
       stego value when no candidate is valid — identical semantics.

These functions live only in this analysis directory; the authoritative
src/ tree is NOT modified. Equivalence (bit-identical outputs) is verified
experimentally before use, and recovery exactness is re-validated on real
benchmark images.
"""
from __future__ import annotations

import numpy as np
import torch


def fast_cnn_predict_map(image, model, device="cpu", patch_size=None, batch_size=2048):
    """Vectorized equivalent of src/predictor.cnn_predict_map (see docstring)."""
    if patch_size is None:
        patch_size = getattr(model, "patch_size", None)
        if patch_size is None:
            raise ValueError("patch_size missing")
    patch_size = int(patch_size)
    if patch_size not in [3, 5, 7]:
        raise ValueError(f"patch_size must be 3/5/7, got {patch_size}")

    HALF = patch_size // 2
    h, w = image.shape

    padded = np.pad(image.astype(np.float32) / 255.0, HALF, mode="reflect")

    # sliding windows of shape (h, w, ps, ps); copy to contiguous memory
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(padded, (patch_size, patch_size))  # (h, w, ps, ps)
    patches = np.ascontiguousarray(win).reshape(h * w, patch_size * patch_size)
    # mask centre pixel (same value in every patch)
    patches[:, HALF * patch_size + HALF] = 0.0
    patches = patches.reshape(h * w, 1, patch_size, patch_size).astype(np.float32)

    preds = np.zeros(h * w, dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, h * w, batch_size):
            end = min(start + batch_size, h * w)
            batch = torch.from_numpy(patches[start:end]).to(device)
            output = model(batch)
            preds[start:end] = output.squeeze(1).cpu().numpy()
    return preds.reshape(h, w)


# ---------------------------------------------------------------------------
# Vectorized embedding / extraction / recovery
# ---------------------------------------------------------------------------

def _flat_bits_from_payload(payload: np.ndarray, total_replaceable: int) -> np.ndarray:
    """Payload bits zero-padded to total_replaceable bits (sender convention)."""
    out = np.zeros(total_replaceable, dtype=np.uint8)
    n = min(len(payload), total_replaceable)
    out[:n] = payload[:n].astype(np.uint8)
    return out


def embed_msb_vectorized(image: np.ndarray, bpp_map: np.ndarray, payload: np.ndarray) -> np.ndarray:
    """Vectorized equivalent of the per-pixel loop in sender_embed_encrypt()
    (MSB replacement only; encryption is applied afterwards by the caller).

    Raster order, n>0 pixels consume payload bits MSB-first, remaining
    replaceable bits are zero-padded — identical to the original loop.
    """
    h, w = image.shape
    stego = image.astype(np.int32).copy()
    n_flat = bpp_map.flatten()
    pix_flat = stego.flatten()

    idx = np.flatnonzero(n_flat)          # pixels with n > 0, raster order
    if idx.size == 0:
        return stego.astype(np.uint8)

    ns = n_flat[idx].astype(np.int64)
    # positions of every replaceable bit in raster order
    offsets = np.zeros(idx.size + 1, dtype=np.int64)
    np.cumsum(ns, out=offsets[1:])
    total = int(offsets[-1])

    bits = _flat_bits_from_payload(payload, total)

    # per bit: pixel index (repeated) and bit rank j within that pixel
    pix_per_bit = np.repeat(np.arange(idx.size), ns)
    j = np.arange(total) - np.repeat(offsets[:-1], ns)
    bitvals = bits.astype(np.int32)

    # per pixel: keep low (8-n) bits, OR in payload bits at positions (7-j)
    vals = pix_flat[idx].astype(np.int64)              # (P,)
    lower_mask = (1 << (8 - ns)) - 1                   # (P,)
    lower = vals & lower_mask
    upper = np.zeros(idx.size, dtype=np.int64)          # (P,)
    np.add.at(upper, pix_per_bit, bitvals << (7 - j))   # distinct positions -> add == OR
    newpix = pix_flat.copy()
    newpix[idx] = lower | upper
    return newpix.reshape(h, w).astype(np.uint8)


def recover_vectorized(stego_plain: np.ndarray, pred_int: np.ndarray,
                       bpp_map: np.ndarray, min_e_map: np.ndarray,
                       max_e_map: np.ndarray, payload_len: int) -> dict:
    """Vectorized equivalent of receiver_extract_recover()'s extract+recover
    (decryption is applied by the caller before this).

    Candidate enumeration order matches _recover_pixel(): combo = 0..2^n-1,
    first valid candidate wins; fallback = stego value.
    """
    h, w = stego_plain.shape
    sv_flat = stego_plain.astype(np.int32).flatten()
    n_flat = bpp_map.flatten().astype(np.int64)
    pred_flat = pred_int.flatten().astype(np.int64)
    min_flat = min_e_map.flatten().astype(np.int64)
    max_flat = max_e_map.flatten().astype(np.int64)

    recovered = sv_flat.copy()
    idx = np.flatnonzero(n_flat)
    if idx.size == 0:
        return {
            "extracted": np.zeros(0, dtype=np.uint8),
            "recovered": recovered.reshape(h, w).astype(np.uint8),
        }

    ns = n_flat[idx]
    offsets = np.zeros(idx.size + 1, dtype=np.int64)
    np.cumsum(ns, out=offsets[1:])
    total = int(offsets[-1])

    # ---- extraction: MSB-first from each pixel's top n bits, raster order
    bits = np.zeros(total, dtype=np.int64)
    pix_per_bit = np.repeat(np.arange(idx.size), ns)
    j = np.arange(total) - np.repeat(offsets[:-1], ns)
    vals_arr = sv_flat[idx]
    bits = (vals_arr[pix_per_bit] >> (7 - j)) & 1
    extracted = bits[:min(int(payload_len), total)].astype(np.uint8)

    # ---- recovery: enumerate 2^n candidates per pixel (n <= 7)
    maxn = int(ns.max())
    K = 1 << maxn                      # <= 128
    lower_mask = ((1 << (8 - ns)) - 1)          # per-pixel
    lower = vals_arr & lower_mask
    combo = np.arange(K, dtype=np.int64)        # (K,)
    # candidate c for pixel p, combo k: (k << (8-n_p)) | lower_p, only valid for k < 2^n_p
    shift = (8 - ns)                            # (P,)
    cand = (combo[None, :] << shift[:, None]) | lower[:, None]   # (P, K)
    valid_k = combo[None, :] < (1 << ns)[:, None]               # (P, K)
    in_range = (cand >= 0) & (cand <= 255)
    p = pred_flat[idx][:, None]
    d = np.abs(cand - p)
    ok = valid_k & in_range & (d >= min_flat[idx][:, None]) & (d <= max_flat[idx][:, None])
    has = ok.any(axis=1)
    # first valid combo (same order as the per-pixel loop)
    first = np.argmax(ok, axis=1)
    rec_vals = np.where(has, cand[np.arange(idx.size), first], vals_arr)
    recovered[idx] = rec_vals

    return {
        "extracted": extracted,
        "recovered": recovered.reshape(h, w).astype(np.uint8),
    }
