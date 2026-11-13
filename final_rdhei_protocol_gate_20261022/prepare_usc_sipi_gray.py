#!/usr/bin/env python3
"""Download the official USC-SIPI archives and retain native 8-bit grayscale TIFFs only.

This script never converts RGB images to grayscale and never extracts arbitrary tar paths.
It is intentionally a dataset-preparation utility; it does not alter the EDR1 codec.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ARCHIVES = {
    "textures": "https://sipi.usc.edu/database/textures.tar.gz",
    "rotate": "https://sipi.usc.edu/database/rotate.tar.gz",
    "aerials": "https://sipi.usc.edu/database/aerials.tar.gz",
    "misc": "https://sipi.usc.edu/database/misc.tar.gz",
    "sequences": "https://sipi.usc.edu/database/sequences.tar.gz",
}
IMAGE_SUFFIXES = {".tif", ".tiff"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, destination: Path) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RDHEI-EDR1-reproducibility/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as out:
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


def extract_grayscale(archive_path: Path, volume: str, output_root: Path, archive_url: str, archive_sha: str):
    accepted, skipped = [], []
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            member_path = Path(member.name)
            if not member.isfile() or member_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            source = archive.extractfile(member)
            if source is None:
                skipped.append({"member": member.name, "reason": "archive member could not be read"})
                continue
            raw = source.read()
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

            # Use only the archive member's basename below a fixed volume directory.
            # No archive path is extracted directly, preventing traversal.
            filename = member_path.name
            destination = output_root / volume / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError(f"refusing to overwrite existing image: {destination}")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/usc_sipi_gray")
    parser.add_argument("--archive-dir", default="data/usc_sipi_archives")
    parser.add_argument("--force", action="store_true", help="Allow output directories that already exist; existing image files are never overwritten.")
    args = parser.parse_args()

    output_root = Path(args.output_dir).expanduser().resolve()
    archive_root = Path(args.archive_dir).expanduser().resolve()
    if output_root.exists() and any(output_root.rglob("*.tif")) or output_root.exists() and any(output_root.rglob("*.tiff")):
        if not args.force:
            raise FileExistsError(
                f"{output_root} already contains TIFF files; choose a clean output directory or pass --force"
            )
    output_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)

    all_images, all_skipped, archive_records = [], [], []
    for volume, url in ARCHIVES.items():
        archive_path = archive_root / f"{volume}.tar.gz"
        if archive_path.exists():
            archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
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
            "grayscale_images": len(images),
            "skipped_image_members": len(skipped),
        })
        all_images.extend(images)
        all_skipped.extend([{"volume": volume, **row} for row in skipped])
        print(f"{volume}: retained {len(images)} native grayscale TIFFs; skipped {len(skipped)}", flush=True)

    manifest = {
        "dataset": "USC-SIPI Image Database",
        "preparation_script": "final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py",
        "source_homepage": "https://sipi.usc.edu/database/",
        "policy": "Only native single-frame 8-bit grayscale TIFFs (Pillow mode L, uint8, 2D) are retained. RGB files are not converted.",
        "archive_records": archive_records,
        "image_count_before_pixel_deduplication": len(all_images),
        "images": all_images,
        "skipped_image_members": all_skipped,
    }
    manifest_path = output_root / "dataset_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    print(f"Native grayscale TIFFs retained: {len(all_images)}")
    print("Pixel-identical copies are deduplicated later by run_gate.py using decoded pixels + dimensions.")


if __name__ == "__main__":
    main()
