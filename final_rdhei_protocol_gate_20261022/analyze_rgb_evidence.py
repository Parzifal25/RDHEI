#!/usr/bin/env python3
"""Generate paper-facing CC-EDR2-RGB tables and plots from a corpus run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BLENDS = (0, 1, 2, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    evidence = Path(args.evidence_dir).resolve()
    output = Path(args.output_dir).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    capacity = pd.read_csv(evidence / "rgb_capacity_summary.csv")
    roundtrip = pd.read_csv(evidence / "rgb_roundtrip_summary.csv")
    assignments = pd.read_csv(evidence / "rgb_phase_assignment_scores.csv")
    run = json.loads((evidence / "rgb_run_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((evidence / "rgb_input_manifest.json").read_text(encoding="utf-8"))

    capacity["status"] = capacity["status"].fillna("unknown")
    rows = []
    mae_rows = []
    assignment_frequency_rows = []
    detailed_assignment_rows = []

    for blend in BLENDS:
        cap_col = f"blend_{blend}_net_capacity_bits"
        bpp_col = f"blend_{blend}_net_bpp"
        if cap_col not in capacity:
            continue
        values = pd.to_numeric(capacity[cap_col], errors="coerce")
        usable = values.dropna()
        success_images = int(
            ((values > 0) & capacity["status"].isin(["roundtrip_passed", "roundtrip_failed"])).sum()
        )
        rows.append({
            "cross_blend": f"{blend}/4",
            "images_with_capacity": int(usable.notna().sum()),
            "positive_net_images": int((usable > 0).sum()),
            "nonpositive_net_images": int((usable <= 0).sum()),
            "mean_signed_net_bits": float(usable.mean()) if len(usable) else np.nan,
            "median_signed_net_bits": float(usable.median()) if len(usable) else np.nan,
            "mean_signed_net_bpp_per_rgb_pixel": float(pd.to_numeric(capacity[bpp_col], errors="coerce").mean()),
            "median_signed_net_bpp_per_rgb_pixel": float(pd.to_numeric(capacity[bpp_col], errors="coerce").median()),
            "images_better_than_spatial_only": np.nan if blend == 0 else int(
                (values > pd.to_numeric(capacity["blend_0_net_capacity_bits"], errors="coerce")).sum()
            ),
            "images_with_roundtrip": success_images if blend == 1 else 0,
        })
        for channel in range(3):
            for metric in ("spatial_mae", "cross_channel_mae", "fused_mae"):
                col = f"blend_{blend}_channel_{channel}_{metric}"
                if col not in capacity:
                    continue
                v = pd.to_numeric(capacity[col], errors="coerce").dropna()
                mae_rows.append({
                    "cross_blend": f"{blend}/4",
                    "channel": ("R", "G", "B")[channel],
                    "predictor": metric,
                    "images": len(v),
                    "mean_mae": float(v.mean()) if len(v) else np.nan,
                    "median_mae": float(v.median()) if len(v) else np.nan,
                    "std_mae": float(v.std(ddof=1)) if len(v) > 1 else np.nan,
                })

        subset = assignments[assignments["blend_num"] == blend]
        if len(subset):
            tuples = subset["selected_phases_rgb"].astype(str).value_counts()
            for assignment, count in tuples.items():
                assignment_frequency_rows.append({
                    "cross_blend": f"{blend}/4",
                    "selected_rgb_phase_tuple": assignment,
                    "image_count": int(count),
                })
            for _, row in subset.iterrows():
                scores = json.loads(row["phase_assignment_scores_json"])
                for score in scores:
                    detailed_assignment_rows.append({
                        "image": row["image"],
                        "pixels_sha256": row["pixels_sha256"],
                        "cross_blend": f"{blend}/4",
                        "rgb_phases": json.dumps(score["phases"]),
                        "calibration_phase": score["calibration_phase"],
                        "directory_bytes": score["directory_bytes"],
                        "net_capacity_bits": score["net_capacity_bits"],
                    })

    blend_summary = pd.DataFrame(rows)
    mae_summary = pd.DataFrame(mae_rows)
    assignment_frequency = pd.DataFrame(assignment_frequency_rows)
    assignment_details = pd.DataFrame(detailed_assignment_rows)

    roundtrip["passed_bool"] = roundtrip["passed"].astype(str).str.lower().eq("true")
    rt_summary = roundtrip.groupby("case", sort=False).agg(
        tests=("image", "count"),
        passed=("passed_bool", "sum"),
        payload_bits_min=("payload_bits", "min"),
        payload_bits_max=("payload_bits", "max"),
    ).reset_index()
    rt_summary["failed"] = rt_summary["tests"] - rt_summary["passed"]

    capacity.to_csv(output / "rgb_per_image_capacity_and_prediction.csv", index=False)
    blend_summary.to_csv(output / "rgb_blend_ablation_summary.csv", index=False)
    mae_summary.to_csv(output / "rgb_prediction_mae_summary.csv", index=False)
    assignment_frequency.to_csv(output / "rgb_selected_phase_frequency.csv", index=False)
    assignment_details.to_csv(output / "rgb_all_24_phase_assignments_per_image.csv", index=False)
    rt_summary.to_csv(output / "rgb_exact_recovery_summary.csv", index=False)

    if len(blend_summary):
        plt.figure(figsize=(9, 5))
        labels = blend_summary["cross_blend"].tolist()
        x = np.arange(len(labels))
        plt.bar(x, blend_summary["mean_signed_net_bpp_per_rgb_pixel"])
        plt.xticks(x, labels)
        plt.axhline(0, linewidth=0.8)
        plt.ylabel("Mean signed net capacity (bits per RGB pixel)")
        plt.xlabel("Cross-channel blend weight")
        plt.title("CC-EDR2-RGB capacity by cross-channel blend ablation")
        plt.tight_layout()
        plt.savefig(output / "fig_rgb_01_capacity_by_blend.png", dpi=220)
        plt.close()

    if len(mae_summary):
        pivot = mae_summary.pivot(index="cross_blend", columns="predictor", values="mean_mae")
        plt.figure(figsize=(9, 5))
        for predictor_name in ("spatial_mae", "cross_channel_mae", "fused_mae"):
            if predictor_name in pivot:
                plt.plot(pivot.index, pivot[predictor_name], marker="o", label=predictor_name)
        plt.ylabel("Mean prediction MAE")
        plt.xlabel("Cross-channel blend weight")
        plt.title("Per-channel predictor error by blend setting")
        plt.legend()
        plt.tight_layout()
        plt.savefig(output / "fig_rgb_02_prediction_mae.png", dpi=220)
        plt.close()

    if len(capacity) and "adaptive_assignment_gain_bits" in capacity:
        gains = pd.to_numeric(capacity["adaptive_assignment_gain_bits"], errors="coerce").dropna()
        plt.figure(figsize=(8, 5))
        plt.hist(gains, bins=24)
        plt.axvline(0, linewidth=0.8)
        plt.xlabel("Adaptive 24-assignment gain over fixed (0,1,2) (bits)")
        plt.ylabel("Image count")
        plt.title("RGB phase-permutation selection gain")
        plt.tight_layout()
        plt.savefig(output / "fig_rgb_03_phase_selection_gain.png", dpi=220)
        plt.close()

    report = [
        "# CC-EDR2-RGB corpus evaluation report",
        "",
        "## Provenance",
        f"- Protocol: {run.get('protocol')}",
        f"- Distinct native RGB images: {run.get('distinct_native_rgb_inputs')}",
        f"- Skipped inputs: {run.get('skipped_files')}",
        f"- Frozen checkpoint SHA-256: {run.get('checkpoint_sha256')}",
        f"- Model retraining: {run.get('training_performed')}",
        f"- Benchmark seed: {run.get('seed')}",
        "",
        "## Blend ablation",
        "",
        blend_summary.to_markdown(index=False) if len(blend_summary) else "_No blend rows._",
        "",
        "## Prediction error",
        "",
        mae_summary.to_markdown(index=False) if len(mae_summary) else "_No prediction rows._",
        "",
        "## Exact-recovery tests",
        "",
        rt_summary.to_markdown(index=False) if len(rt_summary) else "_No round-trip rows._",
        "",
        f"- Total tested payload cases: {len(roundtrip)}",
        f"- Exact image/payload round trips passed: {int(roundtrip['passed_bool'].sum())}",
        f"- Round-trip failures: {int((~roundtrip['passed_bool']).sum())}",
        "",
        "## Method and interpretation",
        "",
        "The four lattice phases are assigned to R/G/B in all 24 ordered permutations; the remaining phase is an untouched common calibration lattice. The fixed assignment (0,1,2) is compared with adaptive selection. The frozen grayscale 3×3 CNN checkpoint is reused independently in each channel; no RGB retraining is performed.",
        "",
        "The 0/4 blend is the independent spatial-CNN baseline. The 1/4, 2/4 and 3/4 blends test deterministic cross-channel regression fusion. Report both per-channel MAE and aggregate signed net capacity. A lower MAE alone is not proof of higher net capacity.",
        "",
        "Only images with positive signed net capacity can carry payload. Rejections remain in the denominator. Net bpp is measured per RGB pixel, not per channel sample.",
        "",
        "RGB support, cross-channel correlation, prediction fusion and adaptive channel allocation are not claimed as novel in isolation. The candidate distinction is the three disjoint channel lattices, the common untouched calibration lattice, deterministic regression reconstruction without coefficient side information, and authenticated joint phase discovery. Prior-art comparison and independent security review remain required.",
        "",
        "USC-SIPI advises that it does not own the copyright of most database images and that copyright status may be unknown. Check its rights information before reproducing any source image in a publication.",
        "",
    ]
    (output / "CC_EDR2_RGB_FINAL_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    (output / "analysis_provenance.json").write_text(json.dumps({
        "source_run_summary": run,
        "source_manifest_sha256": hashlib.sha256(
            (evidence / "rgb_input_manifest.json").read_bytes()
        ).hexdigest(),
        "source_manifest_images": len(manifest.get("images", [])),
        "analysis_script": Path(__file__).name,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "output_dir": str(output),
        "blend_rows": len(blend_summary),
        "per_channel_mae_rows": len(mae_summary),
        "assignment_rows": len(assignment_details),
        "roundtrip_cases": len(roundtrip),
        "figures": [p.name for p in sorted(output.glob("fig_rgb_*.png"))],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
