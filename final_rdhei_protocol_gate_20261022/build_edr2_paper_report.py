#!/usr/bin/env python3
"""Generate EDR2 paper-facing report from run ledgers and optional matched ablation."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def load_json(path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback

def md_table(frame):
    return frame.to_markdown(index=False) if not frame.empty else "_No rows._"

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adaptive-dir", required=True)
    ap.add_argument("--analysis-dir", default=None)
    ap.add_argument("--literature-file", default="EDR2_LITERATURE_COMPARISON.md")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    adaptive = Path(args.adaptive_dir)
    analysis_dir = Path(args.analysis_dir) if args.analysis_dir else None
    cap = pd.read_csv(adaptive / "capacity_summary.csv")
    rt = pd.read_csv(adaptive / "roundtrip_summary.csv")
    integrity = load_json(adaptive / "integrity.json", {})
    algebra = load_json(adaptive / "algebra.json", {})
    negatives = load_json(adaptive / "negative_checks_and_rejections.json", [])
    manifest = load_json(adaptive / "input_manifest.json", {})
    validation = load_json(analysis_dir / "analysis_validation.json", {}) if analysis_dir else {}

    total = len(cap)
    accepted = int(cap["accepted"].astype(str).str.lower().eq("true").sum())
    rejected = total - accepted
    classes = cap["classification"].fillna("unspecified").value_counts().to_dict()
    groups = cap.groupby(["corpus_group", "classification"], dropna=False).agg(
        images=("image", "count"),
        accepted=("accepted", lambda x: x.astype(str).str.lower().eq("true").sum()),
        mean_signed_net_bpp=("signed_net_bpp", "mean"),
        median_signed_net_bpp=("signed_net_bpp", "median"),
        mean_net_bits=("net_capacity_bits", "mean"),
        median_net_bits=("net_capacity_bits", "median"),
    ).reset_index()

    phase_rows = []
    for p in range(4):
        values = pd.to_numeric(cap[f"phase{p}_net_capacity_bits"], errors="coerce")
        phase_rows.append({
            "Phase": p, "Images": int(values.notna().sum()),
            "Positive capacity": int((values > 0).sum()),
            "Rejected": int((values <= 0).sum()),
            "Mean signed net bpp": float((values / cap["pixels"]).mean()),
            "Median signed net bpp": float((values / cap["pixels"]).median()),
            "Mean net bits": float(values.mean()),
            "Median net bits": float(values.median()),
        })
    phase_table = pd.DataFrame(phase_rows)
    selected = cap["selected_lattice_phase"].value_counts().sort_index()
    gain = pd.to_numeric(cap["phase_selection_gain_bits"], errors="coerce")
    def as_bool(series):
        return series.map(lambda value: value if isinstance(value, bool) else str(value).strip().lower() == "true")

    image_exact = as_bool(rt["image_exact"])
    payload_exact = as_bool(rt["payload_exact"])
    roundtrips = []
    for case, frame in rt.groupby("case", sort=False):
        n = len(frame)
        roundtrips.append({
            "Payload case": case, "Tests": n,
            "Exact image": int(as_bool(frame["image_exact"]).sum()),
            "Exact payload": int(as_bool(frame["payload_exact"]).sum()),
        })
    roundtrip_table = pd.DataFrame(roundtrips)
    cluster_counts = manifest.get("correlation_cluster_counts", {})
    checkpoint = integrity.get("checkpoint_sha256", "not recorded")
    report = [
        "# EDR2 paper-evidence report",
        "",
        "## Run provenance",
        f"- Adaptive run directory: {adaptive}",
        f"- Distinct evaluation inputs: {total}",
        f"- Positive signed-net images: {accepted}",
        f"- Non-positive signed-net rejections: {rejected}",
        f"- Classifications: {json.dumps(classes, sort_keys=True)}",
        f"- Unique correlation clusters: {len(cluster_counts) if cluster_counts else 'not recorded'}",
        f"- Frozen checkpoint SHA-256: {checkpoint}",
        f"- Retraining performed: {integrity.get('model_training_performed', False)}",
        "",
    ]
    missing = manifest.get("missing_original_baseline_stems", [])
    if missing:
        report += [
            "**Six-image baseline status:** not complete in this run.",
            f"Missing baseline stems recorded by the runner: {', '.join(missing)}.",
            "Do not describe this as a combined six-baseline plus USC-SIPI experiment. A matched six-image run is pending until the exact original files are supplied.",
            "",
        ]
    else:
        report += ["**Six-image baseline status:** all six project baseline PNGs were present in this run.", ""]
    report += ["## Curated corpus summary", "", md_table(groups.round(4)), ""]
    report += ["## Four-phase capacity summary", "", md_table(phase_table.round(4)), ""]
    report += [
        f"- Adaptive selected phase counts: {json.dumps({int(k): int(v) for k, v in selected.items()}, sort_keys=True)}",
        f"- Images with higher adaptive capacity than phase 0: {int((gain > 0).sum())}",
        f"- Images tied with phase 0: {int((gain == 0).sum())}",
        f"- Images worse than phase 0: {int((gain < 0).sum())}",
        "",
    ]
    report += ["## Exact recovery and payload extraction", "", md_table(roundtrip_table), ""]
    report += [
        f"- Total round-trip cases: {len(rt)}",
        f"- Exact image recovery: {int(image_exact.sum())}/{len(rt)}",
        f"- Exact payload extraction: {int(payload_exact.sum())}/{len(rt)}",
        f"- Negative/rejection ledger records: {len(negatives)}",
        f"- Mapping pairs checked: {algebra.get('pairs_checked', algebra.get('pairs', 'not recorded'))}",
        f"- Valid payload words checked: {algebra.get('payload_words_checked', algebra.get('payload_words', 'not recorded'))}",
        f"- Mapping failures: {algebra.get('failures', 'not recorded')}",
        "",
    ]
    report += ["## Fixed-phase matched-ablation verification", ""]
    if validation:
        report += [
            "The fixed-phase analysis artifact is present and contains the following checks:",
            "",
            "Analysis validation JSON:",
            json.dumps(validation, indent=2, sort_keys=True),
            "",
            "The analysis is accepted only when source paths, file hashes, decoded-pixel hashes and dimensions match, and each fixed-phase capacity reproduces the adaptive run's corresponding phase score.",
            "",
        ]
    else:
        report += [
            "No matched fixed-phase analysis artifact was supplied to this report generator. The phase columns above are the four phase-specific capacities calculated during the adaptive run; they do not alone establish four independent fixed-phase end-to-end recovery runs.",
            "",
        ]
    report += [
        "## Interpretation and limitations",
        "",
        "Do not pool rotated texture variants or sequence frames as independent photographs. Use the correlation-cluster summary and cluster-bootstrap intervals for family-aware inference. Keep the descriptive sequence subgroups separate where the USC-SIPI catalogue identifies different motion characteristics, while retaining the shared sequence identifier for overall dependence analysis.",
        "",
        "Published RDHEI rates are contextual only unless datasets, pixel sets, encryption stages, receiver inputs and overhead accounting are harmonized. The accompanying literature comparison records these limitations; it is not a matched implementation benchmark.",
        "",
        "No state-of-the-art or superiority claim is established by this report. The candidate contribution is limited to the specific CNN-receptive-field-safe lattice, exact prediction synchronization after candidate writes, and authenticated in-band phase discovery, subject to full-text prior-art review and matched experiments.",
        "",
        "## Reproducible tables and figures",
        "",
    ]
    if analysis_dir and analysis_dir.exists():
        for path in sorted(analysis_dir.glob("*.csv")):
            report.append(f"- {path.name}")
        for path in sorted(analysis_dir.glob("fig*.png")):
            report.append(f"- {path.name}")
    lit = Path(args.literature_file)
    if lit.is_file():
        report += ["", f"Detailed related-work matrix: {lit.name}", ""]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
