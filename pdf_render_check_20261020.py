#!/usr/bin/env python3
"""pdf_render_check_20261020.py — rendered-PDF consistency check.

Extracts text from the rendered PDF and verifies that the manuscript's key
quantities, table captions, figure captions, section structure, limitations
and the corrected 4.2.06 red-channel value survived rendering — and that the
superseded 4.5647 truncation does NOT appear anywhere.

Usage: python3 pdf_render_check_20261020.py <manuscript.pdf>
Exit 0 iff every required string is present and no forbidden string appears.
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

REQUIRED = [
    # document identity / status
    ("title", "Final Project Report"),
    ("status", "READY WITH DISCLOSED LIMITATIONS"),
    ("scope", "Bit-Plane Replacement"),
    # sections
    ("section", "Abstract"), ("section", "Introduction"),
    ("section", "Literature review"), ("section", "System architecture"),
    ("section", "Methodology"), ("section", "Experimental setup"),
    ("section", "Results and tables"), ("section", "Discussion"),
    ("section", "Security and implementation limitations"),
    ("section", "Conclusion and future work"), ("section", "References"),
    ("section", "Reproducibility appendix"),
    # corrected disputed value (rounded, not truncated)
    ("T5 value", "4.5648"),
    # ablation / benchmark means
    ("T1 mean", "5.1897"), ("T2 mean", "4.4615"),
    ("T3 mean", "4.8838"), ("T4 mean", "6.5558"),
    ("abstract gray", "5.190 bpp"), ("abstract rgb", "4.884 bpp"),
    # parameter counts + complexity (Table 11 / regenerated Table 3)
    ("params", "46,881"), ("params", "112,417"), ("params", "112,353"),
    ("params", "210,721"), ("T11 MACs", "122,816"), ("T11 MACs", "668,096"),
    ("T11 flops", "245,632"), ("T11 flops", "1,336,192"), ("T11 flops", "680,256"),
    ("T11 caption", "Table 11."),
    # runtime: predictor-only fresh + artifact + e2e (kept separate)
    ("T9 fresh", "1,707.3"), ("T9 artifact", "1,763.4"),
    ("T10 e2e", "5,063.1"), ("T10 e2e", "16,252.6"),
    ("T10 label", "End-to-end pipeline runtime"),
    ("T9 label", "Predictor-only runtime"),
    # table captions 1..10 (this manuscript numbers tables in its §8.x headings)
    *[(f"table marker {i}", f"(Table {i})") for i in range(1, 11)],
    # figure captions 1..9
    *[(f"figure caption {i}", f"Figure {i}:") for i in range(1, 10)],
    # limitations that must remain explicit
    ("limitation", "training provenance"), ("limitation", "dataset provenance"),
    ("limitation", "superseded"), ("limitation", "untraceable"),
    ("limitation", "bibliography"),
    ("limitation", "No verified bibliography exists"),
    # scope qualifications
    ("qualification", "mean"), ("qualification", "not universal"),
    ("qualification", "not a speed improvement"),
]

FORBIDDEN = [
    ("superseded truncation value", "4.5647"),
    ("missing-glyph marker", "\ufffd"),
]


def main(pdf_path):
    reader = PdfReader(pdf_path)
    raw = "\n".join((page.extract_text() or "") for page in reader.pages)
    text = re.sub(r"\s+", " ", raw)
    fails = warns = 0
    print(f"Rendered-PDF check: {pdf_path}")
    print(f"  pages={len(reader.pages)}  extracted_chars={len(text)}")
    print("=" * 100)
    for kind, needle in REQUIRED:
        if needle in text:
            print(f"PASS | {kind:<24} | found: {needle!r}")
        else:
            print(f"FAIL | {kind:<24} | MISSING: {needle!r}")
            fails += 1
    for kind, needle in FORBIDDEN:
        if needle in text:
            print(f"FAIL | {kind:<24} | PRESENT: {needle!r}")
            fails += 1
        else:
            print(f"PASS | {kind:<24} | absent as required: {needle!r}")
    # soft check: every 'Table N' reference in body has a caption
    for i in range(12, 13):
        if f"Table {i}." in text:
            warns += 1
            print(f"WARN | numbering            | unexpected Table {i} caption")
    print("=" * 100)
    print(f"TOTAL: {fails} FAIL / {warns} WARN over {len(REQUIRED) + len(FORBIDDEN)} checks")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
