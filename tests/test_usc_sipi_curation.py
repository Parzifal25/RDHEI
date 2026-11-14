"""Tests for USC-SIPI archive inventory and catalogue curation."""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2))

import curate_usc_sipi_allowlist as curator
import prepare_usc_sipi_gray as preparer


def _write_tiff(path: Path, pixels: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(path, format="TIFF")


def test_archive_inventory_detects_legacy_filename_and_preserves_bytes(tmp_path):
    source = tmp_path / "source.tiff"
    pixels = np.arange(100, dtype=np.uint8).reshape(10, 10)
    _write_tiff(source, pixels)
    raw = source.read_bytes()
    archive_path = tmp_path / "textures.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("textures/1.1.01.p512")
        info.size = len(raw)
        import io
        archive.addfile(info, io.BytesIO(raw))

    output = tmp_path / "out"
    images, skipped = preparer.extract_grayscale(
        archive_path, "textures", output, "https://sipi.usc.edu/database/textures.tar.gz", "a" * 64
    )
    assert skipped == []
    assert len(images) == 1
    expected = output / "textures" / "textures" / "1.1.01.p512.tiff"
    assert expected.read_bytes() == raw
    assert images[0]["path"] == "textures/textures/1.1.01.p512.tiff"
    assert images[0]["file_sha256"] == hashlib.sha256(raw).hexdigest()
    np.testing.assert_array_equal(np.asarray(Image.open(expected)), pixels)


def test_archive_inventory_skips_rgb_and_rejects_traversal(tmp_path):
    rgb_path = tmp_path / "rgb.tiff"
    _write_tiff(rgb_path, np.zeros((10, 10, 3), dtype=np.uint8))
    raw = rgb_path.read_bytes()
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        import io
        info = tarfile.TarInfo("textures/../escape.p512")
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))

    images, skipped = preparer.extract_grayscale(
        archive_path, "textures", tmp_path / "out",
        "https://sipi.usc.edu/database/textures.tar.gz", "b" * 64
    )
    assert images == []
    assert skipped == []  # rejected RGB/non-TIFF payloads are not inventory candidates

    # Path validation is exercised directly for a valid TIFF member name.
    try:
        preparer.normalized_output_path("textures", "../escape.p512", tmp_path / "out")
    except ValueError as exc:
        assert "unsafe archive member path" in str(exc)
    else:
        raise AssertionError("archive path traversal should be rejected")


def test_allowlist_curation_excludes_maps_charts_and_odd_sizes(tmp_path):
    root = tmp_path / "usc_sipi_gray"
    rows = []

    def add(volume: str, filename: str, member: str, pixels: np.ndarray):
        rel = f"{volume}/{filename}"
        path = root / rel
        _write_tiff(path, pixels)
        raw = path.read_bytes()
        rows.append({
            "path": rel,
            "archive_member": member,
            "file_sha256": hashlib.sha256(raw).hexdigest(),
            "mode": "L",
            "dtype": "uint8",
            "shape": list(pixels.shape),
        })

    even = np.arange(100, dtype=np.uint8).reshape(10, 10)
    odd = np.arange(99, dtype=np.uint8).reshape(9, 11)
    add("textures", "sample.tiff", "1.1.01.p512", even)
    add("textures", "map.tiff", "texmos2.s512", even + 1)
    add("misc", "chart.tiff", "5.1.13", even + 2)
    add("misc", "odd.tiff", "5.1.14", odd)
    add("sequences", "frame.tiff", "6.1.01", even + 3)

    manifest = {
        "dataset": "USC-SIPI Image Database",
        "images": rows,
    }
    manifest_path = root / "dataset_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = root / "natural_image_allowlist.json"

    result = curator.create_allowlist(manifest_path, output_path)
    accepted = {row["path"]: row for row in result["images"]}
    assert set(accepted) == {"textures/sample.tiff", "sequences/frame.tiff"}
    assert accepted["textures/sample.tiff"]["corpus_group"] == "texture_scans_and_mosaics"
    assert accepted["sequences/frame.tiff"]["corpus_group"] == "monochrome_sequence_frames"
    reasons = {row["path"]: row["reason"] for row in result["excluded_catalogue_or_format_candidates"]}
    assert "segmentation-information map" in reasons["textures/map.tiff"]
    assert "resolution/calibration chart" in reasons["misc/chart.tiff"]
    assert "odd image dimensions" in reasons["misc/odd.tiff"]


def test_allowlist_curation_fails_when_source_hash_changes(tmp_path):
    root = tmp_path / "usc_sipi_gray"
    path = root / "aerials" / "aerial.tiff"
    _write_tiff(path, np.arange(100, dtype=np.uint8).reshape(10, 10))
    manifest_path = root / "dataset_manifest.json"
    manifest_path.write_text(json.dumps({
        "dataset": "USC-SIPI Image Database",
        "images": [{
            "path": "aerials/aerial.tiff",
            "archive_member": "2.1.07",
            "file_sha256": "0" * 64,
            "mode": "L",
            "dtype": "uint8",
            "shape": [10, 10],
        }],
    }), encoding="utf-8")
    try:
        curator.create_allowlist(manifest_path, root / "natural_image_allowlist.json")
    except ValueError as exc:
        assert "SHA-256 mismatch" in str(exc)
    else:
        raise AssertionError("changed source file should fail closed")
