"""
==============================================================
Prediction Error Histogram Analysis
==============================================================

Generates Figure 4 of the paper.

Comparison:

1. MED
2. GAP
3. CALIC
4. CNN-3×3 (Proposed)

Output

results/
    histograms/
        prediction_error_histogram.png

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
    "histograms"
)

os.makedirs(
    RESULT_DIR,
    exist_ok=True
)


# ==========================================================
# Utilities
# ==========================================================

def load_grayscale(path):

    path = str(path)

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nImage not found:\n{path}"
        )

    image = cv2.imread(
        path,
        cv2.IMREAD_GRAYSCALE
    )

    if image is None:

        raise RuntimeError(
            f"OpenCV could not read:\n{path}"
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
    """
    CNN-3×3 prediction map.
    """

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
# Prediction Errors
# ==========================================================

def prediction_error(
        image,
        prediction
):
    """
    Signed prediction error.
    """

    return (

        image.astype(np.float32)

        -

        prediction.astype(np.float32)

    )


def absolute_error(
        image,
        prediction
):
    """
    Absolute prediction error.
    """

    return np.abs(

        prediction_error(

            image,

            prediction

        )

    )


# ==========================================================
# Flatten Histogram Data
# ==========================================================

def histogram_values(error):

    return error.flatten()


# ==========================================================
# Generate Prediction Errors
# ==========================================================

def compute_errors(
        image,
        model_path,
        device="cpu"
):
    """
    Compute prediction errors
    for all predictors.
    """

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

            histogram_values(

                prediction_error(
                    image,
                    med
                )
            ),

        "GAP":

            histogram_values(

                prediction_error(
                    image,
                    gap
                )
            ),

        "CALIC":

            histogram_values(

                prediction_error(
                    image,
                    calic
                )
            ),

        "CNN-3×3 (Proposed)":

            histogram_values(

                prediction_error(
                    image,
                    cnn
                )
            )

    }

    return errors

# ==========================================================
# Plot Histogram
# ==========================================================

def plot_histogram(errors):
    """
    Generate publication-quality prediction
    error histogram.
    """

    plt.figure(
        figsize=(10, 6)
    )

    colors = {

        "MED": "#1f77b4",

        "GAP": "#ff7f0e",

        "CALIC": "#2ca02c",

        "CNN-3×3 (Proposed)": "#d62728"

    }

    for method, values in errors.items():

        plt.hist(

            values,

            bins=201,

            range=(-50, 50),

            density=True,

            alpha=0.45,

            label=method,

            color=colors[method],

            linewidth=1.0,

            histtype="stepfilled"

        )

    plt.title(

        "Distribution of Prediction Errors"

    )

    plt.xlabel(

        "Prediction Error"

    )

    plt.ylabel(

        "Normalized Frequency"

    )

    plt.grid(

        True,

        linestyle="--",

        alpha=0.4

    )

    plt.legend()

    plt.tight_layout()

    output = os.path.join(

        RESULT_DIR,

        "prediction_error_histogram.png"

    )

    plt.savefig(

        output,

        dpi=300,

        bbox_inches="tight"

    )

    plt.close()

    print()

    print(

        f"Histogram saved to:\n{output}"

    )


# ==========================================================
# Statistics
# ==========================================================

def print_statistics(errors):

    print()

    print("=" * 70)

    print("Prediction Error Statistics")

    print("=" * 70)

    print()

    header = "{:<22s}{:>12s}{:>12s}{:>12s}{:>12s}"

    row = "{:<22s}{:>12.3f}{:>12.3f}{:>12.3f}{:>12.3f}"

    print(

        header.format(

            "Method",

            "Mean",

            "Median",

            "Std",

            "Max"

        )

    )

    print("-" * 70)

    for method, values in errors.items():

        print(

            row.format(

                method,

                np.mean(values),

                np.median(values),

                np.std(values),

                np.max(values)

            )

        )


# ==========================================================
# Main
# ==========================================================

def main():

    # ------------------------------------------------------
    # CHANGE THESE PATHS
    # ------------------------------------------------------

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    IMAGE_PATH = PROJECT_ROOT / "data" / "kodak_gray" / "Lena.png"

    MODEL_PATH = PROJECT_ROOT / "models_ablation" / "v4_patch3.pth"

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    print()

    print("=" * 70)

    print("Prediction Error Histogram Analysis")

    print("=" * 70)

    print()

    print(f"Image  : {IMAGE_PATH}")

    print(f"Model  : {MODEL_PATH}")

    print(f"Device : {DEVICE}")

    image = load_grayscale(

        str(IMAGE_PATH)

    )

    errors = compute_errors(

        image,

        str(MODEL_PATH),

        DEVICE

    )

    plot_histogram(

        errors

    )

    print_statistics(

        errors

    )

    print()

    print("=" * 70)

    print("Figure 4 generated successfully.")

    print("=" * 70)

    print()

    print(

        os.path.join(

            RESULT_DIR,

            "prediction_error_histogram.png"

        )

    )


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()