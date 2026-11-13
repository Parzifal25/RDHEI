import sys,json
from pathlib import Path
import numpy as np
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
import prototype as pr
from src.rdhei_core import _compute_bpp_and_range
pairs=words=0
for p in range(256):
 for x in range(256):
  n,lo,hi=_compute_bpp_and_range(abs(x-p));code=int(pr.LABEL[abs(x-p)])
  assert tuple(pr.BOOK[code])==(n,lo,hi)
  q=np.arange(1<<n);s=1<<(8-n);marked=(q<<(8-n))|(x&(s-1))
  assert np.all((marked>>(8-n))==q)
  if n:
   cs=[c for c in range(x&(s-1),256,s) if lo<=abs(c-p)<=hi]
   assert cs==[x]
   assert np.all((marked&(s-1))==(x&(s-1)))
  else:assert marked[0]==x
  pairs+=1;words+=len(q)
labels=np.tile(np.arange(len(pr.BOOK),dtype=np.uint8),3)
assert np.array_equal(labels,pr.unpacklabels(pr.packlabels(labels),len(labels)))
obj=dict(pairs=pairs,payload_words=words,failures=0,label_classes=len(pr.BOOK),codebook=pr.BOOK.tolist(),scope='Unique original with serialized label class internally decoded; all payload words; n=0 pass-through; not a mapless-decoding result',framing_size=pr.HEADER.size)
with (D/'metadata_math_gate.json').open('x') as f:json.dump(obj,f,indent=2)
print(obj)
