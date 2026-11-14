#!/usr/bin/env python3
"""Reproducible CC-EDR2-RGB evaluation, blend ablations and exact round trips."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import shutil
import sys
import time
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

import predictor
import rgb_protocol


SUPPORTED = {".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg"}
BLENDS = ((0, 4), (1, 4), (2, 4), (3, 4))
FIXED_ASSIGNMENT = (0, 1, 2)
PAYLOAD_CASES = (
    ("empty", 0), ("one_bit", 1), ("seven_bits", 7), ("byte_aligned", 8),
    ("nine_bits", 9), ("short_37", 37), ("nonbyte_137", 137),
    ("near_capacity", -1), ("full_capacity", -2),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pixel_sha256(array: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    h.update(b"|uint8|RGB|")
    h.update(array.tobytes(order="C"))
    return h.hexdigest()


def load_native_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError(f"multi-frame input is unsupported: {image.n_frames} frames")
        if image.mode != "RGB":
            raise ValueError(f"expected native 8-bit RGB mode, received {image.mode}")
        array = np.asarray(image)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"expected HxWx3 uint8 RGB, got {array.dtype}/{array.shape}")
    if array.shape[0] % 2 or array.shape[1] % 2:
        raise ValueError(f"CC-EDR2-RGB currently requires even dimensions, got {array.shape[:2]}")
    return np.ascontiguousarray(array)


def stable_ids(seed: int, pixel_hash: str, packet_context: str = "default",
               nonce_namespace: str = "unit-test"):
    """Return a stable benchmark key and a namespace-/packet-specific nonce."""
    base = hashlib.sha256(f"CC-EDR2-RGB-BENCH|{seed}|{pixel_hash}".encode("ascii")).digest()
    master = hashlib.sha256(b"EDR2RGB-MASTER|" + base).digest()
    nonce_input = (
        b"EDR2RGB-NONCE|" + base + b"|" + packet_context.encode("utf-8")
        + b"|" + nonce_namespace.encode("utf-8")
    )
    nonce = int.from_bytes(hashlib.sha256(nonce_input).digest()[:16], "big")
    return master, nonce


def payload_for(length: int, seed: int, pixel_hash: str, case: str) -> np.ndarray:
    if length < 0:
        raise ValueError("payload length cannot be negative")
    stream = hashlib.sha256(f"{seed}|{pixel_hash}|{case}".encode("ascii")).digest()
    child_seed = int.from_bytes(stream[:16], "big")
    return np.random.default_rng(child_seed).integers(0, 2, length, dtype=np.uint8)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None):
    fields = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def completion_status(capacity_rows: list[dict], inventory: list[dict],
                      roundtrip_rows: list[dict],
                      input_limit: int = 0) -> tuple[str, list[str]]:
    """Require complete exact-recovery evidence for every positive-capacity blend."""
    failures = []
    if input_limit:
        failures.append("limited-input smoke runs are not eligible for paper analysis")
    if not inventory:
        failures.append("no native even-sized uint8 RGB images were accepted")
    if len(capacity_rows) != len(inventory):
        failures.append(
            f"capacity ledger has {len(capacity_rows)} rows for {len(inventory)} accepted inputs"
        )

    if any(row.get("status") in {"error", "blend_roundtrip_failed"} for row in capacity_rows):
        failures.append("one or more RGB inputs have processing or exact-recovery failures")

    by_image_blend = {}
    for row in roundtrip_rows:
        key = (row.get("image"), int(row.get("blend_num", -1)))
        by_image_blend.setdefault(key, []).append(row)

    for capacity in capacity_rows:
        image = capacity.get("image")
        for blend_num, _ in BLENDS:
            net = int(capacity.get(f"blend_{blend_num}_net_capacity_bits", 0) or 0)
            blend_status = capacity.get(f"blend_{blend_num}_status")
            cases = by_image_blend.get((image, blend_num), [])
            if net <= 0:
                if blend_status != "rejected_nonpositive_net_capacity" or cases:
                    failures.append(
                        f"{image}: blend {blend_num}/4 has invalid non-positive-capacity handling"
                    )
                continue
            if blend_status != "roundtrip_passed" or not cases:
                failures.append(
                    f"{image}: positive-capacity blend {blend_num}/4 has no exact-recovery evidence"
                )
                continue
            if any(row.get("passed") is not True for row in cases):
                failures.append(
                    f"{image}: blend {blend_num}/4 has one or more exact-recovery failures"
                )
            expected_lengths = {
                min(requested, net) for requested in (0, 1, 7, 8, 9, 37, 137)
            }
            expected_lengths.update({max(0, net - 1), net})
            observed_lengths = {int(row.get("payload_bits", -1)) for row in cases}
            if observed_lengths != expected_lengths:
                failures.append(
                    f"{image}: blend {blend_num}/4 payload-boundary evidence mismatch"
                )
            if any(int(row.get("net_capacity_bits", -1)) != net for row in cases):
                failures.append(
                    f"{image}: blend {blend_num}/4 round-trip capacity mismatch"
                )

    return ("completed_with_failures" if failures else "completed"), failures


def safe_id(relative: str) -> str:
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--keep-artifacts", action="store_true",
                        help="Retain original, reserved, encrypted-marked and recovered images per image/case.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Optional deterministic maximum number of files; zero means all.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be zero (all inputs) or a positive integer")

    root = Path(args.data_dir).resolve()
    output = Path(args.output_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    artifact_root = output / "images"
    if args.keep_artifacts:
        artifact_root.mkdir()

    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    if args.limit:
        files = files[:args.limit]

    capacity_rows = []
    roundtrip_rows = []
    assignment_rows = []
    inventory = []
    skipped = []
    seen_pixel_hashes = set()
    model_identity = predictor.model_identity()
    # A new namespace per corpus run prevents deterministic benchmark keys
    # from reusing a CTR nonce when the same image/seed is evaluated again.
    nonce_namespace = secrets.token_hex(16)
    started = time.perf_counter()

    for source in files:
        relative = source.relative_to(root).as_posix()
        try:
            image = load_native_rgb(source)
        except Exception as exc:
            skipped.append({"path": relative, "reason": str(exc)})
            continue

        source_hash = sha256_file(source)
        pixels_hash = pixel_sha256(image)
        if pixels_hash in seen_pixel_hashes:
            skipped.append({"path": relative, "reason": "duplicate decoded RGB pixels"})
            continue
        seen_pixel_hashes.add(pixels_hash)
        volume = PurePosixPath(relative).parts[0] if len(PurePosixPath(relative).parts) > 1 else "unspecified"
        record = {
            "image": relative,
            "volume": volume,
            "corpus_group": "aerial_colour" if volume == "aerials" else ("miscellaneous_colour" if volume == "misc" else volume),
            "source_sha256": source_hash,
            "pixels_sha256": pixels_hash,
            "height": int(image.shape[0]),
            "width": int(image.shape[1]),
            "mode": "RGB",
            "dtype": "uint8",
            "file_bytes": int(source.stat().st_size),
        }
        inventory.append(record)
        master, _ = stable_ids(args.seed, pixels_hash, nonce_namespace=nonce_namespace)
        base_row = dict(record)
        base_row["status"] = "prepared"
        image_started = time.perf_counter()

        try:
            # Compute the 12 channel/phase CNN outputs only once per source image.
            spatial_cache, coordinate_cache = rgb_protocol.build_spatial_cache(image)
            blend_results = {}
            for blend_num, blend_den in BLENDS:
                blend_started = time.perf_counter()
                q = rgb_protocol.prepare(
                    image,
                    blend_num=blend_num,
                    blend_den=blend_den,
                    spatial_cache=spatial_cache,
                    coordinate_cache=coordinate_cache,
                )
                blend_results[blend_num] = q
                assignment_rows.append({
                    "image": relative,
                    "pixels_sha256": pixels_hash,
                    "blend_num": blend_num,
                    "blend_den": blend_den,
                    "selected_phases_rgb": json.dumps(list(q["phases"])),
                    "calibration_phase": q["calibration_phase"],
                    "assignment_search": q["assignment_search"],
                    "net_capacity_bits": int(q["net"]),
                    "net_bpp_per_rgb_pixel": float(q["net"] / (image.shape[0] * image.shape[1])),
                    "directory_bytes": len(q["metadata"]),
                    "phase_assignment_scores_json": json.dumps(q["assignment_scores"], separators=(",", ":")),
                    "prediction_metrics_by_channel_json": json.dumps(q["prediction_metrics"], separators=(",", ":")),
                    "prepare_seconds": time.perf_counter() - blend_started,
                })

            fixed = rgb_protocol.prepare(
                image,
                blend_num=1,
                blend_den=4,
                assignment_override=FIXED_ASSIGNMENT,
                spatial_cache=spatial_cache,
                coordinate_cache=coordinate_cache,
            )
            best_blend = max(blend_results, key=lambda b: blend_results[b]["net"])
            if args.keep_artifacts:
                image_dir = artifact_root / safe_id(relative)
                image_dir.mkdir(parents=True, exist_ok=False)
                shutil.copy2(source, image_dir / ("original" + source.suffix.lower()))

            for blend_value, result in blend_results.items():
                blend_net = int(result["net"])
                prefix = f"blend_{blend_value}"
                base_row[f"{prefix}_net_capacity_bits"] = blend_net
                base_row[f"{prefix}_net_bpp"] = float(
                    blend_net / (image.shape[0] * image.shape[1])
                )
                base_row[f"{prefix}_phases"] = json.dumps(list(result["phases"]))
                base_row[f"{prefix}_status"] = (
                    "rejected_nonpositive_net_capacity" if blend_net <= 0 else "pending_roundtrip"
                )
                for channel, metric in enumerate(result["prediction_metrics"]):
                    for metric_name, metric_value in metric.items():
                        base_row[
                            f"{prefix}_channel_{channel}_{metric_name}"
                        ] = float(metric_value)

                if blend_net <= 0:
                    continue

                used_nonces = set()
                tested_lengths = set()
                blend_rows = []
                for case, requested in PAYLOAD_CASES:
                    if requested >= 0:
                        length = requested
                    elif requested == -1:
                        length = max(0, blend_net - 1)
                    else:
                        length = blend_net
                    length = min(int(length), blend_net)
                    if length in tested_lengths:
                        continue
                    tested_lengths.add(length)

                    packet_context = f"blend_{blend_value}_{case}"
                    packet_master, packet_nonce = stable_ids(
                        args.seed, pixels_hash, packet_context=packet_context,
                        nonce_namespace=nonce_namespace
                    )
                    if packet_master != master or packet_nonce in used_nonces:
                        raise RuntimeError("benchmark packet key/nonce separation failed")
                    used_nonces.add(packet_nonce)
                    reserved, capability = rgb_protocol.reserve(
                        image, packet_master, packet_nonce, prepared=result
                    )
                    if args.keep_artifacts and len(used_nonces) == 1:
                        Image.fromarray(reserved, mode="RGB").save(
                            image_dir / f"{prefix}_reserved.png"
                        )

                    payload = payload_for(length, args.seed, pixels_hash, packet_context)
                    marked_started = time.perf_counter()
                    marked = rgb_protocol.embed(reserved, payload, capability["hider"])
                    embed_seconds = time.perf_counter() - marked_started
                    receive_started = time.perf_counter()
                    recovered, extracted = rgb_protocol.receive(
                        marked, packet_master, packet_nonce
                    )
                    receiver_seconds = time.perf_counter() - receive_started
                    image_exact = bool(np.array_equal(recovered, image))
                    payload_exact = bool(np.array_equal(extracted, payload))
                    roundtrip = {
                        "image": relative,
                        "pixels_sha256": pixels_hash,
                        "blend_num": int(blend_value),
                        "blend_den": 4,
                        "case": case,
                        "payload_bits": int(length),
                        "net_capacity_bits": blend_net,
                        "image_exact": image_exact,
                        "payload_exact": payload_exact,
                        "embed_seconds": embed_seconds,
                        "receiver_seconds": receiver_seconds,
                        "passed": image_exact and payload_exact,
                    }
                    roundtrip_rows.append(roundtrip)
                    blend_rows.append(roundtrip)
                    if args.keep_artifacts:
                        Image.fromarray(marked, mode="RGB").save(
                            image_dir / f"{prefix}_marked_{case}.png"
                        )
                        Image.fromarray(recovered, mode="RGB").save(
                            image_dir / f"{prefix}_recovered_{case}.png"
                        )
                        np.save(
                            image_dir / f"{prefix}_payload_{case}.npy",
                            payload, allow_pickle=False
                        )
                        np.save(
                            image_dir / f"{prefix}_extracted_{case}.npy",
                            extracted, allow_pickle=False
                        )

                blend_passed = (
                    len(blend_rows) > 0
                    and all(row["passed"] is True for row in blend_rows)
                    and any(row["payload_bits"] == blend_net for row in blend_rows)
                    and any(row["payload_bits"] == 0 for row in blend_rows)
                )
                base_row[f"{prefix}_status"] = (
                    "roundtrip_passed" if blend_passed else "roundtrip_failed"
                )

            base_row.update({
                "status": (
                    "roundtrip_passed"
                    if all(base_row.get(f"blend_{blend}_status") in {
                        "roundtrip_passed", "rejected_nonpositive_net_capacity"
                    } for blend, _ in BLENDS)
                    else "blend_roundtrip_failed"
                ),
                "candidate_count_per_channel": int(
                    blend_results[1]["stats"]["candidate_count_per_channel"]
                ),
                "best_blend_num_by_capacity": int(best_blend),
                "best_blend_net_capacity_bits": int(blend_results[best_blend]["net"]),
                "fixed_assignment_012_net_capacity_bits": int(fixed["net"]),
                "adaptive_assignment_gain_bits": int(
                    blend_results[1]["net"] - fixed["net"]
                ),
                "image_prepare_seconds": time.perf_counter() - image_started,
            })
            base_row["all_blends_exact"] = base_row["status"] == "roundtrip_passed"
            capacity_rows.append(base_row)
        except Exception as exc:
            base_row["status"] = "error"
            base_row["error"] = f"{type(exc).__name__}: {exc}"
            capacity_rows.append(base_row)

    elapsed = time.perf_counter() - started
    write_csv(output / "rgb_capacity_summary.csv", capacity_rows)
    write_csv(
        output / "rgb_roundtrip_summary.csv",
        roundtrip_rows,
        fieldnames=[
            "image", "pixels_sha256", "case", "payload_bits", "net_capacity_bits",
            "image_exact", "payload_exact", "embed_seconds", "receiver_seconds", "passed",
        ],
    )
    write_csv(
        output / "rgb_phase_assignment_scores.csv",
        assignment_rows,
        fieldnames=[
            "image", "pixels_sha256", "blend_num", "blend_den", "selected_phases_rgb",
            "calibration_phase", "assignment_search", "net_capacity_bits",
            "net_bpp_per_rgb_pixel", "directory_bytes", "phase_assignment_scores_json",
            "prediction_metrics_by_channel_json", "prepare_seconds",
        ],
    )
    write_csv(output / "rgb_input_inventory.csv", inventory)
    write_csv(output / "rgb_skipped_inputs.csv", skipped)

    status, failure_reasons = completion_status(
        capacity_rows, inventory, roundtrip_rows, input_limit=args.limit
    )
    per_blend_summary = {}
    for blend_num, blend_den in BLENDS:
        net_values = [
            int(row.get(f"blend_{blend_num}_net_capacity_bits", 0) or 0)
            for row in capacity_rows
        ]
        per_blend_summary[f"{blend_num}/{blend_den}"] = {
            "positive_net_images": sum(value > 0 for value in net_values),
            "nonpositive_net_images": sum(value <= 0 for value in net_values),
            "roundtrip_passed_images": sum(
                row.get(f"blend_{blend_num}_status") == "roundtrip_passed"
                for row in capacity_rows
            ),
            "roundtrip_failed_images": sum(
                row.get(f"blend_{blend_num}_status") == "roundtrip_failed"
                for row in capacity_rows
            ),
            "roundtrip_cases": sum(
                int(row.get("blend_num", -1)) == blend_num for row in roundtrip_rows
            ),
        }
    summary = {
        "protocol": "CC-EDR2-RGB",
        "status": status,
        "analysis_ready": status == "completed",
        "failure_reasons": failure_reasons,
        "input_files_seen": len(files),
        "distinct_native_rgb_inputs": len(inventory),
        "skipped_files": len(skipped),
        "capacity_rows": len(capacity_rows),
        "blend_summaries": per_blend_summary,
        "roundtrip_cases": len(roundtrip_rows),
        "roundtrip_passed": sum(row.get("passed") is True for row in roundtrip_rows),
        "roundtrip_failed": sum(row.get("passed") is False for row in roundtrip_rows),
        "blend_settings": [{"num": n, "den": d} for n, d in BLENDS],
        "fixed_assignment_ablation": list(FIXED_ASSIGNMENT),
        "checkpoint_sha256": model_identity["checkpoint_sha256"],
        "checkpoint": model_identity,
        "training_performed": False,
        "benchmark_key_policy": (
            "Public deterministic test keys with a random namespace per corpus run; "
            "each blend/payload packet uses a fresh nonce and fresh reservation. "
            "Not a deployment key-management recommendation."
        ),
        "seed": args.seed,
        "input_limit": args.limit,
        "nonce_namespace": nonce_namespace,
        "benchmark_keys_are_public_test_material": True,
        "elapsed_seconds": elapsed,
    }
    (output / "rgb_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "rgb_input_manifest.json").write_text(
        json.dumps({
            "images": inventory,
            "skipped": skipped,
            "nonce_namespace": nonce_namespace,
            "key_policy": "Public benchmark-only keys; a random namespace is used for each run and a fresh nonce/reservation for each payload packet.",
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
