#!/usr/bin/env python3
"""Generate paper-facing CC-EDR2-RGB tables and plots from a corpus run."""
from __future__ import annotations

import argparse
import hashlib
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
    status_counts = capacity["status"].value_counts(dropna=False).to_dict()
    error_records = []
    for blend in BLENDS:
        error_col = f"blend_{blend}_error"
        if error_col not in capacity:
            continue
        for reason, count in capacity.loc[
            capacity[error_col].fillna("").astype(str).str.len() > 0, error_col
        ].value_counts().items():
            error_records.append({
                "cross_blend": f"{blend}/4",
                "error_reason": str(reason),
                "image_count": int(count),
            })
    error_summary = pd.DataFrame(
        error_records, columns=["cross_blend", "error_reason", "image_count"]
    )
    outcome_columns = [
        "image", "status", "signed_net_capacity_bits",
        "signed_net_bpp_per_rgb_pixel", "best_blend_num_by_capacity",
        "selected_rgb_phases", "all_roundtrips_passed",
    ]
    image_outcomes = capacity[[col for col in outcome_columns if col in capacity]].copy()
    for blend in BLENDS:
        for suffix in ("net_capacity_bits", "net_bpp", "directory_fit_assignments", "error"):
            col = f"blend_{blend}_{suffix}"
            if col in capacity:
                image_outcomes[col] = capacity[col]
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
        blend_roundtrips = (
            roundtrip.loc[
                pd.to_numeric(roundtrip.get("blend_num", pd.Series(dtype=float)), errors="coerce") == blend
            ].copy()
            if len(roundtrip) else roundtrip.copy()
        )
        if len(blend_roundtrips):
            blend_roundtrips["passed_bool"] = (
                blend_roundtrips["passed"].astype(str).str.lower().eq("true")
            )
            per_image_rt = blend_roundtrips.groupby("image")["passed_bool"].agg(["count", "all"])
            complete_case_images = int(((per_image_rt["count"] >= 9) & per_image_rt["all"]).sum())
            receiver_processes = int(
                blend_roundtrips.get(
                    "independent_receiver_process", pd.Series([False] * len(blend_roundtrips))
                ).astype(str).str.lower().eq("true").sum()
            )
            source_access_violations = int(
                blend_roundtrips.get(
                    "receiver_source_access", pd.Series([False] * len(blend_roundtrips))
                ).astype(str).str.lower().eq("true").sum()
            ) + int(
                blend_roundtrips.get(
                    "receiver_source_access_violation", pd.Series([False] * len(blend_roundtrips))
                ).astype(str).str.lower().eq("true").sum()
            )
        else:
            complete_case_images = receiver_processes = source_access_violations = 0
        images_tested = int(blend_roundtrips["image"].nunique()) if len(blend_roundtrips) else 0
        rows.append({
            "cross_blend": f"{blend}/4",
            "corpus_images": int(len(capacity)),
            "images_with_capacity": int(usable.notna().sum()),
            "positive_net_images": int((usable > 0).sum()),
            "nonpositive_net_images": int((usable <= 0).sum()),
            "images_without_any_directory_fit": int(
                (pd.to_numeric(capacity.get(f"blend_{blend}_directory_fit_assignments", 0),
                               errors="coerce").fillna(0) == 0).sum()
            ) if f"blend_{blend}_directory_fit_assignments" in capacity
            else int(len(capacity) - usable.notna().sum()),
            "images_with_roundtrip": images_tested,
            "roundtrip_cases": int(len(blend_roundtrips)),
            "roundtrip_passed": int(blend_roundtrips["passed_bool"].sum()) if len(blend_roundtrips) else 0,
            "roundtrip_failed": int((~blend_roundtrips["passed_bool"]).sum()) if len(blend_roundtrips) else 0,
            "complete_9_case_images_all_exact": complete_case_images,
            "receiver_process_attempts": int(len(blend_roundtrips)),
            "independent_receiver_processes": receiver_processes,
            "receiver_source_access_violations": source_access_violations,
            "mean_signed_net_bits": float(usable.mean()) if len(usable) else np.nan,
            "median_signed_net_bits": float(usable.median()) if len(usable) else np.nan,
            "mean_signed_net_bpp_per_rgb_pixel": float(pd.to_numeric(capacity[bpp_col], errors="coerce").mean()),
            "median_signed_net_bpp_per_rgb_pixel": float(pd.to_numeric(capacity[bpp_col], errors="coerce").median()),
            "images_better_than_spatial_only": np.nan if blend == 0 else int(
                (values > pd.to_numeric(capacity["blend_0_net_capacity_bits"], errors="coerce")).sum()
            ),
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
                    "aggregation_scope_counts": json.dumps(
                        capacity.get(
                            f"blend_{blend}_prediction_metric_scope",
                            pd.Series(["unspecified"] * len(capacity), index=capacity.index),
                        ).fillna("unspecified").value_counts().to_dict(),
                        sort_keys=True,
                    ),
                })

        subset = assignments[assignments["blend_num"] == blend]
        if len(subset):
            tuples = subset["selected_phases_rgb"].fillna("").astype(str).replace(
                "", "no_feasible_assignment"
            ).value_counts()
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
                        "directory_fits": bool(score.get("directory_fits", False)),
                        "candidate_count_per_channel": score.get("candidate_count_per_channel"),
                        "bootstrap_candidates": score.get("bootstrap_candidates"),
                        "net_capacity_bits": score.get("net_capacity_bits"),
                        "prediction_metrics_by_channel_json": json.dumps(
                            score.get("prediction_metrics", []), separators=(",", ":")
                        ),
                    })

    blend_summary = pd.DataFrame(rows)
    mae_summary = pd.DataFrame(mae_rows)
    assignment_frequency = pd.DataFrame(assignment_frequency_rows)
    assignment_details = pd.DataFrame(detailed_assignment_rows)

    roundtrip["passed_bool"] = roundtrip["passed"].astype(str).str.lower().eq("true")
    if len(roundtrip):
        group_cols = [col for col in ("blend_num", "case") if col in roundtrip.columns]
        agg = {
            "image": ("image", "count"),
            "passed": ("passed_bool", "sum"),
            "payload_bits_min": ("payload_bits", "min"),
            "payload_bits_max": ("payload_bits", "max"),
            "independent_receiver_processes": ("independent_receiver_process", "sum"),
        }
        rt_summary = roundtrip.groupby(group_cols, sort=False).agg(**agg).reset_index()
        rt_summary = rt_summary.rename(columns={"image": "tests"})
    else:
        rt_summary = pd.DataFrame(columns=[
            "blend_num", "case", "tests", "passed", "payload_bits_min",
            "payload_bits_max", "independent_receiver_processes"
        ])
    rt_summary["failed"] = rt_summary["tests"] - rt_summary["passed"]

    capacity.to_csv(output / "rgb_per_image_capacity_and_prediction.csv", index=False)
    image_outcomes.to_csv(output / "rgb_protocol_image_outcomes.csv", index=False)
    error_summary.to_csv(output / "rgb_protocol_failure_reasons.csv", index=False)
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
        # There are three channel rows (R/G/B) for each blend/predictor.
        # Average those channels for the aggregate figure; retain per-channel
        # results unchanged in rgb_prediction_mae_summary.csv.
        pivot = mae_summary.pivot_table(
            index="cross_blend", columns="predictor", values="mean_mae", aggfunc="mean"
        )
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

    positive_columns = [
        pd.to_numeric(capacity[f"blend_{b}_net_capacity_bits"], errors="coerce") > 0
        for b in BLENDS if f"blend_{b}_net_capacity_bits" in capacity
    ]
    positive_any_blend = int(pd.concat(positive_columns, axis=1).any(axis=1).sum()) if positive_columns else 0

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
        "## Corpus feasibility",
        "",
        f"- Images evaluated: {len(capacity)}",
        f"- Images with positive net capacity under at least one blend: {positive_any_blend}",
        f"- Images rejected before capacity calculation: {int((capacity['status'] == 'error').sum())}",
        f"- Status counts: {json.dumps({str(k): int(v) for k, v in status_counts.items()}, sort_keys=True)}",
        "",
        "### Blend-specific directory failures",
        "",
        error_summary.to_markdown(index=False) if len(error_summary) else "_No blend-specific directory failures._",
        "",
        "Images rejected because the current single-directory bootstrap could not fit are not treated as zero-capacity samples. They are counted as protocol feasibility failures and retained in the corpus denominator.",
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
        f"- Independent receiver process invocations: {run.get('independent_receiver_processes')}",
        f"- Forbidden source-read violations: {run.get('receiver_source_access_violations')}",
        f"- Exact image/payload round trips passed: {int(roundtrip['passed_bool'].sum())}",
        f"- Round-trip failures: {int((~roundtrip['passed_bool']).sum())}",
        f"- Images receiving round-trip tests: {int(roundtrip['image'].nunique()) if len(roundtrip) else 0}",
        "- Every positive-net image/blend combination is attempted with nine payload sizes. Each completed case uses a fresh receiver OS process. The receiver receives only the marked RGB image, master key and nonce. Python builtins.open/io.open are guarded against reads beneath source paths; the parent audits reported paths. This is a guarded file-I/O audit, not an OS-level sandbox.",
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
