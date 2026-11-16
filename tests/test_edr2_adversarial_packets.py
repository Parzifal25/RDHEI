"""Adversarial tests for EDR2 packet framing, authentication and parsing.

These tests are deterministic regression checks, not a substitute for independent
cryptographic review or coverage-guided fuzzing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2))

import protocol  # noqa: E402
import wire  # noqa: E402


def make_packet():
    """Build one valid packet using the frozen checkpoint and a small smooth image."""
    original = np.full((128, 128), 128, dtype=np.uint8)
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F001
    prepared = protocol.prepare(original)
    assert prepared["net"] > 0
    reserved, owner = protocol.reserve(original, master, nonce, prepared=prepared)
    capability = wire.hider_keys(owner["hider"])
    payload = np.asarray([1, 0, 1, 1, 0, 0, 1, 1, 1], dtype=np.uint8)
    marked = wire.embed(reserved, payload, capability)
    parsed = wire.inspect(marked, capability)
    return original, master, nonce, payload, capability, marked, parsed


@pytest.mark.parametrize("region", ["header", "directory", "tag", "payload", "image_body"])
def test_any_authenticated_region_tampering_is_rejected(region):
    _, _, _, _, capability, marked, parsed = make_packet()
    changed = marked.copy()

    if region == "header":
        y, x = int(parsed["y"][0]), int(parsed["x"][0])
        changed[y, x] ^= 0x01
    elif region == "directory":
        assert parsed["length"] > 0
        y = int(parsed["y"][wire.HEADER_BYTES])
        x = int(parsed["x"][wire.HEADER_BYTES])
        changed[y, x] ^= 0x01
    elif region == "tag":
        tag_index = wire.HEADER_BYTES + int(parsed["length"])
        y, x = int(parsed["y"][tag_index]), int(parsed["x"][tag_index])
        changed[y, x] ^= 0x01
    elif region == "payload":
        slot_index = int(parsed["backup"])
        assert slot_index < len(parsed["positions"][0])
        pixel = int(parsed["positions"][0][slot_index])
        shift = int(parsed["positions"][1][slot_index])
        changed.reshape(-1)[pixel] ^= 1 << shift
    else:
        # The packet MAC covers the complete marked image, not just carrier bytes.
        changed[0, 0] ^= 0x01

    with pytest.raises(ValueError):
        wire.inspect(changed, capability)


def test_wrong_key_and_wrong_nonce_are_rejected_before_recovery():
    _, master, nonce, _, _, marked, _ = make_packet()
    with pytest.raises(ValueError):
        protocol.receive(marked, bytes(reversed(master)), nonce)
    with pytest.raises(ValueError):
        protocol.receive(marked, master, nonce + 1)


def test_distinct_nonces_derive_distinct_grayscale_packet_keys():
    master = bytes(range(32))
    first = wire.keys(master, 7)
    second = wire.keys(master, 8)
    assert first["image"] != second["image"]
    assert first["hider"] != second["hider"]
    # The KDF is deterministic: uniqueness is an operational nonce-allocation
    # requirement, not something this stateless packet function can enforce.
    assert wire.keys(master, 7) == first


@pytest.mark.parametrize(
    "mode,reserved,directory_length",
    [
        (2, b"\\x00\\x00\\x00", 0),       # unknown codec
        (0, b"\\x01\\x00\\x00", 0),       # nonzero reserved header field
        (0, b"\\x00\\x00\\x00", 2**32 - 1),  # impossible directory bound
    ],
)
def test_framing_rejects_malformed_encrypted_header(mode, reserved, directory_length):
    capability = wire.hider_keys(bytes(reversed(range(32))))
    image = np.zeros((128, 128), dtype=np.uint8)
    y, x = wire.grid(image.shape, phase=0)
    plaintext = wire.HEADER.pack(
        wire.PROTOCOL_MAGIC, mode, reserved, directory_length, 0
    )
    ciphertext = wire.crypt(plaintext, capability["header_bootstrap"])
    image[y[:wire.HEADER_BYTES], x[:wire.HEADER_BYTES]] = np.frombuffer(
        ciphertext, dtype=np.uint8
    )
    with pytest.raises(ValueError):
        wire.framing(image, capability, header_stage="bootstrap", phase=0)


def test_authenticated_malformed_zlib_stream_is_rejected_as_value_error():
    _, _, _, _, capability, marked, parsed = make_packet()
    malformed = bytes(8)  # Invalid zlib header; the packet tag below is recomputed.
    changed = marked.copy()
    y, x = parsed["y"], parsed["x"]
    directory_length = len(malformed)
    bootstrap = wire.HEADER_BYTES + directory_length + wire.TAG_BYTES
    assert bootstrap < len(y)

    header = wire.encode_header(
        1, directory_length, parsed["plen"], capability, "final"
    )
    changed[y[:wire.HEADER_BYTES], x[:wire.HEADER_BYTES]] = np.frombuffer(
        header, dtype=np.uint8
    )
    changed[
        y[wire.HEADER_BYTES:wire.HEADER_BYTES + directory_length],
        x[wire.HEADER_BYTES:wire.HEADER_BYTES + directory_length],
    ] = np.frombuffer(
        wire.crypt(malformed, capability["directory"]), dtype=np.uint8
    )
    changed[
        y[wire.HEADER_BYTES + directory_length:bootstrap],
        x[wire.HEADER_BYTES + directory_length:bootstrap],
    ] = 0
    wire.seal(changed, capability, header_stage="final", phase=parsed["phase"])

    # The authentication tag is valid for the malformed directory. Rejection
    # therefore exercises the post-authentication decompression parser path.
    with pytest.raises(ValueError):
        wire.inspect(changed, capability, header_stage="final")


def test_seeded_packet_mutation_fuzz_rejects_without_unexpected_exceptions():
    _, _, _, _, capability, marked, _ = make_packet()
    rng = np.random.default_rng(20261116)
    flat_size = marked.size

    # Every mutation is a one-bit change to a different image byte. The test
    # exercises framing/authentication rejection on a reproducible set of inputs.
    indices = rng.choice(flat_size, size=64, replace=False)
    for index in indices:
        changed = marked.copy()
        changed.reshape(-1)[int(index)] ^= 1 << int(rng.integers(0, 8))
        with pytest.raises(ValueError):
            wire.inspect(changed, capability)

    for shape in ((4, 4), (16, 32), (128, 128)):
        random_packet = rng.integers(0, 256, size=shape, dtype=np.uint8)
        with pytest.raises(ValueError):
            wire.inspect(random_packet, capability)
