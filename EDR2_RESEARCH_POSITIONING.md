# EDR2 research positioning and publication gate

**Branch:** `research/edr2-publication-hardening`  
**Status:** implementation hardening and research positioning; **not yet publication-ready**  
**Checkpoint policy:** use the existing `models/v4_patch3.pth` weights unchanged. No retraining is part of this revision.

## 1. What the active system is

EDR2 is a reserve-room-before-encryption (RRBE) reversible data hiding in encrypted images (RDHEI) protocol for native 8-bit grayscale images with even height and width. Odd dimensions are outside the present four-phase maximum-density proof and are rejected by the current implementation.

The per-image semantic inputs at the receiver are:

1. the final marked encrypted image;
2. a 32-byte master key (K); and
3. a 128-bit nonce (V), unique per packet under (K).

The receiver also has the shared protocol software and the fixed CNN-3x3 checkpoint installed. It is not supplied with per-image prediction maps, label maps, error intervals, a sender-side object, a payload-length sidecar, or an original image. The owner supplies a nonce-specific data-hiding capability key to the independent hider; this is cryptographic key material, not an image-dependent sidecar. The protocol does not eliminate the owner's setup/key handoff to the hider.

The active implementation is under `final_rdhei_protocol_gate_20261022/`:

- `predictor.py`: frozen 3x3 inference, candidate geometry, class labels and compressed directory;
- `wire.py`: EDR2 wire format, encrypted header and directory, HMAC, payload ciphering and ciphertext-domain insertion;
- `protocol.py`: owner reservation and receiver-only extraction/reconstruction;
- `PROTOCOL_EDR2.md`: normative packet and protocol specification;
- `run_gate.py`: natural-image capacity ledger and fresh-process end-to-end gate.

The legacy `src/rdhei_core.py` dense pipeline remains a separate historical implementation. Its receiver requires externally supplied maps and payload length; it is not evidence for EDR2's receiver contract. The active EDR2 predictor and evaluation gate must not depend on that legacy receiver.

## 2. The strongest technical contribution candidate

The primary candidate contribution is a **four-phase, content-adaptive selection among maximum-density context-invariant lattices for a fixed non-causal 3x3 CNN, where the selected phase maximizes signed net payload after in-band directory compression and bootstrap restoration costs**. The phase is implicitly identified by the authenticated header's carrier coordinates, so selection adds neither a per-image sidecar nor extra phase bits.

The 3x3 predictor uses a local patch and masks its centre before inference. Only the chosen candidate centres may be modified. Let the candidate centre set be (G), and let (B_1(g)) be the 3x3 Chebyshev-radius-one neighbourhood around (g). Require

[
  |g-g'|_infty geq 2
  quad 	ext{for every distinct }g,g'in G.
]

Then no other mutable centre lies in a candidate's 3x3 input patch. The candidate's own centre is masked. Thus, after arbitrary changes to all candidate-centre bytes, the complete masked input tensor at every candidate remains unchanged. With the checkpoint in evaluation mode (fixed BatchNorm running statistics), fixed preprocessing, rounding and inference settings, the owner and receiver obtain the same candidate predictions. This is the synchronization guarantee; it is not a claim that dense CNN predictions can be recomputed after arbitrary dense embedding.

### Finite-domain density bound

For an (h\times w) image, valid centres lie in the interior rectangle ({1,\ldots,h-2}\times{1,\ldots,w-2}). Partition that rectangle into disjoint 2x2 tiles. At most one candidate centre can be selected from each tile, because any two positions within one tile have Chebyshev distance at most one. Therefore,

[
 |G| \leq
 \left\lceil\frac{h-2}{2}\right\rceil
 \left\lceil\frac{w-2}{2}\right\rceil.
]

The step-2 lattice ((y,x)=(1+2i,1+2j)), restricted to valid 3x3 centres, attains this bound. For a 512x512 image it selects (255\times255=65{,}025) candidate centres, or 24.81% of all image pixels. This is a geometric candidate-density result, **not** an embedding-capacity result. Net capacity must still be measured after label coding, header, authentication and backup overhead.

The four step-2 phases are alternatives, not a union of mutable centres. For phase q in {0,1,2,3}, let the row/column offsets be r_q=1+floor(q/2) and c_q=1+(q mod 2). Every phase independently attains 65,025 centres on a 512x512 image and preserves the same radius-one context invariant.

### Net-capacity phase selection

For each phase q, the owner independently runs the frozen checkpoint and computes the compressed label directory, bootstrap carrier count H_q, ordinary-slot opportunity cost F_q and signed payload budget

