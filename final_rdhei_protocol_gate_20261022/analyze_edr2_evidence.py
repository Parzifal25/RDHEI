#!/usr/bin/env python3
"""Combine EDR2 adaptive and fixed-phase evidence into publication tables and figures.

The script refuses to combine different source-image hashes or incomplete phase
runs. It reports image-level capacity and a correlation-cluster-balanced
summary, with a deterministic cluster bootstrap for phase-0 comparisons.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def load_run(path: Path, label: str) -> pd.DataFrame:
    csv_path = path / "capacity_summary.csv"
    require_file(csv_path)
    frame = pd.read_csv(csv_path)
    needed = {
        "image", "source_sha256", "pixels_sha256", "pixels", "net_capacity_bits",
        "accepted", "corpus_group", "classification", "correlation_cluster",
    }
    missing = sorted(needed - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: capacity_summary.csv is missing columns: {missing}")
    if frame["image"].duplicated().any():
        raise ValueError(f"{label}: duplicate image keys in capacity_summary.csv")
    frame["net_capacity_bits"] = pd.to_numeric(frame["net_capacity_bits"], errors="raise").astype("int64")
    frame["pixels"] = pd.to_numeric(frame["pixels"], errors="raise").astype("int64")
    frame["net_bpp"] = frame["net_capacity_bits"] / frame["pixels"]
    return frame


def bootstrap_mean_ci(values: np.ndarray, seed: int, reps: int = 5000):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return {"clusters": 0, "mean": math.nan, "ci95_low": math.nan, "ci95_high": math.nan}
    if n == 1:
        return {"clusters": 1, "mean": float(values[0]), "ci95_low": math.nan, "ci95_high": math.nan}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n, size=(reps, n))
    means = values[draws].mean(axis=1)
    return {
        "clusters": n,
        "mean": float(values.mean()),
        "ci95_low": float(np.quantile(means, 0.025)),
        "ci95_high": float(np.quantile(means, 0.975)),
    }


def summarise(frame: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    rows = []
    if key_cols:
        grouped = frame.groupby(key_cols, dropna=False, sort=True)
    else:
        grouped = [(("ALL",), frame)]
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: val for col, val in zip(key_cols, key)}
        row.update({
            "images": int(len(group)),
            "accepted_adaptive": int((group["adaptive_net_bits"] > 0).sum()),
            "rejected_adaptive": int((group["adaptive_net_bits"] <= 0).sum()),
            "adaptive_acceptance_rate": float((group["adaptive_net_bits"] > 0).mean()),
            "adaptive_mean_net_bits_per_image": float(group["adaptive_net_bits"].mean()),
            "adaptive_median_net_bits_per_image": float(group["adaptive_net_bits"].median()),
            "adaptive_mean_signed_net_bpp": float(group["adaptive_net_bpp"].mean()),
            "adaptive_median_signed_net_bpp": float(group["adaptive_net_bpp"].median()),
            "mean_phase_selection_gain_bits": float(group["gain_vs_phase0_bits"].mean()),
            "median_phase_selection_gain_bits": float(group["gain_vs_phase0_bits"].median()),
            "images_improved_vs_phase0": int((group["gain_vs_phase0_bits"] > 0).sum()),
            "images_tied_vs_phase0": int((group["gain_vs_phase0_bits"] == 0).sum()),
        })
        for phase in range(4):
            row[f"phase{phase}_mean_net_bits"] = float(group[f"phase{phase}_net_bits"].mean())
            row[f"phase{phase}_median_net_bits"] = float(group[f"phase{phase}_net_bits"].median())
            row[f"phase{phase}_positive_images"] = int((group[f"phase{phase}_net_bits"] > 0).sum())
            row[f"phase{phase}_mean_net_bpp"] = float(group[f"phase{phase}_net_bpp"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def make_plots(frame: pd.DataFrame, group_summary: pd.DataFrame, cluster_ci: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5))
    data = [frame[f"phase{p}_net_bpp"].dropna().to_numpy() for p in range(4)]
    data.append(frame["adaptive_net_bpp"].dropna().to_numpy())
    plt.boxplot(data, labels=["Fixed 0", "Fixed 1", "Fixed 2", "Fixed 3", "Adaptive"])
    plt.axhline(0, linewidth=0.8)
    plt.ylabel("Signed net payload (bpp)")
    plt.title("EDR2 signed net payload by fixed phase and adaptive selection")
    plt.tight_layout()
    plt.savefig(out / "fig01_phase_capacity_boxplot.png", dpi=220)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.hist(frame["gain_vs_phase0_bits"], bins=30)
    plt.axvline(0, linewidth=1)
    plt.xlabel("Adaptive gain over fixed phase 0 (bits/image)")
    plt.ylabel("Number of images")
    plt.title("Per-image adaptive phase-selection gain")
    plt.tight_layout()
    plt.savefig(out / "fig02_phase_selection_gain_histogram.png", dpi=220)
    plt.close()

    plot = group_summary.sort_values("images", ascending=True)
    plt.figure(figsize=(10, 6))
    y = np.arange(len(plot))
    plt.barh(y - 0.18, plot["images"], height=0.35, label="Images")
    plt.barh(y + 0.18, plot["accepted_adaptive"], height=0.35, label="Positive net capacity")
    plt.yticks(y, plot["corpus_group"])
    plt.xlabel("Image count")
    plt.title("EDR2 inputs and accepted samples by curated stratum")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "fig03_group_acceptance_counts.png", dpi=220)
    plt.close()

    plt.figure(figsize=(8, 6))
    x = frame["phase0_net_bpp"]
    y = frame["adaptive_net_bpp"]
    plt.scatter(x, y, alpha=0.65)
    low = float(min(x.min(), y.min()))
    high = float(max(x.max(), y.max()))
    plt.plot([low, high], [low, high], linestyle="--", linewidth=1)
    plt.xlabel("Fixed phase 0 signed net payload (bpp)")
    plt.ylabel("Adaptive selected-phase signed net payload (bpp)")
    plt.title("Paired per-image comparison: adaptive versus fixed phase 0")
    plt.tight_layout()
    plt.savefig(out / "fig04_adaptive_vs_phase0_scatter.png", dpi=220)
    plt.close()

    valid = cluster_ci[
        cluster_ci["metric"].eq("adaptive_gain_vs_phase0_bpp")
        & cluster_ci["ci95_low"].notna()
    ].sort_values("mean")
    if len(valid):
        plt.figure(figsize=(10, max(4, 0.42 * len(valid))))
        y = np.arange(len(valid))
        err_low = valid["mean"].to_numpy() - valid["ci95_low"].to_numpy()
        err_high = valid["ci95_high"].to_numpy() - valid["mean"].to_numpy()
        plt.errorbar(valid["mean"], y, xerr=[err_low, err_high], fmt="o", capsize=3)
        plt.axvline(0, linewidth=0.8)
        plt.yticks(y, valid["corpus_group"].fillna("ALL"))
        plt.xlabel("Cluster-balanced mean gain (bpp), 95% cluster-bootstrap CI")
        plt.title("Adaptive phase gain with correlated-image clustering")
        plt.tight_layout()
        plt.savefig(out / "fig05_cluster_balanced_gain_ci.png", dpi=220)
        plt.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adaptive-dir", required=True)
    ap.add_argument("--fixed-phase-root", required=True, help="Parent containing edr2-fixed-phase-0 ... -3")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--bootstrap-reps", type=int, default=5000)
    args = ap.parse_args()

    adaptive = load_run(Path(args.adaptive_dir), "adaptive")
    fixed_root = Path(args.fixed_phase_root)
    fixed = [load_run(fixed_root / f"edr2-fixed-phase-{p}", f"fixed phase {p}") for p in range(4)]

    base = adaptive[[
        "image", "source_sha256", "pixels_sha256", "pixels", "classification",
        "corpus_group", "correlation_cluster", "net_capacity_bits",
        "selected_lattice_phase", "phase_selection_gain_bits",
    ]].copy().rename(columns={
        "net_capacity_bits": "adaptive_net_bits",
        "selected_lattice_phase": "adaptive_selected_phase",
        "phase_selection_gain_bits": "gain_vs_phase0_bits",
    })
    base["adaptive_net_bpp"] = base["adaptive_net_bits"] / base["pixels"]
    for phase, frame in enumerate(fixed):
        cols = frame[["image", "source_sha256", "pixels_sha256", "pixels", "net_capacity_bits"]].copy()
        cols = cols.rename(columns={"net_capacity_bits": f"phase{phase}_net_bits"})
        base = base.merge(cols, on="image", how="outer", validate="one_to_one", suffixes=("", f"_phase{phase}"))
        for col in (f"source_sha256_phase{phase}", f"pixels_sha256_phase{phase}", f"pixels_phase{phase}"):
            if col in base:
                if col == f"source_sha256_phase{phase}":
                    mismatch = base[col].ne(base["source_sha256"])
                elif col == f"pixels_sha256_phase{phase}":
                    mismatch = base[col].ne(base["pixels_sha256"])
                else:
                    mismatch = base[col].ne(base["pixels"])
                if mismatch.any():
                    examples = base.loc[mismatch, "image"].head(5).tolist()
                    raise ValueError(f"fixed phase {phase} input mismatch for {examples}")
                base.drop(columns=[col], inplace=True)

        expected_col = f"phase{phase}_net_capacity_bits"
        expected = adaptive.set_index("image")[expected_col]
        actual = base.set_index("image")[f"phase{phase}_net_bits"]
        compare = pd.concat([expected.rename("expected"), actual.rename("actual")], axis=1)
        mismatch = compare["expected"].notna() & (compare["expected"].astype("int64") != compare["actual"].astype("int64"))
        if mismatch.any():
            examples = mismatch[mismatch].index.tolist()[:10]
            raise ValueError(f"fixed phase {phase} capacity differs from adaptive per-phase score: {examples}")

    for phase in range(4):
        base[f"phase{phase}_net_bpp"] = base[f"phase{phase}_net_bits"] / base["pixels"]
    base["adaptive_gain_vs_phase0_bits"] = base["adaptive_net_bits"] - base["phase0_net_bits"]
    base["adaptive_gain_vs_phase0_bpp"] = base["adaptive_gain_vs_phase0_bits"] / base["pixels"]
    base["phase0_improves"] = base["adaptive_gain_vs_phase0_bits"] > 0
    base["phase_tie_vs0"] = base["adaptive_gain_vs_phase0_bits"] == 0

    max_phase = base[[f"phase{p}_net_bits" for p in range(4)]].to_numpy().argmax(axis=1)
    if not np.array_equal(max_phase, base["adaptive_selected_phase"].astype(int).to_numpy()):
        raise ValueError("adaptive selected phases do not match argmax across four fixed phases")
    best = base[[f"phase{p}_net_bits" for p in range(4)]].max(axis=1)
    if not np.array_equal(best.to_numpy(dtype="int64"), base["adaptive_net_bits"].to_numpy(dtype="int64")):
        raise ValueError("adaptive net capacities do not equal the maximum fixed-phase capacities")

    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    base.to_csv(out / "phase_ablation_per_image.csv", index=False)

    phase_rows = []
    for subset_name, subset in [
        ("all_inputs", base),
        ("natural_classified", base[base["classification"] == "natural"]),
        ("constructed_mosaics", base[base["classification"] == "constructed"]),
    ]:
        for phase in range(4):
            v = subset[f"phase{phase}_net_bits"]
            bpp = subset[f"phase{phase}_net_bpp"]
            phase_rows.append({
                "subset": subset_name, "phase": phase, "images": len(subset),
                "positive_net_images": int((v > 0).sum()),
                "rejected_nonpositive_net_images": int((v <= 0).sum()),
                "mean_net_bits_per_image": float(v.mean()),
                "median_net_bits_per_image": float(v.median()),
                "mean_signed_net_bpp_per_image": float(bpp.mean()),
                "median_signed_net_bpp_per_image": float(bpp.median()),
            })
    phase_summary = pd.DataFrame(phase_rows)
    phase_summary.to_csv(out / "phase_ablation_summary.csv", index=False)

    group_summary = summarise(base, ["corpus_group"])
    group_summary.to_csv(out / "group_phase_summary.csv", index=False)
    classification_summary = summarise(base, ["classification"])
    classification_summary.to_csv(out / "classification_phase_summary.csv", index=False)

    def summarize_clusters(data: pd.DataFrame, group_col: bool) -> pd.DataFrame:
        rows = []
        groupby_cols = ["correlation_cluster", "corpus_group"] if group_col else ["correlation_cluster"]
        for key, frame in data.groupby(groupby_cols, dropna=False, sort=True):
            if not isinstance(key, tuple):
                key = (key,)
            if group_col:
                cluster, group = key
            else:
                cluster, group = key[0], "ALL_CLUSTERS"
            row = {
                "corpus_group": group,
                "correlation_cluster": cluster,
                "images_in_cluster": int(len(frame)),
                "source_groups": "|".join(sorted(frame["corpus_group"].dropna().astype(str).unique())),
                "adaptive_mean_net_bpp": float(frame["adaptive_net_bpp"].mean()),
                "phase0_mean_net_bpp": float(frame["phase0_net_bpp"].mean()),
                "adaptive_gain_vs_phase0_bpp": float(frame["adaptive_gain_vs_phase0_bpp"].mean()),
                "adaptive_positive_fraction": float((frame["adaptive_net_bits"] > 0).mean()),
            }
            for phase in range(4):
                row[f"phase{phase}_mean_net_bpp"] = float(frame[f"phase{phase}_net_bpp"].mean())
            rows.append(row)
        return pd.DataFrame(rows)

    # Overall dependence analysis clusters sequence 6.2 frames 1-16 and 17-32
    # together under the same source-sequence identifier. Group-specific tables
    # remain split for descriptive reporting but are not double-counted overall.
    cluster_summary = summarize_clusters(base, group_col=False)
    group_cluster_summary = summarize_clusters(base, group_col=True)
    cluster_summary.to_csv(out / "correlation_cluster_summary.csv", index=False)
    group_cluster_summary.to_csv(out / "correlation_cluster_by_group_summary.csv", index=False)

    ci_rows = []
    overall_values = cluster_summary
    for metric in ["adaptive_gain_vs_phase0_bpp", "adaptive_mean_net_bpp", "phase0_mean_net_bpp"]:
        stats = bootstrap_mean_ci(
            overall_values[metric].to_numpy(), 20261114 + len(ci_rows), args.bootstrap_reps
        )
        ci_rows.append({
            "corpus_group": "ALL_CLUSTERS",
            "metric": metric,
            **stats,
            "bootstrap_reps": args.bootstrap_reps,
            "resampling_unit": "unique_correlation_cluster",
        })
    for group_name in sorted(base["corpus_group"].astype(str).unique()):
        subset = group_cluster_summary[group_cluster_summary["corpus_group"] == group_name]
        for metric in ["adaptive_gain_vs_phase0_bpp", "adaptive_mean_net_bpp", "phase0_mean_net_bpp"]:
            stats = bootstrap_mean_ci(
                subset[metric].to_numpy(), 20261114 + len(ci_rows), args.bootstrap_reps
            )
            ci_rows.append({
                "corpus_group": group_name,
                "metric": metric,
                **stats,
                "bootstrap_reps": args.bootstrap_reps,
                "resampling_unit": "correlation_cluster_within_stratum",
            })
    cluster_ci = pd.DataFrame(ci_rows)
    cluster_ci.to_csv(out / "cluster_bootstrap_summary.csv", index=False)

    make_plots(base, group_summary, cluster_ci, out)

    validation = {
        "adaptive_rows": int(len(adaptive)),
        "fixed_phase_rows": [int(len(x)) for x in fixed],
        "all_phase_inputs_and_hashes_match": True,
        "fixed_phase_capacity_matches_adaptive_phase_score": True,
        "adaptive_selected_phase_is_lowest_index_argmax": True,
        "adaptive_net_capacity_equals_max_fixed_phase_capacity": True,
        "adaptive_input_count": int(len(base)),
        "correlation_clusters": int(cluster_summary["correlation_cluster"].nunique()),
        "phase_selection_improved_over_phase0": int((base["adaptive_gain_vs_phase0_bits"] > 0).sum()),
        "phase_selection_tied_with_phase0": int((base["adaptive_gain_vs_phase0_bits"] == 0).sum()),
        "phase_selection_never_worse_than_phase0": bool((base["adaptive_gain_vs_phase0_bits"] >= 0).all()),
    }
    (out / "analysis_validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = """# EDR2 fixed-phase and correlation-aware analysis

phase_ablation_per_image.csv contains four independently executed fixed-phase net capacities, adaptive-selected capacity, source-image SHA-256 values, group and correlation-cluster identifiers.

phase_ablation_summary.csv reports fixed-phase capacity distributions. group_phase_summary.csv reports the same by curated stratum. correlation_cluster_summary.csv first averages correlated images within their source family. cluster_bootstrap_summary.csv resamples those families, not individual frames or rotations.

The analysis fails closed unless every fixed run uses the same image paths, file hashes, decoded-pixel hashes and dimensions as the adaptive run; all per-phase fixed capacities must equal the per-image phase score produced during adaptive selection; and adaptive capacity must equal the maximum of the four phases with lowest-index tie-breaking.

Net capacity is signed and includes metadata-carrier opportunity cost and bootstrap backup bits. Non-positive budgets remain negative and count as rejected, not zero-capacity successes. BPP is net bits divided by image pixels.

The fixed-phase experiments are matched by source image and checkpoint. They are not a comparison against independent published algorithms. Correlation-cluster bootstrap intervals are descriptive and should be interpreted cautiously when there are few source families.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
