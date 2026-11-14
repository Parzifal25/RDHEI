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

import analyze_rgb_evidence as rgb_analyzer
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



def _valid_rgb_evidence_frames():
    import pandas as pd

    capacity = pd.DataFrame([
        {
            "image": "aerials/a.tiff",
            "pixels_sha256": "a" * 64,
            "status": "roundtrip_passed",
            "signed_net_capacity_bits": 137,
        },
        {
            "image": "misc/b.tiff",
            "pixels_sha256": "b" * 64,
            "status": "rejected_nonpositive_net_capacity",
            "signed_net_capacity_bits": -4,
        },
    ])
    lengths = [0, 1, 7, 8, 9, 37, 136, 137]
    roundtrip = pd.DataFrame([
        {
            "image": "aerials/a.tiff", "pixels_sha256": "a" * 64,
            "case": f"payload_{length}", "payload_bits": length, "net_capacity_bits": 137,
            "image_exact": True, "payload_exact": True, "passed": True,
        }
        for length in lengths
    ])
    assignment_rows = []
    phases = [{
        "phases": [r, g, b],
        "calibration_phase": next(p for p in range(4) if p not in (r, g, b)),
        "net_capacity_bits": 10,
        "directory_bytes": 5,
    } for r in range(4) for g in range(4) if g != r
      for b in range(4) if b not in (r, g)]
    for image, pixel_hash in (("aerials/a.tiff", "a" * 64), ("misc/b.tiff", "b" * 64)):
        for blend in (0, 1, 2, 3):
            assignment_rows.append({
                "image": image, "pixels_sha256": pixel_hash,
                "blend_num": blend, "blend_den": 4,
                "assignment_search": "adaptive_24",
                "phase_assignment_scores_json": __import__("json").dumps(phases),
            })
    assignments = pd.DataFrame(assignment_rows)
    run = {
        "status": "completed", "analysis_ready": True, "roundtrip_failed": 0,
        "roundtrip_cases": len(roundtrip), "roundtrip_passed": len(roundtrip),
        "capacity_rows": 2, "distinct_native_rgb_inputs": 2,
    }
    manifest = {"images": [
        {"image": "aerials/a.tiff"}, {"image": "misc/b.tiff"},
    ]}
    return capacity, roundtrip, assignments, run, manifest


def test_rgb_paper_analyzer_accepts_only_complete_evidence():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)


def test_rgb_paper_analyzer_rejects_failed_run_even_when_csvs_exist():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    run["status"] = "completed_with_failures"
    run["analysis_ready"] = False
    with pytest.raises(ValueError, match="not analysis-ready"):
        rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)


def test_rgb_paper_analyzer_rejects_missing_full_capacity_recovery():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    roundtrip = roundtrip[roundtrip["payload_bits"] == 0]
    run["roundtrip_cases"] = 1
    run["roundtrip_passed"] = 1
    with pytest.raises(ValueError, match="payload-boundary ledger mismatch"):
        rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)


def test_rgb_paper_analyzer_rejects_incomplete_phase_assignment_ablations():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    assignments = assignments[assignments["blend_num"] != 3]
    with pytest.raises(ValueError, match="incomplete"):
        rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)



def test_rgb_paper_analyzer_rejects_duplicate_phase_permutations():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    scores = __import__("json").loads(assignments.iloc[0]["phase_assignment_scores_json"])
    scores[-1] = scores[0]
    assignments.loc[0, "phase_assignment_scores_json"] = __import__("json").dumps(scores)
    with pytest.raises(ValueError, match="24 distinct ordered phase assignments"):
        rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)


def test_rgb_paper_analyzer_rejects_missing_nonbyte_payload_boundary():
    capacity, roundtrip, assignments, run, manifest = _valid_rgb_evidence_frames()
    roundtrip = roundtrip[roundtrip["payload_bits"] != 136]
    run["roundtrip_cases"] = len(roundtrip)
    run["roundtrip_passed"] = len(roundtrip)
    with pytest.raises(ValueError, match="payload-boundary ledger mismatch"):
        rgb_analyzer.validate_evidence(capacity, roundtrip, assignments, run, manifest)


def test_rgb_benchmark_nonce_namespace_prevents_cross_run_reuse():
    master_a, nonce_a = rgb_gate.stable_ids(
        42, "a" * 64, "empty", nonce_namespace="run-one"
    )
    master_b, nonce_b = rgb_gate.stable_ids(
        42, "a" * 64, "empty", nonce_namespace="run-two"
    )
    assert master_a == master_b
    assert nonce_a != nonce_b
