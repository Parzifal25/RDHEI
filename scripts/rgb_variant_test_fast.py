#!/usr/bin/env python3
"""
RGB Validation — 5-Variant Test (Fast Version)

Test all 5 variants but with better progress reporting and 
ability to continue if interrupted.
"""

import sys
import csv
import numpy as np
from pathlib import Path
from PIL import Image
from datetime import datetime
import time
import signal

# Setup paths
BASE = Path("/home/parzifal/RDHEI_Project")
sys.path.insert(0, str(BASE))

from src.rdhei_color import run_rdhei_color
from src.cnn_model import load_model

OUT = Path("/home/parzifal/RDHEI_Project/results/rgb_validation_20261013")
OUT.mkdir(parents=True, exist_ok=True)

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

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Image test timed out")

def get_genuine_rgb_images():
    images = []
    for path in sorted(DATA_DIR.glob("*.png")):
        if path.name.endswith(":Zone.Identifier"):
            continue
        with Image.open(path) as img:
            if img.mode == "RGB":
                arr = np.array(img)
                r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
                max_diff = max(
                    np.max(np.abs(r.astype(int) - g.astype(int))),
                    np.max(np.abs(g.astype(int) - b.astype(int))),
                    np.max(np.abs(r.astype(int) - b.astype(int)))
                )
                if max_diff > 0:
                    images.append({"path": path, "name": path.name, "shape": arr.shape})
    return images

def test_single_image(variant_name, model, patch_size, image_rgb, image_name):
    """Test single image with timeout."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(300)  # 5 minute timeout per image
    
    try:
        start = time.time()
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
        elapsed = time.time() - start
        signal.alarm(0)  # Cancel alarm
        
        exact_rgb = np.array_equal(image_rgb, result['recovered'])
        passed = exact_rgb and result['perfect'] and result['bit_acc'] == 100.0
        
        return {
            "variant": variant_name,
            "image": image_name,
            "shape": f"{image_rgb.shape[0]}x{image_rgb.shape[1]}x{image_rgb.shape[2]}",
            "bpp": result['bpp'],
            "psnr": result['psnr_rec'] if np.isfinite(result['psnr_rec']) else "inf",
            "ssim": result['ssim_rec'],
            "mae": result['mae_rec'],
            "bit_acc": result['bit_acc'],
            "pipeline_perfect": result['perfect'],
            "exact_rgb": exact_rgb,
            "passed": passed,
            "elapsed_seconds": elapsed
        }
    except TimeoutException:
        signal.alarm(0)
        return {
            "variant": variant_name,
            "image": image_name,
            "shape": f"{image_rgb.shape[0]}x{image_rgb.shape[1]}x{image_rgb.shape[2]}",
            "bpp": None,
            "psnr": None,
            "ssim": None,
            "mae": None,
            "bit_acc": None,
            "pipeline_perfect": None,
            "exact_rgb": None,
            "passed": False,
            "elapsed_seconds": 300,
            "error": "TIMEOUT"
        }
    except Exception as e:
        signal.alarm(0)
        return {
            "variant": variant_name,
            "image": image_name,
            "shape": f"{image_rgb.shape[0]}x{image_rgb.shape[1]}x{image_rgb.shape[2]}",
            "bpp": None,
            "psnr": None,
            "ssim": None,
            "mae": None,
            "bit_acc": None,
            "pipeline_perfect": None,
            "exact_rgb": None,
            "passed": False,
            "elapsed_seconds": 0,
            "error": str(e)
        }

def main():
    print("="*70)
    print("RGB 5-VARIANT TEST")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*70)
    
    images = get_genuine_rgb_images()
    print(f"\nGenuine RGB images: {len(images)}")
    for img in images:
        print(f"  - {img['name']}")
    
    all_results = []
    
    # Test each variant
    for variant_name, checkpoint_path in CHECKPOINTS.items():
        if not checkpoint_path.exists():
            print(f"\n[SKIP] Checkpoint not found: {checkpoint_path.name}")
            continue
        
        print(f"\n{'='*70}")
        print(f"Variant: {variant_name}")
        print(f"{'='*70}")
        
        try:
            model, patch_size, residual, params = load_model(checkpoint_path, device=DEVICE)
            print(f"  Patch: {patch_size}x{patch_size}, Residual: {residual}, Params: {params:,}")
        except Exception as e:
            print(f"  ERROR loading model: {e}")
            continue
        
        variant_start = time.time()
        variant_results = []
        
        for img in images:
            print(f"  Testing {img['name']}... ", end="", flush=True)
            
            with Image.open(img['path']) as pil_img:
                image_rgb = np.array(pil_img)
            
            result = test_single_image(variant_name, model, patch_size, image_rgb, img['name'])
            variant_results.append(result)
            
            if result['passed']:
                print(f"PASS ({result['elapsed_seconds']:.1f}s, BPP={result['bpp']:.2f})")
            elif result.get('error') == 'TIMEOUT':
                print(f"TIMEOUT")
            else:
                print(f"FAIL/error")
        
        variant_time = time.time() - variant_start
        passed = sum(1 for r in variant_results if r['passed'])
        print(f"\n  {variant_name}: {passed}/{len(variant_results)} passed ({variant_time:.1f}s total)")
        
        all_results.extend(variant_results)
        
        # Save progress after each variant
        csv_file = OUT / "rgb_per_image_per_variant.csv"
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ["variant", "image", "shape", "bpp", "psnr", "ssim", "mae", 
                         "bit_acc", "pipeline_perfect", "exact_rgb", "passed", "elapsed_seconds"]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for r in all_results:
                writer.writerow(r)
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    
    total = len(all_results)
    passed = sum(1 for r in all_results if r['passed'])
    
    print(f"\nTotal: {total} tests, {passed} passed ({passed/total*100:.1f}%)")
    
    for variant in CHECKPOINTS.keys():
        v_results = [r for r in all_results if r['variant'] == variant]
        if v_results:
            v_passed = sum(1 for r in v_results if r['passed'])
            print(f"  {variant}: {v_passed}/{len(v_results)}")
    
    # Final CSV
    csv_file = OUT / "rgb_per_image_per_variant.csv"
    with open(csv_file, 'w', newline='') as f:
        fieldnames = ["variant", "image", "shape", "bpp", "psnr", "ssim", "mae", 
                     "bit_acc", "pipeline_perfect", "exact_rgb", "passed", "elapsed_seconds"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)
    
    print(f"\nResults CSV: {csv_file}")
    print(f"Completed: {datetime.now().isoformat()}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
