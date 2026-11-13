import numpy as np
from typing import Tuple, Optional


# ── MED ───────────────────────────────────────────────────────────────────

def _med(A, B, C):
    if C >= max(A, B): return min(A, B)
    elif C <= min(A, B): return max(A, B)
    return A + B - C

def _med_pred(buf, y, x):
    if y == 0 and x == 0: return -1          # skip sentinel
    elif y == 0:           return int(buf[y, x-1])
    elif x == 0:           return int(buf[y-1, x])
    return _med(int(buf[y, x-1]), int(buf[y-1, x]), int(buf[y-1, x-1]))


# ── public helpers ────────────────────────────────────────────────────────

def compute_errors(image, pred):
    return image.astype(np.int32) - np.round(pred).astype(np.int32)

def select_safe_pixels(errors, threshold):
    return np.abs(errors) <= threshold


# ── EMBED ─────────────────────────────────────────────────────────────────

def embed(image: np.ndarray,
          pred,                   # None → MED;  float32 map → CNN fixed map
          payload: np.ndarray,
          threshold: int = 3,
          method: str = "med",
          model=None,
          device: str = "cpu") -> Tuple[np.ndarray, dict]:
    """
    Causal-scan PEE embedding.

    MED: prediction = _med_pred(stego_buffer, y, x)   [causal, from modified buf]
    CNN: prediction = round(pred[y, x])                [fixed map, same at extract]
    """
    h, w    = image.shape
    buf     = image.astype(np.int32).copy()
    bit_idx = 0

    use_cnn = (method == "cnn" and pred is not None)
    if use_cnn:
        pred_int = np.round(pred).astype(np.int32)

    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                continue

            p = int(np.clip(pred_int[y, x], 0, 255)) if use_cnn else _med_pred(buf, y, x)
            e = int(buf[y, x]) - p

            if abs(e) <= threshold:
                b = int(payload[bit_idx]) if bit_idx < len(payload) else 0
                if bit_idx < len(payload):
                    bit_idx += 1
                buf[y, x] = int(np.clip(p + 2*e + b, 0, 255))
            else:
                shift = (threshold+1) if e > threshold else -(threshold+1)
                buf[y, x] = int(np.clip(buf[y, x] + shift, 0, 255))

    return buf.astype(np.uint8), {"threshold": threshold, "capacity": bit_idx}


# ── EXTRACT + RECOVER ─────────────────────────────────────────────────────

def extract_and_recover(stego: np.ndarray,
                        pred,           # None → MED;  same fixed map as embed → CNN
                        payload_len: int,
                        threshold: int = 3,
                        method: str = "med",
                        model=None,
                        device: str = "cpu") -> Tuple[np.ndarray, np.ndarray]:
    """
    Causal-scan PEE extraction.

    MED: reads from stego array for predictions (mirrors embed).
    CNN: uses the same fixed pred_map passed at embed time.
    """
    h, w = stego.shape
    si   = stego.astype(np.int32)           # read-only stego
    rec  = stego.astype(np.int32).copy()
    bits = []

    use_cnn = (method == "cnn" and pred is not None)
    if use_cnn:
        pred_int = np.round(pred).astype(np.int32)

    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                continue

            p  = int(np.clip(pred_int[y, x], 0, 255)) if use_cnn else _med_pred(si, y, x)
            ep = int(si[y, x]) - p

            if abs(ep) <= 2*threshold + 1:
                b      = ep % 2
                e_orig = ep >> 1
                rec[y, x] = int(np.clip(p + e_orig, 0, 255))
                if len(bits) < payload_len:
                    bits.append(b)
            else:
                delta = -(threshold+1) if ep > 2*threshold+1 else (threshold+1)
                rec[y, x] = int(np.clip(si[y, x] + delta, 0, 255))

    return np.array(bits[:payload_len], dtype=np.uint8), rec.astype(np.uint8)


# ── bit utilities ─────────────────────────────────────────────────────────

def bytes_to_bits(data):
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return np.array(bits, dtype=np.uint8)

def bits_to_bytes(bits):
    n = len(bits) // 8
    out = bytearray()
    for i in range(n):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | int(bits[i*8+j])
        out.append(byte)
    return bytes(out)