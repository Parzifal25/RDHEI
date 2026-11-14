"""Publication-hardening tests for the EDR2 natural-image protocol branch.

These tests use tiny generated arrays only as unit-test fixtures. They are not
members of the paper-facing image corpus and cannot enter run_gate.py metrics.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EDR2_DIR = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2_DIR))

import predictor
import protocol
import run_gate
import wire


def test_step_two_lattice_is_maximal_for_the_fixed_three_by_three_context():
    y, x = wire.grid((512, 512))
    assert len(y) == 65_025
    assert len(x) == 65_025
    assert (int(y.min()), int(y.max())) == (1, 509)
    assert (int(x.min()), int(x.max())) == (1, 509)
    assert len(np.unique(y)) == 255
    assert len(np.unique(x)) == 255
    assert np.all(np.diff(np.unique(y)) == 2)
    assert np.all(np.diff(np.unique(x)) == 2)

    py, px = predictor.coords((512, 512))
    np.testing.assert_array_equal(py, y)
    np.testing.assert_array_equal(px, x)

    # No candidate centre may lie in another candidate's 3x3 masked context.
    candidate_set = set(zip(y.tolist(), x.tolist()))
    for cy, cx in candidate_set:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                assert (cy + dy, cx + dx) not in candidate_set


def test_step_two_lattice_handles_small_and_invalid_shapes():
    y, x = wire.grid((4, 4))
    assert len(y) == 1 and len(x) == 1
    with pytest.raises(ValueError):
        wire.grid((8, 8, 3))


def test_wire_allocation_matches_the_production_label_map_for_every_error():
    from src.rdhei_core import _compute_bpp_and_range

    for error in range(256):
        assert wire.allocation(error) == _compute_bpp_and_range(error)


def test_encrypted_header_requires_zero_reserved_bytes():
    capability = wire.hider_keys(bytes(range(32)))
    image = np.zeros((512, 512), dtype=np.uint8)
    y, x = wire.grid(image.shape)

    valid = wire.encode_header(0, 1, 0, capability, "bootstrap")
    image[y[:wire.HEADER_BYTES], x[:wire.HEADER_BYTES]] = np.frombuffer(
        valid, dtype=np.uint8
    )
    _, _, mode, length, payload_length, h = wire.framing(
        image, capability, header_stage="bootstrap"
    )
    assert (mode, length, payload_length) == (0, 1, 0)
    assert h == wire.HEADER_BYTES + 1 + wire.TAG_BYTES

    malformed_plain = wire.HEADER.pack(
        wire.PROTOCOL_MAGIC, 0, b"\\x01\\x00\\x00", 1, 0
    )
    malformed_cipher = wire.crypt(
        malformed_plain, capability["header_bootstrap"]
    )
    image[y[:wire.HEADER_BYTES], x[:wire.HEADER_BYTES]] = np.frombuffer(
        malformed_cipher, dtype=np.uint8
    )
    with pytest.raises(ValueError, match="reserved bytes"):
        wire.framing(image, capability, header_stage="bootstrap")


def test_label_nibble_padding_is_canonical_and_invalid_classes_reject():
    packed = predictor.packlabels(np.asarray([0, 14, 4], dtype=np.uint8))
    assert packed == bytes((0x0E, 0x40))
    with pytest.raises(ValueError, match="invalid label"):
        predictor.packlabels(np.asarray([len(wire.BOOK)], dtype=np.uint8))


def test_image_identity_binds_dimensions_and_pixel_bytes():
    image = np.arange(64, dtype=np.uint8).reshape(8, 8)
    same = image.copy()
    different_shape = image.reshape(4, 16)
    different_pixels = image.copy()
    different_pixels[0, 0] ^= 1

    digest = protocol._image_identity(image)
    assert digest == protocol._image_identity(same)
    assert digest != protocol._image_identity(different_shape)
    assert digest != protocol._image_identity(different_pixels)


def test_paper_corpus_rejects_synthetic_and_unreviewed_inputs(tmp_path):
    baseline = tmp_path / "kodak_gray"
    expanded = tmp_path / "usc_sipi_gray"
    volume = expanded / "textures"
    baseline.mkdir()
    volume.mkdir(parents=True)

    # Test-only image fixtures validate corpus filtering; they are not reported.
    baseline_image = np.arange(100, dtype=np.uint8).reshape(10, 10)
    synthetic_image = np.full((10, 10), 128, dtype=np.uint8)
    unreviewed_image = np.flipud(baseline_image)
    allowlisted_image = np.fliplr(baseline_image)

    baseline_path = baseline / "Airplane.png"
    synthetic_path = baseline / "constant128.png"
    unreviewed_path = expanded / "unreviewed.tiff"
    allowlisted_path = volume / "texture_01.tiff"

    Image.fromarray(baseline_image, mode="L").save(baseline_path)
    Image.fromarray(synthetic_image, mode="L").save(synthetic_path)
    Image.fromarray(unreviewed_image, mode="L").save(unreviewed_path)
    Image.fromarray(allowlisted_image, mode="L").save(allowlisted_path)

    allowlist = {
        "images": [
            {
                "path": "textures/texture_01.tiff",
                "sha256": hashlib.sha256(allowlisted_path.read_bytes()).hexdigest(),
                "classification": "natural",
                "curation_note": "Human-reviewed native USC-SIPI grayscale image.",
            }
        ]
    }
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps(allowlist), encoding="utf-8"
    )

    corpus, skipped, duplicates, inventory, missing = run_gate.load_corpus(
        [baseline, expanded], allow_missing_baseline=True
    )
    names = {row["name"] for row in corpus}
    assert "Airplane.png" in names
    assert "textures/texture_01.tiff" in names
    assert not any("constant128" in row["relative_path"] for row in skipped)
    assert any(
        "synthetic control explicitly excluded" in row["reason"]
        for row in skipped
    )
    assert any(
        row["relative_path"] == "unreviewed.tiff"
        and "not curator-allowlisted" in row["reason"]
        for row in skipped
    )
    assert len(duplicates) == 0
    assert len(inventory) == len(corpus)
    assert missing == sorted(run_gate.BASELINE_STEMS - {"airplane"})


def test_allowlisted_image_hash_mismatch_fails_closed(tmp_path):
    expanded = tmp_path / "usc_sipi_gray"
    volume = expanded / "textures"
    volume.mkdir(parents=True)
    image_path = volume / "candidate.tiff"
    Image.fromarray(np.arange(100, dtype=np.uint8).reshape(10, 10), mode="L").save(
        image_path
    )
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps({
            "images": [{
                "path": "textures/candidate.tiff",
                "sha256": "0" * 64,
                "classification": "natural",
                "curation_note": "Test mismatch.",
            }]
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="file hash changed"):
        run_gate.load_corpus([expanded], allow_missing_baseline=True)
