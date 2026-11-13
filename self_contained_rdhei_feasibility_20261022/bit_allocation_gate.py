import sys,json
from pathlib import Path
import numpy as np
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D.parent))
from src.rdhei_core import _compute_bpp_and_range,_embed_pixel,_recover_pixel
from src.embedding import embed
out={}
# Figure2 top-n payload replacement followed by three-LSB label storage.
examples=[]
for x,p in [(0,0),(1,0),(2,0),(6,0),(100,100),(64,0)]:
 n,lo,hi=_compute_bpp_and_range(abs(x-p));a=_embed_pixel(x,n,[1]*n);y=(a&248)|n
 rec=_recover_pixel(y,p,n,lo,hi)
 examples.append(dict(x=x,prediction=p,n=n,marked_before_label=a,marked_after_label=y,recovered_with_true_maps=rec,payload_before=[1]*n,payload_after=[(y>>i)&1 for i in range(7,7-n,-1)]))
out['figure2_label_overwrite_examples']=examples
# Legacy PEE clips two different payload bits into the same marked image.
a=np.array([[255,255]],dtype=np.uint8)
e0,_=embed(a,None,np.array([0],dtype=np.uint8),threshold=1)
e1,_=embed(a,None,np.array([1],dtype=np.uint8),threshold=1)
assert np.array_equal(e0,e1)
out['legacy_clipping_collision']=dict(original=a.tolist(),payload0_marked=e0.tolist(),payload1_marked=e1.tolist())
out['paper_table_vs_current_capacity']=[dict(e=e,paper_n=8-(1 if e==0 else 2 if e==1 else 3 if e==2 else 4 if e<=7 else 5 if e<=15 else 8),current_n=_compute_bpp_and_range(e)[0]) for e in range(256) if 8-(1 if e==0 else 2 if e==1 else 3 if e==2 else 4 if e<=7 else 5 if e<=15 else 8)!=_compute_bpp_and_range(e)[0]]
with (D/'bit_allocation_gate.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2)[:2000])
