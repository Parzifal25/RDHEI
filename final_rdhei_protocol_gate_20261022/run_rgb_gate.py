#!/usr/bin/env python3
"""Reproducible CC-EDR2-RGB evaluation, blend ablations and exact round trips."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
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


def stable_ids(seed: int, pixel_hash: str):
    digest = hashlib.sha256(f"CC-EDR2-RGB-BENCH|{seed}|{pixel_hash}".encode("ascii")).digest()
    master = hashlib.sha256(b"EDR2RGB-MASTER|" + digest).digest()
    nonce = int.from_bytes(hashlib.sha256(b"EDR2RGB-NONCE|" + digest).digest()[:16], "big")
    return master, nonce


def payload_for(length: int, seed: int, pixel_hash: str, case: str) -> np.ndarray:
    if length < 0:
        raise ValueError("payload length cannot be negative")
    stream = hashlib.sha256(f"{seed}|{pixel_hash}|{case}".encode("ascii")).digest()
    child_seed = int.from_bytes(stream[:16], "big")
    return np.random.default_rng(child_seed).integers(0, 2, length, dtype=np.uint8)


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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
        master, nonce = stable_ids(args.seed, pixels_hash)
        base_row = dict(record)
        base_row["status"] = "prepared"
        image_started = time.perf_counter()

        try:
            # Build the frozen CNN outputs once, then independently evaluate all
            # four blend settings. A metadata overflow in one blend must never
            # short-circuit the other blend or phase-assignment measurements.
            spatial_cache, coordinate_cache = rgb_protocol.build_spatial_cache(image)
            blend_results = {}
            blend_diagnostics = {}
            blend_errors = {}

            def mean_metrics_over_assignments(scores):
                means = []
                for channel in range(3):
                    row = {}
                    for metric_name in ("spatial_mae", "cross_channel_mae", "fused_mae"):
                        values = [
                            float(score["prediction_metrics"][channel][metric_name])
                            for score in scores
                            if score.get("prediction_metrics")
                            and len(score["prediction_metrics"]) == 3
                        ]
                        row[metric_name] = float(np.mean(values)) if values else float("nan")
                    means.append(row)
                return means

            for blend_num, blend_den in BLENDS:
                blend_started = time.perf_counter()
                try:
                    q = rgb_protocol.prepare(
                        image,
                        blend_num=blend_num,
                        blend_den=blend_den,
                        spatial_cache=spatial_cache,
                        coordinate_cache=coordinate_cache,
                    )
                    blend_results[blend_num] = q
                    scores = q["assignment_scores"]
                    selected_phases = json.dumps(list(q["phases"]))
                    calibration_phase = int(q["calibration_phase"])
                    net_capacity = int(q["net"])
                    net_bpp = float(q["net"] / (image.shape[0] * image.shape[1]))
                    directory_bytes = int(len(q["metadata"]))
                    selected_metrics = q["prediction_metrics"]
                except rgb_protocol.RGBCapacityError as exc:
                    scores = exc.diagnostics
                    blend_errors[blend_num] = str(exc)
                    blend_diagnostics[blend_num] = scores
                    selected_phases = ""
                    calibration_phase = None
                    net_capacity = None
                    net_bpp = None
                    directory_bytes = min(
                        (int(score["directory_bytes"]) for score in scores),
                        default=None,
                    )
                    selected_metrics = mean_metrics_over_assignments(scores)

                feasible_assignments = sum(
                    bool(score.get("directory_fits")) for score in scores
                )
                assignment_rows.append({
                    "image": relative,
                    "pixels_sha256": pixels_hash,
                    "blend_num": blend_num,
                    "blend_den": blend_den,
                    "selected_phases_rgb": selected_phases,
                    "calibration_phase": calibration_phase,
                    "assignment_search": "adaptive_24",
                    "net_capacity_bits": net_capacity,
                    "net_bpp_per_rgb_pixel": net_bpp,
                    "directory_bytes": directory_bytes,
                    "phase_assignment_count": len(scores),
                    "directory_fit_assignment_count": feasible_assignments,
                    "phase_assignment_scores_json": json.dumps(scores, separators=(",", ":")),
                    "prediction_metrics_by_channel_json": json.dumps(selected_metrics, separators=(",", ":")),
                    "blend_error": blend_errors.get(blend_num, ""),
                    "prepare_seconds": time.perf_counter() - blend_started,
                })

                base_row[f"blend_{blend_num}_net_capacity_bits"] = net_capacity
                base_row[f"blend_{blend_num}_net_bpp"] = net_bpp
                base_row[f"blend_{blend_num}_phases"] = selected_phases
                base_row[f"blend_{blend_num}_directory_bytes"] = directory_bytes
                base_row[f"blend_{blend_num}_directory_fit_assignments"] = feasible_assignments
                base_row[f"blend_{blend_num}_error"] = blend_errors.get(blend_num, "")
                base_row[f"blend_{blend_num}_prediction_metric_scope"] = (
                    "selected_net_best_assignment" if blend_num in blend_results
                    else "mean_over_24_assignments_no_directory_fit"
                )
                for channel, metric in enumerate(selected_metrics):
                    for metric_name, metric_value in metric.items():
                        base_row[f"blend_{blend_num}_channel_{channel}_{metric_name}"] = float(metric_value)

            if blend_results:
                best_blend = max(blend_results, key=lambda b: blend_results[b]["net"])
                best_result = blend_results[best_blend]
                base_row["best_blend_num_by_capacity"] = int(best_blend)
                base_row["best_blend_net_capacity_bits"] = int(best_result["net"])
            else:
                best_blend = None
                base_row["best_blend_num_by_capacity"] = None
                base_row["best_blend_net_capacity_bits"] = None

            selected = blend_results.get(1)
            if selected is None:
                base_row.update({
                    "status": "rejected_no_feasible_assignment_at_1_4_blend",
                    "error": blend_errors.get(1, "no feasible 1/4 blend assignment"),
                    "blend_feasible_count": len(blend_results),
                    "image_prepare_seconds": time.perf_counter() - image_started,
                })
                capacity_rows.append(base_row)
                continue

            fixed_assignment_error = ""
            try:
                fixed = rgb_protocol.prepare(
                    image,
                    blend_num=1,
                    blend_den=4,
                    assignment_override=FIXED_ASSIGNMENT,
                    spatial_cache=spatial_cache,
                    coordinate_cache=coordinate_cache,
                )
            except rgb_protocol.RGBCapacityError as exc:
                fixed = None
                fixed_assignment_error = str(exc)

            selected["stats"]["blend_feasible_count"] = len(blend_results)
            base_row.update({
                "status": "capacity_evaluated",
                "candidate_count_per_channel": int(selected["stats"]["candidate_count_per_channel"]),
                "gross_slots_all_channels": int(selected["stats"]["gross_slots_all_channels"]),
                "foregone_red_header_slots": int(selected["stats"]["foregone_red_header_slots"]),
                "metadata_bytes": int(selected["stats"]["directory_stored_bytes"] + rgb_protocol.rgb_wire.HEADER_BYTES + rgb_protocol.rgb_wire.TAG_BYTES),
                "bootstrap_candidates": int(selected["stats"]["bootstrap_candidates"]),
                "backup_bits": int(selected["stats"]["bootstrap_backup_bits"]),
                "stream_bits": int(selected["stats"]["ordinary_stream_bits"]),
                "signed_net_capacity_bits": int(selected["net"]),
                "signed_net_bpp_per_rgb_pixel": float(selected["net"] / (image.shape[0] * image.shape[1])),
                "selected_rgb_phases": json.dumps(list(selected["phases"])),
                "calibration_phase": int(selected["calibration_phase"]),
                "fixed_assignment_012_net_capacity_bits": int(fixed["net"]) if fixed is not None else None,
                "fixed_assignment_error": fixed_assignment_error,
                "adaptive_assignment_gain_bits": int(selected["net"] - fixed["net"]) if fixed is not None else None,
                "channel_prediction_metrics": json.dumps(selected["prediction_metrics"], separators=(",", ":")),
                "phase_assignment_scores": json.dumps(selected["assignment_scores"], separators=(",", ":")),
                "blend_feasible_count": len(blend_results),
                "image_prepare_seconds": time.perf_counter() - image_started,
            })

            if selected["net"] <= 0:
                base_row["status"] = "rejected_nonpositive_net_capacity"
                capacity_rows.append(base_row)
                continue

            reserved, capability = rgb_protocol.reserve(
                image, master, nonce, prepared=selected
            )
            if args.keep_artifacts:
                image_dir = artifact_root / safe_id(relative)
                image_dir.mkdir(parents=True, exist_ok=False)
                shutil.copy2(source, image_dir / ("original" + source.suffix.lower()))
                Image.fromarray(reserved, mode="RGB").save(image_dir / "reserved_encrypted.png")

            lengths = []
            for case, requested in PAYLOAD_CASES:
                if requested >= 0:
                    length = requested
                elif requested == -1:
                    length = max(0, int(selected["net"]) - 1)
                else:
                    length = int(selected["net"])
                length = min(int(length), int(selected["net"]))
                if length not in lengths:
                    lengths.append(length)
                    payload = payload_for(length, args.seed, pixels_hash, case)
                    marked_started = time.perf_counter()
                    marked = rgb_protocol.embed(reserved, payload, capability["hider"])
                    embed_seconds = time.perf_counter() - marked_started
                    receive_started = time.perf_counter()
                    recovered, extracted = rgb_protocol.receive(marked, master, nonce)
                    receiver_seconds = time.perf_counter() - receive_started
                    image_exact = bool(np.array_equal(recovered, image))
                    payload_exact = bool(np.array_equal(extracted, payload))
                    roundtrip_rows.append({
                        "image": relative,
                        "pixels_sha256": pixels_hash,
                        "blend_num": 1,
                        "blend_den": 4,
                        "case": case,
                        "payload_bits": int(length),
                        "net_capacity_bits": int(selected["net"]),
                        "image_exact": image_exact,
                        "payload_exact": payload_exact,
                        "passed": image_exact and payload_exact,
                        "embed_seconds": embed_seconds,
                        "receiver_seconds": receiver_seconds,
                    })
                    if args.keep_artifacts:
                        Image.fromarray(marked, mode="RGB").save(image_dir / f"marked_{case}.png")
                        Image.fromarray(recovered, mode="RGB").save(image_dir / f"recovered_{case}.png")
                        np.save(image_dir / f"payload_{case}.npy", payload, allow_pickle=False)
                        np.save(image_dir / f"extracted_{case}.npy", extracted, allow_pickle=False)

            all_passed = all(
                row["passed"] is True
                for row in roundtrip_rows if row["image"] == relative
            )
            base_row["status"] = "roundtrip_passed" if all_passed else "roundtrip_failed"
            base_row["all_roundtrips_passed"] = all_passed
            capacity_rows.append(base_row)
        except Exception as exc:
            base_row["status"] = "error"
            base_row["error"] = f"{type(exc).__name__}: {exc}"
            capacity_rows.append(base_row)

    elapsed = time.perf_counter() - started
    write_csv(output / "rgb_capacity_summary.csv", capacity_rows)
    write_csv(output / "rgb_roundtrip_summary.csv", roundtrip_rows)
    write_csv(output / "rgb_phase_assignment_scores.csv", assignment_rows)
    write_csv(output / "rgb_input_inventory.csv", inventory)
    write_csv(output / "rgb_skipped_inputs.csv", skipped)

    blend_positive_counts = {
        str(blend): sum(
            float(row.get(f"blend_{blend}_net_capacity_bits") or 0) > 0
            for row in capacity_rows
        )
        for blend, _ in BLENDS
    }
    blend_fit_counts = {
        str(blend): sum(
            int(row.get(f"blend_{blend}_directory_fit_assignments") or 0) > 0
            for row in capacity_rows
        )
        for blend, _ in BLENDS
    }
    summary = {
        "protocol": "CC-EDR2-RGB",
        "status": "completed_with_failures" if any(
            row.get("status") in {
                "error", "roundtrip_failed",
                "rejected_nonpositive_net_capacity",
                "rejected_no_feasible_assignment_at_1_4_blend",
            } for row in capacity_rows
        ) else "completed",
        "input_files_seen": len(files),
        "distinct_native_rgb_inputs": len(inventory),
        "skipped_files": len(skipped),
        "capacity_rows": len(capacity_rows),
        "positive_net_images": sum(
            float(row.get("signed_net_capacity_bits") or 0) > 0 for row in capacity_rows
        ),
        "positive_net_images_by_blend": blend_positive_counts,
        "images_with_at_least_one_directory_fit_by_blend": blend_fit_counts,
        "nonpositive_net_images": sum(
            row.get("status") == "rejected_nonpositive_net_capacity" for row in capacity_rows
        ),
        "no_feasible_1_4_images": sum(
            row.get("status") == "rejected_no_feasible_assignment_at_1_4_blend"
            for row in capacity_rows
        ),
        "roundtrip_images": len({row["image"] for row in roundtrip_rows}),
        "roundtrip_cases": len(roundtrip_rows),
        "roundtrip_passed": sum(row.get("passed") is True for row in roundtrip_rows),
        "roundtrip_failed": sum(row.get("passed") is False for row in roundtrip_rows),
        "blend_settings": [{"num": n, "den": d} for n, d in BLENDS],
        "phase_assignments_per_blend": 24,
        "checkpoint_sha256": model_identity["checkpoint_sha256"],
        "checkpoint": model_identity,
        "training_performed": False,
        "benchmark_key_policy": (
            "Deterministically derived per-image keys/nonces for reproducible experiments only; "
            "not a deployment key-management recommendation."
        ),
        "seed": args.seed,
        "elapsed_seconds": elapsed,
    }
    (output / "rgb_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "rgb_input_manifest.json").write_text(
        json.dumps({"images": inventory, "skipped": skipped}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
