#!/usr/bin/env python3
"""
RGB Validation Task — Image Inspection

Inspect the actual image files in data/kodak_color/ and determine:
- Original PIL mode
- Dimensions
- Channel count
- Whether it's a genuine RGB image (not grayscale)
- Dataset provenance where verifiable

Do NOT convert grayscale to RGB — report what's actually on disk.
"""

import numpy as np
from PIL import Image
from pathlib import Path
import csv
from datetime import datetime

DATA_DIR = Path("/home/parzifal/RDHEI_Project/data/kodak_color")
OUTPUT_DIR = Path("/home/parzifal/RDHEI_Project/results/rgb_validation_20261013")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def inspect_image(path: Path) -> dict:
    """Inspect a single image file without any conversion."""
    result = {
        "filename": path.name,
        "file_size_bytes": path.stat().st_size,
        "pil_mode": None,
        "shape": None,
        "channels": None,
        "dtype": None,
        "is_genuine_rgb": False,
        "max_inter_channel_diff": None,
        "notes": []
    }
    
    try:
        # Open WITHOUT conversion to see the actual mode
        with Image.open(path) as img:
            result["pil_mode"] = img.mode
            img.load()  # Force load
            
            arr = np.array(img)
            result["shape"] = arr.shape
            result["dtype"] = str(arr.dtype)
            
            if img.mode == "RGB":
                result["channels"] = 3
                # Check for genuine colour variation
                r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
                diff_rg = np.max(np.abs(r.astype(int) - g.astype(int)))
                diff_gb = np.max(np.abs(g.astype(int) - b.astype(int)))
                diff_rb = np.max(np.abs(r.astype(int) - b.astype(int)))
                result["max_inter_channel_diff"] = max(diff_rg, diff_gb, diff_rb)
                result["is_genuine_rgb"] = result["max_inter_channel_diff"] > 0
                if not result["is_genuine_rgb"]:
                    result["notes"].append("RGB mode but all channels identical (grayscale content)")
            elif img.mode == "L":
                result["channels"] = 1
                result["notes"].append("Grayscale mode — NOT a genuine RGB image")
            elif img.mode == "RGBA":
                result["channels"] = 4
                result["notes"].append("RGBA mode — has alpha channel")
            else:
                result["channels"] = len(arr.shape) if len(arr.shape) == 3 else 1
                result["notes"].append(f"Unknown mode {img.mode}")
                
    except Exception as e:
        result["notes"].append(f"Error loading: {e}")
    
    return result

def main():
    print("=" * 70)
    print("RGB VALIDATION TASK — IMAGE INSPECTION")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Find all PNG files (excluding :Zone.Identifier files)
    png_files = sorted([f for f in DATA_DIR.glob("*.png") 
                        if not f.name.endswith(":Zone.Identifier")])
    
    print(f"\nFound {len(png_files)} PNG files in {DATA_DIR}")
    print("-" * 70)
    
    inventory = []
    
    for path in png_files:
        print(f"\nInspecting: {path.name}")
        result = inspect_image(path)
        inventory.append(result)
        
        print(f"  File size:     {result['file_size_bytes']:,} bytes")
        print(f"  PIL mode:      {result['pil_mode']}")
        print(f"  Shape:         {result['shape']}")
        print(f"  Channels:      {result['channels']}")
        print(f"  Dtype:         {result['dtype']}")
        
        if result['is_genuine_rgb']:
            print(f"  Genuine RGB:   YES")
            print(f"  Max channel diff: {result['max_inter_channel_diff']}")
        else:
            print(f"  Genuine RGB:   NO")
        
        if result['notes']:
            for note in result['notes']:
                print(f"  Note:         {note}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    rgb_count = sum(1 for r in inventory if r['is_genuine_rgb'])
    gray_count = sum(1 for r in inventory 
                     if r['pil_mode'] == 'L' or r['pil_mode'] == 'LA')
    other_count = len(inventory) - rgb_count - gray_count
    
    print(f"\nGenuine RGB images (3-channel, colour variation): {rgb_count}")
    print(f"Grayscale images (L mode):                        {gray_count}")
    print(f"Other:                                             {other_count}")
    print(f"Total:                                             {len(inventory)}")
    
    if rgb_count == 0:
        print("\n*** NO GENUINE RGB IMAGES AVAILABLE ***")
        print("Cannot proceed with RGB validation without genuine colour images.")
        print("Dataset needed: 3-channel RGB PNG images with actual colour variation.")
    else:
        print(f"\n{rgb_count} genuine RGB images available for testing.")
    
    # Write inventory CSV
    inv_csv = OUTPUT_DIR / "rgb_dataset_inventory.csv"
    with open(inv_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "file_size_bytes", "pil_mode", "shape", 
            "channels", "dtype", "is_genuine_rgb", "max_inter_channel_diff", "notes"
        ])
        writer.writeheader()
        for r in inventory:
            row = r.copy()
            row["notes"] = "; ".join(r["notes"]) if r["notes"] else ""
            writer.writerow(row)
    
    print(f"\nInventory written to: {inv_csv}")
    
    # Write summary file
    summary = OUTPUT_DIR / "inspection_summary.txt"
    with open(summary, 'w') as f:
        f.write(f"RGB Validation Image Inspection Summary\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Data directory: {DATA_DIR}\n\n")
        f.write(f"Total PNG files: {len(inventory)}\n")
        f.write(f"Genuine RGB: {rgb_count}\n")
        f.write(f"Grayscale: {gray_count}\n\n")
        f.write("Images:\n")
        for r in inventory:
            f.write(f"  {r['filename']}:\n")
            f.write(f"    PIL mode: {r['pil_mode']}\n")
            f.write(f"    Shape: {r['shape']}\n")
            f.write(f"    Channels: {r['channels']}\n")
            f.write(f"    Genuine RGB: {r['is_genuine_rgb']}\n")
            if r['max_inter_channel_diff'] is not None:
                f.write(f"    Max channel diff: {r['max_inter_channel_diff']}\n")
            f.write("\n")
    
    print(f"Summary written to: {summary}")
    
    return rgb_count > 0, inventory

if __name__ == "__main__":
    has_rgb, inventory = main()
    exit(0 if has_rgb else 1)
