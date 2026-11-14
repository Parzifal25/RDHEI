"""Reproducible lightweight-CNN training with image-level validation splits."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from bisect import bisect_right
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from src.cnn_model import build_model, save_model

SUPPORTED = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pgm"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class WeightedL1Loss(nn.Module):
    """Weighted absolute error; a surrogate, not a proof of capacity optimality."""
    def __init__(self, alpha: float = 2.0):
        super().__init__()
        if alpha < 0:
            raise ValueError("alpha must be nonnegative")
        self.alpha = float(alpha)

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        error = torch.abs(pred - target)
        return ((1.0 + self.alpha * error / 255.0) * error).mean()


def load_native_gray_images(directory: str):
    """Load only native uint8 grayscale files; never silently convert RGB inputs."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"training directory does not exist: {root}")
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) != 1 or image.mode != "L":
                raise ValueError(f"expected single-frame native grayscale mode L: {path}")
            array = np.asarray(image)
        if array.dtype != np.uint8 or array.ndim != 2 or min(array.shape) < 3:
            raise ValueError(f"expected 2D uint8 grayscale image at least 3x3: {path}")
        digest_obj = hashlib.sha256()
        digest_obj.update(str(tuple(array.shape)).encode("ascii"))
        digest_obj.update(b"|uint8|")
        digest_obj.update(array.tobytes(order="C"))
        digest = digest_obj.hexdigest()
        records.append((path, np.ascontiguousarray(array), digest))
    if not records:
        raise FileNotFoundError(f"no native grayscale images found recursively under {root}")
    return records


def split_by_source_image(records, validation_fraction: float, seed: int):
    """Split source images before extracting or augmenting any patches."""
    if len(records) < 2:
        raise ValueError("at least two distinct source images are required")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    order = np.random.default_rng(seed).permutation(len(records)).tolist()
    n_val = min(len(records) - 1, max(1, int(round(len(records) * validation_fraction))))
    val_ids = set(order[:n_val])
    return (
        [records[i] for i in range(len(records)) if i not in val_ids],
        [records[i] for i in range(len(records)) if i in val_ids],
    )


class LazyPatchDataset(Dataset):
    """Extract patches lazily; training flips are variants of training images only."""
    def __init__(self, images, patch_size: int, stride: int, augment: bool):
        if patch_size not in (3, 5, 7) or stride < 1:
            raise ValueError("patch_size must be 3/5/7 and stride must be positive")
        self.patch_size = patch_size
        self.radius = patch_size // 2
        self.variants = []
        self.cumulative = []
        total = 0
        for image in images:
            h, w = image.shape
            padded = np.pad(image.astype(np.float32) / 255.0, self.radius, mode="reflect")
            ny, nx = (h + stride - 1) // stride, (w + stride - 1) // stride
            views = [padded]
            if augment:
                views.extend((padded[:, ::-1], padded[::-1, :]))
            for view in views:
                self.variants.append((view, h, w, nx, stride))
                total += ny * nx
                self.cumulative.append(total)
        self.stride = stride
        self.total = total

    def __len__(self):
        return self.total

    def __getitem__(self, index):
        if not 0 <= index < self.total:
            raise IndexError(index)
        variant = bisect_right(self.cumulative, index)
        previous = 0 if variant == 0 else self.cumulative[variant - 1]
        view, h, w, nx, stride = self.variants[variant]
        local = index - previous
        yi, xi = divmod(local, nx)
        y, x = yi * stride, xi * stride
        r = self.radius
        patch = view[y:y + self.patch_size, x:x + self.patch_size].copy()
        target = float(patch[r, r] * 255.0)
        patch[r, r] = 0.0
        return torch.from_numpy(patch).unsqueeze(0), torch.tensor(target, dtype=torch.float32)


