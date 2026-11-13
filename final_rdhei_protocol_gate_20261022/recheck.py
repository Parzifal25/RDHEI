"""Additional bit restoration checks; does not modify the frozen main experiment."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image
import wire
import protocol as pr

BASE = Path(__file__).resolve().parent
D = BASE/'evidence'
master = bytes(range(32))
checks = []
rows = json.loads((D/'roundtrips.json').read_text())
for row in rows:
    stem = row['image'].replace('.','_')+'_'+row['case']
    reserved = np.array(Image.open(D/(stem+'_reserved.png')))
    final = np.array(Image.open(D/(stem+'_cipher.png')))
    png=(D/(stem+'_cipher.png')).read_bytes()
    offset=8;chunks=[]
    while offset<len(png):
        length=struct.unpack('>I',png[offset:offset+4])[0]
        chunks.append(png[offset+4:offset+8].decode('ascii'))
        offset+=12+length
    assert set(chunks)<= {'IHDR','IDAT','IEND'}
    k = wire.keys(master,row['nonce'])
    q = wire.inspect(final,k)
    u = tuple(v[q['backup']:] for v in q['positions'])
    z = np.frombuffer(wire.crypt(bytes(final.size),k['image']),np.uint8).reshape(final.shape)
    restored = final.copy()
    wire.writebits(restored,u,wire.readbits(z,u))
    restored[q['y'][:q['h']],q['x'][:q['h']]] = z[q['y'][:q['h']],q['x'][:q['h']]]
    expected = reserved.copy()
    expected[q['y'][:q['h']],q['x'][:q['h']]] = z[q['y'][:q['h']],q['x'][:q['h']]]
    assert np.array_equal(restored,expected)
    checks.append(dict(image=row['image'],case=row['case'],reserved_ciphertext_exact=True,
                       no_png_ancillary_metadata=True))

# Exercise every split of an arbitrary variable-slot stream, including within bytes.
rng=np.random.default_rng(1)
split_checks=0
for n in range(1,8):
    positions=(np.repeat(np.arange(3),n),np.tile(np.arange(7,7-n,-1,dtype=np.uint8),3))
    for split in range(3*n+1):
        a=rng.integers(0,256,(1,3),dtype=np.uint8)
        old=a.copy()
        bits=rng.integers(0,2,3*n-split,dtype=np.uint8)
        suffix=tuple(v[split:] for v in positions)
        prefix=tuple(v[:split] for v in positions)
        wire.writebits(a,suffix,bits)
        assert np.array_equal(wire.readbits(a,suffix),bits)
        assert np.array_equal(wire.readbits(a,prefix),wire.readbits(old,prefix))
        wire.writebits(a,suffix,wire.readbits(old,suffix))
        assert np.array_equal(a,old)
        split_checks+=1

# Wrong payload capability with a valid authentication key still fails zero padding.
# Authentication alone intentionally trusts an authorized embedder.
row=next(r for r in rows if r['case']=='empty')
stem=row['image'].replace('.','_')+'_'+row['case']
a=np.array(Image.open(D/(stem+'_reserved.png')))
k=wire.keys(master,row['nonce'])
bad={d:k[d] for d in ('directory','payload','auth')};bad['payload']=bytes(32)
final=wire.embed(a,np.empty(0,np.uint8),bad)
try:
    pr.receive(final,master,row['nonce'])
except ValueError as e:
    assert str(e)=='nonzero payload padding'
else:
    raise AssertionError('expected wrong payload key failure')

with (BASE/'restoration_checks.json').open('x') as f:
    json.dump(dict(ciphertext_restoration_checks=checks,slot_split_checks=split_checks,
                   wrong_payload_key_rejected=True),f,indent=2)
print('Exact reserved ciphertext restoration:',len(checks),'slot splits:',split_checks)
