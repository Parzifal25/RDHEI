#!/usr/bin/env python3
import argparse,csv,json,math,statistics
from pathlib import Path
def rows(path):
    with open(path,newline="") as f:return list(csv.DictReader(f))
def stats(vals):
    x=[float(v) for v in vals if v not in ("","NaN","nan","None")]
    if not x:return {"n":0,"mean":None,"median":None,"min":None,"max":None}
    return {"n":len(x),"mean":statistics.mean(x),"median":statistics.median(x),"min":min(x),"max":max(x)}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--multi",required=True);p.add_argument("--ppmr",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    methods=[("Multi-MSB+Huffman",rows(a.multi),"method_native_net_bpp"),
             ("PPMR",rows(a.ppmr),"method_native_net_bpp")]
    report=[]
    for name,data,key in methods:
        vals=[r[key] for r in data if r.get(key) not in ("","NaN","nan")]
        positive=[v for v in vals if float(v)>0]
        report.append({"method":name,"pilot_images":len(data),
          "positive_native_net_capacity_images":sum(float(v)>0 for v in vals),
          "native_net_bpp_all":stats(vals),"native_net_bpp_positive_only":stats(positive),
          "payload_exact":sum(r.get("payload_exact")=="1" for r in data),
          "image_exact":sum(r.get("image_exact")=="1" for r in data),
          "runtime_seconds":stats([r.get("runtime_s","") for r in data]),
          "status_counts":{s:sum(r.get("status")==s for r in data) for s in sorted({r.get("status") for r in data})},
          "scope":"Six-image stratified smoke pilot only; not the 243-image corpus result."})
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
