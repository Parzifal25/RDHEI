#!/usr/bin/env python3
"""Run a single-variant RGB pipeline sweep for smoke + precinct testing."""
from __future__ import annotations
import csv, signal, time
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path('/home/parzifal/RDHEI_Project')
MODELS_DIR = BASE / 'RDHEI_FIXED_V1' / 'models'
COLOR_DIR = BASE / 'data' / 'kodak_color'
OUT = BASE / 'results' / 'rgb_audit_20261013T100000'
OUT.mkdir(parents=True, exist_ok=True)

import sys
sys.path.insert(0, str(BASE))
from src.rdhei_color import run_rdhei_color
from src.rdhei_core import run_rdhei
from src.cnn_model import load_model

LOG: list[str] = []

def log(*args, **kwargs):
    msg = ' '.join(str(a) for a in args)
    LOG.append(msg)
    print(msg, flush=True)

class _T(Exception):
    pass

def _t(signum, frame):
    raise _T()

signal.signal(signal.SIGALRM, _t)

def guarded(fn, *args, **kwargs):
    start = time.time()
    signal.alarm(300)
    try:
        res = fn(*args, **kwargs)
        elapsed = time.time() - start
        signal.alarm(0)
        return res, elapsed, None
    except _T:
        elapsed = time.time() - start
        signal.alarm(0)
        return None, elapsed, 'timeout'
    except Exception as exc:
        elapsed = time.time() - start
        signal.alarm(0)
        return None, elapsed, repr(exc)
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass

def main() -> None:
    log('\nRGB AUDIT 2 — smoke + first-3-color-images sweep, v4_patch3')
    log('Project root:', BASE)
    log('Models dir:', MODELS_DIR)
    log('Color dir:', COLOR_DIR)
    log('Output dir:', OUT)
    log('')

    model_path = MODELS_DIR / 'v4_patch3.pth'
    model, patch, residual, nparams = load_model(str(model_path), device='cpu')
    log(f'Model: patch={patch} residual={residual} params={nparams}')
    log('')

    color_images = []
    for p in sorted(COLOR_DIR.glob('*.png')):
        im = Image.open(p)
        rgb = np.asarray(im.convert('RGB'))
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            log(f'SKIP not RGB after convert: {p.name} shape={rgb.shape}')
            continue
        color_images.append((p.name, rgb))
    log(f'Color images: {len(color_images)}')
    for n, a in color_images:
        log(f'  {n}: shape={a.shape} dtype={a.dtype}')
    log('')

    per_variant_start = time.time()

    for iname, img in color_images[:3]:
        log(f'\n== Image: {iname} shape={img.shape} ==')
        key = b'k' * 16
        nonce = 0
        seed = 42
        res, elapsed, err = guarded(
            run_rdhei_color,
            image_rgb=img, key=key, nonce=nonce, method='cnn',
            model=model, device='cpu', patch_size=patch, seed=seed,
        )
        if err:
            log(f'  status=ERROR error={err} time={round(elapsed,3)}s')
            continue

        exact_image = bool(np.array_equal(img, res['recovered']))
        perfect = bool(res['perfect'])
        bit_acc = float(res['bit_acc'])
        capacity_bits = int(res.get('capacity', -1)) if res.get('capacity') is not None else None
        status = 'PASS' if (exact_image and perfect and bit_acc == 100.0) else 'FAIL'
        log(f'  aggregate: status={status} exact={exact_image} perfect={perfect} bit_acc={bit_acc} capacity={capacity_bits} time={round(elapsed,3)}s')

        log('  per-channel pipeline-reported:')
        for ch in res.get('per_channel', []):
            ch_nonce = nonce + ['R','G','B'].index(ch['channel']) + 1
            log(f"    {ch['channel']}: bpp={ch['bpp']:.6f} capacity={ch['capacity']} perfect={ch['perfect']} bit_acc={ch['bit_acc']} nonce={ch_nonce}")

        log('  per-channel independent exact image + payload bit-for-bit:')
        ch_rows = []
        for c, ch_name in enumerate(['R','G','B']):
            chan = img[..., c]
            ch_nonce = nonce + c + 1
            r, _, rerr = guarded(
                run_rdhei,
                chan, key=key, nonce=ch_nonce, method='cnn',
                model=model, device='cpu', patch_size=patch, seed=seed + c,
            )
            if rerr or r is None:
                log(f'    {ch_name}: ERROR {rerr}')
                ch_rows.append((ch_name, False, False, None, None, ch_nonce, rerr))
                continue
            ex = bool(np.array_equal(chan, r['recovered']))
            pl = bool(np.array_equal(r['payload'], r['extracted']))
            log(f'    {ch_name}: exact_image={ex} payload_exact={pl} perfect={r["perfect"]} bit_acc={r["bit_acc"]} bpp={r["bpp"]:.6f} cap={r["capacity"]} nonce={ch_nonce}')
            ch_rows.append((ch_name, ex, pl, float(r['bpp']), int(r['capacity']), ch_nonce, None))

    total_wall = round(time.time() - per_variant_start, 3)
    log(f'\nVariant wall time: {total_wall}s')

    log_path = OUT / 'rgb_audit2_log.txt'
    with log_path.open('w') as f:
        f.write('\n'.join(LOG) + '\n')
    log(f'\nLog written: {log_path}')

if __name__ == '__main__':
    main()
