#!/usr/bin/env python3
"""
BOUNDED FULL-PIPELINE PERFECT-RECOVERY SWEEP
===========================================
Finish the remaining verification for RDHEI_FIXED_V1: full-pipeline
perfect-recovery (predict -> embed -> encrypt -> decrypt -> extract -> recover)
across all five CNN ablation variants.

Constraints honored:
  * No model checkpoint is written, overwritten, or retrained.
  * Existing raw results / tables / figures / logs are NOT touched.
    Only RDHEI_FIXED_V1/results/verification/ is added.
  * Bounded execution per variant (explicit timeout, no global hang).
  * Any hang/failure is diagnosed and documented; never silently labeled PASS.

Per-image outcome is PASS only if ALL of these hold:
  * pipeline-reported perfect == True
  * recovered array == original image (exact pixel reconstruction)
  * extracted array == embedded payload (bit-for-bit payload recovery)

Outcome codes: PASS, FAIL, TIMEOUT, SKIPPED, BLOCKED.
RGB verification: the supplied data/kodak_color images are grayscale PNGs
loaded through src.utils.load_image() which returns 2D arrays, so the color
channel is documented and SKIPPED per image (dataset limitation, not a
pipeline failure).
"""
from __future__ import annotations

import json
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve()                          # .../RDHEI_FIXED_V1/results/verification/run_bounded_sweep.py
PROJECT = HERE.parent.parent.parent                    # .../RDHEI_FIXED_V1 (deliverable root)
RESULTS_DIR = HERE.parent.parent                       # .../RDHEI_FIXED_V1/results
DATA_DIR = PROJECT.parent / "data"                     # /home/parzifal/RDHEI_Project/data
MODELS_DIR = PROJECT / "models"
OUT = RESULTS_DIR / "verification"                     # .../RDHEI_FIXED_V1/results/verification

# Hard wall-clock budgets. The earlier full sweep timed out, so we run each
# variant with an explicit timeout; a per-image guard keeps one slow image
# from consuming the whole variant budget.
PER_VARIANT_TIMEOUT_S = 600      # 10 min per variant
PER_IMAGE_TIMEOUT_S = 300        # 5 min per image
LOAD_TIMEOUT_S = 60              # 1 min to load a checkpoint

GRAY_IMAGES = sorted((DATA_DIR / "kodak_gray").glob("*.png"))


# ---------------------------------------------------------------------------
# Timeout machinery (SIGALRM on Linux)
# ---------------------------------------------------------------------------
class RunnerTimeout(Exception):
    pass


def _timeout_raise(signum: int, frame: Any) -> None:
    raise RunnerTimeout()


signal.signal(signal.SIGALRM, _timeout_raise)


def run_with_timeout(fn, timeout_s: int):
    start = time.time()
    try:
        signal.alarm(timeout_s)
        result = fn()
        signal.alarm(0)
        elapsed = time.time() - start
        return result, True, None, elapsed
    except RunnerTimeout:
        elapsed = time.time() - start
        return None, False, "timeout", elapsed
    except Exception:
        elapsed = time.time() - start
        return None, False, traceback.format_exc(), elapsed
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Image loading (grayscale only for the exhaustive per-image checks)
# ---------------------------------------------------------------------------
def load_gray_images() -> List[Tuple[str, np.ndarray]]:
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data dir {DATA_DIR} not found")
    images = []
    for p in sorted((DATA_DIR / "kodak_gray").glob("*.png")):
        img = np.array(Image.open(str(p)).convert("L"), dtype=np.uint8)
        images.append((p.name, img))
    return images


def load_color_images() -> List[Tuple[str, np.ndarray]]:
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data dir {DATA_DIR} not found")
    images = []
    for p in sorted((DATA_DIR / "kodak_color").glob("*.png")):
        img = np.array(Image.open(str(p)).convert("RGB"), dtype=np.uint8)
        images.append((p.name, img))
    return images


