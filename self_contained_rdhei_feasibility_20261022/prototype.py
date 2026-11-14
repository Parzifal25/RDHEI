"""Isolated feasibility prototype only. Receiver signature has no maps or payload length."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,struct,zlib,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.cnn_model import load_model
from src.rdhei_core import _compute_bpp_and_range
from src.encryption import encrypt_image,decrypt_image
CHECKPOINT=ROOT/'models/v4_patch3.pth'
# Preinstalled decoding constants. All candidate centers are >2 pixels from boundaries.
HEADER=struct.Struct('>4sB3xIQ') # magic, metadata codec, metadata bytes, user payload bit length:20 bytes
BOOK=sorted(set(_compute_bpp_and_range(e) for e in range(256)))
ENC={v:i for i,v in enumerate(BOOK)}
LABEL=np.array([ENC[_compute_bpp_and_range(e)] for e in range(256)],dtype=np.uint8)
BOOK=np.array(BOOK,dtype=np.int32)
_MODEL=None

def model():
 global _MODEL
 if _MODEL is None:
  torch.set_num_threads(4);torch.set_grad_enabled(False)
  _MODEL=load_model(str(CHECKPOINT),device='cpu')[0];_MODEL.eval();_MODEL.requires_grad_(False)
 return _MODEL

def coords(shape,step=2,radius=2):
 y,x=np.meshgrid(np.arange(radius,shape[0]-radius,step),np.arange(radius,shape[1]-radius,step),indexing='ij')
 return y.ravel(),x.ravel()

def predict(a,ys,xs,m=None):
 m=model() if m is None else m;r=m.patch_size//2
 # These patches exactly match original normalization/masking; fixed batch size shared at both ends.
 p=np.stack([a[y-r:y+r+1,x-r:x+r+1] for y,x in zip(ys,xs)]).astype(np.float32)/255.
 p[:,r,r]=0;p=p[:,None]
 vals=[]
 with torch.inference_mode():
  for st in range(0,len(p),2048): vals.append(m(torch.from_numpy(p[st:st+2048])).cpu().numpy().ravel())
 return np.concatenate(vals)

def packlabels(labels):
 if len(labels)%2:labels=np.r_[labels,np.uint8(0)]
 return ((labels[::2]<<4)|labels[1::2]).astype(np.uint8).tobytes()

def unpacklabels(raw,count):
 v=np.frombuffer(raw,dtype=np.uint8);a=np.stack([v>>4,v&15],axis=1).ravel()[:count]
 if len(a)!=count or np.any(a>=len(BOOK)):raise ValueError('invalid label stream')
 return a

def prepare(a):
 ys,xs=coords(a.shape)
 if len(ys)<HEADER.size:raise ValueError('image too small')
 floats=predict(a,ys,xs);p=np.rint(floats).astype(np.int32)
 labels=LABEL[np.abs(a[ys,xs].astype(np.int32)-p)]
 raw=packlabels(labels);comp=zlib.compress(raw,9)
 mode=1 if len(comp)<len(raw) else 0;meta=comp if mode else raw
 h=HEADER.size+len(meta)
 if h>=len(ys):raise ValueError('metadata occupies all candidates')
 ns=BOOK[labels,0];gross=int(ns.sum());lost=int(ns[:h].sum());remaining=int(ns[h:].sum());backup=8*h;net=remaining-backup
 return dict(ys=ys,xs=xs,p=p,floats=floats,labels=labels,ns=ns,meta=meta,mode=mode,h=h,stats=dict(candidate_count=len(ys),candidate_fraction=len(ys)/a.size,gross_slots=gross,gross_bpp=gross/a.size,raw_labels_bits=4*len(ys),packed_raw_label_bits=len(raw)*8,compressed_label_bytes=len(comp),stored_label_bits=8*len(meta),header_bits=HEADER.size*8,payload_length_framing_bits=64,bootstrap_pixels=h,displaced_original_bits=backup,foregone_original_slots=lost,available_stream_bits=remaining,net_payload_bits=net,net_payload_bpp=max(0,net)/a.size,overhead_relative_to_gross=backup+lost,metadata_codec='zlib' if mode else 'raw_nibbles'))

def send(a,payload,key,nonce,pre=None):
 q=prepare(a) if pre is None else pre
 if q['stats']['net_payload_bits']<0:raise ValueError('nonpositive reversible budget')
 if len(payload)>q['stats']['net_payload_bits']:raise ValueError('payload too long')
 y,x=q['ys'],q['xs'];h=q['h'];buf=a.copy()
 header=HEADER.pack(b'SCF1',q['mode'],len(q['meta']),len(payload))+q['meta']
 assert len(header)==h
 stream=np.r_[np.unpackbits(a[y[:h],x[:h]]),payload].astype(np.uint8)
 stream=np.pad(stream,(0,q['stats']['available_stream_bits']-len(stream)))
 bit=0
 for i in range(h,len(y)):
  n=int(q['ns'][i]);word=0
  for b in stream[bit:bit+n]:word=(word<<1)|int(b)
  bit+=n;s=1<<(8-n)
  buf[y[i],x[i]]=(int(a[y[i],x[i]])&(s-1))|(word<<(8-n))
 buf[y[:h],x[:h]]=np.frombuffer(header,dtype=np.uint8)
 assert bit==len(stream)
 return encrypt_image(buf,key,nonce),q['stats']

def receive(encrypted_image,key,nonce):
 """Only ciphertext image, key, nonce. Checkpoint/algorithm are installed constants."""
 a=decrypt_image(encrypted_image,key,nonce);y,x=coords(a.shape);c=len(y)
 if c<HEADER.size:raise ValueError('image too small')
 magic,mode,mlen,plen=HEADER.unpack(a[y[:HEADER.size],x[:HEADER.size]].tobytes())
 h=HEADER.size+mlen
 if magic!=b'SCF1' or mode not in [0,1] or h>=c:raise ValueError('invalid framing')
 data=a[y[HEADER.size:h],x[HEADER.size:h]].tobytes()
 raw=zlib.decompress(data) if mode else data
 if len(raw)!=(c+1)//2:raise ValueError('label size mismatch')
 labels=unpacklabels(raw,c);p=np.rint(predict(a,y,x)).astype(np.int32)
 rec=a.copy();bits=[]
 for i in range(h,c):
  n,lo,hi=map(int,BOOK[labels[i]]);v=int(a[y[i],x[i]])
  if not n:continue
  bits.extend((v>>j)&1 for j in range(7,7-n,-1))
  s=1<<(8-n);cs=[cc for cc in range(v&(s-1),256,s) if lo<=abs(cc-int(p[i]))<=hi]
  if len(cs)!=1:raise ValueError('nonunique original')
  rec[y[i],x[i]]=cs[0]
 bits=np.array(bits,dtype=np.uint8)
 if 8*h+plen>len(bits):raise ValueError('payload length beyond budget')
 rec[y[:h],x[:h]]=np.packbits(bits[:8*h])
 return rec,bits[8*h:8*h+plen]

if __name__=='__main__':
 # Explicit process boundary: no sender state, maps, original or length accepted.
 if sys.argv[1]!='receive' or len(sys.argv)!=7:raise ValueError('usage: receive ciphertext.npy keyhex nonce recovered.npy payload.npy')
 enc=np.load(sys.argv[2],allow_pickle=False);t=time.perf_counter()
 rec,bits=receive(enc,bytes.fromhex(sys.argv[3]),int(sys.argv[4]));sec=time.perf_counter()-t
 np.save(sys.argv[5],rec,allow_pickle=False);np.save(sys.argv[6],bits,allow_pickle=False)
 print(json.dumps(dict(receiver_seconds=sec,payload_bits=len(bits))))
