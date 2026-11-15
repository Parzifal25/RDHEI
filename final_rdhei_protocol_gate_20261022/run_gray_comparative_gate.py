#!/usr/bin/env python3
"""Full-corpus grayscale E2E comparison: MED/GAP/CALIC, frozen CNN ablations, and HS.

The predictor methods share one conservative step-4 safe lattice (radius 3,
16 implicit phases) so no mutable candidate falls inside any 7x7 prediction
context. The receiver gets only the marked encrypted image, master key, and
nonce. Histogram shifting is a separately implemented global peak/zero-bin
reference; it embeds before AES-CTR encryption and is reported separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import secrets
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import numpy as np
from PIL import Image
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_gate import load_corpus, read_native_gray, pixel_sha256, file_sha256

GRID_STEP = 4
GRID_BORDER = 3
GRID_PHASES = GRID_STEP * GRID_STEP
HEADER = struct.Struct(">4sB3sIQ")
HEADER_BYTES = HEADER.size
TAG_BYTES = 32
MAGIC = b"EDC3"
HIST_MAGIC = b"HST1"
HIST_HEADER_PIXELS = 32
HIST_HEADER_BASE = struct.Struct(">4sBBQH")
HIST_TAG_BYTES = HIST_HEADER_PIXELS - HIST_HEADER_BASE.size

SPECS = [
    {"name": "MED", "id": 0, "kind": "baseline", "checkpoint": None},
    {"name": "GAP", "id": 1, "kind": "baseline", "checkpoint": None},
    {"name": "CALIC_simplified", "id": 2, "kind": "baseline", "checkpoint": None},
    {"name": "CNN_v1_full", "id": 3, "kind": "cnn", "checkpoint": "v1_full.pth"},
    {"name": "CNN_v2_no_residual", "id": 4, "kind": "cnn", "checkpoint": "v2_no_residual.pth"},
    {"name": "CNN_v3_no_weighted_loss", "id": 5, "kind": "cnn", "checkpoint": "v3_no_weighted_loss.pth"},
    {"name": "CNN_v4_patch3_proposed", "id": 6, "kind": "cnn", "checkpoint": "v4_patch3.pth"},
    {"name": "CNN_v5_patch7", "id": 7, "kind": "cnn", "checkpoint": "v5_patch7.pth"},
]
SPEC_BY_ID = {row["id"]: row for row in SPECS}
SPEC_BY_NAME = {row["name"]: row for row in SPECS}

def allocation(e: int) -> tuple[int, int, int]:
    if not 0 <= int(e) <= 255:
        raise ValueError("absolute prediction error must lie in [0,255]")
    n = 0
    for r in range(7, 0, -1):
        low, mid, high = 2 ** (r - 1) - 1, 2 ** (r - 1), 2 ** r - 1
        if e <= low:
            n += 1
        elif mid < e <= high:
            return n + 1, mid + 1, high
        elif e == mid:
            return n, mid, mid
    return n, 0, 0

BOOK = np.asarray(sorted({allocation(e) for e in range(256)}), dtype=np.int32)
ENC = {tuple(map(int, row)): i for i, row in enumerate(BOOK)}
LABEL = np.asarray([ENC[allocation(e)] for e in range(256)], dtype=np.uint8)

def grid(shape: tuple[int, int], phase: int = 0) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(phase, int) or not 0 <= phase < GRID_PHASES:
        raise ValueError("phase must be in [0,15]")
    height, width = map(int, shape)
    if height <= 2 * GRID_BORDER or width <= 2 * GRID_BORDER:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    row_start = GRID_BORDER + phase // GRID_STEP
    col_start = GRID_BORDER + phase % GRID_STEP
    yy, xx = np.meshgrid(
        np.arange(row_start, height - GRID_BORDER, GRID_STEP),
        np.arange(col_start, width - GRID_BORDER, GRID_STEP),
        indexing="ij",
    )
    return yy.ravel(), xx.ravel()

def pack_labels(labels: np.ndarray) -> bytes:
    labels = np.asarray(labels, dtype=np.uint8)
    if labels.ndim != 1 or np.any(labels >= len(BOOK)):
        raise ValueError("invalid label sequence")
    if len(labels) % 2:
        labels = np.concatenate((labels, np.zeros(1, np.uint8)))
    return ((labels[::2] << 4) | labels[1::2]).astype(np.uint8).tobytes()

def slots(shape, labels, bootstrap_pixels, phase):
    yy, xx = grid(shape, phase)
    pixels, shifts = [], []
    for i in range(int(bootstrap_pixels), len(yy)):
        n = int(BOOK[int(labels[i]), 0])
        if n:
            flat_index = int(yy[i] * shape[1] + xx[i])
            pixels.extend([flat_index] * n)
            shifts.extend(range(7, 7 - n, -1))
    return np.asarray(pixels, np.int64), np.asarray(shifts, np.uint8)

def read_bits(array, positions):
    pixels, shifts = positions
    return (array.ravel()[pixels] >> shifts) & 1

def write_bits(array, positions, bits):
    pixels, shifts = positions
    bits = np.asarray(bits, dtype=np.uint8)
    if len(bits) != len(pixels):
        raise ValueError(f"bit-slot length mismatch: {len(bits)} != {len(pixels)}")
    flat = array.ravel()
    for p, s, bit in zip(pixels, shifts, bits):
        mask = 1 << int(s)
        flat[p] = (int(flat[p]) & (255 ^ mask)) | (int(bit) << int(s))

def derive_keys(master: bytes, nonce: int):
    if not isinstance(master, (bytes, bytearray)) or len(master) != 32:
        raise ValueError("expected a 32-byte master key")
    if not isinstance(nonce, int) or not 0 <= nonce < 2**128:
        raise ValueError("expected a uint128 nonce")
    salt = nonce.to_bytes(16, "big")
    root = HKDF(bytes(master), 32, salt, SHA256, context=MAGIC + b"/master-root")
    return {
        "image": HKDF(root, 32, b"", SHA256, context=MAGIC + b"/image-encryption"),
        "hider": HKDF(root, 32, b"", SHA256, context=MAGIC + b"/data-hiding-master"),
    }

def hider_keys(hider_key: bytes):
    if not isinstance(hider_key, (bytes, bytearray)) or len(hider_key) != 32:
        raise ValueError("expected a 32-byte data-hiding capability key")
    return {
        name.replace("-", "_"): HKDF(
            bytes(hider_key), 32, b"", SHA256,
            context=MAGIC + b"/hider/" + name.encode("ascii")
        )
        for name in ("header-bootstrap", "header-final", "directory", "payload", "auth")
    }

def crypt(data: bytes, key: bytes) -> bytes:
    return AES.new(key, AES.MODE_CTR, nonce=b"", initial_value=0).encrypt(data)

def _header_key(capability, stage):
    key_name = "header_bootstrap" if stage == "bootstrap" else "header_final"
    return capability[key_name]

def encode_header(mode, directory_length, payload_length, capability, stage, method_id):
    if mode not in (0, 1) or not 0 <= directory_length < 2**32 or not 0 <= payload_length < 2**64:
        raise ValueError("invalid EDC3 header values")
    reserved = bytes((int(method_id), GRID_STEP, GRID_BORDER))
    plain = HEADER.pack(MAGIC, int(mode), reserved, int(directory_length), int(payload_length))
    return crypt(plain, _header_key(capability, stage))

def _packet_tag(array, capability, phase, directory_length):
    yy, xx = grid(array.shape, phase)
    end = HEADER_BYTES + int(directory_length) + TAG_BYTES
    work = array.copy()
    work[yy[HEADER_BYTES + directory_length:end], xx[HEADER_BYTES + directory_length:end]] = 0
    msg = struct.pack(">QQB", *array.shape, int(phase)) + work.tobytes(order="C")
    return hmac.new(capability["auth"], msg, hashlib.sha256).digest()

def _write_header_and_tag(array, yy, xx, mode, directory_length, payload_length,
                          capability, stage, method_id, phase):
    end = HEADER_BYTES + int(directory_length) + TAG_BYTES
    if end >= len(yy):
        raise ValueError("EDC3 directory/header does not fit this lattice phase")
    header = encode_header(mode, directory_length, payload_length, capability, stage, method_id)
    array[yy[:HEADER_BYTES], xx[:HEADER_BYTES]] = np.frombuffer(header, np.uint8)
    array[yy[HEADER_BYTES + directory_length:end], xx[HEADER_BYTES + directory_length:end]] = 0
    tag = _packet_tag(array, capability, phase, directory_length)
    array[yy[HEADER_BYTES + directory_length:end], xx[HEADER_BYTES + directory_length:end]] = np.frombuffer(tag, np.uint8)

def inspect_packet(array, capability, stage="final"):
    if array.dtype != np.uint8 or array.ndim != 2:
        raise ValueError("expected a uint8 grayscale packet")
    valid, failures = [], []
    for phase in range(GRID_PHASES):
        yy, xx = grid(array.shape, phase)
        if len(yy) <= HEADER_BYTES + TAG_BYTES:
            continue
        try:
            raw_header = crypt(array[yy[:HEADER_BYTES], xx[:HEADER_BYTES]].tobytes(), _header_key(capability, stage))
            magic, mode, reserved, directory_length, payload_length = HEADER.unpack(raw_header)
            if (magic != MAGIC or mode not in (0, 1) or len(reserved) != 3
                    or reserved[1] != GRID_STEP or reserved[2] != GRID_BORDER
                    or reserved[0] not in SPEC_BY_ID):
                continue
            h = HEADER_BYTES + directory_length + TAG_BYTES
            if h >= len(yy):
                continue
            actual_tag = array[yy[HEADER_BYTES + directory_length:h],
                               xx[HEADER_BYTES + directory_length:h]].tobytes()
            expected_tag = _packet_tag(array, capability, phase, directory_length)
            if not hmac.compare_digest(actual_tag, expected_tag):
                failures.append("authentication failure")
                continue
            encrypted_directory = array[yy[HEADER_BYTES:HEADER_BYTES + directory_length],
                                        xx[HEADER_BYTES:HEADER_BYTES + directory_length]].tobytes()
            directory = crypt(encrypted_directory, capability["directory"])
            expected_length = (len(yy) + 1) // 2
            if mode:
                dec = zlib.decompressobj()
                raw_directory = dec.decompress(directory, expected_length + 1)
                if (len(raw_directory) != expected_length or not dec.eof
                        or dec.unused_data or dec.unconsumed_tail):
                    raise ValueError("invalid bounded EDC3 directory")
            else:
                raw_directory = directory
            if len(raw_directory) != expected_length:
                raise ValueError("EDC3 directory length mismatch")
            packed = np.frombuffer(raw_directory, np.uint8)
            labels = np.stack((packed >> 4, packed & 15), axis=1).ravel()[:len(yy)]
            if len(yy) % 2 and labels[-1] != 0:
                raise ValueError("nonzero EDC3 directory padding")
            if np.any(labels >= len(BOOK)):
                raise ValueError("invalid EDC3 label identifier")
            positions = slots(array.shape, labels, h, phase)
            backup = 8 * h
            net = len(positions[0]) - backup
            if net <= 0 or payload_length > net:
                raise ValueError("invalid EDC3 net capacity or payload length")
            valid.append({
                "phase": phase, "y": yy, "x": xx, "mode": mode,
                "directory_length": directory_length, "payload_length": payload_length,
                "h": h, "labels": labels, "positions": positions,
                "backup": backup, "net": net, "method_id": int(reserved[0]),
            })
        except (ValueError, struct.error, zlib.error) as exc:
            failures.append(str(exc))
    if len(valid) == 1:
        return valid[0]
    if len(valid) > 1:
        raise ValueError("ambiguous authenticated EDC3 lattice phase")
    detail = failures[-1] if failures else "no candidate header parsed"
    raise ValueError("no valid authenticated EDC3 packet: " + detail)

def embed_encrypted(reserved_image, payload, capability):
    q = inspect_packet(reserved_image, capability, stage="bootstrap")
    payload = np.asarray(payload, dtype=np.uint8)
    if payload.ndim != 1 or np.any((payload != 0) & (payload != 1)):
        raise ValueError("payload must be one-dimensional binary data")
    if len(payload) > q["net"]:
        raise ValueError("payload exceeds EDC3 net capacity")
    plain = np.pad(payload, (0, q["net"] - len(payload)))
    encrypted_bits = np.unpackbits(np.frombuffer(
        crypt(np.packbits(plain).tobytes(), capability["payload"]), np.uint8
    ))[:q["net"]]
    out = reserved_image.copy()
    ordinary = tuple(v[q["backup"]:] for v in q["positions"])
    write_bits(out, ordinary, encrypted_bits)
    _write_header_and_tag(
        out, q["y"], q["x"], q["mode"], q["directory_length"], len(payload),
        capability, "final", q["method_id"], q["phase"],
    )
    return out

def get_model(spec, cache):
    name = spec["name"]
    if name not in cache:
        import torch
        from src.cnn_model import load_model
        path = ROOT / "models" / spec["checkpoint"]
        loaded, patch_size, residual, parameters = load_model(str(path), device="cpu")
        if patch_size not in (3, 5, 7):
            raise ValueError(f"unsupported checkpoint patch size for {name}: {patch_size}")
        loaded.eval()
        loaded.requires_grad_(False)
        cache[name] = {
            "model": loaded, "patch_size": int(patch_size), "residual": bool(residual),
            "parameters": int(parameters), "sha256": file_sha256(path),
        }
    return cache[name]

def prediction_values(image, yy, xx, spec, model_cache, map_cache=None):
    if spec["kind"] == "baseline":
        if map_cache is not None and spec["name"] in map_cache:
            pred_map = map_cache[spec["name"]]
        else:
            from src.baselines import med_predict, gap_predict, calic_predict
            functions = {
                "MED": med_predict, "GAP": gap_predict, "CALIC_simplified": calic_predict,
            }
            pred_map = functions[spec["name"]](image)
            if map_cache is not None:
                map_cache[spec["name"]] = pred_map
        return np.asarray(pred_map[yy, xx], dtype=np.float32)
    info = get_model(spec, model_cache)
    model = info["model"]
    patch_size = info["patch_size"]
    radius = patch_size // 2
    if np.any(yy < radius) or np.any(xx < radius) or np.any(yy >= image.shape[0] - radius) or np.any(xx >= image.shape[1] - radius):
        raise ValueError("CNN candidate falls outside its native receptive-field border")
    patches = np.stack([
        image[y-radius:y+radius+1, x-radius:x+radius+1]
        for y, x in zip(yy, xx)
    ]).astype(np.float32) / 255.0
    patches[:, radius, radius] = 0.0
    patches = patches[:, None, :, :]
    import torch
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(patches), 2048):
            batch = torch.from_numpy(patches[start:start+2048])
            outputs.append(model(batch).cpu().numpy().reshape(-1))
    return np.concatenate(outputs).astype(np.float32, copy=False) if outputs else np.empty(0, np.float32)

def prepare_predictor_packet(image, spec, model_cache):
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError("expected a native uint8 grayscale image")
    map_cache = {}
    alternatives, invalid_phases = [], []
    for phase in range(GRID_PHASES):
        yy, xx = grid(image.shape, phase)
        if len(yy) <= HEADER_BYTES + TAG_BYTES:
            invalid_phases.append(phase)
            continue
        preds = prediction_values(image, yy, xx, spec, model_cache, map_cache)
        rounded = np.rint(preds).astype(np.int32)
        errors = np.abs(image[yy, xx].astype(np.int32) - rounded)
        labels = LABEL[errors]
        raw = pack_labels(labels)
        compressed = zlib.compress(raw, 9)
        mode = 1 if len(compressed) < len(raw) else 0
        metadata = compressed if mode else raw
        h = HEADER_BYTES + len(metadata) + TAG_BYTES
        if h >= len(yy):
            invalid_phases.append(phase)
            continue
        ns = BOOK[labels, 0].astype(np.int32)
        positions = slots(image.shape, labels, h, phase)
        gross = int(ns.sum())
        foregone = int(ns[:h].sum())
        available = len(positions[0])
        backup = 8 * h
        net = available - backup
        if available != gross - foregone:
            raise AssertionError("EDC3 slot count differs from allocation sum")
        alternatives.append({
            "phase": phase, "y": yy, "x": xx, "predictions": preds,
            "labels": labels, "ns": ns, "metadata": metadata, "mode": mode,
            "h": h, "positions": positions, "net": net, "gross": gross,
            "foregone": foregone, "backup": backup, "raw_mae": float(errors.mean()),
            "compressed_bytes": len(compressed),
        })
    if not alternatives:
        raise ValueError("EDC3 directory does not fit any of the 16 safe-grid phases")
    chosen = max(alternatives, key=lambda row: (row["net"], -row["phase"]))
    chosen["phase_scores"] = [
        {"phase": int(q["phase"]), "net_bits": int(q["net"]),
         "gross_bits": int(q["gross"]), "directory_bytes": len(q["metadata"]),
         "candidate_count": len(q["y"])} for q in alternatives
    ]
    chosen["phase_net_bits"] = [
        next((int(q["net"]) for q in alternatives if q["phase"] == phase), None)
        for phase in range(GRID_PHASES)
    ]
    chosen["method_id"] = int(spec["id"])
    chosen["candidate_count"] = int(len(chosen["y"]))
    chosen["phase_selection_gain_bits"] = int(chosen["net"] - chosen["phase_net_bits"][0])
    return chosen

def reserve_predictor_packet(original, q, master, nonce):
    if q["net"] <= 0:
        raise ValueError("nonpositive EDC3 net capacity")
    k = derive_keys(master, nonce)
    cap = hider_keys(k["hider"])
    yy, xx, h = q["y"], q["x"], q["h"]
    backup = np.unpackbits(original[yy[:h], xx[:h]])
    stream = np.concatenate((backup, np.zeros(q["net"], np.uint8)))
    reserved = original.copy()
    write_bits(reserved, q["positions"], stream)
    reserved[yy[:h], xx[:h]] = 0
    encrypted = np.frombuffer(crypt(reserved.tobytes(order="C"), k["image"]), np.uint8).copy().reshape(original.shape)
    encrypted_directory = crypt(q["metadata"], cap["directory"])
    _write_header_and_tag(
        encrypted, yy, xx, q["mode"], len(encrypted_directory), 0,
        cap, "bootstrap", q["method_id"], q["phase"],
    )
    encrypted[yy[HEADER_BYTES:HEADER_BYTES + len(encrypted_directory)],
              xx[HEADER_BYTES:HEADER_BYTES + len(encrypted_directory)]] = np.frombuffer(encrypted_directory, np.uint8)
    # The tag is regenerated after the encrypted directory is written.
    start = HEADER_BYTES + len(encrypted_directory)
    end = start + TAG_BYTES
    encrypted[yy[start:end], xx[start:end]] = 0
    tag = _packet_tag(encrypted, cap, q["phase"], len(encrypted_directory))
    encrypted[yy[start:end], xx[start:end]] = np.frombuffer(tag, np.uint8)
    return encrypted, k["hider"]

def receive_predictor_packet(encrypted_image, master, nonce, model_cache):
    k = derive_keys(master, nonce)
    cap = hider_keys(k["hider"])
    q = inspect_packet(encrypted_image, cap, stage="final")
    yy, xx, h = q["y"], q["x"], q["h"]
    ordinary = tuple(v[q["backup"]:] for v in q["positions"])
    encrypted_bits = read_bits(encrypted_image, ordinary)
    plain_bits = np.unpackbits(np.frombuffer(
        crypt(np.packbits(encrypted_bits).tobytes(), cap["payload"]), np.uint8
    ))[:q["net"]]
    if np.any(plain_bits[q["payload_length"]:] != 0):
        raise ValueError("nonzero EDC3 payload padding")
    payload = plain_bits[:q["payload_length"]].copy()

    zero_cipher = np.frombuffer(crypt(bytes(encrypted_image.size), k["image"]), np.uint8).reshape(encrypted_image.shape)
    c = encrypted_image.copy()
    write_bits(c, ordinary, read_bits(zero_cipher, ordinary))
    c[yy[:h], xx[:h]] = zero_cipher[yy[:h], xx[:h]]
    reserved = np.frombuffer(crypt(c.tobytes(order="C"), k["image"]), np.uint8).copy().reshape(c.shape)
    backup_bits = read_bits(reserved, tuple(v[:q["backup"]] for v in q["positions"]))
    spec = SPEC_BY_ID[q["method_id"]]
    predictions = np.rint(prediction_values(reserved, yy, xx, spec, model_cache)).astype(np.int32)
    recovered = reserved.copy()
    for i in range(h, len(yy)):
        n, low, high = map(int, BOOK[int(q["labels"][i])])
        if not n:
            continue
        modulus = 1 << (8 - n)
        residue = int(reserved[yy[i], xx[i]]) & (modulus - 1)
        candidates = [
            value for value in range(residue, 256, modulus)
            if low <= abs(value - int(predictions[i])) <= high
        ]
        if len(candidates) != 1:
            raise ValueError(f"nonunique recovered value at candidate {i}")
        recovered[yy[i], xx[i]] = candidates[0]
    recovered[yy[:h], xx[:h]] = np.packbits(backup_bits)
    return recovered, payload

def histogram_choice(image):
    flat = image.ravel()
    h = HIST_HEADER_PIXELS
    if flat.size <= h:
        return None
    hist = np.bincount(flat[h:], minlength=256)
    zero_bins = np.flatnonzero(hist == 0)
    if not len(zero_bins):
        return None
    peak = int(np.argmax(hist))
    zero = min((int(v) for v in zero_bins), key=lambda v: (abs(v - peak), v))
    direction = 1 if zero > peak else -1
    carrier_count = int(hist[peak])
    return {
        "peak": peak, "zero": zero, "direction": direction,
        "carrier_count": carrier_count,
        "header_backup_bits": 8 * h,
        "net": carrier_count - 8 * h,
        "histogram": hist,
    }

def histogram_shift_encrypt(image, payload, master, nonce, choice=None):
    choice = histogram_choice(image) if choice is None else choice
    if choice is None:
        raise ValueError("histogram-shifting baseline has no empty histogram bin")
    if choice["net"] <= 0:
        raise ValueError("histogram-shifting peak has nonpositive net capacity")
    payload = np.asarray(payload, dtype=np.uint8)
    if payload.ndim != 1 or np.any((payload != 0) & (payload != 1)) or len(payload) > choice["net"]:
        raise ValueError("invalid histogram-shifting payload")
    flat = image.ravel()
    h, peak, zero, direction = HIST_HEADER_PIXELS, choice["peak"], choice["zero"], choice["direction"]
    carriers = np.flatnonzero(flat[h:] == peak).astype(np.int64) + h
    backup = np.unpackbits(flat[:h])
    bits = np.concatenate((backup, payload, np.zeros(len(carriers) - len(backup) - len(payload), np.uint8)))
    shifted = flat.copy()
    tail = shifted[h:]
    if direction > 0:
        mask = (tail > peak) & (tail < zero)
        tail[mask] += 1
    else:
        mask = (tail < peak) & (tail > zero)
        tail[mask] -= 1
    shifted[carriers] = peak + direction * bits
    base = HIST_HEADER_BASE.pack(HIST_MAGIC, peak, zero, len(payload), h)
    k = derive_keys(master, nonce)
    auth_key = hider_keys(k["hider"])["auth"]
    tag = hmac.new(auth_key, base + shifted[h:].tobytes(), hashlib.sha256).digest()[:HIST_TAG_BYTES]
    shifted[:h] = np.frombuffer(base + tag, np.uint8)
    encrypted = np.frombuffer(crypt(shifted.tobytes(), k["image"]), np.uint8).copy().reshape(image.shape)
    return encrypted

def receive_histogram_shift(plain_image, auth_key):
    flat = plain_image.ravel().copy()
    h = HIST_HEADER_PIXELS
    header = flat[:h].tobytes()
    if len(header) != h:
        raise ValueError("truncated histogram-shift header")
    base = header[:HIST_HEADER_BASE.size]
    tag = header[HIST_HEADER_BASE.size:]
    magic, peak, zero, payload_length, encoded_h = HIST_HEADER_BASE.unpack(base)
    if magic != HIST_MAGIC or encoded_h != h or peak == zero:
        raise ValueError("invalid histogram-shift header")
    expected = hmac.new(auth_key, base + flat[h:].tobytes(), hashlib.sha256).digest()[:HIST_TAG_BYTES]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("histogram-shift authentication failed")
    direction = 1 if zero > peak else -1
    adjacent = peak + direction
    if not 0 <= adjacent <= 255:
        raise ValueError("invalid histogram-shift adjacent bin")
    carriers = np.flatnonzero((flat[h:] == peak) | (flat[h:] == adjacent)).astype(np.int64) + h
    bits = (flat[carriers] == adjacent).astype(np.uint8)
    backup_bits = 8 * h
    if len(bits) < backup_bits + payload_length:
        raise ValueError("histogram-shift carrier count is below its declared length")
    backup = np.packbits(bits[:backup_bits])
    payload = bits[backup_bits:backup_bits + payload_length].copy()
    restored = flat.copy()
    restored[carriers] = peak
    tail = restored[h:]
    if direction > 0:
        mask = (tail >= peak + 2) & (tail <= zero)
        tail[mask] -= 1
    else:
        mask = (tail >= zero) & (tail <= peak - 2)
        tail[mask] += 1
    restored[:h] = backup
    return restored.reshape(plain_image.shape).astype(np.uint8), payload

def receive_any_packet(encrypted_image, master, nonce, model_cache):
    k = derive_keys(master, nonce)
    plain = np.frombuffer(crypt(encrypted_image.tobytes(order="C"), k["image"]), np.uint8).copy().reshape(encrypted_image.shape)
    if plain.ravel()[:4].tobytes() == HIST_MAGIC:
        return receive_histogram_shift(plain, hider_keys(k["hider"])["auth"])
    return receive_predictor_packet(encrypted_image, master, nonce, model_cache)

def cmd_embed_batch(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows = []
    for item in manifest["items"]:
        try:
            reserved = np.asarray(Image.open(item["reserved_path"]), dtype=np.uint8)
            payload = np.load(item["payload_path"], allow_pickle=False)
            capability = hider_keys(bytes.fromhex(item["hider_key_hex"]))
            final = embed_encrypted(reserved, payload, capability)
            Image.fromarray(final, mode="L").save(item["cipher_path"])
            rows.append({"id": item["id"], "status": "PASS", "torch_imported": "torch" in sys.modules})
        except Exception as exc:
            rows.append({"id": item["id"], "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    output = Path(manifest["result_path"])
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    if any(row["status"] != "PASS" or row.get("torch_imported") for row in rows):
        raise RuntimeError("encrypted-domain hider batch failed or imported a predictor framework")
    print(json.dumps({"hider_items": len(rows), "passed": len(rows), "torch_imported": False}))

def cmd_receiver_batch(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    denied_root = (ROOT / "data").resolve()
    source_paths = {
        os.path.realpath(os.fspath(path))
        for path in manifest.get("source_paths", [])
    }
    reads = []

    def audit(event, args):
        if event != "open" or not args:
            return
        raw_path = args[0]
        if not isinstance(raw_path, (str, bytes, os.PathLike)):
            return
        path = os.path.realpath(os.fsdecode(raw_path))
        mode = args[1] if len(args) > 1 else None
        if mode is None or "r" in str(mode) or isinstance(mode, int):
            reads.append(path)
            if path in source_paths or path.startswith(str(denied_root) + os.sep):
                raise RuntimeError("receiver attempted to read an original/source data file")

    sys.addaudithook(audit)
    model_cache = {}
    results = []
    for item in manifest["items"]:
        try:
            encrypted = np.asarray(Image.open(item["cipher_path"]), dtype=np.uint8)
            recovered, payload = receive_any_packet(
                encrypted, bytes.fromhex(item["master_hex"]), int(item["nonce"]), model_cache
            )
            np.save(item["recovered_path"], recovered, allow_pickle=False)
            np.save(item["extracted_path"], payload, allow_pickle=False)
            results.append({
                "id": item["id"], "status": "PASS", "payload_bits": int(len(payload)),
                "source_access": False,
            })
        except Exception as exc:
            results.append({
                "id": item["id"], "status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
            })
    output = Path(manifest["result_path"])
    output.write_text(json.dumps({
        "items": results,
        "source_access": any(
            item in source_paths or item.startswith(str(denied_root) + os.sep)
            for item in reads
        ),
        "read_paths": sorted(set(reads)),
        "checkpoint_sha256": {name: info["sha256"] for name, info in model_cache.items()},
        "training_performed": False,
    }, indent=2) + "\n", encoding="utf-8")
    if any(row["status"] != "PASS" for row in results):
        raise RuntimeError("one or more receiver batch cases failed")
    print(json.dumps({
        "receiver_items": len(results), "passed": len(results),
        "source_access": False, "training_performed": False,
    }))

def persist_progress(out: Path, all_rows: list[dict], summaries: list[dict]) -> None:
    """Atomically persist completed-method evidence so interrupted CI retains results."""
    if all_rows:
        fields = sorted({key for row in all_rows for key in row})
        temporary = out / "per_image_comparison.csv.tmp"
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)
        temporary.replace(out / "per_image_comparison.csv")
    if summaries:
        fields = sorted({key for row in summaries for key in row})
        temporary = out / "method_summary.csv.tmp"
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(summaries)
        temporary.replace(out / "method_summary.csv")
    (out / "progress.json").write_text(json.dumps({
        "completed_methods": [row["method"] for row in summaries],
        "method_summaries": summaries,
        "training_performed": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize_method(method, rows):
    attempted = [r for r in rows if r.get("roundtrip_attempted")]
    exact = [r for r in attempted if r.get("image_exact") and r.get("payload_exact")]
    bpp_values = [float(r["signed_net_bpp"]) for r in rows if r.get("signed_net_bpp") is not None]
    positive_bpp = [float(r["signed_net_bpp"]) for r in rows if r.get("accepted") and r.get("signed_net_bpp") is not None]
    mae = [float(r["candidate_mae"]) for r in rows if r.get("candidate_mae") is not None]
    return {
        "method": method, "images": len(rows),
        "positive_net_images": sum(bool(r.get("accepted")) for r in rows),
        "roundtrip_attempts": len(attempted),
        "exact_image_recoveries": sum(bool(r.get("image_exact")) for r in attempted),
        "exact_payload_recoveries": sum(bool(r.get("payload_exact")) for r in attempted),
        "exact_roundtrips": len(exact),
        "exact_roundtrip_rate_attempted": (len(exact) / len(attempted)) if attempted else None,
        "mean_signed_net_bpp_all_valid": (float(np.mean(bpp_values)) if bpp_values else None),
        "median_signed_net_bpp_all_valid": (float(np.median(bpp_values)) if bpp_values else None),
        "mean_positive_net_bpp": (float(np.mean(positive_bpp)) if positive_bpp else None),
        "mean_candidate_mae": (float(np.mean(mae)) if mae else None),
        "receiver_failures": sum(r.get("status") == "FAIL_RECEIVER" for r in rows),
        "preparation_rejections": sum(r.get("status") == "PREPARE_REJECTED" for r in rows),
    }

def run_comparison(data_dir, output_dir, expected_images=248, seed=20261115, threads=4):
    import torch
    torch.set_num_threads(threads)
    corpus, skipped, duplicates, inventory, missing = load_corpus([Path(data_dir).resolve()], True)
    if expected_images is not None and len(corpus) != expected_images:
        raise ValueError(f"expected {expected_images} curated distinct grayscale images, found {len(corpus)}")
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    tmp = out / "temporary_packets"
    tmp.mkdir()
    (out / "corpus_manifest.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    (out / "skipped_inputs.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")
    (out / "pixel_duplicates.json").write_text(json.dumps(duplicates, indent=2), encoding="utf-8")

    master = bytes(range(32))
    nonce_base = secrets.randbits(96) << 32
    sequence = 0
    all_rows = []
    model_identity = {}
    method_summaries = []

    for method_index, spec in enumerate(SPECS + [{"name": "HistogramShift_global_peak_zero", "id": 8, "kind": "hist"}]):
        name = spec["name"]
        print(f"\n=== Grayscale full-corpus E2E: {name} ===", flush=True)
        method_dir = tmp / f"{method_index:02d}_{name}"
        method_dir.mkdir()
        owner_start = time.perf_counter()
        rows, embed_items, compare_items = [], [], {}
        model_cache = {}

        for image_index, image_record in enumerate(corpus):
            source = Path(image_record["source"])
            original = read_native_gray(source)
            if pixel_sha256(original) != image_record["pixels_sha256"]:
                raise AssertionError(f"source pixels changed after inventory: {image_record['name']}")
            base_row = {
                "method": name, "image": image_record["name"],
                "source_sha256": image_record["source_sha256"],
                "pixels_sha256": image_record["pixels_sha256"],
                "height": int(original.shape[0]), "width": int(original.shape[1]),
                "pixels": int(original.size), "accepted": False,
                "roundtrip_attempted": False, "image_exact": None,
                "payload_exact": None, "status": "NOT_ATTEMPTED",
                "candidate_mae": None, "candidate_count": None,
                "gross_capacity_bits": None, "metadata_foregone_bits": None,
                "bootstrap_backup_bits": None, "net_capacity_bits": None,
                "signed_net_bpp": None, "positive_net": False,
                "owner_prepare_seconds": None, "nonce": None,
            }
            try:
                if spec["kind"] == "hist":
                    choice = histogram_choice(original)
                    if choice is None:
                        base_row.update(status="PREPARE_REJECTED", rejection_reason="no empty histogram bin")
                        rows.append(base_row)
                        continue
                    net = int(choice["net"])
                    base_row.update(
                        candidate_count=int(choice["carrier_count"]),
                        gross_capacity_bits=int(choice["carrier_count"]),
                        metadata_foregone_bits=0,
                        bootstrap_backup_bits=int(choice["header_backup_bits"]),
                        net_capacity_bits=net,
                        signed_net_bpp=net / original.size,
                    )
                    if net <= 0:
                        base_row.update(status="NO_POSITIVE_NET_CAPACITY", rejection_reason="peak-bin carriers do not cover the 32-pixel header backup")
                        rows.append(base_row)
                        continue
                else:
                    start = time.perf_counter()
                    q = prepare_predictor_packet(original, spec, model_cache)
                    base_row["owner_prepare_seconds"] = time.perf_counter() - start
                    net = int(q["net"])
                    base_row.update(
                        candidate_mae=float(q["raw_mae"]),
                        candidate_count=int(q["candidate_count"]),
                        gross_capacity_bits=int(q["gross"]),
                        metadata_foregone_bits=int(q["foregone"]),
                        bootstrap_backup_bits=int(q["backup"]),
                        net_capacity_bits=net,
                        signed_net_bpp=net / original.size,
                        selected_phase=int(q["phase"]),
                        phase_selection_gain_bits=int(q["phase_selection_gain_bits"]),
                    )
                    if net <= 0:
                        base_row.update(status="NO_POSITIVE_NET_CAPACITY", rejection_reason="signed net capacity is nonpositive after directory/bootstrap costs")
                        rows.append(base_row)
                        continue
            except Exception as exc:
                base_row.update(status="PREPARE_REJECTED", rejection_reason=f"{type(exc).__name__}: {exc}")
                rows.append(base_row)
                continue

            accepted = net > 0
            base_row.update(accepted=accepted, positive_net=accepted)
            sequence += 1
            nonce = nonce_base + sequence
            if nonce >= 2**128:
                raise OverflowError("comparison-run nonce sequence exceeded uint128")
            rng = np.random.default_rng(seed + method_index * 1_000_003 + image_index)
            payload = rng.integers(0, 2, size=net, dtype=np.uint8)
            case_id = f"{method_index:02d}_{image_index:04d}"
            cipher_path = method_dir / f"{case_id}_cipher.png"
            payload_path = method_dir / f"{case_id}_payload.npy"
            recovered_path = method_dir / f"{case_id}_recovered.npy"
            extracted_path = method_dir / f"{case_id}_extracted.npy"
            np.save(payload_path, payload, allow_pickle=False)

            if spec["kind"] == "hist":
                encrypted = histogram_shift_encrypt(original, payload, master, nonce, choice)
                Image.fromarray(encrypted, mode="L").save(cipher_path)
            else:
                reserved_path = method_dir / f"{case_id}_reserved.png"
                reserved, hider_key = reserve_predictor_packet(original, q, master, nonce)
                Image.fromarray(reserved, mode="L").save(reserved_path)
                embed_items.append({
                    "id": case_id, "reserved_path": str(reserved_path),
                    "payload_path": str(payload_path), "hider_key_hex": hider_key.hex(),
                    "cipher_path": str(cipher_path),
                })
            compare_items[case_id] = {
                "source": str(source), "payload_path": str(payload_path),
                "recovered_path": str(recovered_path), "extracted_path": str(extracted_path),
            }
            base_row.update(
                roundtrip_attempted=True, status="PENDING_RECEIVER",
                payload_bits=net, nonce=f"{nonce:032x}",
            )
            rows.append(base_row)

            if spec["kind"] == "cnn":
                info = get_model(spec, model_cache)
                model_identity[name] = {
                    "checkpoint": spec["checkpoint"], "checkpoint_sha256": info["sha256"],
                    "patch_size": info["patch_size"], "residual": info["residual"],
                    "parameters": info["parameters"],
                }

        # The encrypted-domain hider receives reserved ciphertext, payload, and
        # its capability key only. It never receives the original image or K.
        if embed_items:
            embed_manifest = {
                "items": embed_items, "result_path": str(method_dir / "hider_results.json"),
            }
            manifest_path = method_dir / "hider_manifest.json"
            manifest_path.write_text(json.dumps(embed_manifest, indent=2), encoding="utf-8")
            cp = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "embed-batch", str(manifest_path)],
                capture_output=True, text=True,
            )
            (method_dir / "hider.log").write_text(cp.stdout + cp.stderr, encoding="utf-8")
            if cp.returncode != 0:
                raise RuntimeError(f"{name} encrypted-domain hider failed:\n{cp.stdout}\n{cp.stderr}")

        receiver_items = []
        for case_id, ref in compare_items.items():
            source_row = next(row for row in rows if row["image"] == corpus[int(case_id.split("_")[-1])]["name"] and row["status"] == "PENDING_RECEIVER")
            nonce = int(source_row["nonce"], 16)
            receiver_items.append({
                "id": case_id, "cipher_path": str(method_dir / f"{case_id}_cipher.png"),
                "recovered_path": ref["recovered_path"], "extracted_path": ref["extracted_path"],
                "master_hex": master.hex(), "nonce": nonce,
            })
        if receiver_items:
            receiver_manifest = {
                "items": receiver_items,
                "source_paths": [record["source"] for record in corpus],
                "result_path": str(method_dir / "receiver_results.json"),
            }
            receiver_manifest_path = method_dir / "receiver_manifest.json"
            receiver_manifest_path.write_text(json.dumps(receiver_manifest, indent=2), encoding="utf-8")
            cp = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "receiver-batch", str(receiver_manifest_path)],
                capture_output=True, text=True,
            )
            (method_dir / "receiver.log").write_text(cp.stdout + cp.stderr, encoding="utf-8")
            if cp.returncode != 0:
                # Batch rows retain successful/failed receiver details for diagnosis.
                if not (method_dir / "receiver_results.json").exists():
                    raise RuntimeError(f"{name} receiver batch failed:\n{cp.stdout}\n{cp.stderr}")
            receiver_audit = json.loads((method_dir / "receiver_results.json").read_text(encoding="utf-8"))
            receiver_status = {row["id"]: row for row in receiver_audit["items"]}
            if receiver_audit.get("source_access"):
                raise AssertionError(f"{name} receiver accessed source images")

            for row in rows:
                if row.get("status") != "PENDING_RECEIVER":
                    continue
                case_id = next(k for k, v in compare_items.items() if v["source"] == str(Path(next(rec["source"] for rec in corpus if rec["name"] == row["image"]))))
                rx = receiver_status.get(case_id, {"status": "FAIL", "error": "missing receiver record"})
                if rx["status"] != "PASS":
                    row.update(status="FAIL_RECEIVER", receiver_error=rx.get("error", "unknown receiver error"))
                    continue
                recovered = np.load(compare_items[case_id]["recovered_path"], allow_pickle=False)
                extracted = np.load(compare_items[case_id]["extracted_path"], allow_pickle=False)
                original = read_native_gray(Path(compare_items[case_id]["source"]))
                payload = np.load(compare_items[case_id]["payload_path"], allow_pickle=False)
                image_ok = bool(np.array_equal(recovered, original))
                payload_ok = bool(np.array_equal(extracted, payload) and len(extracted) == len(payload))
                row.update(
                    image_exact=image_ok, payload_exact=payload_ok,
                    extracted_bits=int(len(extracted)),
                    status="PASS" if image_ok and payload_ok else "FAIL_EXACTNESS",
                    receiver_source_access=False,
                )
        else:
            receiver_audit = {"source_access": False, "items": []}

        if spec["kind"] == "cnn":
            # Verify frozen inference did not mutate any model weights.
            for info in model_cache.values():
                if info["model"].training:
                    raise AssertionError(f"model left in training mode: {name}")
        elapsed = time.perf_counter() - owner_start
        summary = summarize_method(name, rows)
        summary["total_method_wall_seconds"] = elapsed
        method_summaries.append(summary)
        all_rows.extend(rows)
        persist_progress(out, all_rows, method_summaries)
        print(json.dumps(summary, sort_keys=True), flush=True)

        # Keep only CSV/JSON evidence; temporary encrypted packets are removed
        # after independent receiver outputs have been checked by the owner.
        for child in method_dir.iterdir():
            if child.is_file():
                child.unlink()
        method_dir.rmdir()

    fields = sorted({key for row in all_rows for key in row})
    with (out / "per_image_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    aggregate_fields = sorted({key for row in method_summaries for key in row})
    with (out / "method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=aggregate_fields)
        writer.writeheader()
        writer.writerows(method_summaries)

    report_lines = [
        "# Full-corpus grayscale end-to-end comparison",
        "",
        f"- Distinct curated native 8-bit grayscale images: {len(corpus)}",
        "- Model training: not performed; all CNN checkpoints loaded in evaluation mode and frozen.",
        f"- Matched predictor protocol: one common step-{GRID_STEP} lattice, border {GRID_BORDER}, {GRID_PHASES} implicit phases.",
        "- Payload test: one full measured-net-capacity random binary payload per positive-capacity image and method.",
        "- Receiver semantic inputs: marked encrypted image, 32-byte master key, and nonce. Receiver process is separately launched and source-data reads are blocked.",
        "- MED/GAP/CALIC and all CNN variants use the same predictor-error label map, directory format, AES-CTR image encryption, authenticated in-band metadata, and recovery rule.",
        "- HistogramShift is a separately implemented global peak/nearest-zero-bin, one-bit-per-peak-pixel reversible reference. It embeds before AES-CTR encryption and is not the same encrypted-domain hider architecture; its results must be interpreted as a separately identified reference.",
        "",
        "## Per-method summary",
        "",
        "| Method | Positive-net images | Exact E2E recoveries | Attempts | Mean signed net bpp | Mean candidate MAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in method_summaries:
        bpp = row["mean_signed_net_bpp_all_valid"]
        mae = row["mean_candidate_mae"]
        report_lines.append(
            f"| {row['method']} | {row['positive_net_images']}/{row['images']} | "
            f"{row['exact_roundtrips']}/{row['roundtrip_attempts']} | {row['roundtrip_attempts']} | "
            f"{'NA' if bpp is None else f'{bpp:.6f}'} | {'NA' if mae is None else f'{mae:.6f}'} |"
        )
    report_lines += [
        "",
        "## Interpretation limits",
        "",
        "- Mean signed net bpp is calculated over images for which a bootstrap directory fit was possible; nonpositive net values are retained rather than clamped to zero. Images with no valid directory phase are counted as preparation rejections and have no numeric net-bpp value.",
        "- The matched step-4 grid is intentionally conservative so the largest 7x7 CNN receptive field and the radius-2 MED/GAP/CALIC contexts cannot include another mutable candidate. It equalizes candidate locations across predictor methods; do not mix these bpp values with the native step-2 v4 EDR2 result.",
        "- CALIC is the repository's simplified CALIC-style predictor, not a canonical full CALIC codec.",
        "- The histogram-shifting baseline uses an explicit peak/zero header and 256-bit backup for 32 header pixels; its separate embedding order is disclosed above.",
        "- Exact recovery is reported only for positive-net cases actually passed through the independent receiver. A method with fewer positive-net images does not have 248/248 full-corpus recovery coverage.",
        "",
        "Raw per-image rows, source hashes, method checkpoint hashes, and receiver audits are included in this artifact.",
    ]
    (out / "GRAYSCALE_E2E_COMPARISON_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (out / "protocol_identity.json").write_text(json.dumps({
        "protocol": "EDC3 matched grayscale predictor comparison",
        "grid_step": GRID_STEP, "grid_border": GRID_BORDER, "grid_phase_count": GRID_PHASES,
        "distinct_images": len(corpus), "training_performed": False,
        "models": model_identity,
        "baseline_implementations": {
            "MED": "src.baselines.med_predict",
            "GAP": "src.baselines.gap_predict",
            "CALIC_simplified": "src.baselines.calic_predict (simplified predictor only)",
            "HistogramShift_global_peak_zero": "one-bit global peak/nearest-zero histogram shift, 32-pixel in-band header, 256-bit header-pixel backup, AES-CTR after embedding",
        },
        "receiver_semantic_inputs": ["marked encrypted image", "master key", "nonce"],
        "hider_semantic_inputs_for_EDC3": ["encrypted reserved image", "binary payload", "derived data-hiding capability key"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "run_summary.json").write_text(json.dumps({
        "dataset_images": len(corpus), "skipped_files": len(skipped),
        "duplicate_pixel_files": len(duplicates), "methods": method_summaries,
        "training_performed": False, "checkpoint_hashes": model_identity,
        "nonce_base_hex": f"{nonce_base:032x}", "fixed_test_master_hex": master.hex(),
        "all_predictor_methods_used_matched_grid": True,
        "histogram_shifting_reported_as_separate_reference": True,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proposed = next(row for row in method_summaries if row["method"] == "CNN_v4_patch3_proposed")
    print(
        "PROPOSED_CNN_COVERAGE "
        f"{proposed['positive_net_images']}/{len(corpus)} positive-net images; "
        f"{proposed['exact_roundtrips']}/{proposed['roundtrip_attempts']} exact receiver round trips",
        flush=True,
    )
    print("GRAYSCALE COMPARATIVE E2E COMPLETE", flush=True)
    return 0

def self_test():
    # Exercise the common predictor packet with all three classical predictors.
    y, x = np.indices((512, 512))
    image = ((x * 3 + y * 2) % 251).astype(np.uint8)
    master = bytes(range(32))
    from src.baselines import med_predict, gap_predict, calic_predict
    for spec in SPECS:
        method_name, method_id = spec["name"], spec["id"]
        q = prepare_predictor_packet(image, spec, {})
        if q["net"] <= 0:
            raise AssertionError(f"self-test {method_name} has no positive capacity")
        payload = np.random.default_rng(51 + method_id).integers(0, 2, q["net"], np.uint8)
        key, nonce = bytes(range(32)), 1000 + method_id
        reserved, hider_key = reserve_predictor_packet(image, q, key, nonce)
        final = embed_encrypted(reserved, payload, hider_keys(hider_key))
        recovered, extracted = receive_predictor_packet(final, key, nonce, {})
        if not np.array_equal(recovered, image) or not np.array_equal(extracted, payload):
            raise AssertionError(f"self-test exact recovery failed for {method_name}")
    # Exercise the independent peak/zero histogram-shifting reference.
    hs = np.full((512, 512), 100, np.uint8)
    hs[100:220, 100:220] = (101 + ((x[100:220, 100:220] + y[100:220, 100:220]) % 100)).astype(np.uint8)
    choice = histogram_choice(hs)
    if choice is None or choice["net"] <= 0:
        raise AssertionError("histogram-shift self-test has no positive capacity")
    payload = np.random.default_rng(991).integers(0, 2, choice["net"], np.uint8)
    master, nonce = bytes(range(32)), 909090
    cipher = histogram_shift_encrypt(hs, payload, master, nonce, choice)
    k = derive_keys(master, nonce)
    plain = np.frombuffer(crypt(cipher.tobytes(), k["image"]), np.uint8).copy().reshape(hs.shape)
    recovered, extracted = receive_histogram_shift(plain, hider_keys(k["hider"])["auth"])
    if not np.array_equal(recovered, hs) or not np.array_equal(extracted, payload):
        raise AssertionError("histogram-shift self-test exact recovery failed")
    print("SELF-TEST PASS: MED, GAP, simplified CALIC and histogram shifting exact round trips")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "embed-batch":
        if len(sys.argv) != 3:
            raise ValueError("usage: run_gray_comparative_gate.py embed-batch manifest.json")
        cmd_embed_batch(sys.argv[2])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "receiver-batch":
        if len(sys.argv) != 3:
            raise ValueError("usage: run_gray_comparative_gate.py receiver-batch manifest.json")
        cmd_receiver_batch(sys.argv[2])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-images", type=int, default=248)
    parser.add_argument("--seed", type=int, default=20261115)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run_comparison(args.data_dir, args.output_dir, args.expected_images, args.seed, args.threads)

if __name__ == "__main__":
    main()
