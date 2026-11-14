"""Assert-based exhaustive tests for the legacy pixel allocation map.

These are deterministic software-correctness fixtures, not experimental images.
Synthetic unit fixtures remain useful for checking all 256 pixel values and all
payload words; they are never admitted to paper-facing natural-image metrics.
"""
from __future__ import annotations

import numpy as np

from src.rdhei_core import (
    _compute_bpp_and_range,
    _embed_pixel,
    _recover_pixel,
    generate_label_map_fast,
)


BOUNDARY_CASES = [
    (0, 7, 0, 0),
    (1, 6, 1, 1),
    (2, 5, 2, 2),
    (3, 6, 3, 3),
    (4, 4, 4, 4),
    (5, 5, 5, 7),
    (6, 5, 5, 7),
    (7, 5, 5, 7),
    (8, 3, 8, 8),
    (15, 4, 9, 15),
    (16, 2, 16, 16),
    (31, 3, 17, 31),
    (32, 1, 32, 32),
    (63, 2, 33, 63),
    (64, 0, 64, 64),
    (127, 1, 65, 127),
    (128, 0, 0, 0),
    (129, 0, 0, 0),
    (200, 0, 0, 0),
    (255, 0, 0, 0),
]


def test_boundary_values_match_deployed_mapping():
    for error, expected_n, expected_lo, expected_hi in BOUNDARY_CASES:
        assert _compute_bpp_and_range(error) == (
            expected_n,
            expected_lo,
            expected_hi,
        )


def test_scalar_and_vectorized_mappings_match_for_all_256_errors():
    errors = np.arange(256, dtype=np.int32).reshape(16, 16)
    n_map, lo_map, hi_map = generate_label_map_fast(errors)
    expected = np.asarray(
        [_compute_bpp_and_range(int(error)) for error in errors.ravel()],
        dtype=np.int32,
    ).reshape(16, 16, 3)
    actual = np.stack((n_map, lo_map, hi_map), axis=-1)
    np.testing.assert_array_equal(actual, expected)


def test_exact_recovery_for_every_original_prediction_pair_and_payload_word():
    """Exhaust all 65,536 source/prediction pairs and every one of their 2^n words."""
    tested_pairs = 0
    tested_payload_words = 0

    for prediction in range(256):
        for original in range(256):
            n, lo, hi = _compute_bpp_and_range(abs(original - prediction))
            tested_pairs += 1

            if n == 0:
                assert _recover_pixel(original, prediction, n, lo, hi) == original
                continue

            preserved_bits = 8 - n
            modulus = 1 << preserved_bits
            residue = original % modulus
            candidates = [
                candidate
                for candidate in range(residue, 256, modulus)
                if lo <= abs(candidate - prediction) <= hi
            ]
            assert candidates == [original], (
                f"non-unique decoder set for original={original}, prediction={prediction}, "
                f"n={n}, range=[{lo},{hi}]: {candidates}"
            )

            for payload_integer in range(1 << n):
                payload = [
                    (payload_integer >> (n - 1 - bit)) & 1
                    for bit in range(n)
                ]
                marked = _embed_pixel(original, n, payload)
                recovered = _recover_pixel(marked, prediction, n, lo, hi)
                assert recovered == original, (
                    f"recovery failed: original={original}, prediction={prediction}, "
                    f"payload={payload}, marked={marked}, recovered={recovered}"
                )
                tested_payload_words += 1

    assert tested_pairs == 65_536
    assert tested_payload_words == 396_032


def test_embedding_preserves_the_required_low_bit_residue():
    for original in range(256):
        for n in range(8):
            if n == 0:
                continue
            payload = [((original + bit) >> (bit % 8)) & 1 for bit in range(n)]
            marked = _embed_pixel(original, n, payload)
            modulus = 1 << (8 - n)
            assert marked % modulus == original % modulus
