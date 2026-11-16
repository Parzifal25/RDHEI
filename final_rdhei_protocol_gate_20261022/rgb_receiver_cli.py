#!/usr/bin/env python3
"""Isolated CC-EDR2-RGB receiver process.

Only a marked RGB image, master key and nonce are semantic receiver inputs.
Original source paths are forbidden and audited by guarded Python file opens.
"""
from __future__ import annotations

import argparse
import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
if str(EDR2) not in sys.path:
    sys.path.insert(0, str(EDR2))

import predictor  # noqa: E402
import rgb_protocol  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_forbidden(path_value, forbidden: list[Path]) -> bool:
    try:
        candidate = Path(os.fspath(path_value)).resolve()
    except (TypeError, ValueError, OSError):
        return False
    for root in forbidden:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-json", required=True,
                        help="JSON file containing only marked image, key/nonce and output paths.")
    args = parser.parse_args()

    request_path = Path(args.request_json).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    required = {
        "marked_image", "master_key_hex", "nonce",
        "recovered_image", "payload_npy", "result_json",
        "forbidden_paths",
    }
    if set(request) != required:
        raise ValueError(f"receiver request keys differ: {sorted(set(request) ^ required)}")

    marked_path = Path(request["marked_image"]).resolve()
    recovered_path = Path(request["recovered_image"]).resolve()
    payload_path = Path(request["payload_npy"]).resolve()
    result_path = Path(request["result_json"]).resolve()
    forbidden = [Path(p).resolve() for p in request["forbidden_paths"]]
    if is_forbidden(marked_path, forbidden):
        raise ValueError("marked image unexpectedly lies under forbidden source path")

    key = bytes.fromhex(request["master_key_hex"])
    nonce = int(request["nonce"])
    if len(key) != 32 or not 0 <= nonce < 2**128:
        raise ValueError("invalid receiver key or nonce")

    opened_reads: list[str] = []
    blocked_reads: list[str] = []
    original_builtin_open = builtins.open
    original_io_open = io.open

    def guarded_open(file, mode="r", *open_args, **open_kwargs):
        if any(flag in str(mode) for flag in ("r", "+")) and is_forbidden(file, forbidden):
            blocked_reads.append(str(Path(os.fspath(file)).resolve()))
            raise PermissionError("receiver source-read audit blocked forbidden source path")
        if any(flag in str(mode) for flag in ("r", "+")):
            try:
                opened_reads.append(str(Path(os.fspath(file)).resolve()))
            except (TypeError, ValueError, OSError):
                pass
        return original_builtin_open(file, mode, *open_args, **open_kwargs)

    def guarded_io_open(file, mode="r", *open_args, **open_kwargs):
        if any(flag in str(mode) for flag in ("r", "+")) and is_forbidden(file, forbidden):
            blocked_reads.append(str(Path(os.fspath(file)).resolve()))
            raise PermissionError("receiver source-read audit blocked forbidden source path")
        if any(flag in str(mode) for flag in ("r", "+")):
            try:
                opened_reads.append(str(Path(os.fspath(file)).resolve()))
            except (TypeError, ValueError, OSError):
                pass
        return original_io_open(file, mode, *open_args, **open_kwargs)

    builtins.open = guarded_open
    io.open = guarded_io_open
    started = time.perf_counter()
    try:
        with Image.open(marked_path) as image:
            if image.mode != "RGB" or getattr(image, "n_frames", 1) != 1:
                raise ValueError(f"receiver requires a single-frame native RGB image, got {image.mode}")
            marked = np.asarray(image, dtype=np.uint8).copy()
        recovered, payload = rgb_protocol.receive(marked, key, nonce)
        if recovered.shape != marked.shape or recovered.dtype != np.uint8:
            raise ValueError("receiver returned invalid restored RGB image")
        recovered_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(recovered, mode="RGB").save(recovered_path, format="PNG")
        np.save(payload_path, np.asarray(payload, dtype=np.uint8), allow_pickle=False)
        elapsed = time.perf_counter() - started
        result = {
            "status": "receiver_completed",
            "receiver_pid": os.getpid(),
            "receiver_seconds": elapsed,
            "marked_image_sha256": sha256_bytes(marked.tobytes(order="C")),
            "recovered_pixel_sha256": sha256_bytes(recovered.tobytes(order="C")),
            "payload_sha256": sha256_bytes(np.asarray(payload, dtype=np.uint8).tobytes()),
            "payload_bits": int(len(payload)),
            "source_access": bool(blocked_reads),
            "source_reads": blocked_reads,
            "opened_read_paths": sorted(set(opened_reads)),
            "training_performed": False,
        }
        # Restore guarded calls before writing result JSON. The final output is not
        # a semantic receiver input and remains outside all forbidden paths.
        builtins.open = original_builtin_open
        io.open = original_io_open
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    finally:
        builtins.open = original_builtin_open
        io.open = original_io_open


if __name__ == "__main__":
    raise SystemExit(main())
