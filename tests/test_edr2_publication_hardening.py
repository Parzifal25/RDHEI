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


def test_all_four_step_two_lattices_are_maximal_and_context_safe():
    for phase in range(wire.SAFE_ZONE_PHASES):
        y, x = wire.grid((512, 512), phase=phase)
        assert len(y) == 65_025
        assert len(x) == 65_025
        assert len(np.unique(y)) == 255
        assert len(np.unique(x)) == 255
        assert np.all(np.diff(np.unique(y)) == 2)
        assert np.all(np.diff(np.unique(x)) == 2)

        py, px = predictor.coords((512, 512), phase=phase)
        np.testing.assert_array_equal(py, y)
        np.testing.assert_array_equal(px, x)

        # No mutable centre may occur in another centre's 3x3 predictor patch.
        candidate_set = set(zip(y.tolist(), x.tolist()))
        for cy, cx in candidate_set:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy or dx:
                        assert (cy + dy, cx + dx) not in candidate_set


def test_step_two_lattice_handles_small_and_invalid_shapes():
    y, x = wire.grid((4, 4))
    assert len(y) == len(x) == 1
    with pytest.raises(ValueError, match="grayscale"):
        wire.grid((8, 8, 3))
    with pytest.raises(ValueError, match="even image dimensions"):
        wire.grid((511, 512))
    with pytest.raises(ValueError, match="even image dimensions"):
        wire.grid((512, 511))


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



def test_authenticated_header_location_discovers_each_of_four_lattice_phases():
    original = np.full((128, 128), 128, dtype=np.uint8)
    master = bytes(reversed(range(32)))
    payload = np.asarray([1, 0, 1, 1, 0, 0, 1], dtype=np.uint8)

    for phase in range(wire.SAFE_ZONE_PHASES):
        nonce = 0x2030405060708090A0B0C0D0E0F00000 + phase
        prepared = protocol.prepare(original, phase_override=phase)
        assert prepared["phase"] == phase
        assert prepared["net"] > 0
        reserved, owner_capability = protocol.reserve(
            original, master, nonce, prepared=prepared
        )
        hider_capability = wire.hider_keys(owner_capability["hider"])
        discovered = wire.inspect(
            reserved, hider_capability, header_stage="bootstrap"
        )
        assert discovered["phase"] == phase

        marked = wire.embed(reserved, payload, hider_capability)
        final = wire.inspect(marked, hider_capability, header_stage="final")
        assert final["phase"] == phase
        recovered, extracted = protocol.receive(marked, master, nonce)
        np.testing.assert_array_equal(recovered, original)
        np.testing.assert_array_equal(extracted, payload)

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


def test_paper_corpus_rejects_synthetic_and_unreviewed_inputs(tmp_path, monkeypatch):
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
    monkeypatch.setitem(run_gate.BASELINE_EXPECTED_HASHES, "airplane.png", {
        "file_sha256": run_gate.file_sha256(baseline_path),
        "pixels_sha256": run_gate.pixel_sha256(base_pixels),
        "shape": [10, 10],
    })
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


def test_capacity_row_derives_candidate_fraction_from_counts():
    image = {
        "name": "fixture.tiff",
        "corpus_group": "unit_test_fixture",
        "classification": "natural",
        "source": "fixture.tiff",
        "source_sha256": "a" * 64,
        "pixels_sha256": "b" * 64,
        "shape": [10, 10],
    }
    stats = {
        "pixels": 100,
        "candidates": 25,
        "gross_slots": 400,
        "foregone_gross_slots": 20,
        "backup_bits": 40,
        "metadata_total_bits": 48,
        "accepted": True,
        "codec": "raw",
        "compressed_label_bytes": 3,
        "bootstrap_pixels": 6,
        "fixed_header_bits": 160,
        "authentication_bits": 256,
    }
    prepared = {
        "stats": stats,
        "net": 340,
        "phase": 2,
        "phase_net_bits": [330, 335, 340, 320],
        "phase_scores": [],
    }

    row = run_gate.capacity_row(image, prepared, 0.125)

    assert row["candidate_count"] == 25
    assert row["pixels"] == 100
    assert row["candidate_fraction"] == pytest.approx(0.25)
    assert row["net_capacity_bits"] == 340


def test_edr2_allocation_is_pixel_unique_for_every_original_prediction_pair_and_payload_word():
    """Exhaust the active EDR2 map, not the separate legacy src/rdhei_core map."""
    tested_pairs = 0
    tested_payload_words = 0

    for prediction in range(256):
        for original in range(256):
            error = abs(original - prediction)
            n, low, high = wire.allocation(error)
            label = int(predictor.LABEL[error])
            assert tuple(map(int, wire.BOOK[label])) == (n, low, high)
            tested_pairs += 1

            if n == 0:
                continue

            modulus = 1 << (8 - n)
            residue = original & (modulus - 1)
            candidates = [
                candidate for candidate in range(residue, 256, modulus)
                if low <= abs(candidate - prediction) <= high
            ]
            assert candidates == [original], (
                f"EDR2 mapping is not unique: original={original}, "
                f"prediction={prediction}, error={error}, label={(n, low, high)}, "
                f"candidates={candidates}"
            )

            # Exhaust every possible n-bit payload word. The lower residue is
            # preserved by MSB replacement and the decoder must still identify x.
            for payload_word in range(1 << n):
                marked = residue | (payload_word << (8 - n))
                assert marked >> (8 - n) == payload_word
                marked_residue = marked & (modulus - 1)
                recovered_candidates = [
                    candidate for candidate in range(marked_residue, 256, modulus)
                    if low <= abs(candidate - prediction) <= high
                ]
                assert recovered_candidates == [original]
                tested_payload_words += 1

    assert tested_pairs == 65_536
    assert tested_payload_words == 379_136


def test_fixed_six_baselines_reject_same_named_nonoriginal_images(tmp_path, monkeypatch):
    baseline = tmp_path / "kodak_gray"
    baseline.mkdir()
    image_path = baseline / "Airplane.png"
    pixels = np.arange(100, dtype=np.uint8).reshape(10, 10)
    Image.fromarray(pixels).save(image_path)
    monkeypatch.setitem(run_gate.BASELINE_EXPECTED_HASHES, "airplane.png", {
        "file_sha256": "0" * 64,
        "pixels_sha256": run_gate.pixel_sha256(pixels),
        "shape": [10, 10],
    })
    with pytest.raises(ValueError, match="does not match the exact original project image"):
        run_gate.load_corpus([baseline], allow_missing_baseline=True)


def test_fixed_six_baselines_verify_decoded_pixel_hash_and_dimensions(tmp_path, monkeypatch):
    baseline = tmp_path / "kodak_gray"
    baseline.mkdir()
    image_path = baseline / "Airplane.png"
    pixels = np.arange(100, dtype=np.uint8).reshape(10, 10)
    Image.fromarray(pixels).save(image_path)
    monkeypatch.setitem(run_gate.BASELINE_EXPECTED_HASHES, "airplane.png", {
        "file_sha256": run_gate.file_sha256(image_path),
        "pixels_sha256": "1" * 64,
        "shape": [10, 10],
    })
    with pytest.raises(ValueError, match="does not match the exact original project image"):
        run_gate.load_corpus([baseline], allow_missing_baseline=True)
