#!/usr/bin/env python3
"""Inventory native 8-bit grayscale TIFFs from official USC-SIPI archives.

USC-SIPI uses legacy filenames without conventional .tif/.tiff suffixes. This
script detects TIFF content by its file signature, preserves the original TIFF
bytes, and writes safe normalized .tiff filenames. It does not convert RGB,
resize, crop, recompress, or blindly extract archive paths. The generated
inventory is not itself an approved evaluation corpus; run
curate_usc_sipi_allowlist.py for hash-pinned catalogue curation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

ARCHIVES = {
    "textures": "https://sipi.usc.edu/database/textures.tar.gz",
    "rotate": "https://sipi.usc.edu/database/rotate.tar.gz",
    "aerials": "https://sipi.usc.edu/database/aerials.tar.gz",
    "misc": "https://sipi.usc.edu/database/misc.tar.gz",
    "sequences": "https://sipi.usc.edu/database/sequences.tar.gz",
}
TIFF_MAGICS = {b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "RDHEI-EDR2-reproducibility/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
            digest = hashlib.sha256()
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                out.write(block)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"failed to download {url}: {exc}") from exc
    return digest.hexdigest()


def normalized_output_path(volume: str, member_name: str, output_root: Path) -> Path:
    member = PurePosixPath(member_name)
    if member.is_absolute() or not member.parts or any(part in ("..", "") for part in member.parts):
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    if ":" in member.parts[0] or "\\" in member_name:
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    original_name = member.name
    suffix = Path(original_name).suffix.lower()
    stem = Path(original_name).stem if suffix in {".tif", ".tiff"} else original_name
    if not stem or stem in {".", ".."}:
        raise ValueError(f"invalid archive member filename: {member_name!r}")
    relative = Path(volume, *member.parts[:-1], stem + ".tiff")
    destination = (output_root / relative).resolve()
    if output_root.resolve() not in destination.parents:
        raise ValueError(f"archive member escapes output directory: {member_name!r}")
    return destination


def extract_grayscale(archive_path: Path, volume: str, output_root: Path, archive_url: str, archive_sha: str):
    accepted, skipped = [], []
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            raw = source.read()
            if len(raw) < 4 or raw[:4] not in TIFF_MAGICS:
                continue
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    if getattr(image, "n_frames", 1) != 1:
                        skipped.append({"member": member.name, "reason": "multi-frame TIFF"})
                        continue
                    mode = image.mode
                    image.load()
                    pixels = np.asarray(image)
                    if mode != "L" or pixels.dtype != np.uint8 or pixels.ndim != 2:
                        skipped.append({
                            "member": member.name,
                            "reason": f"not native 8-bit grayscale (mode={mode}, dtype={pixels.dtype}, shape={pixels.shape})",
                        })
                        continue
                    height, width = map(int, pixels.shape)
            except Exception as exc:
                skipped.append({"member": member.name, "reason": f"{type(exc).__name__}: {exc}"})
                continue

            try:
                destination = normalized_output_path(volume, member.name, output_root)
            except ValueError as exc:
                skipped.append({"member": member.name, "reason": str(exc)})
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError(
                    f"two archive members normalize to the same path: {destination}"
                )
            destination.write_bytes(raw)
            accepted.append({
                "path": destination.relative_to(output_root).as_posix(),
                "archive_member": member.name,
                "source_url": archive_url,
                "archive_sha256": archive_sha,
                "file_sha256": sha256(raw),
                "mode": "L",
                "dtype": "uint8",
                "shape": [height, width],
                "bytes": len(raw),
            })
    return accepted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/usc_sipi_gray")
    parser.add_argument("--archive-dir", default="data/usc_sipi_archives")
    args = parser.parse_args()

    output_root = Path(args.output_dir).expanduser().resolve()
    archive_root = Path(args.archive_dir).expanduser().resolve()
    if output_root.exists() and any(
        path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
        for path in output_root.rglob("*")
    ):
        raise FileExistsError(
            f"{output_root} already contains TIFF files; choose a clean output directory"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)

    all_images, all_skipped, archive_records = [], [], []
    for volume, url in ARCHIVES.items():
        archive_path = archive_root / f"{volume}.tar.gz"
        if archive_path.exists():
            archive_sha = sha256_file(archive_path)
        else:
            print(f"Downloading {url}", flush=True)
            archive_sha = download(url, archive_path)
        images, skipped = extract_grayscale(
            archive_path, volume, output_root, url, archive_sha
        )
        archive_records.append({
            "volume": volume,
            "url": url,
            "archive_path": str(archive_path),
            "archive_sha256": archive_sha,
            "native_grayscale_tiffs": len(images),
            "skipped_tiff_candidates": len(skipped),
        })
        all_images.extend(images)
        all_skipped.extend([{"volume": volume, **row} for row in skipped])
        print(f"{volume}: retained {len(images)} native grayscale TIFFs; skipped {len(skipped)} TIFF candidates", flush=True)

    manifest = {
        "dataset": "USC-SIPI Image Database",
        "preparation_script": "final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py",
        "source_homepage": "https://sipi.usc.edu/database/",
        "policy": (
            "TIFF files are identified by byte signature rather than filename suffix. "
            "Only native single-frame 8-bit grayscale TIFFs (Pillow mode L, uint8, 2D) "
            "are retained. RGB and 16-bit images are not converted. Original TIFF bytes "
            "are preserved under safe normalized .tiff filenames. This is an inventory "
            "only; catalogue review, exact-file SHA-256 checks, even dimensions, and a "
            "curated allowlist are required before EDR2 paper-facing evaluation."
        ),
        "archive_records": archive_records,
        "image_count_before_pixel_deduplication": len(all_images),
        "images": all_images,
        "skipped_tiff_candidates": all_skipped,
    }
    manifest_path = output_root / "dataset_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    print(f"Native grayscale TIFFs retained: {len(all_images)}")
    print("Next: run curate_usc_sipi_allowlist.py. The inventory itself is not an approved paper corpus.")


if __name__ == "__main__":
    main()
