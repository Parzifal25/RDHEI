from __future__ import annotations

import inspect
import io
import sys
import tarfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(SCRIPT_DIR))

import protocol  # noqa: E402
import run_gate  # noqa: E402
import wire  # noqa: E402
import prepare_usc_sipi_gray as prepare_sipi  # noqa: E402


def write_gray(path: Path, value: int, shape=(12, 12)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full(shape, value, dtype=np.uint8), mode="L").save(path)


def test_receiver_api_has_only_stego_image_master_key_and_nonce():
    assert list(inspect.signature(protocol.receive).parameters) == [
        "encrypted_image",
        "master",
        "nonce",
    ]
    assert wire.PROTOCOL_MAGIC == b"EDR2"


def test_one_derived_hider_key_is_separate_from_image_key():
    master = bytes(range(32))
    keys = wire.keys(master, 0x1020304050607080)
    assert set(keys) == {"image", "hider"}
    assert len(keys["image"]) == 32
    assert len(keys["hider"]) == 32
    assert keys["image"] != keys["hider"]

    hider_keys = wire.hider_keys(keys["hider"])
    assert set(hider_keys) == {"directory", "payload", "auth"}
    assert all(len(value) == 32 for value in hider_keys.values())
    assert len(set(hider_keys.values())) == 3
    assert keys["image"] not in hider_keys.values()


def test_load_corpus_keeps_six_originals_and_discovers_grayscale(tmp_path):
    baseline = tmp_path / "kodak_gray"
    expanded = tmp_path / "usc_sipi_gray"

    for index, stem in enumerate(sorted(run_gate.BASELINE_STEMS)):
        write_gray(baseline / f"{stem}.png", index + 10)

    write_gray(expanded / "duplicates" / "copy_of_airplane.tiff", 10)
    write_gray(expanded / "textures" / "extra_texture.tiff", 99)
    expanded.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((12, 12, 3), dtype=np.uint8), mode="RGB").save(
        expanded / "color_input.png"
    )

    corpus, skipped, duplicates, inventory, missing = run_gate.load_corpus(
        [baseline, expanded], allow_missing_baseline=False
    )

    assert len(corpus) == 7
    assert len(inventory) == 7
    assert len(duplicates) == 1
    assert len(skipped) == 1
    assert missing == []
    assert all("array" not in item for item in corpus)
    assert any(item["relative_path"] == "textures/extra_texture.tiff" for item in corpus)


def test_load_corpus_requires_baseline_in_kodak_directory(tmp_path):
    expanded = tmp_path / "usc_sipi_gray"
    write_gray(expanded / "airplane.tiff", 15)

    with pytest.raises(ValueError, match="original baseline image names are missing"):
        run_gate.load_corpus([expanded], allow_missing_baseline=False)

    corpus, skipped, duplicates, inventory, missing = run_gate.load_corpus(
        [expanded], allow_missing_baseline=True
    )
    assert len(corpus) == 1
    assert len(missing) == 6


def test_native_grayscale_reader_rejects_color_without_conversion(tmp_path):
    path = tmp_path / "rgb.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(path)
    with pytest.raises(ValueError, match="native 8-bit grayscale"):
        run_gate.read_native_gray(path)


def test_capacity_ledger_separates_metadata_carrier_opportunity_cost_and_backup():
    image = {
        "name": "unit-test",
        "source": "unit-test",
        "source_sha256": "source-hash",
        "pixels_sha256": "pixel-hash",
        "shape": [10, 10],
    }
    q = {
        "net": 340,
        "stats": {
            "gross_slots": 420,
            "foregone_gross_slots": 40,
            "backup_bits": 40,
            "metadata_total_bits": 40,
            "pixels": 100,
            "candidates": 10,
            "compressed_label_bytes": 4,
            "bootstrap_pixels": 5,
            "fixed_header_bits": 160,
            "authentication_bits": 256,
            "codec": "raw",
            "accepted": True,
        },
    }

    row = run_gate.capacity_row(image, q, 0.25)
    assert row["gross_capacity_bits"] == 420
    assert row["metadata_wire_storage_bits"] == 40
    assert row["metadata_overhead_bits"] == 40
    assert row["bootstrap_backup_bits"] == 40
    assert row["total_overhead_bits"] == 80
    assert row["net_capacity_bits"] == 340
    assert row["signed_net_bpp"] == pytest.approx(3.4)


def test_sipi_preparer_keeps_only_native_gray_and_confines_archive_paths(tmp_path):
    def tiff_bytes(array, mode):
        buffer = io.BytesIO()
        Image.fromarray(array, mode=mode).save(buffer, format="TIFF")
        return buffer.getvalue()

    gray = tiff_bytes(np.arange(64, dtype=np.uint8).reshape(8, 8), "L")
    rgb = tiff_bytes(np.zeros((8, 8, 3), dtype=np.uint8), "RGB")
    archive_path = tmp_path / "sipi-fixture.tar.gz"

    with tarfile.open(archive_path, "w:gz") as archive:
        for member_name, payload in [
            ("folder/native_gray.tiff", gray),
            ("folder/color_rgb.tiff", rgb),
            ("../../outside_destination.tiff", gray),
        ]:
            info = tarfile.TarInfo(member_name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))

    output_root = tmp_path / "prepared"
    accepted, skipped = prepare_sipi.extract_grayscale(
        archive_path,
        "fixture_volume",
        output_root,
        "https://example.invalid/fixture.tar.gz",
        "archive-sha",
    )

    assert len(accepted) == 2
    assert len(skipped) == 1
    assert (output_root / "fixture_volume" / "native_gray.tiff").read_bytes() == gray
    assert (output_root / "fixture_volume" / "outside_destination.tiff").read_bytes() == gray
    assert not (tmp_path / "outside_destination.tiff").exists()
    with Image.open(output_root / "fixture_volume" / "native_gray.tiff") as image:
        assert image.mode == "L"
        assert np.asarray(image).dtype == np.uint8
