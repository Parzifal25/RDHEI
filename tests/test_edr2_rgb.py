from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2))

import predictor
import rgb_protocol
import rgb_wire
import wire


def fake_spatial(image, ys, xs, active_model=None):
    return np.full(len(ys), 128.0, dtype=np.float32)


def constant_rgb(height=128, width=128):
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = 100
    image[:, :, 1] = 120
    image[:, :, 2] = 140
    return image


def test_rgb_phase_staggering_leaves_one_common_calibration_lattice():
    shape = (128, 128)
    phase_sets = []
    for phase in range(4):
        ys, xs = wire.grid(shape, phase=phase)
        phase_sets.append(set(zip(ys.tolist(), xs.tolist())))
    for i in range(4):
        for j in range(i + 1, 4):
            assert phase_sets[i].isdisjoint(phase_sets[j])
    assert set.union(*phase_sets) == {
        (y, x) for y in range(1, shape[0] - 1) for x in range(1, shape[1] - 1)
    }


def test_rgb_cross_regression_is_integer_deterministic_and_uses_anchor_phase():
    image = constant_rgb()
    first = rgb_protocol.fit_cross_regressions(image, calibration_phase=3)
    second = rgb_protocol.fit_cross_regressions(image.copy(), calibration_phase=3)
    assert first == second
    assert len(first) == 3
    assert all(isinstance(v, tuple) and len(v) == 2 for v in first)
    # Constant reference features give a zero-slope predictor and exact channel mean.
    assert first[0][0] == 0
    assert first[0][1] == 100 * 256
    assert first[1][0] == 0
    assert first[1][1] == 120 * 256
    assert first[2][0] == 0
    assert first[2][1] == 140 * 256


def test_rgb_keys_are_domain_separated_for_each_channel():
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F001
    keys = rgb_wire.keys(master, nonce)
    assert len(keys["image"]) == 3
    assert len({key for key in keys["image"]}) == 3
    assert len(keys["hider"]) == 32
    assert rgb_wire.keys(master, nonce) == keys


def test_rgb_exact_roundtrip_payload_and_authenticated_phase_discovery(monkeypatch):
    monkeypatch.setattr(predictor, "model", lambda: object())
    monkeypatch.setattr(predictor, "predict", fake_spatial)
    original = constant_rgb()
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F123

    prepared = rgb_protocol.prepare(original)
    assert prepared["net"] > 0
    assert len(set(prepared["phases"])) == 3
    assert prepared["calibration_phase"] not in prepared["phases"]

    reserved, capability = rgb_protocol.reserve(original, master, nonce, prepared=prepared)
    hider = rgb_wire.hider_keys(capability["hider"])
    inspected = rgb_wire.inspect(reserved, hider, stage="bootstrap")
    assert inspected["phases"] == prepared["phases"]
    assert inspected["calibration_phase"] == prepared["calibration_phase"]

    payload = np.random.default_rng(19).integers(0, 2, 137, dtype=np.uint8)
    marked = rgb_protocol.embed(reserved, payload, capability["hider"])
    recovered, recovered_payload = rgb_protocol.receive(marked, master, nonce)

    np.testing.assert_array_equal(recovered, original)
    np.testing.assert_array_equal(recovered_payload, payload)
    assert marked.shape == original.shape
    assert marked.dtype == np.uint8


def test_rgb_wrong_key_and_tampering_fail_closed(monkeypatch):
    monkeypatch.setattr(predictor, "model", lambda: object())
    monkeypatch.setattr(predictor, "predict", fake_spatial)
    original = constant_rgb()
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F124
    reserved, capability = rgb_protocol.reserve(original, master, nonce)
    payload = np.zeros(53, dtype=np.uint8)
    marked = rgb_protocol.embed(reserved, payload, capability["hider"])

    with pytest.raises(ValueError, match="no valid authenticated RGB packet"):
        rgb_protocol.receive(marked, bytes(reversed(range(32))), nonce)

    tampered = marked.copy()
    tampered[10, 10, 1] ^= 1
    with pytest.raises(ValueError, match="no valid authenticated RGB packet"):
        rgb_protocol.receive(tampered, master, nonce)


@pytest.mark.parametrize("shape", [(127, 128, 3), (128, 127, 3)])
def test_rgb_rejects_odd_dimensions(shape):
    with pytest.raises(ValueError, match="even"):
        rgb_protocol.prepare(np.zeros(shape, dtype=np.uint8))


def test_rgb_rejects_gray_and_rgba_inputs():
    with pytest.raises(ValueError, match="RGB HxWx3"):
        rgb_protocol.prepare(np.zeros((128, 128), dtype=np.uint8))
    with pytest.raises(ValueError, match="RGB HxWx3"):
        rgb_protocol.prepare(np.zeros((128, 128, 4), dtype=np.uint8))


@pytest.mark.parametrize("bit_length", [0, 1, 7, 8, 9, 31, 137, 1025])
def test_rgb_bit_exact_ctr_roundtrip_for_partial_bytes(bit_length):
    key = bytes(range(32))
    bits = np.random.default_rng(bit_length + 73).integers(0, 2, bit_length, dtype=np.uint8)
    encrypted = rgb_wire.crypt_bits(bits, key)
    decrypted = rgb_wire.crypt_bits(encrypted, key)
    assert len(encrypted) == bit_length
    np.testing.assert_array_equal(decrypted, bits)


def test_rgb_writer_preserves_multiple_bit_slots_in_one_channel_byte():
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    positions = (
        np.asarray([0, 0, 0, 1], dtype=np.int64),
        np.asarray([0, 0, 0, 2], dtype=np.uint8),
        np.asarray([7, 6, 5, 7], dtype=np.uint8),
        [],
    )
    bits = np.asarray([1, 0, 1, 1], dtype=np.uint8)
    rgb_wire.writebits(image, positions, bits)
    observed = rgb_wire.readbits(image, positions)
    np.testing.assert_array_equal(observed, bits)
    assert image[0, 0, 0] == 0b10100000
    assert image[0, 0, 2] == 0
    assert image[0, 1, 2] == 0b10000000


def test_rgb_fixed_assignment_ablation_records_one_predeclared_tuple(monkeypatch):
    monkeypatch.setattr(predictor, "model", lambda: object())
    monkeypatch.setattr(predictor, "predict", fake_spatial)
    original = constant_rgb()
    prepared = rgb_protocol.prepare(
        original,
        blend_num=1,
        blend_den=4,
        assignment_override=(0, 1, 2),
    )
    assert prepared["assignment_search"] == "fixed_override"
    assert prepared["phases"] == (0, 1, 2)
    assert prepared["calibration_phase"] == 3
    assert len(prepared["assignment_scores"]) == 1
    assert len(prepared["prediction_metrics"]) == 3
    assert all(
        set(row) == {"spatial_mae", "cross_channel_mae", "fused_mae"}
        for row in prepared["prediction_metrics"]
    )


def test_rgb_adaptive_search_evaluates_all_24_ordered_phase_assignments(monkeypatch):
    monkeypatch.setattr(predictor, "model", lambda: object())
    monkeypatch.setattr(predictor, "predict", fake_spatial)
    prepared = rgb_protocol.prepare(constant_rgb(), blend_num=0, blend_den=4)
    assert prepared["assignment_search"] == "adaptive_24"
    assert len(prepared["assignment_scores"]) == 24
    assert all(len(row["phases"]) == 3 for row in prepared["assignment_scores"])
    assert all(len(set(row["phases"] + (row["calibration_phase"],))) == 4
               for row in prepared["assignment_scores"])
