"""Frozen EDR2 CNN predictor and safe-zone label-map preparation.

This module contains prediction/label preprocessing only. It does not encrypt,
embed payloads, or decode receiver packets.
"""
from __future__ import annotations

import zlib
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cnn_model import load_model
import wire
CHECKPOINT = ROOT / "models" / "v4_patch3.pth"
SAFE_ZONE_STEP = 2
PREDICTOR_RADIUS = 1
BATCH_SIZE = 2048

BOOK = wire.BOOK.copy()
ENC = {tuple(map(int, row)): index for index, row in enumerate(BOOK)}
# EDR2 owns its allocation rule in wire.py; do not import the legacy
# dense pipeline or its external-map receiver into the active protocol.
LABEL = np.asarray(
    [ENC[tuple(map(int, wire.allocation(error)))] for error in range(256)],
    dtype=np.uint8,
)

_MODEL = None
_MODEL_IDENTITY = None


def model():
    """Load and cache the frozen 3x3 checkpoint on CPU."""
    global _MODEL, _MODEL_IDENTITY
    if _MODEL is None:
        torch.set_num_threads(4)
        loaded, patch_size, residual, params = load_model(str(CHECKPOINT), device="cpu")
        if patch_size != 3 or residual is not True:
            raise ValueError(
                f"EDR2 requires the frozen residual CNN-3x3 checkpoint; found patch={patch_size}, residual={residual}"
            )
        loaded.eval()
        loaded.requires_grad_(False)
        _MODEL = loaded
        _MODEL_IDENTITY = {
            "checkpoint": str(CHECKPOINT),
            "checkpoint_sha256": __import__("hashlib").sha256(CHECKPOINT.read_bytes()).hexdigest(),
            "patch_size": patch_size,
            "residual": residual,
            "parameters": params,
            "batch_size": BATCH_SIZE,
            "safe_zone_step": SAFE_ZONE_STEP,
            "safe_zone_phase_count": wire.SAFE_ZONE_PHASES,
        }
    return _MODEL


def model_identity():
    model()
    return dict(_MODEL_IDENTITY)


def coords(shape, step: int = SAFE_ZONE_STEP, radius: int = PREDICTOR_RADIUS, phase: int = 0):
    """Row-major centers on the maximal step-2 lattice with a one-pixel 3x3 border."""
    if len(shape) != 2:
        raise ValueError("EDR2 predictor supports 2D grayscale images only")
    if step != SAFE_ZONE_STEP:
        raise ValueError("EDR2 protocol safe-zone step is fixed at 2")
    if radius != PREDICTOR_RADIUS:
        raise ValueError("EDR2 candidate border is fixed to the 3x3 predictor radius")
    if shape[0] <= 2 * radius or shape[1] <= 2 * radius:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    return wire.grid(shape, phase=phase)


def predict(image, ys, xs, active_model=None):
    """Apply the exact masked 3x3 predictor at the candidate coordinates."""
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError("expected uint8 grayscale image")
    active_model = model() if active_model is None else active_model
    radius = int(active_model.patch_size) // 2
    if active_model.patch_size != 3:
        raise ValueError("EDR2 predictor checkpoint must use 3x3 patches")
    if len(ys) != len(xs):
        raise ValueError("coordinate arrays must have equal length")
    if len(ys) == 0:
        return np.empty(0, dtype=np.float32)

    patches = np.stack([
        image[y - radius:y + radius + 1, x - radius:x + radius + 1]
        for y, x in zip(ys, xs)
    ]).astype(np.float32) / 255.0
    patches[:, radius, radius] = 0.0
    patches = patches[:, None, :, :]

    outputs = []
    active_model.eval()
    with torch.inference_mode():
        for start in range(0, len(patches), BATCH_SIZE):
            batch = torch.from_numpy(patches[start:start + BATCH_SIZE])
            outputs.append(active_model(batch).cpu().numpy().reshape(-1))
    return np.concatenate(outputs).astype(np.float32, copy=False)


def packlabels(labels):
    labels = np.asarray(labels, dtype=np.uint8)
    if labels.ndim != 1 or np.any(labels >= len(BOOK)):
        raise ValueError("invalid label class sequence")
    if len(labels) % 2:
        labels = np.concatenate((labels, np.zeros(1, dtype=np.uint8)))
    return ((labels[::2] << 4) | labels[1::2]).astype(np.uint8).tobytes()


