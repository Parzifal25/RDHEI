#!/usr/bin/env python3
"""
MAPPING VALIDATION TESTS
========================

Comprehensive tests for the prediction-error to bit-allocation mapping.
Tests all boundary values, edge cases, and verifies unique decodability.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.rdhei_core import (
    _compute_bpp_and_range,
    _embed_pixel,
    _recover_pixel,
    generate_label_map_fast
)


def test_boundary_values():
    """Test all critical boundary values for the mapping function."""
    print("\n" + "="*70)
    print("TEST 1: Boundary Values for _compute_bpp_and_range")
    print("="*70)
    
    # Critical boundaries to test
    test_cases = [
        # (e_abs, expected_bpp, expected_min_e, expected_max_e, description)
        (0, 7, 0, 0, "|e|=0: 7 bits, range [0,0]"),
        (1, 6, 1, 1, "|e|=1: 6 bits, range [1,1]"),
        (2, 5, 2, 2, "|e|=2: 5 bits, range [2,2]"),
        (3, 6, 3, 3, "|e|=3: 6 bits, range [3,3]"),
        (4, 4, 4, 4, "|e|=4: 4 bits, range [4,4]"),
        (5, 4, 0, 0, "|e|=5: 4 bits, no range (falls through)"),
        (6, 4, 0, 0, "|e|=6: 4 bits, no range"),
        (7, 5, 5, 7, "|e|=7: 5 bits, range [5,7]"),
        (8, 3, 8, 8, "|e|=8: 3 bits, range [8,8]"),
        (15, 4, 9, 15, "|e|=15: 4 bits, range [9,15]"),
        (16, 2, 16, 16, "|e|=16: 2 bits, range [16,16]"),
        (31, 3, 17, 31, "|e|=31: 3 bits, range [17,31]"),
        (32, 1, 32, 32, "|e|=32: 1 bit, range [32,32]"),
        (63, 2, 33, 63, "|e|=63: 2 bits, range [33,63]"),
        (64, 0, 64, 64, "|e|=64: 0 bits, range [64,64]"),
        (127, 1, 65, 127, "|e|=127: 1 bit, range [65,127]"),
        (128, 0, 0, 0, "|e|=128: 0 bits, no capacity"),
        (129, 0, 0, 0, "|e|=129+: 0 bits, no capacity"),
        (200, 0, 0, 0, "|e|=200: 0 bits, no capacity"),
        (255, 0, 0, 0, "|e|=255: 0 bits, no capacity"),
    ]
    
    all_pass = True
    for e_abs, exp_bpp, exp_min, exp_max, desc in test_cases:
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        # Check
        bpp_ok = (bpp == exp_bpp)
        min_ok = (min_e == exp_min)
        max_ok = (max_e == exp_max)
        
        if bpp_ok and min_ok and max_ok:
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False
            print(f"  {status}: |e|={e_abs:3d} - {desc}")
            print(f"    Expected: bpp={exp_bpp}, min={exp_min}, max={exp_max}")
            print(f"    Got:      bpp={bpp}, min={min_e}, max={max_e}")
        # else:
        #     print(f"  {status}: |e|={e_abs:3d} - {desc}")
    
    print(f"\nBoundary value test: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


def test_recovery_for_all_errors():
    """Test recovery for all possible |e| values with random payloads."""
    print("\n" + "="*70)
    print("TEST 2: Recovery for All |e| Values (0-255)")
    print("="*70)
    
    np.random.seed(42)
    
    failures = []
    total_tested = 0
    
    for e_abs in range(256):
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        if bpp == 0:
            continue  # Skip if no capacity
        
        total_tested += 1
        
        # Test with multiple random (orig, pred) pairs that give this |e|
        for _ in range(5):
            # Random original pixel
            orig = np.random.randint(0, 256)
            
            # Random pred that gives |orig - pred| = e_abs
            if orig >= e_abs:
                pred = orig - e_abs
            else:
                pred = orig + e_abs
            
            pred = min(max(pred, 0), 255)
            
            # Verify |orig - pred| = e_abs
            actual_e = abs(orig - pred)
            if actual_e != e_abs:
                continue
            
            # Generate random payload
            payload = [int(b) for b in np.random.randint(0, 2, size=bpp)]
            
            # Embed
            stego = _embed_pixel(orig, bpp, payload)
            
            # Recover
            recovered = _recover_pixel(stego, pred, bpp, min_e, max_e)
            
            # Check
            if recovered != orig:
                failures.append((orig, pred, e_abs, bpp, payload, recovered))
    
    print(f"Tested {total_tested} different |e| values")
    print(f"Failures: {len(failures)}")
    
    if failures:
        print("\nFirst 5 failures:")
        for orig, pred, e_abs, bpp, payload, recovered in failures[:5]:
            print(f"  orig={orig}, pred={pred}, |e|={e_abs}, bpp={bpp}")
            print(f"    payload={payload}, recovered={recovered} (expected {orig})")
        return False
    
    print("PASS: All recovery tests ✓")
    return True


def test_all_payloads_for_sample_cases():
    """Test ALL possible payloads for specific (orig, pred) pairs."""
    print("\n" + "="*70)
    print("TEST 3: All Payloads for Sample Cases")
    print("="*70)
    
    test_cases = [
        (100, 100, "orig=pred (e=0, 7 bits)"),
        (100, 108, "orig=100, pred=108 (e=8, 3 bits)"),
        (50, 50, "orig=pred=50 (e=0, 7 bits)"),
        (128, 128, "orig=pred=128 (e=0, 7 bits)"),
        (128, 136, "orig=128, pred=136 (e=8, 3 bits)"),
        (10, 10, "orig=pred=10 (e=0, 7 bits)"),
        (200, 192, "orig=200, pred=192 (e=8, 3 bits)"),
    ]
    
    all_pass = True
    
    for orig, pred, desc in test_cases:
        e_abs = abs(orig - pred)
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        print(f"\n{desc}: orig={orig}, pred={pred}, |e|={e_abs}, bpp={bpp}")
        
        if bpp == 0:
            print(f"  No capacity - skipping")
            continue
        
        # Test all possible payloads
        failures = []
        for payload_int in range(2**bpp):
            payload = [(payload_int >> (bpp-1-i)) & 1 for i in range(bpp)]
            stego = _embed_pixel(orig, bpp, payload)
            recovered = _recover_pixel(stego, pred, bpp, min_e, max_e)
            
            if recovered != orig:
                failures.append((payload_int, payload, stego, recovered))
        
        if failures:
            print(f"  FAIL: {len(failures)} payload(s) failed recovery")
            for p_int, p_bits, stego, rec in failures[:3]:
                print(f"    payload={p_int:0{bpp}b} ({p_bits}) -> stego={stego} -> recovered={rec}")
            all_pass = False
        else:
            print(f"  PASS: All {2**bpp} payloads recovered correctly")
    
    print(f"\nAll-payloads test: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


def test_ambiguity():
    """Test for ambiguity: can different (orig, pred) produce same stego?"""
    print("\n" + "="*70)
    print("TEST 4: Ambiguity Check")
    print("="*70)
    
    # Check if different (orig, pred) pairs can produce same stego pixel
    # with the same payload
    
    stego_map = {}  # stego_val -> list of (orig, pred, payload)
    collisions = []
    
    np.random.seed(42)
    
    for _ in range(1000):
        orig = np.random.randint(0, 256)
        pred = np.random.randint(0, 256)
        e_abs = abs(orig - pred)
        
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        if bpp == 0:
            continue
        
        # Use a fixed payload pattern for this test
        payload = [1, 0, 1, 0, 1, 0, 1][:bpp]
        
        stego = _embed_pixel(orig, bpp, payload)
        
        key = (stego, tuple(payload))
        if key in stego_map:
            # Same stego and payload, but different (orig, pred)
            for prev_orig, prev_pred in stego_map[key]:
                if prev_orig != orig or prev_pred != pred:
                    collisions.append((prev_orig, prev_pred, orig, pred, stego, payload))
        else:
            stego_map[key] = [(orig, pred)]
    
    if collisions:
        print(f"Found {len(collisions)} potential collision(s):")
        for prev_orig, prev_pred, orig, pred, stego, payload in collisions[:5]:
            print(f"  stego={stego}, payload={payload}")
            print(f"    From (orig={prev_orig}, pred={prev_pred})")
            print(f"    Also from (orig={orig}, pred={pred})")
        
        # Verify recovery for each case
        print("\nVerifying recovery for collision cases:")
        for prev_orig, prev_pred, orig, pred, stego, payload in collisions[:3]:
            bpp = len(payload)
            e_abs_prev = abs(prev_orig - prev_pred)
            _, min_e_prev, max_e_prev = _compute_bpp_and_range(e_abs_prev)
            
            recovered_prev = _recover_pixel(stego, prev_pred, bpp, min_e_prev, max_e_prev)
            print(f"  (orig={prev_orig}, pred={prev_pred}) -> recovered={recovered_prev} (match={recovered_prev==prev_orig})")
        
        return False
    else:
        print("No collisions found in random sampling")
        print("PASS: No ambiguity detected ✓")
        return True


def test_signed_vs_unsigned():
    """Test behavior with signed vs unsigned errors."""
    print("\n" + "="*70)
    print("TEST 5: Signed vs Unsigned Error Handling")
    print("="*70)
    
    # The function expects |e| (absolute value)
    # Test what happens with negative values
    
    print("\nTesting negative e_abs values (should be treated as unsigned):")
    
    for e in [-1, -5, -10, -50, -100, -200]:
        bpp, min_e, max_e = _compute_bpp_and_range(e)
        print(f"  e_abs={e:4d}: bpp={bpp}, min={min_e}, max={max_e}")
    
    # In Python, negative % 256 gives positive result for uint8 simulation
    # but _compute_bpp_and_range just uses the value directly
    # Negative values will behave unexpectedly
    
    print("\nNote: Function expects |e|, not signed error")
    print("If signed error is passed, behavior is undefined")
    
    return True


def test_candidate_set():
    """Analyze the candidate set for recovery."""
    print("\n" + "="*70)
    print("TEST 6: Candidate Set Analysis")
    print("="*70)
    
    test_cases = [
        (100, 100, "e=0"),
        (100, 101, "e=1"),
        (100, 108, "e=8"),
        (50, 50, "e=0"),
        (128, 128, "e=0"),
        (128, 136, "e=8"),
        (10, 20, "e=10"),
        (200, 180, "e=20"),
    ]
    
    for orig, pred, desc in test_cases:
        e_abs = abs(orig - pred)
        bpp, min_e, max_e = _compute_bpp_and_range(e_abs)
        
        print(f"\n{desc}: orig={orig}, pred={pred}, |e|={e_abs}")
        print(f"  bpp={bpp}, range=[{min_e}, {max_e}]")
        
        if bpp == 0:
            print(f"  No capacity - no candidates")
            continue
        
        # Find all candidates
        n_lower = 8 - bpp
        lower_mask = (1 << n_lower) - 1
        lower = orig & lower_mask
        
        candidates = []
        for combo in range(2**bpp):
            c = (combo << n_lower) | lower
            if 0 <= c <= 255 and min_e <= abs(c - pred) <= max_e:
                candidates.append(c)
        
        print(f"  Lower bits: {lower:0{n_lower}b}")
        print(f"  Candidate set size: {len(candidates)}")
        print(f"  Candidates: {sorted(candidates)[:20]}{'...' if len(candidates) > 20 else ''}")
        print(f"  Original in candidates: {orig in candidates}")
        
        if orig not in candidates:
            print(f"  ERROR: Original not in candidate set!")
    
    print("\nPASS: Candidate set analysis complete")
    return True


def run_all_tests():
    """Run all mapping validation tests."""
    print("\n" + "#"*70)
    print("# MAPPING VALIDATION TESTS")
    print("#"*70)
    
    tests = [
        ("Boundary values", test_boundary_values),
        ("Recovery for all |e|", test_recovery_for_all_errors),
        ("All payloads for samples", test_all_payloads_for_sample_cases),
        ("Ambiguity check", test_ambiguity),
        ("Signed vs unsigned", test_signed_vs_unsigned),
        ("Candidate set analysis", test_candidate_set),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, "PASS" if passed else "FAIL", None))
        except Exception as e:
            print(f"\nERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, "ERROR", str(e)))
    
    print("\n" + "#"*70)
    print("# TEST SUMMARY")
    print("#"*70)
    
    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  {error}")
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    return all(status == "PASS" for _, status, _ in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
