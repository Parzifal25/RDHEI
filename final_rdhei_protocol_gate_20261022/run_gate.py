"""Natural-image EDR2 corpus gate: deterministic discovery, capacity ledger, fresh-process round trips."""
import argparse
import csv
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import numpy as np
from PIL import Image

import protocol as pr
import wire

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
D = None
SUPPORTED_SUFFIXES = {".png", ".pgm", ".bmp", ".tif", ".tiff"}
BASELINE_STEMS = {"airplane", "baboon", "goldhill", "jetplane", "lena", "peppers"}
IMAGE_EXTENSIONS = sorted(SUPPORTED_SUFFIXES)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the frozen EDR2 protocol on every distinct 8-bit grayscale image found."
    )
    parser.add_argument(
        "--data-dir",
        action="append",
        default=None,
        help="Input directory; repeat to add corpora. Files are discovered recursively.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="New output directory. Defaults to a timestamped folder beside this script's evidence directory.",
    )
    parser.add_argument(
        "--allow-missing-baseline",
        action="store_true",
        help="Run an additional corpus even when one or more of the original six baseline names are absent.",
    )
    parser.add_argument("--seed", type=int, default=20261113, help="Seed for reproducible payload bits and test mutations.")
    parser.add_argument("--short-payload-bits", type=int, default=37)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--keep-artifacts", action="store_true", help="Retain all reserved/cipher/recovered image and payload arrays for every case.")
    return parser.parse_args()


def default_data_dirs():
    candidates = [
        ROOT / "data" / "kodak_gray",
        ROOT / "data" / "usc_sipi_gray",
        ROOT.parent / "data" / "kodak_gray",  # legacy layout used by the first gate
    ]
    found, seen = [], set()
    for path in candidates:
        key = str(path.resolve())
        if path.is_dir() and key not in seen:
            found.append(path)
            seen.add(key)
    return found


def discover_files(data_dirs):
    files, seen = [], set()
    for directory in data_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"input directory does not exist: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                resolved = path.resolve()
                if resolved not in seen:
                    files.append((directory, path))
                    seen.add(resolved)
    return files


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_native_gray(path):
    """Accept true 8-bit grayscale only; do not silently convert RGB or 16-bit images."""
    with Image.open(path) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError(f"multi-frame image is outside this 2D protocol scope: {image.n_frames} frames")
        if image.mode != "L":
            raise ValueError(f"expected native 8-bit grayscale TIFF/PNG (mode L), found mode {image.mode}")
        array = np.asarray(image)
    if array.dtype != np.uint8 or array.ndim != 2:
        raise ValueError(f"expected 2D uint8 grayscale, got dtype={array.dtype}, shape={array.shape}")
    return np.ascontiguousarray(array)


def pixel_sha256(array):
    digest = hashlib.sha256()
    digest.update(str(tuple(array.shape)).encode("ascii"))
    digest.update(b"|uint8|")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def rel_label(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def load_corpus(data_dirs, allow_missing_baseline):
    discovered = discover_files(data_dirs)
    if not discovered:
        raise FileNotFoundError(
            "no supported grayscale image files found; expected .png/.pgm/.bmp/.tif/.tiff under "
            + ", ".join(str(x) for x in data_dirs)
        )

    corpus, skipped, duplicates = [], [], []
    pixel_owner = {}
    baseline_stems = set()

    for directory, path in discovered:
        label = rel_label(path, directory)
        try:
            array = read_native_gray(path)
        except Exception as exc:
            skipped.append(
                dict(path=str(path), relative_path=label, accepted=False,
                     reason=f"{type(exc).__name__}: {exc}")
            )
            continue

        if directory.name.lower() == "kodak_gray":
            baseline_stems.add(path.stem.lower())
        digest = pixel_sha256(array)
        record = dict(
            name=label,
            safe_name=re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_"),
            source=str(path),
            dataset=str(directory),
            relative_path=label,
            source_sha256=file_sha256(path),
            pixels_sha256=digest,
            shape=list(array.shape),
            pixels=int(array.size),
        )
        if digest in pixel_owner:
            duplicates.append(
                dict(path=str(path), relative_path=label, duplicate_of=pixel_owner[digest],
                     pixels_sha256=digest, reason="identical decoded uint8 pixels and dimensions")
            )
            continue
        pixel_owner[digest] = label
        corpus.append(record)

    missing_baseline = sorted(BASELINE_STEMS - baseline_stems)
    if missing_baseline and not allow_missing_baseline:
        raise ValueError(
            "original baseline image names are missing: " + ", ".join(missing_baseline)
            + ". Keep the six original files in a directory named data/kodak_gray; pass --allow-missing-baseline only for a separate expanded-corpus-only run."
        )
    if not corpus:
        raise ValueError("no valid native 8-bit grayscale images remained after input validation")

    inventory = list(corpus)
    return corpus, skipped, duplicates, inventory, missing_baseline


def save(name, obj):
    path = D / name
    with path.open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, sort_keys=True)


