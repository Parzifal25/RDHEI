#!/usr/bin/env python3
"""Build per-stratum original/reserved/encrypted/recovered image panels."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


def fit_thumb(image: Image.Image, box=(280, 280)) -> Image.Image:
    return ImageOps.pad(image.convert("L"), box, color=255, centering=(0.5, 0.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample-dir", default="data/usc_sipi_visual_samples")
    ap.add_argument("--evidence-dir", default="/tmp/edr2-visual-sample-evidence")
    ap.add_argument("--output-dir", default="/tmp/edr2-visual-gallery")
    args = ap.parse_args()

    sample_dir = Path(args.sample_dir).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True)
    visual_dir = output_dir / "panels"
    visual_dir.mkdir()
    capacity_path = evidence_dir / "capacity_summary.csv"
    if not capacity_path.is_file():
        raise FileNotFoundError(capacity_path)

    rows = list(csv.DictReader(capacity_path.open(newline="", encoding="utf-8")))
    gallery_items = []
    font = ImageFont.load_default()
    for row in rows:
        name = row["image"]
        source = sample_dir / Path(*Path(name).parts)
        original = Image.open(source).convert("L")
        safe = safe_name(name)
        stem = safe + "_full"
        reserved_path = evidence_dir / (stem + "_reserved.png")
        cipher_path = evidence_dir / (stem + "_cipher.png")
        recovered_path = evidence_dir / (stem + "_recovered.npy")
        accepted = row.get("accepted", "").lower() == "true"

        panels = [
            ("Original cover", original.copy()),
        ]
        if accepted and reserved_path.is_file() and cipher_path.is_file() and recovered_path.is_file():
            panels.extend([
                ("Reserved image", Image.open(reserved_path).convert("L")),
                ("Marked encrypted image", Image.open(cipher_path).convert("L")),
                ("Recovered cover", Image.fromarray(np.load(recovered_path, allow_pickle=False).astype(np.uint8), mode="L")),
            ])
        else:
            placeholder = Image.new("L", (280, 280), 230)
            d = ImageDraw.Draw(placeholder)
            msg = "No positive net capacity\nImage rejected by EDR2"
            d.multiline_text((24, 120), msg, fill=0, font=font, spacing=8, align="center")
            panels.extend([
                ("Reserved image", placeholder.copy()),
                ("Marked encrypted image", placeholder.copy()),
                ("Recovered cover", placeholder.copy()),
            ])

        normalized = []
        for title, image in panels:
            thumb = fit_thumb(image)
            tile = Image.new("RGB", (300, 330), "white")
            tile.paste(thumb.convert("RGB"), (10, 35))
            draw = ImageDraw.Draw(tile)
            draw.text((10, 10), title, fill="black", font=font)
            normalized.append(tile)
        panel = Image.new("RGB", (1200, 330), "white")
        for idx, tile in enumerate(normalized):
            panel.paste(tile, (idx * 300, 0))
        draw = ImageDraw.Draw(panel)
        label = f"{row.get('corpus_group','')} | {name} | net={row.get('net_capacity_bits','')} bits | phase={row.get('selected_lattice_phase','')}"
        draw.rectangle((0, 330, 1200, 360), fill=(238, 242, 247))
        draw.text((10, 338), label[:180], fill="black", font=font)
        dest = visual_dir / (safe + "_full_capacity_panel.png")
        panel.save(dest)
        gallery_items.append({
            "image": name,
            "corpus_group": row.get("corpus_group", ""),
            "classification": row.get("classification", ""),
            "accepted": accepted,
            "net_capacity_bits": row.get("net_capacity_bits", ""),
            "selected_phase": row.get("selected_lattice_phase", ""),
            "panel": str(dest),
            "original_file": str(source),
        })

    height = 360 * len(gallery_items)
    contact = Image.new("RGB", (1200, height), "white")
    for idx, item in enumerate(gallery_items):
        img = Image.open(item["panel"]).convert("RGB")
        contact.paste(img, (0, idx * 360))
    contact_path = output_dir / "full_capacity_gallery.png"
    contact.save(contact_path)
    with (output_dir / "gallery_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(gallery_items[0].keys()))
        writer.writeheader()
        writer.writerows(gallery_items)
    (output_dir / "gallery_manifest.json").write_text(
        json.dumps(gallery_items, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"gallery": str(contact_path), "panels": len(gallery_items)}, indent=2))


if __name__ == "__main__":
    main()