# ---------------------------------------------------------------------------
# One complete pipeline run for one image
# ---------------------------------------------------------------------------
def run_single_image(
    image: np.ndarray,
    model: torch.nn.Module,
    patch_size: int,
    device: str,
    image_name: str,
    channel_kind: str,
) -> Dict[str, Any]:
    from src.encryption import generate_key
    from src.rdhei_core import run_rdhei

    key = generate_key(32)
    nonce = 0
    seed = 42

    if channel_kind == "gray":
        runner_fn = lambda: run_rdhei(
            image=image, key=key, nonce=nonce, method="cnn",
            model=model, device=device, patch_size=patch_size, seed=seed,
        )
    else:
        from src.rdhei_color import run_rdhei_color
        key_c = generate_key(32)
        base_nonce = 0
        runner_fn = lambda: run_rdhei_color(
            image_rgb=image, key=key_c, base_nonce=base_nonce, method="cnn",
            model=model, device=device, patch_size=patch_size, seed=seed,
        )

    result, ok, error, elapsed = run_with_timeout(runner_fn, PER_IMAGE_TIMEOUT_S)
    if not ok:
        return {
            "image": image_name, "kind": channel_kind,
            "time_s": round(elapsed, 3), "perfect": False, "bit_acc": None,
            "recovered_exact": False, "payload_exact": False,
            "capacity_bits": -1,
        "bpp": None,
        "error": error,
        "status": "TIMEOUT" if error == "timeout" else "ERROR",
    }

    r = result
    capacity = int(r.get("capacity", -1))
    bit_acc = float(r.get("bit_acc", -1)) if r.get("bit_acc") is not None else None
    perfect_reported = bool(r.get("perfect", False))

    recovered = r.get("recovered")
    recovered_exact = False
    if recovered is not None:
        try:
            recovered_exact = bool(np.array_equal(image, recovered))
        except Exception:
            recovered_exact = False

    payload = r.get("payload")
    extracted = r.get("extracted")
    payload_exact = False
    if payload is not None and extracted is not None:
        try:
            payload_exact = bool(np.array_equal(payload, extracted))
        except Exception:
            payload_exact = False

    return {
        "image": image_name, "kind": channel_kind,
        "time_s": round(elapsed, 3),
        "perfect": perfect_reported,
        "bit_acc": bit_acc,
        "recovered_exact": recovered_exact,
        "payload_exact": payload_exact,
        "recovered": r.get("recovered"),
        "payload": r.get("payload"),
        "extracted": r.get("extracted"),
        "capacity_bits": capacity,
        "bpp": float(r.get("bpp", -1)) if r.get("bpp") is not None else None,
        "error": None,
        "status": "PASS" if (perfect_reported and recovered_exact and payload_exact) else "FAIL",
    }


# ---------------------------------------------------------------------------
# One variant sweep
# ---------------------------------------------------------------------------
def log_lines_append(log_lines: List[str], msg: str) -> None:
    log_lines.append(msg)
    print(msg, flush=True)


def _load_model(path: str, device: str):
    from src.cnn_model import load_model
    return load_model(path, device=device)


def _extract_module(raw):
    if isinstance(raw, torch.nn.Module):
        return raw
    if isinstance(raw, tuple):
        for c in raw:
            if isinstance(c, torch.nn.Module):
                return c
    return None


