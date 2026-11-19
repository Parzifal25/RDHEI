#!/usr/bin/env python3
"""Validate a PPMR shard ledger and attach pinned source/pixel hashes from corpus metadata."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

def image_id(relative_path):
    return relative_path.replace("/", "__").replace(".tiff", "")

def read_ids(path):
    ids = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                image_id_value, _ = line.split("\t", 1)
                ids.append(image_id_value)
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-list", required=True)
    ap.add_argument("--canonical", required=True)
    ap.add_argument("--ppmr", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    expected = read_ids(a.expected_list)
    canonical = json.loads(Path(a.canonical).read_text(encoding="utf-8"))
    canonical_by_id = {image_id(row["relative_path"]): row for row in canonical}
    if set(expected) - set(canonical_by_id):
        raise SystemExit("Shard input list contains image IDs absent from canonical hash manifest")

    with Path(a.ppmr).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    got = [row["image_id"] for row in rows]
    counts = Counter(got)
    duplicates = sorted(k for k, v in counts.items() if v > 1)
    missing = sorted(set(expected) - set(got))
    extra = sorted(set(got) - set(expected))

    # Attach hashes from the immutable, previously verified corpus manifest to
    # each ledger row. The shard worker reads these exact staged manifest paths.
    for row in rows:
        meta = canonical_by_id.get(row["image_id"])
        if meta is not None:
            row["source_file_sha256"] = meta["source_sha256"]
            row["decoded_pixel_sha256"] = meta["pixels_sha256"]
    if rows:
        fieldnames = list(rows[0])
        with Path(a.ppmr).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    exact_rows = [
        row for row in rows
        if row.get("status") == "PASS"
        and row.get("payload_exact", "").lower() in {"1", "true"}
        and row.get("image_exact", "").lower() in {"1", "true"}
    ]
    result = {
        "expected_images": len(expected),
        "ledger_rows": len(rows),
        "unique_images": len(set(got)),
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "exact_roundtrip_rows": len(exact_rows),
        "status_counts": dict(sorted(Counter(row.get("status", "MISSING_STATUS") for row in rows).items())),
        "ledger_complete": len(rows) == len(expected) and len(set(got)) == len(expected)
            and not missing and not extra and not duplicates,
        "all_exact": len(exact_rows) == len(expected),
        "source_and_pixel_hashes_attached_from": "canonical_corpus_verified.json"
    }
    Path(a.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ledger_complete"]:
        raise SystemExit("PPMR shard ledger is incomplete or has duplicate image IDs")

if __name__ == "__main__":
    main()
