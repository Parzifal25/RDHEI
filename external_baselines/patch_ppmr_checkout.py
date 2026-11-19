#!/usr/bin/env python3
"""Apply hash-pinned compatibility/correctness repairs to a temporary PPMR checkout.

Only the temporary checkout is modified. Exact source context and replacement counts
are checked; the pinned upstream repository is never changed.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PINNED_COMMIT = "21f397890289049798ced0f98d1482d629f93b06"

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_lines(path: Path):
    return path.read_bytes().splitlines(keepends=True)

def write_lines(path: Path, lines):
    path.write_bytes(b"".join(lines))

def patch_encrypt_image(path: Path):
    lines = read_lines(path)
    matches = [i for i, line in enumerate(lines)
               if b"[final_enbitplane7] = encrypt_All(" in line]
    assert len(matches) == 1, "Expected exactly one bit-plane-7 fallback"
    i7 = matches[0]
    assert i7 + 1 < len(lines) and b"%---" in lines[i7 + 1], (
        "Unexpected source context after bit-plane-7 fallback"
    )
    lines.insert(i7 + 1, b"end\r\n")
    calls = [i for i, line in enumerate(lines)
             if b"[Encrypt_I] = eight_to_one(" in line]
    assert len(calls) == 1, "Expected exactly one final eight-plane assembly"
    ci = calls[0]
    prior_ends = [i for i in range(max(0, ci - 3), ci)
                  if lines[i].strip() == b"end"]
    assert len(prior_ends) == 2, "Expected two branch terminators before final bit-plane assembly"
    # The inserted end closes plane 7. The first original end closes plane 8;
    # the second original end was the now-redundant outer plane-7 terminator.
    del lines[prior_ends[-1]]
    write_lines(path, lines)

def patch_extract_function(path: Path, func_prefix: bytes, count_name: bytes,
                           data_prefix: bytes, tag_name: bytes):
    lines = read_lines(path)
    starts = [
        i for i, line in enumerate(lines)
        if line.strip().split(b"=", 1)[0].strip() == count_name
        and b"=" in line
    ]
    funcs = [i for i, line in enumerate(lines)
             if line.lstrip().startswith(func_prefix)]
    assert len(starts) == 1 and len(funcs) == 1 and starts[0] < funcs[0], (
        f"Unexpected function layout in {path.name}: count declarations={starts}, function declarations={funcs}"
    )
    start_i, next_func_i = starts[0], funcs[0]
    end_i = next_func_i - 1
    while end_i >= 0 and not lines[end_i].strip():
        end_i -= 1
    assert end_i >= 0 and lines[end_i].strip() == b"end", (
        f"Could not identify enclosing function terminator in {path.name}"
    )

    if count_name == b"exUB_numData":
        counts = [f"ex_end_UB_t{i}".encode() for i in range(1, 9)]
        arrays = [f"exUBD{i}".encode() for i in range(1, 9)]
    else:
        counts = [f"exNUB_t{i}".encode() for i in range(1, 9)]
        arrays = [f"exNUBD{i}".encode() for i in range(1, 9)]

    newline = b"\r\n" if any(b"\r\n" in line for line in lines) else b"\n"
    replacement = [
        count_name + b" = " + b"+".join(counts) + b";" + newline
    ]
    for arr, cnt in zip(arrays, counts):
        replacement.append(arr + b" = " + arr + b"(1:" + cnt + b");" + newline)

    parts_name = data_prefix + b"_parts"
    replacement.extend([
        parts_name + b" = {" + b",".join(arrays) + b"};" + newline,
        data_prefix + b" = [];" + newline,
        b"for plane = 1:8" + newline,
        b"    if " + tag_name + b"(plane) == 1" + newline,
        b"        " + data_prefix + b" = [" + data_prefix + b", " + parts_name + b"{plane}];" + newline,
        b"    end" + newline,
        b"end" + newline,
    ])
    write_lines(path, lines[:start_i] + replacement + lines[end_i:])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != PINNED_COMMIT:
        raise SystemExit(f"Unexpected upstream commit {head}; expected {PINNED_COMMIT}")
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain"], text=True
    ).strip()
    if dirty:
        raise SystemExit(f"Temporary checkout was not clean before patching: {dirty}")

    names = ["Encrypt_image.m", "Extract_UBdata.m", "Extract_NUBdata.m"]
    before = {name: sha256((repo / name).read_bytes()) for name in names}
    patch_encrypt_image(repo / "Encrypt_image.m")
    patch_extract_function(
        repo / "Extract_UBdata.m", b"function [exUBD,exUB_t]",
        b"exUB_numData", b"exUB_Data", b"tag_preprocess"
    )
    patch_extract_function(
        repo / "Extract_NUBdata.m", b"function [exNUBD1,exNUB_t1]",
        b"exNUB_numData", b"exNUB_Data", b"tag_preprocess"
    )
    after = {name: sha256((repo / name).read_bytes()) for name in names}
    if before == after:
        raise SystemExit("No source hashes changed; expected three compatibility patches")

    patch = {
        "repository": "edu-yinzhaoxia/RDH-EI-based-on-pixel-prediction-and-multi-MSB-planes-rearrangement",
        "pinned_commit": PINNED_COMMIT,
        "training_performed": False,
        "edr2_checkpoint_modified": False,
        "temporary_checkout_only": True,
        "patches": [
            {
                "file": "Encrypt_image.m",
                "reason": "Close the bit-plane-7 conditional before the independent bit-plane-8 branch; the upstream nesting could leave final_enbitplane8 undefined.",
                "scope": "Control-flow repair only; each of the eight planes is still encrypted according to its own tag_preprocess flag."
            },
            {
                "file": "Extract_UBdata.m",
                "reason": "Concatenate extracted UB payloads from the actual active planes in ascending plane order; upstream concatenated the first m planes where m was only the number of active planes.",
                "scope": "Extraction ordering now follows the traversal order in Embed_data.m."
            },
            {
                "file": "Extract_NUBdata.m",
                "reason": "Concatenate extracted NUB payloads from the actual active planes in ascending plane order; upstream concatenated the first m planes where m was only the number of active planes.",
                "scope": "Extraction ordering now follows the traversal order in Embed_NUBdata.m."
            }
        ],
        "sha256_before": before,
        "sha256_after": after
    }
    Path(args.output).write_text(
        json.dumps(patch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(patch, indent=2))

if __name__ == "__main__":
    main()
