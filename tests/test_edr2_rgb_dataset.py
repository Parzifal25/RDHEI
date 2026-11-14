from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2))

import prepare_usc_sipi_rgb as sipi_rgb
import run_rgb_gate as rgb_gate


def test_rgb_runner_accepts_native_rgb_and_rejects_silent_conversion(tmp_path):
    rgb = np.zeros((12, 14, 3), dtype=np.uint8)
    rgb_path = tmp_path / "native_rgb.png"
    Image.fromarray(rgb, mode="RGB").save(rgb_path)
    np.testing.assert_array_equal(rgb_gate.load_native_rgb(rgb_path), rgb)

    gray_path = tmp_path / "gray.png"
    Image.fromarray(np.zeros((12, 14), dtype=np.uint8), mode="L").save(gray_path)
    with pytest.raises(ValueError, match="native 8-bit RGB"):
        rgb_gate.load_native_rgb(gray_path)

    rgba_path = tmp_path / "rgba.png"
    Image.fromarray(np.zeros((12, 14, 4), dtype=np.uint8), mode="RGBA").save(rgba_path)
    with pytest.raises(ValueError, match="native 8-bit RGB"):
        rgb_gate.load_native_rgb(rgba_path)


def test_rgb_runner_rejects_odd_dimensions(tmp_path):
    path = tmp_path / "odd.png"
    Image.fromarray(np.zeros((11, 14, 3), dtype=np.uint8), mode="RGB").save(path)
    with pytest.raises(ValueError, match="even dimensions"):
        rgb_gate.load_native_rgb(path)


def test_rgb_benchmark_ids_and_payload_are_deterministic():
    first = rgb_gate.stable_ids(42, "a" * 64)
    second = rgb_gate.stable_ids(42, "a" * 64)
    different = rgb_gate.stable_ids(42, "b" * 64)
    assert first == second
    assert first != different
    payload_a = rgb_gate.payload_for(137, 42, "a" * 64, "partial")
    payload_b = rgb_gate.payload_for(137, 42, "a" * 64, "partial")
    np.testing.assert_array_equal(payload_a, payload_b)


def test_official_checksum_parser_reads_published_posix_cksum_values():
    page = (
        b"<pre>aerials/2.1.01.tiff | 1220177504\n"
        b"misc/4.2.03.tiff | 3944512653\n</pre>"
    )
    values = sipi_rgb.parse_checksums(page)
    assert values == {
        "aerials/2.1.01.tiff": 1220177504,
        "misc/4.2.03.tiff": 3944512653,
    }


def test_rgb_archive_extraction_confines_member_paths(tmp_path):
    archive_path = tmp_path / "fixture.tar.gz"
    payload = b"native TIFF fixture"
    with tarfile.open(archive_path, "w:gz") as archive:
        safe = tarfile.TarInfo("aerials/fixture.tiff")
        safe.size = len(payload)
        archive.addfile(safe, io.BytesIO(payload))

        malicious = tarfile.TarInfo("aerials/../../escape.tiff")
        malicious.size = len(payload)
        archive.addfile(malicious, io.BytesIO(payload))

    destination = tmp_path / "out"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        extracted = sipi_rgb.extract_safe_member(
            archive, members["aerials/fixture.tiff"], destination
        )
        assert extracted.read_bytes() == payload
        with pytest.raises(ValueError, match="unsafe"):
            sipi_rgb.extract_safe_member(
                archive, members["aerials/../../escape.tiff"], destination
            )
    assert not (tmp_path / "escape.tiff").exists()



def test_rgb_runner_completion_gate_fails_when_every_input_is_skipped():
    status, failures = rgb_gate.completion_status([], [], [])
    assert status == "completed_with_failures"
    assert any("no native" in failure for failure in failures)


def test_rgb_runner_completion_gate_fails_on_roundtrip_or_missing_full_capacity():
    inventory = [{"image": "aerials/a.tiff"}]
    capacity = [{
        "image": "aerials/a.tiff",
        "status": "roundtrip_passed",
        "signed_net_capacity_bits": 100,
    }]
    incomplete = [{
        "image": "aerials/a.tiff",
        "payload_bits": 37,
        "passed": True,
    }]
    status, failures = rgb_gate.completion_status(capacity, inventory, incomplete)
    assert status == "completed_with_failures"
    assert any("full-capacity" in failure for failure in failures)

    failed = [{
        "image": "aerials/a.tiff",
        "payload_bits": 100,
        "passed": False,
    }]
    status, failures = rgb_gate.completion_status(capacity, inventory, failed)
    assert status == "completed_with_failures"
    assert any("exact-recovery" in failure for failure in failures)


def test_rgb_runner_completion_gate_accepts_rejected_capacity_and_exact_positive_case():
    inventory = [
        {"image": "aerials/a.tiff"},
        {"image": "misc/b.tiff"},
    ]
    capacity = [
        {
            "image": "aerials/a.tiff",
            "status": "roundtrip_passed",
            "signed_net_capacity_bits": 100,
        },
        {
            "image": "misc/b.tiff",
            "status": "rejected_nonpositive_net_capacity",
            "signed_net_capacity_bits": -5,
        },
    ]
    roundtrips = [
        {"image": "aerials/a.tiff", "payload_bits": 0, "passed": True},
        {"image": "aerials/a.tiff", "payload_bits": 100, "passed": True},
    ]
    status, failures = rgb_gate.completion_status(capacity, inventory, roundtrips)
    assert status == "completed"
    assert failures == []



def test_rgb_benchmark_uses_distinct_nonce_for_each_payload_packet():
    master_a, nonce_a = rgb_gate.stable_ids(42, "a" * 64, "empty")
    master_b, nonce_b = rgb_gate.stable_ids(42, "a" * 64, "short_37")
    master_repeat, nonce_repeat = rgb_gate.stable_ids(42, "a" * 64, "empty")
    assert master_a == master_b == master_repeat
    assert nonce_a != nonce_b
    assert nonce_a == nonce_repeat


def test_rgb_benchmark_nonce_changes_between_images_and_seeds():
    _, nonce_a = rgb_gate.stable_ids(42, "a" * 64, "full")
    _, nonce_b = rgb_gate.stable_ids(42, "b" * 64, "full")
    _, nonce_c = rgb_gate.stable_ids(43, "a" * 64, "full")
    assert len({nonce_a, nonce_b, nonce_c}) == 3