\[
N_q = G_{0,q} - F_q - 8H_q.
\]

The selected phase is

\[
q^* = \arg\max_{q\in\{0,1,2,3\}} N_q,
\]

with the lowest phase index used as a deterministic tie-break. A packet is rejected when max_q N_q is non-positive. Because label compression and bootstrap labels vary by phase, this optimizes actual net payload, not gross allocation.

The selected phase is inferred from the fixed-format encrypted header location. Hider and receiver test the four public header locations and accept exactly one whose framing, phase-bound HMAC and bounded directory validate. The phase index is part of the HMAC input but is not separately stored or sent out-of-band. This selection does not increase the number of candidate centres; it can only improve the best net budget among the four equal-density layouts.

This is a candidate method contribution, not a measured gain. The natural-image evaluation must report all four N_q values, chosen phase, gain over a preregistered fixed phase (phase 0), and the percentage of natural images for which selection improves net bits. The maximum-of-four selection advantage must be measured on a frozen corpus and compared with adaptive spatial/partition methods in the literature.

The proof is conditional on the implemented model actually having only a 3x3 per-pixel input and on no cross-candidate/global operations being introduced at inference. The protocol identity must pin the checkpoint hash, preprocessing, rounding, evaluation mode, batch behaviour and software environment.

## 3. In-band metadata and complete net-capacity accounting

EDR2 stores a four-bit class for each candidate, packs two classes per byte, and uses zlib level 9 only when it strictly reduces the packed byte count. The in-band packet has a fixed 20-byte encrypted header, the encrypted directory and a 32-byte HMAC-SHA256 tag. The header contains the directory codec, directory length and payload length. The reserved three-byte header field must decode to zero; a malformed value is rejected before the directory length is used.

Let:

- (C=|G|) be the number of candidate centres;
- (n_i) be the number of replaceable MSBs for candidate (i);
- (G_0=\sum_{i=0}^{C-1}n_i) be gross candidate slots;
- (L) be the encoded directory length in bytes;
- (H=20+L+32=52+L) be the number of bootstrap candidate bytes;
- (F=\sum_{i=0}^{H-1}n_i) be the ordinary slots forfeited at bootstrap carriers;
- (S=G_0-F) be the ordinary slots remaining; and
- (B=8H) be the bits required to back up the original (H) bootstrap bytes.

The signed net user-payload budget is

[
  N=S-B=G_0-F-8H.
]

An image is rejected before producing a packet whenever (N\leq0). The reported rate must be (N/(hw)), not (G_0/(hw)). Rejected images must retain their signed negative budget in the results ledger; they must not be reported as zero-capacity successes.

The backup is mandatory: writing a header, encrypted directory or tag over candidate bytes without preserving those original bytes would violate reversibility. The backup and payload slot ranges are disjoint, even if the boundary falls inside a candidate byte.

## 4. What is and is not new

### Established ingredients — do not claim these as new

CNN-based prediction, prediction-error-based bit-plane allocation, MSB replacement, room reservation before encryption, in-image location/label maps, entropy coding, AES-CTR, keyed authentication and separable RDHEI have prior art. The project must not claim any of these primitives alone as a novelty.

### Narrow candidate contribution

The research claim should be framed as a verifiable integration of:

1. a finite-domain maximum-density safe lattice derived from the fixed 3x3 CNN's masked receptive field;
2. four parity phases, each preserving the same CNN-context synchronization guarantee;
3. content-adaptive phase selection maximizing the exact signed net payload N_q after directory compression, metadata-carrier opportunity cost and bootstrap backup;
4. implicit phase discovery through the authenticated in-band header location, without external phase metadata;
5. an encrypted, compressed, self-framed class directory and complete bootstrap backup; and
6. receiver-only exact reconstruction with explicit net-capacity acceptance.

This claim must not be framed as new generic partitioning, embedded labels, adaptive bit-plane coding, authentication or choosing the highest-capacity partition. Novelty remains conditional on full-text comparison of the exact CNN-receptive-field-constrained phase family, bitwise prediction synchronization, phase-bound authenticated header self-location, and signed net-capacity optimisation against close prior art.

