import sys,json
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D.parent))
from src.rdhei_core import _compute_bpp_and_range
out={}
for mode in ['MSB','LSB']:
    collisions=0;words=0;observed=0;ambig_allocation=0;witnesses=[]
    for p in range(256):
        buckets=[[] for _ in range(256)]
        for x in range(256):
            n,lo,hi=_compute_bpp_and_range(abs(x-p))
            for q in range(1<<n):
                y=(q<<(8-n))|(x&((1<<(8-n))-1)) if mode=='MSB' else (x&~((1<<n)-1))|q
                buckets[y].append((x,n,q));words+=1
        for y,b in enumerate(buckets):
            if not b:continue
            observed+=1
            if len(b)>1:
                collisions+=1
                if len({v[1] for v in b})>1:ambig_allocation+=1
                if len(witnesses)<8:witnesses.append(dict(p=p,marked=y,alternatives=b[:6],total=len(b)))
    out[mode]=dict(enumerated_original_prediction_pairs=65536,payload_words=words,observed_prediction_marked_pairs=observed,nonunique_pairs=collisions,allocation_ambiguous_pairs=ambig_allocation,witnesses=witnesses,GO=collisions==0)
with (D/'joint_mapless_enumeration.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
