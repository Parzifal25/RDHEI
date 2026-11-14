"""Channel-separated EDR2-RGB packet framing, authentication and slot enumeration.

Separate from wire.py: this module leaves the validated grayscale protocol untouched.
"""
from __future__ import annotations

import hashlib
import hmac
import struct
import zlib

import numpy as np
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF

import wire

RGB_ID = b"EDR2RGB"
RGB_MAGIC = b"R3D1"
HEADER = wire.HEADER
HEADER_BYTES = wire.HEADER_BYTES
TAG_BYTES = wire.TAG_BYTES
PHASES = 4
CHANNELS = 3


def keys(master: bytes, nonce: int) -> dict:
    if not isinstance(master, (bytes, bytearray)) or len(master) != 32:
        raise ValueError("expected a 32-byte RGB master key")
    if not isinstance(nonce, int) or not 0 <= nonce < 2**128:
        raise ValueError("expected a uint128 nonce")
    salt = nonce.to_bytes(16, "big")
    root = HKDF(bytes(master), 32, salt, SHA256, context=RGB_ID + b"/master-root")
    image = [
        HKDF(root, 32, b"", SHA256, context=RGB_ID + b"/image-channel-" + bytes([channel]))
        for channel in range(CHANNELS)
    ]
    hider = HKDF(root, 32, b"", SHA256, context=RGB_ID + b"/data-hiding-root")
    return {"image": image, "hider": hider}


def hider_keys(hider_key: bytes) -> dict:
    if not isinstance(hider_key, (bytes, bytearray)) or len(hider_key) != 32:
        raise ValueError("expected a 32-byte RGB data-hiding capability")
    root = bytes(hider_key)
    domains = ("header-bootstrap", "header-final", "directory", "payload", "auth")
    return {
        domain.replace("-", "_"): HKDF(
            root, 32, b"", SHA256, context=RGB_ID + b"/hider/" + domain.encode("ascii")
        )
        for domain in domains
    }


def crypt(data: bytes, key: bytes) -> bytes:
    return AES.new(key, AES.MODE_CTR, nonce=b"", initial_value=0).encrypt(data)


def _header_key(capability: dict, stage: str) -> bytes:
    if stage == "bootstrap":
        return capability["header_bootstrap"]
    if stage == "final":
        return capability["header_final"]
    raise ValueError("header stage must be bootstrap or final")


def encode_header(codec: int, directory_length: int, payload_length: int, capability: dict, stage: str) -> bytes:
    if codec not in (0, 1):
        raise ValueError("invalid RGB directory codec")
    if not 0 <= directory_length < 2**32 or not 0 <= payload_length < 2**64:
        raise ValueError("RGB packet length outside header bounds")
    plain = HEADER.pack(RGB_MAGIC, codec, b"\x00\x00\x00", directory_length, payload_length)
    return crypt(plain, _header_key(capability, stage))


def _read_header(image: np.ndarray, capability: dict, stage: str, red_phase: int):
    height, width, channels = image.shape
    if image.dtype != np.uint8 or channels != 3 or height % 2 or width % 2:
        raise ValueError("expected even-sized uint8 HxWx3 RGB image")
    ys, xs = wire.grid((height, width), phase=red_phase)
    if len(ys) < HEADER_BYTES:
        raise ValueError("too few red-channel candidates for RGB header")
    raw = crypt(image[ys[:HEADER_BYTES], xs[:HEADER_BYTES], 0].tobytes(), _header_key(capability, stage))
    magic, codec, reserved, length, payload_length = HEADER.unpack(raw)
    bootstrap = HEADER_BYTES + length + TAG_BYTES
    if magic != RGB_MAGIC or codec not in (0, 1) or reserved != b"\x00\x00\x00" or bootstrap >= len(ys):
        raise ValueError("invalid RGB header, reserved bytes or directory bound")
    return ys, xs, codec, length, payload_length, bootstrap


