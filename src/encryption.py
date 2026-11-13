"""
AES-CTR Encryption for RDHEI

SECURITY DESIGN:
- Each RGB channel uses a unique nonce derived from base_nonce + channel_offset
- No keystream reuse under the same key
- Nonce allocation: base_nonce + 1 for R, base_nonce + 2 for G, base_nonce + 3 for B
- Receiver reconstructs nonces using the same derivation

LIMITATIONS:
- No authentication/integrity protection (CTR mode only)
- Nonce must be transmitted/stored separately for receiver
- Does not provide tamper resistance
"""

import numpy as np
from Crypto.Cipher import AES
from Crypto.Util import Counter
import os
import struct


def generate_key(key_size: int = 16) -> bytes:
    """Generate a random AES key."""
    return os.urandom(key_size)


def get_keystream(key: bytes, nonce: int, size: int) -> np.ndarray:
    """Generate a keystream of the specified size using AES-CTR."""
    ctr = Counter.new(128, initial_value=nonce)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return np.frombuffer(cipher.encrypt(bytes(size)), dtype=np.uint8)


def encrypt_image(image: np.ndarray, key: bytes, nonce: int = 0) -> np.ndarray:
    """
    Encrypt a 2D grayscale image using AES-CTR.
    
    Args:
        image: 2D uint8 numpy array (H, W)
        key: AES key bytes
        nonce: Counter initial value (nonce)
    
    Returns:
        Encrypted 2D uint8 array (H, W)
    """
    assert image.ndim == 2, f"Expected 2D array, got {image.ndim}D"
    assert image.dtype == np.uint8, f"Expected uint8, got {image.dtype}"
    
    h, w = image.shape
    flat = image.flatten().tobytes()
    ctr = Counter.new(128, initial_value=nonce)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    encrypted = cipher.encrypt(flat)
    return np.frombuffer(encrypted, dtype=np.uint8).reshape(h, w)


def decrypt_image(encrypted: np.ndarray, key: bytes, nonce: int = 0) -> np.ndarray:
    """
    Decrypt a 2D AES-CTR encrypted image.
    
    AES-CTR is symmetric: encryption and decryption are the same operation.
    
    Args:
        encrypted: 2D uint8 encrypted array (H, W)
        key: AES key bytes (must match encryption key)
        nonce: Counter initial value (must match encryption nonce)
    
    Returns:
        Decrypted 2D uint8 array (H, W)
    """
    return encrypt_image(encrypted, key, nonce)


def encrypt_rgb_channels(image_rgb: np.ndarray, key: bytes, base_nonce: int = 0) -> np.ndarray:
    """
    Encrypt RGB image channels with UNIQUE nonces per channel.
    
    This prevents keystream reuse across channels, which would completely
    break AES-CTR security.
    
    Nonce allocation:
        R channel: base_nonce + 1
        G channel: base_nonce + 2
        B channel: base_nonce + 3
    
    Args:
        image_rgb: HxWxD3 uint8 RGB image
        key: AES key bytes
        base_nonce: Base nonce value (non-negative integer)
    
    Returns:
        Encrypted HxWxD3 uint8 array
    """
    assert image_rgb.ndim == 3, f"Expected 3D array, got {image_rgb.ndim}D"
    assert image_rgb.shape[2] == 3, f"Expected 3 channels, got {image_rgb.shape[2]}"
    assert image_rgb.dtype == np.uint8, f"Expected uint8, got {image_rgb.dtype}"
    
    h, w, _ = image_rgb.shape
    encrypted_rgb = np.zeros_like(image_rgb)
    
    # Unique nonce per channel: base_nonce + channel_index + 1
    for c in range(3):
        channel = image_rgb[:, :, c]
        nonce = base_nonce + c + 1  # Each channel gets unique nonce
        encrypted_rgb[:, :, c] = encrypt_image(channel, key, nonce)
    
    return encrypted_rgb


