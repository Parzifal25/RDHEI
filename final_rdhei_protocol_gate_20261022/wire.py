"""EDR2 wire codec and encrypted-domain hider. No Torch/model dependency."""
import hashlib
import hmac
import struct
import zlib

import numpy as np
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF

HEADER = struct.Struct(">4sB3sIQ")
HEADER_BYTES = HEADER.size
TAG_BYTES = 32
PROTOCOL_MAGIC = b"EDR2"
PROTOCOL_ID = b"EDR2"
SAFE_ZONE_STEP = 2
PREDICTOR_RADIUS = 1
SAFE_ZONE_BORDER = PREDICTOR_RADIUS


def allocation(e):
    """Return (replaceable_MSB_count, admissible_error_lower, upper)."""
    n = 0
    for r in range(7, 0, -1):
        low, mid, high = 2 ** (r - 1) - 1, 2 ** (r - 1), 2 ** r - 1
        if e <= low:
            n += 1
        elif mid < e <= high:
            return n + 1, mid + 1, high
        elif e == mid:
            return n, mid, mid
    return n, 0, 0


BOOK = np.array(sorted({allocation(e) for e in range(256)}), dtype=np.int32)


def grid(shape):
    """Maximum-density square lattice with no mutable center in another 3x3 patch."""
    if len(shape) != 2:
        raise ValueError("grayscale only")
    y, x = np.meshgrid(
        np.arange(SAFE_ZONE_BORDER, shape[0] - SAFE_ZONE_BORDER, SAFE_ZONE_STEP),
        np.arange(SAFE_ZONE_BORDER, shape[1] - SAFE_ZONE_BORDER, SAFE_ZONE_STEP),
        indexing="ij",
    )
    return y.ravel(), x.ravel()


def keys(master, nonce):
    """Derive image and hider roots exclusively from the receiver's K and V."""
    if not isinstance(master, (bytes, bytearray)) or len(master) != 32:
        raise ValueError("expected a 32-byte master key")
    if not isinstance(nonce, int) or not 0 <= nonce < 2**128:
        raise ValueError("expected a uint128 nonce")
    salt = nonce.to_bytes(16, "big")
    root = HKDF(bytes(master), 32, salt, SHA256, context=PROTOCOL_ID + b"/master-root")
    return {
        "image": HKDF(root, 32, b"", SHA256, context=PROTOCOL_ID + b"/image-encryption"),
        "hider": HKDF(root, 32, b"", SHA256, context=PROTOCOL_ID + b"/data-hiding-master"),
    }


def hider_keys(hider_key):
    """Derive independent header-stage, directory, payload and authentication keys."""
    if not isinstance(hider_key, (bytes, bytearray)) or len(hider_key) != 32:
        raise ValueError("expected one 32-byte data-hiding capability key")
    master = bytes(hider_key)
    domains = ("header-bootstrap", "header-final", "directory", "payload", "auth")
    return {
        domain.replace("-", "_"): HKDF(
            master, 32, b"", SHA256,
            context=PROTOCOL_ID + b"/hider/" + domain.encode("ascii"),
        )
        for domain in domains
    }


def crypt(data, key):
    """AES-256-CTR transform under one domain-separated, packet-specific key."""
    return AES.new(key, AES.MODE_CTR, nonce=b"", initial_value=0).encrypt(data)


def slots(shape, labels, h):
    y, x = grid(shape)
    pixels, shifts = [], []
    for i in range(h, len(y)):
        n = int(BOOK[labels[i], 0])
        pixels.extend([int(y[i] * shape[1] + x[i])] * n)
        shifts.extend(range(7, 7 - n, -1))
    return np.asarray(pixels, dtype=np.int64), np.asarray(shifts, dtype=np.uint8)


def readbits(a, positions):
    pixels, shifts = positions
    return (a.ravel()[pixels] >> shifts) & 1


def writebits(a, positions, bits):
    pixels, shifts = positions
    if len(bits) != len(pixels):
        raise ValueError("slot length")
    flat = a.ravel()
    for p, s, b in zip(pixels, shifts, bits):
        mask = 1 << int(s)
        flat[p] = (int(flat[p]) & (255 ^ mask)) | (int(b) << int(s))


def _header_key(capability, header_stage):
    if header_stage == "bootstrap":
        name = "header_bootstrap"
    elif header_stage == "final":
        name = "header_final"
    else:
        raise ValueError("header_stage must be 'bootstrap' or 'final'")
    try:
        return capability[name]
    except KeyError as exc:
        raise ValueError(f"missing {name} key") from exc


def encode_header(mode, directory_length, payload_length, capability, header_stage):
    if mode not in (0, 1):
        raise ValueError("invalid directory codec")
    if not 0 <= directory_length < 2**32:
        raise ValueError("directory too large")
    if not 0 <= payload_length < 2**64:
        raise ValueError("payload length outside uint64")
    plain = HEADER.pack(PROTOCOL_MAGIC, mode, b"\\x00\\x00\\x00", directory_length, payload_length)
    return crypt(plain, _header_key(capability, header_stage))