The claim is **highly conditional**. Generic partition selection, dynamic block partitioning, embedded compressed recovery maps and net-capacity accounting are established. Only the combination of (i) a phase family constrained by the fixed CNN receptive field, (ii) exact owner/receiver prediction identity after arbitrary candidate writes, and (iii) authenticated self-location of the selected phase may remain distinctive. The complete methods of Wang et al. (overlapping sawtooth and capacity-based partition selection), Nguyen et al. (D4 symmetry, dynamic partitioning, compressed in-image location map), and Hoang Nam & Nguyen (overlapping sub-blocks and shared-MSB encoding) must be compared before stating even this narrow gap. Do not use “first”, “state of the art”, “superior”, “high capacity”, “universal” or “novel CNN” without full-text evidence and matched experiments.

## 5. Prior-art checks that the manuscript must address

The following works already overlap with important EDR2 ingredients. They must be included in the related-work comparison and checked at full-text level for candidate selection, receiver inputs, metadata representation, recovery synchronisation, authentication and net-capacity accounting.

- Xu, D. (2022). *Reversible data hiding in encrypted images with high payload*. IET Information Security, 16(4), 301–313. [https://doi.org/10.1049/ise2.12062](https://doi.org/10.1049/ise2.12062). This work uses improved GAP prediction, a binary location map and multi-MSB substitution; it is directly relevant to predictor-driven bit-plane embedding and embedded location information.
- Qin, J., He, Z., Xiang, X., Tan, Y., & Michienzi, A. (2022). *Reversible Data Hiding in Encrypted Images Based on Adaptive Gradient Prediction*. Security and Communication Networks. [https://doi.org/10.1155/2022/8757594](https://doi.org/10.1155/2022/8757594). This is relevant to adaptive local prediction and prediction-guided room allocation.
- Li, Z., & Li, T. (2025). *A Robust Multi-Key Reversible Data Hiding Scheme Leveraging Image Duplication and Smoothness Estimation*. Security and Privacy, 8(6). [https://doi.org/10.1002/spy2.70145](https://doi.org/10.1002/spy2.70145). This work is relevant to context enlargement, block selection and recovery under small-block settings.
- Zhou, G., & Li, N. (2026). *Reversible Data Hiding in Encrypted Images Based on Bit-Plane Classification and Adaptive Group Coding*. IET Image Processing, 20(1), e70310. [https://doi.org/10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310). It combines prediction errors, block/sequence-level bit-plane classification and adaptive group coding.
- Peng, S., Zhang, M., Ke, Y., Jiang, C., et al. (2026). *High-capacity reversible data hiding in encrypted images using dual-stage bit-plane compression and CP-ABE-based recovery authorization*. Scientific Reports. [https://doi.org/10.1038/s41598-026-65778-w](https://doi.org/10.1038/s41598-026-65778-w). It uses predictor errors, bit-plane compression, adaptive hierarchical block variable-length coding and block rearrangement.
- Hoang Nam, T., & Nguyen, T.-S. (2026). *Reversible data hiding in encrypted images based on overlapping block partitioning and shared-MSB encoding*. CTU Journal of Innovation and Sustainable Development, 18 (Special issue). [https://doi.org/10.22144/ctujoisd.2026.049](https://doi.org/10.22144/ctujoisd.2026.049). It uses four overlapping sub-blocks and shared-MSB encoding, and is a particularly important recent partitioning comparator.
- Wang, X., Li, L., Wang, M., et al. (2025/2026). *High-capacity reversible data hiding in encrypted images based on MSB sharing and overlapping sawtooth partition*. Journal of King Saud University Computer and Information Sciences, 38, 24. [https://doi.org/10.1007/s44443-025-00238-5](https://doi.org/10.1007/s44443-025-00238-5). It uses overlapping sawtooth partitions, multiple partition variants and discusses partition selection for maximum capacity; it is a direct comparator for any claim about adaptive phase/partition selection.
- Nguyen, N. H., Cao, T. L., & Pham, V. A. (2026). *High-Capacity Reversible Data Hiding in Encrypted Images Using D4-Symmetry Bidirectional Pixel Shifting and Context-Aware Recovery*. Applied Sciences, 16(20), 10343; published 19 October 2026. [https://doi.org/10.3390/app162010343](https://doi.org/10.3390/app162010343). It combines D4 symmetries, bidirectional pixel shifts, dynamic block partitioning, a compressed in-image location map, exact reconstruction and explicit net-rate accounting. Do not claim those elements individually as new.

- Li, X., Zhou, X., Zhou, Q., Han, S., Liu, Z., & Kuniya, T. (2020). *High-Capacity Reversible Data Hiding in Encrypted Images by Information Preprocessing*. Complexity. [https://doi.org/10.1155/2020/6989452](https://doi.org/10.1155/2020/6989452). It is relevant to room reservation, preprocessing and in-image label-map coding.

These references are a starting comparison set, not an exhaustive systematic review. In particular, the partition-grid synchronisation idea must be compared against the full methods—not just titles, abstracts or secondary summaries—before stating the exact research gap.

## 5.1. Novelty boundary after the 2026 prior-art check

The recent literature rules out several tempting but indefensible claims:

- Four-way partition selection or selecting the partition with the highest capacity is not new by itself.
- Dynamic block partitioning and overlapping partitions are not new by themselves.
- Compressed recovery/location metadata embedded in the marked image is not new by itself.
- Charging location-map and displaced-bit costs in a net-capacity calculation is not new by itself.
- Shared-MSB encoding and block-level bit-plane compression are established, active RDHEI directions.

The potentially distinguishing object is not simply “choose one of four grids”. It is a phase family whose admissibility is proven from the fixed CNN receptive field, with exact prediction equality after arbitrary candidate writes, plus phase discovery from the phase-bound authenticated header location. The hider and receiver must derive exactly the same selected candidate geometry with no sidecar. The method-level difference from existing adaptive block selection and overlapping partition methods must be established by comparing their actual selection predicates, prediction synchronization requirements, receiver inputs and accounting—not by comparing titles or rates from different protocols.

## 6. Evaluation protocol required before paper writing

### Natural-image corpus only

The EDR2 evaluation uses real, source-database image data only. The six fixed root-level grayscale images in `data/kodak_gray/` are a separate smoke-test set; they are not a prerequisite for the expanded USC-SIPI evaluation. The expanded corpus must be catalogue-curated and entered in `natural_image_allowlist.json` with a relative path, exact source-file SHA-256, classification `natural` or `constructed`, corpus group, and curation note. USC-assembled texture mosaics are classified as constructed and reported separately. Inventory presence alone does not qualify an image. RGB and 16-bit images must not be silently converted into grayscale. Odd dimensions, segmentation-information maps, resolution charts, calibration wedges and pixel rulers are excluded. Exact pixel duplicates must be deduplicated and reported.

The USC-SIPI corpus must be described in distinct strata: unrotated texture scans/mosaics, rotated texture series, monochrome aerial imagery, monochrome miscellaneous imagery, and grayscale sequence frames. Histogram-equalized variants, rotated copies, and adjacent frames are correlated samples; report subgroup results and avoid describing all files as independent natural-scene photographs. The official catalogue reports 155 monochrome texture-volume images (including the rotated texture series), one monochrome aerial image, 28 monochrome miscellaneous images and 69 grayscale sequence frames before catalogue exclusions, image-format filtering and pixel deduplication. The exact accepted corpus count must come from the generated manifest, not these catalogue totals. USC-SIPI warns that rights are mixed and unknown for some files; do not redistribute source images or promise publication rights based only on their availability.

Synthetic constant, random, tiny, checkerboard, noise, or other generated controls are excluded from paper-facing capacity, recovery, averages, plots and claims. Historical synthetic-control experiments remain only as archived engineering history; they are not EDR2 natural-image evidence. Small generated arrays may still appear inside unit tests because they are software fixtures, not experimental samples.

### Required measurements

For every natural image, report:

- source file SHA-256, decoded-pixel SHA-256, dimensions and corpus provenance;
- candidate count and candidate fraction;
- directory raw size, compressed size and selected codec;
- gross slots (G_0), bootstrap opportunity cost (F), backup cost (8H), signed net bits (N), net bpp and accept/reject decision;
- predictor and end-to-end preparation, embedding and receiver timings with hardware, software, threads and repetitions;
- exact image recovery and exact payload recovery for payload lengths 0, 1, short, half-capacity, capacity-minus-one and full capacity;
- authentication rejection for changed ciphertext/header/directory/tag, plus wrong key, wrong nonce, wrong hider capability key, malformed header, invalid directory and over-capacity payload;
- receiver file-read audit showing that its only image-dependent input is the final marked encrypted image; and
- checkpoint and source-code SHA-256 identities.

Use per-image values and paired comparisons. Report the number of accepted and rejected natural images. Do not average away rejected images; present the signed budget distribution. Do not describe (65{,}025) candidate centres per 512x512 image as 65,025 bits or as net bpp.

### Reproducible phase-selection runs

From the repository root, after preparing `data/usc_sipi_gray/` and its hash-pinned allowlist:

```bash
# Normal protocol: evaluate all four phases and select maximum signed net payload.
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/usc_sipi_gray \
  --allow-missing-baseline \
  --output-dir results/edr2_adaptive_phase

# Matched fixed-phase baselines; use a distinct output folder for each run.
for phase in 0 1 2 3; do
  python final_rdhei_protocol_gate_20261022/run_gate.py \
    --data-dir data/kodak_gray \
    --fixed-phase "$phase" \
    --output-dir "results/edr2_fixed_phase_$phase"
done

# Assert-based mapping, receiver, lattice, phase-discovery and allowlist tests.
python -m pytest -q \
  tests/test_mapping.py \
  tests/test_edr2_receiver_only.py \
  tests/test_edr2_publication_hardening.py
```

The auto run's `capacity_summary.csv` must include each image's corpus group, selected phase, all four per-phase net capacities, and the phase-selection gain relative to phase 0. The group counts in `input_manifest.json` and `run_summary.json` define the accepted subgroup sizes. The fixed-phase runs deliberately report unavailable alternative-phase scores as null; their selected-phase capacity remains directly comparable. Use identical source-image bytes, checkpoint hash, seed, thread count, payload cases and software environment in every run. Do not pool multiple copies of the same natural image as independent samples.

### Matched ablations required

At minimum compare:

1. fixed phase 0 versus four-phase adaptive selection; report all N_q values and chosen phase per natural image;
2. step-3 versus each step-2 phase using the same checkpoint, codebook, header, codec and net-overhead accounting;
3. the maximum-density step-2 family versus a deliberately sparser lattice;
4. compressed directory versus raw packed labels;
5. complete bootstrap backup versus an intentionally omitted-backup negative control, which must fail reversibility; and
6. EDR2 receiver-only packets versus the legacy dense-map receiver, with all external map bits charged to the legacy baseline.

Do not tune lattice phase, label coding, test images or payloads after seeing per-image results without recording the change and rerunning the frozen protocol.

## 7. Frozen checkpoint and training provenance

No retraining is planned. The author confirms that the existing residual CNN-3x3 checkpoint was trained using 10,000 BOSSBase grayscale images. The checkpoint is evaluated as a frozen artifact and must be identified by its full SHA-256 in every result release.

The original per-checkpoint training manifest, image list, split file and historical logs are not present in the current repository. Therefore the 10,000-image training history is author-attested, not independently reconstructable from the checkpoint. A previous rejected manuscript draft stated that 200 BOSSBase images were sampled; this conflicts with the current author-confirmed 10,000-image account. Remove the obsolete 200-image statement if it does not describe the actual run, and report the provenance limitation transparently. Do not infer optimiser, epochs, seed, split or validation accuracy from the binary weights. No retraining is needed to complete the EDR2 protocol evaluation.

## 8. Current limitations and non-claims

- EDR2 is currently specified for native 8-bit grayscale only; RGB is not validated.
- The protocol's positive net capacity is content-dependent; images with (N\leq0) are rejected. No general positive-capacity guarantee is claimed.
- The candidate lattice improves the geometric mutable fraction but does not, by itself, prove improved net payload.
- Exact prediction identity has been verified only on the pinned implementation environment until a cross-platform or integer-inference study exists.
- The security design uses domain-separated HKDF keys, AES-256-CTR and HMAC-SHA256, but this is not a formal cryptographic proof. State the threat model and the hider's capability-key assumptions.
- The authorised hider receives capability keys and learns the encrypted directory's decoded class map. This leakage and trust assumption must be stated.
- No matched comparison against recent RDHEI schemes has yet been run.
- The existing EDR2 natural-image gate and new assert-based tests have been changed in this branch but **must be executed** before their results can support the paper. Do not call them passing until CI/local execution supplies logs.

## 9. Paper-writing gate

Paper writing should begin only after all of the following are complete:

1. `pytest -q` passes, including the assert-based exhaustive mapping and new EDR2 tests.
2. The 6-image natural baseline gate completes with all accepted and rejected records.
3. The manually curated expanded natural-image corpus gate completes, if that corpus is used.
4. The step-2 versus step-3 matched ablation is measured.
5. The receiver-only input audit, payload-boundary tests and all negative security tests pass.
6. Per-image net capacity and all aggregates are recomputed from raw result files.
7. The novelty/related-work comparison is reviewed against the full texts of the closest 2025–2026 methods.
8. The authors reconcile the BOSSBase 10,000-versus-200 discrepancy and approve the final provenance statement.
9. The paper claims, tables and figures are independently checked against committed evidence hashes.

**No fresh EDR2 capacity numbers are asserted in this document.** The candidate count and protocol equations are design facts; measured EDR2 rates require a fresh natural-image run.
