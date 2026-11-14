#!/usr/bin/env python3
"""Verify candidate public sources for the exact six original RDHEI baseline PNGs.

No candidate is accepted by filename or appearance. A source is restored only if
its original bytes match the pinned file SHA-256, or its decoded pixels match
the pinned pixel SHA-256 and a deterministic Pillow PNG re-encode reproduces
the exact pinned file SHA-256. All other candidates are report-only.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "baseline_candidate_verification.json"
TARGET_DIR = ROOT / "data" / "kodak_gray"

EXPECTED = {
    "Airplane.png": {
        "file_sha256": "7f8b1f59666ca174f7b29012e74ededac54a126b58c06d5a206704b706fe0610",
        "pixels_sha256": "5da692fdfdddeb62f11e835d0391c73c349348ed3284cb8b719d0cebf3577a71",
        "shape": [512, 512],
    },
    "Baboon.png": {
        "file_sha256": "011facaeced920692fb981e475d077784a6496be02ccf5fe8745e0d20c79e879",
        "pixels_sha256": "ec56f895304cff5c0153efcfe517a04fcb7edffe7f9cfa8207b4b949cf57168f",
        "shape": [512, 512],
    },
    "Goldhill.png": {
        "file_sha256": "bb30071d1326e30a0f981f0fa12ba22a907a62f38b9802cf05ec754b23b84cd1",
        "pixels_sha256": "956059e859ba1af1b0bf21c6eacae9e7a0956c949b400b6a1579c44b5b4bca49",
        "shape": [576, 720],
    },
    "Jetplane.png": {
        "file_sha256": "5387655110fe834b6421c7f56fc77bd80feb8c10902847309aea638281d8bbc3",
        "pixels_sha256": "71e53d7e42ee3908f1bd3a2a59e235e533a816e1e03dbab2b67a2c0ab6c1ab75",
        "shape": [1024, 1024],
    },
    "Lena.png": {
        "file_sha256": "5ca92b8fbb3f446ad92dcdea58b0662e271be90f0630de276762af1e88c0b5fd",
        "pixels_sha256": "eb6cd30ede15f638d0fccba36977d7c6a6ae3f31b8bd8f78dffdfcb47437acc7",
        "shape": [512, 512],
    },
    "Peppers.png": {
        "file_sha256": "e554728dd6b60a0c5d7df075353546c5be48b77b2c0c0d4ae467086c4e3f1986",
        "pixels_sha256": "a90f9cdb5111a7bc4c8063e53e3e65ef634639fa27929abaf329f726540a697f",
        "shape": [512, 512],
    },
}

RAW = "https://raw.githubusercontent.com/"
CANDIDATES = {
    "Airplane.png": [
        RAW + "semnan-university-ai/image-processing-benchmark/bf86b771a920d11ec57aafd084cb88616a1c555c/airplane.png",
        "https://homepages.cae.wisc.edu/~ece533/images/airplane.png",
    ],
    "Baboon.png": [
        RAW + "semnan-university-ai/image-processing-benchmark/bf86b771a920d11ec57aafd084cb88616a1c555c/baboon.png",
        "https://homepages.cae.wisc.edu/~ece533/images/baboon.png",
    ],
    "Goldhill.png": [
        RAW + "semnan-university-ai/image-processing-benchmark/bf86b771a920d11ec57aafd084cb88616a1c555c/goldhill.png",
        "https://homepages.cae.wisc.edu/~ece533/images/goldhill.png",
    ],
    "Jetplane.png": [
        RAW + "wilywork/processamento-de-imagens-m2/a79b54c4bc9f735d19d8f505e5be0176f5bfe57c/imagens_originais/jetplane.png",
        "https://homepages.cae.wisc.edu/~ece533/images/jetplane.png",
    ],
    "Lena.png": [
        RAW + "semnan-university-ai/image-processing-benchmark/bf86b771a920d11ec57aafd084cb88616a1c555c/lena.png",
        "https://homepages.cae.wisc.edu/~ece533/images/lena.png",
    ],
    "Peppers.png": [
        RAW + "semnan-university-ai/image-processing-benchmark/bf86b771a920d11ec57aafd084cb88616a1c555c/peppers.png",
        "https://homepages.cae.wisc.edu/~ece533/images/peppers.png",
    ],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_sha256(array: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(str(tuple(array.shape)).encode("ascii"))
    h.update(b"|uint8|")
    h.update(array.tobytes(order="C"))
    return h.hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RDHEI-baseline-provenance-check/1.0"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        data = response.read()
    if len(data) < 100:
        raise ValueError("response is too small to be an image")
    return data


def candidate_arrays(data: bytes):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        native_mode = image.mode
        native = np.asarray(image)
        if native_mode == "L" and native.dtype == np.uint8 and native.ndim == 2:
            yield "native-L", np.ascontiguousarray(native)
        # This is only a diagnostic candidate. It is never silently adopted:
        # the decoded pixels must match the project's pinned pixel hash.
        gray = np.asarray(image.convert("L"))
        if gray.dtype == np.uint8 and gray.ndim == 2:
            yield "Pillow-convert-L", np.ascontiguousarray(gray)


def reencode_matches(array: np.ndarray, expected_file_hash: str):
    image = Image.fromarray(array, mode="L")
    for optimize in (False, True):
        for level in range(10):
            buffer = io.BytesIO()
            image.save(
                buffer,
                format="PNG",
                optimize=optimize,
                compress_level=level,
            )
            raw = buffer.getvalue()
            if sha256(raw) == expected_file_hash:
                return raw, {"optimize": optimize, "compress_level": level}
    return None, None


def main():
    report = {
        "title": "Exact original six-image baseline source verification",
        "policy": (
            "A source is restored only on exact file hash, or exact decoded-pixel "
            "hash plus a re-encoded PNG whose bytes reproduce the pinned file hash."
        ),
        "images": {},
        "restored": [],
    }
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    for name, expected in EXPECTED.items():
        rows = []
        restored = None
        for url in CANDIDATES[name]:
            item = {"url": url}
            try:
                data = fetch(url)
                item["candidate_file_sha256"] = sha256(data)
                item["byte_exact"] = item["candidate_file_sha256"] == expected["file_sha256"]
                variants = []
                for variant_name, array in candidate_arrays(data):
                    digest = pixel_sha256(array)
                    variant = {
                        "variant": variant_name,
                        "shape": list(array.shape),
                        "pixel_sha256": digest,
                        "pixel_exact": (
                            digest == expected["pixels_sha256"]
                            and list(array.shape) == expected["shape"]
                        ),
                    }
                    if variant["pixel_exact"]:
                        encoded, settings = reencode_matches(array, expected["file_sha256"])
                        variant["png_reencode_exact"] = encoded is not None
                        variant["pillow_encoding"] = settings
                        if encoded is not None:
                            restored = encoded
                    variants.append(variant)
                item["variants"] = variants
                if item["byte_exact"]:
                    restored = data
            except Exception as exc:
                item["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(item)
            if restored is not None:
                break

        restored_path = TARGET_DIR / name
        if restored is not None:
            if restored_path.exists():
                raise FileExistsError(
                    f"refusing to overwrite an existing baseline: {restored_path}"
                )
            restored_path.write_bytes(restored)
            report["restored"].append(name)
            rows.append({"restored_to": str(restored_path), "file_sha256": sha256(restored)})
        report["images"][name] = {
            "expected": expected,
            "candidates": rows,
            "restored": restored is not None,
        }

    report["all_six_restored"] = len(report["restored"]) == 6
    report["restored_count"] = len(report["restored"])
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "restored": report["restored"],
        "restored_count": report["restored_count"],
        "all_six_restored": report["all_six_restored"],
        "report": str(OUTPUT),
    }, indent=2))
    # A source-search miss is a valid result; it must not make CI pretend that
    # missing baselines were restored.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
