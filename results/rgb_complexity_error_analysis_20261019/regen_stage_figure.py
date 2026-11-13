#!/usr/bin/env python3
"""Regenerate figures/fig_runtime_stages.png from runtime_summary.csv.

Layout: per scenario (Airplane gray, 4.2.03 RGB), a stage breakdown with the
stage timing boundaries exactly as measured:
  label_map, embed (vectorized-identical variant; original-loop embed times are
  in improvement_experiments.csv), encrypt, decrypt, extract+recover (original
  receiver loop), plus TOTAL(original) and TOTAL(fast-variant) side by side.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "runtime_summary.csv")))
by = {r["method"]: r for r in rows}

stages = ["label_map", "embed", "encrypt", "decrypt", "extract+recover"]
scenarios = [("Airplane.png MED", "Airplane gray 512×512 — MED"),
             ("Airplane.png CNN3x3", "Airplane gray 512×512 — CNN-3×3"),
             ("4.2.03.png MED", "4.2.03 RGB 512×512×3 (3 channels) — MED"),
             ("4.2.03.png CNN3x3", "4.2.03 RGB 512×512×3 (3 channels) — CNN-3×3")]

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
for ax, (scen, title) in zip(axes.flatten(), scenarios):
    xs = np.arange(len(stages) + 2)
    vals = [float(by[f"{s} {scen}"]["mean_ms"]) for s in stages]
    tot_o = float(by[f"TOTAL(original) {scen}"]["mean_ms"])
    tot_f = float(by[f"TOTAL(fast-variant) {scen}"]["mean_ms"])
    bars = vals + [tot_o, tot_f]
    colors = ["#4C72B0"] * len(stages) + ["#C44E52", "#55A868"]
    ax.bar(xs, bars, color=colors)
    for x, v in zip(xs, bars):
        ax.text(x, v * 1.02, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(xs)
    ax.set_xticklabels(stages + ["TOTAL\noriginal", "TOTAL\nfast-variant"], fontsize=8)
    ax.set_ylabel("ms (mean of 3 repeats, full-capacity payload)")
    ax.set_title(title)
    ax.set_ylim(0, max(bars) * 1.15)
    ax.grid(alpha=0.3, axis="y")

fig.suptitle("Stage-wise RDHEI pipeline runtime — disjoint timing boundaries\n"
             "embed stage measured with the bitwise-identical vectorized embedder "
             "(original-loop embed: see improvement_experiments.csv)", fontsize=10)
fig.tight_layout()
fig.savefig(HERE / "figures" / "fig_runtime_stages.png", dpi=140)
print("regenerated figures/fig_runtime_stages.png")
