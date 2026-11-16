#!/usr/bin/env python3
"""Coverage-guided fuzz target for the authenticated EDR2 grayscale parser.

The harness creates a valid local packet once, then uses Atheris inputs to
construct authenticated malformed headers/directories and mutate carrier and
non-carrier bytes. ValueError is the expected packet-rejection outcome; any
other uncaught exception is a fuzzer finding.

Run:
  python -m pip install atheris
  python tests/fuzz_edr2_parser.py tests/fuzz_corpus -artifact_prefix=/tmp/edr2-crash-
"""
from __future__ import annotations

import hashlib
import struct
import sys

import numpy as np

import atheris

with atheris.instrument_imports():
    from final_rdhei_protocol_gate_20261022 import protocol, wire

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


def TestOneInput(data: bytes) -> None:
    """Fuzz one canonical image packet without allowing invalid input to escape."""
    if not data:
        return

    packet = _BASE.copy()

    # Mutate a deterministic set of non-carrier bytes, then authenticate the
    # resulting packet so the receiver progresses beyond the HMAC check.
    for offset in range(min(16, len(data) // 2)):
        index = int.from_bytes(data[offset * 2:offset * 2 + 2], "big") % packet.size
        packet.reshape(-1)[index] ^= _byte(data, 32 + offset) or 1

    mode = _byte(data, 0) & 1
    reserved = b"\\x00\\x00\\x00" if (_byte(data, 1) & 3) else bytes(
        (_byte(data, 1), _byte(data, 2), _byte(data, 3))
    )
    max_length = max(0, min(_MAX_DIRECTORY_BYTES, 65535))
    if mode == 0:
        directory_length = _EXPECTED_DIRECTORY_BYTES
        start = 4
    else:
        directory_length = int.from_bytes(data[4:6].ljust(2, b"\\x00"), "big") % (max_length + 1)
        start = 6

    raw_directory = data[start:start + directory_length]
    if len(raw_directory) < directory_length:
        raw_directory = raw_directory + bytes(directory_length - len(raw_directory))

    if mode == 0:
        # Raw directory path: exact packed-label byte count is required.
        directory_length = _EXPECTED_DIRECTORY_BYTES
        raw_directory = (raw_directory + bytes(directory_length))[:directory_length]

    payload_length = int.from_bytes(data[6:10].ljust(4, b"\\x00"), "big")
    # Keep some cases in range and some deliberately over capacity.
    if _byte(data, 10) & 1:
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
        # Invalid lengths or noncanonical framing are ordinary rejections.
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
