#!/usr/bin/env python3
"""Full native-corpus EDR2 system check for CNN-v3 on its own safe geometry.

CNN-v3 uses a 5x5 receptive field. To stop any other mutable candidate from
entering a candidate's 5x5 context, this experiment uses a step-3 lattice with
nine discoverable phases and a two-pixel border. It is deliberately isolated
from the production EDR2 step-2 / four-phase / CNN-v4 wire configuration.

This runner temporarily patches geometry in-process, but writes no production
module or checkpoint changes. It compares *whole-system* capacity and exact
round trips against the already reported v4 step-2 results; metrics remain
separate because the geometries differ.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import protocol
import predictor
import run_gate
import wire
from src.cnn_model import load_model


STEP = 3
RADIUS = 2
PHASE_COUNT = STEP * STEP
CHECKPOINT = ROOT / "models" / "v3_no_weighted_loss.pth"
BATCH_SIZE = 2048


def grid_v3(shape, phase=0):
    if len(shape) != 2:
        raise ValueError("v3 experiment supports grayscale HxW images only")
    height, width = map(int, shape)
    if height % 2 or width % 2:
        raise ValueError("v3 experiment currently requires even image dimensions")
    if not isinstance(phase, int) or not 0 <= phase < PHASE_COUNT:
        raise ValueError(f"v3 phase must be an integer in [0,{PHASE_COUNT - 1}]")
    row_start = RADIUS + phase // STEP
    col_start = RADIUS + phase % STEP
    y, x = np.meshgrid(
        np.arange(row_start, height - RADIUS, STEP, dtype=np.int64),
        np.arange(col_start, width - RADIUS, STEP, dtype=np.int64),
        indexing="ij",
    )
    return y.ravel(), x.ravel()


def predict_v3(image, ys, xs, active_model=None):
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError("expected native uint8 grayscale")
    active_model = model if active_model is None else active_model
    radius = int(active_model.patch_size) // 2
    if active_model.patch_size != 5 or radius != RADIUS:
        raise ValueError("v3 experiment requires the frozen 5x5 checkpoint")
    if len(ys) != len(xs):
        raise ValueError("coordinate arrays must have equal lengths")
    if len(ys) == 0:
        return np.empty(0, dtype=np.float32)
    patches = np.stack([
        image[y - radius:y + radius + 1, x - radius:x + radius + 1]
        for y, x in zip(ys, xs)
    ]).astype(np.float32) / 255.0
    patches[:, radius, radius] = 0.0
    patches = patches[:, None, :, :]
    outputs = []
    active_model.eval()
    with torch.inference_mode():
        for start in range(0, len(patches), BATCH_SIZE):
            batch = torch.from_numpy(patches[start:start + BATCH_SIZE])
            outputs.append(active_model(batch).cpu().numpy().reshape(-1))
    return np.concatenate(outputs).astype(np.float32, copy=False)


model = None


def install_experimental_v3_geometry():
    global model
    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)
    torch.set_num_threads(4)
    model, patch, residual, parameters = load_model(str(CHECKPOINT), device="cpu")
    if patch != 5 or residual is not True:
        raise AssertionError(f"unexpected v3 checkpoint architecture: {(patch, residual)}")
    model.eval()
    model.requires_grad_(False)

    # All live protocol functions dereference this shared module at call time.
    wire.SAFE_ZONE_STEP = STEP
    wire.SAFE_ZONE_BORDER = RADIUS
    wire.SAFE_ZONE_PHASES = PHASE_COUNT
    wire.grid = grid_v3

    predictor.SAFE_ZONE_STEP = STEP
    predictor.PREDICTOR_RADIUS = RADIUS
    predictor.BATCH_SIZE = BATCH_SIZE
    predictor.CHECKPOINT = CHECKPOINT
    predictor.model = lambda: model
    predictor.coords = lambda shape, step=STEP, radius=RADIUS, phase=0: (
        grid_v3(shape, phase=phase)
        if step == STEP and radius == RADIUS
        else (_ for _ in ()).throw(ValueError("invalid v3 geometry request"))
    )
    predictor.predict = predict_v3
    return parameters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-images", type=int, default=243)
    parser.add_argument("--seed", type=int, default=20261117)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-images", type=int, default=0,
                        help="Optional quick subset; zero means the complete corpus.")
    args = parser.parse_args()
    if args.threads < 1:
        raise ValueError("--threads must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=False)

    parameters = install_experimental_v3_geometry()
    torch.set_num_threads(args.threads)
    corpus, skipped, duplicates, inventory, missing_baseline = run_gate.load_corpus(
        [args.data_dir.resolve()], allow_missing_baseline=True
    )
    if args.expected_images and len(corpus) != args.expected_images:
        raise AssertionError(
            f"expected {args.expected_images} allowlisted images, found {len(corpus)}"
        )
    if args.max_images:
        corpus = corpus[:args.max_images]
    if not corpus:
        raise AssertionError("no native grayscale images survived the allowlist")

    rng = np.random.default_rng(args.seed)
    master = bytes(range(32))
    rows, trial_rows = [], []
    total_prepare = total_trials = total_exact = 0
    for index, item in enumerate(corpus, start=1):
        original = run_gate.read_native_gray(Path(item["source"]))
        if run_gate.pixel_sha256(original) != item["pixels_sha256"]:
            raise AssertionError(f"pixel hash changed after corpus inventory: {item['name']}")
        t0 = time.perf_counter()
        q = protocol.prepare(original)
        prepare_seconds = time.perf_counter() - t0
        total_prepare += prepare_seconds

        # Invariance audit: arbitrarily rewrite every selected centre. With
        # pairwise Chebyshev spacing >=3 and a 5x5 radius of 2, no such centre
        # enters another selected candidate's context; each own centre is masked.
        changed = original.copy()
        changed[q["ys"], q["xs"]] = rng.integers(
            0, 256, len(q["ys"]), dtype=np.uint8
        )
        changed_predictions = predictor.predict(changed, q["ys"], q["xs"], model)
        invariance_ok = bool(np.array_equal(changed_predictions, q["predictions"]))
        if not invariance_ok:
            raise AssertionError(f"v3 prediction invariance failed: {item['name']}")

        row = {
            "index": index,
            "image": item["name"],
            "corpus_group": item.get("corpus_group", "unspecified"),
            "classification": item.get("classification", "unspecified"),
            "correlation_cluster": item.get("correlation_cluster", "unspecified"),
            "height": int(original.shape[0]),
            "width": int(original.shape[1]),
            "pixels": int(original.size),
            "phase_count": PHASE_COUNT,
            "selected_phase": int(q["phase"]),
            "candidate_count": int(len(q["ys"])),
            "candidate_fraction": float(len(q["ys"]) / original.size),
            "directory_bytes": int(len(q["meta"])),
            "bootstrap_candidates": int(q["h"]),
            "gross_slots": int(q["stats"]["gross_slots"]),
            "backup_bits": int(q["backup"]),
            "signed_net_payload_bits": int(q["net"]),
            "net_bpp": float(q["net"] / original.size),
            "accepted": bool(q["net"] > 0),
            "prepare_seconds": prepare_seconds,
            "prediction_invariance": invariance_ok,
            "checkpoint_sha256": hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
        }
        rows.append(row)
        if q["net"] <= 0:
            print("NONPOSITIVE", item["name"], q["net"], flush=True)
            continue

        cases = [
            ("empty", 0),
            ("one_bit", min(1, int(q["net"]))),
            ("partial", int(q["net"]) // 2),
            ("near_max", max(0, int(q["net"]) - 1)),
            ("full", int(q["net"])),
        ]
        for case_index, (case, length) in enumerate(cases, start=1):
            total_trials += 1
            nonce = (args.seed << 64) + index * 16 + case_index
            if nonce >= 2**128:
                raise OverflowError("experiment nonce exceeded uint128")
            payload = rng.integers(0, 2, length, dtype=np.uint8)
            t0 = time.perf_counter()
            reserved, capability = protocol.reserve(original, master, nonce, prepared=q)
            reserve_seconds = time.perf_counter() - t0
            t0 = time.perf_counter()
            marked = wire.embed(
                reserved, payload, wire.hider_keys(capability["hider"])
            )
            embed_seconds = time.perf_counter() - t0
            t0 = time.perf_counter()
            recovered, extracted = protocol.receive(marked, master, nonce)
            receive_seconds = time.perf_counter() - t0
            image_ok = bool(np.array_equal(recovered, original))
            payload_ok = bool(np.array_equal(extracted, payload))
            if not (image_ok and payload_ok):
                raise AssertionError(
                    f"v3 exact recovery failed: {item['name']} / {case} / {length}"
                )
            total_exact += 1
            trial_rows.append({
                "image": item["name"], "case": case, "payload_bits": length,
                "capacity_bits": int(q["net"]), "reserve_seconds": reserve_seconds,
                "embed_seconds": embed_seconds, "receive_seconds": receive_seconds,
                "exact_image_recovery": image_ok, "exact_payload_recovery": payload_ok,
            })
        print(
            f"IMAGE {index}/{len(corpus)} {item['name']} net={q['net']} "
            f"bpp={q['net']/original.size:.6f} phase={q['phase']} trials={len(cases)}",
            flush=True,
        )

    with (args.output_dir / "v3_step3_nine_phase_capacity.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (args.output_dir / "v3_step3_nine_phase_trials.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trial_rows[0]) if trial_rows else [
            "image", "case", "payload_bits", "capacity_bits", "reserve_seconds",
            "embed_seconds", "receive_seconds", "exact_image_recovery", "exact_payload_recovery"
        ])
        writer.writeheader()
        writer.writerows(trial_rows)

    positive = [r for r in rows if r["accepted"]]
    summary = {
        "experiment": "EDR2-v3 5x5 predictor on experimental step-3 nine-phase safe lattice",
        "not_production_wire_format": True,
        "checkpoint": str(CHECKPOINT.relative_to(ROOT)),
        "checkpoint_sha256": hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
        "architecture": {"patch": 5, "residual": True, "parameters": parameters},
        "geometry": {
            "step": STEP, "radius_and_border": RADIUS, "phase_count": PHASE_COUNT,
            "candidate_lattice": "row=2+phase//3, col=2+phase%3, step=3",
            "safety_reason": "5x5 receptive radius 2; other mutable centres are Chebyshev distance >=3",
        },
        "dataset_count": len(corpus),
        "expected_dataset_count": args.expected_images,
        "complete_dataset_run": not bool(args.max_images),
        "skipped_records_from_inventory": len(skipped),
        "duplicate_records_from_inventory": len(duplicates),
        "missing_original_six_baseline_stems": missing_baseline,
        "positive_images": len(positive),
        "positive_fraction": len(positive) / len(rows),
        "mean_signed_net_bpp_all_images": float(np.mean([r["net_bpp"] for r in rows])),
        "mean_signed_net_bpp_positive_only": (
            float(np.mean([r["net_bpp"] for r in positive]) if positive else 0.0)
        ),
        "median_signed_net_bpp_positive_only": (
            float(np.median([r["net_bpp"] for r in positive]) if positive else 0.0)
        ),
        "total_exact_trials": total_trials,
        "total_exact_image_and_payload_recoveries": total_exact,
        "exact_recovery_fraction": total_exact / total_trials if total_trials else None,
        "prediction_invariance_passes": sum(1 for r in rows if r["prediction_invariance"]),
        "prepare_seconds_total": total_prepare,
        "seed": args.seed,
        "threads": args.threads,
        "payload_cases": ["empty", "one_bit", "partial", "near_max", "full"],
        "protocol_geometry_warning": (
            "Nine-phase step-3 packets are experimental and must not be mixed with "
            "the production four-phase step-2 EDR2 receiver."
        ),
    }
    (args.output_dir / "v3_step3_nine_phase_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
