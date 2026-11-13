#!/usr/bin/env python3
"""
RGB Validation Task — Smoke Test

Run a genuine RGB smoke test through the actual run_rdhei_color() pipeline
using an existing compatible checkpoint. Verify:
- Exact RGB reconstruction with np.array_equal(original_rgb, recovered_rgb)
- Exact payload recovery (per-channel)

Uses v4_patch3.pth as a compatible checkpoint.
"""

import sys
import numpy as np
from pathlib import Path
from PIL import Image
from datetime import datetime

# Setup paths
BASE = Path("/home/parzifal/RDHEI_Project")
sys.path.insert(0, str(BASE))

from src.rdhei_color import run_rdhei_color
from src.cnn_model import load_model
from src.rdhei_core import run_rdhei

# Output directory
OUT = Path("/home/parzifal/RDHEI_Project/results/rgb_validation_20261013")
OUT.mkdir(parents=True, exist_ok=True)

def main():
    print("=" * 70)
    print("RGB SMOKE TEST")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Configuration
    image_path = BASE / "data/kodak_color/4.2.03.png"
    checkpoint_path = BASE / "RDHEI_FIXED_V1/models/v4_patch3.pth"
    key = b'k' * 16  # Constant key for reproducibility
    nonce = 0
    seed = 42
    device = "cpu"
    
    print(f"\nConfiguration:")
    print(f"  Image:       {image_path}")
    print(f"  Checkpoint:  {checkpoint_path}")
    print(f"  Key:         {key.hex()} (16 bytes)")
    print(f"  Nonce:       {nonce}")
    print(f"  Seed:        {seed}")
    print(f"  Device:      {device}")
    
    # Load image as RGB (verify it's already RGB first)
    print(f"\nLoading image...")
    with Image.open(image_path) as img:
        original_mode = img.mode
        print(f"  Original PIL mode: {original_mode}")
        
        # Only convert if not already RGB — we're testing genuine RGB
        if original_mode != "RGB":
            print(f"  WARNING: Converting {original_mode} to RGB (not genuine RGB test)")
            image_rgb = np.array(img.convert("RGB"))
        else:
            image_rgb = np.array(img)
    
    print(f"  Shape:       {image_rgb.shape}")
    print(f"  Dtype:       {image_rgb.dtype}")
    print(f"  Channels:    {image_rgb.shape[2] if image_rgb.ndim == 3 else 1}")
    
    # Verify it's a genuine RGB image (not grayscale in RGB clothing)
    if image_rgb.ndim == 3 and image_rgb.shape[2] == 3:
        r, g, b = image_rgb[:,:,0], image_rgb[:,:,1], image_rgb[:,:,2]
        max_diff = max(
            np.max(np.abs(r.astype(int) - g.astype(int))),
            np.max(np.abs(g.astype(int) - b.astype(int))),
            np.max(np.abs(r.astype(int) - b.astype(int)))
        )
        print(f"  Max channel diff: {max_diff}")
        if max_diff == 0:
            print("  WARNING: All channels identical — not genuine colour variation")
        else:
            print("  ✓ Genuine colour variation confirmed")
    else:
        print("  ERROR: Not a 3-channel RGB image!")
        return False
    
    # Load checkpoint
    print(f"\nLoading checkpoint: {checkpoint_path}")
    model, patch_size, has_residual, num_params = load_model(checkpoint_path, device=device)
    print(f"  Patch size:     {patch_size}")
    print(f"  Has residual:   {has_residual}")
    print(f"  Parameters:     {num_params:,}")
    
    # Run the pipeline
    print(f"\nRunning run_rdhei_color()...")
    result = run_rdhei_color(
        image_rgb=image_rgb,
        key=key,
        nonce=nonce,
        method="cnn",
        model=model,
        device=device,
        patch_size=patch_size,
        seed=seed
    )
    
    print(f"\nPipeline-reported results:")
    print(f"  BPP:           {result['bpp']:.6f}")
    print(f"  PSNR:          {result['psnr_rec']:.2f}" if np.isfinite(result['psnr_rec']) else f"  PSNR:          inf (exact match)")
    print(f"  SSIM:          {result['ssim_rec']:.6f}")
    print(f"  MAE:           {result['mae_rec']:.6f}")
    print(f"  Bit accuracy:  {result['bit_acc']:.2f}%")
    print(f"  Perfect:       {result['perfect']}")
    
    print(f"\nPer-channel results:")
    print(f"  {'Channel':<8} {'BPP':<12} {'Capacity':<12} {'Perfect':<10} {'Bit Acc':<10} {'Nonce':<6}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*10} {'-'*10} {'-'*6}")
    for ch in result['per_channel']:
        print(f"  {ch['channel']:<8} {ch['bpp']:<12.6f} {ch['capacity']:<12} {str(ch['perfect']):<10} {ch['bit_acc']:<10.2f}")
    
    # Independent verification
    print(f"\n" + "=" * 70)
    print("INDEPENDENT VERIFICATION")
    print("=" * 70)
    
    # 1. Exact RGB reconstruction check
    print(f"\n1. EXACT RGB RECONSTRUCTION")
    print(f"   np.array_equal(original_rgb, recovered_rgb):")
    exact_match = np.array_equal(image_rgb, result['recovered'])
    print(f"   Result: {exact_match}")
    
    if not exact_match:
        diff = np.abs(image_rgb.astype(int) - result['recovered'].astype(int))
        print(f"   Max absolute difference: {np.max(diff)}")
        print(f"   Pixels differing: {np.sum(diff > 0)} / {image_rgb.size}")
        # Show where differences are
        diff_mask = diff > 0
        if np.any(diff_mask):
            coords = np.where(diff_mask)
            print(f"   First 5 differing pixels:")
            for i in range(min(5, len(coords[0]))):
                y, x, c = coords[0][i], coords[1][i], coords[2][i]
                print(f"     [{y},{x},{c}]: original={image_rgb[y,x,c]}, recovered={result['recovered'][y,x,c]}")
    else:
        print(f"   ✓ EXACT MATCH CONFIRMED")
    
    # 2. Per-channel exact checks
    print(f"\n2. PER-CHANNEL VERIFICATION")
    h, w, _ = image_rgb.shape
    
    all_channels_pass = True
    for c, ch_name in enumerate(['R', 'G', 'B']):
        print(f"\n   Channel {ch_name} (nonce={c+1}, seed={seed+c}):")
        
        # Run per-channel independently
        channel_original = image_rgb[:, :, c]
        channel_nonce = nonce + c + 1  # Match the derivation used in run_rdhei_color
        channel_seed = seed + c
        
        channel_result = run_rdhei(
            image=channel_original,
            key=key,
            nonce=channel_nonce,
            method="cnn",
            model=model,
            device=device,
            patch_size=patch_size,
            seed=channel_seed
        )
        
        # Check exact image recovery
        channel_exact = np.array_equal(channel_original, channel_result['recovered'])
        print(f"     np.array_equal(channel_original, recovered): {channel_exact}")
        
        # Check exact payload recovery
        payload_exact = np.array_equal(channel_result['payload'], channel_result['extracted'])
        print(f"     np.array_equal(payload, extracted): {payload_exact}")
        print(f"     Payload length: {len(channel_result['payload'])}")
        print(f"     Extracted length: {len(channel_result['extracted'])}")
        print(f"     Perfect: {channel_result['perfect']}")
        print(f"     Bit accuracy: {channel_result['bit_acc']:.2f}%")
        
        if not channel_exact:
            all_channels_pass = False
            diff = np.sum(channel_original != channel_result['recovered'])
            print(f"     ✗ {diff} pixels differ")
        if not payload_exact:
            all_channels_pass = False
            diff_bits = np.sum(channel_result['payload'] != channel_result['extracted'])
            print(f"     ✗ {diff_bits} bits differ")
    
    # Overall verdict
    print(f"\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    
    smoke_passed = exact_match and all_channels_pass and result['perfect'] and result['bit_acc'] == 100.0
    
    print(f"\n  Exact RGB reconstruction: {'PASS' if exact_match else 'FAIL'}")
    print(f"  All channels exact recovery: {'PASS' if all_channels_pass else 'FAIL'}")
    print(f"  Pipeline perfect: {result['perfect']}")
    print(f"  Pipeline bit_acc: {result['bit_acc']:.2f}%")
    
    if smoke_passed:
        print(f"\n  *** SMOKE TEST PASSED ***")
        print(f"  The RGB pipeline correctly reconstructs genuine RGB images")
        print(f"  and recovers embedded payloads bit-for-bit.")
    else:
        print(f"\n  *** SMOKE TEST FAILED ***")
    
    # Write results
    log_file = OUT / "rgb_smoke_test_log.txt"
    with open(log_file, 'w') as f:
        f.write(f"RGB Smoke Test Log\n")
        f.write(f"Date: {datetime.now().isoformat()}\n\n")
        f.write(f"Image: {image_path}\n")
        f.write(f"Original mode: {original_mode}\n")
        f.write(f"Shape: {image_rgb.shape}\n")
        f.write(f"Checkpoint: {checkpoint_path}\n")
        f.write(f"Variant: v4_patch3\n\n")
        f.write(f"Pipeline Results:\n")
        f.write(f"  BPP: {result['bpp']:.6f}\n")
        f.write(f"  Perfect: {result['perfect']}\n")
        f.write(f"  Bit accuracy: {result['bit_acc']:.2f}%\n\n")
        f.write(f"Independent Verification:\n")
        f.write(f"  Exact RGB reconstruction: {exact_match}\n")
        f.write(f"  All channels pass: {all_channels_pass}\n")
        for ch in result['per_channel']:
            f.write(f"  {ch['channel']}: perfect={ch['perfect']}, bit_acc={ch['bit_acc']:.2f}%\n")
        f.write(f"\nVerdict: {'PASS' if smoke_passed else 'FAIL'}\n")
    
    print(f"\nLog written to: {log_file}")
    
    # Write CSV
    csv_file = OUT / "rgb_smoke_test_results.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["test", "image", "checkpoint", "exact_rgb", "all_channels_pass", 
                        "pipeline_perfect", "pipeline_bit_acc", "verdict"])
        writer.writerow(["smoke_test", image_path.name, "v4_patch3.pth",
                        exact_match, all_channels_pass,
                        result['perfect'], f"{result['bit_acc']:.2f}%",
                        "PASS" if smoke_passed else "FAIL"])
    
    print(f"Results written to: {csv_file}")
    
    return smoke_passed

if __name__ == "__main__":
    import csv
    success = main()
    exit(0 if success else 1)
