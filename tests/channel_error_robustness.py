#!/usr/bin/env python3
"""Controlled channel-error experiment for authenticated EDR1 protocol.

This is protocol-level evidence, not historical EDR2 evidence and not a
communication-channel simulation of a specific physical medium.
"""
from pathlib import Path
import sys, json, struct, hashlib
import numpy as np

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/"final_rdhei_protocol_gate_20261022"
sys.path.insert(0,str(BASE))
import protocol, wire

MASTER=bytes(range(32))
NONCE=0x23456789ABCDEF0123456789ABCDEF01

def fixture():
    yy,xx=np.indices((512,512),dtype=np.uint16)
    return (96+((3*yy+5*xx+(yy//16)*7)%32)).astype(np.uint8)

def rejected(image):
    try:
        protocol.receive(image,MASTER,NONCE)
    except (ValueError, struct.error, IndexError):
        return True
    return False

def main():
    out=HERE/"channel_error_results.json"
    original=fixture()
    prepared=protocol.prepare(original)
    if prepared["net"]<=0: raise RuntimeError("fixture has no positive net capacity")
    reserved,cap=protocol.reserve(original,MASTER,NONCE,prepared=prepared)
    rng=np.random.default_rng(20261121)
    payload=rng.integers(0,2,prepared["net"],dtype=np.uint8)
    marked=wire.embed(reserved,payload,cap)
    recovered,extracted=protocol.receive(marked,MASTER,NONCE)
    assert np.array_equal(recovered,original) and np.array_equal(extracted,payload)
    print("PASS clean baseline exact image/payload recovery")

    total_bits=marked.size*8
    rates=[1e-6,1e-5,1e-4,1e-3,1e-2]
    trials=20
    rows=[]
    for rate in rates:
        flips=max(1,int(round(total_bits*rate)))
        detected=0
        for t in range(trials):
            corrupted=marked.copy()
            positions=rng.choice(total_bits,size=min(flips,total_bits),replace=False)
            flat=corrupted.reshape(-1)
            bytepos=positions//8
            bitpos=positions%8
            flat[bytepos]^=(1<<bitpos).astype(np.uint8)
            detected+=int(rejected(corrupted))
        row={"bit_error_rate_target":rate,"flipped_bits_per_trial":flips,
             "trials":trials,"rejected_trials":detected,
             "detection_rate":detected/trials,"false_accepts":trials-detected}
        rows.append(row)
        print("BER",json.dumps(row),flush=True)
        assert detected==trials, f"undetected corruption at BER {rate}"

    # Burst errors: contiguous bit regions across flattened serialized pixels.
    burst_sizes=[8,64,512,4096]
    burst_rows=[]
    for size in burst_sizes:
        detected=0
        for _ in range(trials):
            corrupted=marked.copy()
            start=int(rng.integers(0,total_bits-size+1))
            positions=np.arange(start,start+size)
            corrupted.reshape(-1)[positions//8]^=(1<<(positions%8)).astype(np.uint8)
            detected+=int(rejected(corrupted))
        row={"burst_bits":size,"trials":trials,"rejected_trials":detected,
             "detection_rate":detected/trials,"false_accepts":trials-detected}
        burst_rows.append(row)
        print("BURST",json.dumps(row),flush=True)
        assert detected==trials, f"undetected burst corruption of {size} bits"

    report={"scope":"Authenticated EDR1 protocol only; not historical EDR2 AES-CTR.",
            "image_shape":list(marked.shape),"total_image_bits":total_bits,
            "payload_bits":int(len(payload)),"clean_roundtrip_exact":True,
            "random_bit_errors":rows,"burst_errors":burst_rows,
            "trials_per_condition":trials,
            "interpretation":"All tested corruptions were rejected by authentication; no error-correcting recovery is implemented. This measures detection/rejection, not correction."}
    out.write_text(json.dumps(report,indent=2)+"\\n")
    print("REPORT",out)
    print("ALL CHANNEL-ERROR TESTS PASSED")

if __name__=="__main__": main()
