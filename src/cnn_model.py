import os
import torch
import torch.nn as nn


class CNNPredictor(nn.Module):
    """
    Lightweight CNN Predictor

    Supports:
        - 3×3
        - 5×5
        - 7×7
        - Residual ON/OFF
    """

    def __init__(
            self,
            patch_size=5,
            residual=True,
            channels=32
    ):
        super().__init__()

        assert patch_size in [3, 5, 7]

        self.patch_size = patch_size
        self.residual = residual

        self.conv1 = nn.Sequential(
            nn.Conv2d(1, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True)
        )

        self.conv2 = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True)
        )

        if residual:
            self.res = nn.Conv2d(
                1,
                channels,
                kernel_size=1
            )

        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(
                channels * patch_size * patch_size,
                128
            ),
            nn.ReLU(inplace=True),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, x):

        out = self.conv1(x)
        out = self.conv2(out)

        if self.residual:
            out = out + self.res(x)

        out = self.head(out)

        return out * 255.0


# ----------------------------------------------------------
# Factory
# ----------------------------------------------------------

def build_model(
        patch_size=5,
        residual=True,
        device="cpu"
):
    model = CNNPredictor(
        patch_size=patch_size,
        residual=residual
    )

    return model.to(device)


# ----------------------------------------------------------
# Load
# ----------------------------------------------------------

import math


def _clean_state_dict(obj):
    """
    Accept either a bare state_dict or a checkpoint dict, and strip prefixes
    left by torch.compile (_orig_mod.) or DataParallel (module.).
    """
    if isinstance(obj, dict) and "head.1.weight" not in obj:
        for k in ("state_dict", "model_state_dict", "model", "net"):
            if k in obj and isinstance(obj[k], dict):
                obj = obj[k]
                break
    cleaned = {}
    for k, v in obj.items():
        nk = k
        for pre in ("_orig_mod.", "module."):
            if nk.startswith(pre):
                nk = nk[len(pre):]
        cleaned[nk] = v
    return cleaned


def _infer_config(state_dict):
    """Recover (patch, residual) from a state_dict's shapes/keys."""
    in_dim = state_dict["head.1.weight"].shape[1]      # 32 * P * P
    patch = int(round(math.sqrt(in_dim / 32)))
    if 32 * patch * patch != in_dim:
        raise ValueError(f"Unexpected head input dim {in_dim}; cannot infer patch size.")
    residual = "res.weight" in state_dict
    return patch, residual


def load_model(
        path,
        patch_size=None,
        residual=None,
        device="cpu"
):
    state = torch.load(
        path,
        map_location=device
    )

    state = _clean_state_dict(state)

    # Infer architecture from state_dict if not explicitly provided
    if patch_size is None or residual is None:
        inferred_patch, inferred_residual = _infer_config(state)
        if patch_size is None:
            patch_size = inferred_patch
        if residual is None:
            residual = inferred_residual

    model = build_model(
        patch_size=patch_size,
        residual=residual,
        device=device
    )

    model.load_state_dict(state)
    model.eval()

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Loaded model: {path}")
    print(f"  Patch size: {patch_size}x{patch_size}  |  Residual: {residual}  |  Params: {n_params:,}")

    return model, patch_size, residual, n_params


# ----------------------------------------------------------
# Save
# ----------------------------------------------------------

def save_model(model, path):

    os.makedirs(
        os.path.dirname(path) or ".",
        exist_ok=True
    )

    torch.save(
        model.state_dict(),
        path
    )


# ----------------------------------------------------------
# Utilities
# ----------------------------------------------------------

def count_parameters(model):

    return sum(
        p.numel()
        for p in model.parameters()
        if p.requires_grad
    )


# ----------------------------------------------------------
# Test
# ----------------------------------------------------------

if __name__ == "__main__":

    variants = [

        ("3x3", 3, True),

        ("5x5", 5, True),

        ("No Residual", 5, False),

        ("7x7", 7, True),

    ]

    print()

    for name, patch, res in variants:

        model = build_model(
            patch_size=patch,
            residual=res
        )

        params = count_parameters(model)

        print(
            f"{name:15s}"
            f"{params:,} parameters"
        )