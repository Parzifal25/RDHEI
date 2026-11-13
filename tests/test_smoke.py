#!/usr/bin/env python3
"""
SMOKE TESTS for RDHEI_FIXED_V1
================================

These tests validate that the core repairs work correctly:
1. Encryption with unique nonces per RGB channel
2. Full pipeline round-trip (grayscale)
3. Full pipeline round-trip (RGB)
4. Payload extraction accuracy
5. Recovery correctness
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.encryption import (
    generate_key,
    encrypt_image,
    decrypt_image,
    encrypt_rgb_channels,
    decrypt_rgb_channels,
    get_channel_nonce,
    pack_metadata,
    unpack_metadata
)

from src.rdhei_core import run_rdhei
from src.rdhei_color import run_rdhei_color


def test_encryption_unique_nonces():
    """Test that RGB channels use unique nonces."""
    print("\n" + "="*60)
    print("TEST 1: Unique nonces per RGB channel")
    print("="*60)
    
    base_nonce = 100
    nonces = [get_channel_nonce(base_nonce, c) for c in range(3)]
    
    print(f"Base nonce: {base_nonce}")
    print(f"Channel nonces: R={nonces[0]}, G={nonces[1]}, B={nonces[2]}")
    
    assert len(set(nonces)) == 3, "Nonces must be unique"
    assert nonces[0] == base_nonce + 1, "R nonce should be base_nonce + 1"
    assert nonces[1] == base_nonce + 2, "G nonce should be base_nonce + 2"
    assert nonces[2] == base_nonce + 3, "B nonce should be base_nonce + 3"
    
    print("PASS: Unique nonces per channel")


def test_grayscale_roundtrip():
    """Test grayscale RDHEI pipeline end-to-end."""
    print("\n" + "="*60)
    print("TEST 2: Grayscale pipeline round-trip")
    print("="*60)
    
    np.random.seed(42)
    
    # Create test image
    img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    
    # Generate key and nonce
    key = generate_key(16)
    nonce = 42
    
    # Run pipeline
    result = run_rdhei(img, key, nonce=nonce, method="med", seed=42)
    
    # Check results
    print(f"Image shape: {img.shape}")
    print(f"Capacity: {result['capacity']} bits")
    print(f"BPP: {result['bpp']:.4f}")
    print(f"Perfect recovery: {result['perfect']}")
    print(f"Bit accuracy: {result['bit_acc']:.2f}%")
    
    # Assertions
    assert result['perfect'], "Image not perfectly recovered"
    assert result['bit_acc'] == 100.0, f"Bit accuracy not 100%: {result['bit_acc']}"
    assert np.array_equal(img, result['recovered']), "Recovery mismatch"
    assert np.array_equal(result['payload'], result['extracted']), "Payload mismatch"
    
    print(f"PSNR: {result['metrics']['psnr']}")
    print(f"SSIM: {result['metrics']['ssim']}")
    print(f"MAE: {result['metrics']['mae']}")
    
    print("PASS: Grayscale round-trip")


def test_rgb_roundtrip():
    """Test RGB RDHEI pipeline end-to-end with unique nonces."""
    print("\n" + "="*60)
    print("TEST 3: RGB pipeline round-trip with unique nonces")
    print("="*60)
    
    np.random.seed(42)
    
    # Create test RGB image
    img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
    
    # Generate key and base_nonce
    key = generate_key(16)
    base_nonce = 100
    
    # Run pipeline (now uses unique nonces per channel)
    result = run_rdhei_color(img, key, nonce=base_nonce, method="med", seed=42)
    
    # Check results
    print(f"Image shape: {img.shape}")
    print(f"BPP (avg): {result['bpp']:.4f}")
    print(f"Perfect recovery: {result['perfect']}")
    print(f"Bit accuracy: {result['bit_acc']:.2f}%")
    print(f"PSNR: {result['psnr_rec']}")
    print(f"SSIM: {result['ssim_rec']}")
    print(f"MAE: {result['mae_rec']}")
    
    print("\nPer-channel results:")
    for ch in result['per_channel']:
        print(f"  {ch['channel']}: BPP={ch['bpp']:.4f}, nonce={ch['nonce_used']}, perfect={ch['perfect']}")
    
    # Assertions
    assert result['perfect'], "Image not perfectly recovered"
    assert result['bit_acc'] == 100.0, f"Bit accuracy not 100%: {result['bit_acc']}"
    assert np.array_equal(img, result['recovered']), "Recovery mismatch"
    
    # Verify unique nonces were used
    nonces_used = [ch['nonce_used'] for ch in result['per_channel']]
    assert len(set(nonces_used)) == 3, "Nonces should be unique per channel"
    print(f"\nNonces used: {nonces_used}")
    
    print("PASS: RGB round-trip with unique nonces")


def test_metadata_pack_unpack():
    """Test metadata packing/unpacking."""
    print("\n" + "="*60)
    print("TEST 4: Metadata pack/unpack")
    print("="*60)
    
    base_nonce = 12345
    key_size = 16
    
    packed = pack_metadata(base_nonce, key_size)
    print(f"Packed metadata: {packed.hex()} ({len(packed)} bytes)")
    
    unpacked = unpack_metadata(packed)
    print(f"Unpacked: base_nonce={unpacked['base_nonce']}, key_size={unpacked['key_size']}")
    
    assert unpacked['base_nonce'] == base_nonce
    assert unpacked['key_size'] == key_size
    
    print("PASS: Metadata pack/unpack")


def test_edge_cases():
    """Test edge cases."""
    print("\n" + "="*60)
    print("TEST 5: Edge cases")
    print("="*60)
    
    key = generate_key(16)
    
    # Test 1: Constant image
    print("\n5a: Constant image")
    img = np.full((32, 32), 128, dtype=np.uint8)
    result = run_rdhei(img, key, nonce=0, method="med", seed=42)
    assert result['perfect'], "Constant image not recovered"
    print(f"  Constant image: capacity={result['capacity']}, BPP={result['bpp']:.4f}, perfect={result['perfect']}")
    
    # Test 2: Gradient image
    print("\n5b: Gradient image")
    img = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
    result = run_rdhei(img, key, nonce=1, method="med", seed=42)
    assert result['perfect'], "Gradient image not recovered"
    print(f"  Gradient image: capacity={result['capacity']}, BPP={result['bpp']:.4f}, perfect={result['perfect']}")
    
    # Test 3: Image with extreme values
    print("\n5c: Extreme values image")
    img = np.zeros((32, 32), dtype=np.uint8)
    img[0, 0] = 0
    img[1, 1] = 255
    result = run_rdhei(img, key, nonce=2, method="med", seed=42)
    assert result['perfect'], "Extreme values image not recovered"
    print(f"  Extreme values: capacity={result['capacity']}, BPP={result['bpp']:.4f}, perfect={result['perfect']}")
    
    print("\nPASS: Edge cases")


def run_all_tests():
    """Run all smoke tests."""
    print("\n" + "#"*60)
    print("# RDHEI_FIXED_V1 SMOKE TESTS")
    print("#"*60)
    
    tests = [
        ("Encryption unique nonces", test_encryption_unique_nonces),
        ("Grayscale round-trip", test_grayscale_roundtrip),
        ("RGB round-trip", test_rgb_roundtrip),
        ("Metadata pack/unpack", test_metadata_pack_unpack),
        ("Edge cases", test_edge_cases),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "PASS", None))
        except Exception as e:
            print(f"\nFAIL: {name}")
            import traceback
            traceback.print_exc()
            results.append((name, "FAIL", str(e)))
    
    print("\n" + "#"*60)
    print("# TEST SUMMARY")
    print("#"*60)
    
    for name, status, error in results:
        status_symbol = "PASS" if status == "PASS" else "FAIL"
        print(f"{status_symbol}: {name}")
        if error:
            print(f"  Error: {error}")
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    return all(status == "PASS" for _, status, _ in results)


if __name__ == "__main__":
    import numpy as np
    success = run_all_tests()
    sys.exit(0 if success else 1)
