#!/usr/bin/env python3
"""Test v5_patch7 only"""

import sys
import csv
import numpy as np
from pathlib import Path
from PIL import Image
import time

BASE = Path("/home/parzifal/RDHEI_Project")
sys.path.insert(0, str(BASE))

from src.rdhei_color import run_rdhei_color
from src.cnn_model import load_model

OUT = Path("/home/parzifal/RDHEI_Project/results/rgb_validation_20261013")
DATA_DIR = BASE / "data/kodak_color"

CHECKPOINT = BASE / "RDHEI_FIXED_V1/models/v5_patch7.pth"

KEY = b'k' * 16
NONCE = 0
SEED = 42
DEVICE = "cpu"

def get_images():
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
                    images.append({"path": path, "name": path.name, "arr": arr})
    return images

def main():
    print("Testing v5_patch7...")
    images = get_images()
    
    # Load existing results
    existing_results = []
    csv_path = OUT / "rgb_per_image_per_variant.csv"
    if csv_path.exists():
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_results.append(row)
    
    existing_variants = set(r['variant'] for r in existing_results)
    print(f"Existing variants: {existing_variants}")
    
    if "v5_patch7" in existing_variants:
        print("v5_patch7 already completed, skipping")
        return
    
    all_results = list(existing_results)
    
    print(f"\n{'='*60}")
    print(f"Testing v5_patch7")
    print(f"{'='*60}")
    
    model, patch_size, residual, params = load_model(CHECKPOINT, device=DEVICE)
    print(f"Patch: {patch_size}x{patch_size}, Params: {params:,}")
    
    for img in images:
        print(f"  {img['name']}... ", end="", flush=True)
        start = time.time()
        
        result = run_rdhei_color(
            image_rgb=img['arr'],
            key=KEY,
            nonce=NONCE,
            method="cnn",
            model=model,
            device=DEVICE,
            patch_size=patch_size,
            seed=SEED
        )
        
        elapsed = time.time() - start
        exact_rgb = np.array_equal(img['arr'], result['recovered'])
        passed = exact_rgb and result['perfect'] and result['bit_acc'] == 100.0
        
        row = {
            "variant": "v5_patch7",
            "image": img['name'],
            "shape": f"{img['arr'].shape[0]}x{img['arr'].shape[1]}x{img['arr'].shape[2]}",
            "bpp": result['bpp'],
            "psnr": "inf" if np.isfinite(result['psnr_rec']) else result['psnr_rec'],
            "ssim": result['ssim_rec'],
            "mae": result['mae_rec'],
            "bit_acc": result['bit_acc'],
            "pipeline_perfect": result['perfect'],
            "exact_rgb": exact_rgb,
            "passed": passed,
            "elapsed_seconds": elapsed
        }
        all_results.append(row)
        
        status = "PASS" if passed else "FAIL"
        print(f"{status} ({elapsed:.1f}s, BPP={result['bpp']:.2f})")
    
    # Save results
    with open(csv_path, 'w', newline='') as f:
        fieldnames = ["variant", "image", "shape", "bpp", "psnr", "ssim", "mae", 
                     "bit_acc", "pipeline_perfect", "exact_rgb", "passed", "elapsed_seconds"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Completed: {datetime.now().isoformat()}")

if __name__ == "__main__":
    from datetime import datetime
    main()
