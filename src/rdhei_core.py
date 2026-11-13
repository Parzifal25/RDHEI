import numpy as np
from src.encryption import encrypt_image, decrypt_image
from src.metrics import evaluate_all


# ── Prediction ────────────────────────────────────────────────────────────

def med_predict(image: np.ndarray) -> np.ndarray:
    img = image.astype(np.float32)

    padded = np.pad(
        img,
        ((1, 0), (1, 0)),
        mode="edge"
    )

    A = padded[1:, :-1]
    B = padded[:-1, 1:]
    C = padded[:-1, :-1]

    return np.where(
        C >= np.maximum(A, B),
        np.minimum(A, B),
        np.where(
            C <= np.minimum(A, B),
            np.maximum(A, B),
            A + B - C
        )
    )


def cnn_predict(
        image: np.ndarray,
        model,
        device: str = "cpu",
        patch_size: int = None
) -> np.ndarray:
    """
    Generate CNN prediction map.

    If patch_size is not explicitly supplied, the patch size is
    automatically obtained from the trained model.
    """

    from src.predictor import cnn_predict_map

    # Automatically use the patch size belonging to the model.
    if patch_size is None:
        patch_size = getattr(model, "patch_size", None)

        if patch_size is None:
            raise ValueError(
                "CNN patch size could not be determined from the model. "
                "Pass patch_size explicitly."
            )

    return cnn_predict_map(
        image,
        model,
        device=device,
        patch_size=int(patch_size)
    )


# ── Label Map ─────────────────────────────────────────────────────────────

def _compute_bpp_and_range(e_abs: int):
    """
    For a given |e|, compute (bpp, min_e, max_e):

      bpp    = number of MSBs to replace
      min_e, max_e = valid |e| range for unique recovery
    """

    bpp = 0

    for r in range(7, 0, -1):

        low = 2 ** (r - 1) - 1
        mid = 2 ** (r - 1)
        high = 2 ** r - 1

        if e_abs <= low:
            bpp += 1

        elif e_abs > mid and e_abs <= high:
            bpp += 1

            return (
                bpp,
                2 ** (r - 1) + 1,
                2 ** r - 1
            )

        elif e_abs == mid:
            return (
                bpp,
                mid,
                mid
            )

    return bpp, 0, 0


def generate_label_map(error_abs: np.ndarray):
    """
    Returns:
        bpp_map
        min_e_map
        max_e_map
    """

    h, w = error_abs.shape

    bpp_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    min_e_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    max_e_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    for y in range(h):

        for x in range(w):

            bpp, mn, mx = _compute_bpp_and_range(
                int(error_abs[y, x])
            )

            bpp_map[y, x] = bpp
            min_e_map[y, x] = mn
            max_e_map[y, x] = mx

    return (
        bpp_map,
        min_e_map,
        max_e_map
    )


def generate_label_map_fast(error_abs: np.ndarray):
    """
    Vectorised version of generate_label_map.
    """

    h, w = error_abs.shape

    bpp_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    min_e_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    max_e_map = np.zeros(
        (h, w),
        dtype=np.int32
    )

    active = error_abs < 128
    stopped = np.zeros(
        (h, w),
        dtype=bool
    )

    for r in range(7, 0, -1):

        low = 2 ** (r - 1) - 1
        mid = 2 ** (r - 1)
        high = 2 ** r - 1

        l0 = (
            active &
            (error_abs <= low)
        )

        l1 = (
            active &
            (error_abs > mid) &
            (error_abs <= high)
        )

        l2 = (
            active &
            (error_abs == mid)
        )

        bpp_map += (
            l0 | l1
        ).astype(np.int32)

        # l1 stop
        min_e_map = np.where(
            l1 & ~stopped,
            2 ** (r - 1) + 1,
            min_e_map
        )

        max_e_map = np.where(
            l1 & ~stopped,
            2 ** r - 1,
            max_e_map
        )

        stopped = stopped | l1

        # l2 stop
        min_e_map = np.where(
            l2 & ~stopped,
            mid,
            min_e_map
        )

        max_e_map = np.where(
            l2 & ~stopped,
            mid,
            max_e_map
        )

        stopped = stopped | l2

        active = l0.copy()

    # Remaining active pixels:
    # all label-0 cases where |e| = 0
    min_e_map = np.where(
        active,
        0,
        min_e_map
    )

    max_e_map = np.where(
        active,
        0,
        max_e_map
    )

    return (
        bpp_map,
        min_e_map,
        max_e_map
    )


