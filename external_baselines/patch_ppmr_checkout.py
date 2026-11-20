#!/usr/bin/env python3
"""Apply explicit, hash-pinned PPMR compatibility repairs to a temporary checkout.

The upstream repository is untouched. This script reconstructs the two malformed
MSB-plane-7/8 conditionals explicitly rather than relying on positional end removal.
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

def patch_plane7_plane8(path: Path, variable_prefix: bytes, plane7_input: bytes,
                        plane8_input: bytes, assembly_prefix: bytes):
    lines = read_lines(path)
    i7 = [i for i, line in enumerate(lines)
          if line.strip().startswith(b"if tag_preprocess(7)==1")]
    f7 = [i for i, line in enumerate(lines)
          if plane7_input in line]
    i8 = [i for i, line in enumerate(lines)
          if line.strip().startswith(b"if tag_preprocess(8)==1")]
    f8 = [i for i, line in enumerate(lines)
          if plane8_input in line]
    assemble = [i for i, line in enumerate(lines)
                if line.lstrip().startswith(assembly_prefix)]
    assert all(len(x) == 1 for x in (i7, f7, i8, f8, assemble)), (
        f"{path.name}: expected unique plane-7/8 branch markers"
    )
    i7, f7, i8, f8, assemble = i7[0], f7[0], i8[0], f8[0], assemble[0]
    assert i7 < f7 < i8 < f8 < assemble, (
        f"{path.name}: unexpected plane-7/8 source order"
    )

    # The upstream plane-7 ELSE accidentally contains the entire plane-8 IF.
    # Reconstruct the block boundaries:
    #   plane 7: if ... else ... end
    #   plane 8: if ... else ... end
    # followed immediately by final plane assembly and the function terminator.
    end8_candidates = [
        i for i in range(f8 + 1, assemble)
        if lines[i].strip() == b"end"
    ]
    assert len(end8_candidates) == 2, (
        f"{path.name}: expected the plane-8 end and the erroneous outer plane-7 end; "
        f"found {end8_candidates}"
    )
    end8 = end8_candidates[0]
    redundant_outer_end = end8_candidates[1]
    between = [line for line in lines[end8 + 1:assemble] if line.strip()]
    assert len(between) == 1 and between[0].strip() == b"end", (
        f"{path.name}: unexpected source between plane-8 branch and assembly"
    )
    newline = next((b"\r\n" if b"\r\n" in line else b"\n"
                    for line in lines if line.endswith((b"\r\n", b"\n"))), b"\n")
    # Keep every original byte except: close plane 7 immediately after its ELSE
    # fallback, and drop the now-redundant original outer END after plane 8.
    repaired = (
        lines[:f7 + 1]
        + [b"end" + newline]
        + lines[f7 + 1:redundant_outer_end]
        + lines[redundant_outer_end + 1:]
    )
    # The preceding slice still contains the plane-8 closing END, and the
    # assembly now follows it directly. Confirm branch order after reconstruction.
    new_i8 = [i for i, line in enumerate(repaired)
              if line.strip().startswith(b"if tag_preprocess(8)==1")]
    new_assembly = [i for i, line in enumerate(repaired)
                    if line.lstrip().startswith(assembly_prefix)]
    assert len(new_i8) == len(new_assembly) == 1 and new_i8[0] < new_assembly[0]
    assert repaired[new_assembly[0] - 1].strip() == b"end", (
        f"{path.name}: plane-8 conditional is not closed immediately before assembly"
    )
    write_lines(path, repaired)

def patch_extract_function(path: Path, func_prefix: bytes, count_name: bytes,
                           data_prefix: bytes, tag_name: bytes):
    lines = read_lines(path)
    starts = [
        i for i, line in enumerate(lines)
        if line.strip().split(b"=", 1)[0].strip() == count_name and b"=" in line
    ]
    funcs = [i for i, line in enumerate(lines)
             if line.lstrip().startswith(func_prefix)]
    assert len(starts) == 1 and len(funcs) == 1 and starts[0] < funcs[0], (
        f"Unexpected extraction function layout in {path.name}"
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

    names = ["Encrypt_image.m", "decrypt_image.m", "Extract_UBdata.m", "Extract_NUBdata.m"]
    before = {name: sha256((repo / name).read_bytes()) for name in names}

    patch_plane7_plane8(
        repo / "Encrypt_image.m", b"final_enbitplane",
        b"[final_enbitplane7] = encrypt_All(",
        b"[final_enbitplane8] = encrypt_All(",
        b"[Encrypt_I] = eight_to_one("
    )
    patch_plane7_plane8(
        repo / "decrypt_image.m", b"final_debitplane",
        b"[final_debitplane7] = decrypt_All(",
        b"[final_debitplane8] = decrypt_All(",
        b"[Decrypt_I] = eight_to_one("
    )
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
        raise SystemExit("No source hashes changed; expected four compatibility patches")
    patch = {
        "repository": "edu-yinzhaoxia/RDH-EI-based-on-pixel-prediction-and-multi-MSB-planes-rearrangement",
        "pinned_commit": PINNED_COMMIT,
        "training_performed": False,
        "edr2_checkpoint_modified": False,
        "temporary_checkout_only": True,
        "patches": [
            {
                "file": "Encrypt_image.m",
                "reason": "The bit-plane-8 conditional was nested inside bit-plane 7. The corrected source closes plane 7 before opening the independent plane-8 branch.",
                "scope": "Control-flow correction; same upstream per-plane operations and cryptographic functions."
            },
            {
                "file": "decrypt_image.m",
                "reason": "The paired decryption function had the same malformed nesting. The corrected source closes plane 7 before opening the independent plane-8 branch.",
                "scope": "Control-flow correction; restores the inverse per-plane operation ordering."
            },
            {
                "file": "Extract_UBdata.m",
                "reason": "The upstream code concatenated the first m planes, although m is only the number of active planes. The corrected code concatenates the actual active planes in ascending plane order.",
                "scope": "Extraction order now matches Embed_data.m traversal."
            },
            {
                "file": "Extract_NUBdata.m",
                "reason": "The upstream code concatenated the first m planes, although m is only the number of active planes. The corrected code concatenates the actual active planes in ascending plane order.",
                "scope": "Extraction order now matches Embed_NUBdata.m traversal."
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