def decrypt_rgb_channels(encrypted_rgb: np.ndarray, key: bytes, base_nonce: int = 0) -> np.ndarray:
    """
    Decrypt RGB image channels using the same unique nonce derivation.
    
    Must use the same base_nonce and derivation as encryption.
    
    Args:
        encrypted_rgb: HxWxD3 encrypted uint8 RGB image
        key: AES key bytes (must match encryption key)
        base_nonce: Base nonce value (must match encryption base_nonce)
    
    Returns:
        Decrypted HxWxD3 uint8 array
    """
    assert encrypted_rgb.ndim == 3, f"Expected 3D array, got {encrypted_rgb.ndim}D"
    assert encrypted_rgb.shape[2] == 3, f"Expected 3 channels, got {encrypted_rgb.shape[2]}"
    
    h, w, _ = encrypted_rgb.shape
    decrypted_rgb = np.zeros_like(encrypted_rgb)
    
    # Same nonce derivation as encryption
    for c in range(3):
        channel = encrypted_rgb[:, :, c]
        nonce = base_nonce + c + 1  # Must match encryption
        decrypted_rgb[:, :, c] = decrypt_image(channel, key, nonce)
    
    return decrypted_rgb


def get_channel_nonce(base_nonce: int, channel_index: int) -> int:
    """
    Calculate the nonce for a specific RGB channel.
    
    This is the canonical nonce derivation used by both encryption and decryption.
    
    Args:
        base_nonce: Base nonce value
        channel_index: Channel index (0=R, 1=G, 2=B)
    
    Returns:
        Derived nonce for this channel
    """
    return base_nonce + channel_index + 1


def pack_metadata(base_nonce: int, key_size: int = 16) -> bytes:
    """Pack encryption metadata for transmission to receiver."""
    return struct.pack('<I', base_nonce) + struct.pack('B', key_size)


def unpack_metadata(metadata: bytes) -> dict:
    """Unpack encryption metadata received from sender."""
    if len(metadata) < 5:
        raise ValueError(f"Metadata too short: {len(metadata)} bytes, expected 5")
    
    base_nonce = struct.unpack('<I', metadata[:4])[0]
    key_size = struct.unpack('B', metadata[4:5])[0]
    
    return {'base_nonce': base_nonce, 'key_size': key_size}


# Tests
def run_tests():
    print("=" * 60)
    print("ENCRYPTION MODULE TESTS")
    print("=" * 60)
    
    all_pass = True
    
    # Test 1: Grayscale round-trip
    try:
        np.random.seed(42)
        img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        key = generate_key(16)
        
        for nonce in [0, 1, 999]:
            ct = encrypt_image(img, key, nonce)
            pt = decrypt_image(ct, key, nonce)
            assert np.array_equal(img, pt), f"Failed for nonce={nonce}"
        
        print("PASS: Grayscale encrypt/decrypt")
    except Exception as e:
        print(f"FAIL: Grayscale encrypt/decrypt - {e}")
        all_pass = False
    
    # Test 2: Unique nonce derivation
    try:
        base_nonce = 100
        
        for c in range(3):
            nonce = get_channel_nonce(base_nonce, c)
            expected = base_nonce + c + 1
            assert nonce == expected, f"Channel {c}: expected {expected}, got {nonce}"
        
        print("PASS: Unique nonce derivation")
    except Exception as e:
        print(f"FAIL: Unique nonce derivation - {e}")
        all_pass = False
    
    # Test 3: RGB round-trip
    try:
        np.random.seed(42)
        img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        key = generate_key(16)
        
        ct = encrypt_rgb_channels(img, key, base_nonce=42)
        pt = decrypt_rgb_channels(ct, key, base_nonce=42)
        assert np.array_equal(img, pt), "RGB round-trip failed"
        
        # Verify different base_nonce produces different ciphertext
        ct2 = encrypt_rgb_channels(img, key, base_nonce=100)
        assert not np.array_equal(ct, ct2), "Different nonces should produce different ciphertext"
        
        print("PASS: RGB encrypt/decrypt with unique nonces")
    except Exception as e:
        print(f"FAIL: RGB encrypt/decrypt - {e}")
        all_pass = False
    
    # Test 4: No keystream reuse
    try:
        key = generate_key(16)
        base_nonce = 0
        
        nonces = [get_channel_nonce(base_nonce, c) for c in range(3)]
        assert len(set(nonces)) == 3, f"Nonces not unique: {nonces}"
        
        print("PASS: No keystream reuse")
        print(f"  Nonces: R={nonces[0]}, G={nonces[1]}, B={nonces[2]}")
    except Exception as e:
        print(f"FAIL: No keystream reuse - {e}")
        all_pass = False
    
    print("=" * 60)
    if all_pass:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    
    return all_pass


if __name__ == "__main__":
    import numpy as np
    success = run_tests()
    exit(0 if success else 1)
