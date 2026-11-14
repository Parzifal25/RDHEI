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
        correlation_cluster = Path(rel).stem
        texture_stem = Path(archive_member).stem.lower()

        if volume == "textures":
            is_constructed_texture_mosaic = (
                (texture_stem.startswith("texmos") and ".s512" not in member_basename)
                or member_basename.startswith("1.5.")
            )
            if is_constructed_texture_mosaic:
                classification = "constructed"
                group = "constructed_texture_mosaics"
                correlation_cluster = "constructed_texture_mosaics"
                if texture_stem.startswith("texmos"):
                    note = (
                        "USC-SIPI catalogue identifies this file as a texture mosaic assembled "
                        "from Brodatz texture regions. It is a real image-domain composite, "
                        "not an independent natural-scene photograph; report separately."
                    )
                else:
                    note = (
                        "USC-SIPI catalogue labels the 1.5.xx family as texture mosaics. "
                        "It is a constructed texture composition, not an independent "
                        "natural-scene photograph; report separately."
                    )
            else:
                group = "texture_scans"
                tokens = texture_stem.split(".")
                correlation_cluster = (
                    f"texture_series_{tokens[0]}.{tokens[1]}"
                    if len(tokens) >= 3 else f"texture_item_{texture_stem}"
                )
                note = (
                    "Native USC-SIPI grayscale texture scan. Images in the same catalogue "
                    "texture series share source material/context and are summarized as a "
                    "cluster rather than assumed independent scenes."
                )
        elif volume == "rotate":
            group = "rotated_texture_series"
            family = texture_stem.rsplit(".", 1)[0]
            correlation_cluster = f"rotated_texture_{family}"
            note = (
                f"USC-SIPI rotation variant from the {family} texture family. All angular "
                "variants of this source texture are a correlated cluster."
            )
        elif volume == "sequences":
            if texture_stem.startswith("motion"):
                group = "sequence_motion_toy_vehicles"
                correlation_cluster = "sequence_motion_toy_vehicles"
                note = (
                    "USC-SIPI Volume 4 toy-vehicle motion sequence; frames are correlated "
                    "observations of one source sequence."
                )
            else:
                parts = texture_stem.split(".")
                sequence_id = ".".join(parts[:2]) if len(parts) >= 2 else texture_stem
                frame = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else -1
                correlation_cluster = f"sequence_{sequence_id}"
                if sequence_id == "6.1":
                    group = "sequence_6_1_walter_cronkite"
                    note = "USC-SIPI Walter Cronkite moving-head sequence; frames are correlated."
                elif sequence_id == "6.2" and 1 <= frame <= 16:
                    group = "sequence_6_2_true_motion_frames_01_16"
                    note = (
                        "USC-SIPI chemical-plant close-view sequence, frames 1-16. "
                        "The database identifies these as a true motion sequence; frames "
                        "are correlated and grouped together."
                    )
                elif sequence_id == "6.2" and 17 <= frame <= 32:
                    group = "sequence_6_2_undirected_frames_17_32"
                    note = (
                        "USC-SIPI chemical-plant close-view frames 17-32. The database "
                        "states these show motion but no clear direction; they are not "
                        "pooled with the first 16-frame true-motion subset."
                    )
                elif sequence_id == "6.3":
                    group = "sequence_6_3_chemical_plant_far"
                    note = "USC-SIPI chemical-plant far-view sequence; frames are correlated."
                else:
                    group = "sequence_other"
                    note = "USC-SIPI grayscale sequence frame; related frames are correlated."
        elif volume == "misc":
            group = "miscellaneous_monochrome"
            parts = texture_stem.split(".")
            if len(parts) >= 2 and parts[0] in {"5", "7"}:
                correlation_cluster = f"misc_family_{parts[0]}.{parts[1]}"
            else:
                correlation_cluster = f"misc_item_{texture_stem}"
            note = (
                "USC-SIPI monochrome miscellaneous image. Calibration charts and "
                "test patterns are excluded; retained items are grouped by catalogue "
                "family where the filename indicates a shared series."
            )
        elif volume == "aerials":
            group = "monochrome_aerial"
            correlation_cluster = f"aerial_item_{texture_stem}"
            note = "USC-SIPI catalogue-listed monochrome aerial image."
        accepted.append({
            "path": Path(rel).as_posix(),
            "sha256": actual,
            "classification": classification,
            "corpus_group": group,
            "correlation_cluster": correlation_cluster,
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
            "maps, resolution charts, calibration wedges, pixel rulers, and unrecognized "
            "volumes are excluded; exact decoded-pixel duplicates are removed by the runner. "
            "Texture scans, 1.5.xx/texmos constructed mosaics, rotation families, aerial, "
            "miscellaneous, and sequence subgroups carry explicit group and correlation-cluster "
            "labels. Sequence 6.2 frames 1-16 and 17-32 are separated according to the "
            "USC-SIPI catalogue description. USC-SIPI's "
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
