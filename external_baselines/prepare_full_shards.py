#!/usr/bin/env python3
"""Create one immutable 243-image dataset package and deterministic LPT shards."""
import argparse, hashlib, json, shutil
from pathlib import Path

def sha_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def safe_id(rel):
    return rel.replace("/","__").replace(".tiff","")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset-dir",required=True)
    ap.add_argument("--canonical",required=True)
    ap.add_argument("--output-dir",required=True)
    ap.add_argument("--shards",type=int,default=40)
    a=ap.parse_args()
    source=Path(a.dataset_dir).resolve()
    canonical=json.loads(Path(a.canonical).read_text())
    out=Path(a.output_dir).resolve()
    if out.exists(): shutil.rmtree(out)
    images=out/"images"; sharddir=out/"shards"
    images.mkdir(parents=True); sharddir.mkdir(parents=True)
    if len(canonical)!=243: raise SystemExit(f"Expected 243 canonical records, got {len(canonical)}")
    ids=set(); seen_hashes=set(); staged=[]
    for meta in canonical:
        rel=meta["relative_path"]
        p=(source/rel).resolve()
        if source not in p.parents or not p.is_file(): raise SystemExit(f"Missing image {rel}")
        if sha_file(p)!=meta["source_sha256"]: raise SystemExit(f"Source SHA256 mismatch {rel}")
        image_id=safe_id(rel)
        if image_id in ids: raise SystemExit(f"Image ID collision: {image_id}")
        ids.add(image_id)
        ph=meta["pixels_sha256"]
        if ph in seen_hashes: raise SystemExit(f"Duplicate pixel image: {rel}")
        seen_hashes.add(ph)
        target=images/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
        pixels=int(meta["shape"][0])*int(meta["shape"][1])
        # Pixel count is a reproducible first-order workload estimate.
        staged.append({"image_id":image_id,"relative_path":rel,"pixels":pixels,
          "source_sha256":meta["source_sha256"],"pixels_sha256":ph,
          "corpus_group":meta.get("corpus_group","unspecified"),
          "correlation_cluster":meta.get("correlation_cluster") or image_id,
          "classification":meta.get("classification","unspecified")})
    # Longest-processing-time first, with pixel count as a transparent proxy.
    bins=[{"shard":i,"estimated_pixels":0,"images":[]} for i in range(a.shards)]
    for row in sorted(staged,key=lambda x:(-x["pixels"],x["image_id"])):
        target=min(bins,key=lambda x:(x["estimated_pixels"],x["shard"]))
        target["images"].append(row)
        target["estimated_pixels"]+=row["pixels"]
    for b in bins:
        b["images"].sort(key=lambda x:x["image_id"])
        fn=sharddir/f"shard_{b['shard']:02d}.tsv"
        with fn.open("w",encoding="utf-8") as f:
            for x in b["images"]: f.write(x["image_id"]+"\t"+x["relative_path"]+"\n")
    (out/"canonical_corpus_verified.json").write_text(json.dumps(canonical,indent=2,sort_keys=True)+"\n")
    plan={"image_count":len(staged),"unique_pixel_hashes":len(seen_hashes),"shard_count":a.shards,
      "assignment":"deterministic longest-processing-time-first, descending pixel count, least-loaded shard; image id breaks ties",
      "cost_proxy":"native height x width; original-source runtime can also depend on image content",
      "shards":[{"shard":b["shard"],"image_count":len(b["images"]),"estimated_pixels":b["estimated_pixels"],
        "image_ids":[x["image_id"] for x in b["images"]]} for b in bins]}
    (out/"shard_plan.json").write_text(json.dumps(plan,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"image_count":len(staged),"shards":[{"shard":b["shard"],"images":len(b["images"]),"pixels":b["estimated_pixels"]} for b in bins]},indent=2))
if __name__=="__main__":main()
