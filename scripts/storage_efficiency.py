#!/usr/bin/env python3
"""Matched serialized-storage accounting for marked-image RDHEI artifacts.

Usage:
 python scripts/storage_efficiency.py --original original.png --marked marked.png --payload-bits payload.npy --output report.json

Baseline is lossless AES-CTR ciphertext of the original raw pixel bytes plus a
separately stored packed payload and 48 bytes of nonce+authentication metadata.
Marked storage is the serialized marked image plus any explicit sidecars.
This is a byte-accounting tool; protocol overheads must be supplied as sidecars
or explicitly described in the report.
"""
import argparse, json, os
from pathlib import Path
import numpy as np
from PIL import Image
from Crypto.Cipher import AES

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",required=True)
    p.add_argument("--marked",required=True)
    p.add_argument("--payload-bits",required=True)
    p.add_argument("--sidecar",action="append",default=[])
    p.add_argument("--output",required=True)
    a=p.parse_args()
    original_path=Path(a.original); marked_path=Path(a.marked)
    bits=np.load(a.payload_bits,allow_pickle=False)
    if bits.ndim!=1 or np.any((bits!=0)&(bits!=1)):
        raise ValueError("payload file must contain a 1-D binary array")
    with Image.open(original_path) as im:
        original=np.asarray(im)
    raw=original.tobytes(order="C")
    key=bytes(range(32)); nonce=bytes(range(16))
    cipher=AES.new(key,AES.MODE_CTR,nonce=b"",initial_value=int.from_bytes(nonce,"big"))
    ciphertext=cipher.encrypt(raw)
    payload_bytes=(len(bits)+7)//8
    baseline_bytes=len(ciphertext)+payload_bytes+48
    sidecars=[Path(x) for x in a.sidecar]
    marked_bytes=marked_path.stat().st_size+sum(x.stat().st_size for x in sidecars)
    report={
      "payload_bits":int(len(bits)),
      "payload_packed_bytes":payload_bytes,
      "original_raw_pixel_bytes":len(raw),
      "baseline":{"encrypted_original_bytes":len(ciphertext),"separate_payload_bytes":payload_bytes,"nonce_and_auth_metadata_bytes":48,"total_bytes":baseline_bytes},
      "marked_artifact":{"marked_image_bytes":marked_path.stat().st_size,"sidecar_bytes":sum(x.stat().st_size for x in sidecars),"sidecars":[{"path":str(x),"bytes":x.stat().st_size} for x in sidecars],"total_bytes":marked_bytes},
      "storage_saving_bytes":baseline_bytes-marked_bytes,
      "storage_saving_percent":100*(baseline_bytes-marked_bytes)/baseline_bytes if baseline_bytes else None,
      "marked_total_bytes_per_payload_bit":marked_bytes/len(bits) if len(bits) else None,
      "baseline_total_bytes_per_payload_bit":baseline_bytes/len(bits) if len(bits) else None,
      "note":"Baseline is a declared accounting model; disclose image format and all sidecars. Compare equal payload lengths and include all required protocol metadata."
    }
    Path(a.output).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
