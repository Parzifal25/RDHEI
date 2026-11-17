#!/usr/bin/env python3
"""Benchmark exact, vectorized EDR2 patch extraction and CPU inference settings.

No checkpoint is changed. Every candidate setting is compared with the original
2048-sample / 4-thread inference path, including rounded uint8 predictions,
because encoder/receiver prediction agreement is part of the protocol.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from numpy.lib.stride_tricks import sliding_window_view

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CHECKPOINT = ROOT / "models" / "v4_patch3.pth"
IMAGE_SHAPE = (512, 512)
SEED = 20261117
BATCH_SIZES = (1024, 2048, 4096, 8192, 16384, 32768)
THREAD_COUNTS = (1, 2, 4)
WARMUPS = 1
REPEATS = 3


def make_image() -> np.ndarray:
    rng = np.random.default_rng(SEED)
    return rng.integers(0, 256, size=IMAGE_SHAPE, dtype=np.uint8)


def coordinates(shape: tuple[int, int]):
    # One active EDR2 phase: radius-one border, step-two lattice.
    y, x = np.meshgrid(
        np.arange(1, shape[0] - 1, 2, dtype=np.int64),
        np.arange(1, shape[1] - 1, 2, dtype=np.int64),
        indexing="ij",
    )
    return y.ravel(), x.ravel()


def extract_legacy(image: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    patches = np.stack([
        image[y - 1:y + 2, x - 1:x + 2] for y, x in zip(ys, xs)
    ]).astype(np.float32) / 255.0
    patches[:, 1, 1] = 0.0
    return patches[:, None, :, :]


def extract_vectorized(image: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    windows = sliding_window_view(image, (3, 3))
    patches = windows[ys - 1, xs - 1].astype(np.float32) / 255.0
    patches[:, 1, 1] = 0.0
    return np.ascontiguousarray(patches[:, None, :, :])


def infer(model, patches: np.ndarray, batch_size: int) -> np.ndarray:
    values = []
    with torch.inference_mode():
        for start in range(0, len(patches), batch_size):
            batch = torch.from_numpy(patches[start:start + batch_size])
            values.append(model(batch).cpu().numpy().reshape(-1))
    return np.concatenate(values).astype(np.float32, copy=False)


def measure(fn, warmups: int, repeats: int):
    for _ in range(warmups):
        fn()
    samples = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return result, samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)
    image = make_image()
    ys, xs = coordinates(image.shape)

    t0 = time.perf_counter()
    legacy = extract_legacy(image, ys, xs)
    legacy_extract_ms = (time.perf_counter() - t0) * 1000.0
    t0 = time.perf_counter()
    vectorized = extract_vectorized(image, ys, xs)
    vector_extract_ms = (time.perf_counter() - t0) * 1000.0
    if not np.array_equal(legacy, vectorized):
        raise AssertionError("vectorized patch extraction differs from the legacy implementation")

    checkpoint_hash = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
    loaded, patch_size, residual, parameter_count = __import__(
        "src.cnn_model", fromlist=["load_model"]
    ).load_model(str(CHECKPOINT), device="cpu")
    if (patch_size, residual) != (3, True):
        raise AssertionError(f"unexpected checkpoint architecture: {(patch_size, residual)}")
    loaded.eval()
    loaded.requires_grad_(False)

    rows = []
    reference_predictions = None
    reference_rounded = None
    # The original production defaults establish the comparison baseline.
    for threads, batch_size in ((4, 2048),):
        torch.set_num_threads(threads)
        model = loaded
        pred, samples = measure(lambda: infer(model, legacy, batch_size), WARMUPS, REPEATS)
        reference_predictions = pred
        reference_rounded = np.rint(pred).astype(np.int16)
        rows.append({
            "threads": threads, "batch_size": batch_size, "extractor": "legacy",
            "mean_inference_ms": float(np.mean(samples)),
            "std_inference_ms": float(np.std(samples, ddof=1)) if len(samples) > 1 else 0.0,
            "median_inference_ms": float(np.median(samples)),
            "max_abs_prediction_delta": 0.0, "rounded_prediction_mismatches": 0,
            "patch_count": int(len(legacy)), "checkpoint_sha256": checkpoint_hash,
        })

    for threads in THREAD_COUNTS:
        torch.set_num_threads(threads)
        for batch_size in BATCH_SIZES:
            pred, samples = measure(
                lambda: infer(loaded, vectorized, batch_size), WARMUPS, REPEATS
            )
            rounded = np.rint(pred).astype(np.int16)
            max_delta = float(np.max(np.abs(pred - reference_predictions)))
            mismatches = int(np.count_nonzero(rounded != reference_rounded))
            row = {
                "threads": threads, "batch_size": batch_size, "extractor": "vectorized",
                "mean_inference_ms": float(np.mean(samples)),
                "std_inference_ms": float(np.std(samples, ddof=1)) if len(samples) > 1 else 0.0,
                "median_inference_ms": float(np.median(samples)),
                "max_abs_prediction_delta": max_delta,
                "rounded_prediction_mismatches": mismatches,
                "patch_count": int(len(vectorized)), "checkpoint_sha256": checkpoint_hash,
            }
            rows.append(row)

    with (args.output_dir / "predictor_optimization_sweep.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    compatible = [
        r for r in rows
        if r["rounded_prediction_mismatches"] == 0
        and r["max_abs_prediction_delta"] <= 1e-4
    ]
    best = min(compatible, key=lambda r: r["mean_inference_ms"]) if compatible else None
    report = {
        "image_shape": list(image.shape), "seed": SEED,
        "phase": "step-2 phase 0, one-pixel border",
        "patch_count": int(len(ys)), "checkpoint_sha256": checkpoint_hash,
        "architecture": {"patch_size": patch_size, "residual": residual, "parameters": parameter_count},
        "legacy_patch_extraction_ms": legacy_extract_ms,
        "vectorized_patch_extraction_ms": vector_extract_ms,
        "patch_extraction_arrays_identical": True,
        "warmups": WARMUPS, "timed_repeats": REPEATS,
        "reference": {"threads": 4, "batch_size": 2048, "extractor": "legacy"},
        "best_exact_rounded_setting": best,
        "all_candidates_preserve_rounded_predictions": all(
            r["rounded_prediction_mismatches"] == 0 for r in rows
        ),
        "rows": rows,
    }
    (args.output_dir / "predictor_optimization_report.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps({
        "legacy_extract_ms": legacy_extract_ms,
        "vector_extract_ms": vector_extract_ms,
        "reference_ms": rows[0]["mean_inference_ms"],
        "best_exact_setting": best,
    }, indent=2))


if __name__ == "__main__":
    main()