# ── Pixel-level operations ────────────────────────────────────────────────

def _embed_pixel(
        pixel: int,
        n: int,
        payload_bits
) -> int:

    """Replace upper n MSBs with payload. Lower (8-n) unchanged."""

    if n == 0:
        return pixel

    n_lower = 8 - n

    lower_mask = (
        (1 << n_lower) - 1
    )

    lower = pixel & lower_mask

    upper = 0

    for i in range(n):

        upper |= (
            int(payload_bits[i])
            << (7 - i)
        )

    return (
        upper & ~lower_mask
    ) | lower


def _recover_pixel(
        stego_val: int,
        pred: int,
        n: int,
        min_e: int,
        max_e: int
) -> int:

    """
    Find unique combo of upper n bits such that
    |candidate - pred| is in [min_e, max_e].

    Lower (8-n) bits from stego_val are unchanged.
    """

    if n == 0:
        return stego_val

    n_lower = 8 - n

    lower_mask = (
        (1 << n_lower) - 1
    )

    lower = stego_val & lower_mask

    for combo in range(2 ** n):

        c = (
            combo << n_lower
        ) | lower

        if (
            0 <= c <= 255
            and
            min_e <= abs(c - pred) <= max_e
        ):
            return c

    return stego_val


# ══════════════════════════════════════════════════════════════════════════
# CONTENT OWNER — predict → embed → encrypt
# ══════════════════════════════════════════════════════════════════════════

def content_owner_prepare(
        image: np.ndarray,
        key: bytes,
        nonce: int = 0,
        method: str = "med",
        model=None,
        device: str = "cpu",
        patch_size: int = None
) -> dict:

    h, w = image.shape

    if method == "cnn" and model is not None:

        pred_map = cnn_predict(
            image,
            model,
            device=device,
            patch_size=patch_size
        )

    else:

        pred_map = med_predict(
            image
        ).astype(np.float32)

    pred_int = np.round(
        pred_map
    ).astype(np.int32)

    error_abs = np.abs(
        image.astype(np.int32) -
        pred_int
    )

    (
        bpp_map,
        min_e_map,
        max_e_map
    ) = generate_label_map_fast(
        error_abs
    )

    capacity = int(
        bpp_map.sum()
    )

    return {
        "image": image,
        "key": key,
        "nonce": nonce,
        "pred_int": pred_int,
        "bpp_map": bpp_map,
        "min_e_map": min_e_map,
        "max_e_map": max_e_map,
        "capacity": capacity,
        "bpp": capacity / (h * w),
        "method": method,
        "patch_size": patch_size
    }


def sender_embed_encrypt(
        co: dict,
        payload: np.ndarray
) -> np.ndarray:

    """Embed payload into plaintext via MSB replacement, then encrypt."""

    image = co["image"]
    bpp_map = co["bpp_map"]

    h, w = image.shape

    stego = image.flatten().astype(
        np.int32
    )

    bpp_flat = bpp_map.flatten()

    bit_idx = 0

    for i in range(h * w):

        n = int(
            bpp_flat[i]
        )

        if n == 0:
            continue

        bits = []

        for _ in range(n):

            bits.append(
                int(payload[bit_idx])
                if bit_idx < len(payload)
                else 0
            )

            if bit_idx < len(payload):
                bit_idx += 1

        stego[i] = _embed_pixel(
            int(stego[i]),
            n,
            bits
        )

    stego_plain = stego.reshape(
        h, w
    ).astype(np.uint8)

    return encrypt_image(
        stego_plain,
        co["key"],
        co["nonce"]
    )


