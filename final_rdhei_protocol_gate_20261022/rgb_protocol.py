"""Prototype CC-EDR2-RGB owner, encrypted-domain hider and receiver.

A single authenticated RGB directory describes three channel label maps. R/G/B
use three distinct step-2 lattice phases; the unused fourth phase is a shared
calibration lattice. Cross-channel linear predictors are fitted on that
untouched lattice with deterministic integer arithmetic and recomputed by the
receiver. The existing grayscale protocol is not modified.
"""
from __future__ import annotations

import hashlib
import itertools
import struct
import zlib

import numpy as np

import predictor
import wire
import rgb_wire


CROSS_BLEND_NUM = 1
CROSS_BLEND_DEN = 4
RGB_VERSION = b"R3D1"


def _round_div_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    value = abs(int(numerator))
    quotient, remainder = divmod(value, int(denominator))
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2):
        quotient += 1
    return sign * quotient


def _round_div_even_array(numerators: np.ndarray, denominator: int) -> np.ndarray:
    values = np.asarray(numerators, dtype=np.int64)
    return np.fromiter(
        (_round_div_even(int(value), denominator) for value in values.flat),
        dtype=np.int64, count=values.size
    ).reshape(values.shape)


def _cross_feature(image: np.ndarray, target: int, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    refs = [channel for channel in range(3) if channel != target]
    a = image[ys, xs, refs[0]].astype(np.uint16)
    b = image[ys, xs, refs[1]].astype(np.uint16)
    return ((a + b + 1) // 2).astype(np.int64)


def fit_cross_regressions(image: np.ndarray, calibration_phase: int):
    """Fit Q8 affine channel predictors using only mutually untouched anchor pixels."""
    height, width, channels = image.shape
    if image.dtype != np.uint8 or image.ndim != 3 or channels != 3:
        raise ValueError("expected uint8 HxWx3 RGB")
    ys, xs = wire.grid((height, width), phase=calibration_phase)
    if len(ys) < 2:
        raise ValueError("too few untouched calibration pixels")
    regressions = []
    for target in range(3):
        x = _cross_feature(image, target, ys, xs)
        y = image[ys, xs, target].astype(np.int64)
        n = int(len(x))
        sx, sy = int(x.sum()), int(y.sum())
        sxx = int(np.dot(x, x))
        sxy = int(np.dot(x, y))
        denominator = n * sxx - sx * sx
        numerator = n * sxy - sx * sy
        slope_q8 = 0 if denominator == 0 else _round_div_even(numerator * 256, denominator)
        intercept_q8 = _round_div_even(sy * 256 - slope_q8 * sx, n)
        regressions.append((int(slope_q8), int(intercept_q8)))
    return tuple(regressions)


def _fused_prediction(spatial: np.ndarray, reference_feature: np.ndarray,
                      regression: tuple[int, int],
                      blend_num: int = CROSS_BLEND_NUM,
                      blend_den: int = CROSS_BLEND_DEN) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not 0 <= blend_num <= blend_den or blend_den <= 0:
        raise ValueError("invalid RGB cross-channel blend ratio")
    slope_q8, intercept_q8 = regression
    cross_q8 = slope_q8 * np.asarray(reference_feature, dtype=np.int64) + intercept_q8
    cross = np.clip(_round_div_even_array(cross_q8, 256), 0, 255).astype(np.int32)
    spatial_integer = np.clip(
        np.rint(np.asarray(spatial, dtype=np.float32)).astype(np.int64), 0, 255
    ).astype(np.int32)
    fused = _round_div_even_array(
        (blend_den - blend_num) * spatial_integer.astype(np.int64)
        + blend_num * cross.astype(np.int64),
        blend_den
    )
    return np.clip(fused, 0, 255).astype(np.int32), cross, spatial_integer


def _image_identity(image: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack(">QQB", image.shape[0], image.shape[1], image.shape[2]))
    digest.update(b"|uint8|")
    digest.update(image.tobytes(order="C"))
    return digest.hexdigest()


def _pack_directory(phases: tuple[int, int, int], calibration_phase: int,
                    labels: list[np.ndarray]) -> tuple[bytes, bytes, int]:
    raw = bytearray(RGB_VERSION + bytes((*phases, calibration_phase)))
    for row in labels:
        raw.extend(predictor.packlabels(row))
    raw = bytes(raw)
    compressed = zlib.compress(raw, 9)
    codec = 1 if len(compressed) < len(raw) else 0
    return raw, (compressed if codec else raw), codec


def build_spatial_cache(original: np.ndarray):
    """Run the frozen grayscale CNN once per channel and lattice phase."""
    if (not isinstance(original, np.ndarray) or original.dtype != np.uint8
            or original.ndim != 3 or original.shape[2] != 3):
        raise ValueError("CC-EDR2-RGB expects native uint8 RGB HxWx3")
    active_model = predictor.model()
    spatial_cache = {}
    coordinate_cache = {}
    for channel in range(3):
        plane = np.ascontiguousarray(original[:, :, channel])
        for phase in range(4):
            ys, xs = predictor.coords(plane.shape, phase=phase)
            coordinate_cache[(channel, phase)] = (ys, xs)
            spatial_cache[(channel, phase)] = predictor.predict(
                plane, ys, xs, active_model
            )
    return spatial_cache, coordinate_cache


def prepare(original: np.ndarray, *, blend_num: int = CROSS_BLEND_NUM,
            blend_den: int = CROSS_BLEND_DEN,
            assignment_override: tuple[int, int, int] | None = None,
            spatial_cache: dict | None = None,
            coordinate_cache: dict | None = None):
    """Jointly optimize 3-of-4 channel phase assignment and RGB net capacity."""
    if (not isinstance(original, np.ndarray) or original.dtype != np.uint8
            or original.ndim != 3 or original.shape[2] != 3):
        raise ValueError("CC-EDR2-RGB expects native uint8 RGB HxWx3")
    height, width, _ = original.shape
    if height % 2 or width % 2:
        raise ValueError("CC-EDR2-RGB currently requires even height and width")
    if blend_den <= 0 or not 0 <= blend_num <= blend_den:
        raise ValueError("invalid cross-channel blend ratio")

    if spatial_cache is None and coordinate_cache is None:
        spatial_cache, coordinate_cache = build_spatial_cache(original)
    elif spatial_cache is None or coordinate_cache is None:
        raise ValueError("spatial_cache and coordinate_cache must be supplied together")
    expected_keys = {(channel, phase) for channel in range(3) for phase in range(4)}
    if set(spatial_cache) != expected_keys or set(coordinate_cache) != expected_keys:
        raise ValueError("RGB spatial/coordinate cache must contain all 12 channel-phase entries")
    for channel in range(3):
        for phase in range(4):
            ys, xs = coordinate_cache[(channel, phase)]
            if (len(ys) != len(xs)
                    or np.asarray(spatial_cache[(channel, phase)]).shape != (len(ys),)):
                raise ValueError("invalid cached RGB spatial prediction or coordinate lengths")

    alternatives = []
    if assignment_override is None:
        all_assignments = [
            (r, g, b, next(p for p in range(4) if p not in (r, g, b)))
            for r in range(4)
            for g in range(4) if g != r
            for b in range(4) if b not in (r, g)
        ]
    else:
        if (not isinstance(assignment_override, (tuple, list))
                or len(assignment_override) != 3
                or any(not isinstance(value, int) or not 0 <= value < 4 for value in assignment_override)
                or len(set(assignment_override)) != 3):
            raise ValueError("assignment_override must be three distinct phases in [0,3]")
        fixed_phases = tuple(int(value) for value in assignment_override)
        calibration_phase = next(value for value in range(4) if value not in fixed_phases)
        all_assignments = [(*fixed_phases, calibration_phase)]
    for red_phase, green_phase, blue_phase, calibration_phase in all_assignments:
        phases = (red_phase, green_phase, blue_phase)
        regressions = fit_cross_regressions(original, calibration_phase)
        labels_by_channel = []
        predictions_by_channel = []
        prediction_metrics = []
        for channel, phase in enumerate(phases):
            ys, xs = coordinate_cache[(channel, phase)]
            references = _cross_feature(original, channel, ys, xs)
            fused, cross, spatial_integer = _fused_prediction(
                spatial_cache[(channel, phase)], references, regressions[channel],
                blend_num, blend_den
            )
            target = original[ys, xs, channel].astype(np.int32)
            error = np.abs(target - fused)
            labels = predictor.LABEL[error]
            labels_by_channel.append(labels)
            predictions_by_channel.append(fused)
            prediction_metrics.append({
                "spatial_mae": float(np.mean(np.abs(target - spatial_integer))),
                "cross_channel_mae": float(np.mean(np.abs(target - cross))),
                "fused_mae": float(np.mean(error)),
            })

        raw, metadata, codec = _pack_directory(
            phases, calibration_phase, labels_by_channel
        )
        bootstrap = rgb_wire.HEADER_BYTES + len(metadata) + rgb_wire.TAG_BYTES
        candidate_count = len(coordinate_cache[(0, red_phase)][0])
        if bootstrap >= candidate_count:
            continue

        positions = rgb_wire.enumerate_slots(
            (height, width), labels_by_channel, phases, bootstrap
        )
        gross = int(sum(wire.BOOK[row, 0].sum() for row in labels_by_channel))
        foregone = int(wire.BOOK[labels_by_channel[0][:bootstrap], 0].sum())
        stream = gross - foregone
        backup = 8 * bootstrap
        net = stream - backup
        if len(positions[0]) != stream:
            raise AssertionError("RGB slot enumeration and net accounting disagree")
        stats = {
            "phase_assignment": list(phases),
            "calibration_phase": calibration_phase,
            "candidate_count_per_channel": candidate_count,
            "directory_raw_bytes": len(raw),
            "directory_stored_bytes": len(metadata),
            "directory_codec": codec,
            "bootstrap_candidates": bootstrap,
            "gross_slots_all_channels": gross,
            "foregone_red_header_slots": foregone,
            "bootstrap_backup_bits": backup,
            "ordinary_stream_bits": stream,
            "signed_net_payload_bits": net,
            "net_bpp_per_rgb_pixel": net / (height * width),
            "cross_blend": [blend_num, blend_den],
            "cross_regressions_q8": [list(pair) for pair in regressions],
            "prediction_metrics_by_channel": prediction_metrics,
        }
        alternatives.append({
            "phases": phases,
            "calibration_phase": calibration_phase,
            "labels": labels_by_channel,
            "predictions": predictions_by_channel,
            "prediction_metrics": prediction_metrics,
            "regressions": regressions,
            "raw_directory": raw,
            "metadata": metadata,
            "codec": codec,
            "bootstrap": bootstrap,
            "backup_bits": backup,
            "positions": positions,
            "net": net,
            "stats": stats,
        })

    if not alternatives:
        raise ValueError("no RGB phase assignment has enough bootstrap candidates")
    chosen = max(
        alternatives,
        key=lambda row: (row["net"], tuple(-phase for phase in (*row["phases"], row["calibration_phase"])))
    )
    chosen["assignment_scores"] = [
        {
            "phases": list(row["phases"]),
            "calibration_phase": row["calibration_phase"],
            "directory_bytes": len(row["metadata"]),
            "net_capacity_bits": row["net"],
        }
        for row in alternatives
    ]
    chosen["source_sha256"] = _image_identity(original)
    chosen["source_shape"] = tuple(map(int, original.shape))
    chosen["blend_num"] = blend_num
    chosen["blend_den"] = blend_den
    chosen["assignment_search"] = "adaptive_24" if assignment_override is None else "fixed_override"
    chosen["stats"]["assignment_search"] = chosen["assignment_search"]
    return chosen


def reserve(original: np.ndarray, master: bytes, nonce: int, prepared=None):
    """Reserve room and encrypt all three channels with independent AES-CTR keys."""
    q = prepare(original) if prepared is None else prepared
    if (tuple(q.get("source_shape", ())) != tuple(original.shape)
            or q.get("source_sha256") != _image_identity(original)):
        raise ValueError("prepared RGB state does not belong to this exact source image")
    if q["net"] <= 0:
        raise ValueError("non-positive CC-EDR2-RGB capacity")
    keys = rgb_wire.keys(master, nonce)
    capability = rgb_wire.hider_keys(keys["hider"])
    red_phase = q["phases"][0]
    ys, xs = wire.grid(original.shape[:2], phase=red_phase)
    bootstrap = q["bootstrap"]
    backup_bits = np.unpackbits(original[ys[:bootstrap], xs[:bootstrap], 0])
    stream = np.concatenate((backup_bits, np.zeros(q["net"], dtype=np.uint8)))
    reserved = original.copy()
    rgb_wire.writebits(reserved, q["positions"], stream)
    reserved[ys[:bootstrap], xs[:bootstrap], 0] = 0

    encrypted = np.empty_like(reserved)
    for channel in range(3):
        encrypted[:, :, channel] = np.frombuffer(
            rgb_wire.crypt(reserved[:, :, channel].tobytes(order="C"), keys["image"][channel]),
            dtype=np.uint8
        ).reshape(original.shape[:2])

    directory_cipher = rgb_wire.crypt(q["metadata"], capability["directory"])
    header = rgb_wire.encode_header(
        q["codec"], len(directory_cipher), 0, capability, "bootstrap"
    )
    encrypted[ys[:rgb_wire.HEADER_BYTES], xs[:rgb_wire.HEADER_BYTES], 0] = np.frombuffer(header, dtype=np.uint8)
    encrypted[ys[rgb_wire.HEADER_BYTES:rgb_wire.HEADER_BYTES + len(directory_cipher)],
              xs[rgb_wire.HEADER_BYTES:rgb_wire.HEADER_BYTES + len(directory_cipher)], 0] = np.frombuffer(directory_cipher, dtype=np.uint8)
    encrypted[ys[rgb_wire.HEADER_BYTES + len(directory_cipher):bootstrap],
              xs[rgb_wire.HEADER_BYTES + len(directory_cipher):bootstrap], 0] = 0
    rgb_wire.seal(
        encrypted, capability, "bootstrap",
        (*q["phases"], q["calibration_phase"]), len(directory_cipher)
    )
    return encrypted, {"hider": keys["hider"]}


def embed(reserved_rgb: np.ndarray, payload: np.ndarray, capability_key: bytes) -> np.ndarray:
    capability = rgb_wire.hider_keys(capability_key)
    return rgb_wire.embed(reserved_rgb, payload, capability)


def receive(marked_rgb: np.ndarray, master: bytes, nonce: int):
    """Receiver semantic inputs: marked RGB image, master key and nonce only."""
    keys = rgb_wire.keys(master, nonce)
    capability = rgb_wire.hider_keys(keys["hider"])
    q = rgb_wire.inspect(marked_rgb, capability, stage="final")
    encrypted_payload_bits = rgb_wire.readbits(
        marked_rgb, q["positions"], start=q["backup_bits"]
    )
    plain_bits = rgb_wire.crypt_bits(encrypted_payload_bits, capability["payload"])
    if np.any(plain_bits[q["payload_length"]:] != 0):
        raise ValueError("nonzero RGB payload padding")
    payload = plain_bits[:q["payload_length"]].copy()

    zero_cipher = np.empty_like(marked_rgb)
    for channel in range(3):
        zero_cipher[:, :, channel] = np.frombuffer(
            rgb_wire.crypt(bytes(marked_rgb.shape[0] * marked_rgb.shape[1]), keys["image"][channel]),
            dtype=np.uint8
        ).reshape(marked_rgb.shape[:2])

    restored_cipher = marked_rgb.copy()
    payload_positions = tuple(part[q["backup_bits"]:] for part in q["positions"][:3])
    zero_bits = rgb_wire.readbits(zero_cipher, q["positions"], start=q["backup_bits"])
    rgb_wire.writebits(restored_cipher, payload_positions + (q["positions"][3],), zero_bits)
    red_y, red_x = q["ys"], q["xs"]
    restored_cipher[red_y[:q["bootstrap"]], red_x[:q["bootstrap"]], 0] = zero_cipher[
        red_y[:q["bootstrap"]], red_x[:q["bootstrap"]], 0
    ]

    reserved = np.empty_like(marked_rgb)
    for channel in range(3):
        reserved[:, :, channel] = np.frombuffer(
            rgb_wire.crypt(restored_cipher[:, :, channel].tobytes(order="C"), keys["image"][channel]),
            dtype=np.uint8
        ).reshape(marked_rgb.shape[:2])

    backup = rgb_wire.readbits(reserved, q["positions"])[:q["backup_bits"]]
    regressions = fit_cross_regressions(reserved, q["calibration_phase"])
    recovered = reserved.copy()
    for channel, phase in enumerate(q["phases"]):
        ys, xs = wire.grid(reserved.shape[:2], phase=phase)
        spatial = predictor.predict(
            np.ascontiguousarray(reserved[:, :, channel]), ys, xs, predictor.model()
        )
        references = _cross_feature(reserved, channel, ys, xs)
        fused, _, _ = _fused_prediction(
            spatial, references, regressions[channel],
            CROSS_BLEND_NUM, CROSS_BLEND_DEN
        )
        start = q["bootstrap"] if channel == 0 else 0
        labels = q["labels"][channel]
        for index in range(start, len(ys)):
            n, low, high = map(int, wire.BOOK[int(labels[index])])
            if n == 0:
                continue
            modulus = 1 << (8 - n)
            residue = int(reserved[ys[index], xs[index], channel]) & (modulus - 1)
            candidates = [
                value for value in range(residue, 256, modulus)
                if low <= abs(value - int(fused[index])) <= high
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f"nonunique RGB channel-{channel} sample reconstruction at candidate {index}"
                )
            recovered[ys[index], xs[index], channel] = candidates[0]

    recovered[red_y[:q["bootstrap"]], red_x[:q["bootstrap"]], 0] = np.packbits(backup)
    return recovered, payload
