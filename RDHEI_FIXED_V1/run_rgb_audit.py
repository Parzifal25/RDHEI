#!/usr/bin/env python3
"""Run the RGB pipeline verification and write audit artifacts."""
from __future__ import annotations
import csv, json, signal, time
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path('/home/parzifal/RDHEI_Project')
GRAY_DIR = BASE / 'data' / 'kodak_gray'
COLOR_DIR = BASE / 'data' / 'kodak_color'
MODELS_DIR = BASE / 'RDHEI_FIXED_V1' / 'models'
OUT = BASE / 'results' / 'rgb_audit_20261013T100000'
OUT.mkdir(parents=True, exist_ok=True)

sys_path_inserted = False
def ensure_path():
    global sys_path_inserted
    if not sys_path_inserted:
        import sys
        sys.path.insert(0, str(BASE))
        sys_path_inserted = True

ensure_path()
from src.rdhei_color import run_rdhei_color
from src.rdhei_core import run_rdhei
from src.cnn_model import load_model

VARIANTS = [
    ('v1_full', 5, True),
    ('v2_no_residual', 5, False),
    ('v3_no_weighted_loss', 5, True),
    ('v4_patch3', 3, True),
    ('v5_patch7', 7, True),
]

LOG: list[str] = []

def log(*args, **kwargs) -> None:
    msg = ' '.join(str(a) for a in args)
    LOG.append(msg)
    print(msg, flush=True)

class _T(Exception):
    pass

def _t(signum, frame):
    raise _T()

signal.signal(signal.SIGALRM, _t)

def run_rdhei_color_guarded(img, model, patch, nonce=0, seed=42):
    key = b'k' * 16
    start = time.time()
    signal.alarm(300)
    try:
        res = run_rdhei_color(
            image_rgb=img,
            key=key,
            nonce=nonce,
            method='cnn',
            model=model,
            device='cpu',
            patch_size=patch,
            seed=seed,
        )
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

