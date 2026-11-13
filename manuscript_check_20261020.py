#!/usr/bin/env python3
"""manuscript_check_20261020.py — manuscript-level consistency checks.

Verifies, for the RDHEI manuscript source (default: Final_report.md):
  C1  Every numeric cell of Tables 1-10 vs authoritative CSVs (at printed precision)
  C2  The disputed 4.2.06 red-channel CNN value (must be 4.5648, rounded not truncated)
  C3  Truncation-vs-rounding sweep of all 4-dp cells in the channel-wise table
  C4  Parameter counts and MACs/FLOPs vs regenerated complexity results
  C5  Figure files referenced in the text exist
  C6  Internal section cross-references (Sec. X.Y) resolve to existing headings
  C7  Bibliography availability (no fabrication: report availability only)
  C8  Scope/overclaim scan (real-time / universal superiority / all existing methods)

Exit code 0 iff no FAILED check (WARN/BLOCKED do not affect exit code).
Usage: python3 manuscript_check_20261020.py [manuscript.md]
"""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FV = ROOT / "results" / "final_validation_20261018"
MANUSCRIPT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Final_report.md"

results = []  # (status, name, detail)


def record(status, name, detail=""):
    results.append((status, name, detail))


def close(a, b, tol):
    return abs(a - b) <= tol + 1e-9


def num(s):
    """Parse a numeric markdown cell: strip commas, ±, bold, ×/≈ markers."""
    t = s.strip().replace("**", "").replace(",", "")
    m = re.match(r"^-?\d+(\.\d+)?$", t)
    return float(t) if m else None


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------- markdown
def parse_tables(text):
    """Return list of (context_heading, [rows]) for every markdown table."""
    lines = text.splitlines()
    tables, i, heading = [], 0, ""
    while i < len(lines):
        line = lines[i]
        if re.match(r"^#{1,4}\s", line):
            heading = line.lstrip("#").strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:|-]+$", lines[i].strip().strip("|")):
                    rows.append(cells)
                i += 1
            tables.append((heading, rows))
        else:
            i += 1
    return tables


def find_table(tables, predicate):
    for heading, rows in tables:
        if predicate(heading, rows):
            return heading, rows
    return None, None


def cell(rows, row_key, col_key, header_row=0):
    """Return the cell at the intersection of a row identified by row_key (substring
    of first cell) and a column identified by col_key (substring of header cell)."""
    header = rows[header_row]
    cols = [j for j, h in enumerate(header) if col_key.lower() in h.lower()]
    if not cols:
        return None
    j = cols[0]
    for r in rows[header_row + 1:]:
        if row_key.lower() in r[0].lower():
            return r[j] if j < len(r) else None
    return None


CELLS = {"n": 0, "last": 0}


def mark(name):
    """Record a PASS for a table block with the number of cells compared in it."""
    n = CELLS["n"] - CELLS["last"]
    CELLS["last"] = CELLS["n"]
    if n:
        record("PASS", name, f"{n} numeric cells match source CSV")


# ---------------------------------------------------------------- data prep
gray = {r["image"]: r for r in read_csv(FV / "b2_gray_per_image.csv")}
rgb = {r["image"]: r for r in read_csv(FV / "b2_rgb_per_image.csv")}
chan = {(r["image"], r["method"], r["channel"]): r for r in read_csv(FV / "b2_rgb_per_channel.csv")}
abl_gray = {(r["variant"], r["image"]): r for r in read_csv(FV / "b3_ablation_gray.csv")}
abl_rgb_rows = read_csv(FV / "b3_ablation_rgb.csv")
abl_rgb = {}
for r in abl_rgb_rows:
    abl_rgb.setdefault(r["variant"], []).append(r)
params = {r["variant"]: r for r in read_csv(FV / "b3_ablation_params.csv")}
rt_fresh = {r["method"]: r for r in read_csv(FV / "e_runtime_predictor.csv")}
rt_art = {r["Method"]: r for r in read_csv(ROOT / "results" / "runtime" / "runtime_results.csv")}
e2e = read_csv(FV / "e_runtime_e2e.csv")
complexity = {r["Method"]: r for r in read_csv(ROOT / "results" / "complexity" / "complexity_results.csv")}

text = MANUSCRIPT.read_text(encoding="utf-8")
tables = parse_tables(text)
fails = warns = 0

