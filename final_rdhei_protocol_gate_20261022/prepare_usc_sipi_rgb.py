#!/usr/bin/env python3
"""Download and curate native 24-bit RGB images from official USC-SIPI volumes.

The script validates each TIFF against USC-SIPI's published POSIX cksum list,
then retains only native Pillow mode RGB, uint8, even-sized images. It never
converts grayscale/RGBA/palette/16-bit images.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import tarfile
import urllib.request
from io import BytesIO
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

ARCHIVES = {
    "aerials": "https://sipi.usc.edu/database/aerials.tar.gz",
    "misc": "https://sipi.usc.edu/database/misc.tar.gz",
}
CHECKSUMS_URL = "https://sipi.usc.edu/database/checksums.php"
DATABASE_URL = "https://sipi.usc.edu/database/"
EXPECTED_CATALOGUE_COUNTS = {"aerials": 37, "misc": 16}


def fetch(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CC-EDR2-RGB-research-dataset-preparer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_hash(array: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    digest.update(b"|uint8|RGB|")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def parse_checksums(page: bytes) -> dict[str, int]:
    text = html.unescape(page.decode("utf-8", errors="replace"))
    pairs = re.findall(r"([A-Za-z0-9_./-]+\.tiff)\s*\|\s*(\d+)", text)
    result = {name: int(value) for name, value in pairs}
    if not result:
        raise ValueError("could not parse published USC-SIPI TIFF checksum list")
    return result


def posix_cksum(path: Path) -> int:
    completed = subprocess.run(
        ["cksum", str(path)], check=True, capture_output=True, text=True
    )
    return int(completed.stdout.split()[0])


def extract_safe_member(archive: tarfile.TarFile, member: tarfile.TarInfo, destination: Path) -> Path:
    name = PurePosixPath(member.name)
    if name.is_absolute() or ".." in name.parts or len(name.parts) != 2:
        raise ValueError(f"unsafe/unexpected USC-SIPI archive member path: {member.name!r}")
    if name.parts[0] not in ARCHIVES or not member.isfile():
        raise ValueError(f"unexpected archive entry type/path: {member.name!r}")
    target = destination / Path(*name.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"could not read archive member {member.name!r}")
    with stream, target.open("wb") as output:
        shutil.copyfileobj(stream, output)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--keep-archives", action="store_true")
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    checksum_bytes = fetch(CHECKSUMS_URL)
    checksum_sha = sha256_bytes(checksum_bytes)
    official_checksums = parse_checksums(checksum_bytes)

    archive_records = {}
    accepted = []
    skipped = []
    seen_pixels = set()

    for volume, url in ARCHIVES.items():
        archive_bytes = fetch(url)
        archive_sha = sha256_bytes(archive_bytes)
        archive_records[volume] = {
            "url": url,
            "sha256": archive_sha,
            "bytes": len(archive_bytes),
        }
        archive_path = output / f"{volume}.tar.gz"
        archive_path.write_bytes(archive_bytes)
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as archive:
            for member in sorted(archive.getmembers(), key=lambda row: row.name):
                rel = PurePosixPath(member.name).as_posix()
                if not rel.endswith(".tiff"):
                    continue
                if not member.isfile():
                    skipped.append({"path": rel, "reason": "not a regular TIFF file"})
                    continue
                if rel not in official_checksums:
                    raise ValueError(f"no official USC-SIPI checksum entry for {rel}")

                path = extract_safe_member(archive, member, output)
                actual_cksum = posix_cksum(path)
                expected_cksum = official_checksums[rel]
                if actual_cksum != expected_cksum:
                    raise ValueError(
                        f"official checksum mismatch for {rel}: expected {expected_cksum}, got {actual_cksum}"
                    )

                try:
                    with Image.open(path) as image:
                        if getattr(image, "n_frames", 1) != 1:
                            raise ValueError("multi-frame TIFF")
                        mode = image.mode
                        array = np.asarray(image)
                    if mode != "RGB":
                        skipped.append({"path": rel, "reason": f"native TIFF mode is {mode}, not RGB"})
                        path.unlink(missing_ok=True)
                        continue
                    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3:
                        skipped.append({"path": rel, "reason": f"native array is {array.dtype}/{array.shape}, not uint8 RGB"})
                        path.unlink(missing_ok=True)
                        continue
                    if array.shape[0] % 2 or array.shape[1] % 2:
                        skipped.append({"path": rel, "reason": f"odd image dimensions {array.shape[:2]}"})
                        path.unlink(missing_ok=True)
                        continue
                    array = np.ascontiguousarray(array)
                except Exception as exc:
                    skipped.append({"path": rel, "reason": f"TIFF decode/validation error: {type(exc).__name__}: {exc}"})
                    path.unlink(missing_ok=True)
                    continue

                digest = pixel_hash(array)
                if digest in seen_pixels:
                    skipped.append({"path": rel, "reason": "duplicate decoded RGB pixels"})
                    path.unlink(missing_ok=True)
                    continue
                seen_pixels.add(digest)
                accepted.append({
                    "path": rel,
                    "volume": volume,
                    "corpus_group": "aerial_colour" if volume == "aerials" else "miscellaneous_colour",
                    "correlation_cluster": f"{volume}:{PurePosixPath(rel).stem}",
                    "source_url": url,
                    "source_archive_sha256": archive_sha,
                    "published_posix_cksum": expected_cksum,
                    "observed_posix_cksum": actual_cksum,
                    "file_sha256": sha256_bytes(path.read_bytes()),
                    "pixel_sha256": digest,
                    "width": int(array.shape[1]),
                    "height": int(array.shape[0]),
                    "mode": mode,
                    "dtype": "uint8",
                    "channels": 3,
                    "file_bytes": int(path.stat().st_size),
                    "curation_note": "Native single-frame 24-bit RGB TIFF from the official USC-SIPI volume; checksum verified against the publisher's published list; no conversion performed.",
                })

        expected = EXPECTED_CATALOGUE_COUNTS[volume]
        actual = sum(row["volume"] == volume for row in accepted)
        if actual > expected:
            raise ValueError(f"{volume}: accepted {actual} native RGB images, exceeds catalogue count {expected}")

    manifest = {
        "dataset": "USC-SIPI native RGB evaluation subset",
        "source_database": DATABASE_URL,
        "checksum_page": CHECKSUMS_URL,
        "checksum_page_sha256": checksum_sha,
        "archive_records": archive_records,
        "catalogue_expected_colour_images": EXPECTED_CATALOGUE_COUNTS,
        "accepted_native_rgb_images": len(accepted),
        "accepted_by_volume": {
            volume: sum(row["volume"] == volume for row in accepted)
            for volume in ARCHIVES
        },
        "skipped_candidates": len(skipped),
        "policy": [
            "Only native single-frame TIFF mode RGB, uint8, HxWx3 images with even dimensions are accepted.",
            "No grayscale conversion, resizing, cropping, palette expansion, 16-bit conversion, or recompression.",
            "Every TIFF candidate is checked against the publisher's POSIX cksum before decoding.",
            "Exact decoded RGB duplicates are removed.",
            "USC-SIPI notes that it does not own the copyright of most images and that copyright status may be unknown. Researchers must review the publisher's copyright information before publication or redistribution.",
        ],
        "images": accepted,
        "skipped": skipped,
    }
    (output / "rgb_source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not args.keep_archives:
        for volume in ARCHIVES:
            (output / f"{volume}.tar.gz").unlink(missing_ok=True)

    summary = {
        "accepted_native_rgb_images": len(accepted),
        "accepted_by_volume": manifest["accepted_by_volume"],
        "skipped_candidates": len(skipped),
        "archive_sha256": {name: value["sha256"] for name, value in archive_records.items()},
        "manifest": str(output / "rgb_source_manifest.json"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