def enumerate_slots(shape: tuple[int, int], labels_by_channel: list[np.ndarray], phases: tuple[int, int, int], red_header_count: int):
    height, width = map(int, shape)
    pixel_indices, channel_indices, shifts = [], [], []
    per_channel_counts = []
    for channel, phase in enumerate(phases):
        ys, xs = wire.grid((height, width), phase=phase)
        labels = np.asarray(labels_by_channel[channel], dtype=np.uint8)
        if len(labels) != len(ys) or np.any(labels >= len(wire.BOOK)):
            raise ValueError(f"RGB label count/codebook mismatch for channel {channel}")
        counts = wire.BOOK[labels, 0].astype(np.int32)
        start = red_header_count if channel == 0 else 0
        if not 0 <= start <= len(ys):
            raise ValueError("invalid red-channel bootstrap candidate count")
        per_channel_counts.append(counts)
        for i in range(start, len(ys)):
            n = int(counts[i])
            if n:
                pixel_indices.extend([int(ys[i] * width + xs[i])] * n)
                channel_indices.extend([channel] * n)
                shifts.extend(range(7, 7 - n, -1))
    return (
        np.asarray(pixel_indices, dtype=np.int64),
        np.asarray(channel_indices, dtype=np.uint8),
        np.asarray(shifts, dtype=np.uint8),
        per_channel_counts,
    )


def readbits(image: np.ndarray, positions, start: int = 0) -> np.ndarray:
    pixel, channel, shift = (part[start:] for part in positions[:3])
    flat = image.reshape(-1, 3)
    return (flat[pixel, channel] >> shift) & 1


def writebits(image: np.ndarray, positions, bits: np.ndarray, start: int = 0) -> None:
    pixel, channel, shift = (part[start:] for part in positions[:3])
    bits = np.asarray(bits, dtype=np.uint8)
    if bits.ndim != 1 or len(bits) != len(pixel):
        raise ValueError("RGB slot write length mismatch")
    flat = image.reshape(-1, 3)
    values = flat[pixel, channel].astype(np.uint8)
    mask = (255 ^ (1 << shift.astype(np.int64))).astype(np.uint8)
    flat[pixel, channel] = (values & mask) | (bits << shift)


def _tag_message(image: np.ndarray, capability: dict, stage: str,
                 phases: tuple[int, int, int, int], directory_length: int) -> bytes:
    red_phase = phases[0]
    ys, xs, _, _, _, bootstrap = _read_header(image, capability, stage, red_phase)
    tag_start = HEADER_BYTES + directory_length
    if bootstrap != tag_start + TAG_BYTES:
        raise ValueError("RGB tag framing mismatch")
    clean = image.copy()
    clean[ys[tag_start:bootstrap], xs[tag_start:bootstrap], 0] = 0
    prefix = struct.pack(">QQ4B", image.shape[0], image.shape[1], *phases)
    return prefix + clean.tobytes(order="C")


def tag(image: np.ndarray, capability: dict, stage: str,
        phases: tuple[int, int, int, int], directory_length: int) -> bytes:
    return hmac.new(
        capability["auth"],
        _tag_message(image, capability, stage, phases, directory_length),
        hashlib.sha256,
    ).digest()


def seal(image: np.ndarray, capability: dict, stage: str,
         phases: tuple[int, int, int, int], directory_length: int) -> None:
    ys, xs, _, _, _, bootstrap = _read_header(image, capability, stage, phases[0])
    start = HEADER_BYTES + directory_length
    image[ys[start:bootstrap], xs[start:bootstrap], 0] = np.frombuffer(
        tag(image, capability, stage, phases, directory_length), dtype=np.uint8
    )


def _unpack_labels(data: bytes, candidate_count: int):
    expected = (candidate_count + 1) // 2
    if len(data) != 8 + 3 * expected or data[:4] != RGB_MAGIC:
        raise ValueError("invalid RGB directory length or magic")
    phases = tuple(int(v) for v in data[4:8])
    if len(set(phases)) != 4 or set(phases) != set(range(PHASES)):
        raise ValueError("RGB phases must be a permutation of 0,1,2,3")
    labels = []
    offset = 8
    for _ in range(3):
        packed = np.frombuffer(data[offset:offset + expected], dtype=np.uint8)
        offset += expected
        values = np.stack((packed >> 4, packed & 15), axis=1).reshape(-1)
        if candidate_count % 2 and values[-1] != 0:
            raise ValueError("nonzero RGB label padding")
        values = values[:candidate_count]
        if np.any(values >= len(wire.BOOK)):
            raise ValueError("invalid RGB label class")
        labels.append(values.astype(np.uint8, copy=True))
    return phases, labels


