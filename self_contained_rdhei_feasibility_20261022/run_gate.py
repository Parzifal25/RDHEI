import os,sys,time,json,hashlib,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import torch
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;D=BASE/'attempt2';D.mkdir(exist_ok=False);sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
import prototype as pr
from src.cnn_model import load_model
from src.predictor import cnn_predict_map
from src.rdhei_core import generate_label_map_fast,_compute_bpp_and_range

def save(name,obj):
 with (D/name).open('x') as f:json.dump(obj,f,indent=2)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
torch.set_num_threads(4);torch.set_grad_enabled(False)
rng=np.random.default_rng(20261022)
model=pr.model();state={k:v.clone() for k,v in model.state_dict().items()}
source=ROOT.parent/'data/kodak_gray/Airplane.png';a=np.array(Image.open(source).convert('L'))
small=a[:128,:128].copy();repro=[]
for cp in ['v4_patch3.pth','v1_full.pth']:
 m=model if cp=='v4_patch3.pth' else load_model(str(ROOT/'models'/cp),device='cpu')[0]
 m.eval();m.requires_grad_(False)
 t=time.perf_counter();base=cnn_predict_map(small,m,patch_size=m.patch_size)
 changed=small.copy();changed[:]=rng.integers(0,256,changed.shape,dtype=np.uint8)
 dense=cnn_predict_map(changed,m,patch_size=m.patch_size)
 # Arbitrary actual MSB replacement under the existing map, with arbitrary payload words.
 pi=np.rint(base).astype(np.int32);ns,_,_=generate_label_map_fast(np.abs(small.astype(np.int32)-pi))
 marked=small.copy()
 for y in range(small.shape[0]):
  for x in range(small.shape[1]):
   n=int(ns[y,x]);s=1<<(8-n)
   marked[y,x]=(int(small[y,x])&(s-1))|(int(rng.integers(1<<n))<<(8-n))
 after=cnn_predict_map(marked,m,patch_size=m.patch_size)
 ys,xs=pr.coords(small.shape);isolated=small.copy();isolated[ys,xs]=rng.integers(0,256,len(ys),dtype=np.uint8)
 orig=pr.predict(small,ys,xs,m);iso=pr.predict(isolated,ys,xs,m)
 patch_equal=True;r=m.patch_size//2
 for y,x in zip(ys,xs):
  p=small[y-r:y+r+1,x-r:x+r+1].copy();q=isolated[y-r:y+r+1,x-r:x+r+1].copy();p[r,r]=q[r,r]=0
  patch_equal &= bool(np.array_equal(p,q))
 assert patch_equal and np.array_equal(orig,iso)
 repro.append(dict(checkpoint=cp,sha256=sha(ROOT/'models'/cp),patch=m.patch_size,shape=list(small.shape),dense_modified_pixels=int(np.sum(marked!=small)),dense_float_prediction_changes=int(np.sum(base!=after)),dense_integer_prediction_changes=int(np.sum(np.rint(base)!=np.rint(after))),dense_max_abs_prediction_change=float(np.max(np.abs(base-after))),isolated_candidates=len(ys),isolated_input_patches_exact=patch_equal,isolated_float_predictions_exact=bool(np.array_equal(orig,iso)),isolated_integer_predictions_exact=bool(np.array_equal(np.rint(orig),np.rint(iso))),seconds=time.perf_counter()-t))
 print('repro',cp,repro[-1],flush=True)
