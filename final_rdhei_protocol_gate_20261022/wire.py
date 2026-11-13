"""EDR1 wire codec and encrypted-domain embedder. No Torch/model dependency."""
import hashlib
import hmac
import struct
import zlib
import numpy as np
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF

HEADER = struct.Struct('>4sB3xIQ')
TAG_BYTES = 32


def allocation(e):
    # Exact existing mapping, independent of production module imports.
    n = 0
    for r in range(7, 0, -1):
        low, mid, high = 2**(r-1)-1, 2**(r-1), 2**r-1
        if e <= low:
            n += 1
        elif mid < e <= high:
            return n+1, mid+1, high
        elif e == mid:
            return n, mid, mid
    return n, 0, 0


BOOK = np.array(sorted({allocation(e) for e in range(256)}), dtype=np.int32)


def grid(shape):
    if len(shape) != 2:
        raise ValueError('grayscale only')
    y, x = np.meshgrid(np.arange(2, shape[0]-2, 3),
                       np.arange(2, shape[1]-2, 3), indexing='ij')
    return y.ravel(), x.ravel()


def keys(master, nonce):
    if len(master) != 32 or not 0 <= nonce < 2**128:
        raise ValueError('expected 32-byte master and uint128 nonce')
    return {d: HKDF(master, 32, nonce.to_bytes(16, 'big'), SHA256,
                    context=b'EDR1/'+d.encode())
            for d in ('image', 'directory', 'payload', 'auth')}


def crypt(data, key):
    return AES.new(key, AES.MODE_CTR, nonce=b'', initial_value=0).encrypt(data)


def slots(shape, labels, h):
    y, x = grid(shape)
    pixels, shifts = [], []
    for i in range(h, len(y)):
        n = int(BOOK[labels[i], 0])
        pixels.extend([int(y[i]*shape[1]+x[i])]*n)
        shifts.extend(range(7, 7-n, -1))
    return np.asarray(pixels, dtype=np.int64), np.asarray(shifts, dtype=np.uint8)


def readbits(a, positions):
    pixels, shifts = positions
    return (a.ravel()[pixels] >> shifts) & 1


def writebits(a, positions, bits):
    pixels, shifts = positions
    if len(bits) != len(pixels):
        raise ValueError('slot length')
    # Repeated pixel indices must accumulate separate bit changes.
    flat = a.ravel()
    for p, s, b in zip(pixels, shifts, bits):
        mask = 1 << int(s)
        flat[p] = (int(flat[p]) & (255 ^ mask)) | (int(b) << int(s))


def framing(a):
    if a.dtype != np.uint8 or a.ndim != 2:
        raise ValueError('expected uint8 grayscale')
    y, x = grid(a.shape)
    if len(y) < HEADER.size:
        raise ValueError('too few candidates')
    raw = a[y[:20], x[:20]].tobytes()
    magic, mode, length, plen = HEADER.unpack(raw)
    h = 52 + length
    if magic != b'EDR1' or mode not in (0, 1) or raw[5:8] != bytes(3) or h >= len(y):
        raise ValueError('invalid header')
    return y, x, mode, length, plen, h


def tag(a, auth_key):
    y, x, _, length, _, h = framing(a)
    buf = a.copy()
    buf[y[20+length:h], x[20+length:h]] = 0
    return hmac.new(auth_key, struct.pack('>QQ', *a.shape)+buf.tobytes(),
                    hashlib.sha256).digest()


def seal(a, auth_key):
    y, x, _, length, _, h = framing(a)
    a[y[20+length:h], x[20+length:h]] = np.frombuffer(tag(a, auth_key), np.uint8)


def inspect(a, capability):
    y, x, mode, length, plen, h = framing(a)
    actual = a[y[20+length:h], x[20+length:h]].tobytes()
    if not hmac.compare_digest(actual, tag(a, capability['auth'])):
        raise ValueError('authentication failed')
    enc = a[y[20:20+length], x[20:20+length]].tobytes()
    data = crypt(enc, capability['directory'])
    expected = (len(y)+1)//2
    if mode:
        dec = zlib.decompressobj()
        raw = dec.decompress(data, expected+1)
        if len(raw) != expected or not dec.eof or dec.unused_data or dec.unconsumed_tail:
            raise ValueError('invalid bounded compressed directory')
    else:
        raw = data
    if len(raw) != expected:
        raise ValueError('directory length')
    v = np.frombuffer(raw, np.uint8)
    labels = np.stack((v >> 4, v & 15), axis=1).ravel()
    if len(y) % 2 and labels[-1] != 0:
        raise ValueError('nonzero label padding')
    labels = labels[:len(y)]
    if np.any(labels >= len(BOOK)):
        raise ValueError('invalid label')
    positions = slots(a.shape, labels, h)
    backup = 8*h
    net = len(positions[0])-backup
    if net <= 0 or plen > net:
        raise ValueError('invalid capacity or length')
    return dict(y=y, x=x, mode=mode, length=length, plen=plen, h=h,
                labels=labels, positions=positions, backup=backup, net=net)


def embed(a, payload, capability):
    """No master/image key, original, model, map, or capacity argument."""
    q = inspect(a, capability)
    if payload.ndim != 1 or np.any((payload != 0) & (payload != 1)):
        raise ValueError('payload must be bits')
    if len(payload) > q['net']:
        raise ValueError('payload exceeds net capacity')
    plain = np.pad(payload.astype(np.uint8), (0, q['net']-len(payload)))
    cipher = np.unpackbits(np.frombuffer(crypt(np.packbits(plain).tobytes(),
                                             capability['payload']), np.uint8))[:q['net']]
    out = a.copy()
    pos = tuple(v[q['backup']:] for v in q['positions'])
    writebits(out, pos, cipher)
    header = HEADER.pack(b'EDR1', q['mode'], q['length'], len(payload))
    out[q['y'][:20], q['x'][:20]] = np.frombuffer(header, np.uint8)
    seal(out, capability['auth'])
    return out


if __name__ == '__main__':
    import json
    import sys
    import time
    # input image, payload, three capability hex keys, output image
    if len(sys.argv) != 8:
        raise ValueError('usage: wire.py image payload directorykey payloadkey authkey output')
    start = time.perf_counter()
    from PIL import Image
    a = np.array(Image.open(sys.argv[1]))
    payload = np.load(sys.argv[2], allow_pickle=False)
    capability = dict(zip(('directory', 'payload', 'auth'),
                          map(bytes.fromhex, sys.argv[3:6])))
    out = embed(a, payload, capability)
    Image.fromarray(out).save(sys.argv[6])
    # Last arg is a log/audit destination; no model is ever imported.
    result = dict(seconds=time.perf_counter()-start, model_imported='torch' in sys.modules,
                  image_key_received=False, capacity=inspect(out, capability)['net'])
    with open(sys.argv[7], 'x') as f:
        json.dump(result, f, indent=2)