def run_rdhei_guarded(chan, model, patch, nonce, seed):
    key = b'k' * 16
    start = time.time()
    signal.alarm(300)
    try:
        r = run_rdhei(
            chan,
            key=key,
            nonce=nonce,
            method='cnn',
            model=model,
            device='cpu',
            patch_size=patch,
            seed=seed,
        )
        elapsed = time.time() - start
        signal.alarm(0)
        return r, elapsed, None
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
    log('\nRGB AUDIT — Full pipeline sweep, 5 CNN variants x valid RGB images')
    log('Project root:', BASE)
    log('Models dir:', MODELS_DIR)
    log('Color dir:', COLOR_DIR)
    log('Output dir:', OUT)
    log('')

    # Dataset inventory
    inventory_path = OUT / 'rgb_dataset_inventory.csv'
    color_images = []
    inv_rows = [['path', 'orig_mode', 'shape', 'dtype', 'channels', 'has_color_variation', 'max_channel_abs_diff']]
    for p in sorted(COLOR_DIR.glob('*.png')):
        im = Image.open(p)
        orig_mode = im.mode
        arr = np.asarray(im)
        shape = arr.shape
        dtype = str(arr.dtype)
        channels = arr.shape[2] if arr.ndim == 3 else 1
        if arr.ndim == 3 and arr.shape[2] == 3:
            rgb = arr.astype(np.int32)
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            max_abs_diff = int(max(np.max(np.abs(r - g)), np.max(np.abs(g - b)), np.max(np.abs(r - b))))
            has_color_variation = max_abs_diff > 0
        else:
            max_abs_diff = ''
            has_color_variation = False
        inv_rows.append([str(p.relative_to(BASE)), orig_mode, str(shape), dtype, channels, has_color_variation, max_abs_diff])
        rgb_arr = np.asarray(im.convert('RGB'))
        if rgb_arr.ndim == 3 and rgb_arr.shape[2] == 3:
            color_images.append((p.name, rgb_arr))
    with inventory_path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerows(inv_rows)
    log(f'Dataset inventory written: {inventory_path}')
    log(f'Valid RGB images for pipeline testing: {len(color_images)}')
    for n, a in color_images:
        log(f'  {n}: shape={a.shape} dtype={a.dtype}')
    log('')

    summary_csv = OUT / 'rgb_variant_sweep.csv'
    per_image_csv = OUT / 'rgb_per_image_per_variant.csv'
    log_path = OUT / 'rgb_audit_execution_log.txt'

    summary_rows: list[list[str]] = []
    per_image_rows: list[list[str]] = []

    for tag, expected_patch, expected_residual in VARIANTS:
        model_path = MODELS_DIR / f'{tag}.pth'
        if not model_path.exists():
            log(f'VARIANT {tag}: checkpoint missing -> {model_path}')
            summary_rows.append([tag, model_path.name, 'NOT RUN', 'missing checkpoint', '', '', '', '', '', '', '', '', ''])
            continue

        try:
            model, patch, residual, nparams = load_model(str(model_path), device='cpu')
        except Exception as exc:
            log(f'VARIANT {tag}: model load FAILED -> {exc}')
            summary_rows.append([tag, model_path.name, 'ERROR', repr(exc), '', '', '', '', '', '', '', '', ''])
            continue

        if patch != expected_patch or residual != expected_residual:
            log(f'VARIANT {tag}: ARCHITECTURE MISMATCH expected patch={expected_patch} residual={expected_residual}, got patch={patch} residual={residual}')

        log(f'\nVARIANT {tag}: patch={patch} residual={residual} params={nparams}')

        n_pass = 0
        n_total = len(color_images)
        total_wall_start = time.time()
        variant_channel_summary_parts: list[str] = []

        for iname, img in color_images:
            res, elapsed, err = run_rdhei_color_guarded(img, model, patch, nonce=0, seed=42)
            if err:
                log(f'  {iname}: status=ERROR error={err} time={round(elapsed,3)}s')
                per_image_rows.append([
                    tag, iname, str(img.shape), 'ERROR',
                    '', '', '', round(elapsed, 3) if elapsed is not None else '',
                    '',
                    '', '', '', '', '',
                    '', '', '', '', '',
                    '', '', '', '', '',
                    err,
                ])
                continue

            exact_image = bool(np.array_equal(img, res['recovered']))
            perfect = bool(res['perfect'])
            bit_acc = float(res['bit_acc'])
            capacity_bits = int(res.get('capacity', -1)) if res.get('capacity') is not None else None
            status = 'PASS' if (exact_image and perfect and bit_acc == 100.0) else 'FAIL'

            channel_check = {}
            per_channel_summary_parts: list[str] = []
            for c, ch_name in enumerate(['R', 'G', 'B']):
                chan = img[..., c]
                ch_nonce = 0 + c + 1
                r, _, rerr = run_rdhei_guarded(chan, model, patch, ch_nonce, seed=42 + c)
                if rerr or r is None:
                    channel_check[ch_name] = dict(exact=False, payload_exact=False, bpp=None, capacity=None, nonce=ch_nonce, error=rerr)
                    per_channel_summary_parts.append(f'{ch_name}: ERROR {rerr}')
                    continue
                channel_check[ch_name] = dict(
                    exact=bool(np.array_equal(chan, r['recovered'])),
                    payload_exact=bool(np.array_equal(r['payload'], r['extracted'])),
                    bpp=float(r['bpp']),
                    capacity=int(r['capacity']),
                    nonce=ch_nonce,
                )
                per_channel_summary_parts.append(
                    f"{ch_name}: exact={channel_check[ch_name]['exact']} payload_exact={channel_check[ch_name]['payload_exact']} "
                    f"bpp={channel_check[ch_name]['bpp']:.4f} cap={channel_check[ch_name]['capacity']} nonce={ch_nonce}"
                )

            log(f'  {iname}: status={status} exact={exact_image} perfect={perfect} bit_acc={bit_acc} time={round(elapsed,3)}s')
            log(f'     {"; ".join(per_channel_summary_parts)}')

            if status == 'PASS':
                n_pass += 1

            per_image_rows.append([
                tag, iname, str(img.shape), status,
                exact_image, perfect, bit_acc, round(elapsed, 3) if elapsed is not None else '',
                capacity_bits,
                channel_check['R']['exact'], channel_check['R']['payload_exact'], channel_check['R']['bpp'], channel_check['R']['capacity'], channel_check['R']['nonce'],
                channel_check['G']['exact'], channel_check['G']['payload_exact'], channel_check['G']['bpp'], channel_check['G']['capacity'], channel_check['G']['nonce'],
                channel_check['B']['exact'], channel_check['B']['payload_exact'], channel_check['B']['bpp'], channel_check['B']['capacity'], channel_check['B']['nonce'],
                '',
            ])

        total_wall = round(time.time() - total_wall_start, 3)
        overall = 'PASS' if n_pass == n_total else ('PARTIAL' if n_pass > 0 else 'FAIL')
        log(f'\nVARIANT {tag}: {n_pass}/{n_total} PASS, wall_time={total_wall}s')
        summary_rows.append([
            tag,
            model_path.name,
            overall,
            f'{n_pass}/{n_total} passed',
            str(patch),
            str(residual),
            str(nparams),
            str(n_pass),
            str(n_total),
            '; '.join(variant_channel_summary_parts),
            str(total_wall),
            '',
            '',
        ])

    log('\nWriting artifacts:')
    log(str(summary_csv))
    log(str(per_image_csv))
    log(str(inventory_path))
    log(str(log_path))

    with summary_csv.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['variant', 'checkpoint', 'overall', 'summary', 'patch', 'residual', 'nparams', 'color_pass', 'color_total', 'per_channel_summary', 'wall_time_s', 'notes', 'errors'])
        w.writerows(summary_rows)

    with per_image_csv.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow([
            'variant', 'image', 'shape', 'status',
            'exact_image', 'perfect', 'bit_acc', 'time_s', 'capacity_bits',
            'R_exact', 'R_payload_exact', 'R_bpp', 'R_capacity', 'R_nonce',
            'G_exact', 'G_payload_exact', 'G_bpp', 'G_capacity', 'G_nonce',
            'B_exact', 'B_payload_exact', 'B_bpp', 'B_capacity', 'B_nonce',
            'error',
        ])
        w.writerows(per_image_rows)

    with log_path.open('w') as f:
        f.write('\n'.join(LOG) + '\n')

    log('\nOVERALL SUMMARY:')
    for row in summary_rows:
        log(f"  {row[0]:22s} [{row[2]:8s}] {row[7]}/{row[8]} color PASS, wall_time={row[10]}s")

if __name__ == '__main__':
    main()
