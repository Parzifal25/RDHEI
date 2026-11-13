#!/usr/bin/env python3
"""
RGB Validation Task — Full 5-Variant Test

Test all five existing CNN variants on the available genuine RGB images.
Preserve earlier results.

Variants:
1. v1_full.pth - 5x5 patch, residual=True
2. v2_no_residual.pth - 5x5 patch, residual=False
3. v3_no_weighted_loss.pth - 5x5 patch, residual=True
4. v4_patch3.pth - 3x3 patch, residual=True
5. v5_patch7.pth - 7x7 patch, residual=True

Only test on genuine RGB images (skip images.png which is grayscale).
"""

import sys
import csv
import numpy as np
from pathlib import Path
from PIL import Image
from datetime import datetime
import time

# Setup paths
BASE = Path("/home/parzifal/RDHEI_Project")
sys.path.insert(0, str(BASE))

from src.rdhei_color import run_rdhei_color
from src.cnn_model import load_model

# Output directory
OUT = Path("/home/parzifal/RDHEI_Project/results/rgb_validation_20261013")
OUT.mkdir(parents=True, exist_ok=True)

# Configuration
DATA_DIR = BASE / "data/kodak_color"
CHECKPOINTS = {
    "v1_full": BASE / "RDHEI_FIXED_V1/models/v1_full.pth",
    "v2_no_residual": BASE / "RDHEI_FIXED_V1/models/v2_no_residual.pth",
    "v3_no_weighted_loss": BASE / "RDHEI_FIXED_V1/models/v3_no_weighted_loss.pth",
    "v4_patch3": BASE / "RDHEI_FIXED_V1/models/v4_patch3.pth",
    "v5_patch7": BASE / "RDHEI_FIXED_V1/models/v5_patch7.pth",
}

KEY = b'k' * 16
NONCE = 0
SEED = 42
DEVICE = "cpu"

def get_genuine_rgb_images():
    """Get list of genuine RGB images (exclude grayscale)."""
    images = []
    for path in sorted(DATA_DIR.glob("*.png")):
        if path.name.endswith(":Zone.Identifier"):
            continue
        
        with Image.open(path) as img:
            if img.mode == "RGB":
                arr = np.array(img)
                # Verify genuine colour variation
                r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
                max_diff = max(
                    np.max(np.abs(r.astype(int) - g.astype(int))),
                    np.max(np.abs(g.astype(int) - b.astype(int))),
                    np.max(np.abs(r.astype(int) - b.astype(int)))
                )
                if max_diff > 0:
                    images.append({
                        "path": path,
                        "name": path.name,
                        "shape": arr.shape,
                        "max_diff": max_diff
                    })
    
    return images

def test_variant(variant_name, checkpoint_path, images):
    """Test a single variant on all genuine RGB images."""
    print(f"\n{'='*70}")
    print(f"Testing variant: {variant_name}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"{'='*70}")
    
    # Load model
    model, patch_size, has_residual, num_params = load_model(checkpoint_path, device=DEVICE)
    
    results = []
    
    for img_info in images:
        print(f"\n  Testing {img_info['name']} ({img_info['shape']})...", end=" ")
        sys.stdout.flush()
        
        start_time = time.time()
        
        try:
            # Load image
            with Image.open(img_info['path']) as img:
                image_rgb = np.array(img)
            
            # Run pipeline
            result = run_rdhei_color(
                image_rgb=image_rgb,
                key=KEY,
                nonce=NONCE,
                method="cnn",
                model=model,
                device=DEVICE,
                patch_size=patch_size,
                seed=SEED
            )
            
            elapsed = time.time() - start_time
            
            # Independent verification
            exact_rgb = np.array_equal(image_rgb, result['recovered'])
            pipeline_perfect = result['perfect']
            pipeline_bit_acc = result['bit_acc']
            
            # Per-channel verification
            all_channels_exact = True
            all_payloads_exact = True
            
            for ch in result['per_channel']:
                if not ch['perfect']:
                    all_channels_exact = False
                if ch['bit_acc'] < 100.0:
                    all_payloads_exact = False
            
            # Determine pass/fail
            passed = exact_rgb and pipeline_perfect and pipeline_bit_acc == 100.0 \
                     and all_channels_exact and all_payloads_exact
            
            status = "PASS" if passed else "FAIL"
            print(f"{status} ({elapsed:.1f}s)")
            
            if not passed:
                print(f"    Exact RGB: {exact_rgb}")
                print(f"    Pipeline perfect: {pipeline_perfect}")
                print(f"    Pipeline bit_acc: {pipeline_bit_acc}")
                print(f"    All channels exact: {all_channels_exact}")
                print(f"    All payloads exact: {all_payloads_exact}")
            
            results.append({
                "variant": variant_name,
                "image": img_info['name'],
                "shape": f"{img_info['shape'][0]}x{img_info['shape'][1]}x{img_info['shape'][2]}",
                "checkpoint": checkpoint_path.name,
                "patch_size": patch_size,
                "residual": has_residual,
                "params": num_params,
                "bpp": result['bpp'],
                "psnr": result['psnr_rec'] if np.isfinite(result['psnr_rec']) else "inf",
                "ssim": result['ssim_rec'],
                "mae": result['mae_rec'],
                "bit_acc": result['bit_acc'],
                "pipeline_perfect": pipeline_perfect,
                "exact_rgb": exact_rgb,
                "all_channels_exact": all_channels_exact,
                "all_payloads_exact": all_payloads_exact,
                "passed": passed,
                "elapsed_seconds": elapsed
            })
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"ERROR ({elapsed:.1f}s): {e}")
            results.append({
                "variant": variant_name,
                "image": img_info['name'],
                "shape": f"{img_info['shape'][0]}x{img_info['shape'][1]}x{img_info['shape'][2]}",
                "checkpoint": checkpoint_path.name,
                "patch_size": patch_size,
                "residual": has_residual,
                "params": num_params,
                "bpp": None,
                "psnr": None,
                "ssim": None,
                "mae": None,
                "bit_acc": None,
                "pipeline_perfect": None,
                "exact_rgb": None,
                "all_channels_exact": None,
                "all_payloads_exact": None,
                "passed": False,
                "elapsed_seconds": elapsed,
                "error": str(e)
            })
    
    return results