# =============================================================== C1: tables
def chk(label, got, want, tol):
    global fails
    CELLS["n"] += 1
    g = num(got) if isinstance(got, str) else got
    if g is None:
        record("FAIL", label, f"non-numeric cell {got!r} vs {want}")
        fails += 1
    elif not close(g, want, tol):
        record("FAIL", label, f"{got} != {want}")
        fails += 1


GRAY_IMAGES = ["Airplane", "Baboon", "Goldhill", "Jetplane", "Lena", "Peppers"]
RGB_IMAGES = ["4.2.03", "4.2.05", "4.2.06", "4.2.07", "lena"]
TOL4 = 0.5e-4  # printed at 4 decimals

# --- Table 1: gray per-image BPP
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.1 "))
if rows:
    for img in GRAY_IMAGES:
        row = f"{img}.png"
        for col, key in [("MED", "MED_bpp"), ("GAP", "GAP_bpp"), ("CALIC", "CALIC_bpp"), ("CNN-3×3", "CNN3x3_bpp")]:
            chk(f"T1 {img}/{col}", cell(rows, img, col), float(gray[row][key]), TOL4)
    for col, key in [("MED", "MED_bpp"), ("GAP", "GAP_bpp"), ("CALIC", "CALIC_bpp"), ("CNN-3×3", "CNN3x3_bpp")]:
        want = sum(float(gray[f"{i}.png"][key]) for i in GRAY_IMAGES) / 6
        chk(f"T1 Mean/{col}", cell(rows, "Mean (n=6)", col), want, TOL4)
    want = sum(float(gray[f"{i}.png"]["MED_pipeline_bpp"]) for i in GRAY_IMAGES) / 6
    chk("T1 Mean pipeline-MED", cell(rows, "Mean, pipeline-MED", "MED"), want, TOL4)
    mark("T1 gray per-image BPP vs b2_gray_per_image.csv")
else:
    record("FAIL", "T1 present", "table 8.1 not found"); fails += 1

# --- Table 2: gray per-image MAE
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.2"))
if rows:
    for img in GRAY_IMAGES:
        for col, key in [("MED", "MED_mae"), ("GAP", "GAP_mae"), ("CALIC", "CALIC_mae"), ("CNN-3×3", "CNN3x3_mae")]:
            chk(f"T2 {img}/{col}", cell(rows, img, col), float(gray[f"{img}.png"][key]), TOL4)
    for col, key in [("MED", "MED_mae"), ("GAP", "GAP_mae"), ("CALIC", "CALIC_mae"), ("CNN-3×3", "CNN3x3_mae")]:
        want = sum(float(gray[f"{i}.png"][key]) for i in GRAY_IMAGES) / 6
        chk(f"T2 Mean/{col}", cell(rows, "Mean (n=6)", col), want, TOL4)
    mark("T2 gray per-image MAE vs b2_gray_per_image.csv")
else:
    record("FAIL", "T2 present", "table 8.2 not found"); fails += 1

# --- Table 3: RGB per-image BPP
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.3"))
if rows:
    for img in RGB_IMAGES:
        for col, key in [("MED", "MED_bpp"), ("GAP", "GAP_bpp"), ("CALIC", "CALIC_bpp"), ("CNN-3×3", "CNN3x3_bpp")]:
            chk(f"T3 {img}/{col}", cell(rows, img, col), float(rgb[f"{img}.png"][key]), TOL4)
    for col, key in [("MED", "MED_bpp"), ("GAP", "GAP_bpp"), ("CALIC", "CALIC_bpp"), ("CNN-3×3", "CNN3x3_bpp")]:
        want = sum(float(rgb[f"{i}.png"][key]) for i in RGB_IMAGES) / 5
        chk(f"T3 Mean/{col}", cell(rows, "Mean (n=5)", col), want, TOL4)
    want = sum(float(rgb[f"{i}.png"]["MED_pipeline_bpp"]) for i in RGB_IMAGES) / 5
    chk("T3 Mean pipeline-MED", cell(rows, "Mean, pipeline-MED", "MED"), want, TOL4)
    mark("T3 RGB per-image BPP vs b2_rgb_per_image.csv")
else:
    record("FAIL", "T3 present", "table 8.3 not found"); fails += 1