# ══════════════════════════════════════════════════════════════════════════
# RECEIVER — decrypt → extract → recover
# ══════════════════════════════════════════════════════════════════════════

def receiver_extract_recover(
        stego_enc: np.ndarray,
        key: bytes,
        nonce: int,
        bpp_map: np.ndarray,
        min_e_map: np.ndarray,
        max_e_map: np.ndarray,
        pred_int: np.ndarray,
        payload_len: int
) -> dict:

    h, w = stego_enc.shape

    stego_plain = decrypt_image(
        stego_enc,
        key,
        nonce
    )

    sp_flat = stego_plain.flatten().astype(
        np.int32
    )

    pred_flat = pred_int.flatten()
    bpp_flat = bpp_map.flatten()
    min_flat = min_e_map.flatten()
    max_flat = max_e_map.flatten()

    extracted = []
    recovered = sp_flat.copy()

    for i in range(h * w):

        n = int(bpp_flat[i])
        sv = int(sp_flat[i])

        if n == 0:
            # No embedding occurred for this pixel; stego == original.
            recovered[i] = sv
            continue

        p = int(pred_flat[i])
        mn = int(min_flat[i])
        mx = int(max_flat[i])

        # Extract payload bits only up to payload_len, MSB-first order.
        # Once payload_len bits have been collected, stop extracting but keep
        # recovering every remaining pixel (recovery depends on sv/pred/range,
        # not on the payload bits).
        if len(extracted) < payload_len:
            for j in range(n):

                if len(extracted) >= payload_len:
                    break

                extracted.append(
                    (sv >> (7 - j)) & 1
                )

        # Recover every pixel independently of payload extraction.
        recovered[i] = _recover_pixel(
            sv,
            p,
            n,
            mn,
            mx
        )

    return {
        "extracted": np.array(
            extracted[:payload_len],
            dtype=np.uint8
        ),
        "recovered": recovered.reshape(
            h, w
        ).astype(np.uint8),
        "stego_plain": stego_plain
    }


# ══════════════════════════════════════════════════════════════════════════
# Full pipeline
# ══════════════════════════════════════════════════════════════════════════

def run_rdhei(
        image: np.ndarray,
        key: bytes,
        nonce: int = 0,
        method: str = "med",
        model=None,
        device: str = "cpu",
        patch_size: int = None,
        seed: int = 42
) -> dict:

    h, w = image.shape

    rng = np.random.RandomState(
        seed
    )

    co = content_owner_prepare(
        image=image,
        key=key,
        nonce=nonce,
        method=method,
        model=model,
        device=device,
        patch_size=patch_size
    )

    payload = rng.randint(
        0,
        2,
        size=co["capacity"],
        dtype=np.uint8
    )

    stego_enc = sender_embed_encrypt(
        co,
        payload
    )

    rx = receiver_extract_recover(
        stego_enc,
        key,
        nonce,
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        co["capacity"]
    )

    extracted = rx["extracted"]
    recovered = rx["recovered"]
    stego_plain = rx["stego_plain"]

    bit_acc = (
        float(
            np.mean(
                extracted == payload
            ) * 100
        )
        if co["capacity"] > 0
        else 0.0
    )

    perfect = bool(
        np.array_equal(
            image,
            recovered
        )
    )

    metrics = evaluate_all(
        image,
        stego_plain,
        co["capacity"]
    )

    metrics["bpp"] = co["bpp"]

    return {
        "method": method,
        "capacity": co["capacity"],
        "bpp": co["bpp"],
        "bit_acc": bit_acc,
        "perfect": perfect,
        "metrics": metrics,
        "encrypted": stego_enc,
        "stego_enc": stego_enc,
        "stego_plain": stego_plain,
        "recovered": recovered,
        "payload": payload,
        "extracted": extracted
    }