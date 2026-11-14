from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDR2 = ROOT / "final_rdhei_protocol_gate_20261022"
sys.path.insert(0, str(EDR2))

import build_edr2_paper_report as report


def test_report_generator_marks_six_baselines_missing_and_uses_raw_ledgers(tmp_path):
    adaptive = tmp_path / "adaptive"
    adaptive.mkdir()
    cap = pd.DataFrame([{
        "image": "textures/a.tiff",
        "classification": "natural",
        "corpus_group": "texture_scans",
        "accepted": True,
        "pixels": 100,
        "signed_net_bpp": 0.2,
        "net_capacity_bits": 20,
        "selected_lattice_phase": 2,
        "phase_selection_gain_bits": 5,
        **{f"phase{i}_net_capacity_bits": 15 + i for i in range(4)},
    }])
    cap.to_csv(adaptive / "capacity_summary.csv", index=False)
    pd.DataFrame([{
        "case": "empty", "image_exact": True, "payload_exact": True,
    }]).to_csv(adaptive / "roundtrip_summary.csv", index=False)
    (adaptive / "input_manifest.json").write_text(json.dumps({
        "missing_original_baseline_stems": ["airplane", "baboon"],
        "correlation_cluster_counts": {"texture_series_1.1": 1},
    }), encoding="utf-8")
    (adaptive / "integrity.json").write_text(json.dumps({
        "checkpoint_sha256": "abc123", "model_training_performed": False,
    }), encoding="utf-8")
    (adaptive / "algebra.json").write_text(json.dumps({
        "pairs": 65536, "payload_words": 396032, "failures": 0,
    }), encoding="utf-8")
    (adaptive / "negative_checks_and_rejections.json").write_text("[]", encoding="utf-8")

    out = tmp_path / "report.md"
    report.generate(adaptive, None, out, None)
    text = out.read_text(encoding="utf-8")

    assert "Six-image baseline status" in text
    assert "airplane, baboon" in text
    assert "No matched fixed-phase analysis artifact" in text
    assert "163" not in text  # report uses fixture ledger, not cached historical counts
    assert "abc123" in text