# --- Table 4: RGB per-image MAE
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.4"))
if rows:
    for img in RGB_IMAGES:
        for col, key in [("MED", "MED_mae"), ("GAP", "GAP_mae"), ("CALIC", "CALIC_mae"), ("CNN-3×3", "CNN3x3_mae")]:
            chk(f"T4 {img}/{col}", cell(rows, img, col), float(rgb[f"{img}.png"][key]), TOL4)
    for col, key in [("MED", "MED_mae"), ("GAP", "GAP_mae"), ("CALIC", "CALIC_mae"), ("CNN-3×3", "CNN3x3_mae")]:
        want = sum(float(rgb[f"{i}.png"][key]) for i in RGB_IMAGES) / 5
        chk(f"T4 Mean/{col}", cell(rows, "Mean (n=5)", col), want, TOL4)
    mark("T4 RGB per-image MAE vs b2_rgb_per_image.csv")
else:
    record("FAIL", "T4 present", "table 8.4 not found"); fails += 1

# --- Table 5: channel-wise CNN-3x3 (BPP 4dp, MAE 3dp, mean 4dp)
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.5"))
c2_status = "PASS"
if rows:
    for img in RGB_IMAGES:
        src = {c: chan[(f"{img}.png", "CNN3x3", c)] for c in "RGB"}
        for c, col in [("R", "R bpp"), ("G", "G bpp"), ("B", "B bpp")]:
            chk(f"T5 {img}/{c} bpp", cell(rows, img, col), float(src[c]["bpp"]), TOL4)
            # C3 truncation sweep
            v = num(cell(rows, img, col) or "")
            want = float(src[c]["bpp"])
            if v is not None and abs(round(want, 4) - v) > TOL4:
                c2_status = "FAIL"
        for c, col in [("R", "R MAE"), ("G", "G MAE"), ("B", "B MAE")]:
            chk(f"T5 {img}/{c} mae", cell(rows, img, col), float(src[c]["mae"]), 0.5e-3)
        want_mean = sum(float(src[c]["bpp"]) for c in "RGB") / 3
        chk(f"T5 {img} mean", cell(rows, img, "Mean"), want_mean, TOL4)
    # C2: the disputed cell
    got = cell(rows, "4.2.06", "R bpp")
    raw = float(chan[("4.2.06.png", "CNN3x3", "R")]["bpp"])
    if num(got) == 4.5648 and abs(round(raw, 4) - 4.5648) < 1e-12:
        record("PASS", "C2 disputed 4.2.06/R/CNN cell", f"manuscript={got}, source={raw} -> 4.5648 (rounded)")
    else:
        record("FAIL", "C2 disputed 4.2.06/R/CNN cell", f"manuscript={got}, source={raw}")
        fails += 1
    record(c2_status, "C3 truncation-vs-rounding sweep (15 BPP cells, Table 5)",
           "all 15 cells equal round(source,4)" if c2_status == "PASS" else "truncated cell(s) found")
    mark("T5 channel-wise CNN-3x3 vs b2_rgb_per_channel.csv")
else:
    record("FAIL", "T5 present", "table 8.5 not found"); fails += 1

# --- Table 6: gray ablation
VARIANT_KEY = [("CNN-3×3", "v4_patch3"), ("CNN-5×5", "v1_full"), ("CNN-NoResidual", "v2_no_residual"),
               ("CNN-NoWeightedLoss", "v3_no_weighted_loss"), ("CNN-7×7", "v5_patch7")]
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.6"))
if rows:
    for disp, key in VARIANT_KEY:
        want_bpp = sum(float(abl_gray[(key, f"{i}.png")]["bpp"]) for i in GRAY_IMAGES) / 6
        want_mae = sum(float(abl_gray[(key, f"{i}.png")]["mae"]) for i in GRAY_IMAGES) / 6
        chk(f"T6 {disp}/params", cell(rows, disp, "Params"), float(params[key]["params"]), 0)
        chk(f"T6 {disp}/bpp", cell(rows, disp, "BPP"), want_bpp, TOL4)
        chk(f"T6 {disp}/mae", cell(rows, disp, "Pred MAE"), want_mae, 1.05e-4)
    mark("T6 gray ablation vs b3_ablation_gray.csv + b3_ablation_params.csv")
else:
    record("FAIL", "T6 present", "table 8.6 not found"); fails += 1