def fuse_predictions(spatial_predictions, cross_references, ys, xs, cross_offset=0, blend_num=0, blend_den=4):
    """Fuse the frozen spatial CNN with a deterministic co-located cross-channel estimate.

    The two reference-channel samples are read at the target candidate coordinate.
    In the RGB protocol those coordinates are untouched in both reference channels
    because the three channels are assigned distinct lattice phases.
    """
    spatial = np.asarray(spatial_predictions, dtype=np.float32)
    if spatial.ndim != 1 or len(spatial) != len(ys) or len(xs) != len(ys):
        raise ValueError("spatial prediction and candidate coordinate lengths differ")
    if cross_references is None:
        if blend_num not in (0,):
            raise ValueError("cross-channel blend requires two reference channels")
        return spatial
    if not isinstance(cross_references, (tuple, list)) or len(cross_references) != 2:
        raise ValueError("cross_references must contain exactly two channel arrays")
    if not isinstance(blend_den, int) or blend_den < 1:
        raise ValueError("blend_den must be a positive integer")
    if not isinstance(blend_num, int) or not 0 <= blend_num <= blend_den:
        raise ValueError("blend_num must be an integer in [0, blend_den]")
    if not isinstance(cross_offset, int) or not -255 <= cross_offset <= 255:
        raise ValueError("cross_offset must be an integer in [-255,255]")
    ref_a, ref_b = (np.asarray(value) for value in cross_references)
    if (ref_a.dtype != np.uint8 or ref_b.dtype != np.uint8
            or ref_a.ndim != 2 or ref_b.ndim != 2
            or ref_a.shape != ref_b.shape):
        raise ValueError("cross-reference channels must be same-sized 2D uint8 arrays")
    if np.any(ys < 0) or np.any(xs < 0) or np.any(ys >= ref_a.shape[0]) or np.any(xs >= ref_a.shape[1]):
        raise ValueError("cross-reference candidate coordinate outside image")
    # Integer half-up average, signed integer bias, then clipping.
    total = ref_a[ys, xs].astype(np.uint16) + ref_b[ys, xs].astype(np.uint16)
    mean = ((total + 1) // 2).astype(np.int16)
    cross = np.clip(mean + cross_offset, 0, 255).astype(np.float32)
    if blend_num == 0:
        return spatial
    # Keep the same float32 operations and nearest-even np.rint at both ends.
    return (
        np.float32(blend_den - blend_num) * spatial
        + np.float32(blend_num) * cross
    ) / np.float32(blend_den)


def prepare(
    image,
    phase_override=None,
    cross_references=None,
    cross_offset=0,
    cross_blend_num=0,
    cross_blend_den=4,
    spatial_prediction_override=None,
):
    """Evaluate four maximum-density safe-grid phases and select by true net payload.

    Inference is performed phase-by-phase with the same coordinate order and
    batch protocol used by the receiver. The chosen phase is implicit in the
    in-image authenticated header location; it costs no sidecar or header bits.
    """
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError("expected uint8 grayscale")
    if spatial_prediction_override is not None and phase_override is None:
        raise ValueError("spatial_prediction_override requires one fixed phase")

    active_model = model()
    alternatives = []
    invalid_phases = []
    if phase_override is not None:
        if not isinstance(phase_override, int) or not 0 <= phase_override < wire.SAFE_ZONE_PHASES:
            raise ValueError("phase_override must be an integer in [0,3]")
        phases = (phase_override,)
    else:
        phases = range(wire.SAFE_ZONE_PHASES)

    for phase in phases:
        ys, xs = coords(image.shape, phase=phase)
        if len(ys) < wire.HEADER_BYTES:
            invalid_phases.append(phase)
            continue

        # Do not batch phases together: receiver inference for the selected
        # phase must reproduce the owner's exact floating-point batch schedule.
        if spatial_prediction_override is None:
            spatial_predictions = predict(image, ys, xs, active_model)
        else:
            spatial_predictions = np.asarray(spatial_prediction_override, dtype=np.float32)
            if spatial_predictions.ndim != 1 or len(spatial_predictions) != len(ys):
                raise ValueError("spatial_prediction_override has the wrong candidate count")
        predictions = fuse_predictions(
            spatial_predictions,
            cross_references,
            ys,
            xs,
            cross_offset=cross_offset,
            blend_num=cross_blend_num,
            blend_den=cross_blend_den,
        )
        rounded = np.rint(predictions).astype(np.int32)
        error_abs = np.abs(image[ys, xs].astype(np.int32) - rounded)
        labels = LABEL[error_abs]
        raw = packlabels(labels)
        compressed = zlib.compress(raw, 9)
        codec = 1 if len(compressed) < len(raw) else 0
        metadata = compressed if codec else raw
        header_pixels = wire.HEADER_BYTES + len(metadata) + wire.TAG_BYTES

        if header_pixels >= len(ys):
            invalid_phases.append(phase)
            continue

        counts = BOOK[labels, 0].astype(np.int32)
        positions = wire.slots(image.shape, labels, header_pixels, phase=phase)
        gross = int(counts.sum())
        foregone = int(counts[:header_pixels].sum())
        available = len(positions[0])
        backup = 8 * header_pixels
        net = available - backup
        if available != gross - foregone:
            raise AssertionError("slot enumeration and allocation sum disagree")

        stats = dict(
            pixels=int(image.size),
            candidates=int(len(ys)),
            candidate_fraction=float(len(ys) / image.size),
            gross_slots=gross,
            gross_bpp=gross / image.size,
            raw_label_bits=4 * len(ys),
            packed_raw_label_bits=8 * len(raw),
            compressed_label_bytes=len(compressed),
            stored_label_bits=8 * len(metadata),
            fixed_header_bits=8 * wire.HEADER_BYTES,
            payload_length_bits_in_encrypted_header=64,
            authentication_bits=8 * wire.TAG_BYTES,
            bootstrap_pixels=header_pixels,
            metadata_total_bits=8 * header_pixels,
            backup_bits=backup,
            foregone_gross_slots=foregone,
            stream_bits=available,
            physical_gross_bits=available + 8 * header_pixels,
            signed_net_bits=net,
            net_bpp=net / image.size,
            payload_encryption_expansion_bits=0,
            accepted=net > 0,
            phase=phase,
            cross_offset=int(cross_offset) if cross_references is not None else None,
            cross_blend_num=int(cross_blend_num),
            cross_blend_den=int(cross_blend_den),
        )
        alternatives.append(dict(
            phase=phase, ys=ys, xs=xs, predictions=predictions,
            spatial_predictions=spatial_predictions,
            cross_offset=int(cross_offset) if cross_references is not None else None,
            cross_blend_num=int(cross_blend_num),
            cross_blend_den=int(cross_blend_den),
            p=rounded, labels=labels, ns=counts, meta=metadata,
            mode=codec, h=header_pixels, net=net, positions=positions,
            stats=stats,
        ))

    if not alternatives:
        raise ValueError("image too small for every EDR2 safe-grid phase")

    # Maximise net payload after the phase-specific compressed directory,
    # bootstrap carrier opportunity cost and exact byte backup are charged.
    # Ties are deterministic: the lowest phase index wins.
    chosen = max(alternatives, key=lambda row: (row["net"], -row["phase"]))
    chosen["phase_net_bits"] = [
        next((int(item["net"]) for item in alternatives if item["phase"] == phase), None)
        for phase in range(wire.SAFE_ZONE_PHASES)
    ]
    chosen["phase_scores"] = [
        {
            "phase": int(item["phase"]),
            "candidate_count": int(len(item["ys"])),
            "directory_bytes": int(len(item["meta"])),
            "bootstrap_candidates": int(item["h"]),
            "gross_slots": int(item["stats"]["gross_slots"]),
            "foregone_slots": int(item["stats"]["foregone_gross_slots"]),
            "backup_bits": int(item["stats"]["backup_bits"]),
            "net_payload_bits": int(item["net"]),
        }
        for item in alternatives
    ]
    chosen["invalid_phases"] = invalid_phases
    chosen["stats"]["phase_selection_gain_bits"] = (
        int(chosen["net"]) - int(chosen["phase_net_bits"][0])
        if chosen["phase_net_bits"][0] is not None else None
    )
    return chosen
