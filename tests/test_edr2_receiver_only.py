from __future__ import annotations

import inspect
import io
import json
import os
import subprocess
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
from src.cnn_model import build_model  # noqa: E402
from src.train import LazyPatchDataset, load_native_gray_images, split_by_source_image  # noqa: E402


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
    assert set(hider_keys) == {
        "header_bootstrap", "header_final", "directory", "payload", "auth"
    }
    assert all(len(value) == 32 for value in hider_keys.values())
    assert len(set(hider_keys.values())) == len(hider_keys)
    assert keys["image"] not in hider_keys.values()


def test_load_corpus_keeps_six_originals_and_only_curated_grayscale(tmp_path):
    import hashlib

    baseline = tmp_path / "kodak_gray"
    expanded = tmp_path / "usc_sipi_gray"

    for index, stem in enumerate(sorted(run_gate.BASELINE_STEMS)):
        write_gray(baseline / f"{stem}.png", index + 10)

    duplicate_path = expanded / "duplicates" / "copy_of_airplane.tiff"
    extra_path = expanded / "textures" / "extra_texture.tiff"
    write_gray(duplicate_path, 10)
    write_gray(extra_path, 99)
    expanded.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((12, 12, 3), dtype=np.uint8), mode="RGB").save(
        expanded / "color_input.png"
    )
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps({
            "images": [
                {
                    "path": "duplicates/copy_of_airplane.tiff",
                    "sha256": hashlib.sha256(duplicate_path.read_bytes()).hexdigest(),
                    "classification": "natural",
                    "curation_note": "Duplicate source used only to test pixel deduplication.",
                },
                {
                    "path": "textures/extra_texture.tiff",
                    "sha256": hashlib.sha256(extra_path.read_bytes()).hexdigest(),
                    "classification": "natural",
                    "curation_note": "Human-reviewed native USC-SIPI grayscale photograph.",
                },
            ]
        }),
        encoding="utf-8",
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
    assert any(item["relative_path"] == "color_input.png" for item in skipped)


def test_load_corpus_requires_baseline_in_kodak_directory(tmp_path):
    import hashlib

    expanded = tmp_path / "usc_sipi_gray"
    candidate = expanded / "airplane.tiff"
    write_gray(candidate, 15)
    (expanded / run_gate.NATURAL_ALLOWLIST_NAME).write_text(
        json.dumps({
            "images": [{
                "path": "airplane.tiff",
                "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "classification": "natural",
                "curation_note": "Reviewed native grayscale fixture for this unit test.",
            }]
        }),
        encoding="utf-8",
    )

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



def test_safe_zone_grid_is_synchronization_safe_and_maximally_dense():
    y, x = wire.grid((512, 512))
    assert len(y) == 255 * 255
    assert np.all(np.diff(np.unique(y)) == 2)
    assert np.all(np.diff(np.unique(x)) == 2)

    coords = set(zip(y.tolist(), x.tolist()))
    for cy, cx in list(coords)[::97]:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    assert (cy + dy, cx + dx) not in coords

    # The finite one-pixel-border candidate domain is 510x510. A 2x2
    # witness tile can contain at most one centre, and this lattice reaches
    # that bound: 255x255 candidates (24.81% of all pixels).
    assert len(coords) / (512 * 512) == pytest.approx(65025 / 262144)
    assert int(y.min()) == int(x.min()) == 1
    assert int(y.max()) == int(x.max()) == 509
    y3, x3 = np.meshgrid(np.arange(2, 510, 3), np.arange(2, 510, 3), indexing="ij")
    assert len(y) > y3.size
    assert len(y) / y3.size == pytest.approx(65025 / 28900)


