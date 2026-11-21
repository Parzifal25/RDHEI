#!/usr/bin/env python3
"""Reproducible active EDR2 end-to-end runtime and memory benchmark.

Measures prepare -> reserve/encrypt -> encrypted-domain embed -> authenticate,
extract and recover on a deterministic synthetic native grayscale fixture.
This is a pipeline benchmark, not a natural-image corpus evaluation.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
import platform
import statistics
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil
import torch

ROOT = Path(__file__).resolve().parents[1]
EDR2 = Path(__file__).resolve().parent
sys.path.insert(0, str(EDR2))

import protocol
import wire

IMAGE_SEED = 20261116
MASTER_KEY = bytes(range(32))
NONCE_BASE = 0x45445232000000000000000000000000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_image(shape: tuple[int, int]) -> np.ndarray:
    yy, xx = np.indices(shape, dtype=np.uint16)
    return (96 + ((3 * yy + 5 * xx + (yy // 16) * 7) % 32)).astype(np.uint8)


def run_once(original: np.ndarray, run_index: int) -> dict:
    nonce = NONCE_BASE + run_index
    stages: dict[str, float] = {}

    started = time.perf_counter()
    prepared = protocol.prepare(original)
    stages["prepare_prediction_and_directory_seconds"] = time.perf_counter() - started
    if int(prepared["net"]) <= 0:
        raise RuntimeError(f"synthetic fixture has nonpositive net capacity: {prepared['net']}")

    payload_rng = np.random.default_rng(IMAGE_SEED + run_index)
    payload = payload_rng.integers(0, 2, size=int(prepared["net"]), dtype=np.uint8)

    started = time.perf_counter()
    reserved, owner_capability = protocol.reserve(
        original, MASTER_KEY, nonce, prepared=prepared
    )
    stages["reserve_and_encrypt_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    marked = wire.embed(reserved, payload, owner_capability)
    stages["encrypted_domain_embed_and_reauthenticate_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    recovered, extracted = protocol.receive(marked, MASTER_KEY, nonce)
    stages["receiver_authenticate_extract_and_recover_seconds"] = time.perf_counter() - started

    if not np.array_equal(recovered, original):
        raise AssertionError(f"exact image recovery failed in iteration {run_index}")
    if not np.array_equal(extracted, payload):
        raise AssertionError(f"exact payload recovery failed in iteration {run_index}")

    stages["total_pipeline_seconds"] = sum(stages.values())
    return {
        "iteration": run_index,
        "nonce_hex": f"{nonce:032x}",
        "payload_bits": int(len(payload)),
        "net_capacity_bits": int(prepared["net"]),
        "signed_net_bpp": float(prepared["net"] / original.size),
        "selected_phase": int(prepared["phase"]),
        "exact_image_recovery": True,
        "exact_payload_recovery": True,
        **stages,
    }


def sample_rss_around(fn):
    process = psutil.Process(os.getpid())
    baseline = process.memory_info().rss
    peak = [baseline]
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            try:
                peak[0] = max(peak[0], process.memory_info().rss)
            except psutil.Error:
                pass
            stop.wait(0.005)

    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    try:
        rows = fn()
        peak[0] = max(peak[0], process.memory_info().rss)
    finally:
        stop.set()
        thread.join(timeout=2.0)
    return rows, baseline, peak[0], peak[0] - baseline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--size", type=int, default=512, help="Synthetic fixture size when --image-path is omitted.")
    parser.add_argument("--image-path", default=None, help="Optional native 8-bit grayscale image path for a real-image run.")
    args = parser.parse_args()
    if args.repeats < 2 or args.warmups < 1 or args.size < 128 or args.size % 2:
        raise ValueError("require repeats>=2, warmups>=1 and even size>=128")

    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    if args.image_path:
        from PIL import Image
        image_path = Path(args.image_path).expanduser().resolve()
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as source:
            if getattr(source, "n_frames", 1) != 1 or source.mode != "L":
                raise ValueError("benchmark image must be one native 8-bit grayscale frame (mode L)")
            image = np.asarray(source)
        if image.dtype != np.uint8 or image.ndim != 2 or image.shape[0] % 2 or image.shape[1] % 2:
            raise ValueError(f"benchmark image must be even-dimension 2D uint8 grayscale, got {image.dtype} {image.shape}")
        image = np.ascontiguousarray(image)
        source_image_name = image_path.name
        source_image_sha256 = sha256_file(image_path)
        source_image_type = "native_usc_sipi_grayscale"
    else:
        image_path = None
        image = make_image((args.size, args.size))
        source_image_name = "deterministic_synthetic_fixture"
        source_image_sha256 = None
        source_image_type = "synthetic"
    checkpoint = ROOT / "models" / "v4_patch3.pth"
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    image_hash = hashlib.sha256(image.tobytes(order="C")).hexdigest()

    # Warm the model and complete pipeline before measuring.
    for i in range(args.warmups):
        run_once(image, i + 1)
        gc.collect()

    def measured():
        rows = []
        for i in range(args.repeats):
            rows.append(run_once(image, args.warmups + i + 1))
            gc.collect()
        return rows

    rows, baseline, peak, delta = sample_rss_around(measured)
    nonce_values = [row["nonce_hex"] for row in rows]
    if len(set(nonce_values)) != len(nonce_values):
        raise AssertionError("benchmark reused a nonce under the same master key")
    checkpoint_hash = sha256_file(checkpoint)

    with (output / "e2e_stage_timings.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    stages = [
        "prepare_prediction_and_directory_seconds",
        "reserve_and_encrypt_seconds",
        "encrypted_domain_embed_and_reauthenticate_seconds",
        "receiver_authenticate_extract_and_recover_seconds",
        "total_pipeline_seconds",
    ]
    summary = {}
    for stage in stages:
        values = [float(row[stage]) for row in rows]
        summary[stage] = {
            "mean_seconds": statistics.mean(values),
            "sample_std_seconds": statistics.stdev(values),
            "median_seconds": statistics.median(values),
            "min_seconds": min(values),
            "max_seconds": max(values),
        }

    environment = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "psutil": psutil.__version__,
        "device": "CPU",
        "torch_threads": 4,
        "image_shape": list(image.shape),
        "image_seed": IMAGE_SEED if image_path is None else None,
        "source_image_type": source_image_type,
        "source_image_name": source_image_name,
        "source_file_sha256": source_image_sha256,
        "image_pixel_sha256": image_hash,
        "checkpoint": "models/v4_patch3.pth",
        "checkpoint_sha256": checkpoint_hash,
        "checkpoint_parameters": 46881,
        "master_key_bytes": len(MASTER_KEY),
        "nonce_policy": "unique sequential 128-bit benchmark nonces under one fixed master key; benchmark-only",
        "warmups": args.warmups,
        "measured_repeats": args.repeats,
        "unique_measured_nonces": len(set(nonce_values)),
        "payload_policy": "full measured net capacity in every trial",
        "timing_scope": (
            "in-memory prepare, reserve/encrypt, encrypted-domain embed, packet authentication, "
            "extract and exact image/payload reconstruction; warmed model; excludes process startup, "
            "checkpoint load, file I/O and dataset download"
        ),
        "memory_scope": (
            "process RSS sampled every 5 ms across measured end-to-end iterations; baseline after "
            "warmup with model resident; incremental RSS delta may miss sub-5-ms peaks"
        ),
        "training_or_finetuning": False,
    }
    memory = {
        "baseline_rss_mib": baseline / 2**20,
        "peak_rss_mib": peak / 2**20,
        "peak_rss_delta_mib": delta / 2**20,
        "sampling_interval_ms": 5,
    }
    report = {
        "environment": environment,
        "memory": memory,
        "stage_summary": summary,
        "iterations": rows,
        "all_exact_recoveries": all(
            row["exact_image_recovery"] and row["exact_payload_recovery"] for row in rows
        ),
    }
    (output / "e2e_benchmark.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    labels = {
        "prepare_prediction_and_directory_seconds": "Prediction and directory preparation",
        "reserve_and_encrypt_seconds": "Reservation and image encryption",
        "encrypted_domain_embed_and_reauthenticate_seconds": "Encrypted-domain embedding and authentication",
        "receiver_authenticate_extract_and_recover_seconds": "Receiver authentication, extraction and recovery",
        "total_pipeline_seconds": "Total end-to-end pipeline",
    }
    lines = [
        "# Active EDR2 end-to-end runtime and memory benchmark",
        "",
        f"- Input: {source_image_type} image {source_image_name}, shape {image.shape[0]}x{image.shape[1]} uint8 grayscale.",
        f"- Input file SHA-256: {source_image_sha256 if source_image_sha256 else 'not applicable (synthetic fixture)'}; decoded pixel SHA-256: {image_hash}.",
        f"- Frozen checkpoint: v4_patch3.pth (46,881 parameters), SHA-256 {checkpoint_hash}.",
        f"- Device: CPU, 4 PyTorch threads; warm-ups: {args.warmups}; measured repeats: {args.repeats}.",
        f"- Payload: full measured net capacity in every iteration; all image and payload recoveries exact: {report['all_exact_recoveries']}.",
        f"- Memory: baseline {memory['baseline_rss_mib']:.2f} MiB; sampled peak {memory['peak_rss_mib']:.2f} MiB; incremental peak {memory['peak_rss_delta_mib']:.2f} MiB.",
        "- Timing scope: complete in-memory prepare -> reserve/encrypt -> embed -> authenticate/extract/recover.",
        "- Excludes process startup, checkpoint loading, file I/O and dataset acquisition. Model is warmed and resident.",
        "- RSS is sampled every 5 ms; very short transient peaks may be missed.",
        "- Deterministic engineering benchmark only; not a natural-image corpus result or production deployment latency claim.",
        "",
        "| Stage | Mean (s) | Std (s) | Median (s) | Min (s) | Max (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for stage in stages:
        item = summary[stage]
        lines.append(
            f"| {labels[stage]} | {item['mean_seconds']:.6f} | {item['sample_std_seconds']:.6f} "
            f"| {item['median_seconds']:.6f} | {item['min_seconds']:.6f} | {item['max_seconds']:.6f} |"
        )
    lines += [
        "",
        "Per-iteration timing and nonce evidence is in e2e_stage_timings.csv.",
        "Machine metadata and full iteration evidence is in e2e_benchmark.json.",
        "",
    ]
    (output / "E2E_BENCHMARK_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print((output / "E2E_BENCHMARK_REPORT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
