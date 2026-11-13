#!/usr/bin/env python3
"""
FINAL_VERIFY_FULL_PIPELINE.py
=============================
Finish the blocked ablation verification: full-pipeline perfect-recovery sweep
for all 5 CNN variants, with separate logs per variant.

This is intentionally NOT a generic rerun of earlier experiments. It exercises
the COMPLETE pipeline (predict -> embed -> encrypt -> decrypt -> extract ->
recover) and checks:
  * exact original-image reconstruction
  * bit-for-bit payload recovery
  * pipeline-reported perfect / bit_acc

Constraints honored:
  * No model checkpoint is written, overwritten, or retrained.
  * Existing raw results / tables / figures / logs are untouched.
  * Bounded execution per variant; per-variant logs and timeouts.
  * Any hang/failure is diagnosed and documented, never silently labeled PASS.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch

# ---------------------------------------------------------------------------
# Paths — resolve relative to this script so cwd does not matter.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT = HERE
# In this workspace RDHEI_FIXED_V1 is the project root for code + models.
GRAY_DIR = HERE.parent / "data" / "kodak_gray"
COLOR_DIR = HERE.parent / "data" / "kodak_color"

MODELS_DIR = HERE / "models"
if not MODELS_DIR.exists():
    raise FileNotFoundError(f"Expected canonical model dir {MODELS_DIR} does not exist.")

# Legacy alternate checkpoint dir, only used for reporting if present.
_MODELS_DIR_ALT = HERE.parent / "models_ablation" if HERE.parent.exists() else None

OUT = PROJECT / "results" / "verification"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Hard per-variant wall clock budget. The earlier full sweep timed out, so we
# run each variant with an explicit timeout and do not rely on a single global
# timeout that can silently kill the whole job.
# ---------------------------------------------------------------------------
PER_VARIANT_TIMEOUT_S = 600  # 10 minutes

# Per-image guard inside a variant, so a single slow image does not consume the
# whole variant budget without producing a per-image record.
PER_IMAGE_TIMEOUT_S = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Timeout machinery — SIGALRM-based for this Linux environment.
# ---------------------------------------------------------------------------
class RunnerTimeout(Exception):
    pass


def _timeout_raise(signum: int, frame: Any) -> None:
    raise RunnerTimeout()


signal.signal(signal.SIGALRM, _timeout_raise)


def run_with_timeout(fn, timeout_s: int):
    """Call `fn()` under an alarm-based timeout.

    Returns (result, ok, error, elapsed).
    """
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
# Image loading (reuse project utilities, but through absolute dirs).
# ---------------------------------------------------------------------------
def load_gray_images() -> List[Tuple[str, np.ndarray]]:
    from src.utils import load_images_from_dir

    if not GRAY_DIR.exists():
        raise FileNotFoundError(f"Gray image dir {GRAY_DIR} not found")
    return [ (n, a if isinstance(a, np.ndarray) else np.array(a)) for n, a in load_images_from_dir(str(GRAY_DIR)) ]


def load_color_images() -> List[Tuple[str, np.ndarray]]:
    from src.utils import load_images_from_dir

    if not COLOR_DIR.exists():
        raise FileNotFoundError(f"Color image dir {COLOR_DIR} not found")
    return [ (n, a if isinstance(a, np.ndarray) else np.array(a)) for n, a in load_images_from_dir(str(COLOR_DIR)) ]


# ---------------------------------------------------------------------------
# Variant list.
# ---------------------------------------------------------------------------
VARIANTS = [
    {
        "tag": "v1_full",
        "rel": "v1_full.pth",
        "expected_patch": 5,
        "expected_residual": True,
        "channels": ["gray", "color"],
    },
    {
        "tag": "v2_no_residual",
        "rel": "v2_no_residual.pth",
        "expected_patch": 5,
        "expected_residual": False,
        "channels": ["gray", "color"],
    },
    {
        "tag": "v3_no_weighted_loss",
        "rel": "v3_no_weighted_loss.pth",
        "expected_patch": 5,
        "expected_residual": True,
        "channels": ["gray", "color"],
    },
    {
        "tag": "v5_patch7",
        "rel": "v5_patch7.pth",
        "expected_patch": 7,
        "expected_residual": True,
        "channels": ["gray", "color"],
    },
    # v4_patch3 already verified separately as a regression check, but we still
    # include it here only for completeness of the sweep artifact. If it fails
    # here but passed the dedicated regression run, we reflect that accurately.
    {
        "tag": "v4_patch3",
        "rel": "v4_patch3.pth",
        "expected_patch": 3,
        "expected_residual": True,
        "channels": ["gray", "color"],
    },
]


def variant_notes(tag: str) -> str:
    t = tag.lower()
    if "no_residual" in t:
        return "No residual skip"
    if "no_weighted" in t:
        return "Plain L1 loss"
    if "patch3" in t:
        return "3x3 patches"
    if "patch7" in t:
        return "7x7 patches"
    if "full" in t:
        return "Full model (baseline)"
    return "unknown"


# ---------------------------------------------------------------------------
# One complete pipeline run for one image + one variant.
# ---------------------------------------------------------------------------
def run_single_image(
    method: str,
    channel_kind: str,
    image_name: str,
    image: np.ndarray,
    model,
    patch_size: int,
    device: str,
) -> Dict[str, Any]:
    """Run the complete RDHEI pipeline for one image.

    Returns a dict with explicit exact-recovery checks, even if the pipeline
    already reports `perfect`.
    """
    if method != "cnn":
        raise NotImplementedError("Only CNN method is used here.")

    if channel_kind == "gray":
        key = __import__("src.encryption", fromlist=["generate_key"]).generate_key(32)
        nonce = 0
        seed = 42
        runner_fn = lambda: __import__("src.rdhei_core", fromlist=["run_rdhei"]).run_rdhei(
            image=image,
            key=key,
            nonce=nonce,
            method="cnn",
            model=model,
            device=device,
            patch_size=patch_size,
            seed=seed,
        )
    else:
        from src.encryption import generate_key

        key = generate_key(32)
        base_nonce = 0
        seed = 42
        from src.rdhei_color import run_rdhei_color

        runner_fn = lambda: run_rdhei_color(
            image_rgb=image,
            key=key,
            base_nonce=base_nonce,
            method="cnn",
            model=model,
            device=device,
            patch_size=patch_size,
            seed=seed,
        )

    result, ok, error, elapsed = run_with_timeout(runner_fn, PER_IMAGE_TIMEOUT_S)

    if not ok:
        return {
            "image": image_name,
            "kind": channel_kind,
            "time_s": round(elapsed, 3),
            "perfect": False,
            "bit_acc": None,
            "recovered_exact": False,
            "payload_exact": False,
            "status": "TIMEOUT" if error == "timeout" else "ERROR",
            "error": error,
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
        "image": image_name,
        "kind": channel_kind,
        "time_s": round(elapsed, 3),
        "perfect": perfect_reported,
        "bit_acc": bit_acc,
        "recovered_exact": recovered_exact,
        "payload_exact": payload_exact,
        "capacity_bits": capacity,
        "bpp": float(r.get("bpp", -1)) if r.get("bpp") is not None else None,
        "status": "PASS" if (perfect_reported and recovered_exact and payload_exact) else "FAIL",
    }


# ---------------------------------------------------------------------------
# One variant sweep.
# ---------------------------------------------------------------------------
def run_variant(variant: Dict[str, Any]) -> Dict[str, Any]:
    tag = variant["tag"]
    pth = MODELS_DIR / variant["rel"]
    if not pth.exists():
        raise FileNotFoundError(f"Variant checkpoint {pth} not found")

    log_lines: List[str] = []
    def log(msg: str) -> None:
        log_lines.append(msg)
        print(msg, flush=True)

    log(f"\n===== {tag} : {variant['rel']} =====")

    # Model load under timeout so a broken checkpoint cannot hang the sweep.
    model = None
    load_elapsed = 0.0
    load_error = None

    try:
        from src.cnn_model import load_model as _lm
        signal.alarm(60)
        raw = _lm(str(pth), device="cpu")
        signal.alarm(0)
    except Exception as exc:
        load_error = traceback.format_exc()
        log("MODEL LOAD: exception -> " + repr(exc))
        return variant_failure(tag, pth.name, None, None, [], [], load_error=load_error, log_lines=log_lines)
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass

    # load_model returns (model, patch, residual, n_params).
    if isinstance(raw, torch.nn.Module):
        model = raw
    elif isinstance(raw, tuple):
        model = None
        for candidate in raw:
            if isinstance(candidate, torch.nn.Module):
                model = candidate
                break
        if model is None:
            load_error = "load_model returned a tuple with no torch.nn.Module (got " + repr(raw)[:200] + "...)"
            log("MODEL LOAD: bad return -> " + load_error)
            return variant_failure(tag, pth.name, None, None, [], [], load_error=load_error, log_lines=log_lines)
    else:
        load_error = "load_model returned unexpected type " + repr(type(raw))
        log("MODEL LOAD: bad return type -> " + load_error)
        return variant_failure(tag, pth.name, None, None, [], [], load_error=load_error, log_lines=log_lines)

    if model is None or not hasattr(model, "parameters"):
        log("MODEL LOAD: model is None or not a torch.nn.Module (type=" + repr(type(model)) + ")")
        return variant_failure(tag, pth.name, None, None, [], [], load_error="model is None or not a Module (type=" + repr(type(model)) + ")", log_lines=log_lines)

    patch = getattr(model, "patch_size", None)
    residual = getattr(model, "residual", None)
    if not isinstance(patch, int) or not isinstance(residual, bool):
        log(f"MODEL ATTRIBUTES WRONG TYPE: patch={patch!r} ({type(patch).__name__}), residual={residual!r} ({type(residual).__name__})")
        return variant_failure(
            tag,
            pth.name,
            patch,
            residual,
            [],
            [],
            load_error=f"model attributes wrong type: patch={patch!r}, residual={residual!r}",
            log_lines=log_lines,
        )

    nparams = int(sum(p.numel() for p in model.parameters()))

    log("Loaded: patch=" + repr(patch) + ", residual=" + repr(residual) + ", params=" + format(nparams, ",") + ", load_time=" + format(load_elapsed, ".2f") + "s")
    log("Expected: patch=" + repr(variant["expected_patch"]) + ", residual=" + repr(variant["expected_residual"]))

    patch_ok = patch == variant["expected_patch"]
    residual_ok = residual == variant["expected_residual"]
    if not (patch_ok and residual_ok):
        log(f"ARCHITECTURE MISMATCH vs expected: patch_ok={patch_ok}, residual_ok={residual_ok}")
        return variant_failure(
            tag,
            pth.name,
            patch,
            residual,
            [],
            [],
            load_error=f"expected patch={variant['expected_patch']} residual={variant['expected_residual']} but got patch={patch} residual={residual}",
            log_lines=log_lines,
        )

    # ---- end model validation ----

    gray_images = load_gray_images()
    color_images = load_color_images()

    log("Test images: gray=" + str(len(gray_images)) + ", color=" + str(len(color_images)))

    results: List[Dict[str, Any]] = []
    channel_results: Dict[str, List[Dict[str, Any]]] = {}

    for channel_kind in variant["channels"]:
        if channel_kind == "gray":
            raw_images = gray_images
        else:
            raw_images = color_images

        channel_results[channel_kind] = []
        log("\n--- " + channel_kind.upper() + " : " + str(len(raw_images)) + " images ---")
        for idx, (iname, img) in enumerate(raw_images, start=1):
            log(f"[{idx}/{len(raw_images)}] {iname} ...")
            if channel_kind == "color":
                if not isinstance(img, np.ndarray) or img.ndim != 3 or img.shape[2] != 3:
                    log("  -> SKIPPED (not a 3-channel RGB array: shape=" + repr(getattr(img, "shape", None)) + ")")
                    channel_results[channel_kind].append({
                        "image": iname,
                        "kind": channel_kind,
                        "status": "SKIPPED",
                        "reason": "dataset image is not a 3-channel RGB array",
                        "perfect": False,
                        "bit_acc": None,
                        "recovered_exact": False,
                        "payload_exact": False,
                        "time_s": 0.0,
                    })
                    continue
            rec = run_single_image(
                method="cnn",
                channel_kind=channel_kind,
                image_name=iname,
                image=img,
                model=model,
                patch_size=patch,
                device="cpu",
            )
            channel_results[channel_kind].append(rec)
            log(
                f"  -> status={rec['status']} perfect={rec['perfect']} bit_acc={rec['bit_acc']} "
                f"exact={rec['recovered_exact']} payload_exact={rec['payload_exact']} "
                f"time={rec['time_s']}s"
            )
            if rec["status"] != "PASS":
                if rec["error"]:
                    log(f"     error: {rec['error']}")
        log("")

    overall_status = compute_overall_status(channel_results)

    return {
        "tag": tag,
        "checkpoint": pth.name,
        "architecture": {
            "patch": patch,
            "residual": residual,
            "nparams": nparams,
            "expected": {
                "patch": variant["expected_patch"],
                "residual": variant["expected_residual"],
            },
        },
        "images": {
            "gray": [n for n, _ in gray_images],
            "color": [n for n, _ in color_images],
        },
        "results": channel_results,
        "overall_status": overall_status,
        "log_lines": log_lines,
        "load_time_s": round(load_elapsed, 3),
        "variant_wall_time_s": None,  # filled by caller
        "notes": variant_notes(tag),
    }


def variant_failure(
    tag: str,
    checkpoint: str,
    patch: Any,
    residual: Any,
    results: Any,
    channel_results: Any,
    load_error: Any,
    log_lines: Any,
) -> Dict[str, Any]:
    return {
        "tag": tag,
        "checkpoint": checkpoint,
        "architecture": {"patch": patch, "residual": residual, "nparams": None, "expected": None},
        "images": {"gray": [], "color": []},
        "results": {},
        "overall_status": "FAIL",
        "log_lines": log_lines,
        "load_error": load_error,
        "variant_wall_time_s": None,
        "notes": variant_notes(tag),
    }


def compute_overall_status(channel_results: Dict[str, List[Dict[str, Any]]]) -> str:
    """Variant-level status.

    PASS  - every attempted image in every required channel is PASS.
    FAIL  - at least one attempted image is FAIL/TIMEOUT/ERROR.
    PARTIAL - some required channel/image was not attempted but for a
              documented non-implementation reason (for example the dataset
              does not provide a 3-channel RGB image for the color channel).
    """
    attempts: List[str] = []
    skips: List[str] = []
    failures: List[str] = []

    for kind, recs in channel_results.items():
        if not recs:
            attempts.append(f"{kind}: no results")
            continue
        for r in recs:
            s = r.get("status")
            if s == "SKIPPED":
                skips.append(f"{kind}/{r['image']}: {r.get('reason','skipped')}")
            elif s == "PASS":
                continue
            else:
                failures.append(f"{kind}/{r['image']}: {s}")

    if failures:
        return "FAIL"
    if skips:
        return "PARTIAL"
    return "PASS"


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
def main() -> None:
    sys.path.insert(0, str(PROJECT))

    np.random.seed(0)
    torch.manual_seed(0)

    manifest_info = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT),
        "gray_dir": str(GRAY_DIR),
        "color_dir": str(COLOR_DIR),
        "models_dir": str(MODELS_DIR),
        "model_dir_alt_present": bool(_MODELS_DIR_ALT and _MODELS_DIR_ALT.exists()),
        "variants": [v["tag"] for v in VARIANTS],
        "per_variant_timeout_s": PER_VARIANT_TIMEOUT_S,
        "per_image_timeout_s": PER_IMAGE_TIMEOUT_S,
        "method": "cnn",
        "payload_config": "deterministic seed=42 per image; payload length = pipeline capacity for that image",
        "exact_checks": ["recovered == original image", "extracted == embedded payload"],
        "model_dir": str(MODELS_DIR),
        "constraints": [
            "No model checkpoint written/overwritten/retrained.",
            "Existing raw results / tables / figures / logs untouched.",
            "Bounded execution per variant with per-variant log.",
            "Any hang/failure diagnosed and documented; never silently PASS.",
        ],
    }

    all_results: List[Dict[str, Any]] = []
    regen_log_path = OUT / "final_verification.log"
    report_log_handle = None
    try:
        report_log_handle = open(regen_log_path, "w", encoding="utf-8")
        report_log_handle.write(f"FINAL VERIFICATION LOG\n")
        report_log_handle.write(f"started_utc: {manifest_info['started_utc']}\n")
        report_log_handle.write(f"project_root: {manifest_info['project_root']}\n\n")

        for v in VARIANTS:
            pth = MODELS_DIR / v["rel"]
            if not pth.exists():
                entry = {
                    "tag": v["tag"],
                    "checkpoint": v["rel"],
                    "overall_status": "NOT RUN",
                    "log_lines": [
                        "Checkpoint missing at expected path: " + str(MODELS_DIR / v['rel']),
                    ],
                    "load_error": "missing " + str(MODELS_DIR / v['rel']),
                }
                all_results.append(entry)
                continue

            start = time.time()
            variant_started = time.time()
            try:
                signal.alarm(PER_VARIANT_TIMEOUT_S)
                entry = run_variant(v)
                signal.alarm(0)
            except RunnerTimeout:
                entry = {
                    "tag": v["tag"],
                    "checkpoint": v["rel"],
                    "overall_status": "BLOCKED",
                    "log_lines": [
                        f"Variant wall-clock timeout after {PER_VARIANT_TIMEOUT_S}s.",
                        "Last partial log:",
                    ] + traceback.format_stack(),
                }
            except Exception:
                entry = {
                    "tag": v["tag"],
                    "checkpoint": v["rel"],
                    "overall_status": "FAIL",
                    "log_lines": [traceback.format_exc()],
                }
            finally:
                try:
                    signal.alarm(0)
                except Exception:
                    pass

            entry["variant_wall_time_s"] = round(time.time() - variant_started, 3)
            all_results.append(entry)

            # Write per-variant log immediately so a later crash still leaves the
            # per-variant artifact.
            variant_log = OUT / f"variant_{v['tag']}.log"
            variant_log.write_text("\n".join(entry.get("log_lines", [])) + "\n", encoding="utf-8")

            # Mirror into the consolidated log.
            report_log_handle.write("\n".join(["=" * 70, f"VARIANT: {v['tag']}", "=" * 70] + entry.get("log_lines", []) + [""]))
            report_log_handle.flush()

        manifest_info["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest_info["exit_reason"] = "completed"

    except Exception:
        manifest_info["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest_info["exit_reason"] = "interrupted"
        manifest_info["exception"] = traceback.format_exc()
        raise
    finally:
        if report_log_handle is not None:
            report_log_handle.close()

    # Summary JSON + CSV-style summary for the report.
    summary_rows = []
    for entry in all_results:
        recs = entry.get("results", {})
        g_recs = recs.get("gray", [])
        c_recs = recs.get("color", [])
        g_pass = sum(1 for r in g_recs if r.get("status") == "PASS")
        c_pass = sum(1 for r in c_recs if r.get("status") == "PASS")
        g_total = len(g_recs)
        c_total = len(c_recs)
        summary_rows.append({
            "variant": entry.get("tag", "?"),
            "checkpoint": entry.get("checkpoint", "?"),
            "overall_status": entry.get("overall_status", "NOT RUN"),
            "notes": entry.get("notes", ""),
            "architecture": entry.get("architecture"),
            "gray_pass": g_pass,
            "gray_total": g_total,
            "color_pass": c_pass,
            "color_total": c_total,
            "variant_wall_time_s": entry.get("variant_wall_time_s"),
            "load_error": (entry.get("load_error") or ""),
        })

    summary_path = OUT / "final_verification_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump({
            "manifest": manifest_info,
            "summary": summary_rows,
            "entries": all_results,
        }, f, indent=2, default=str)

    csv_path = OUT / "final_verification_summary.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("variant,checkpoint,overall_status,notes,patch,residual,nparams,gray_pass,gray_total,color_pass,color_total,variant_wall_time_s,load_error\n")
        for s in summary_rows:
            arch = s["architecture"] or {}
            patch = arch.get("patch", "")
            residual = arch.get("residual", "")
            nparams = arch.get("nparams", "")
            err = (s.get("load_error") or "").replace("\n", " ")
            f.write(
                f"{s['variant']},{s['checkpoint']},{s['overall_status']},{s['notes']},"
                f"{patch},{residual},{nparams},{s['gray_pass']},{s['gray_total']},"
                f"{s['color_pass']},{s['color_total']},{s['variant_wall_time_s']},{err}\n"
            )

    # Console summary with preserved exit semantics.
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 70)
    for s in summary_rows:
        print(
            f"{s['variant']:20s} [{s['overall_status']:8s}] "
            f"gray={s['gray_pass']}/{s['gray_total']} color={s['color_pass']}/{s['color_total']} "
            f"time={s['variant_wall_time_s']}s"
            + (f" load_error={s['load_error']}" if s.get("load_error") else "")
        )
    print("=" * 70)

    statuses = [s["overall_status"] for s in summary_rows]
    any_fail = any(st in {"FAIL", "BLOCKED"} for st in statuses)
    any_not_run = any(st == "NOT RUN" for st in statuses)

    print("\nArtifacts:")
    print(f"  {regen_log_path}")
    print(f"  {OUT / 'variant_v1_full.log'}")
    print(f"  {OUT / 'variant_v2_no_residual.log'}")
    print(f"  {OUT / 'variant_v3_no_weighted_loss.log'}")
    print(f"  {OUT / 'variant_v4_patch3.log'}")
    print(f"  {OUT / 'variant_v5_patch7.log'}")
    print(f"  {summary_path}")
    print(f"  {csv_path}")

    if any_fail:
        print("\nOVERALL: FAIL — at least one variant failed or was blocked.")
        sys.exit(1)
    if any_not_run:
        print("\nOVERALL: PARTIAL — at least one variant was NOT RUN.")
        sys.exit(2)
    print("\nOVERALL: PASS — all variants produced PASS-level full-pipeline results.")
    sys.exit(0)


if __name__ == "__main__":
    main()