def main():
    print("=" * 70)
    print("RGB VALIDATION TASK — 5-VARIANT TEST")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Get genuine RGB images
    images = get_genuine_rgb_images()
    
    print(f"\nGenuine RGB images to test: {len(images)}")
    for img in images:
        print(f"  - {img['name']}: {img['shape']}, max channel diff={img['max_diff']}")
    
    if len(images) == 0:
        print("\nERROR: No genuine RGB images available!")
        print("Cannot proceed with variant testing.")
        return False
    
    # Test all variants
    all_results = []
    
    for variant_name, checkpoint_path in CHECKPOINTS.items():
        if not checkpoint_path.exists():
            print(f"\nWARNING: Checkpoint not found: {checkpoint_path}")
            continue
        
        variant_results = test_variant(variant_name, checkpoint_path, images)
        all_results.extend(variant_results)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r['passed'])
    
    print(f"\nTotal tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Pass rate: {passed_tests/total_tests*100:.1f}%")
    
    # Per-variant summary
    print(f"\nPer-variant summary:")
    for variant in CHECKPOINTS.keys():
        variant_results = [r for r in all_results if r['variant'] == variant]
        if variant_results:
            variant_passed = sum(1 for r in variant_results if r['passed'])
            print(f"  {variant}: {variant_passed}/{len(variant_results)} passed")
    
    # Write per-image per-variant CSV
    csv_file = OUT / "rgb_per_image_per_variant.csv"
    with open(csv_file, 'w', newline='') as f:
        fieldnames = [
            "variant", "image", "shape", "checkpoint", "patch_size", "residual",
            "params", "bpp", "psnr", "ssim", "mae", "bit_acc",
            "pipeline_perfect", "exact_rgb", "all_channels_exact", "all_payloads_exact",
            "passed", "elapsed_seconds"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row)
    
    print(f"\nPer-image per-variant CSV: {csv_file}")
    
    # Write summary CSV
    summary_file = OUT / "rgb_variant_summary.csv"
    with open(summary_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["variant", "checkpoint", "patch_size", "residual", "params",
                        "images_tested", "images_passed", "pass_rate", "total_time_seconds"])
        
        for variant in CHECKPOINTS.keys():
            variant_results = [r for r in all_results if r['variant'] == variant]
            if variant_results:
                passed = sum(1 for r in variant_results if r['passed'])
                total_time = sum(r.get('elapsed_seconds', 0) for r in variant_results)
                writer.writerow([
                    variant,
                    variant_results[0]['checkpoint'],
                    variant_results[0]['patch_size'],
                    variant_results[0]['residual'],
                    variant_results[0]['params'],
                    len(variant_results),
                    passed,
                    f"{passed/len(variant_results)*100:.1f}%",
                    f"{total_time:.1f}"
                ])
    
    print(f"Variant summary CSV: {summary_file}")
    
    # Write detailed log
    log_file = OUT / "rgb_variant_test_log.txt"
    with open(log_file, 'w') as f:
        f.write(f"RGB Variant Test Log\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Images tested: {len(images)}\n")
        f.write(f"Variants tested: {len(CHECKPOINTS)}\n\n")
        
        f.write("Images:\n")
        for img in images:
            f.write(f"  {img['name']}: {img['shape']}\n")
        
        f.write("\nResults:\n")
        for r in all_results:
            f.write(f"\n{r['variant']} on {r['image']}:\n")
            f.write(f"  Status: {'PASS' if r['passed'] else 'FAIL'}\n")
            f.write(f"  BPP: {r['bpp']:.6f}\n" if r['bpp'] is not None else "  BPP: N/A\n")
            f.write(f"  Exact RGB: {r['exact_rgb']}\n" if r['exact_rgb'] is not None else "  Exact RGB: N/A\n")
            f.write(f"  Pipeline perfect: {r['pipeline_perfect']}\n" if r['pipeline_perfect'] is not None else "  Pipeline perfect: N/A\n")
            f.write(f"  Bit accuracy: {r['bit_acc']:.2f}%\n" if r['bit_acc'] is not None else "  Bit accuracy: N/A\n")
            if r.get('error'):
                f.write(f"  Error: {r['error']}\n")
    
    print(f"Detailed log: {log_file}")
    
    # Overall verdict
    print(f"\n{'='*70}")
    if passed_tests == total_tests:
        print("ALL TESTS PASSED")
        print("All 5 CNN variants correctly process genuine RGB images")
        print("with exact reconstruction and bit-accurate payload recovery.")
    else:
        print(f"PARTIAL RESULTS: {passed_tests}/{total_tests} passed")
    print(f"{'='*70}")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
