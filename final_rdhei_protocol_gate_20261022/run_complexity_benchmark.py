#!/usr/bin/env python3
"""Reproducible frozen-checkpoint complexity, runtime and CPU-memory benchmark.

MAC convention: Conv2d MACs = output elements * (in_channels/groups) * kernel area;
Linear MACs = output elements * in_features. FLOPs = 2 * MACs (multiply + add).
Bias, BatchNorm, ReLU, Sigmoid, clipping and patch extraction are excluded from
the primary MAC/FLOP count. RSS is sampled every 5 ms in a fresh worker process.
"""
from __future__ import annotations
import csv, gc, hashlib, json, multiprocessing as mp, os, platform, sys, threading, time
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psutil
import torch

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
OUT_DEFAULT = ROOT / "results" / "reproducible_complexity_20261116"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final_rdhei_protocol_gate_20261022"))
from src.baselines import med_predict, gap_predict, calic_predict
from src.cnn_model import load_model
from src.predictor import cnn_predict_map
import wire

WARMUP, REPEATS, THREADS = 5, 10, 4
IMAGE_SHAPE, IMAGE_SEED = (512, 512), 20261116
VARIANTS = [
    ("CNN-3x3 (proposed v4)", "v4_patch3.pth"),
    ("CNN-5x5 (v1 full)", "v1_full.pth"),
    ("CNN-5x5 (v2 no residual)", "v2_no_residual.pth"),
    ("CNN-5x5 (v3 no weighted loss)", "v3_no_weighted_loss.pth"),
    ("CNN-7x7 (v5)", "v5_patch7.pth"),
]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def make_image():
    rng = np.random.default_rng(IMAGE_SEED)
    noise = rng.integers(0, 256, IMAGE_SHAPE, dtype=np.uint8)
    y = np.arange(IMAGE_SHAPE[0], dtype=np.uint16)[:, None]
    x = np.arange(IMAGE_SHAPE[1], dtype=np.uint16)[None, :]
    pattern = ((3 * y + 5 * x + ((y // 16) % 2) * 31) % 256).astype(np.uint8)
    return ((noise.astype(np.uint16) + pattern.astype(np.uint16)) // 2).astype(np.uint8)

def count_model_ops(model, patch_size):
    counts = {"macs": 0}
    handles = []
    def conv_hook(module, inputs, output):
        batch, out_channels, out_h, out_w = output.shape
        kh, kw = module.kernel_size
        counts["macs"] += int(batch * out_channels * out_h * out_w *
                              (module.in_channels // module.groups) * kh * kw)
    def linear_hook(module, inputs, output):
        counts["macs"] += int(output.numel() * module.in_features)
    for module in model.modules():
        if isinstance(module, torch.nn.Conv2d):
            handles.append(module.register_forward_hook(conv_hook))
        elif isinstance(module, torch.nn.Linear):
            handles.append(module.register_forward_hook(linear_hook))
    with torch.inference_mode():
        model(torch.zeros((1, 1, patch_size, patch_size), dtype=torch.float32))
    for handle in handles:
        handle.remove()
    return int(counts["macs"]), sum(int(p.numel()) for p in model.parameters())

def sample_peak_rss(fn):
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
    samples = []
    try:
        for _ in range(REPEATS):
            started = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - started) * 1000.0)
            peak[0] = max(peak[0], process.memory_info().rss)
    finally:
        stop.set()
        thread.join(timeout=2.0)
    return samples, float(baseline / 2**20), float(peak[0] / 2**20), float((peak[0]-baseline) / 2**20)

def worker(method, checkpoint_name, output_json):
    torch.set_num_threads(THREADS)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    image = make_image()
    result = {
        "method": method, "image_shape": list(image.shape),
        "image_sha256": hashlib.sha256(image.tobytes(order="C")).hexdigest(),
        "device": "cpu", "threads": THREADS,
        "warmup_runs": WARMUP, "timed_repeats": REPEATS,
    }
    if checkpoint_name is None:
        funcs = {"MED": med_predict, "GAP": gap_predict, "CALIC": calic_predict}
        fn = lambda: funcs[method](image)
        for _ in range(WARMUP):
            fn()
        gc.collect()
        samples, baseline, peak, delta = sample_peak_rss(fn)
        result.update({
            "parameters": 0, "macs_per_patch": None, "flops_per_patch": None,
            "checkpoint_file_bytes": 0, "parameter_tensor_bytes": 0,
            "state_dict_tensor_bytes": 0,
        })
    else:
        checkpoint = MODELS / checkpoint_name
        model, patch_size, residual, params = load_model(str(checkpoint), device="cpu")
        model.eval()
        model.requires_grad_(False)
        macs, counted_params = count_model_ops(model, patch_size)
        if counted_params != params:
            raise AssertionError(f"hook parameter count {counted_params} != loader count {params}")
        state_bytes = sum(int(t.numel() * t.element_size()) for t in model.state_dict().values()
                          if isinstance(t, torch.Tensor))
        parameter_bytes = sum(int(p.numel() * p.element_size()) for p in model.parameters())
        fn = lambda: cnn_predict_map(image, model, device="cpu", patch_size=patch_size)
        for _ in range(WARMUP):
            fn()
        gc.collect()
        samples, baseline, peak, delta = sample_peak_rss(fn)
        ys, xs = wire.grid(IMAGE_SHAPE, phase=0)
        safe_candidates = int(len(ys))
        full_count = IMAGE_SHAPE[0] * IMAGE_SHAPE[1]
        result.update({
            "checkpoint": checkpoint_name, "checkpoint_sha256": sha256_file(checkpoint),
            "checkpoint_file_bytes": int(checkpoint.stat().st_size),
            "patch_size": int(patch_size), "residual": bool(residual),
            "parameters": int(params), "parameter_tensor_bytes": int(parameter_bytes),
            "state_dict_tensor_bytes": int(state_bytes),
            "macs_per_patch": int(macs), "flops_per_patch": int(2*macs),
            "full_map_predictions_512": int(full_count),
            "full_map_macs_512": int(macs*full_count),
            "full_map_flops_512": int(2*macs*full_count),
            "edr2_candidates_per_phase_512": safe_candidates,
            "edr2_macs_per_phase_512": int(macs*safe_candidates),
            "edr2_flops_per_phase_512": int(2*macs*safe_candidates),
            "edr2_all_four_phase_macs_512": int(macs*safe_candidates*4),
            "edr2_all_four_phase_flops_512": int(2*macs*safe_candidates*4),
        })
        del model
        gc.collect()
    arr = np.asarray(samples, dtype=np.float64)
    result.update({
        "baseline_rss_mb": round(baseline, 3), "peak_rss_mb": round(peak, 3),
        "peak_rss_delta_mb": round(delta, 3),
        "runtime_mean_ms": float(arr.mean()), "runtime_std_ms": float(arr.std(ddof=1)),
        "runtime_min_ms": float(arr.min()), "runtime_max_ms": float(arr.max()),
        "runtime_median_ms": float(np.median(arr)),
        "runtime_fps": float(1000.0/arr.mean()),
        "runtime_samples_ms": [float(v) for v in samples],
    })
    Path(output_json).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")

def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(OUT_DEFAULT))
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    image = make_image()
    env = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(), "processor": platform.processor(),
        "machine": platform.machine(), "cpu_count_logical": os.cpu_count(),
        "python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
        "device": "CPU", "torch_threads": THREADS, "benchmark_image_shape": list(IMAGE_SHAPE),
        "benchmark_image_seed": IMAGE_SEED,
        "benchmark_image_sha256": hashlib.sha256(image.tobytes(order="C")).hexdigest(),
        "warmup_runs": WARMUP, "timed_repeats": REPEATS,
        "runtime_scope": "full-map predictor only; excludes embedding, AES, extraction and recovery",
        "flop_convention": "one multiply-accumulate = 2 FLOPs; Conv2d and Linear only",
        "excluded_from_mac_flop_count": ["bias additions", "BatchNorm", "ReLU", "Sigmoid",
            "output scaling", "patch extraction/memory copies", "NumPy preprocessing", "Python overhead"],
        "memory_measurement": "RSS sampled every 5 ms during timed inference in a fresh process; baseline after warmup",
        "training_performed": False, "training_or_finetuning": False,
    }
    (output / "benchmark_environment.json").write_text(json.dumps(env, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    methods = [("MED", None), ("GAP", None), ("CALIC", None)] + VARIANTS
    ctx = mp.get_context("spawn")
    results = []
    for i, (method, checkpoint) in enumerate(methods):
        out_json = output / f"worker_{i:02d}.json"
        proc = ctx.Process(target=worker, args=(method, checkpoint, str(out_json)))
        proc.start()
        proc.join()
        if proc.exitcode != 0 or not out_json.is_file():
            raise RuntimeError(f"benchmark worker failed for {method}: exit={proc.exitcode}")
        row = json.loads(out_json.read_text(encoding="utf-8"))
        results.append(row)
        print(f"{method}: {row['runtime_mean_ms']:.3f} ms, peak RSS delta={row['peak_rss_delta_mb']:.2f} MB", flush=True)

    cols = []
    for row in results:
        for key in row:
            if key != "runtime_samples_ms" and key not in cols:
                cols.append(key)
    with (output / "complexity_runtime_memory.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=cols)
        writer.writeheader()
        writer.writerows([{k:v for k,v in row.items() if k != "runtime_samples_ms"} for row in results])
    with (output / "runtime_samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["method", "sample_index", "runtime_ms"])
        writer.writeheader()
        for row in results:
            for i, sample in enumerate(row["runtime_samples_ms"]):
                writer.writerow({"method": row["method"], "sample_index": i+1, "runtime_ms": sample})

    cnn = [r for r in results if r.get("checkpoint")]
    lines = [
        "# Reproducible CNN complexity, runtime and memory benchmark", "",
        f"- Host: {env['processor'] or env['machine']}; OS: {env['platform']}",
        f"- Python: {env['python']}; NumPy: {env['numpy']}; PyTorch: {env['torch']}",
        f"- Device: CPU; threads: {THREADS}",
        f"- Input: deterministic 512x512 uint8 synthetic grayscale image; SHA-256 {env['benchmark_image_sha256']}",
        f"- Timing: {WARMUP} warmups and {REPEATS} timed repeats; full-map predictor only",
        "- FLOP convention: one MAC = 2 FLOPs, counting Conv2d and Linear only; non-matrix operations excluded.",
        "- Memory: fresh worker per method; process RSS sampled every 5 ms after warmup.",
        "- Checkpoint file bytes, tensor storage and peak RSS delta are separate measurements.",
        "- No training or fine-tuning performed.", "",
        "## CNN complexity and runtime", "",
        "| Model | Patch | Params | MACs/patch | FLOPs/patch | FLOPs/full 512x512 map | Checkpoint MB | State tensor MB | Peak RSS delta MB | Mean runtime ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in cnn:
        lines.append(f"| {r['method']} | {r['patch_size']}x{r['patch_size']} | {r['parameters']:,} "
            f"| {r['macs_per_patch']:,} | {r['flops_per_patch']:,} | {r['full_map_flops_512']:,} "
            f"| {r['checkpoint_file_bytes']/1e6:.4f} | {r['state_dict_tensor_bytes']/1e6:.4f} "
            f"| {r['peak_rss_delta_mb']:.2f} | {r['runtime_mean_ms']:.3f} |")
    lines += ["", "## Predictor runtime comparison", "",
        "| Method | Mean ms | Std ms | Median ms | Min ms | Max ms | FPS | Peak RSS delta MB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        lines.append(f"| {r['method']} | {r['runtime_mean_ms']:.3f} | {r['runtime_std_ms']:.3f} "
            f"| {r['runtime_median_ms']:.3f} | {r['runtime_min_ms']:.3f} | {r['runtime_max_ms']:.3f} "
            f"| {r['runtime_fps']:.4f} | {r['peak_rss_delta_mb']:.2f} |")
    lines += ["", "## Measurement boundaries", "",
        "- FLOPs/patch is one forward pass on one P×P input patch. Full-map FLOPs multiply the patch count by 262,144.",
        "- The exact EDR2 safe-lattice per-phase and four-phase MAC/FLOP counts are recorded in the CSV; do not confuse them with full-map legacy predictor runtime.",
        "- RSS delta is sampled and can miss transient peaks shorter than the 5 ms sampling interval.",
        "- Classical predictors have no learned CNN parameters or Conv2d/Linear MAC count; runtime and RSS are measured identically.", "",
        "## Frozen checkpoint SHA-256", ""]
    for r in cnn:
        lines.append(f"- {r['checkpoint']}: {r['checkpoint_sha256']}")
    (output / "complexity_benchmark_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")

    figures = output / "figures"
    figures.mkdir()
    def bar(name, labels, values, ylabel, title, log=False):
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(labels))
        ax.bar(x, values)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=28, ha="right")
        if log:
            ax.set_yscale("log")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(figures / name, dpi=180)
        plt.close(fig)
    bar("fig_runtime_predictor_ms.png", [r["method"] for r in results],
        [r["runtime_mean_ms"] for r in results], "Mean runtime (ms)",
        "Full-map predictor runtime (512x512 CPU)", log=True)
    bar("fig_cnn_parameters.png", [r["method"] for r in cnn],
        [r["parameters"] for r in cnn], "Parameters", "CNN parameter count")
    bar("fig_cnn_flops_per_patch.png", [r["method"] for r in cnn],
        [r["flops_per_patch"] for r in cnn], "FLOPs per patch", "CNN forward-pass FLOPs per input patch")
    bar("fig_cnn_peak_rss_delta.png", [r["method"] for r in cnn],
        [r["peak_rss_delta_mb"] for r in cnn], "Peak RSS delta (MB)",
        "Sampled incremental process RSS during CNN inference")
    print(f"Complexity benchmark complete: {output}", flush=True)

if __name__ == "__main__":
    main()
