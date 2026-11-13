#!/usr/bin/env python3
"""ASCII-safe version of mapping tests for Windows compatibility."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.rdhei_core import (
    _compute_bpp_and_range,
    _embed_pixel,
    _recover_pixel
)


def test_boundary_values():
    """Test boundary values."""
    print("\n" + "="*70)
    print("TEST 1: Boundary Values")
    print("="*70)
    
    test_cases = [
        (0, 7, 0, 0),
        (1, 6, 1, 1),
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
    ]
    
    all_pass = True
    for e_abs, exp_bpp, exp_min, exp_max in test_cases:
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        if bpp == exp_bpp and min_e == exp_min and max_e == exp_max:
            print(f"  PASS: |e|={e_abs:3d} -> bpp={bpp}, range=[{min_e},{max_e}]")
        else:
            print(f"  FAIL: |e|={e_abs:3d} -> bpp={bpp}, range=[{min_e},{max_e}] (expected bpp={exp_bpp}, range=[{exp_min},{max_e}])")
            all_pass = False
    
    return all_pass


def test_recovery_random():
    """Test recovery with random samples."""
    print("\n" + "="*70)
    print("TEST 2: Recovery Random Samples")
    print("="*70)
    
    np.random.seed(42)
    failures = 0
    tested = 0
    
    for _ in range(1000):
        orig = np.random.randint(0, 256)
        pred = np.random.randint(0, 256)
        e_abs = abs(orig - pred)
        
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        if bpp == 0:
            continue
        
        tested += 1
        payload = [int(b) for b in np.random.randint(0, 2, size=bpp)]
        stego = _embed_pixel(orig, bpp, payload)
        recovered = _recover_pixel(stego, pred, bpp, min_e, max_e)
        
        if recovered != orig:
            failures += 1
    
    print(f"Tested {tested} cases, {failures} failures")
    return failures == 0


def test_ambiguity_check():
    """Check for ambiguity in recovery."""
    print("\n" + "="*70)
    print("TEST 3: Ambiguity Check")
    print("="*70)
    
    stego_map = {}
    collisions = []
    
    np.random.seed(42)
    
    for _ in range(500):
        orig = np.random.randint(0, 256)
        pred = np.random.randint(0, 256)
        e_abs = abs(orig - pred)
        
        bpp, _, _ = _compute_bpp_and_range(e_abs)
        if bpp == 0:
            continue
        
        payload = [1, 0, 1, 0, 1, 0, 1][:bpp]
        stego = _embed_pixel(orig, bpp, payload)
        
        key = (stego, tuple(payload))
        if key in stego_map:
            for prev_orig, prev_pred in stego_map[key]:
                if prev_orig != orig or prev_pred != pred:
                    collisions.append((prev_orig, prev_pred, orig, pred, stego, payload))
        else:
            stego_map[key] = [(orig, pred)]
    
    print(f"Found {len(collisions)} collision(s) in 500 samples")
    
    # Verify each collision still recovers correctly
    all_recover = True
    for prev_orig, prev_pred, orig, pred, stego, payload in collisions[:5]:
        bpp = len(payload)
        e_abs_prev = abs(prev_orig - prev_pred)
        _, min_e_prev, max_e_prev = _compute_bpp_and_range(e_abs_prev)
        recovered = _recover_pixel(stego, prev_pred, bpp, min_e_prev, max_e_prev)
        match = recovered == prev_orig
        print(f"  Collision: stego={stego}, payload={payload}")
        print(f"    (orig={prev_orig}, pred={prev_pred}) -> recovered={recovered} (match={match})")
        if not match:
            all_recover = False
    
    return all_recover


def run_all_tests():
    print("\n" + "#"*70)
    print("# MAPPING VALIDATION TESTS (ASCII-safe)")
    print("#"*70)
    
    results = []
    for name, test_func in [
        ("Boundary values", test_boundary_values),
        ("Recovery random samples", test_recovery_random),
        ("Ambiguity check", test_ambiguity_check),
    ]:
        try:
            passed = test_func()
            results.append((name, "PASS" if passed else "FAIL"))
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
    
    print("\n" + "#"*70)
    print("# SUMMARY")
    print("#"*70)
    
    for name, status in results:
        print(f"{'[PASS]' if status == 'PASS' else '[FAIL]'}: {name}")
    
    all_pass = all(status == "PASS" for _, status in results)
    print(f"\n{'ALL PASSED' if all_pass else 'SOME FAILED'}")
    return all_pass


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