def save_csv(name, rows, fields):
    with (D / name).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return file_sha256(path)


def rejection(fn):
    try:
        fn()
    except ValueError as exc:
        return str(exc)
    raise AssertionError("expected rejection")


def run_process(args, log):
    start = time.perf_counter()
    cp = subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    with log.open("x", encoding="utf-8") as handle:
        handle.write(cp.stdout + cp.stderr)
    if cp.returncode:
        raise RuntimeError(
            f"subprocess failed with exit code {cp.returncode}\n"
            + cp.stdout + cp.stderr
        )
    return time.perf_counter() - start


def capacity_row(image, q, seconds):
    stats = q["stats"]
    gross = int(stats["gross_slots"])
    foregone = int(stats["foregone_gross_slots"])
    backup = int(stats["backup_bits"])
    net = int(q["net"])
    # The wire metadata occupies 8H bootstrap bytes. Those bootstrap pixels
    # forfeit F ordinary slots; B ordinary slots preserve their original bytes.
    # The in-image metadata physically occupies 8H bootstrap bytes. Its
    # opportunity cost against ordinary slots is F; the disjoint backup prefix
    # costs B. Report these separately to avoid double counting.
    metadata_overhead = foregone
    total_overhead = metadata_overhead + backup
    if gross - total_overhead != net:
        raise AssertionError(
            f"capacity identity failed for {image['name']}: "
            f"{gross} - {foregone} - {backup} != {net}"
        )
    return dict(
        image=image["name"],
        source=image["source"],
        source_sha256=image["source_sha256"],
        pixels_sha256=image["pixels_sha256"],
        height=image["shape"][0],
        width=image["shape"][1],
        pixels=int(stats["pixels"]),
        candidate_count=int(stats["candidates"]),
        gross_capacity_bits=gross,
        gross_bpp=gross / int(stats["pixels"]),
        bootstrap_foregone_slots_bits=foregone,
        metadata_wire_storage_bits=int(stats["metadata_total_bits"]),
        bootstrap_backup_bits=backup,
        metadata_overhead_bits=metadata_overhead,
        total_overhead_bits=total_overhead,
        net_capacity_bits=net,
        signed_net_bpp=net / int(stats["pixels"]),
        usable_net_bpp=max(0, net) / int(stats["pixels"]),
        accepted=bool(stats["accepted"]),
        rejection_reason="" if stats["accepted"] else "nonpositive net capacity",
        prepare_seconds=seconds,
        codec=stats["codec"],
        compressed_directory_bytes=int(stats["compressed_label_bytes"]),
        bootstrap_candidates=int(stats["bootstrap_pixels"]),
        fixed_header_bits=int(stats["fixed_header_bits"]),
        authentication_bits=int(stats["authentication_bits"]),
    )


