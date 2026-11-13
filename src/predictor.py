import numpy as np
import torch


def cnn_predict_map(
        image: np.ndarray,
        model,
        device: str = "cpu",
        patch_size: int = None,
        batch_size: int = 2048
):
    """
    Generate CNN prediction map.

    Parameters
    ----------
    image : ndarray
        Input grayscale image.

    model : CNNPredictor
        Trained CNN model.

    device : str
        cpu / cuda

    patch_size : int, optional
        CNN patch size: 3, 5 or 7.
        If None, automatically uses the patch size stored
        in the trained model.

    batch_size : int
        CNN inference batch size.

    Returns
    -------
    pred_map : ndarray
        Prediction map in [0,255] / normalized model output range.
    """

    # ------------------------------------------------------
    # Automatically determine patch size from model
    # ------------------------------------------------------
    if patch_size is None:
        patch_size = getattr(model, "patch_size", None)

        if patch_size is None:
            raise ValueError(
                "patch_size was not provided and could not be "
                "determined from the model."
            )

    # Convert to Python int in case it is a NumPy/PyTorch scalar
    patch_size = int(patch_size)

    # Validate patch size
    if patch_size not in [3, 5, 7]:
        raise ValueError(
            f"patch_size must be 3, 5 or 7, got {patch_size}."
        )

    HALF = patch_size // 2

    h, w = image.shape

    # ------------------------------------------------------
    # Normalize image and pad
    # ------------------------------------------------------
    padded = np.pad(
        image.astype(np.float32) / 255.0,
        HALF,
        mode="reflect"
    )

    # ------------------------------------------------------
    # Extract masked patches
    # ------------------------------------------------------
    patches = []

    for y in range(h):

        for x in range(w):

            patch = padded[
                y:y + patch_size,
                x:x + patch_size
            ].copy()

            # Mask centre pixel
            patch[HALF, HALF] = 0.0

            patches.append(patch)

    patches = np.asarray(
        patches,
        dtype=np.float32
    )

    # Add channel dimension
    # [N, H, W] -> [N, 1, H, W]
    patches = patches[:, np.newaxis]

    # ------------------------------------------------------
    # Prediction
    # ------------------------------------------------------
    preds = np.zeros(
        h * w,
        dtype=np.float32
    )

    model.eval()

    with torch.no_grad():

        for start in range(0, h * w, batch_size):

            end = min(
                start + batch_size,
                h * w
            )

            batch = torch.from_numpy(
                patches[start:end]
            ).to(device)

            output = model(batch)

            preds[start:end] = (
                output
                .squeeze(1)
                .cpu()
                .numpy()
            )

    # ------------------------------------------------------
    # Restore image dimensions
    # ------------------------------------------------------
    return preds.reshape(h, w)


def med_predict_map(image: np.ndarray):
    """
    Vectorized MED prediction.
    """

    img = image.astype(np.float32)

    padded = np.pad(
        img,
        ((1, 0), (1, 0)),
        mode="edge"
    )

    A = padded[1:, :-1]
    B = padded[:-1, 1:]
    C = padded[:-1, :-1]

    pred = np.where(
        C >= np.maximum(A, B),
        np.minimum(A, B),
        np.where(
            C <= np.minimum(A, B),
            np.maximum(A, B),
            A + B - C
        )
    )

    return pred


# ----------------------------------------------------------
# Backward Compatibility
# ----------------------------------------------------------

cnn_predict = cnn_predict_map