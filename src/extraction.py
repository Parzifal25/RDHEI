import numpy as np
from src.embedding  import extract_and_recover, bits_to_bytes
from src.encryption import decrypt_image


# ── Header encode / decode ────────────────────────────────────────────────

HEADER_BITS = 32   # 16 for length + 8 for T + 8 for method

def encode_header(payload_len: int, threshold: int, method_flag: int) -> np.ndarray:
    """Pack (payload_len, T, method) into 32 bits."""
    bits = []
    for i in range(15, -1, -1):
        bits.append((payload_len >> i) & 1)
    for i in range(7, -1, -1):
        bits.append((threshold >> i) & 1)
    for i in range(7, -1, -1):
        bits.append((method_flag >> i) & 1)
    return np.array(bits, dtype=np.uint8)


def decode_header(bits: np.ndarray):
    """Unpack 32-bit header → (payload_len, threshold, method_flag)."""
    payload_len  = int("".join(str(b) for b in bits[0:16]),  2)
    threshold    = int("".join(str(b) for b in bits[16:24]), 2)
    method_flag  = int("".join(str(b) for b in bits[24:32]), 2)
    return payload_len, threshold, method_flag


# ── Full extraction (receiver only needs key + nonce + stego) ─────────────

def full_extraction(stego_encrypted: np.ndarray,
                    key:   bytes,
                    nonce: int = 0,
                    # Legacy params kept for backward compat (ignored if header present)
                    payload_len: int = None,
                    threshold:   int = None,
                    method:      str = "med",
                    model=None,
                    device: str = "cpu") -> dict:
    """
    Receiver pipeline — only key, nonce, stego_encrypted required.

    Steps:
      1. AES-CTR decrypt → plaintext stego
      2. Extract 32-bit header → learns payload_len, T, method automatically
      3. Extract payload bits + recover original image
    """
    # Step 1: decrypt
    stego_plain = decrypt_image(stego_encrypted, key, nonce)

    # Step 2: extract header (first 32 bits)
    header_bits, _ = extract_and_recover(
        stego_plain, pred=None,
        payload_len=HEADER_BITS,
        threshold=threshold if threshold else 1,   # header always uses T=1 band
        method="med"
    )

    # If caller passed explicit params (old API), use those; else decode header
    if payload_len is not None and threshold is not None:
        pl   = payload_len
        T    = threshold
        meth = method
    else:
        pl, T, mflag = decode_header(header_bits)
        meth = "cnn" if mflag == 1 else "med"

    # Step 3: full extraction
    extracted_bits, recovered = extract_and_recover(
        stego_plain,
        pred=None,
        payload_len=pl,
        threshold=T,
        method="med",     # MED is always used for the causal scan
        model=model,
        device=device,
    )

    return {
        "extracted_bits":     extracted_bits,
        "extracted_bytes":    bits_to_bytes(extracted_bits),
        "stego_plaintext":    stego_plain,
        "recovered_original": recovered,
        "payload_len":        pl,
        "threshold":          T,
    }