def train_cnn(
    train_dir="data/train", model_path="models/edr2_cnn3x3.pth",
    epochs=20, batch_size=256, lr=1e-4, stride=4, patch_size=3,
    device_str="cpu", seed=42, validation_fraction=0.1, num_workers=0,
):
    if epochs < 1 or batch_size < 1 or lr <= 0 or num_workers < 0:
        raise ValueError("invalid epochs, batch size, learning rate, or worker count")
    set_seed(seed)
    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device_str == "auto" else torch.device(device_str)
    )
    records = load_native_gray_images(train_dir)
    train_records, val_records = split_by_source_image(records, validation_fraction, seed)
    train_ds = LazyPatchDataset([r[1] for r in train_records], patch_size, stride, augment=True)
    val_ds = LazyPatchDataset([r[1] for r in val_records], patch_size, stride, augment=False)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=device.type == "cuda",
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=device.type == "cuda",
    )

    # Explicit kwargs fix the old positional bug: build_model("cpu") assigned
    # "cpu" to patch_size and failed its architecture assertion.
    model = build_model(patch_size=patch_size, residual=True, device=str(device))
    criterion = WeightedL1Loss(alpha=2.0)
    val_criterion = nn.L1Loss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    best_val = float("inf")
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        sum_loss = seen = 0
        for patches, targets in train_loader:
            patches = patches.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True).unsqueeze(1)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(patches), targets)
            loss.backward()
            optimizer.step()
            sum_loss += float(loss.item()) * len(patches)
            seen += len(patches)
        train_loss = sum_loss / max(1, seen)

        model.eval()
        val_sum = val_seen = 0
        with torch.inference_mode():
            for patches, targets in val_loader:
                patches = patches.to(device, non_blocking=True)
                targets = targets.to(device, non_blocking=True).unsqueeze(1)
                loss = val_criterion(model(patches), targets)
                val_sum += float(loss.item()) * len(patches)
                val_seen += len(patches)
        val_mae = val_sum / max(1, val_seen)
        scheduler.step()
        improved = val_mae < best_val
        if improved:
            best_val = val_mae
            save_model(model, model_path)
        row = {
            "epoch": epoch, "train_weighted_l1": train_loss,
            "validation_mae": val_mae,
            "learning_rate_next_epoch": scheduler.get_last_lr()[0],
            "best_checkpoint": improved,
        }
        history.append(row)
        print(
            f"Epoch {epoch:02d}/{epochs} | weighted L1={train_loss:.6f} "
            f"| image-held-out MAE={val_mae:.6f} | LR={scheduler.get_last_lr()[0]:.3e}",
            flush=True,
        )

    manifest = {
        "architecture": {"patch_size": patch_size, "channels": 32, "residual": True},
        "training": {
            "epochs": epochs, "batch_size": batch_size, "learning_rate": lr,
            "optimizer": "Adam", "weight_decay": 1e-4,
            "scheduler": "CosineAnnealingLR", "scheduler_eta_min": 1e-6,
            "loss": "WeightedL1(alpha=2.0)", "patch_stride": stride, "seed": seed,
            "validation_fraction_by_source_image": validation_fraction,
            "augmentation": ["horizontal_flip", "vertical_flip"],
        },
        "dataset": {
            "directory": str(Path(train_dir).resolve()),
            "image_count": len(records),
            "train_files": [str(r[0]) for r in train_records],
            "validation_files": [str(r[0]) for r in val_records],
            "image_sha256": {str(r[0]): r[2] for r in records},
        },
        "results": {"best_validation_mae": best_val, "history": history},
        "note": "Weighted L1 is a surrogate; actual capacity must be measured by EDR2 net-bpp experiments.",
    }
    manifest_path = Path(str(model_path) + ".training.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Best image-held-out validation MAE: {best_val:.6f}")
    print(f"Checkpoint: {model_path}")
    print(f"Manifest: {manifest_path}")
    return model_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", default="data/train")
    parser.add_argument("--model-path", default="models/edr2_cnn3x3.pth")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--patch-size", type=int, choices=(3, 5, 7), default=3)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--num-workers", type=int, default=0)
    a = parser.parse_args()
    train_cnn(
        train_dir=a.train_dir, model_path=a.model_path, epochs=a.epochs,
        batch_size=a.batch_size, lr=a.learning_rate, stride=a.stride,
        patch_size=a.patch_size, device_str=a.device, seed=a.seed,
        validation_fraction=a.validation_fraction, num_workers=a.num_workers,
    )


if __name__ == "__main__":
    main()
