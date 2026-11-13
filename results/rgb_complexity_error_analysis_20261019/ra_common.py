"""Shared helpers for the RGB complexity + error-distribution analysis (2026-10-19).

Conventions (matching the authoritative implementation, src/rdhei_core.py):
  signed prediction error  e = image - round(pred)      (image uint8, pred float)
  absolute error           e_abs = |e|
  capacity per pixel       n = bpp_map from generate_label_map_fast(e_abs)
  BPP (gray)               = sum(bpp_map) / (H*W)
  RGB BPP                  = arithmetic mean of the three per-channel BPPs
  prediction MAE           = mean |image - round(pred)|  (per channel for RGB)

Predictors:
  MED          src.baselines.med_predict      (causal; first row/col = 0)
  MED_pipeline src.rdhei_core.med_predict     (edge-padded; pipeline MED)
  GAP          src.baselines.gap_predict
  CALIC        src.baselines.calic_predict
  CNN3x3       src.rdhei_core.cnn_predict with models/v4_patch3.pth
  CNN variants use the other checkpoints (ablations).

Prediction maps are cached on disk (float32 .npy under cache/) because
CNN inference costs ~1.7 s per 512x512 channel on this CPU.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent          # project root (RDHEI_FIXED_V1)
sys.path.insert(0, str(ROOT))

GRAY_DIR = ROOT.parent / "data" / "kodak_gray"
COLOR_DIR = ROOT.parent / "data" / "kodak_color"
MODELS = ROOT / "models"
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)

GRAY_IMAGES = ["Airplane.png", "Baboon.png", "Goldhill.png", "Jetplane.png",
               "Lena.png", "Peppers.png"]
RGB_IMAGES = ["4.2.03.png", "4.2.05.png", "4.2.06.png", "4.2.07.png", "lena.png"]
CHANNELS = ["R", "G", "B"]

CNN_CHECKPOINTS = {
    "CNN3x3": ("v4_patch3.pth", 46881),
    "CNN5x5": ("v1_full.pth", 112417),
    "CNNNoResidual": ("v2_no_residual.pth", 112353),
    "CNNNoWeighted": ("v3_no_weighted_loss.pth", 112417),
    "CNN7x7": ("v5_patch7.pth", 210721),
}

CLASSICAL = ["MED", "MED_pipeline", "GAP", "CALIC"]

_MODEL_CACHE: dict = {}


def load_gray(name: str) -> np.ndarray:
    return np.array(Image.open(GRAY_DIR / name).convert("L"), dtype=np.uint8)


def load_rgb(name: str) -> np.ndarray:
    return np.array(Image.open(COLOR_DIR / name).convert("RGB"), dtype=np.uint8)


def get_model(variant: str):
    if variant not in _MODEL_CACHE:
        from src.cnn_model import load_model
        fname, _ = CNN_CHECKPOINTS[variant]
        model, patch, residual, n_params = load_model(str(MODELS / fname), device="cpu")
        _MODEL_CACHE[variant] = (model, patch, residual, n_params)
    return _MODEL_CACHE[variant]


def classical_predict(arr: np.ndarray, method: str) -> np.ndarray:
    from src.baselines import med_predict as med_base, gap_predict, calic_predict
    from src.rdhei_core import med_predict as med_pipe
    fns = {"MED": med_base, "MED_pipeline": med_pipe,
           "GAP": gap_predict, "CALIC": calic_predict}
    return fns[method](arr).astype(np.float32)


def predict(arr: np.ndarray, method: str) -> np.ndarray:
    """Return float32 prediction map; cached on disk."""
    h, w = arr.shape
    key = f"pred_{method}_{h}x{w}_{hash(arr.tobytes()) & 0xFFFFFFFF:08x}.npy"
    path = CACHE / key
    if path.exists():
        return np.load(path)
    if method in CNN_CHECKPOINTS:
        model, patch, _, _ = get_model(method)
        from src.rdhei_core import cnn_predict
        pred = cnn_predict(arr, model, device="cpu", patch_size=patch).astype(np.float32)
    else:
        pred = classical_predict(arr, method)
    np.save(path, pred)
    return pred


def error_maps(arr: np.ndarray, pred: np.ndarray):
    """Return (signed error int32, e_abs int32, pred_int int32) per convention."""
    pred_int = np.round(pred).astype(np.int32)
    signed = arr.astype(np.int32) - pred_int
    return signed, np.abs(signed), pred_int


def label_maps(e_abs: np.ndarray):
    from src.rdhei_core import generate_label_map_fast
    return generate_label_map_fast(e_abs)


def n_histogram(bpp_map: np.ndarray) -> dict:
    """Count of pixels assigned each n in 0..7."""
    counts = np.bincount(bpp_map.flatten(), minlength=8)
    return {n: int(counts[n]) for n in range(8)}


def channel_metrics(arr: np.ndarray, pred: np.ndarray) -> dict:
    """Per-channel MAE + label-map capacity from the actual implementation."""
    signed, e_abs, _ = error_maps(arr, pred)
    bpp_map, min_e, max_e = label_maps(e_abs)
    h, w = arr.shape
    cap = int(bpp_map.sum())
    return {
        "mae": float(np.abs(signed).mean()),
        "capacity_bits": cap,
        "bpp": cap / (h * w),
        "signed": signed, "e_abs": e_abs,
        "bpp_map": bpp_map, "min_e": min_e, "max_e": max_e,
    }
