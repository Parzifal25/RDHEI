import os, torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split, Dataset
import numpy as np

from src.cnn_model import build_model, save_model
from src.utils     import load_images_from_dir, set_seed

PATCH = 5
HALF  = 2
SEED  = 42


# ── Weighted L1 Loss ──────────────────────────────────────────────────────

class WeightedL1Loss(nn.Module):
    """
    Weighted L1 loss that penalises larger prediction errors more.
    w(e) = 1 + alpha * |e| / 255
    This directly incentivises the CNN to drive errors toward 0,
    which maximises the number of pixels with small |e| and hence
    maximises embedding capacity (BPP).
    """
    def __init__(self, alpha: float = 2.0):
        super().__init__()
        self.alpha = alpha

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        err     = torch.abs(pred - target)
        weights = 1.0 + self.alpha * err / 255.0
        return (weights * err).mean()


# ── Patch Dataset ─────────────────────────────────────────────────────────

class PatchDataset(Dataset):
    """
    5×5 patch dataset for CNN training.
    Augmentation: horizontal flip + vertical flip.
    Supports .pgm and all other grayscale formats.
    """
    def __init__(self, images, stride: int = 4):
        self.patches = []
        self.targets = []
        self.stride  = stride
        for img in images:
            self._add(img)
            self._add(np.fliplr(img).copy())   # horizontal flip
            self._add(np.flipud(img).copy())   # vertical flip

    def _add(self, img):
        h, w   = img.shape
        padded = np.pad(img.astype(np.float32) / 255.0, HALF, mode='reflect')
        for y in range(0, h, self.stride):
            for x in range(0, w, self.stride):
                patch             = padded[y:y+PATCH, x:x+PATCH].copy()
                center            = patch[HALF, HALF]
                patch[HALF, HALF] = 0.0
                self.patches.append(patch)
                self.targets.append(center * 255.0)

    def __len__(self):
        return len(self.patches)

    def __getitem__(self, i):
        return (
            torch.tensor(self.patches[i], dtype=torch.float32).unsqueeze(0),
            torch.tensor(self.targets[i],  dtype=torch.float32)
        )


# ── Training function ─────────────────────────────────────────────────────

def train_cnn(train_dir   = "data/train",
              model_path  = "models/cnn_model.pth",
              epochs      = 20,
              batch_size  = 256,
              lr          = 1e-4,
              stride      = 4,
              device_str  = "cpu"):

    set_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu") \
             if device_str == "auto" else torch.device(device_str)

    # Load ALL images including .pgm (BOSSbase)
    raw = load_images_from_dir(train_dir)
    if not raw:
        raise FileNotFoundError(
            f"No images found in '{train_dir}'.\n"
            f"Copy your 200 BOSSbase .pgm files into that folder.")

    images = [img for _, img in raw]
    exts   = set(os.path.splitext(n)[1].lower() for n,_ in raw)
    print(f"[Train] Device   : {device}")
    print(f"[Train] Images   : {len(images)}  formats={exts}")
    print(f"[Train] Stride   : {stride}  Epochs: {epochs}  LR: {lr}")
    print(f"[Train] Loss     : WeightedL1 (alpha=2.0)  — penalises large errors")

    dataset          = PatchDataset(images, stride=stride)
    n_val            = max(1, int(len(dataset) * 0.1))
    n_train          = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])
    train_loader     = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader       = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)

    model     = build_model(str(device))
    criterion = WeightedL1Loss(alpha=2.0)
    val_crit  = nn.L1Loss()             # plain L1 for validation (comparable)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    # Cosine annealing — smooth LR decay, avoids StepLR's abrupt drops
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"[Train] Params   : {n_params:,}  |  Patches: {len(dataset):,}")
    print(f"[Train] Starting...\n")

    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    best_val = float("inf")

    for epoch in range(1, epochs + 1):
        # Training
        model.train()
        tloss = 0.0
        for patches, targets in train_loader:
            patches = patches.to(device)
            targets = targets.to(device).unsqueeze(1)
            optimizer.zero_grad()
            loss = criterion(model(patches), targets)
            loss.backward()
            optimizer.step()
            tloss += loss.item() * len(patches)
        tloss /= n_train

        # Validation (plain L1 for interpretability)
        model.eval()
        vloss = 0.0
        with torch.no_grad():
            for patches, targets in val_loader:
                vloss += val_crit(
                    model(patches.to(device)),
                    targets.to(device).unsqueeze(1)
                ).item() * len(patches)
        vloss /= n_val
        scheduler.step()

        marker = "  ← best ✓" if vloss < best_val else ""
        print(f"  Epoch [{epoch:2d}/{epochs}]  "
              f"Train Loss={tloss:.3f}  Val MAE={vloss:.3f}"
              f"  LR={scheduler.get_last_lr()[0]:.2e}{marker}")

        if vloss < best_val:
            best_val = vloss
            save_model(model, model_path)

    print(f"\n[Train] Done. Best Val MAE={best_val:.3f}")
    print(f"[Train] Model saved → {model_path}")
    return model_path