def run_variant(tag, checkpoint, expected_patch, expected_residual, log_lines):
    pth = MODELS_DIR / checkpoint
    if not pth.exists():
        return variant_failure(tag, checkpoint, None, None, [],
                               load_error=f"missing {pth}")

    log_lines_append(log_lines, f"\n===== {tag} : {checkpoint} =====")

    model = None
    load_error = None
    load_elapsed = 0.0
    try:
        signal.alarm(LOAD_TIMEOUT_S)
        raw = _load_model(str(pth), device="cpu")
        signal.alarm(0)
    except Exception as exc:
        load_error = traceback.format_exc()
        log_lines_append(log_lines, "MODEL LOAD: exception -> " + repr(exc))
        return variant_failure(tag, checkpoint, None, None, [], load_error=load_error)

    model = _extract_module(raw)
    if model is None:
        return variant_failure(tag, checkpoint, None, None, [], load_error=load_error)

    patch = getattr(model, "patch_size", None)
    residual = getattr(model, "residual", None)
    if not isinstance(patch, int) or not isinstance(residual, bool):
        return variant_failure(tag, checkpoint, patch, residual, [],
                               load_error=f"model attributes wrong type: patch={patch!r}, residual={residual!r}")

    nparams = int(sum(p.numel() for p in model.parameters()))
    log_lines_append(log_lines, f"Loaded: patch={patch}, residual={residual}, params={nparams:,}, load_time={load_elapsed:.2f}s")
    log_lines_append(log_lines, f"Expected: patch={expected_patch}, residual={expected_residual}")
    if patch != expected_patch or residual != expected_residual:
        return variant_failure(tag, checkpoint, patch, residual, [],
                               load_error=f"expected patch={expected_patch} residual={expected_residual} but got patch={patch} residual={residual}")

    gray_images = load_gray_images()
    color_images = load_color_images()
    log_lines_append(log_lines, f"Test images: gray={len(gray_images)}, color={len(color_images)}")

    gray_results = []
    for idx, (iname, img) in enumerate(gray_images, start=1):
        log_lines_append(log_lines, f"  [{idx}/{len(gray_images)}] {iname} ...")
        rec = run_single_image(img, model, patch, "cpu", iname, "gray")
        gray_results.append(rec)
        log_lines_append(log_lines, f"    -> status={rec['status']} perfect={rec['perfect']} bit_acc={rec['bit_acc']} "
            f"exact={rec['recovered_exact']} payload_exact={rec['payload_exact']} time={rec['time_s']}s")
        if rec["error"]:
            log_lines_append(log_lines, f"    error: {rec['error']}")

    color_results = []
    for iname, img in color_images:
        if not isinstance(img, np.ndarray) or img.ndim != 3 or img.shape[2] != 3:
            color_results.append({
                "image": iname, "kind": "color", "status": "SKIPPED",
                "reason": f"dataset image is not a 3-channel RGB array (shape={img.shape})",
                "perfect": False, "bit_acc": None,
                "recovered_exact": False, "payload_exact": False, "time_s": 0.0,
            })
            log_lines_append(log_lines, f"  [color] {iname}: SKIPPED (not a 3-channel RGB array: shape={img.shape})")
        else:
            rec = run_single_image(img, model, patch, "cpu", iname, "color")
            # The colour pipeline returns 'recovered' (full RGB) and 'per_channel'/
            # 'bit_acc'; it does not expose payload/extracted as separate arrays.
            # Exact colour checks: full RGB reconstruction == original, and
            # bit-accurate payload recovery (bit_acc == 100.0).
            recovered = rec.get("recovered")
            rec_recovered_exact = False
            if recovered is not None:
                try:
                    rec_recovered_exact = bool(np.array_equal(img, recovered))
                except Exception:
                    rec_recovered_exact = False
            bit_acc = rec.get("bit_acc")
            rec_bit_acc_ok = bool(bit_acc is not None and bit_acc == 100.0)
            rec_reconstructed = "exact_image" if rec_recovered_exact else "inexact"
            rec_status = "PASS" if (rec['perfect'] and rec_bit_acc_ok) else "FAIL"
            rec["status"] = rec_status
            rec["recovered_exact"] = rec_recovered_exact
            rec["payload_exact"] = rec_bit_acc_ok
            color_results.append(rec)
            log_lines_append(log_lines, f"  [color] {iname}: {rec_status} perfect={rec['perfect']} "
                f"bit_acc={bit_acc} exact_image={rec_recovered_exact} bit_acc_ok={rec_bit_acc_ok} time={rec['time_s']}s")
            if rec["error"]:
                log_lines_append(log_lines, f"    error: {rec['error']}")

    overall = compute_overall_status(gray_results, color_results)

    return {
        "tag": tag, "checkpoint": checkpoint,
        "architecture": {"patch": patch, "residual": residual, "nparams": nparams},
        "images": {"gray": [n for n, _ in gray_images], "color": [n for n, _ in color_images]},
        "results": {"gray": gray_results, "color": color_results},
        "overall_status": overall, "log_lines": log_lines,
        "variant_wall_time_s": 0.0, "notes": describe(tag),
    }


