#!/usr/bin/env python3
"""
Regression tests for the receiver_extract_recover fix.

Verifies, for multiple payload lengths:
  - exact image reconstruction:  np.array_equal(original, recovered)
  - exact payload recovery:      np.array_equal(payload, extracted)
  - return structure / dtypes preserved
  - behaviour for an invalid (over-capacity) payload_len is documented.

No models, checkpoints, label-map equations, or encryption module are modified.
"""
from __future__ import annotations

import numpy as np
import sys
import traceback

PROJECT = "/home/parzifal/RDHEI_Project"
sys.path.insert(0, PROJECT)

from src.rdhei_core import (
    content_owner_prepare,
    sender_embed_encrypt,
    receiver_extract_recover,
    run_rdhei,
)


def til(str):
    return f"\n{'='*72}\n{str}\n{'='*72}"


def run_one(image, payload, payload_len, seed=7, label=""):
    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    capacity = co["capacity"]

    # Build the payload we actually embed. sender_embed_encrypt reads from this
    # array; payload_len controls how many bits the receiver tries to extract.
    embed_payload = payload.astype(np.uint8)

    stego_enc = sender_embed_encrypt(co, embed_payload)
    rx = receiver_extract_recover(
        stego_enc,
        co["key"],
        co["nonce"],
        co["bpp_map"],
        co["min_e_map"],
        co["max_e_map"],
        co["pred_int"],
        payload_len,
    )

    recovered = rx["recovered"]
    extracted = rx["extracted"]

    image_exact = bool(np.array_equal(image, recovered))
    # Payload recovery is exact only when payload_len <= len(payload) and we
    # compare against the *first payload_len bits* of what was embedded.
    if payload_len <= len(embed_payload):
        expected = embed_payload[:payload_len].astype(np.uint8)
    else:
        # For over-capacity payload_len we still extract only what is available.
        expected = embed_payload.astype(np.uint8)

    payload_exact = bool(np.array_equal(extracted, expected))

    return {
        "label": label,
        "payload_len": payload_len,
        "capacity": capacity,
        "image_exact": image_exact,
        "payload_exact": payload_exact,
        "extracted_len": len(extracted),
        "recovered_dtype": recovered.dtype,
        "extracted_dtype": extracted.dtype,
        "rx_keys": tuple(sorted(rx.keys())),
    }


def test_return_structure():
    h, w = 4, 5
    image = np.random.RandomState(11).randint(0, 256, (h, w), dtype=np.uint8)
    co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
    payload = np.random.RandomState(11).randint(0, 2, size=co["capacity"], dtype=np.uint8)
    rx = receiver_extract_recover(
        sender_embed_encrypt(co, payload),
        co["key"], co["nonce"],
        co["bpp_map"], co["min_e_map"], co["max_e_map"],
        co["pred_int"], len(payload),
    )
    expected_keys = ("extracted", "recovered", "stego_plain")
    ok_keys = tuple(sorted(rx.keys())) == expected_keys
    ok_dtypes = (rx["recovered"].dtype == np.uint8 and rx["extracted"].dtype == np.uint8)
    ok_shapes = (
        rx["recovered"].shape == image.shape
        and rx["extracted"].shape == (len(payload),)
        and rx["stego_plain"].shape == image.shape
    )
    assert ok_keys, f"keys: {rx.keys()}"
    assert ok_dtypes, f"dtypes: rec={rx['recovered'].dtype} ext={rx['extracted'].dtype}"
    assert ok_shapes, f"shapes: rec={rx['recovered'].shape} ext={rx['extracted'].shape} sp={rx['stego_plain'].shape}"
    print(f"{til('return structure')}")
    print("keys :", rx.keys())
    print("dtypes: recovered=%s extracted=%s" % (rx["recovered"].dtype, rx["extracted"].dtype))
    print("shapes: recovered=%s extracted=%s stego_plain=%s" % (rx["recovered"].shape, rx["extracted"].shape, rx["stego_plain"].shape))
    print("PASS")
    return True


