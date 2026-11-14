from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDR2_DIR = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2_DIR))

import analyze_edr2_evidence as analysis


def _frame():
    return pd.DataFrame([
        {
            "correlation_cluster": "sequence_6.2",
            "corpus_group": "sequence_6_2_true_motion_frames_01_16",
            "adaptive_net_bpp": 0.20,
            "phase0_net_bpp": 0.10,
            "adaptive_gain_vs_phase0_bpp": 0.10,
            "adaptive_net_bits": 100,
            "phase0_net_bits": 50,
            **{f"phase{i}_net_bpp": 0.1 + i * 0.01 for i in range(4)},
        },
        {
            "correlation_cluster": "sequence_6.2",
            "corpus_group": "sequence_6_2_undirected_frames_17_32",
            "adaptive_net_bpp": -0.10,
            "phase0_net_bpp": -0.15,
            "adaptive_gain_vs_phase0_bpp": 0.05,
            "adaptive_net_bits": -100,
            "phase0_net_bits": -150,
            **{f"phase{i}_net_bpp": -0.15 + i * 0.01 for i in range(4)},
        },
        {
            "correlation_cluster": "texture_series_1.1",
            "corpus_group": "texture_scans",
            "adaptive_net_bpp": 0.30,
            "phase0_net_bpp": 0.20,
            "adaptive_gain_vs_phase0_bpp": 0.10,
            "adaptive_net_bits": 300,
            "phase0_net_bits": 200,
            **{f"phase{i}_net_bpp": 0.20 + i * 0.01 for i in range(4)},
        },
    ])


def test_sequence_62_is_one_overall_correlation_cluster_across_two_subgroups():
    frame = _frame()
    overall = analysis.summarize_clusters(frame, group_col=False)
    by_group = analysis.summarize_clusters(frame, group_col=True)

    assert overall["correlation_cluster"].nunique() == 2
    sequence = overall.loc[overall["correlation_cluster"] == "sequence_6.2"].iloc[0]
    assert sequence["images_in_cluster"] == 2
    assert sequence["source_groups"] == (
        "sequence_6_2_true_motion_frames_01_16|sequence_6_2_undirected_frames_17_32"
    )
    assert len(by_group.loc[by_group["correlation_cluster"] == "sequence_6.2"]) == 2


def test_cluster_bootstrap_is_deterministic_and_reports_cluster_unit():
    first = analysis.bootstrap_mean_ci(np.asarray([0.1, 0.05, -0.02]), seed=42, reps=500)
    second = analysis.bootstrap_mean_ci(np.asarray([0.1, 0.05, -0.02]), seed=42, reps=500)

    assert first == second
    assert first["clusters"] == 3
    assert first["ci95_low"] <= first["mean"] <= first["ci95_high"]
