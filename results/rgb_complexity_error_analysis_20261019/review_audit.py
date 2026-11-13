#!/usr/bin/env python3
"""Phase H — programmatic self-audit of RGB_Complexity_Error_Analysis.md.

Every numeric claim in the report is re-derived from the CSVs in this directory
(or from the checkpoints, for the complexity claims) and asserted. Output:
review_audit.md with PASS/FAIL per check.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

checks = []


def check(name, cond, detail=""):
    checks.append({"check": name, "status": "PASS" if cond else "FAIL", "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}", flush=True)


def rows(f):
    return list(csv.DictReader(open(HERE / f)))


def close(a, b, tol=5e-4):
    return abs(a - b) <= tol


# ------------------------------------------------------------------ baseline
recon = rows("baseline_reconciliation.csv")
n_match = sum(1 for r in recon if r["match"] == "YES")
n_fail = sum(1 for r in recon if r["match"] == "NO")
check("reconciliation 410/410", len(recon) == 410 and n_match == 410 and n_fail == 0,
      f"total={len(recon)} match={n_match} fail={n_fail}")

rgb = rows("rgb_per_image_comparison.csv")
gray = rows("gray_per_image_comparison.csv")
mean_cnn = np.mean([float(r["CNN3x3_bpp"]) for r in rgb])
mean_gap = np.mean([float(r["GAP_bpp"]) for r in rgb])
check("RGB mean BPP CNN 4.8838", close(mean_cnn, 4.8838, 1e-3), f"got {mean_cnn:.4f}")
check("RGB mean BPP GAP 4.7867", close(mean_gap, 4.7867, 1e-3), f"got {mean_gap:.4f}")
check("RGB mean rel +2.03%", close((mean_cnn - mean_gap) / mean_gap * 100, 2.03, 0.02),
      f"got {(mean_cnn - mean_gap) / gap_gap if False else (mean_cnn - mean_gap) / mean_gap * 100:+.2f}%")
mae_cnn = np.mean([float(r["CNN3x3_mae"]) for r in rgb])
mae_gap = np.mean([float(r["GAP_mae"]) for r in rgb])
check("RGB MAE CNN 6.5558", close(mae_cnn, 6.5558, 1e-3), f"got {mae_cnn:.4f}")
check("RGB MAE rel -18.4%", close((mae_cnn - mae_gap) / mae_gap * 100, -18.36, 0.05),
      f"got {(mae_cnn - mae_gap) / mae_gap * 100:+.2f}%")

g_cnn = np.mean([float(r["CNN3x3_bpp"]) for r in gray])
g_gap = np.mean([float(r["GAP_bpp"]) for r in gray])
check("gray mean BPP CNN 5.1897", close(g_cnn, 5.1897, 1e-3), f"got {g_cnn:.4f}")
check("gray mean rel +3.24%", close((g_cnn - g_gap) / g_gap * 100, 3.24, 0.02),
      f"got {(g_cnn - g_gap) / g_gap * 100:+.2f}%")
gmae_cnn = np.mean([float(r["CNN3x3_mae"]) for r in gray])
gmae_gap = np.mean([float(r["GAP_mae"]) for r in gray])
check("gray MAE rel -24.5%", close((gmae_cnn - gmae_gap) / gmae_gap * 100, -24.50, 0.05),
      f"got {(gmae_cnn - gmae_gap) / gmae_gap * 100:+.2f}%")

# per-image diffs CNN-GAP on RGB
per = {r["image"]: float(r["CNN3x3_bpp"]) - float(r["GAP_bpp"]) for r in rgb}
check("4.2.03 diff +0.2407", close(per["4.2.03.png"], 0.2407, 1e-3), f"{per['4.2.03.png']:+.4f}")
check("4.2.05 diff +0.2335", close(per["4.2.05.png"], 0.2335, 1e-3), f"{per['4.2.05.png']:+.4f}")
check("4.2.06 diff +0.0029", close(per["4.2.06.png"], 0.0029, 1e-3), f"{per['4.2.06.png']:+.4f}")
check("4.2.07 diff -0.1292", close(per["4.2.07.png"], -0.1292, 1e-3), f"{per['4.2.07.png']:+.4f}")
check("lena diff +0.1374", close(per["lena.png"], 0.1374, 1e-3), f"{per['lena.png']:+.4f}")
pep = float(next(r for r in gray if r["image"] == "Peppers.png")["CNN3x3_bpp"]) - \
      float(next(r for r in gray if r["image"] == "Peppers.png")["GAP_bpp"])
check("Peppers gray diff -0.0713", close(pep, -0.0713, 1e-3), f"{pep:+.4f}")

# ------------------------------------------------------- underperformance set
under = rows("underperformance_diagnosis.csv")
keys = {(r["image"], r["channel"]) for r in under}
check("5 losing channels = 4.2.06 R/G + 4.2.07 R/G/B",
      keys == {("4.2.06.png", "R"), ("4.2.06.png", "G"), ("4.2.07.png", "R"),
               ("4.2.07.png", "G"), ("4.2.07.png", "B")}, str(sorted(keys)))
check("all best_baseline = GAP", all(r["best_baseline"] == "GAP" for r in under))
u4207r = next(r for r in under if r["image"] == "4.2.07.png" and r["channel"] == "R")
check("4.2.07 R: CNN MAE higher (8.593 vs 7.481)",
      close(float(u4207r["cnn_mae"]), 8.5931, 1e-3) and close(float(u4207r["baseline_mae"]), 7.4807, 1e-3),
      f"{u4207r['cnn_mae']} vs {u4207r['baseline_mae']}")
u4207b = next(r for r in under if r["image"] == "4.2.07.png" and r["channel"] == "B")
check("4.2.07 B: CNN MAE LOWER (5.300 vs 5.826) but BPP lower",
      close(float(u4207b["cnn_mae"]), 5.3003, 1e-3) and close(float(u4207b["baseline_mae"]), 5.8257, 1e-3),
      f"{u4207b['cnn_mae']} vs {u4207b['baseline_mae']}")

# ------------------------------------------- label structure / zero-error mass
stats = rows("prediction_error_statistics.csv")


def st(img, ch, m):
    return next(r for r in stats if r["image"] == img and r["channel"] == ch and r["method"] == m)


check("4.2.07 B zero-error: GAP 9.93% vs CNN 6.09%",
      close(float(st("4.2.07.png", "B", "GAP")["frac_zero_error"]) * 100, 9.93, 0.01) and
      close(float(st("4.2.07.png", "B", "CNN3x3")["frac_zero_error"]) * 100, 6.09, 0.01),
      f"GAP {float(st('4.2.07.png','B','GAP')['frac_zero_error'])*100:.2f} vs "
      f"CNN {float(st('4.2.07.png','B','CNN3x3')['frac_zero_error'])*100:.2f}")
pooled_n7 = {m: 0.0 for m in ("GAP", "CNN3x3")}
pooled_tot = {m: 0 for m in ("GAP", "CNN3x3")}
for r in stats:
    if r["set"] == "gray":
        continue
    if r["method"] in pooled_n7:
        pooled_tot[r["method"]] += int(r["height"]) * int(r["width"])
        pooled_n7[r["method"]] += float(r["n7_count"]) if "n7_count" in r else 0
# n7_count is int in csv; recompute via frac to be safe
pooled_n7 = {m: sum(float(r["n7_count"]) for r in stats if r["set"] != "gray" and r["method"] == m)
             for m in ("GAP", "CNN3x3")}
pooled_tot = {m: sum(int(r["height"]) * int(r["width"]) for r in stats
                     if r["set"] != "gray" and r["method"] == m)
              for m in ("GAP", "CNN3x3")}
check("pooled n7 (|e|=0) both 8.68%",
      close(pooled_n7["GAP"] / pooled_tot["GAP"] * 100, 8.68, 0.01) and
      close(pooled_n7["CNN3x3"] / pooled_tot["CNN3x3"] * 100, 8.68, 0.01),
      f"GAP {pooled_n7['GAP']/pooled_tot['GAP']*100:.2f} CNN {pooled_n7['CNN3x3']/pooled_tot['CNN3x3']*100:.2f}")
pooled_n0 = {m: sum(float(r["n0_count"]) for r in stats if r["set"] != "gray" and r["method"] == m)
             for m in ("GAP", "CNN3x3")}
check("pooled n0 (|e|>=128): GAP 0.200% vs CNN 0.009%",
      close(pooled_n0["GAP"] / pooled_tot["GAP"] * 100, 0.200, 0.002) and
      close(pooled_n0["CNN3x3"] / pooled_tot["CNN3x3"] * 100, 0.009, 0.002),
      f"GAP {pooled_n0['GAP']/pooled_tot['GAP']*100:.3f} CNN {pooled_n0['CNN3x3']/pooled_tot['CNN3x3']*100:.3f}")

# expected candidates per pixel (recovery-cost claim)
lab = rows("label_histograms.csv")
exp = {}
for m in ("MED", "GAP", "CALIC", "CNN3x3"):
    c = np.zeros(8, dtype=np.int64)
    for r in lab:
        if r["set"] != "gray" and r["method"] == m:
            c += np.array([int(r[f"n{n}_count"]) for n in range(8)])
    exp[m] = float((c * (1 << np.arange(8))).sum()) / c.sum()
check("expected candidates MED 38.3", close(exp["MED"], 38.3, 0.05), f"{exp['MED']:.1f}")
check("expected candidates GAP 40.1", close(exp["GAP"], 40.1, 0.05), f"{exp['GAP']:.1f}")
check("expected candidates CALIC 36.8", close(exp["CALIC"], 36.8, 0.05), f"{exp['CALIC']:.1f}")
check("expected candidates CNN 41.3", close(exp["CNN3x3"], 41.3, 0.05), f"{exp['CNN3x3']:.1f}")

# ------------------------------------------------------------------ runtime
rt = rows("runtime_summary.csv")
rtm = {r["method"]: r for r in rt}
check("runtime CNN3x3 2082 ms", close(float(rtm["CNN3x3 (v4_patch3.pth)"]["mean_ms"]), 2082.2, 5),
      rtm["CNN3x3 (v4_patch3.pth)"]["mean_ms"])
check("runtime vectorized 1761 ms", close(float(rtm["CNN-3x3 vectorized (option 3)"]["mean_ms"]), 1761.1, 5),
      rtm["CNN-3x3 vectorized (option 3)"]["mean_ms"])
check("runtime MED 6.40 ms", close(float(rtm["MED"]["mean_ms"]), 6.40, 0.05), rtm["MED"]["mean_ms"])
check("runtime GAP 20.33 ms", close(float(rtm["GAP"]["mean_ms"]), 20.33, 0.05), rtm["GAP"]["mean_ms"])
check("CNN7x7 15623 ms", close(float(rtm["CNN7x7 (v5_patch7.pth)"]["mean_ms"]), 15623.4, 5),
      rtm["CNN7x7 (v5_patch7.pth)"]["mean_ms"])
check("TOTAL Airplane MED 4666", close(float(rtm["TOTAL(original) Airplane.png MED"]["mean_ms"]), 4665.7, 2),
      rtm["TOTAL(original) Airplane.png MED"]["mean_ms"])
check("TOTAL fast Airplane MED 1622", close(float(rtm["TOTAL(fast-variant) Airplane.png MED"]["mean_ms"]), 1621.98, 2),
      rtm["TOTAL(fast-variant) Airplane.png MED"]["mean_ms"])
check("TOTAL 4.2.03 CNN original 15505", close(float(rtm["TOTAL(original) 4.2.03.png CNN3x3"]["mean_ms"]), 15504.5, 5),
      rtm["TOTAL(original) 4.2.03.png CNN3x3"]["mean_ms"])
check("TOTAL 4.2.03 CNN fast 10317", close(float(rtm["TOTAL(fast-variant) 4.2.03.png CNN3x3"]["mean_ms"]), 10317.4, 5),
      rtm["TOTAL(fast-variant) 4.2.03.png CNN3x3"]["mean_ms"])
rec_air = float(rtm["extract+recover Airplane.png MED"]["mean_ms"])
tot_air = float(rtm["TOTAL(original) Airplane.png MED"]["mean_ms"])
check("Airplane MED recover = 75% of total", close(rec_air / tot_air * 100, 75.4, 1.0),
      f"{rec_air / tot_air * 100:.1f}%")

# ------------------------------------------------------------ improvements
imp = rows("improvement_experiments.csv")
eq = [r for r in imp if r["experiment"] == "equiv_fast_cnn_predict"]
check("4/4 prediction equivalence bitwise", len(eq) == 4 and all(r["variant"] == "True" for r in eq))
eqb = [r for r in imp if r["experiment"] == "equiv_fast_embed_recover"]
check("8/8 embed/recover equivalence + exactness",
      len(eqb) == 8 and all("stego_eq=True" in r["variant"] and "img_exact=True" in r["difference"]
                            and "pay_exact=True" in r["difference"] for r in eqb))
gv = rows("fast_validation_gray.csv")
rv = rows("fast_validation_rgb.csv")
check("fast-path gray 48/48 PASS (6 img x 2 pred x 4 rules)",
      len(gv) == 48 and all(r["status"] == "PASS" for r in gv), f"rows={len(gv)}")
check("fast-path rgb 40/40 PASS (5 img x 2 pred x 4 rules)",
      len(rv) == 40 and all(r["status"] == "PASS" for r in rv), f"rows={len(rv)}")
check("fast-path total 88/88 PASS", len(gv) + len(rv) == 88)
ee = next(r for r in imp if r["experiment"] == "runtime_embed_encrypt" and r["image"] == "4.2.03.png")
check("embed+encrypt 4.2.03 3635->98.7", ee["original"].startswith("3635") and ee["variant"].startswith("98.7"),
      f"{ee['original']} -> {ee['variant']}")
rr = next(r for r in imp if r["experiment"] == "runtime_decrypt_extract_recover" and r["image"] == "4.2.03.png")
check("recover 4.2.03 7488->3597", rr["original"].startswith("7488") and rr["variant"].startswith("3597"),
      f"{rr['original']} -> {rr['variant']}")

# ------------------------------------------------------------- complexity
import torch  # noqa: E402
sys.path.insert(0, str(HERE.parent.parent))
from src.cnn_model import load_model  # noqa: E402

for fname, P, res, want_params, want_macs in (
        ("v4_patch3.pth", 3, True, 46881, 122816),
        ("v1_full.pth", 5, True, 112417, 340928),
        ("v2_no_residual.pth", 5, False, 112353, 340128),
        ("v5_patch7.pth", 7, True, 210721, 668096)):
    m, patch, r_, n = load_model(str(HERE.parent.parent / "models" / fname), device="cpu")
    K = 32
    params = (K * 9 + K) + 2 * K + (K * K * 9 + K) + 2 * K + ((K + K) if res else 0) \
        + (K * P * P * 128 + 128) + 129
    macs = K * 9 * P * P + K * K * 9 * P * P + (K * P * P if res else 0) + K * P * P * 128 + 128
    check(f"{fname} params formula == checkpoint", n == want_params == params, f"{n}")
    check(f"{fname} MAC formula", macs == want_macs, f"{macs:,}")

# ------------------------------------------------------------------ write
out = ["# Phase H — programmatic self-audit of RGB_Complexity_Error_Analysis.md", "",
       "Every numeric claim below was re-derived from the CSV artifacts of this run",
       "(or from the loaded checkpoints for the complexity claims).", "",
       "| # | Check | Status | Detail |", "|---|---|---|---|"]
for i, c in enumerate(checks, 1):
    out.append(f"| {i} | {c['check']} | {c['status']} | {c['detail']} |")
n_fail = sum(1 for c in checks if c["status"] == "FAIL")
out += ["", f"Result: {len(checks) - n_fail}/{len(checks)} PASS, {n_fail} FAIL.",
        "", "Reviewer note: an independent second model was not available in this",
        "environment; this audit is a systematic self-review and is disclosed as such",
        "in the report (§9)."]
(HERE / "review_audit.md").write_text("\n".join(out) + "\n")
print(f"\n{len(checks) - n_fail}/{len(checks)} PASS")
sys.exit(1 if n_fail else 0)