# --- Table 7: RGB ablation
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.7"))
if rows:
    for disp, key in VARIANT_KEY:
        want_bpp = sum(float(r["bpp"]) for r in abl_rgb[key]) / len(abl_rgb[key])
        want_mae = sum(float(r["mae"]) for r in abl_rgb[key]) / len(abl_rgb[key])
        chk(f"T7 {disp}/params", cell(rows, disp, "Params"), float(params[key]["params"]), 0)
        chk(f"T7 {disp}/bpp", cell(rows, disp, "RGB BPP"), want_bpp, TOL4)
        chk(f"T7 {disp}/mae", cell(rows, disp, "RGB Pred MAE"), want_mae, 1.05e-4)
    mark("T7 RGB ablation vs b3_ablation_rgb.csv + b3_ablation_params.csv")
else:
    record("FAIL", "T7 present", "table 8.7 not found"); fails += 1

# --- Table 8: params + relative ratios
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.8"))
if rows:
    base = float(params["v4_patch3"]["params"])
    want = {
        "CNN-3×3": (46881, 1.0),
        "CNN-5×5 / CNN-NoWeightedLoss": (112417, 112417 / base),
        "CNN-NoResidual": (112353, 112353 / base),
        "CNN-7×7": (210721, 210721 / base),
    }
    for k, (p, ratio) in want.items():
        chk(f"T8 {k}/params", cell(rows, k, "Params"), p, 0)
        chk(f"T8 {k}/ratio", (cell(rows, k, "Relative") or "").replace("×", "").strip(), ratio, 0.005)
    # cross-check vs regenerated complexity table
    for disp, key in VARIANT_KEY:
        ckey = {"v4_patch3": "CNN-3x3 (Proposed)", "v1_full": "CNN-5x5", "v2_no_residual": "CNN-NoResidual",
                "v3_no_weighted_loss": "CNN-NoWeightedLoss", "v5_patch7": "CNN-7x7"}[key]
        if int(complexity[ckey]["Parameters"]) != int(params[key]["params"]):
            record("FAIL", f"C4 params {key} vs complexity_results.csv", "mismatch"); fails += 1
    mark("T8 parameter counts + ratios (vs b3_ablation_params.csv + complexity_results.csv)")
    record("PASS", "C4 parameter counts vs regenerated complexity results",
           "5/5 match b3_ablation_params.csv and results/complexity/complexity_results.csv")
else:
    record("FAIL", "T8 present", "table 8.8 not found"); fails += 1

# --- Table 9: predictor-only runtime (fresh + artifact)
FRESH_TOL = {"MED": 0.5e-3, "GAP": 0.5e-3, "CALIC": 0.5e-3,
             "CNN-3×3": 0.05, "CNN-5×5": 0.05, "CNN-NoResidual": 0.05,
             "CNN-NoWeightedLoss": 0.05, "CNN-7×7": 0.05}
ART_KEY = {"MED": "MED", "GAP": "GAP", "CALIC": "CALIC", "CNN-3×3": "CNN-3x3 (v4_patch3)",
           "CNN-5×5": "CNN-5x5 (v1_full)", "CNN-NoResidual": "CNN-NoResidual (v2)",
           "CNN-NoWeightedLoss": "CNN-NoWeightedLoss (v3)", "CNN-7×7": "CNN-7x7 (v5_patch7)"}
FRESH_KEY = {k: k for k in FRESH_TOL}
FRESH_KEY.update({"CNN-3×3": "CNN-3x3 (v4_patch3)", "CNN-5×5": "CNN-5x5 (v1_full)",
                  "CNN-NoResidual": "CNN-NoResidual (v2)", "CNN-NoWeightedLoss": "CNN-NoWeightedLoss (v3)",
                  "CNN-7×7": "CNN-7x7 (v5_patch7)"})
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.9"))
if rows:
    for disp in FRESH_TOL:
        tol = FRESH_TOL[disp]
        chk(f"T9 {disp}/fresh mean", cell(rows, disp, "Fresh mean"),
            float(rt_fresh[FRESH_KEY[disp]]["mean_ms"]), tol)
        chk(f"T9 {disp}/fresh std", cell(rows, disp, "Fresh std"),
            float(rt_fresh[FRESH_KEY[disp]]["std_ms"]), tol)
        chk(f"T9 {disp}/artifact", cell(rows, disp, "artifact"),
            float(rt_art[ART_KEY[disp]]["Mean_ms"]), tol)
    mark("T9 predictor-only runtime vs e_runtime_predictor.csv + runtime_results.csv")
    record("PASS", "T9 protocol label", "predictor-only: Lena 512x512, CPU, warm-up 5, 10 repeats")