def test_edr2_roundtrip_uses_only_receiver_image_master_nonce_and_encrypted_header():
    original = np.full((128, 128), 128, dtype=np.uint8)
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F001
    prepared = protocol.prepare(original)
    assert prepared["net"] > 0

    reserved, owner_capability = protocol.reserve(
        original, master, nonce, prepared=prepared
    )
    hider_capability = wire.hider_keys(owner_capability["hider"])

    bootstrap = wire.inspect(reserved, hider_capability, header_stage="bootstrap")
    header_ciphertext = reserved[
        bootstrap["y"][:wire.HEADER_BYTES], bootstrap["x"][:wire.HEADER_BYTES]
    ].tobytes()
    assert header_ciphertext != wire.HEADER.pack(
        wire.PROTOCOL_MAGIC, bootstrap["mode"], b"\x00\x00\x00",
        bootstrap["length"], 0
    )

    rng = np.random.default_rng(20261114)
    payload = rng.integers(0, 2, 37, dtype=np.uint8)
    marked = wire.embed(reserved, payload, hider_capability)
    final_packet = wire.inspect(marked, hider_capability, header_stage="final")
    assert final_packet["plen"] == len(payload)
    final_header_ciphertext = marked[
        final_packet["y"][:wire.HEADER_BYTES],
        final_packet["x"][:wire.HEADER_BYTES],
    ].tobytes()
    assert final_header_ciphertext != header_ciphertext

    recovered, extracted = protocol.receive(marked, master, nonce)
    assert np.array_equal(recovered, original)
    assert np.array_equal(extracted, payload)

    # Wrong K, wrong V, and any marked-image modification must fail closed.
    with pytest.raises(ValueError):
        protocol.receive(marked, bytes(32), nonce)
    with pytest.raises(ValueError):
        protocol.receive(marked, master, nonce + 1)
    tampered = marked.copy()
    tampered[0, 0] ^= 1
    with pytest.raises(ValueError):
        protocol.receive(tampered, master, nonce)



def test_training_uses_image_level_split_and_lazy_patch_extraction(tmp_path):
    records = []
    for index in range(10):
        path = tmp_path / f"training_{index:02d}.png"
        pixels = np.full((16, 16), index * 17, dtype=np.uint8)
        Image.fromarray(pixels, mode="L").save(path)
    records = load_native_gray_images(str(tmp_path))
    train_records, val_records = split_by_source_image(records, 0.2, seed=123)
    train_paths = {str(record[0]) for record in train_records}
    val_paths = {str(record[0]) for record in val_records}
    assert train_paths.isdisjoint(val_paths)
    assert len(train_paths) + len(val_paths) == 10

    dataset = LazyPatchDataset([train_records[0][1]], patch_size=3, stride=4, augment=False)
    patch, target = dataset[0]
    assert tuple(patch.shape) == (1, 3, 3)
    assert float(patch[0, 1, 1]) == 0.0
    assert 0.0 <= float(target) <= 255.0


def test_cnn_builder_accepts_explicit_three_by_three_cpu_configuration():
    model = build_model(patch_size=3, residual=True, device="cpu")
    assert model.patch_size == 3
    assert sum(parameter.numel() for parameter in model.parameters()) == 46881



def test_receiver_fresh_process_reads_only_marked_image_and_recovers_exactly(tmp_path):
    original = np.full((128, 128), 128, dtype=np.uint8)
    master = bytes(range(32))
    nonce = 0x102030405060708090A0B0C0D0E0F002

    q = protocol.prepare(original)
    assert q["net"] > 0
    reserved, cap = protocol.reserve(original, master, nonce, prepared=q)
    capability = wire.hider_keys(cap["hider"])
    payload = np.random.default_rng(7).integers(0, 2, 43, dtype=np.uint8)
    marked = wire.embed(reserved, payload, capability)

    marked_path = tmp_path / "marked_encrypted.png"
    recovered_path = tmp_path / "recovered.npy"
    payload_path = tmp_path / "payload.npy"
    audit_path = tmp_path / "receiver_audit.json"
    Image.fromarray(marked, mode="L").save(marked_path)

    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT_DIR / "protocol.py"), "receive",
            str(marked_path), master.hex(), str(nonce),
            str(recovered_path), str(payload_path), str(audit_path),
        ],
        cwd=str(SCRIPT_DIR.parent.parent),
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["semantic_inputs"] == [
        "marked encrypted image", "master key", "nonce"
    ]
    assert audit["source_access"] is False
    assert audit["source_reads"] == []
    read_paths = set(audit["read_paths"])
    assert str(marked_path.resolve()) in read_paths
    project_data_root = str((SCRIPT_DIR.parent / "data").resolve()) + os.sep
    assert not any(path.startswith(project_data_root) for path in read_paths)

    assert np.array_equal(np.load(recovered_path, allow_pickle=False), original)
    assert np.array_equal(np.load(payload_path, allow_pickle=False), payload)
