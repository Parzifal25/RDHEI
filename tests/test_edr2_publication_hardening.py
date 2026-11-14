"""Assert-based publication-hardening tests for the EDR2 research branch.

Generated arrays are unit-test fixtures only. They are not paper-facing samples.
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
    assert np.all(np.diff(np.unique(y)) == 2)
    assert np.all(np.diff(np.unique(x)) == 2)

    py, px = predictor.coords((512, 512))
    np.testing.assert_array_equal(py, y)
    np.testing.assert_array_equal(px, x)

    # No mutable center may occur in another center's 3x3 predictor patch.
    candidate_set = set(zip(y.tolist(), x.tolist()))
    for cy, cx in candidate_set:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    assert (cy + dy, cx + dx) not in candidate_set


def test_step_two_lattice_handles_small_and_invalid_shapes():
    y, x = wire.grid((4, 4))
    assert len(y) == len(x) == 1
    with pytest.raises(ValueError):
        wire.grid((8, 8, 3))


def test_wire_allocation_matches_independent_closed_table():
    for error in range(256):
        assert wire.allocation(error) == run_gate.reference_allocation(error)


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
        wire.PROTOCOL_MAGIC, 0, b"\x01\x00\x00", 1, 0
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
    assert predictor.packlabels(np.asarray([0, 14, 4], dtype=np.uint8)) == bytes(
        (0x0E, 0x40)
    )
    with pytest.raises(ValueError, match="invalid label"):
        predictor.packlabels(np.asarray([len(wire.BOOK)], dtype=np.uint8))


def test_prepared_state_identity_binds_dimensions_and_pixel_bytes():
    image = np.arange(64, dtype=np.uint8).reshape(8, 8)
    digest = protocol._image_identity(image)
    assert digest == protocol._image_identity(image.copy())
    assert digest != protocol._image_identity(image.reshape(4, 16))
    changed = image.copy()
    changed[0, 0] ^= 1
    assert digest != protocol._image_identity(changed)


def test_paper_corpus_rejects_synthetic_and_unreviewed_inputs(tmp_path):
    baseline = tmp_path / "kodak_gray"
    expanded = tmp_path / "usc_sipi_gray"
    volume = expanded / "textures"
    baseline.mkdir()
    volume.mkdir(parents=True)

    # Generated data are fixtures for filtering code, never experimental samples.
    base_pixels = np.arange(100, dtype=np.uint8).reshape(10, 10)
    baseline_path = baseline / "Airplane.png"
    synthetic_path = baseline / "constant128.png"
    unreviewed_path = expanded / "unreviewed.tiff"
    allowlisted_path = volume / "texture_01.tiff"

    Image.fromarray(base_pixels).save(baseline_path)
    Image.fromarray(np.full((10, 10), 128, dtype=np.uint8)).save(synthetic_path)
    Image.fromarray(np.flipud(base_pixels)).save(unreviewed_path)
    Image.fromarray(np.fliplr(base_pixels)).save(allowlisted_path)

    allowlist = {
        "images": [{
            "path": "textures/texture_01.tiff",
            "sha256": hashlib.sha256(allowlisted_path.read_bytes()).hexdigest(),
            "classification": "natural",
            "curation_note": "Human-reviewed native USC-SIPI grayscale image.",
        }]
    }
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps(allowlist), encoding="utf-8"
    )

    corpus, skipped, duplicates, inventory, missing = run_gate.load_corpus(
        [baseline, expanded], allow_missing_baseline=True
    )
    assert {row["name"] for row in corpus} == {
        "Airplane.png", "textures/texture_01.tiff"
    }
    assert any("synthetic control explicitly excluded" in row["reason"] for row in skipped)
    assert any(
        row["relative_path"] == "unreviewed.tiff"
        and "not curator-allowlisted" in row["reason"]
        for row in skipped
    )
    assert duplicates == []
    assert len(inventory) == len(corpus)
    assert missing == sorted(run_gate.BASELINE_STEMS - {"airplane"})


def test_allowlisted_image_hash_mismatch_fails_closed(tmp_path):
    expanded = tmp_path / "usc_sipi_gray"
    volume = expanded / "textures"
    volume.mkdir(parents=True)
    image_path = volume / "candidate.tiff"
    Image.fromarray(np.arange(100, dtype=np.uint8).reshape(10, 10)).save(image_path)
    allowlist = {
        "images": [{
            "path": "textures/candidate.tiff",
            "sha256": "0" * 64,
            "classification": "natural",
            "curation_note": "Deliberate hash mismatch test.",
        }]
    }
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps(allowlist), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="file hash changed"):
        run_gate.load_corpus([expanded], allow_missing_baseline=True)
