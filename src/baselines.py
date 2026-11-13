import numpy as np


def med_predict(image: np.ndarray) -> np.ndarray:
    """Median Edge Detection — 3 causal neighbours."""
    img  = image.astype(np.int32)
    h, w = img.shape
    pred = np.zeros((h, w), dtype=np.float32)

    N  = img[:-1, 1:]    # top
    W  = img[1:,  :-1]   # left
    NW = img[:-1, :-1]   # top-left

    lo = np.minimum(N, W)
    hi = np.maximum(N, W)
    p  = np.where(NW >= hi, lo,
         np.where(NW <= lo, hi, N + W - NW))
    pred[1:, 1:] = p
    return pred


def gap_predict(image: np.ndarray) -> np.ndarray:
    """
    Gradient Adjusted Predictor (Wu & Memon 1997).
    Vectorised — pads right and bottom so NE is always valid.
    """
    img  = image.astype(np.float32)
    h, w = img.shape

    # pad: 2 top, 2 left, 0 bottom, 1 right  (for NE access)
    p = np.pad(img, ((2, 0), (2, 1)), mode="edge")

    # causal neighbours at every interior position
    N   = p[1:-1, 2:-1]   # (h,w)
    W   = p[2:,   1:-2]
    NW  = p[1:-1, 1:-2]
    NE  = p[1:-1, 3:]
    WW  = p[2:,   :-3]
    NN  = p[:-2,  2:-1]
    NNE = p[:-2,  3:]

    dh = np.abs(W - WW) + np.abs(N - NW) + np.abs(NE - N)
    dv = np.abs(N - NN) + np.abs(W - NW) + np.abs(NNE - NE)

    base  = (N + W) / 2.0 + (NE - NW) / 4.0
    p_hat = np.where(dv - dh > 80,  W,
            np.where(dh - dv > 80,  N,
            np.where(dv - dh > 32,  (base + W) / 2.0,
            np.where(dh - dv > 32,  (base + N) / 2.0,
            np.where(dv - dh > 8,   (3*base + W) / 4.0,
            np.where(dh - dv > 8,   (3*base + N) / 4.0,
                                     base))))))

    pred         = np.zeros((h, w), dtype=np.float32)
    pred[1:, 1:] = np.clip(p_hat[1:, 1:], 0, 255)
    return pred


def calic_predict(image: np.ndarray) -> np.ndarray:
    """
    Simplified CALIC predictor (Wu & Memon 1997).
    Vectorised — pads generously so all neighbours are valid.
    """
    img  = image.astype(np.float32)
    h, w = img.shape

    # pad: 2 top, 2 left, 0 bottom, 1 right
    p = np.pad(img, ((2, 0), (2, 1)), mode="edge")

    N   = p[1:-1, 2:-1]
    W   = p[2:,   1:-2]
    NW  = p[1:-1, 1:-2]
    NE  = p[1:-1, 3:]
    WW  = p[2:,   :-3]
    NN  = p[:-2,  2:-1]
    NNE = p[:-2,  3:]
    NNW = p[:-2,  1:-2]

    dh = np.abs(W - WW) + np.abs(N - NW) + np.abs(NE - N)
    dv = np.abs(N - NN) + np.abs(W - NW) + np.abs(NNE - NE)

    horiz  = N + (W - NW) / 2.0
    vert   = W + (N - NW) / 2.0
    smooth = (N + W) / 2.0 + (NE - NW) / 8.0 + (NN - NNW) / 8.0

    p_hat = np.where(dh > dv, horiz,
            np.where(dv > dh, vert, smooth))

    pred         = np.zeros((h, w), dtype=np.float32)
    pred[1:, 1:] = np.clip(p_hat[1:, 1:], 0, 255)
    return pred


def med_pee_run(image: np.ndarray, key: bytes,
                nonce: int = 0, seed: int = 42) -> dict:
    """MED baseline: full RDHEI pipeline using MED predictor."""
    from src.rdhei_core import run_rdhei
    return run_rdhei(image, key, nonce=nonce,
                     method="med", model=None, device="cpu", seed=seed)