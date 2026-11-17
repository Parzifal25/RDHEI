#!/usr/bin/env python3
"""Verify and materialize the exact 243-image corpus used by EDR2's native run."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image
import numpy as np
def sha256(data): return hashlib.sha256(data).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--expected-corpus",required=True); ap.add_argument("--dataset-dir",required=True); ap.add_argument("--output-dir",required=True)
    a=ap.parse_args(); expected_path=Path(a.expected_corpus); root=Path(a.dataset_dir).resolve(); out=Path(a.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True); rows=json.loads(expected_path.read_text())
    if not isinstance(rows,list) or len(rows)!=243: raise SystemExit(f"Expected frozen 243-image corpus.json, got {len(rows) if isinstance(rows,list) else 'non-list'}")
    seen=set(); canonical=[]
    for r in rows:
        rel=r.get("relative_path")
        if not isinstance(rel,str) or Path(rel).is_absolute() or ".." in Path(rel).parts: raise SystemExit(f"Unsafe canonical path: {rel!r}")
        p=(root/rel).resolve()
        if root not in p.parents or not p.is_file(): raise SystemExit(f"Missing canonical source image: {rel}")
        raw_hash=hashlib.sha256(p.read_bytes()).hexdigest()
        if raw_hash!=r["source_sha256"]: raise SystemExit(f"Source-file hash mismatch: {rel}: {raw_hash}")
        with Image.open(p) as im:
            if im.mode!="L" or getattr(im,"n_frames",1)!=1: raise SystemExit(f"Not native single-frame grayscale mode L: {rel}, {im.mode}")
            im.load(); px=np.asarray(im)
        if px.dtype!=np.uint8 or px.ndim!=2: raise SystemExit(f"Not 2D uint8 grayscale: {rel} {px.dtype} {px.shape}")
        if list(px.shape)!=r["shape"]: raise SystemExit(f"Shape mismatch for {rel}: {px.shape} != {r['shape']}")
        ph=sha256(np.ascontiguousarray(px).tobytes())
        if ph!=r["pixels_sha256"]: raise SystemExit(f"Decoded-pixel hash mismatch: {rel}: {ph}")
        if ph in seen: raise SystemExit(f"Unexpected duplicate decoded pixels: {rel}")
        seen.add(ph)
        if any(int(v)%4 for v in px.shape): raise SystemExit(f"PPMR 4x4 block constraint fails for {rel}: {px.shape}")
        row=dict(r); row["verified_file_sha256"]=raw_hash; row["verified_pixels_sha256"]=ph; row["absolute_path"]=str(p); canonical.append(row)
    if len(seen)!=243: raise SystemExit(f"Expected 243 unique pixel buffers, got {len(seen)}")
    (out/"canonical_corpus_verified.json").write_text(json.dumps(canonical,indent=2,sort_keys=True)+"\n")
    def image_id(r): return r["relative_path"].replace("/","__").replace(".tiff","")
    with (out/"all_243_images.txt").open("w") as f:
        for r in canonical: f.write(image_id(r)+"\t"+r["absolute_path"]+"\n")
    groups={}
    for r in canonical: groups.setdefault(r["corpus_group"],[]).append(r)
    if len(groups)<6: raise SystemExit(f"Expected at least six strata, got {list(groups)}")
    smoke=[sorted(groups[g],key=lambda x:x["relative_path"])[0] for g in sorted(groups)]
    with (out/"smoke_6_images.txt").open("w") as f:
        for r in smoke: f.write(image_id(r)+"\t"+r["absolute_path"]+"\n")
    report={"expected_images":243,"verified_images":len(canonical),"unique_pixel_hashes":len(seen),
      "strata":{k:len(v) for k,v in sorted(groups.items())},"smoke_images":[r["relative_path"] for r in smoke],
      "manifest_sha256":sha256(expected_path.read_bytes()),
      "policy":"Exact canonical path, source-file SHA-256, native mode, shape, decoded-pixel SHA-256 and 4x4 compatibility verified against completed EDR2 native-run corpus.json."}
    (out/"dataset_validation.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(json.dumps(report,indent=2))
if __name__=="__main__": main()
