#!/usr/bin/env python3
"""Select one hash-pinned, deterministic visual example per USC-SIPI stratum."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", default="data/usc_sipi_gray")
    ap.add_argument("--baseline-dir", default="data/kodak_gray")
    ap.add_argument("--evidence-dir", default="/tmp/edr2-full-natural-corpus-evidence")
    ap.add_argument("--output-dir", default="data/usc_sipi_visual_samples")
    args = ap.parse_args()

    src = Path(args.source_dir).resolve()
    baseline = Path(args.baseline_dir).resolve()
    evidence = Path(args.evidence_dir).resolve()
    out = Path(args.output_dir).resolve()
    for name in ("capacity_summary.csv", "corpus.json"):
        if not (evidence / name).is_file():
            raise FileNotFoundError(evidence / name)
    allow_path = src / "natural_image_allowlist.json"
    if not allow_path.is_file():
        raise FileNotFoundError(allow_path)

    import csv
    capacities = list(csv.DictReader((evidence / "capacity_summary.csv").open(newline="", encoding="utf-8")))
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    allow_rows = {r["path"]: r for r in allow["images"]}
    groups = sorted({r["corpus_group"] for r in allow["images"]})

    selected = []
    for group in groups:
        rows = [r for r in capacities if r.get("corpus_group") == group]
        if not rows:
            raise ValueError(f"no capacity row for curated group {group}")
        positive = [r for r in rows if r.get("accepted", "").lower() == "true"]
        pool = positive if positive else rows
        row = sorted(pool, key=lambda x: x["image"])[0]
        rel = PurePosixPath(row["image"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe sample path: {row['image']}")
        source = (src / Path(*rel.parts)).resolve()
        if src not in source.parents or not source.is_file():
            raise FileNotFoundError(source)
        metadata = allow_rows.get(rel.as_posix())
        if not metadata:
            raise ValueError(f"sample {rel} is not in the allowlist")
        actual_hash = sha256_file(source)
        if actual_hash != metadata["sha256"]:
            raise ValueError(f"sample hash mismatch for {rel}")

        selected.append({
            "path": rel.as_posix(),
            "corpus_group": group,
            "classification": metadata["classification"],
            "accepted_in_adaptive_run": row.get("accepted", "").lower() == "true",
            "selected_phase": row.get("selected_lattice_phase", ""),
            "net_capacity_bits": int(float(row.get("net_capacity_bits", "0"))),
            "source_sha256": actual_hash,
            "pixels_sha256": row.get("pixels_sha256", ""),
            "selection_policy": "lexicographically first positive-capacity image in each stratum; if none, first image in that stratum",
        })

    # Include the six original root-level baseline files in the gallery whenever
    # they were supplied to the main adaptive run. These are not USC-SIPI allowlist
    # entries; they form a separate, explicitly provenance-labelled baseline stratum.
    baseline_names = ["Airplane.png", "Baboon.png", "Goldhill.png", "Jetplane.png", "Lena.png", "Peppers.png"]
    baseline_missing = []
    if baseline.is_dir():
        baseline_rows = {r["image"]: r for r in capacities}
        for filename in baseline_names:
            source = baseline / filename
            if not source.is_file():
                baseline_missing.append(filename)
                continue
            row = baseline_rows.get(filename)
            if row is None:
                raise ValueError(f"baseline file {filename} is present but absent from adaptive capacity evidence")
            actual_hash = sha256_file(source)
            if actual_hash != row["source_sha256"]:
                raise ValueError(f"baseline source hash mismatch for {filename}")
            relative = PurePosixPath("baseline_images") / filename
            selected.append({
                "path": relative.as_posix(),
                "source_path": str(source),
                "corpus_group": "original_six_baseline",
                "classification": "natural",
                "accepted_in_adaptive_run": row.get("accepted", "").lower() == "true",
                "selected_phase": row.get("selected_lattice_phase", ""),
                "net_capacity_bits": int(float(row.get("net_capacity_bits", "0"))),
                "source_sha256": actual_hash,
                "pixels_sha256": row.get("pixels_sha256", ""),
                "selection_policy": "included as one of the six predefined project baseline images",
            })
    else:
        baseline_missing = baseline_names[:]

    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    for row in selected:
        rel = PurePosixPath(row["path"])
        target = out / Path(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Path(row.get("source_path", src / Path(*rel.parts))).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, target)
    sample_allowlist_rows = [allow_rows[r["path"]] for r in selected if r["path"] in allow_rows]
    sample_allowlist_rows.extend({
        "path": row["path"],
        "sha256": row["source_sha256"],
        "classification": "natural",
        "corpus_group": row["corpus_group"],
        "correlation_cluster": f"baseline_{Path(row['path']).stem.lower()}",
        "curation_note": (
            "One of the six predefined project grayscale baselines; exact source-file "
            "SHA-256 is bound to the corresponding adaptive-run capacity record. "
            "The source provenance should be described using the project baseline manifest."
        ),
    } for row in selected if row["corpus_group"] == "original_six_baseline")
    sample_allowlist = {
        "dataset": "EDR2 representative visual sample subset",
        "source_manifest": str(allow_path),
        "baseline_source_directory": str(baseline),
        "missing_original_baseline_files": baseline_missing,
        "images": sample_allowlist_rows,
    }
    (out / "natural_image_allowlist.json").write_text(
        json.dumps(sample_allowlist, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "sample_selection.json").write_text(
        json.dumps({
            "selection_policy": "one lexicographically first positive-capacity image per curated stratum, or first image where the entire stratum has nonpositive net capacity",
            "selected_count": len(selected),
            "selected": selected,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(out), "selected_count": len(selected), "selected": selected}, indent=2))


if __name__ == "__main__":
    main()
