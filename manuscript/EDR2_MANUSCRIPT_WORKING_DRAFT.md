# EDR2 manuscript working status — 23 November 2026

## Current paper

**Title:** Context-Invariant Prediction and Overhead-Aware Phase Selection for Reversible Data Hiding in Encrypted Images

**Main file:** `manuscript/EDR2_FULL_PAPER_DRAFT.md`

**Bibliography:** `manuscript/EDR2_REFERENCES.bib`

This is a full academic working draft, not yet a submission-ready paper. It contains the abstract, Introduction, Related Work, formal geometry and recovery statements, EDR2 protocol, experimental method, capacity and baseline results, runtime, security, limitations, conclusion and references.

## What the paper argues

The defensible technical centre is the radius-one input non-interference condition: when a 3×3 predictor masks its candidate centre and candidate centres on a step-2 phase are separated by at least two in Chebyshev distance, changing carrier-centre values cannot change any candidate's masked predictor input. The paper does not claim novelty for CNN prediction, masked prediction, checkerboard sampling, MSB replacement, compressed directories, authentication, in-band metadata or net-capacity accounting individually.

## Fixed results currently used

- 243 source- and pixel-hash-pinned native 8-bit grayscale images.
- Canonical curation classes: 232 natural-labelled + 11 constructed texture mosaics.
- Positive net capacity: 163/243; six exact-recovery payload trials per positive image; 978/978 exact image and payload trials.
- Mean signed net rate: 0.110540 bpp; pooled signed rate: 0.059821 bpp.
- Mean usable net rate: 0.143220 bpp; pooled usable rate: 0.095496 bpp.
- Corrected same-corpus native-protocol comparisons: Multi-MSB+Huffman 2.088477 mean usable bpp; corrected PPMR 2.228173. The paper explicitly warns that the methods do not share an identical packet-cost/security model.
- Separate matched-grid predictor study: 3×3 MAE 4.8130/133 positive; 5×5 no-weighted-loss MAE 4.6233/140 positive.
- Optimized 512×512 CPU E2E Run #118: 1.114019 s mean, 10/10 exact; 39,655 payload bits per run; sampled RSS delta 10.87 MiB.

## Literature positioning

The related-work section includes classic RDH/RDHEI and prediction papers plus recent 2025–2026 methods in CNN/masked prediction, adaptive bit-plane coding, dynamic block partition, D4-symmetry recovery, pixel shifting, authentication, and recovery authorisation. The literature review narrows the EDR2 claim to the concrete non-interference proposition and the implemented protocol composition.

## Remaining work

The only research-provenance blocker visible in the current artifacts is the full training manifest for the frozen checkpoint. Final source references should also be independently validated before submission. Figure rights, author/funding details, journal choice, formatting and supervisor review remain author tasks.

No further experiments or retraining are planned. Focus on provenance completion, final citation audit, figures, journal fit and submission preparation.
