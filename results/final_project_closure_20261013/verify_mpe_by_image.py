import sys, csv, json, math
import numpy as np
sys.path.insert(0,'.')
from pathlib import Path
from PIL import Image
from src.rdhei_core import content_owner_prepare

GRAY_DIR = Path('/home/parzifal/RDHEI_Project/data/kodak_gray')
VARIANTS = {
    'v1_full': Path('/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1/models/v1_full.pth'),
    'v2_no_residual': Path('/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1/models/v2_no_residual.pth'),
    'v3_no_weighted_loss': Path('/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1/models/v3_no_weighted_loss.pth'),
    'v4_patch3': Path('/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1/models/v4_patch3.pth'),
    'v5_patch7': Path('/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1/models/v5_patch7.pth'),
}
ROWS=[]
for vname, ckpt in VARIANTS.items():
    from src.cnn_model import load_model
    if not ckpt.exists():
        print('SKIP no checkpoint', vname, ckpt)
        continue
    model, patch_size, residual, nparams = load_model(ckpt, device='cpu')
    print('VARIANT', vname, 'patch', patch_size, 'residual', residual, 'nparams', nparams)
    for p in sorted(GRAY_DIR.glob('*.png')):
        if p.name.endswith(':Zone.Identifier'):
            continue
        im = Image.open(p)
        arr = np.array(im).astype(np.uint8)
        co = content_owner_prepare(image=arr, key=b'k'*16, nonce=0, method='cnn',
                                  model=model, device='cpu', patch_size=patch_size)
        assert co['capacity']==int(co['bpp_map'].sum())
        pred_int = co['pred_int'].astype(np.int32)
        img_int = arr.astype(np.int32)
        err_abs = np.abs(img_int - pred_int)
        mpe = float(err_abs.mean())
        ROWS.append({
            'variant': vname,
            'image': p.name,
            'shape': f"{arr.shape[0]}x{arr.shape[1]}",
            'capacity_bits': int(co['capacity']),
            'bpp': co['bpp'],
            'mpe': mpe,
            'pred_int_min': int(pred_int.min()),
            'pred_int_max': int(pred_int.max()),
            'err_abs_max': int(err_abs.max()),
            'n_pixels': int(arr.size),
        })
        print('  ', p.name, 'bpp=%.6f'%co['bpp'], 'mpe=%.6f'%mpe, 'cap=%d'%co['capacity'])
with open('results/final_project_closure_20261013/mpe_by_image.csv','w',newline='') as f:
    w=csv.DictWriter(f, fieldnames=list(ROWS[0].keys()))
    w.writeheader()
    for r in ROWS:
        w.writerow(r)
print('WROTE mpe_by_image.csv rows=', len(ROWS))
