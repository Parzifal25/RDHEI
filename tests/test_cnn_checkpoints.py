#!/usr/bin/env python3
"""Test CNN checkpoint configurations."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from src.cnn_model import build_model, count_parameters, load_model

def test_parameter_counts():
    """Verify parameter counts match expected values."""
    print("\n" + "="*70)
    print("CNN PARAMETER COUNT VERIFICATION")
    print("="*70)
    
    variants = [
        ("CNN-3x3", 3, True, 46881),
        ("CNN-5x5", 5, True, 112417),
        ("No Residual", 5, False, 112353),
        ("No Weighted", 5, True, 112417),
        ("CNN-7x7", 7, True, 210721),
    ]
    
    all_pass = True
    for name, patch, res, expected in variants:
        model = build_model(patch, res)
        actual = count_parameters(model)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_pass = False
        print(f"{name:15s}: expected={expected:>8,}, actual={actual:>8,} [{status}]")
    
    return all_pass


def test_checkpoint_loading():
    """Test loading all checkpoints."""
    print("\n" + "="*70)
    print("CHECKPOINT LOADING TESTS")
    print("="*70)
    
    checkpoints = [
        ("v4_patch3.pth", 3, True, 46881),
        ("v1_full.pth", 5, True, 112417),
        ("v2_no_residual.pth", 5, False, 112353),
        ("v3_no_weighted_loss.pth", 5, True, 112417),
        ("v5_patch7.pth", 7, True, 210721),
    ]
    
    all_pass = True
    for fname, exp_patch, exp_res, exp_params in checkpoints:
        path = os.path.join("models", fname)
        if not os.path.exists(path):
            print(f"{fname}: SKIP (not found)")
            continue
        
        try:
            model, patch, residual, n_params = load_model(path, device="cpu")
            
            patch_ok = (patch == exp_patch)
            res_ok = (residual == exp_res)
            params_ok = (n_params == exp_params)
            
            status = "PASS" if (patch_ok and res_ok and params_ok) else "FAIL"
            if not (patch_ok and res_ok and params_ok):
                all_pass = False
            
            print(f"{fname:25s}: patch={patch} (exp={exp_patch}) {'OK' if patch_ok else 'MISMATCH'}, "
                  f"residual={residual} (exp={exp_res}) {'OK' if res_ok else 'MISMATCH'}, "
                  f"params={n_params:,} (exp={exp_params:,}) {'OK' if params_ok else 'MISMATCH'} [{status}]")
        except Exception as e:
            print(f"{fname}: FAIL - {e}")
            import traceback
            traceback.print_exc()
            all_pass = False
    
    return all_pass


if __name__ == "__main__":
    print("#"*70)
    print("# CNN CHECKPOINT VALIDATION")
    print("#"*70)
    
    results = []
    for name, test_func in [
        ("Parameter counts", test_parameter_counts),
        ("Checkpoint loading", test_checkpoint_loading),
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
    sys.exit(0 if all_pass else 1)
