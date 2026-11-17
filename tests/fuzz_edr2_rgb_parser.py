#!/usr/bin/env python3
"""Coverage-guided fuzz target for authenticated CC-EDR2-RGB packet parsing.

The seed is a valid RGB packet generated with a deterministic spatial predictor.
For each fuzz input, mutations are rebuilt into authenticated packets so the
parser proceeds beyond HMAC validation and exercises framing, phase discovery,
directory decompression, label parsing, and capacity validation.

Run:
  python -m pip install atheris
  python tests/fuzz_edr2_rgb_parser.py -max_len=4096 -runs=20000 /tmp/edr2-rgb-fuzz-corpus
"""
from __future__ import annotations

import sys
import struct
import zlib
from pathlib import Path

import numpy as np
import atheris

ROOT = Path(__file__).resolve().parents[1]
EDR2_ROOT = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EDR2_ROOT))

with atheris.instrument_imports():
    import predictor
    import rgb_protocol
    import rgb_wire
    import wire


def fake_model():
    return object()


def fake_spatial(image, ys, xs, active_model=None):
    # Deterministic fixture prediction; parser fuzzing does not measure CNN quality.
    return np.full(len(ys), 128.0, dtype=np.float32)


predictor.model = fake_model
predictor.predict = fake_spatial

ORIGINAL = np.empty((128, 128, 3), dtype=np.uint8)
ORIGINAL[:, :, 0] = 100
ORIGINAL[:, :, 1] = 120
ORIGINAL[:, :, 2] = 140
MASTER = bytes(range(32))
NONCE = 0x45445232524742000000000000000001

PREPARED = rgb_protocol.prepare(ORIGINAL)
if PREPARED["net"] <= 0:
    raise RuntimeError("RGB parser fuzz fixture must have positive net capacity")
_RESERVED, OWNER = rgb_protocol.reserve(ORIGINAL, MASTER, NONCE, prepared=PREPARED)
CAPABILITY = rgb_wire.hider_keys(OWNER["hider"])
_BASE = rgb_protocol.embed(
    _RESERVED, np.asarray([1, 0, 1, 1, 0, 1, 0], dtype=np.uint8), OWNER["hider"]
)
_BASE_INFO = rgb_wire.inspect(_BASE, CAPABILITY, stage="final")
_PHASES = (
    int(_BASE_INFO["phases"][0]),
    int(_BASE_INFO["phases"][1]),
    int(_BASE_INFO["phases"][2]),
    int(_BASE_INFO["calibration_phase"]),
)
_RED_Y, _RED_X = wire.grid(ORIGINAL.shape[:2], phase=_PHASES[0])
_CANDIDATE_COUNT = len(_RED_Y)


def _byte(data: bytes, index: int, default: int = 0) -> int:
    return data[index] if index < len(data) else default


def _authenticated_malformed(data: bytes) -> np.ndarray:
    """Build malformed but correctly authenticated RGB packet from fuzz bytes."""
    packet = _BASE.copy()
    phases = _PHASES
    ys, xs = wire.grid(ORIGINAL.shape[:2], phase=phases[0])

    # First perturb ordinary image/body bytes. Re-sealing ensures that
    # authentication succeeds and deeper validation is exercised.
    for offset in range(min(12, len(data) // 2)):
        flat_index = int.from_bytes(data[2 * offset:2 * offset + 2], "big") % packet.size
        channel = flat_index % 3
        pixel = flat_index // 3
        value = _byte(data, 24 + offset) or 1
        packet.reshape(-1, 3)[pixel, channel] ^= value

    mode = _byte(data, 0) & 1
    # Keep all lengths small and in-bounds; the objective is to fuzz parser
    # semantics, not allocate unbounded memory.
    if mode:
        malformed_directory = data[1:1 + min(64, max(1, len(data) - 1))]
        if not malformed_directory:
            malformed_directory = b"\x00"
        codec = 1  # compressed directory; arbitrary bytes exercise bounded zlib parser
    else:
        malformed_directory = data[1:1 + min(64, max(1, len(data) - 1))]
        if not malformed_directory:
            malformed_directory = b"\x00"
        codec = 0  # raw directory; arbitrary lengths/bytes exercise structural parser

    directory_length = len(malformed_directory)
    bootstrap = rgb_wire.HEADER_BYTES + directory_length + rgb_wire.TAG_BYTES
    if bootstrap >= len(ys):
        malformed_directory = malformed_directory[:max(1, len(ys) - rgb_wire.HEADER_BYTES - rgb_wire.TAG_BYTES - 1)]
        directory_length = len(malformed_directory)
        bootstrap = rgb_wire.HEADER_BYTES + directory_length + rgb_wire.TAG_BYTES

    payload_length = int.from_bytes(data[80:88].ljust(8, b"\x00"), "big")
    payload_length %= max(1, int(_BASE_INFO["net"]) + 2)
    header = rgb_wire.encode_header(
        codec, directory_length, payload_length, CAPABILITY, "final"
    )
    packet[ys[:rgb_wire.HEADER_BYTES], xs[:rgb_wire.HEADER_BYTES], 0] = np.frombuffer(
        header, dtype=np.uint8
    )
    packet[
        ys[rgb_wire.HEADER_BYTES:rgb_wire.HEADER_BYTES + directory_length],
        xs[rgb_wire.HEADER_BYTES:rgb_wire.HEADER_BYTES + directory_length],
        0,
    ] = np.frombuffer(
        rgb_wire.crypt(malformed_directory, CAPABILITY["directory"]),
        dtype=np.uint8,
    )
    # The authentication trailer is recomputed over the entire mutated packet.
    packet[
        ys[rgb_wire.HEADER_BYTES + directory_length:bootstrap],
        xs[rgb_wire.HEADER_BYTES + directory_length:bootstrap],
        0,
    ] = 0
    rgb_wire.seal(packet, CAPABILITY, "final", phases, directory_length)
    return packet


def TestOneInput(data: bytes) -> None:
    if not data:
        return
    packet = _authenticated_malformed(data)
    try:
        rgb_wire.inspect(packet, CAPABILITY, stage="final")
    except (ValueError, IndexError, struct.error, zlib.error):
        return


def main() -> None:
    print(
        "CC-EDR2-RGB parser fuzz fixture:",
        {
            "shape": list(ORIGINAL.shape),
            "positive_net_capacity_bits": int(_BASE_INFO["net"]),
            "phase_tuple": list(_PHASES),
            "candidate_count": int(_CANDIDATE_COUNT),
            "directory_bytes": int(_BASE_INFO["directory_length"]),
        },
        flush=True,
    )
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