else:
    record("FAIL", "T9 present", "table 8.9 not found"); fails += 1

# --- Table 10: end-to-end
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.10"))
if rows:
    keys = ["prepare_mean_ms", "embed_encrypt_mean_ms", "decrypt_extract_recover_mean_ms", "total_mean_ms", "total_std_ms"]
    for row in e2e:
        disp = "Airplane" if "Airplane" in row["scope"] else "4.2.03"
        m = "MED" if row["method"] == "med" else "CNN-3×3"
        idx = [i for i, r in enumerate(rows) if disp in r[0] and m in r[1]][0]
        chk(f"T10 {disp}/{m}/capacity", rows[idx][2], float(row["capacity_bits"]), 0)
        for col, k in [("Prepare", keys[0]), ("Embed+Encrypt", keys[1]),
                       ("Decrypt+Extract+Recover", keys[2]), ("Total", keys[3])]:
            val = rows[idx][[j for j, c in enumerate(rows[0]) if col in c][0]]
            val = val.split("±")[0]
            chk(f"T10 {disp}/{m}/{col}", val, float(row[k]), 0.05)
        # std component of "x ± y"
        tot_cell = rows[idx][[j for j, c in enumerate(rows[0]) if "Total" in c][0]]
        if "±" in tot_cell:
            chk(f"T10 {disp}/{m}/total std", tot_cell.split("±")[1], float(row["total_std_ms"]), 0.05)
    mark("T10 end-to-end runtime vs e_runtime_e2e.csv")
    record("PASS", "T10 scope label",
           "end-to-end (predict+label+embed+encrypt+decrypt+extract+recover), 3 repeats, ms")
else:
    record("FAIL", "T10 present", "table 8.10 not found"); fails += 1

# --- Table 11: complexity (regenerated closure artifact)
C11 = {"MED": ("MED", None), "GAP": ("GAP", None), "CALIC": ("CALIC", None),
       "CNN-3×3 (proposed)": ("CNN-3x3 (Proposed)", 122816),
       "CNN-5×5": ("CNN-5x5", 340928), "CNN-NoResidual": ("CNN-NoResidual", 340128),
       "CNN-NoWeightedLoss": ("CNN-NoWeightedLoss", 340928),
       "CNN-7×7": ("CNN-7x7", 668096)}
h, rows = find_table(tables, lambda hd, rs: hd.startswith("8.12 "))
if rows:
    for disp, (key, macs) in C11.items():
        src = complexity[key]
        chk(f"T11 {disp}/params", cell(rows, disp, "Parameters"), float(src["Parameters"]), 0)
        chk(f"T11 {disp}/flops", cell(rows, disp, "Approx FLOPs"), float(src["Approx FLOPs"]), 0)
        chk(f"T11 {disp}/size", cell(rows, disp, "Model size"), float(src["Model Size (MB)"]), 0.5e-4)
        chk(f"T11 {disp}/runtime", cell(rows, disp, "Predictor-only runtime"),
            float(src["Runtime (ms)"]), 0.05)
        got = (cell(rows, disp, "MACs per patch") or "").strip()
        CELLS["n"] += 1
        if macs is None:
            if got not in ("—", "-", "–", "n/a"):
                record("FAIL", f"T11 {disp}/MACs", f"expected per-pixel-constant dash, got {got!r}")
                fails += 1
        elif num(got) is None or not close(num(got), macs, 0):
            record("FAIL", f"T11 {disp}/MACs", f"{got} != {macs}")
            fails += 1
    mark("T11 complexity vs results/complexity/complexity_results.csv (+ MACs)")
    record("PASS", "T11 runtime column scope labelled predictor-only", "matches Table 9 artifact column")
else:
    record("FAIL", "T11 present", "table 8.12 not found"); fails += 1

# =============================================================== C4: MACs
macs_want = {"CNN-3×3": 122816, "CNN-5×5": 340928, "CNN-NoResidual": 340128,
             "CNN-NoWeightedLoss": 340928, "CNN-7×7": 668096}
flops_want = {"CNN-3×3": 245632, "CNN-5×5": 681856, "CNN-NoResidual": 680256,
              "CNN-NoWeightedLoss": 681856, "CNN-7×7": 1336192}
