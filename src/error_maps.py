"""
==============================================================
Prediction Error Map Visualization
==============================================================

Generates Figure 3 of the paper.

Comparison

1. Original Image
2. MED Error Map
3. GAP Error Map
4. CALIC Error Map
5. CNN-3×3 (Proposed) Error Map

==============================================================
"""

import os
import warnings
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt

import torch

from baselines import (
    med_predict,
    gap_predict,
    calic_predict
)

from predictor import (
    cnn_predict_map
)

from cnn_model import (
    load_model
)

warnings.filterwarnings("ignore")


# ==========================================================
# Paths
# ==========================================================

RESULT_DIR = os.path.join(
    "results",
    "error_maps"
)

os.makedirs(
    RESULT_DIR,
    exist_ok=True)


# ==========================================================
# Utilities
# ==========================================================

def load_grayscale(path):

    path = str(path)

    image = cv2.imread(
        path,
        cv2.IMREAD_GRAYSCALE
    )

    if image is None:

        raise FileNotFoundError(
            f"Cannot read image:\n{path}"
        )

    return image


# ==========================================================
# Prediction Wrappers
# ==========================================================

def predict_med(image):

    return med_predict(image)


def predict_gap(image):

    return gap_predict(image)


def predict_calic(image):

    return calic_predict(image)


def predict_cnn(
        image,
        model_path,
        device="cpu"
):

    model = load_model(

        model_path,

        patch_size=3,

        residual=True,

        device=device

    )

    prediction = cnn_predict_map(

        image,

        model,

        device=device,

        patch_size=3

    )

    return prediction


# ==========================================================
# Prediction Error
# ==========================================================

def prediction_error(
        image,
        prediction
):
    """
    Signed prediction error.

    Error = Original − Prediction
    """

    return (

        image.astype(np.float32)

        -

        prediction.astype(np.float32)

    )


# ==========================================================
# Generate Error Maps
# ==========================================================

def compute_error_maps(
        image,
        model_path,
        device="cpu"
):

    print()

    print(
        "Generating prediction maps..."
    )

    med = predict_med(image)

    gap = predict_gap(image)

    calic = predict_calic(image)

    cnn = predict_cnn(
        image,
        model_path,
        device
    )

    errors = {

        "MED":
            prediction_error(
                image,
                med
            ),

        "GAP":
            prediction_error(
                image,
                gap
            ),

        "CALIC":
            prediction_error(
                image,
                calic
            ),

        "CNN-3×3 (Proposed)":
            prediction_error(
                image,
                cnn
            )

    }

    return errors

# ==========================================================
# Plot Figure 3
# ==========================================================

def plot_error_maps(
        image,
        errors
):
    """
    Generate Figure 3.

    Layout

           Original

    MED   GAP   CALIC   CNN-3×3

    All error maps share the
    same color scale.
    """

    # Shared color scale
    all_errors = np.concatenate([
        e.flatten()
        for e in errors.values()
    ])

    vmax = np.percentile(
        np.abs(all_errors),
        99
    )

    fig = plt.figure(
        figsize=(12, 6)
    )

    gs = fig.add_gridspec(
        2,
        4,
        height_ratios=[1, 1.2]
    )

    # ------------------------------------------------------
    # Original Image
    # ------------------------------------------------------

    ax0 = fig.add_subplot(gs[0, :])

    ax0.imshow(
        image,
        cmap="gray",
        vmin=0,
        vmax=255
    )

    ax0.set_title(
        "Original Image",
        fontsize=13,
        fontweight="bold"
    )

    ax0.axis("off")

    # ------------------------------------------------------
    # Error Maps
    # ------------------------------------------------------

    titles = list(errors.keys())

    ims = []

    for i, title in enumerate(titles):

        ax = fig.add_subplot(
            gs[1, i]
        )

        im = ax.imshow(

            errors[title],

            cmap="coolwarm",

            vmin=-vmax,

            vmax=vmax

        )

        ims.append(im)

        ax.set_title(

            title,

            fontsize=11,

            fontweight="bold"

        )

        ax.axis("off")

        # ----------------------------------------------
        # Save individual error maps
        # ----------------------------------------------

        plt.imsave(

            os.path.join(

                RESULT_DIR,

                title.replace(
                    " ",
                    "_"
                ).replace(
                    "×",
                    "x"
                ).replace(
                    "(",
                    ""
                ).replace(
                    ")",
                    ""
                ) + ".png"

            ),

            errors[title],

            cmap="coolwarm",

            vmin=-vmax,

            vmax=vmax

        )

    # ------------------------------------------------------
    # Shared Colorbar
    # ------------------------------------------------------

    cbar = fig.colorbar(

        ims[-1],

        ax=fig.axes,

        fraction=0.025,

        pad=0.02

    )

    cbar.set_label(

        "Prediction Error",

        fontsize=11

    )

    plt.suptitle(

        "Figure 3. Prediction Error Maps",

        fontsize=15,

        fontweight="bold"

    )

    plt.tight_layout()

    output = os.path.join(

        RESULT_DIR,

        "figure3_error_maps.png"

    )

    plt.savefig(

        output,

        dpi=300,

        bbox_inches="tight"

    )

    plt.close()

    print()

    print(

        f"Figure saved to:\n{output}"

    )


# ==========================================================
# Main
# ==========================================================

def main():

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    IMAGE_PATH = PROJECT_ROOT / "data" / "kodak_gray" / "Lena.png"

    MODEL_PATH = PROJECT_ROOT / "models_ablation" / "v4_patch3.pth"

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    print()

    print("=" * 70)

    print("Prediction Error Map Analysis")

    print("=" * 70)

    print()

    print(f"Image  : {IMAGE_PATH}")

    print(f"Model  : {MODEL_PATH}")

    print(f"Device : {DEVICE}")

    image = load_grayscale(

        str(IMAGE_PATH)

    )

    errors = compute_error_maps(

        image,

        str(MODEL_PATH),

        DEVICE

    )

    plot_error_maps(

        image,

        errors

    )

    print()

    print("=" * 70)

    print("Figure 3 generated successfully.")

    print("=" * 70)

    print()

    print(

        os.path.join(

            RESULT_DIR,

            "figure3_error_maps.png"

        )

    )


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()