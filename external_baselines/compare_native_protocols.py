#!/usr/bin/env python3
"""Create a matched per-image comparison of native EDR2, Multi-MSB/Huffman and PPMR."""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def truth(value):
    return str(value).strip().lower() in {"1", "true", "yes"}

def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def cluster_bootstrap(rows, value_key, positive_key=None, reps=10000, seed=20261119):
    clusters = defaultdict(list)
    for row in rows:
        clusters[row["correlation_cluster"]].append(row)
    keys = sorted(clusters)
    rng = np.random.default_rng(seed)
    means = []
    coverage = []
    for _ in range(reps):
        chosen = rng.integers(0, len(keys), size=len(keys))
        sample = [row for idx in chosen for row in clusters[keys[int(idx)]]]
        means.append(float(np.mean([row[value_key] for row in sample])))
        if positive_key:
            coverage.append(float(np.mean([bool(row[positive_key]) for row in sample])))
    def ci(values):
        return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]
    return {
        "cluster_count": len(keys),
        "replicates": reps,
        "seed": seed,
        "mean_95ci": ci(means),
        "positive_coverage_95ci": ci(coverage) if positive_key else None,
        "resampling_unit": "29 provenance/correlation clusters; images travel together within each sampled cluster"
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", required=True)
    ap.add_argument("--edr2-capacities", required=True)
    ap.add_argument("--multi", required=True)
    ap.add_argument("--ppmr", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    canonical = json.loads(Path(a.canonical).read_text(encoding="utf-8"))
    edr2_rows = json.loads(Path(a.edr2_capacities).read_text(encoding="utf-8"))
    multi_rows = read_csv(a.multi)
    ppmr_rows = read_csv(a.ppmr)
    if len(canonical) != 243 or len(edr2_rows) != 243:
        raise SystemExit("Expected exactly 243 canonical images and 243 EDR2 capacity records")

    by_rel = {row["relative_path"]: row for row in canonical}
    edr2_by = {row["image"]: row for row in edr2_rows}
    multi_by = {row["image_id"]: row for row in multi_rows}
    ppmr_by = {row["image_id"]: row for row in ppmr_rows}
    expected_ids = {rel.replace("/", "__").replace(".tiff", "") for rel in by_rel}
    if len(by_rel) != 243 or set(edr2_by) != set(by_rel):
        raise SystemExit("Canonical and EDR2 source manifests do not match exactly")
    if set(multi_by) != expected_ids or set(ppmr_by) != expected_ids:
        raise SystemExit("External method ledgers do not contain exactly the canonical 243 image IDs")

    joined = []
    for rel, meta in sorted(by_rel.items()):
        image_id = rel.replace("/", "__").replace(".tiff", "")
        er = edr2_by[rel]
        mr = multi_by[image_id]
        pr = ppmr_by[image_id]
        h, w = map(int, meta["shape"])
        pixels = h * w

        # Confirm exact source TIFF and decoded pixel identity across all three systems.
        for label, row in [("EDR2", er), ("Multi-MSB", mr), ("PPMR", pr)]:
            file_hash = row.get("source_sha256", row.get("source_file_sha256"))
            pixel_hash = row.get("pixels_sha256", row.get("decoded_pixel_sha256"))
            if file_hash != meta["source_sha256"] or pixel_hash != meta["pixels_sha256"]:
                raise SystemExit(f"{label} source/pixel hash mismatch for {rel}")

        edr2_signed_bits = int(er["net_capacity_bits"])
        edr2_signed_bpp = edr2_signed_bits / pixels
        edr2_usable_bits = max(0, edr2_signed_bits) if truth(er["accepted"]) else 0
        edr2_usable_bpp = edr2_usable_bits / pixels

        multi_status = mr.get("status", "ERROR")
        multi_payload_exact = truth(mr.get("payload_exact"))
        multi_image_exact = truth(mr.get("image_exact"))
        multi_embedded_bits = int(float(mr.get("embedded_bits") or 0))
        multi_native_bpp = multi_embedded_bits / pixels if multi_status == "PASS" else None
        reported_multi_bpp = number(mr.get("method_native_net_bpp"))
        if multi_status == "PASS" and (reported_multi_bpp is None or abs(multi_native_bpp - reported_multi_bpp) > 1e-8):
            raise SystemExit(f"Multi-MSB native BPP does not reconcile with embedded payload bits for {image_id}")
        multi_usable_bpp = multi_native_bpp if multi_status == "PASS" and multi_payload_exact and multi_image_exact else 0.0
        multi_positive = multi_usable_bpp > 0

        ppmr_status = pr.get("status", "ERROR")
        ppmr_payload_exact = truth(pr.get("payload_exact"))
        ppmr_image_exact = truth(pr.get("image_exact"))
        ppmr_gross = int(float(pr.get("gross_embedded_bits") or 0))
        ppmr_compressed = int(float(pr.get("compress_predict_bits") or 0))
        ppmr_native_bits = None
        ppmr_native_bpp = None
        if ppmr_status in {"PASS", "ROUNDTRIP_FAIL"}:
            ppmr_native_bits = ppmr_gross - ppmr_compressed - 8 - 16*8 - 16*8
            ppmr_native_bpp = ppmr_native_bits / pixels
            reported_ppmr_bpp = number(pr.get("method_native_net_bpp"))
            if reported_ppmr_bpp is None or abs(ppmr_native_bpp - reported_ppmr_bpp) > 1e-8:
                raise SystemExit(f"PPMR native BPP does not reconcile with Main612 formula for {image_id}")
        ppmr_usable_bpp = ppmr_native_bpp if (
            ppmr_status == "PASS" and ppmr_payload_exact and ppmr_image_exact
            and ppmr_native_bpp is not None and ppmr_native_bpp > 0
        ) else 0.0
        ppmr_positive = ppmr_usable_bpp > 0

        row = {
            "image_id": image_id,
            "relative_path": rel,
            "corpus_group": meta.get("corpus_group", "unspecified"),
            "correlation_cluster": meta.get("correlation_cluster") or image_id,
            "classification": meta.get("classification", "unspecified"),
            "height": h, "width": w, "pixels": pixels,
            "source_file_sha256": meta["source_sha256"],
            "decoded_pixel_sha256": meta["pixels_sha256"],
            "edr2_signed_net_bits": edr2_signed_bits,
            "edr2_signed_net_bpp": edr2_signed_bpp,
            "edr2_usable_net_bits": edr2_usable_bits,
            "edr2_usable_net_bpp": edr2_usable_bpp,
            "edr2_positive_capacity": edr2_signed_bits > 0,
            "edr2_accepted": truth(er["accepted"]),
            "multi_status": multi_status,
            "multi_payload_exact": multi_payload_exact,
            "multi_image_exact": multi_image_exact,
            "multi_payload_bits": multi_embedded_bits,
            "multi_native_net_bpp": multi_native_bpp,
            "multi_usable_net_bpp": multi_usable_bpp,
            "multi_positive_capacity": multi_positive,
            "multi_runtime_s": number(mr.get("runtime_s")),
            "ppmr_status": ppmr_status,
            "ppmr_payload_exact": ppmr_payload_exact,
            "ppmr_ub_payload_exact": truth(pr.get("ub_payload_exact")),
            "ppmr_nub_payload_exact": truth(pr.get("nub_payload_exact")),
            "ppmr_image_exact": ppmr_image_exact,
            "ppmr_gross_embedded_bits": ppmr_gross,
            "ppmr_compressed_prediction_map_bits": ppmr_compressed,
            "ppmr_native_net_payload_bits": ppmr_native_bits,
            "ppmr_native_net_bpp": ppmr_native_bpp,
            "ppmr_usable_net_bpp": ppmr_usable_bpp,
            "ppmr_positive_capacity": ppmr_positive,
            "ppmr_active_plane_mask": pr.get("active_plane_mask", ""),
            "ppmr_runtime_s": number(pr.get("runtime_s")),
            "ppmr_error": pr.get("error", "")
        }
        joined.append(row)

    cluster_count = len({row["correlation_cluster"] for row in joined})
    if cluster_count != 29:
        raise SystemExit(f"Expected 29 preserved correlation clusters; found {cluster_count}")

    total_pixels = sum(row["pixels"] for row in joined)
    methods = {
        "EDR2-native-step2": ("edr2_usable_net_bpp", "edr2_positive_capacity"),
        "Multi-MSB+Huffman": ("multi_usable_net_bpp", "multi_positive_capacity"),
        "PPMR-corrected": ("ppmr_usable_net_bpp", "ppmr_positive_capacity")
    }
    summary = {
        "corpus_images": 243,
        "unique_source_file_hashes": len({row["source_file_sha256"] for row in joined}),
        "unique_decoded_pixel_hashes": len({row["decoded_pixel_sha256"] for row in joined}),
        "correlation_clusters": cluster_count,
        "publication_ready": (
            all(row["multi_status"] == "PASS" and row["multi_payload_exact"] and row["multi_image_exact"] for row in joined)
            and all(row["ppmr_status"] == "PASS" and row["ppmr_payload_exact"] and row["ppmr_image_exact"] for row in joined)
        ),
        "common_estimand": (
            "Usable positive native net payload bpp per image, set to zero when an exact payload+host recovery "
            "is not achieved or no positive net capacity is available. EDR2 signed net bpp is also retained "
            "separately, including negative rejected outcomes."
        ),
        "methods": {},
        "paired_vs_edr2": {},
        "interpretation_limits": [
            "All methods are evaluated on the same 243 hash-verified native 8-bit grayscale USC-SIPI images and 29 provenance/correlation clusters.",
            "This is a matched-corpus, native-protocol comparison, not identical carrier geometry or identical packet-cost accounting.",
            "Multi-MSB net payload is the actual secret-bit count returned as embedded by the pinned source, after the method reserves its auxiliary information and reference pixels.",
            "PPMR net payload follows the pinned Main612.m expression: gross UB/NUB secret bits less the compressed prediction map and the stated fixed bit overhead.",
            "EDR2 signed net capacity charges the in-band header, compressed directory, authentication-tag carrier opportunity cost and bootstrap-byte backup opportunity cost. Negative signed rates are retained in the dedicated EDR2 field.",
            "Usable net bpp is zero for non-exact/failed rows. Failed-run rows remain explicitly identified and do not receive invented signed-capacity values.",
            "Runtime is reported descriptively only; MATLAB/Octave code paths and GitHub runner scheduling do not support a fair cross-method speed ranking."
        ]
    }

    for method, (rate_key, positive_key) in methods.items():
        values = np.asarray([float(row[rate_key]) for row in joined], dtype=float)
        positive_values = values[values > 0]
        if method == "EDR2-native-step2":
            usable_bits = sum(int(row["edr2_usable_net_bits"]) for row in joined)
        elif method == "Multi-MSB+Huffman":
            usable_bits = sum(int(row["multi_payload_bits"]) for row in joined if row["multi_usable_net_bpp"] > 0)
        else:
            usable_bits = sum(int(row["ppmr_native_net_payload_bits"]) for row in joined
                              if row["ppmr_usable_net_bpp"] > 0 and row["ppmr_native_net_payload_bits"] is not None)
        s = {
            "images": len(joined),
            "positive_capacity_images": int(sum(bool(row[positive_key]) for row in joined)),
            "positive_capacity_rate": float(np.mean([bool(row[positive_key]) for row in joined])),
            "mean_usable_net_bpp_all_243": float(np.mean(values)),
            "median_usable_net_bpp_all_243": float(np.median(values)),
            "pooled_usable_net_bpp_total_bits_over_total_pixels": usable_bits / total_pixels,
            "mean_usable_net_bpp_positive_images": float(np.mean(positive_values)) if len(positive_values) else None,
            "median_usable_net_bpp_positive_images": float(np.median(positive_values)) if len(positive_values) else None,
            "sample_sd_usable_net_bpp_all_243": float(np.std(values, ddof=1)),
            "cluster_bootstrap": cluster_bootstrap(joined, rate_key, positive_key)
        }
        if method == "EDR2-native-step2":
            signed = np.asarray([row["edr2_signed_net_bpp"] for row in joined])
            s["mean_signed_net_bpp_all_243_including_negative"] = float(np.mean(signed))
            s["median_signed_net_bpp_all_243_including_negative"] = float(np.median(signed))
            s["accepted_images"] = int(sum(row["edr2_accepted"] for row in joined))
            s["exact_receiver_trials_on_accepted_images"] = "978/978"
        elif method == "Multi-MSB+Huffman":
            s["payload_exact_images"] = int(sum(row["multi_payload_exact"] for row in joined))
            s["image_exact_images"] = int(sum(row["multi_image_exact"] for row in joined))
            s["status_counts"] = dict(sorted(Counter(row["multi_status"] for row in joined).items()))
            times = [row["multi_runtime_s"] for row in joined if row["multi_runtime_s"] is not None]
            s["runtime_median_s"] = float(np.median(times)) if times else None
            s["runtime_p95_s"] = float(np.percentile(times, 95)) if times else None
            s["native_rate_definition"] = "embedded secret bits / pixels, from the pinned implementation's returned embedded stream"
        else:
            s["payload_exact_images"] = int(sum(row["ppmr_payload_exact"] for row in joined))
            s["ub_payload_exact_images"] = int(sum(row["ppmr_ub_payload_exact"] for row in joined))
            s["nub_payload_exact_images"] = int(sum(row["ppmr_nub_payload_exact"] for row in joined))
            s["image_exact_images"] = int(sum(row["ppmr_image_exact"] for row in joined))
            s["status_counts"] = dict(sorted(Counter(row["ppmr_status"] for row in joined).items()))
            times = [row["ppmr_runtime_s"] for row in joined if row["ppmr_runtime_s"] is not None]
            s["runtime_median_s"] = float(np.median(times)) if times else None
            s["runtime_p95_s"] = float(np.percentile(times, 95)) if times else None
            s["native_rate_definition"] = "(UB + NUB gross embedded bits - compressed prediction-map bits - 8 - 16*8 - 16*8) / pixels"
            rates = [row["ppmr_native_net_bpp"] for row in joined if row["ppmr_native_net_bpp"] is not None]
            s["native_signed_rate_rows"] = len(rates)
            s["mean_native_net_bpp_when_measured"] = float(np.mean(rates)) if rates else None
        summary["methods"][method] = s

    for method, key in [
        ("Multi-MSB+Huffman", "multi_usable_net_bpp"),
        ("PPMR-corrected", "ppmr_usable_net_bpp")
    ]:
        differences = np.asarray([row[key] - row["edr2_usable_net_bpp"] for row in joined])
        paired = [dict(row, pair_difference=float(row[key] - row["edr2_usable_net_bpp"])) for row in joined]
        cb = cluster_bootstrap(paired, "pair_difference")
        summary["paired_vs_edr2"][method] = {
            "mean_paired_usable_net_bpp_difference": float(np.mean(differences)),
            "median_paired_usable_net_bpp_difference": float(np.median(differences)),
            "baseline_higher_images": int(np.sum(differences > 0)),
            "equal_images": int(np.sum(differences == 0)),
            "baseline_lower_images": int(np.sum(differences < 0)),
            "cluster_bootstrap_mean_difference_95ci": cb["mean_95ci"],
            "paired_unit": "same image IDs; block bootstrap over 29 provenance/correlation clusters"
        }

    per_image = out / "native_protocol_paired_per_image.csv"
    with per_image.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(joined[0]))
        writer.writeheader()
        writer.writerows(joined)

    group_rows = []
    grouped = defaultdict(list)
    for row in joined:
        grouped[row["corpus_group"]].append(row)
    for group, rows in sorted(grouped.items()):
        item = {"corpus_group": group, "images": len(rows)}
        for method, (rate_key, positive_key) in methods.items():
            item[method + "_positive_images"] = int(sum(bool(row[positive_key]) for row in rows))
            item[method + "_positive_rate"] = item[method + "_positive_images"] / len(rows)
            item[method + "_mean_usable_net_bpp"] = float(np.mean([row[rate_key] for row in rows]))
        group_rows.append(item)
    with (out / "native_protocol_group_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(group_rows[0]))
        writer.writeheader()
        writer.writerows(group_rows)

    (out / "native_protocol_comparison.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
