#!/usr/bin/env python3
"""Join original-source ledgers to exact corpus provenance; compute native and clustered summaries."""
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np

def readcsv(p):
    with open(p,newline="") as f: return list(csv.DictReader(f))

def stats(values):
    x=np.asarray([float(v) for v in values if v is not None and math.isfinite(float(v))],dtype=float)
    if not len(x): return {"n":0,"mean":None,"median":None,"std_sample":None,"q1":None,"q3":None,"iqr":None}
    q1,q3=np.percentile(x,[25,75])
    return {"n":int(len(x)),"mean":float(np.mean(x)),"median":float(np.median(x)),
      "std_sample":float(np.std(x,ddof=1)) if len(x)>1 else 0.0,"q1":float(q1),"q3":float(q3),"iqr":float(q3-q1)}

def cluster_bootstrap(rows, seed=20261118, reps=10000):
    clusters=defaultdict(list)
    for row in rows:
        clusters[row["correlation_cluster"]].append(row)
    keys=sorted(clusters)
    if not keys: return {"clusters":0,"replicates":0,"mean_net_bpp_95ci":None,"positive_coverage_95ci":None}
    rng=np.random.default_rng(seed)
    means=[]; coverages=[]
    for _ in range(reps):
        chosen=rng.integers(0,len(keys),size=len(keys))
        sample=[r for idx in chosen for r in clusters[keys[int(idx)]]]
        values=[r["method_native_net_bpp"] for r in sample if math.isfinite(r["method_native_net_bpp"])]
        if values:
            means.append(float(np.mean(values)))
            coverages.append(float(np.mean([v>0 for v in values])))
    def ci(x):
        if not x:return None
        return [float(np.percentile(x,2.5)),float(np.percentile(x,97.5))]
    return {"clusters":len(keys),"replicates":reps,"seed":seed,
      "mean_net_bpp_95ci":ci(means),"positive_coverage_95ci":ci(coverages),
      "bootstrap_unit":"correlation_cluster; all images within a sampled cluster travel together"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--canonical",required=True);ap.add_argument("--multi",required=True);ap.add_argument("--ppmr",required=True);ap.add_argument("--out-dir",required=True)
    a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    with open(a.canonical,encoding="utf-8") as f: corpus=json.load(f)
    byid={r["relative_path"].replace("/","__").replace(".tiff",""):r for r in corpus}
    configs=[("Multi-MSB+Huffman",a.multi,"multi"),("PPMR",a.ppmr,"ppmr")]
    perimage=[];summaries=[];group_rows=[]
    for method,path,kind in configs:
      joined=[]
      raw=readcsv(path)
      for r in raw:
        meta=byid.get(r["image_id"])
        if meta is None: raise SystemExit(f"Unknown image id in {path}: {r['image_id']}")
        h,w=map(int,meta["shape"]); n=w*h; status=r.get("status","ERROR")
        bpp=float(r["method_native_net_bpp"]) if r.get("method_native_net_bpp") not in (None,"","NaN","nan") else float("nan")
        if kind=="ppmr":
            gross=int(float(r.get("gross_embedded_bits") or 0))
            compressed=int(float(r.get("compress_predict_bits") or 0))
            net_bits=gross-compressed-8-16*8-16*8
        else:
            net_bits=int(float(r.get("embedded_bits") or 0));gross=net_bits;compressed=0
        row={"image_id":r["image_id"],"relative_path":meta["relative_path"],
          "corpus_group":meta.get("corpus_group") or "unspecified",
          "correlation_cluster":meta.get("correlation_cluster") or r["image_id"],
          "classification":meta.get("classification") or "unspecified",
          "height":h,"width":w,"pixels":n,
          "source_file_sha256":meta["source_sha256"],"decoded_pixel_sha256":meta["pixels_sha256"],
          "method":method,"gross_embedded_bits_as_returned_by_source":gross,
          "method_native_net_payload_bits":net_bits,"method_native_net_bpp":bpp,
          "positive_net_capacity":bool(math.isfinite(bpp) and bpp>0),
          "payload_exact":r.get("payload_exact","0") in ("1","True","true"),
          "image_exact":r.get("image_exact","0") in ("1","True","true"),
          "runtime_s":float(r.get("runtime_s") or "nan"),"status":status,"error":r.get("error","")}
        if kind=="ppmr":
            row["ub_embedded_bits"]=int(float(r.get("ub_embedded_bits") or 0))
            row["nub_embedded_bits"]=int(float(r.get("nub_embedded_bits") or 0))
            row["compressed_prediction_map_bits"]=compressed
        joined.append(row);perimage.append(row)
      if len(joined)!=243 or len({x["image_id"] for x in joined})!=243:
        raise SystemExit(f"{method}: expected exactly 243 unique image rows, got {len(joined)}")
      valid=[x for x in joined if math.isfinite(x["method_native_net_bpp"])]
      pos=[x for x in valid if x["method_native_net_bpp"]>0]
      times=[x["runtime_s"] for x in joined if math.isfinite(x["runtime_s"])]
      statuses={s:sum(x["status"]==s for x in joined) for s in sorted({x["status"] for x in joined})}
      summary={"method":method,"images_attempted":243,"images_with_numeric_capacity":len(valid),
        "positive_capacity_images":len(pos),"positive_capacity_rate":len(pos)/243,
        "net_bpp_all_numeric_rows":stats([x["method_native_net_bpp"] for x in valid]),
        "net_bpp_positive_rows":stats([x["method_native_net_bpp"] for x in pos]),
        "payload_exact_passes":sum(x["payload_exact"] for x in joined),"payload_exact_trials":243,
        "image_exact_passes":sum(x["image_exact"] for x in joined),"image_exact_trials":243,
        "status_counts":statuses,
        "runtime_s":{"n":len(times),"median":float(np.median(times)) if times else None,"p95":float(np.percentile(times,95)) if times else None},
        "cluster_bootstrap":cluster_bootstrap(joined),
        "capacity_convention":"Original source method's own reported/native net-rate expression; not normalized to EDR2's in-band signed-net ledger."}
      summaries.append(summary)
      groups=defaultdict(list)
      for x in joined: groups[x["corpus_group"]].append(x)
      for group,items in sorted(groups.items()):
        vals=[x["method_native_net_bpp"] for x in items if math.isfinite(x["method_native_net_bpp"])]
        positives=sum(v>0 for v in vals)
        group_rows.append({"method":method,"corpus_group":group,"images":len(items),
          "numeric_capacity_rows":len(vals),"positive_capacity_images":positives,
          "positive_capacity_rate":positives/len(items) if items else 0,
          "mean_net_bpp":float(np.mean(vals)) if vals else None,
          "median_net_bpp":float(np.median(vals)) if vals else None,
          "payload_exact_passes":sum(x["payload_exact"] for x in items),
          "image_exact_passes":sum(x["image_exact"] for x in items)})
    fieldnames=sorted({k for row in perimage for k in row})
    for method,fn in [("Multi-MSB+Huffman","multi_msb_huffman_per_image.csv"),("PPMR","ppm_rearrangement_per_image.csv")]:
      with open(out/fn,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction="ignore");w.writeheader();w.writerows([x for x in perimage if x["method"]==method])
    with open(out/"aggregate_summary.csv","w",newline="",encoding="utf-8") as f:
      fields=["method","images_attempted","images_with_numeric_capacity","positive_capacity_images","positive_capacity_rate",
        "mean_net_bpp_all_numeric","median_net_bpp_all_numeric","std_net_bpp_all_numeric","iqr_net_bpp_all_numeric",
        "mean_net_bpp_positive","median_net_bpp_positive","std_net_bpp_positive","iqr_net_bpp_positive",
        "payload_exact_passes","payload_exact_trials","image_exact_passes","image_exact_trials",
        "status_counts","runtime_median_s","runtime_p95_s","cluster_count","cluster_bootstrap_mean_95ci","cluster_bootstrap_positive_coverage_95ci","capacity_convention"]
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
      for s in summaries:
        aa=s["net_bpp_all_numeric_rows"];pp=s["net_bpp_positive_rows"];cb=s["cluster_bootstrap"]
        w.writerow({"method":s["method"],"images_attempted":s["images_attempted"],
          "images_with_numeric_capacity":s["images_with_numeric_capacity"],"positive_capacity_images":s["positive_capacity_images"],
          "positive_capacity_rate":s["positive_capacity_rate"],"mean_net_bpp_all_numeric":aa["mean"],
          "median_net_bpp_all_numeric":aa["median"],"std_net_bpp_all_numeric":aa["std_sample"],"iqr_net_bpp_all_numeric":aa["iqr"],
          "mean_net_bpp_positive":pp["mean"],"median_net_bpp_positive":pp["median"],
          "std_net_bpp_positive":pp["std_sample"],"iqr_net_bpp_positive":pp["iqr"],
          "payload_exact_passes":s["payload_exact_passes"],"payload_exact_trials":s["payload_exact_trials"],
          "image_exact_passes":s["image_exact_passes"],"image_exact_trials":s["image_exact_trials"],
          "status_counts":json.dumps(s["status_counts"],sort_keys=True),"runtime_median_s":s["runtime_s"]["median"],
          "runtime_p95_s":s["runtime_s"]["p95"],"cluster_count":cb["clusters"],
          "cluster_bootstrap_mean_95ci":json.dumps(cb["mean_net_bpp_95ci"]),
          "cluster_bootstrap_positive_coverage_95ci":json.dumps(cb["positive_coverage_95ci"]),
          "capacity_convention":s["capacity_convention"]})
    with open(out/"group_summary.csv","w",newline="",encoding="utf-8") as f:
      fields=list(group_rows[0]) if group_rows else ["method","corpus_group","images","numeric_capacity_rows","positive_capacity_images","positive_capacity_rate","mean_net_bpp","median_net_bpp","payload_exact_passes","image_exact_passes"]
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(group_rows)
    (out/"aggregate_summary.json").write_text(json.dumps(summaries,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summaries,indent=2))
if __name__=="__main__":main()
