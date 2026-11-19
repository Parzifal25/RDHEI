#!/usr/bin/env python3
"""Validate one PPMR shard ledger against its deterministic input list."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

def read_ids(path):
    ids = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                image_id, _ = line.split("\t", 1)
                ids.append(image_id)
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-list", required=True)
    ap.add_argument("--ppmr", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    expected = read_ids(a.expected_list)
    with Path(a.ppmr).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    got = [row["image_id"] for row in rows]
    counts = Counter(got)
    duplicates = sorted(k for k, v in counts.items() if v > 1)
    missing = sorted(set(expected) - set(got))
    extra = sorted(set(got) - set(expected))
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
    }
    Path(a.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ledger_complete"]:
        raise SystemExit("PPMR shard ledger is incomplete or has duplicate image IDs")

if __name__ == "__main__":
    main()