def inspect(image: np.ndarray, capability: dict, stage: str = "final"):
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("expected uint8 RGB HxWx3")
    height, width, _ = image.shape
    if height % 2 or width % 2:
        raise ValueError("RGB EDR2 requires even image dimensions")
    valid, errors = [], []
    for red_phase in range(PHASES):
        try:
            ys, xs, codec, length, payload_length, bootstrap = _read_header(
                image, capability, stage, red_phase
            )
            actual_tag = image[
                ys[HEADER_BYTES + length:bootstrap],
                xs[HEADER_BYTES + length:bootstrap],
                0
            ].tobytes()
            remaining = [phase for phase in range(PHASES) if phase != red_phase]

            # Authenticate the phase tuple before decrypting/decompressing the directory.
            # There are 3*2 assignments for G/B once the red header location is known.
            authenticated = []
            for green_phase in remaining:
                for blue_phase in remaining:
                    if blue_phase == green_phase:
                        continue
                    calibration_phase = next(
                        phase for phase in remaining
                        if phase not in (green_phase, blue_phase)
                    )
                    phases = (red_phase, green_phase, blue_phase, calibration_phase)
                    expected_tag = tag(image, capability, stage, phases, length)
                    if hmac.compare_digest(actual_tag, expected_tag):
                        authenticated.append(phases)
            if len(authenticated) != 1:
                raise ValueError("RGB phase authentication yielded zero or multiple assignments")
            authenticated_phases = authenticated[0]

            directory_cipher = image[
                ys[HEADER_BYTES:HEADER_BYTES + length],
                xs[HEADER_BYTES:HEADER_BYTES + length],
                0
            ].tobytes()
            raw = crypt(directory_cipher, capability["directory"])
            candidate_count = len(wire.grid((height, width), phase=0)[0])
            expected_length = 8 + 3 * ((candidate_count + 1) // 2)
            if codec:
                dec = zlib.decompressobj()
                data = dec.decompress(raw, expected_length + 1)
                if len(data) != expected_length or not dec.eof or dec.unused_data or dec.unconsumed_tail:
                    raise ValueError("invalid bounded RGB compressed directory")
            else:
                data = raw
            phases, labels = _unpack_labels(data, candidate_count)
            if phases != authenticated_phases:
                raise ValueError("authenticated phase tuple differs from encrypted directory")
            positions = enumerate_slots(
                (height, width), labels, phases[:3], bootstrap
            )
            gross = int(sum(int(wire.BOOK[row, 0].sum()) for row in labels))
            foregone = int(wire.BOOK[labels[0][:bootstrap], 0].sum())
            stream = gross - foregone
            backup = 8 * bootstrap
            net = stream - backup
            if net <= 0 or payload_length > net or len(positions[0]) != stream:
                raise ValueError("invalid RGB net capacity or payload length")
            valid.append({
                "phases": phases[:3], "calibration_phase": phases[3],
                "labels": labels, "ys": ys, "xs": xs,
                "codec": codec, "directory_length": length,
                "payload_length": payload_length, "bootstrap": bootstrap,
                "positions": positions, "backup_bits": backup, "net": net,
                "gross_slots": gross, "foregone_slots": foregone,
            })
        except (ValueError, IndexError, struct.error, zlib.error) as exc:
            errors.append(exc)
    if len(valid) == 1:
        return valid[0]
    if len(valid) > 1:
        raise ValueError("ambiguous authenticated RGB phase assignment")
    raise ValueError("no valid authenticated RGB packet") from (errors[-1] if errors else None)


def embed(reserved: np.ndarray, payload: np.ndarray, capability: dict) -> np.ndarray:
    q = inspect(reserved, capability, stage="bootstrap")
    payload = np.asarray(payload)
    if payload.ndim != 1 or np.any((payload != 0) & (payload != 1)):
        raise ValueError("RGB payload must be a one-dimensional binary sequence")
    if len(payload) > q["net"]:
        raise ValueError("RGB payload exceeds aggregate net capacity")
    plain = np.pad(payload.astype(np.uint8), (0, q["net"] - len(payload)))
    cipher = np.unpackbits(np.frombuffer(
        crypt(np.packbits(plain).tobytes(), capability["payload"]), dtype=np.uint8
    ))[:q["net"]]
    out = reserved.copy()
    writebits(out, q["positions"], cipher, start=q["backup_bits"])
    header = encode_header(q["codec"], q["directory_length"], len(payload), capability, "final")
    out[q["ys"][:HEADER_BYTES], q["xs"][:HEADER_BYTES], 0] = np.frombuffer(header, dtype=np.uint8)
    seal(out, capability, "final", (*q["phases"], q["calibration_phase"]), q["directory_length"])
    return out