def main():
    global D
    args = parse_args()

    data_dirs = [Path(p).expanduser().resolve() for p in args.data_dir] if args.data_dir else default_data_dirs()
    if not data_dirs:
        raise FileNotFoundError(
            "no default data directories found. Add images to data/kodak_gray and/or "
            "data/usc_sipi_gray, or pass --data-dir."
        )
    if args.short_payload_bits < 1:
        raise ValueError("--short-payload-bits must be at least 1")
    if args.threads < 1:
        raise ValueError("--threads must be at least 1")

    corpus, skipped, duplicates, inventory, missing_baseline = load_corpus(
        data_dirs, args.allow_missing_baseline
    )

    if args.output_dir:
        D = Path(args.output_dir).expanduser().resolve()
    else:
        D = BASE / f"evidence_expanded_{time.strftime('%Y%m%d_%H%M%S')}"
    D.mkdir(parents=True, exist_ok=False)

    total_natural = len(corpus)
    save("corpus.json", inventory)
    save("skipped_inputs.json", skipped)
    save("pixel_duplicates.json", duplicates)
    save("input_manifest.json", dict(
        data_directories=[str(p) for p in data_dirs],
        distinct_valid_grayscale_images=len(corpus),
        skipped_nonconforming_files=len(skipped),
        duplicate_pixel_files=len(duplicates),
        missing_original_baseline_stems=missing_baseline,
        baseline_requirement="original six names required unless --allow-missing-baseline",
        image_modes="native 8-bit grayscale mode L only; no RGB conversion, resize, crop or recompression",
    ))

    # Keep the historical exact mapping and all-pairs recovery checks as hard gates.
    import torch

    torch.set_num_threads(args.threads)
    old = pr.shared()
    assert all(wire.allocation(e) == old._compute_bpp_and_range(e) for e in range(256))
    failures = 0
    pairs = words = 0
    for prediction in range(256):
        for original_value in range(256):
            n, lo, hi = wire.allocation(abs(original_value - prediction))
            pairs += 1
            words += 1 << n
            if not n:
                continue
            modulus = 1 << (8 - n)
            candidates = [
                value for value in range(original_value % modulus, 256, modulus)
                if lo <= abs(value - prediction) <= hi
            ]
            if candidates != [original_value]:
                failures += 1
    assert failures == 0
    save(
        "algebra.json",
        dict(
            pairs=pairs,
            all_payload_words_covered=words,
            failures=failures,
            codebook=wire.BOOK.tolist(),
            proof="Candidate set depends only on retained residue; all 2^n MSB words leave it unchanged.",
            production_mapping_identical=True,
        ),
    )

    master = bytes(range(32))  # Public reproducible test key; never a deployed secret.
    nonce_base = secrets.randbits(96) << 32
    payload_rng = np.random.default_rng(args.seed + 1)
    save(
        "protocol_identity.json",
        dict(
            protocol="EDR2",
            protocol_sha256=sha(BASE / "PROTOCOL_EDR2.md"),
            checkpoint_sha256=sha(ROOT / "models" / "v4_patch3.pth"),
            source_sha256={p.name: sha(p) for p in [BASE / "predictor.py", BASE / "protocol.py", BASE / "wire.py", BASE / "run_gate.py"]},
            test_master_hex=master.hex(),
            test_nonce_base_hex=f"{nonce_base:032x}",
            training=False,
            model_changed=False,
            model_training_performed=False,
            protocol_version="EDR2",
            protocol_changes_from_EDR1=["step-2 safe-zone grid", "encrypted staged header", "EDR2 key hierarchy"],
            receiver_semantic_inputs=["marked encrypted image", "master key", "nonce"],
            data_hider_semantic_inputs=["encrypted reserved image", "payload", "one derived data-hiding key"],
            input_directories=[str(p) for p in data_dirs],
            seed=args.seed,
        ),
    )

    model = old.model()
    initial_state = {key: value.clone() for key, value in model.state_dict().items()}

    # Natural-image evaluation only. Generated test fixtures are confined to
    # unit/CI tests and never enter the paper-facing dataset or capacity tables.
    capacities, results, rejected = [], [], []
    sequence = 0

    for image in corpus:
        original = read_native_gray(Path(image["source"]))
        if pixel_sha256(original) != image["pixels_sha256"]:
            raise AssertionError(f"input pixels changed after inventory: {image['name']}")
        start = time.perf_counter()
        try:
            q = pr.prepare(original)
        except ValueError as exc:
            elapsed = time.perf_counter() - start
            row = dict(
                image=image["name"], source=image["source"],
                source_sha256=image["source_sha256"], pixels_sha256=image["pixels_sha256"],
                height=image["shape"][0], width=image["shape"][1],
                pixels=int(original.size), accepted=False,
                rejection_reason=f"prepare rejected: {exc}", prepare_seconds=elapsed,
            )
            capacities.append(row)
            rejected.append(row)
            print("REJECT_PREPARE", row, flush=True)
            continue

        elapsed = time.perf_counter() - start
        row = capacity_row(image, q, elapsed)
        capacities.append(row)
        print("CAPACITY", row, flush=True)
        if not row["accepted"]:
            reason = rejection(lambda: pr.reserve(original, master, nonce_base + 999999, prepared=q))
            row["rejection_reason"] = reason
            rejected.append(row)
            continue

        y, x = q["ys"], q["xs"]
        changed = original.copy()
        changed[y, x] = payload_rng.integers(0, 256, len(y), dtype=np.uint8)
        assert np.array_equal(old.predict(changed, y, x), q["predictions"])

        short_len = min(args.short_payload_bits, q["net"])
        payload_cases = [
            ("empty", 0),
            ("short", short_len),
            ("partial", q["net"] // 2),
            ("full", q["net"]),
        ]

        for case, payload_length in payload_cases:
            sequence += 1
            nonce = nonce_base + sequence
            if nonce >= 2**128:
                raise OverflowError("test nonce sequence exceeded uint128")
            payload = payload_rng.integers(0, 2, payload_length, dtype=np.uint8)
            stem = image["safe_name"] + "_" + case
            reserved_file = D / (stem + "_reserved.png")
            input_payload = D / (stem + "_input.npy")
            cipher_file = D / (stem + "_cipher.png")
            recovered_file = D / (stem + "_recovered.npy")
            extracted_file = D / (stem + "_extracted.npy")
            embed_audit = D / (stem + "_embed.json")
            receive_audit = D / (stem + "_receive.json")

            start = time.perf_counter()
            reserved, capability = pr.reserve(original, master, nonce, prepared=q)
            reserve_seconds = time.perf_counter() - start
            Image.fromarray(reserved).save(reserved_file)
            np.save(input_payload, payload, allow_pickle=False)

            embed_wall = run_process(
                [
                    BASE / "wire.py", reserved_file, input_payload,
                    capability["hider"].hex(), cipher_file, embed_audit,
                ],
                D / (stem + "_embed.log"),
            )

            final = np.array(Image.open(cipher_file))
            hider_subkeys = wire.hider_keys(capability["hider"])
            fq = wire.inspect(final, hider_subkeys)
            allow = np.zeros_like(final)
            ordinary = tuple(v[fq["backup"]:] for v in fq["positions"])
            wire.writebits(allow, ordinary, np.ones(fq["net"], np.uint8))
            allow[y[:20], x[:20]] = 255
            allow[y[20 + len(q["meta"]):q["h"]], x[20 + len(q["meta"]):q["h"]]] = 255
            assert not np.any((final ^ reserved) & (255 ^ allow))
            assert np.array_equal(
                wire.readbits(final, tuple(v[:fq["backup"]] for v in fq["positions"])),
                wire.readbits(reserved, tuple(v[:fq["backup"]] for v in fq["positions"])),
            )

            receive_wall = run_process(
                [
                    BASE / "protocol.py", "receive", cipher_file, master.hex(), nonce,
                    recovered_file, extracted_file, receive_audit,
                ],
                D / (stem + "_receive.log"),
            )
            image_ok = bool(np.array_equal(np.load(recovered_file, allow_pickle=False), original))
            payload_ok = bool(np.array_equal(np.load(extracted_file, allow_pickle=False), payload))
            assert image_ok and payload_ok, (
                f"exact round trip failed: {image['name']} / {case} / {payload_length} bits"
            )
            rx = json.loads(receive_audit.read_text(encoding="utf-8"))
            emb = json.loads(embed_audit.read_text(encoding="utf-8"))
            assert not rx["source_access"] and not rx["source_reads"]
            assert not emb["model_imported"] and not emb["image_key_received"]
            assert emb["hider_key_received"]
            evidence_reads = [p for p in rx["read_paths"] if str(D) + os.sep in p]
            assert evidence_reads == [str(cipher_file)], evidence_reads

            result = dict(
                image=image["name"], source=image["source"], case=case,
                payload_bits=payload_length, capacity_bits=q["net"],
                nonce=f"{nonce:032x}", image_exact=image_ok, payload_exact=payload_ok,
                reserve_encrypt_seconds=reserve_seconds, embed_seconds=emb["seconds"],
                embed_process_seconds=embed_wall, receiver_seconds=rx["receiver_seconds"],
                receiver_process_seconds=receive_wall,
                receiver_evidence_reads=evidence_reads,
                within_pixel_backup_boundary=bool(
                    fq["backup"] and fq["positions"][0][fq["backup"] - 1]
                    == fq["positions"][0][fq["backup"]]
                ),
                encrypted_payload_changed_bits=int(wire.readbits(final ^ reserved, ordinary).sum()),
                short_case_is_full_capacity=bool(case == "short" and payload_length == q["net"]),
            )
            results.append(result)
            print("PASS", result, flush=True)
            save(stem + "_result.json", result)

            if not args.keep_artifacts:
                for artifact in (reserved_file, input_payload, cipher_file, recovered_file, extracted_file):
                    artifact.unlink(missing_ok=True)

            if case == "short":
                corrupt = final.copy()
                corrupt[0, 0] ^= 1
                badcap = wire.hider_keys(capability["hider"])
                badcap["auth"] = bytes(32)
                rejected_checks = dict(
                    oversized=rejection(
                        lambda: wire.embed(reserved, np.zeros(q["net"] + 1, np.uint8), hider_subkeys)
                    ),
                    nonbinary=rejection(
                        lambda: wire.embed(reserved, np.array([2], dtype=np.uint8), hider_subkeys)
                    ),
                    corrupted_ciphertext=rejection(lambda: pr.receive(corrupt, master, nonce)),
                    wrong_nonce=rejection(lambda: pr.receive(final, master, nonce + 10**9)),
                    wrong_key=rejection(lambda: pr.receive(final, bytes(32), nonce)),
                    wrong_embed_key=rejection(lambda: wire.inspect(final, badcap)),
                )
                rejected.append(dict(image=image["name"], negative_checks=rejected_checks))

    save("capacities.json", capacities)
    save("roundtrips.json", results)
    save("negative_checks_and_rejections.json", rejected)

    capacity_fields = [
        "image", "source", "source_sha256", "pixels_sha256", "height", "width", "pixels",
        "candidate_count", "gross_capacity_bits", "gross_bpp",
        "bootstrap_foregone_slots_bits", "metadata_wire_storage_bits",
        "bootstrap_backup_bits", "metadata_overhead_bits", "total_overhead_bits",
        "net_capacity_bits", "signed_net_bpp", "usable_net_bpp",
        "accepted", "rejection_reason", "prepare_seconds", "codec",
        "compressed_directory_bytes", "bootstrap_candidates",
        "fixed_header_bits", "authentication_bits",
    ]
    save_csv("capacity_summary.csv", capacities, capacity_fields)
    roundtrip_fields = [
        "image", "source", "case", "payload_bits", "capacity_bits", "nonce",
        "image_exact", "payload_exact", "reserve_encrypt_seconds", "embed_seconds",
        "embed_process_seconds", "receiver_seconds", "receiver_process_seconds",
        "within_pixel_backup_boundary", "encrypted_payload_changed_bits",
        "short_case_is_full_capacity",
    ]
    save_csv("roundtrip_summary.csv", results, roundtrip_fields)

    state_unchanged = all(
        torch.equal(initial_state[key], value)
        for key, value in model.state_dict().items()
    )
    assert state_unchanged
    natural_accepted = sum(bool(row.get("accepted")) for row in capacities)
    natural_rejected = sum(not bool(row.get("accepted")) for row in capacities)
    roundtrip_passes = sum(bool(row["image_exact"] and row["payload_exact"]) for row in results)
    save(
        "integrity.json",
        dict(
            state_unchanged=state_unchanged,
            training=False,
            checkpoint_sha256=sha(ROOT / "models" / "v4_patch3.pth"),
            model_changed=False,
            model_training_performed=False,
            protocol_changes_from_EDR1=["step-2 safe-zone grid", "encrypted staged header", "EDR2 key hierarchy"],
        ),
    )
    save(
        "run_summary.json",
        dict(
            distinct_natural_inputs=total_natural,
            synthetic_controls_included=False,
            total_capacity_rows=len(capacities),
            accepted_images=natural_accepted,
            rejected_images=natural_rejected,
            roundtrip_cases=len(results),
            roundtrip_passes=roundtrip_passes,
            roundtrip_failures=len(results) - roundtrip_passes,
            negative_check_records=len(rejected),
            missing_original_baseline_stems=missing_baseline,
            capacity_identity="net = gross - metadata_foregone_slots - bootstrap_backup",
            metadata_wire_storage_bits_reported_separately=True,
            metadata_foregone_slots_are_the_metadata_opportunity_cost=True,
            all_exact_recovery=roundtrip_passes == len(results),
        ),
    )

    print(
        f"COMPLETE: {total_natural} natural grayscale inputs; "
        f"{natural_accepted} accepted, {natural_rejected} rejected; "
        f"{roundtrip_passes}/{len(results)} exact round trips",
        flush=True,
    )
    assert state_unchanged
    assert roundtrip_passes == len(results)
    assert len(results) == sum(4 for row in capacities if row.get("accepted"))
    print("ALL CHECKS PASSED", flush=True)


if __name__ == "__main__":
    main()
