#!/usr/bin/env python3
"""Turn one immutable shard TSV into absolute paths on the current worker."""
import argparse
from pathlib import Path
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shared-dir",required=True);p.add_argument("--shard",type=int,required=True);p.add_argument("--output",required=True)
    a=p.parse_args();root=Path(a.shared_dir).resolve()
    src=root/"shards"/f"shard_{a.shard:02d}.tsv"
    if not src.is_file(): raise SystemExit(f"Missing shard list: {src}")
    count=0
    with src.open(encoding="utf-8") as inp, open(a.output,"w",encoding="utf-8") as out:
        for line in inp:
            image_id,rel=line.rstrip("\n").split("\t",1)
            path=(root/"images"/rel).resolve()
            if root not in path.parents or not path.is_file(): raise SystemExit(f"Unsafe/missing shard image: {rel}")
            out.write(image_id+"\t"+str(path)+"\n");count+=1
    if not count: raise SystemExit(f"Shard {a.shard} is empty")
    print(f"Shard {a.shard:02d}: prepared {count} image paths")
if __name__=="__main__":main()