save('prediction_reproducibility.json',repro)
# Eq12 recovery with paper Table2 allocations, even when labels/predictions are supplied.
paper=[];total=multi=missing=0
for p in range(256):
 for x in range(256):
  e=abs(x-p);l=1 if e==0 else 2 if e==1 else 3 if e==2 else 4 if e<=7 else 5 if e<=15 else 8
  n=8-l;size=1<<n
  if n==0:continue
  cs=[v for v in range((x//size)*size,(x//size+1)*size) if abs(v-p)<size]
  total+=1;multi+=len(cs)>1;missing+=x not in cs
  if len(paper)<8 and len(cs)>1:paper.append(dict(x=x,prediction=p,label=l,candidates=cs[:12],candidate_count=len(cs)))
save('paper_equation12_gate.json',dict(embedded_pairs=total,nonunique=multi,missing_original=missing,witnesses=paper))
# Scope fixed before prototype measurements. No calibration or tuning on these images.
save('protocol.json',dict(model='models/v4_patch3.pth',candidate_grid='rows,cols = range(2, dimension-2,3)',metadata='4-bit code per original candidate tuple (n,min,max); choose shorter of raw nibble bytes and zlib9 bytes',bootstrap='first H isolated candidate bytes hold 20-byte header plus labels; all H original bytes restored from prefix of ordinary candidate stream',cases=['Airplane.png','Baboon.png','Lena.png','constant128','random256'],payloads=['empty','37 bits','half net','full net'],receiver='fresh Python subprocess; arguments ciphertext.npy,key,nonce,output paths only; preinstalled model/algorithm'))
rows=[];capacity_rows=[]
for name in ['Airplane.png','Baboon.png','Lena.png','constant128','random256']:
 if name=='constant128':im=np.full((128,128),128,dtype=np.uint8);path=None
 elif name=='random256':im=rng.integers(0,256,(256,256),dtype=np.uint8);path=None
 else:path=ROOT.parent/'data/kodak_gray'/name;im=np.array(Image.open(path).convert('L'))
 t=time.perf_counter();pre=pr.prepare(im);prep_sec=time.perf_counter()-t
 # Dense hard-map capacity and step2 comparison, same frozen checkpoint.
 dense=cnn_predict_map(im,model,patch_size=3);nmap=generate_label_map_fast(np.abs(im.astype(np.int32)-np.rint(dense).astype(np.int32)))[0]
 ys,xs=pre['ys'],pre['xs'];assert np.array_equal(np.rint(dense[ys,xs]).astype(np.int32),pre['p'])
 y2,x2=pr.coords(im.shape,step=2,radius=1)
 caps=dict(image=name,shape=list(im.shape),pixels=im.size,source_path=str(path) if path else 'synthetic',source_sha256=sha(path) if path else hashlib.sha256(im.tobytes()).hexdigest(),prepare_seconds=prep_sec,dense_gross_bpp=float(nmap.mean()),isolated_step2_count=len(y2),isolated_step2_gross_bpp=float(nmap[y2,x2].sum()/im.size),**pre['stats'])
 net=pre['stats']['net_payload_bits'];caps['GO']=net>0;capacity_rows.append(caps)
 print('capacity',name,caps,flush=True)
 if net<=0:continue
 for case,plen in [('empty',0),('short',min(37,net)),('partial',net//2),('full',net)]:
  payload=rng.integers(0,2,plen,dtype=np.uint8);key=bytes(range(32));nonce=10000+len(rows)*1000000
  t=time.perf_counter();enc,stats=pr.send(im,payload,key,nonce,pre);send_sec=time.perf_counter()-t
  stem=f"{name.replace('.','_')}_{case}";ct=D/f'{stem}_ciphertext.npy';rec=D/f'{stem}_recovered.npy';pay=D/f'{stem}_payload.npy'
  np.save(ct,enc,allow_pickle=False)
  start=time.perf_counter();cp=subprocess.run([sys.executable,str(BASE/'prototype.py'),'receive',str(ct),key.hex(),str(nonce),str(rec),str(pay)],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  process_sec=time.perf_counter()-start
  (D/f'{stem}_receiver.log').write_text(cp.stdout+cp.stderr)
  if cp.returncode:raise RuntimeError(cp.stdout+cp.stderr)
  gotim=np.load(rec,allow_pickle=False);gotpay=np.load(pay,allow_pickle=False)
  okim=bool(np.array_equal(gotim,im));okpay=bool(np.array_equal(gotpay,payload));assert okim and okpay,(name,case)
  # Full payload includes raw backups and padding in addition to these user bits.
  rxstats=json.loads(cp.stdout.strip().splitlines()[-1])
  row=dict(image=name,case=case,image_exact=okim,payload_exact=okpay,sender_seconds=send_sec,receiver_process_seconds=process_sec,nonce=nonce,receiver_argument_count=3,**rxstats)
  rows.append(row);print('roundtrip',row,flush=True)
save('capacity_measurements.json',capacity_rows);save('end_to_end_results.json',rows)
assert all(torch.equal(state[k],v) for k,v in model.state_dict().items())
save('model_integrity.json',dict(checkpoint_sha256=sha(pr.CHECKPOINT),state_unchanged=True,training=False,backprop=False))
print('ALL GATES COMPLETED',flush=True)
