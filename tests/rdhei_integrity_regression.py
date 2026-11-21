#!/usr/bin/env python3
"""Integrity/tamper regression tests for EDR1 wire protocol. Not EDR2 evidence."""
from pathlib import Path
import sys, struct
import numpy as np
HERE = Path(__file__).resolve().parent
PROTOCOL_DIR = HERE.parent / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(PROTOCOL_DIR))
import protocol, wire
MASTER = bytes(range(32))
NONCE = 0x123456789ABCDEF00123456789ABCDEF
def fixture():
    yy, xx = np.indices((512, 512), dtype=np.uint16)
    return (96 + ((3 * yy + 5 * xx + (yy // 16) * 7) % 32)).astype(np.uint8)
def expect_reject(label, mutated, capability):
    try:
        wire.inspect(mutated, capability)
    except (ValueError, struct.error, IndexError):
        print("PASS reject:", label); return
    raise AssertionError("Tampering was not rejected: " + label)
def main():
    original = fixture()
    prepared = protocol.prepare(original)
    if prepared["net"] <= 0: raise RuntimeError("fixture has no positive net capacity")
    reserved, owner = protocol.reserve(original, MASTER, NONCE, prepared=prepared)
    capability = owner
    payload = np.random.default_rng(77).integers(0, 2, prepared["net"], dtype=np.uint8)
    marked = wire.embed(reserved, payload, capability)
    recovered, extracted = protocol.receive(marked, MASTER, NONCE)
    assert np.array_equal(recovered, original) and np.array_equal(extracted, payload)
    print("PASS clean round trip; net capacity bits:", prepared["net"])
    y, x, mode, length, plen, h = wire.framing(marked)
    for label, pos in [("header",(int(y[0]),int(x[0]))),("encrypted directory",(int(y[20]),int(x[20]))),("authentication tag",(int(y[20+length]),int(x[20+length]))),("payload carrier",(int(y[h+2]),int(x[h+2]))),("recovery/carrier pixel",(int(y[-1]),int(x[-1])))]:
        changed=marked.copy(); changed[pos]^=1; expect_reject(label,changed,capability)
    try: wire.inspect(marked[:-2,:],capability)
    except Exception: print("PASS reject: truncated image")
    else: raise AssertionError("truncated image accepted")
    wrong=dict(capability); wrong["auth"]=bytes(b^0xFF for b in capability["auth"])
    try: wire.inspect(marked,wrong)
    except ValueError: print("PASS reject: wrong authentication capability")
    else: raise AssertionError("wrong auth capability accepted")
    print("ALL EDR1 integrity regression tests passed.")
    print("SCOPE: validates EDR1 wire.py; does not validate historical EDR2 AES-CTR.")
if __name__=="__main__": main()
