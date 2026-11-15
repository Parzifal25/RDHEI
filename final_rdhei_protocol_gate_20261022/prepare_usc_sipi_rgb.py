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

# Official USC-SIPI POSIX cksum values for the two RGB source volumes.
# This snapshot is a fail-closed fallback for runner environments that receive
# an anti-bot/interstitial HTML response instead of the publisher's checksum
# listing. Every downloaded TIFF is still checked with the system cksum tool.
# Source: https://sipi.usc.edu/database/checksums.php (retrieved 2026-11-15).
FALLBACK_CHECKSUM_TEXT = """aerials/2.1.01.tiff | 1220177504
aerials/2.1.02.tiff | 1128443052
aerials/2.1.03.tiff | 864150071
aerials/2.1.04.tiff | 2463040999
aerials/2.1.05.tiff | 3925712921
aerials/2.1.06.tiff | 1495561961
aerials/2.1.07.tiff | 4196485761
aerials/2.1.08.tiff | 3173993599
aerials/2.1.09.tiff | 3506737135
aerials/2.1.10.tiff | 357179428
aerials/2.1.11.tiff | 1432749410
aerials/2.1.12.tiff | 539719570
aerials/2.2.01.tiff | 3707813987
aerials/2.2.02.tiff | 2144688418
aerials/2.2.03.tiff | 3857634878
aerials/2.2.04.tiff | 3334241494
aerials/2.2.05.tiff | 2797045534
aerials/2.2.06.tiff | 4247764163
aerials/2.2.07.tiff | 3455463995
aerials/2.2.08.tiff | 955110744
aerials/2.2.09.tiff | 692177684
aerials/2.2.10.tiff | 2967134578
aerials/2.2.11.tiff | 2908148419
aerials/2.2.12.tiff | 3779859802
aerials/2.2.13.tiff | 1241016011
aerials/2.2.14.tiff | 667179025
aerials/2.2.15.tiff | 1820878201
aerials/2.2.16.tiff | 3170955228
aerials/2.2.17.tiff | 2126779588
aerials/2.2.18.tiff | 615390662
aerials/2.2.19.tiff | 1744768252
aerials/2.2.20.tiff | 3932755119
aerials/2.2.21.tiff | 3388477796
aerials/2.2.22.tiff | 3050430799
aerials/2.2.23.tiff | 1502591473
aerials/2.2.24.tiff | 1364544780
aerials/3.2.25.tiff | 93927779
aerials/wash-ir.tiff | 2112055147
misc/4.1.01.tiff | 2265807189
misc/4.1.02.tiff | 1070836551
misc/4.1.03.tiff | 3821551092
misc/4.1.04.tiff | 3344208216
misc/4.1.05.tiff | 1582167302
misc/4.1.06.tiff | 2410777738
misc/4.1.07.tiff | 2545388887
misc/4.1.08.tiff | 4286241145
misc/4.2.01.tiff | 3500310454
misc/4.2.03.tiff | 3944512653
misc/4.2.05.tiff | 3687832802
misc/4.2.06.tiff | 1958307154
misc/4.2.07.tiff | 2608899817
misc/5.1.09.tiff | 1164268028
misc/5.1.10.tiff | 1728730266
misc/5.1.11.tiff | 443324971
misc/5.1.12.tiff | 776391303
misc/5.1.13.tiff | 3183833270
misc/5.1.14.tiff | 3665441261
misc/5.2.08.tiff | 2911318840
misc/5.2.09.tiff | 2449781192
misc/5.2.10.tiff | 1594033806
misc/5.3.01.tiff | 2370538633
misc/5.3.02.tiff | 825310470
misc/7.1.01.tiff | 3058510718
misc/7.1.02.tiff | 3233139240
misc/7.1.03.tiff | 1086184008
misc/7.1.04.tiff | 3788018008
misc/7.1.05.tiff | 670509967
misc/7.1.06.tiff | 1153945945
misc/7.1.07.tiff | 2414551512
misc/7.1.08.tiff | 2492528975
misc/7.1.09.tiff | 88428538
misc/7.1.10.tiff | 3432687112
misc/7.2.01.tiff | 1366161104
misc/boat.512.tiff | 2515944092
misc/gray21.512.tiff | 3650207747
misc/house.tiff | 3014996685
misc/ruler.512.tiff | 3474880593
"""


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


def parse_checksum_text(text: str) -> dict[str, int]:
    pairs = re.findall(r"([A-Za-z0-9_./-]+\.tiff)\s*\|\s*(\d+)", text)
    return {name: int(value) for name, value in pairs}


def parse_checksums(page: bytes) -> dict[str, int]:
    text = html.unescape(page.decode("utf-8", errors="replace"))
    result = parse_checksum_text(text)
    if result:
        return result
    fallback = parse_checksum_text(FALLBACK_CHECKSUM_TEXT)
    if fallback:
        return fallback
    raise ValueError("could not parse live or embedded official USC-SIPI TIFF checksum list")

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
    checksum_response_sha = sha256_bytes(checksum_bytes)
    live_text = html.unescape(checksum_bytes.decode("utf-8", errors="replace"))
    official_checksums = parse_checksum_text(live_text)
    checksum_source_mode = "live_publisher_page"
    if not official_checksums:
        official_checksums = parse_checksum_text(FALLBACK_CHECKSUM_TEXT)
        checksum_source_mode = "embedded_official_volume_snapshot"
    if not official_checksums:
        raise ValueError("could not parse live or embedded official USC-SIPI TIFF checksum list")
    checksum_values_sha = sha256_bytes(
        json.dumps(official_checksums, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

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
        "checksum_page_sha256": checksum_response_sha if checksum_source_mode == "live_publisher_page" else None,
        "checksum_response_sha256": checksum_response_sha,
        "checksum_values_sha256": checksum_values_sha,
        "checksum_source_mode": checksum_source_mode,
        "checksum_values_count": len(official_checksums),
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
