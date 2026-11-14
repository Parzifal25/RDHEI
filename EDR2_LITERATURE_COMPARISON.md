# EDR2 literature comparison and matched-evaluation boundary

**Purpose.** This document positions EDR2 against recent RDHEI work without presenting incompatible published capacity measures as a head-to-head benchmark. The primary EDR2 outcome is signed, in-band **net payload capacity** after metadata-carrier opportunity cost and bootstrap-backup bits. Published papers sometimes report embedding rate, gross room, rate before encryption permutation, or a different net-rate definition. Those values must not be ranked directly against EDR2 until the methods are reproduced on the same images with the same overhead ledger.

## Comparison of close and recent methods

| Work | Main mechanism | Evaluation reported by the paper | Published result / metric | Overlap with EDR2 | Comparability boundary |
|---|---|---|---|---|---|
| Wang et al., *High-capacity RDHEI based on MSB sharing and overlapping sawtooth partition* (published 12 Dec 2025; journal volume 38, 2026), DOI [10.1007/s44443-025-00238-5](https://doi.org/10.1007/s44443-025-00238-5) | MSB sharing encoding with overlapping sawtooth partition; RRBE reservation; block permutation and XOR encryption | Eight standard images plus 200 randomly selected images from each of BOSSbase, BOWS-2 and UCID. The authors state that the permutation operation was omitted in the capacity experiments. | Reports high-capacity performance and evaluates partition parameter/variants; a published partition-choice analysis selects among eight options. | Overlapping partitions, candidate/partition variants, MSB sharing, auxiliary-data reservation and capacity-aware selection are established prior art. | Its capacity experiments omit the permutation operation; EDR2 uses a fixed CNN-context synchronization predicate and a signed net budget including in-band directory and bootstrap backup. Do not treat its headline rate as directly comparable without reproducing both methods under one accounting protocol. |
| Nguyen, Cao & Pham, *High-Capacity RDHEI Using D4-Symmetry Bidirectional Pixel Shifting and Context-Aware Recovery*, *Applied Sciences* 16(20), 10343 (19 Oct 2026), DOI [10.3390/app162010343](https://doi.org/10.3390/app162010343) | D4-symmetry pixel shifting, dynamic block partitioning, context-aware blind recovery, compressed in-image location map | Twelve standard 512×512 grayscale images plus 100 images each from BOSSbase, BOWS-2 and UCID; the paper reports exact reversibility over 312 images. | On twelve standard images: 0.7604 bpp gross and 0.6810 bpp net after the reserved-channel cost; reported 12.8% gain over its bidirectional baseline. | Dynamic partition choice, in-image compressed location metadata, explicit net accounting, exact recovery and no external reconstruction sidecar are close conceptual comparators. | This is a pixel-rearrangement method, not a CNN prediction/bit-plane scheme. Its paper reports within-family reimplementations and a different embedding primitive. The 0.6810-bpp figure is useful context, not an EDR2 matched result. |
| Hoang Nam & Nguyen, *RDHEI based on overlapping block partitioning and shared-MSB encoding*, *CTU Journal of Innovation and Sustainable Development* 18, Special Issue (published 9 Nov 2026), DOI [10.22144/ctujoisd.2026.049](https://doi.org/10.22144/ctujoisd.2026.049) | Four overlapping sub-blocks with shared boundary/reference pixels and shared-MSB encoding | Six standard images; additional experiments on 100 randomly selected BOWS-2 and 100 BOSSBase images. | Abstract reports an average net embedding capacity of 408,730 bits over six standard images and exact image recovery/data extraction. | Overlapping sub-blocks, pixel reuse, shared-MSB encoding, net-capacity reporting and exact reversibility. | The abstract does not provide a directly harmonized per-pixel rate or an image-by-image ledger. Do not convert its average bit count into bpp without the exact image dimensions and weighting scheme. |
| Zhou & Li, *RDHEI based on Bit-Plane Classification and Adaptive Group Coding*, *IET Image Processing* 20(1), e70310 (first published 24 Feb 2026), DOI [10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310) | Prediction-error bit-plane classification; block/sequence units; adaptive fixed-length versus Huffman group coding | BOSSbase, BOWS-2 and UCID | Reports average embedding rates of 4.1472, 4.0565 and 3.4465 bpp, respectively. | Predictor-error classification, bit-plane coding, adaptive code choice and compression of metadata/labels. | Its reported quantity is embedding rate (ER) under its own scheme. EDR2's signed net payload charges a specific four-phase bootstrap header, authentication tag, compressed label directory and original bootstrap-byte backup. A same-data, same-cost reimplementation is needed for a direct numerical comparison. |
| Xu, *Reversible data hiding in encrypted images with high payload*, *IET Information Security* 16(4), 301–313 (2022), DOI [10.1049/ise2.12062](https://doi.org/10.1049/ise2.12062) | Improved GAP prediction, binary location information and multi-MSB substitution | Standard image-based RDHEI evaluation | Prediction-guided multi-MSB payload with a location map. | Predictor-guided bit-plane capacity and embedded location information. | Established ingredients; not a direct numerical baseline for EDR2's four-phase safe lattice and authenticated header discovery. |
| Qin et al., *RDH in encrypted images based on adaptive gradient prediction*, *Security and Communication Networks* (2022), DOI [10.1155/2022/8757594](https://doi.org/10.1155/2022/8757594) | Adaptive gradient prediction and prediction-guided room allocation | Image-based RDHEI evaluation | Adaptive prediction-error-driven capacity allocation. | Adaptive prediction and predictor-dependent room reservation. | Compare methods and exact overhead rules from the full paper; abstract-level descriptions are insufficient for matched numerical comparison. |
| Li & Li, *A Robust Multi-Key Reversible Data Hiding Scheme Leveraging Image Duplication and Smoothness Estimation*, *Security and Privacy* 8(6) (2025), DOI [10.1002/spy2.70145](https://doi.org/10.1002/spy2.70145) | Image duplication and smoothness estimation for multi-key RDHEI | Image-based evaluation | Context enlargement, block selection and recovery under small-block settings. | Context design and content-adaptive capacity/recovery. | Full protocol and key/side-information assumptions must be normalized before a numerical comparison. |

## What the literature rules out as novelty

The following are established ingredients and should not be claimed as novel in isolation:

1. CNN or gradient prediction; prediction-error classification; MSB substitution; compressed label/location maps; RRBE.
2. Dynamic or overlapping partitioning and selection of the partition with the largest capacity.
3. Explicitly accounting for side information, location maps or displaced bootstrap bits in a net-capacity calculation.
4. Shared-MSB encoding, adaptive group coding, AES/CTR, authentication or exact reversible recovery as generic primitives.

## Narrow candidate contribution to test

EDR2's candidate distinction is more specific:

- A maximum-density safe lattice proven against the fixed 3×3 CNN's masked receptive field.
- Four offset/parity phases, each preserving context invariance when all candidate centres are modified.
- Selection of the phase maximizing the **signed** net payload after directory compression, bootstrap-carrier opportunity cost and backup cost.
- Discovery of the selected phase from its authenticated in-band header location, without a separate phase field/sidecar.
- Receiver-only exact reconstruction under the stated key, nonce, checkpoint and protocol-software inputs.

This is still a **candidate** contribution, not a verified novelty claim. The fixed-phase matched ablation is required to demonstrate the gain. The full texts of the sawtooth-partition, D4-symmetry and shared-MSB papers must be compared against the exact safe-set predicate and authenticated self-location mechanism before claiming a research gap.

## Matched comparison protocol needed for a direct performance claim

A defensible head-to-head study would require:

1. The same source images and exact decoded-pixel hashes for every method.
2. The same grayscale scope and image dimensions, without unreported conversion, cropping or resizing.
3. A shared definition of net payload: subtract every displaced metadata/backup bit exactly once; retain non-positive image budgets as rejections.
4. A declared key, nonce, encryption and receiver-side-information model.
5. Identical image inclusion/exclusion and duplicate handling.
6. Exact image and payload recovery checks for every accepted image, with failures reported.
7. Per-image paired differences and correlation-aware uncertainty (the same source-sequence/rotation family must be treated as a cluster).
8. Reimplementations or executable reference code for the comparator. Literature numbers copied from papers remain contextual, not “matched results”.

## Manuscript-safe conclusion

The current results may support a statement that EDR2 implements and validates a four-phase, CNN-context-invariant candidate-lattice protocol with authenticated in-band phase discovery and explicit signed net-capacity accounting. They do **not** yet support a claim of state-of-the-art capacity or superiority over the cited methods. Until matched reimplementations are completed, report published rates in a related-work table with each paper's native metric and dataset, clearly marked as non-comparable context.
