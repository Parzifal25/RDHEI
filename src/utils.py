import os
import random
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# Image I/O
# ---------------------------------------------------------------------------

def load_image(path: str) -> np.ndarray:
    """Load image as 2D uint8 grayscale numpy array."""
    img = Image.open(path).convert("L")
    return np.array(img, dtype=np.uint8)


def save_image(array: np.ndarray, path: str):
    """Save 2D uint8 numpy array as grayscale PNG."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    Image.fromarray(array.astype(np.uint8), mode="L").save(path)


def load_images_from_dir(directory: str) -> list:
    """
    Load all grayscale images from a directory.
    Returns list of (filename, np.ndarray) tuples.
    """
    supported = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".pgm"}
    images = []
    for fname in sorted(os.listdir(directory)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in supported:
            path = os.path.join(directory, fname)
            img = load_image(path)
            images.append((fname, img))
    return images


# ---------------------------------------------------------------------------
# Patch Dataset for CNN Training
# ---------------------------------------------------------------------------

PATCH_SIZE = 5
HALF = PATCH_SIZE // 2


class PatchDataset(Dataset):
    """
    PyTorch Dataset of (patch, center_value) pairs for CNN training.
    Each sample: patch (1, 5, 5) float in [0,1], center pixel zeroed.
    Target:      center pixel value in [0, 255].
    """

    def __init__(self, images: list, stride: int = 1):
        """
        Args:
            images: list of 2D uint8 numpy arrays.
            stride: step size when sliding the patch window.
        """
        self.patches = []
        self.targets = []
        self._build(images, stride)

    def _build(self, images, stride):
        for img in images:
            h, w = img.shape
            padded = np.pad(img.astype(np.float32) / 255.0,
                            HALF, mode="reflect")
            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    patch = padded[y:y + PATCH_SIZE,
                                   x:x + PATCH_SIZE].copy()
                    center = patch[HALF, HALF]
                    patch[HALF, HALF] = 0.0          # mask center
                    self.patches.append(patch)
                    self.targets.append(center * 255.0)

    def __len__(self):
        return len(self.patches)

    def __getitem__(self, idx):
        patch = torch.tensor(self.patches[idx], dtype=torch.float32).unsqueeze(0)
        target = torch.tensor(self.targets[idx], dtype=torch.float32)
        return patch, target


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_seed(seed: int = 42):
    """Fix all random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def random_payload(n_bits: int, seed: int = 0) -> np.ndarray:
    """Generate a deterministic random binary payload."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=n_bits, dtype=np.uint8)


def payload_to_str(bits: np.ndarray) -> str:
    return "".join(str(b) for b in bits)