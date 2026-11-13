"""Owner reservation and receiver; preserves and reuses the historical B predictor."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
import time
import json
from pathlib import Path
import numpy as np
import wire

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def shared():
    sys.path.insert(0, str(ROOT/'self_contained_rdhei_feasibility_20261022'))
    import prototype
    if not np.array_equal(prototype.BOOK, wire.BOOK):
        raise ValueError('shared codebook mismatch')
    return prototype


def prepare(original):
    old = shared()
    if original.ndim != 2 or original.dtype != np.uint8:
        raise ValueError('expected uint8 grayscale')
    # Reuse unchanged checkpoint, preprocessing, prediction, labels and compression.
    q = old.prepare(original)
    h = 52+len(q['meta'])
    if h >= len(q['ys']):
        raise ValueError('metadata occupies all candidates')
    positions = wire.slots(original.shape, q['labels'], h)
    ns = q['ns']
    gross, lost = int(ns.sum()), int(ns[:h].sum())
    stream, backup = len(positions[0]), 8*h
    net = stream-backup
    stats = dict(pixels=original.size, candidates=len(ns), gross_slots=gross,
                 gross_bpp=gross/original.size, raw_label_bits=4*len(ns),
                 packed_label_bits=8*((len(ns)+1)//2),
                 compressed_label_bytes=q['stats']['compressed_label_bytes'],
                 stored_label_bits=8*len(q['meta']), codec=q['mode'],
                 fixed_header_bits=160, payload_length_bits_in_header=64,
                 authentication_bits=256, bootstrap_pixels=h,
                 metadata_total_bits=8*h, backup_bits=backup,
                 foregone_gross_slots=lost, stream_bits=stream,
                 physical_gross_bits=stream+8*h, signed_net_bits=net,
                 net_bpp=max(0, net)/original.size,
                 payload_encryption_expansion_bits=0, accepted=net>0)
    q.update(h=h, positions=positions, backup=backup, net=net, stats=stats)
    return q


def reserve(original, master, nonce, prepared=None):
    """Owner has no user payload argument: reservation precedes its creation."""
    q = prepare(original) if prepared is None else prepared
    if q['net'] <= 0:
        raise ValueError('nonpositive net capacity')
    k = wire.keys(master, nonce)
    h, y, x = q['h'], q['ys'], q['xs']
    backup = np.unpackbits(original[y[:h], x[:h]])
    stream = np.r_[backup, np.zeros(q['net'], dtype=np.uint8)]
    reserved = original.copy()
    wire.writebits(reserved, q['positions'], stream)
    reserved[y[:h], x[:h]] = 0
    out = np.frombuffer(wire.crypt(reserved.tobytes(), k['image']), np.uint8).copy().reshape(original.shape)
    directory = wire.crypt(q['meta'], k['directory'])
    header = wire.HEADER.pack(b'EDR1', q['mode'], len(directory), 0)
    out[y[:h], x[:h]] = np.frombuffer(header+directory+bytes(32), np.uint8)
    wire.seal(out, k['auth'])
    return out, {d:k[d] for d in ('directory', 'payload', 'auth')}


def receive(encrypted_image, master, nonce):
    k = wire.keys(master, nonce)
    q = wire.inspect(encrypted_image, k)
    positions = q['positions']
    u = tuple(v[q['backup']:] for v in positions)
    encrypted_bits = wire.readbits(encrypted_image, u)
    plain_bits = np.unpackbits(np.frombuffer(wire.crypt(np.packbits(encrypted_bits).tobytes(),
                                                     k['payload']), np.uint8))[:q['net']]
    if np.any(plain_bits[q['plen']:]):
        raise ValueError('nonzero payload padding')
    payload = plain_bits[:q['plen']].copy()
    # Restore known-zero reservation ciphertext before image decryption.
    z = np.frombuffer(wire.crypt(bytes(encrypted_image.size), k['image']), np.uint8).reshape(encrypted_image.shape)
    c = encrypted_image.copy()
    wire.writebits(c, u, wire.readbits(z, u))
    h, y, x = q['h'], q['y'], q['x']
    c[y[:h], x[:h]] = z[y[:h], x[:h]]
    reserved = np.frombuffer(wire.crypt(c.tobytes(), k['image']), np.uint8).copy().reshape(c.shape)
    backup = wire.readbits(reserved, tuple(v[:q['backup']] for v in positions))
    old = shared()
    p = np.rint(old.predict(reserved, y, x)).astype(np.int32)
    recovered = reserved.copy()
    for i in range(h, len(y)):
        n, lo, hi = map(int, wire.BOOK[q['labels'][i]])
        if not n:
            continue
        modulus = 1 << (8-n)
        residue = int(reserved[y[i], x[i]]) & (modulus-1)
        cs = [v for v in range(residue, 256, modulus) if lo <= abs(v-int(p[i])) <= hi]
        if len(cs) != 1:
            raise ValueError('nonunique original pixel')
        recovered[y[i], x[i]] = cs[0]
    recovered[y[:h], x[:h]] = np.packbits(backup)
    return recovered, payload


if __name__ == '__main__':
    # Only image,key,nonce are semantic inputs; output paths carry no source data.
    if len(sys.argv) != 8 or sys.argv[1] != 'receive':
        raise ValueError('usage: protocol.py receive image masterhex nonce recovered payload audit')
    reads = []
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = os.path.realpath(os.fsdecode(args[0]))
            mode = args[1]
            if mode is None or 'r' in mode:
                reads.append(path)
                # Source images are not permitted even if accidentally referenced.
                if path.startswith(str(ROOT.parent/'data')+os.sep):
                    raise RuntimeError('receiver attempted source image access')
    sys.addaudithook(audit)
    start = time.perf_counter()
    from PIL import Image
    encrypted = np.array(Image.open(sys.argv[2]))
    recovered, payload = receive(encrypted, bytes.fromhex(sys.argv[3]), int(sys.argv[4]))
    elapsed = time.perf_counter()-start
    np.save(sys.argv[5], recovered, allow_pickle=False)
    np.save(sys.argv[6], payload, allow_pickle=False)
    with open(sys.argv[7], 'x') as f:
        json.dump(dict(receiver_seconds=elapsed, payload_bits=len(payload),
                       semantic_inputs=['encrypted image', 'master key', 'nonce'],
                       source_access=False, read_paths=sorted(set(reads))), f, indent=2)
    print(json.dumps(dict(receiver_seconds=elapsed, payload_bits=len(payload))))
