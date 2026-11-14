#!/usr/bin/env python3
"""Create a hash-pinned USC-SIPI allowlist from the official archive inventory.

The policy is catalogue-based and explicit: native grayscale image captures are
retained by volume; segmentation-information maps and calibration charts are
excluded; correlated texture variants and sequence frames are tagged so they
can be summarized separately. No image is resized, converted, or recompressed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXCLUSIONS = {
    ("textures", "texmos2.s512"): "segmentation-information map, not a source image",
    ("textures", "texmos3.s512"): "segmentation-information map, not a source image",
    ("misc", "5.1.13"): "resolution/calibration chart, not a natural image",
    ("misc", "gray21.512"): "21-level calibration step wedge, not a natural image",
    ("misc", "ruler.512"): "pixel ruler calibration image, not a natural image",
}

GROUPS = {
    "textures": (
        "texture_scans_and_mosaics",
        "USC-SIPI Volume 1: monochrome Brodatz texture scans and texture mosaics. "
        "Related originals, histogram-equalized versions, and resolution variants "
        "are correlated; summarize this subgroup separately."
    ),
    "rotate": (
        "rotated_texture_series",
        "USC-SIPI rotated texture series: the same thirteen source textures digitized "
        "at multiple angles. These are correlated rotation variants, not independent "
        "natural-scene photographs; summarize separately."
    ),
    "aerials": (
        "monochrome_aerial",
        "USC-SIPI Volume 2: catalogue-listed monochrome aerial image. "
        "This subgroup contains a single source image."
    ),
    "misc": (
        "miscellaneous_monochrome",
        "USC-SIPI Volume 3: catalogue-listed monochrome miscellaneous image. "
        "Resolution charts, calibration wedges, and pixel rulers are excluded."
    ),
    "sequences": (
        "monochrome_sequence_frames",
        "USC-SIPI Volume 4: individual grayscale frames from the documented image "
        "sequences. Adjacent frames are correlated; summarize by sequence as well "
        "as by frame."
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_allowlist(manifest_path: Path, output_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset") != "USC-SIPI Image Database":
        raise ValueError("manifest is not identified as the USC-SIPI Image Database")
    root = manifest_path.parent
    candidates = manifest.get("images")
    if not isinstance(candidates, list):
        raise ValueError("dataset manifest must contain an images array")

    accepted, excluded = [], []
    seen_paths = set()
    for row in candidates:
        rel = row.get("path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"unsafe or missing relative path: {rel!r}")
        if rel in seen_paths:
            raise ValueError(f"duplicate path in dataset manifest: {rel}")
        seen_paths.add(rel)

        parts = Path(rel).parts
        if len(parts) < 2:
            excluded.append({"path": rel, "reason": "missing USC-SIPI volume directory"})
            continue
        volume = parts[0].lower()
        archive_member = Path(str(row.get("archive_member", ""))).name
        member_basename = archive_member.lower()
        member_stem = Path(member_basename).stem.lower()
        exclusion = EXCLUSIONS.get((volume, member_basename)) or EXCLUSIONS.get((volume, member_stem))
        if exclusion:
            excluded.append({"path": rel, "archive_member": archive_member, "reason": exclusion})
            continue
        if volume not in GROUPS:
            excluded.append({"path": rel, "reason": f"unrecognized USC-SIPI volume: {volume}"})
            continue

        shape = row.get("shape")
        if (
            row.get("mode") != "L"
            or row.get("dtype") != "uint8"
            or not isinstance(shape, list)
            or len(shape) != 2
            or not all(isinstance(v, int) and v > 0 for v in shape)
        ):
            excluded.append({"path": rel, "reason": "not a native two-dimensional uint8 grayscale image"})
            continue
        if shape[0] % 2 or shape[1] % 2:
            excluded.append({"path": rel, "reason": f"odd image dimensions outside current EDR2 scope: {shape}"})
            continue

        source_file = (root / rel).resolve()
        if root.resolve() not in source_file.parents or not source_file.is_file():
            raise FileNotFoundError(f"manifest image is missing or outside the corpus root: {rel}")
        expected = row.get("file_sha256")
        actual = sha256_file(source_file)
        if not isinstance(expected, str) or actual.lower() != expected.lower():
            raise ValueError(f"source-file SHA-256 mismatch for {rel}: {actual}")

        group, note = GROUPS[volume]
        classification = "natural"
        if volume == "textures" and member_basename.startswith("texmos") and ".s512" not in member_basename:
            classification = "constructed"
            group = "constructed_texture_mosaics"
            note = (
                "USC-SIPI describes this file as a mosaic assembled from eight Brodatz "
                "textures. It is a real image-domain composite, but not an independent "
                "natural-scene photograph; report separately from natural images."
            )
        accepted.append({
            "path": Path(rel).as_posix(),
            "sha256": actual,
            "classification": classification,
            "corpus_group": group,
            "curation_note": (
                f"{note} Source archive member: {archive_member}. "
                "Verified from the official USC-SIPI archive inventory as a native "
                "single-frame 8-bit grayscale image with even dimensions; original "
                "file bytes are hash-pinned and are not converted or resized."
            ),
        })

    if not accepted:
        raise ValueError("no USC-SIPI images passed the catalogue curation and EDR2 format policy")

    result = {
        "dataset": "USC-SIPI Image Database",
        "source_homepage": "https://sipi.usc.edu/database/",
        "curation_policy": (
            "Catalogue-based inclusion of native single-frame 8-bit grayscale TIFF "
            "images from the five official archive groups. Images must have even "
            "height and width. RGB/16-bit/non-grayscale images, segmentation-information "
            "maps, resolution charts, calibration wedges, pixel rulers, unrecognized "
            "volumes, and duplicate decoded pixels are excluded. Textures, rotated "
            "texture series, aerial imagery, miscellaneous imagery, and sequence frames "
            "remain tagged in separate corpus groups; USC-assembled mosaics use the "
            "constructed classification and are not pooled with natural photographs.  USC-SIPI's "
            "copyright notes contain mixed and sometimes unknown per-image rights; "
            "this experiment manifest is not permission to redistribute source images."
        ),
        "accepted_image_count_before_pixel_deduplication": len(accepted),
        "excluded_catalogue_or_format_candidates": excluded,
        "images": accepted,
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/usc_sipi_gray/dataset_manifest.json")
    parser.add_argument("--output", default="data/usc_sipi_gray/natural_image_allowlist.json")
    args = parser.parse_args()
    result = create_allowlist(Path(args.manifest).expanduser().resolve(), Path(args.output).expanduser().resolve())
    group_counts = {}
    for row in result["images"]:
        group_counts[row["corpus_group"]] = group_counts.get(row["corpus_group"], 0) + 1
    print(json.dumps({
        "accepted_before_pixel_deduplication": result["accepted_image_count_before_pixel_deduplication"],
        "excluded_catalogue_or_format_candidates": len(result["excluded_catalogue_or_format_candidates"]),
        "groups": group_counts,
        "allowlist": str(Path(args.output).expanduser().resolve()),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
