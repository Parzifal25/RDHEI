#!/usr/bin/env python3
"""Gate full-corpus execution on six exact original-source round trips per method."""
import argparse,csv,json
def main():
    p=argparse.ArgumentParser(); p.add_argument("csv_file"); p.add_argument("--expected",type=int,default=6); a=p.parse_args()
    with open(a.csv_file,newline="") as f: rows=list(csv.DictReader(f))
    if len(rows)!=a.expected: raise SystemExit(f"SMOKE FAIL: expected {a.expected} rows, got {len(rows)}")
    failed=[]
    for r in rows:
        good=(r.get("status")=="PASS" and r.get("payload_exact","0") in ("1","True","true") and r.get("image_exact","0") in ("1","True","true"))
        if not good: failed.append({k:r.get(k) for k in ("image_id","status","payload_exact","image_exact","error")})
    print(json.dumps({"rows":len(rows),"passed":len(rows)-len(failed),"failed":failed},indent=2))
    if failed: raise SystemExit("SMOKE FAIL: payload extraction and/or byte-exact host recovery did not pass")
if __name__=="__main__":main()
