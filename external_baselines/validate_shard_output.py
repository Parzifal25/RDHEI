#!/usr/bin/env python3
"""Verify that each shard emitted exactly one outcome row per assigned image."""
import argparse,csv,json
from pathlib import Path
def read_ids(p):
    return [line.rstrip("\n").split("\t",1)[0] for line in open(p,encoding="utf-8") if line.strip()]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--expected-list",required=True);ap.add_argument("--multi",required=True);ap.add_argument("--ppmr",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();expected=read_ids(a.expected_list);result={"expected":len(expected),"methods":{}}
    for name,path in [("multi_msb_huffman",a.multi),("ppmr",a.ppmr)]:
        with open(path,newline="") as f: rows=list(csv.DictReader(f))
        got=[r["image_id"] for r in rows]
        missing=sorted(set(expected)-set(got));extra=sorted(set(got)-set(expected));dups=sorted({x for x in got if got.count(x)>1})
        ok=(len(got)==len(expected) and not missing and not extra and not dups)
        result["methods"][name]={"rows":len(rows),"complete":ok,"missing":missing,"extra":extra,"duplicates":dups,
          "status_counts":{s:sum(r.get("status")==s for r in rows) for s in sorted({r.get("status") for r in rows})}}
        if not ok: raise SystemExit(json.dumps(result,indent=2))
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