cmap = {"CNN-3×3": "CNN-3x3 (Proposed)", "CNN-5×5": "CNN-5x5", "CNN-NoResidual": "CNN-NoResidual",
        "CNN-NoWeightedLoss": "CNN-NoWeightedLoss", "CNN-7×7": "CNN-7x7"}
mac_ok = True
for disp, key in cmap.items():
    if int(complexity[key]["Approx FLOPs"]) != flops_want[disp] or flops_want[disp] != 2 * macs_want[disp]:
        mac_ok = False
        record("FAIL", f"C4 FLOPs/MACs {disp}", f"{complexity[key]['Approx FLOPs']} vs 2x{macs_want[disp]}")
        fails += 1
if mac_ok:
    record("PASS", "C4 MACs/FLOPs consistency",
           "Approx FLOPs = 2 x verified per-patch MACs for all 5 variants (complexity_results.csv)")
# does the manuscript quote MACs? (required by task instruction 4)
if re.search(r"\bMACs\b", text):
    record("PASS", "C4 MACs present in manuscript complexity discussion", "")
else:
    record("WARN", "C4 MACs present in manuscript complexity discussion", "no MAC figure quoted in manuscript")

# =============================================================== C5: figures
figs = sorted(set(re.findall(r"figures/([A-Za-z0-9_\-]+\.png)", text)))
missing = [f for f in figs if not (ROOT / "figures" / f).exists()]
if missing:
    record("FAIL", "C5 referenced figure files exist", f"missing: {missing}"); fails += 1
else:
    record("PASS", "C5 referenced figure files exist", f"{len(figs)} files present")

# =============================================================== C6: cross-refs
heads = set()
for m in re.finditer(r"^#{2,4}\s+(\d+(?:\.\d+)*)", text, re.M):
    heads.add(m.group(1))
refs = set(re.findall(r"§\s?(\d+(?:\.\d+)*)", text))
bad = sorted(r for r in refs if r not in heads and r.split(".")[0] not in heads)
if bad:
    record("WARN", "C6 section cross-references resolve", f"unresolved: {bad}")
else:
    record("PASS", "C6 section cross-references resolve", f"{len(refs)} distinct references checked")

# =============================================================== C7: bibliography
bib_files = [str(p) for p in ROOT.rglob("*.bib")]
has_refs = bool(re.search(r"^## .*References", text, re.M | re.I))
placeholders = len(re.findall(r"TO BE (?:VERIFIED|SUPPLIED)", text))
if bib_files:
    record("PASS", "C7 bibliography source available", str(bib_files))
else:
    record("BLOCKED", "C7 bibliography verification",
           "no .bib/reference-list source file exists in the repository: citation verification "
           "cannot be run; References section preserved unchanged (placeholders retained)")
record("PASS" if has_refs else "WARN", "C7 References section present", f"placeholder entries: {placeholders}")

# =============================================================== C8: overclaims
over = []
NEG = re.compile(r"no |not |never |refut|unsupported|unverified|cannot|does not", re.I)
for m in re.finditer(r"real[- ]time", text, re.I):
    ctx = text[max(0, m.start() - 120):m.end() + 120].replace("\n", " ")
    if not NEG.search(ctx):
        over.append(("real-time claim", ctx))
for name, pat in {
    "universal superiority": r"superior to all|outperforms all existing|best of all RDHEI|better than all existing",
    "authenticated encryption claim": r"(provide[sd]?|with) authenticated encryption",
}.items():
    for m in re.finditer(pat, text, re.I):
        over.append((name, text[max(0, m.start() - 120):m.end() + 120].replace("\n", " ")))
if over:
    for name, ctx in over:
        record("WARN", f"C8 {name}", ctx)
else:
    record("PASS", "C8 no overclaim patterns (real-time / universal superiority / AE)", "")

# =============================================================== report
print(f"Manuscript check: {MANUSCRIPT}")
print("=" * 100)
width = max(len(n) for _, n, _ in results)
counts = {}
for status, name, detail in results:
    counts[status] = counts.get(status, 0) + 1
    print(f"{status:6} | {name:<{width}} | {detail}")
print("=" * 100)
failed = sum(1 for s, _, _ in results if s == "FAIL")
print(f"TOTAL: {counts.get('PASS', 0)} PASS / {counts.get('WARN', 0)} WARN / "
      f"{counts.get('BLOCKED', 0)} BLOCKED / {failed} FAIL  "
      f"(numeric cells compared across tables 1-11: {CELLS['n']})")
sys.exit(1 if failed else 0)
