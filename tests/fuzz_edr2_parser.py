#!/usr/bin/env python3
"""Coverage-guided fuzz target for the authenticated EDR2 grayscale parser.

Build a valid authenticated packet fixture, then mutate header fields and
construct authenticated malformed directories so the target reaches
post-authentication framing/decompression/label validation.

Run:
  python -m pip install atheris
  python tests/fuzz_edr2_parser.py --write-seed-dir /tmp/edr2-fuzz-corpus
  python tests/fuzz_edr2_parser.py -max_len=4096 -runs=20000 /tmp/edr2-fuzz-corpus
"""
from __future__ import annotations

import hashlib
import sys
import zlib
from pathlib import Path

import numpy as np
import atheris

EDR2_ROOT = Path(__file__).resolve().parents[1] / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2_ROOT))

with atheris.instrument_imports():
    import protocol
    import wire

ORIGINAL = np.full((128, 128), 128, dtype=np.uint8)
MASTER = bytes(range(32))
NONCE = 0x45445232000000000000000000000001

PREPARED = protocol.prepare(ORIGINAL)
if PREPARED["net"] <= 0:
    raise RuntimeError("fuzz fixture must have positive capacity")
_RESERVED, OWNER = protocol.reserve(ORIGINAL, MASTER, NONCE, prepared=PREPARED)
CAPABILITY = wire.hider_keys(OWNER["hider"])
_BASE = wire.embed(_RESERVED, np.asarray([1, 0, 1], dtype=np.uint8), CAPABILITY)
_BASE_INFO = wire.inspect(_BASE, CAPABILITY)
_BASE_PHASE = int(_BASE_INFO["phase"])
_BASE_Y = _BASE_INFO["y"]
_BASE_X = _BASE_INFO["x"]
_EXPECTED_DIRECTORY_BYTES = (len(_BASE_Y) + 1) // 2
_MAX_DIRECTORY_BYTES = len(_BASE_Y) - wire.HEADER_BYTES - wire.TAG_BYTES - 1


def _byte(data: bytes, index: int, default: int = 0) -> int:
    return data[index] if index < len(data) else default


def _valid_compressed_directory() -> bytes:
    labels = np.asarray(_BASE_INFO["labels"], dtype=np.uint8)
    if len(labels) % 2:
        labels = np.pad(labels, (0, 1))
    packed = ((labels[0::2] << 4) | labels[1::2]).astype(np.uint8).tobytes()
    return zlib.compress(packed, level=9)


def write_seed_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    compressed = _valid_compressed_directory()
    if len(compressed) > 65535:
        raise ValueError("fuzz seed directory too large for header field")
    # mode=1, canonical reserved bytes, compressed directory length and bytes.
    # The trailing four bytes plus flag select an in-range zero payload length.
    seed = (
        bytes((1, 1, 0, 0))
        + len(compressed).to_bytes(2, "big")
        + compressed
        + bytes((0, 0, 0, 0, 1))
    )
    (directory / "valid-compressed-directory.seed").write_bytes(seed)
    print(
        f"wrote valid compressed directory seed: {directory / 'valid-compressed-directory.seed'} "
        f"({len(seed)} bytes)"
    )


def TestOneInput(data: bytes) -> None:
    """Fuzz one canonical image packet; ValueError is expected rejection."""
    if not data:
        return

    packet = _BASE.copy()

    # Mutate selected image bytes, then authenticate the packet, so fuzzing
    # reaches parser paths rather than stopping at an expected MAC failure.
    for offset in range(min(16, len(data) // 2)):
        index = int.from_bytes(data[offset * 2:offset * 2 + 2], "big") % packet.size
        packet.reshape(-1)[index] ^= _byte(data, 32 + offset) or 1

    mode = _byte(data, 0) & 1
    reserved = b"\x00\x00\x00" if (_byte(data, 1) & 3) else bytes(
        (_byte(data, 1), _byte(data, 2), _byte(data, 3))
    )
    max_length = max(0, min(_MAX_DIRECTORY_BYTES, 65535))
    if mode == 0:
        directory_length = _EXPECTED_DIRECTORY_BYTES
        start = 4
    else:
        directory_length = int.from_bytes(data[4:6].ljust(2, b"\x00"), "big") % (max_length + 1)
        start = 6

    raw_directory = data[start:start + directory_length]
    if len(raw_directory) < directory_length:
        raw_directory = raw_directory + bytes(directory_length - len(raw_directory))

    if mode == 0:
        # Raw directory path requires the exact packed-label byte count.
        directory_length = _EXPECTED_DIRECTORY_BYTES
        raw_directory = (raw_directory + bytes(directory_length))[:directory_length]

    # Payload controls follow the directory so they do not overwrite directory
    # seed bytes. Mutations choose both in-range and deliberately invalid lengths.
    payload_offset = start + directory_length
    payload_raw = data[payload_offset:payload_offset + 4].ljust(4, b"\x00")
    payload_length = int.from_bytes(payload_raw, "big")
    if _byte(data, payload_offset + 4) & 1:
        payload_length %= max(1, int(_BASE_INFO["net"]) + 1)
    else:
        payload_length = int(_BASE_INFO["net"]) + (payload_length & 255) + 1

    header = wire.HEADER.pack(
        wire.PROTOCOL_MAGIC,
        mode,
        reserved,
        directory_length,
        payload_length,
    )
    try:
        encrypted_header = wire.crypt(
            header, wire._header_key(CAPABILITY, "final")
        )
        packet[_BASE_Y[:wire.HEADER_BYTES], _BASE_X[:wire.HEADER_BYTES]] = np.frombuffer(
            encrypted_header, dtype=np.uint8
        )
        encrypted_directory = wire.crypt(raw_directory, CAPABILITY["directory"])
        packet[
            _BASE_Y[wire.HEADER_BYTES:wire.HEADER_BYTES + directory_length],
            _BASE_X[wire.HEADER_BYTES:wire.HEADER_BYTES + directory_length],
        ] = np.frombuffer(encrypted_directory, dtype=np.uint8)
        wire.seal(
            packet,
            CAPABILITY,
            header_stage="final",
            phase=_BASE_PHASE,
        )
    except ValueError:
        try:
            wire.inspect(packet, CAPABILITY)
        except ValueError:
            return
        return

    try:
        wire.inspect(packet, CAPABILITY)
    except ValueError:
        return


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--write-seed-dir":
        write_seed_dir(Path(sys.argv[2]))
        return

    print(
        "EDR2 parser fuzz fixture:",
        {
            "shape": list(ORIGINAL.shape),
            "base_net_bits": int(_BASE_INFO["net"]),
            "base_directory_bytes": int(_BASE_INFO["length"]),
            "phase": _BASE_PHASE,
            "master_key_sha256": hashlib.sha256(MASTER).hexdigest(),
            "unique_fuzz_nonce": f"{NONCE:032x}",
        },
        flush=True,
    )
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