def main():
    print(til("REGRESSION TESTS — receiver_extract_recover fix"))

    # Deterministic image(s)
    rs = np.random.RandomState(1234)
    images = {
        "tiny3x3": rs.randint(0, 256, (3, 3), dtype=np.uint8),
        "rand8x8": rs.randint(0, 256, (8, 8), dtype=np.uint8),
    }

    results = []

    for name, image in images.items():
        co = content_owner_prepare(image=image, key=b"k" * 16, nonce=0, method="med")
        capacity = co["capacity"]

        # payload_overflow is longer than capacity: sender_embed_encrypt will
        # read its first 'capacity' bits (it indexes payload[bit_idx] only while
        # bit_idx < len(payload)); the remainder is ignored by the embed loop.
        # We use it to test the over-capacity receiver case.
        payload_full = rs.randint(0, 2, size=capacity, dtype=np.uint8)
        payload_long = rs.randint(0, 2, size=max(capacity + 1, 1), dtype=np.uint8)

        cases = [
            ("empty", 0, np.array([], dtype=np.uint8)),
            ("one_bit", 1, np.array([int(payload_full[0])], dtype=np.uint8) if capacity >= 1 else np.array([], dtype=np.uint8)),
            ("short", max(1, capacity // 2), payload_full[:max(1, capacity // 2)]),
            ("capacity-1", max(0, capacity - 1), payload_full[:max(0, capacity - 1)]),
            ("full_capacity", capacity, payload_full),
        ]

        # Over-capacity case: receiver asks for more bits than were embedded.
        # We embed the FULL capacity payload (so the stego image is well-defined),
        # then ask the receiver for payload_len = capacity+1. The receiver should
        # extract only the available bits and recover the full image.
        over = ("over_capacity", capacity + 1, payload_full)
        cases.append(over)

        print(f"\n--- image={name} capacity={capacity} ---")
        all_ok = True
        for label, plen, payload in cases:
            r = run_one(image, payload, plen, seed=7, label=label)
            results.append(r)
            status = "PASS" if (r["image_exact"] and r["payload_exact"]) else "FAIL"
            if status == "FAIL":
                all_ok = False
            print(f"  {label:14s} payload_len={plen:<4d} capacity={r['capacity']:<4d} "
                  f"image_exact={r['image_exact']!s:<5} payload_exact={r['payload_exact']!s:<5} "
                  f"extracted_len={r['extracted_len']} -> {status}")

            if status == "FAIL":
                print(f"      extracted: {r['extracted'].tolist()}")
                print(f"      expected:  {payload[:plen].tolist() if plen<=len(payload) else payload.tolist()}")

        # Sanity: for the over-capacity case, payload_exact compares extracted vs
        # the FULL embedded payload (since we only embedded 'capacity' bits). This
        # is intentional: we are testing that the receiver (a) does not crash and
        # (b) extracts everything available and (c) recovers the image exactly.
        over = results[-1]
        print(f"  over_capacity NOTE: only {over['capacity']} bits were embedded; "
              f"receiver asked for {over['payload_len']}. extracted_len={over['extracted_len']}. "
              f"payload_exact compares extracted vs the full embedded payload.")

        # Assert the over-capacity case still recovers the image exactly and extracts
        # exactly the available bits.
        assert over["image_exact"], "over-capacity: image must still be recovered exactly"
        assert over["extracted_len"] == over["capacity"], \
            f"over-capacity: should extract exactly {over['capacity']} available bits, got {over['extracted_len']}"
        assert over["payload_exact"], \
            f"over-capacity: extracted must equal the full embedded payload"

        print(f"  over_capacity -> PASS (image_exact={over['image_exact']}, "
              f"extracted_len={over['extracted_len']}==capacity, payload_exact={over['payload_exact']})")

        assert all_ok, f"Some cases failed for image={name}"

    # Run return-structure test
    test_return_structure()

    # Re-run the full-pipeline smoke (run_rdhei uses full-capacity payload internally)
    print(f"\n{til('full-pipeline smoke (run_rdhei, full-capacity payload)')}")
    for name, image in list(images.items())[:1]:
        r = run_rdhei(image=image, key=b"k" * 16, nonce=0, method="med", seed=7)
        print(f"  image={name} capacity={r['capacity']} bpp={r['bpp']:.4f} "
              f"bit_acc={r['bit_acc']} perfect={r['perfect']}")
        assert r["perfect"], "run_rdhei: perfect must be True"
        assert r["bit_acc"] == 100.0, "run_rdhei: bit_acc must be 100.0"
        assert np.array_equal(image, r["recovered"]), "run_rdhei: recovered must equal original"
        assert np.array_equal(r["payload"], r["extracted"]), "run_rdhei: extracted must equal payload"
        print("  PASS")

    print(f"\n{til('ALL REGRESSION TESTS PASSED')}")
    print("Cases run:")
    for r in results:
        print(f"  {r['label']:14s} plen={r['payload_len']:<4d} capacity={r['capacity']:<4d} "
              f"image_exact={r['image_exact']} payload_exact={r['payload_exact']} "
              f"extracted_len={r['extracted_len']}")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        print("ERROR:", traceback.format_exc())
        rc = 2
    sys.exit(rc)