def framing(a, capability, header_stage="final"):
    """Read fixed-size encrypted header, then bound the in-band directory/tag region."""
    if a.dtype != np.uint8 or a.ndim != 2:
        raise ValueError("expected uint8 grayscale")
    y, x = grid(a.shape)
    if len(y) < HEADER_BYTES:
        raise ValueError("too few candidates for header")
    encrypted_header = a[y[:HEADER_BYTES], x[:HEADER_BYTES]].tobytes()
    raw = crypt(encrypted_header, _header_key(capability, header_stage))
    magic, mode, reserved, length, plen = HEADER.unpack(raw)
    h = HEADER_BYTES + length + TAG_BYTES
    if (magic != PROTOCOL_MAGIC or mode not in (0, 1)
            or reserved != b"\\x00\\x00\\x00" or h >= len(y)):
        raise ValueError("invalid encrypted header, reserved bytes, or directory bound")
    return y, x, mode, length, plen, h


def tag(a, capability, header_stage="final"):
    y, x, _, length, _, h = framing(a, capability, header_stage)
    buf = a.copy()
    buf[y[HEADER_BYTES + length:h], x[HEADER_BYTES + length:h]] = 0
    return hmac.new(
        capability["auth"],
        struct.pack(">QQ", *a.shape) + buf.tobytes(),
        hashlib.sha256,
    ).digest()


def seal(a, capability, header_stage="final"):
    y, x, _, length, _, h = framing(a, capability, header_stage)
    a[y[HEADER_BYTES + length:h], x[HEADER_BYTES + length:h]] = np.frombuffer(
        tag(a, capability, header_stage), np.uint8
    )


def inspect(a, capability, header_stage="final"):
    y, x, mode, length, plen, h = framing(a, capability, header_stage)
    actual = a[y[HEADER_BYTES + length:h], x[HEADER_BYTES + length:h]].tobytes()
    expected_tag = tag(a, capability, header_stage)
    if not hmac.compare_digest(actual, expected_tag):
        raise ValueError("authentication failed")

    # Directory decryption and decompression occur only after packet authentication.
    enc = a[y[HEADER_BYTES:HEADER_BYTES + length], x[HEADER_BYTES:HEADER_BYTES + length]].tobytes()
    data = crypt(enc, capability["directory"])
    expected = (len(y) + 1) // 2
    if mode:
        dec = zlib.decompressobj()
        raw = dec.decompress(data, expected + 1)
        if len(raw) != expected or not dec.eof or dec.unused_data or dec.unconsumed_tail:
            raise ValueError("invalid bounded compressed directory")
    else:
        raw = data
    if len(raw) != expected:
        raise ValueError("directory length mismatch")

    packed = np.frombuffer(raw, np.uint8)
    labels = np.stack((packed >> 4, packed & 15), axis=1).ravel()
    if len(y) % 2 and labels[-1] != 0:
        raise ValueError("nonzero label padding")
    labels = labels[:len(y)]
    if np.any(labels >= len(BOOK)):
        raise ValueError("invalid label class")

    positions = slots(a.shape, labels, h)
    backup = 8 * h
    net = len(positions[0]) - backup
    if net <= 0 or plen > net:
        raise ValueError("invalid capacity or payload length")
    return dict(
        y=y, x=x, mode=mode, length=length, plen=plen, h=h,
        labels=labels, positions=positions, backup=backup, net=net,
    )


def embed(a, payload, capability):
    """Encrypted-domain insertion; the hider receives no image key or plaintext image."""
    q = inspect(a, capability, header_stage="bootstrap")
    payload = np.asarray(payload)
    if payload.ndim != 1 or np.any((payload != 0) & (payload != 1)):
        raise ValueError("payload must be a one-dimensional binary sequence")
    if len(payload) > q["net"]:
        raise ValueError("payload exceeds net capacity")

    plain = np.pad(payload.astype(np.uint8), (0, q["net"] - len(payload)))
    cipher = np.unpackbits(
        np.frombuffer(
            crypt(np.packbits(plain).tobytes(), capability["payload"]),
            np.uint8,
        )
    )[:q["net"]]

    out = a.copy()
    pos = tuple(v[q["backup"]:] for v in q["positions"])
    writebits(out, pos, cipher)

    # The final header has a different one-time key domain from the bootstrap
    # header, so comparing reservation and marked packets reveals no header XOR.
    final_header = encode_header(
        q["mode"], q["length"], len(payload), capability, "final"
    )
    out[q["y"][:HEADER_BYTES], q["x"][:HEADER_BYTES]] = np.frombuffer(final_header, np.uint8)
    seal(out, capability, header_stage="final")
    return out


if __name__ == "__main__":
    import json
    import sys
    import time

    if len(sys.argv) != 6:
        raise ValueError("usage: wire.py image payload data_hiding_key output audit")
    start = time.perf_counter()
    from PIL import Image
    a = np.array(Image.open(sys.argv[1]))
    payload = np.load(sys.argv[2], allow_pickle=False)
    capability = hider_keys(bytes.fromhex(sys.argv[3]))
    out = embed(a, payload, capability)
    Image.fromarray(out).save(sys.argv[4])
    result = dict(
        seconds=time.perf_counter() - start,
        model_imported="torch" in sys.modules,
        image_key_received=False,
        hider_key_received=True,
        capacity=inspect(out, capability, header_stage="final")["net"],
    )
    with open(sys.argv[5], "x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