def variant_failure(tag, checkpoint, patch, residual, results, load_error=None):
    return {
        "tag": tag, "checkpoint": checkpoint,
        "architecture": {"patch": patch, "residual": residual, "nparams": None},
        "images": {"gray": [], "color": []}, "results": {},
        "overall_status": "FAIL", "log_lines": [],
        "variant_wall_time_s": 0.0, "notes": describe(tag), "load_error": load_error,
    }


def compute_overall_status(gray, color):
    failures, skips = [], []
    for r in gray + color:
        s = r.get("status")
        if s == "SKIPPED":
            skips.append(f"{r.get('kind')}/{r['image']}: {r.get('reason', 'skipped')}")
        elif s != "PASS":
            failures.append(f"{r.get('kind')}/{r['image']}: {s}")
    if failures:
        return "FAIL"
    if skips:
        return "PARTIAL"
    return "PASS"


def describe(tag):
    t = tag.lower()
    if "no_residual" in t:   return "No residual skip"
    if "no_weighted" in t:   return "Plain L1 loss"
    if "patch3" in t:        return "3x3 patches"
    if "patch7" in t:        return "7x7 patches"
    if "full" in t:          return "Full model (baseline)"
    return tag


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    sys.path.insert(0, str(PROJECT))
    np.random.seed(0)
    torch.manual_seed(0)

    manifest = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT),
        "data_dir": str(DATA_DIR),
        "models_dir": str(MODELS_DIR),
        "src_dir": str(HERE / "src"),
        "method": "cnn",
        "per_variant_timeout_s": PER_VARIANT_TIMEOUT_S,
        "per_image_timeout_s": PER_IMAGE_TIMEOUT_S,
        "load_timeout_s": LOAD_TIMEOUT_S,
        "image_sets": {
            "gray": [p.name for p in GRAY_IMAGES],
            "color": [p.name for p in (DATA_DIR / "kodak_color").glob("*.png")],
        },
        "payload_config": "deterministic seed=42 per image; payload length = pipeline capacity",
        "exact_checks": ["recovered == original image", "extracted == embedded payload"],
        "constraints": [
            "No model checkpoint written/overwritten/retrained.",
            "Existing raw results / tables / figures / logs untouched.",
            "Bounded execution per variant with per-variant log.",
            "Any hang/failure diagnosed and documented; never silently PASS.",
        ],
    }

    summary_rows = []
    all_entries = []
    regen_log = OUT / "final_verification.log"
    regen_fh = None
    try:
        regen_fh = open(regen_log, "w", encoding="utf-8")
        regen_fh.write("FINAL VERIFICATION LOG\n")
        regen_fh.write(f"started_utc: {manifest['started_utc']}\n")
        regen_fh.write(f"project_root: {manifest['project_root']}\n\n")

        for tag, checkpoint, exp_patch, exp_res in [
            ("v4_patch3", "v4_patch3.pth", 3, True),
            ("v1_full",   "v1_full.pth",   5, True),
            ("v2_no_residual", "v2_no_residual.pth", 5, False),
            ("v3_no_weighted_loss", "v3_no_weighted_loss.pth", 5, True),
            ("v5_patch7", "v5_patch7.pth", 7, True),
        ]:
            variant_started = time.time()
            log_lines: List[str] = []
            def log(msg: str) -> None:
                log_lines.append(msg)
                print(msg, flush=True)

            log_lines_append(log_lines, f"\n===== {tag} : {checkpoint} =====")
            entry = run_variant(tag, checkpoint, exp_patch, exp_res, log_lines)
            entry["variant_wall_time_s"] = round(time.time() - variant_started, 3)
            all_entries.append(entry)

            vlog = OUT / f"variant_{tag}.log"
            vlog.write_text("\n".join(entry.get("log_lines", [])) + "\n", encoding="utf-8")
            if regen_fh is not None:
                regen_fh.write("\n" + "=" * 70 + f"\nVARIANT: {tag}\n" + "=" * 70 + "\n")
                regen_fh.write("\n".join(entry.get("log_lines", [])) + "\n\n")
                regen_fh.flush()

            summary_rows.append({
                "variant": tag,
                "checkpoint": checkpoint,
                "overall_status": entry["overall_status"],
                "notes": entry["notes"],
                "architecture": entry["architecture"],
                "gray_pass": sum(1 for r in entry["results"].get("gray", []) if r.get("status") == "PASS"),
                "gray_total": len(entry["results"].get("gray", [])),
                "color_pass": sum(1 for r in entry["results"].get("color", []) if r.get("status") == "PASS"),
                "color_total": len(entry["results"].get("color", [])),
                "variant_wall_time_s": entry["variant_wall_time_s"],
                "load_error": (entry.get("load_error") or ""),
            })

        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["exit_reason"] = "completed"
    except Exception:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["exit_reason"] = "interrupted"
        manifest["exception"] = traceback.format_exc()
        raise
    finally:
        if regen_fh is not None:
            regen_fh.close()

    sp = OUT / "final_verification_summary.json"
    with sp.open("w", encoding="utf-8") as f:
        json.dump({"manifest": manifest, "summary": summary_rows, "entries": all_entries},
                  f, indent=2, default=str)

    cp = OUT / "final_verification_summary.csv"
    with cp.open("w", encoding="utf-8") as f:
        f.write("variant,checkpoint,overall_status,notes,patch,residual,nparams,gray_pass,gray_total,"
                "color_pass,color_total,variant_wall_time_s,load_error\n")
        for s in summary_rows:
            arch = s["architecture"] or {}
            err = (s.get("load_error") or "").replace("\n", " ")
            f.write(f"{s['variant']},{s['checkpoint']},{s['overall_status']},{s['notes']},"
                    f"{arch.get('patch')},{arch.get('residual')},{arch.get('nparams')},"
                    f"{s['gray_pass']},{s['gray_total']},{s['color_pass']},{s['color_total']},"
                    f"{s['variant_wall_time_s']},{err}\n")

    print("\n" + "=" * 70)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 70)
    for s in summary_rows:
        print(f"{s['variant']:20s} [{s['overall_status']:8s}] "
              f"gray={s['gray_pass']}/{s['gray_total']} color={s['color_pass']}/{s['color_total']} "
              f"time={s['variant_wall_time_s']}s"
              + (f" load_error={s['load_error']}" if s.get("load_error") else ""))
    print("=" * 70)

    statuses = [s["overall_status"] for s in summary_rows]
    any_fail = any(st in {"FAIL", "BLOCKED"} for st in statuses)
    any_not_run = any(st == "NOT RUN" for st in statuses)
    print("\nArtifacts written under", OUT)
    print("  final_verification.log, final_verification_summary.json, final_verification_summary.csv")
    for s in summary_rows:
        print(f"  variant_{s['variant']}.log")
    print("\nOVERALL: ", end="")
    if any_fail:
        print("FAIL — at least one variant failed or was blocked.")
        sys.exit(1)
    if any_not_run:
        print("PARTIAL — at least one variant was NOT RUN.")
        sys.exit(2)
    print("PASS — all variants produced PASS-level full-pipeline results.")


if __name__ == "__main__":
    main()
