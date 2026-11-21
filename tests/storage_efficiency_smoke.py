#!/usr/bin/env python3
"""Smoke test for storage-efficiency accounting using temporary artifacts."""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"storage_efficiency.py"
def main():
  with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    original=d/"original.png"; marked=d/"marked.png"; payload=d/"payload.npy"; side=d/"metadata.bin"; out=d/"report.json"
    arr=np.arange(64*64,dtype=np.uint8).reshape(64,64)
    Image.fromarray(arr).save(original)
    Image.fromarray(arr[::-1].copy()).save(marked)
    np.save(payload,np.array([0,1,1,0,1,0,0,1,1],dtype=np.uint8))
    side.write_bytes(b"sidecar-test")
    subprocess.run([sys.executable,str(SCRIPT),"--original",str(original),"--marked",str(marked),"--payload-bits",str(payload),"--sidecar",str(side),"--output",str(out)],check=True,capture_output=True,text=True)
    r=json.loads(out.read_text())
    assert r["payload_bits"]==9
    assert r["payload_packed_bytes"]==2
    assert r["baseline"]["encrypted_original_bytes"]==original.stat().st_size
    assert r["marked_artifact"]["sidecar_bytes"]==side.stat().st_size
    assert r["marked_artifact"]["total_bytes"]==marked.stat().st_size+side.stat().st_size
    assert r["baseline"]["total_bytes"]==original.stat().st_size+2+48
    print("PASS storage accounting smoke test")
if __name__=="__main__":main()
