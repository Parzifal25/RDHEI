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


## Additional close comparators identified in the 2025–2026 literature

| Work | Method details and evaluation reported | EDR2 relevance | Rate / comparison treatment |
|---|---|---|---|
| Ren et al., *Reversible data hiding and authentication scheme for encrypted image based on prediction error compression*, *Scientific Reports* 15, 11636 (4 Apr 2025), DOI [10.1038/s41598-025-95433-9](https://doi.org/10.1038/s41598-025-95433-9) | Uses an ISGAP-based predictor and adaptive Huffman coding of prediction errors, and includes authentication for both plaintext image content and ciphertext/payload. The paper's evaluation includes ten 512×512 grayscale standard images and additional samples from BOSSBase and BOWS-2. It also describes start-position information and distinct keys for separable extraction/recovery. | A particularly close comparator for prediction-error compression plus authentication. It establishes that authentication, predictor-based coding, multiple key roles, and in-band extraction-position information are already used in RDHEI. | The paper reports embedding-rate values (including 3.39 bpp on BOSSBase and 3.27 bpp on BOWS-2 in its evaluation). Do not compare directly to EDR2 signed net bpp until its exact ER denominator and all reserved/authentication/bootstrap costs are normalized on the same files. |
| Zhang et al., *High-Capacity Reversible Data Hiding in Encrypted Images via Robust Regression and Deep-Feature-Guided Prediction Error Encoding*, *IEEE Transactions on Consumer Electronics* (2026), DOI [10.1109/TCE.2026.3665305](https://doi.org/10.1109/TCE.2026.3665305) | A pretrained neural network extracts multichannel deep features; robust regression predicts/encodes prediction errors, with non-negative and radix-remainder transformations used to concentrate the error distribution. The abstract lists BOSSBase, BOWS-2, BrainTumor and USC-SIPI texture datasets. | This directly rules out any broad claim that deep features or neural-network guidance in RDHEI are new. The defensible distinction must be the exact spatial synchronization proof and authenticated phase-location mechanism, not CNN use. | The abstract reports high embedding rates but a same-definition signed-net rate was not established in the available comparison. Treat its numbers as the paper's native ER, not directly comparable net payload. |
| Peng et al., *High-capacity reversible data hiding in encrypted images using dual-stage bit-plane compression and CP-ABE-based recovery authorization*, *Scientific Reports* (2026), DOI [10.1038/s41598-026-65778-w](https://doi.org/10.1038/s41598-026-65778-w) | Uses zero-run coding of consecutive all-zero high-order bit planes followed by adaptive hierarchical block variable-length coding for remaining bit planes; includes ciphertext-policy attribute-based recovery authorization. | Strong comparator for compressed bit-plane directories, hierarchical block coding and recovery/key authorization. | Compare the reported embedding rate only after harmonizing the embedded-map and backup costs. It is not a lattice-phase synchronization comparator. |

## Expanded novelty matrix

Legend: “Yes” means the ingredient is demonstrably present in the cited method as described by its paper; “No evidence found” means the searched method description/full text did not establish that exact mechanism, not a proof that no paper anywhere has done it.

| EDR2 claim component | Wang MSBSE-OSP | D4 symmetry (2026) | CTU shared-MSB (2026) | Zhou–Li BCAGC (2026) | Ren authentication (2025) | Zhang deep-feature (2026) | Peng dual-stage (2026) |
|---|---|---|---|---|---|---|---|
| Prediction-error driven capacity / bit-plane coding | No; MSB sharing / partition | Not its core primitive | Shared-MSB | Yes | Yes | Yes | Yes |
| Neural/deep features in RDHEI | No evidence found | No evidence found | No evidence found | No evidence found | No evidence found | Yes | No evidence found |
| Adaptive/overlapping partition or candidate layout | Yes | Yes | Yes | Block/group adaptation | Adaptive prediction, not a demonstrated EDR2 lattice | Feature-guided grouping | Hierarchical blocks |
| Compressed in-band location/label information | Yes | Yes | Yes/shared-MSB structure | Yes/group codes | Yes/position and authentication information | Prediction-error coding and associated auxiliary information | Yes/bit-plane/block coding |
| Explicit net-rate / overhead accounting | Yes; paper distinguishes reservation/capacity, but its permutation is omitted in capacity experiments | Yes; reports net rate after reserved-channel cost | Abstract reports net embedding capacity | Native ER; must normalize | Native ER; must normalize | Native embedding rates; must normalize | Native rate; must normalize |
| Authentication / authenticated content | Not central to the compared partition claim | Context-aware recovery, but authenticated phase self-location not established from current comparison | Not established in abstract | Not central | Yes, plaintext and ciphertext/payload authentication | Not established as EDR2-style phase authentication | Recovery authorization (CP-ABE), not equivalent to EDR2 HMAC header |
| Receiver-only exact reconstruction | Separable extraction/decryption described | Blind/context-aware recovery | Exact reversible recovery claimed | Exact RDHEI recovery | Separable key-based extraction/recovery | Exact RDHEI recovery | Recovery authorization and reversible embedding |
| Predictor-receptive-field-constrained maximum-density lattice | No evidence found | No evidence found | No evidence found | No evidence found | No evidence found | No evidence found | No evidence found |
| Four offset phases selected by signed net payload after metadata and backup | Partition variants / capacity selection, but not same criterion | Dynamic partitions and net rate; not same CNN-safe phase family | Overlapping blocks, no evidence of this exact signed phase rule | Adaptive group coding, not same geometry | No evidence found | No evidence found | Adaptive coding, not same geometry |
| Selected phase discovered from phase-bound authenticated header coordinates, with no phase sidecar | No evidence found | No evidence found | No evidence found | No evidence found | Authenticated and position data are present, but no evidence found of this exact phase-bound coordinate search | No evidence found | No evidence found |
| Exact owner/receiver predictor identity after arbitrary candidate-centre writes, proven from receptive field | No evidence found | Context recovery exists but not same CNN invariant | Not established | Not established | Prediction-error coding exists but not same proof | Deep feature predictor exists, but no same lattice proof established | Bit-plane compression, not same proof |

### Manuscript-safe related-work paragraph (draft)

Recent RDHEI research has advanced prediction-error coding, adaptive bit-plane grouping, block partitioning, and in-band recovery metadata. Prediction-guided MSB substitution and location-map coding are established, while more recent methods investigate overlapping sawtooth partitions, dynamic D4-symmetry block selection, overlapping sub-block/shared-MSB encodings, adaptive group coding, authenticated prediction-error compression, deep-feature-guided prediction, and hierarchical bit-plane compression. These developments preclude treating CNN use, partition selection, compressed in-band maps, MSB sharing, authentication, or net-rate accounting as standalone novelties. EDR2 is therefore positioned more narrowly: it derives candidate embedding centres from a finite-domain maximum-density lattice constrained by the fixed masked 3×3 CNN receptive field, considers four offset phases that retain predictor synchronization after arbitrary candidate writes, and selects the phase with the greatest signed payload after its in-band directory and bootstrap-restoration costs. The chosen phase is discovered through its phase-bound authenticated header location rather than a separate phase index. This contribution remains conditional on matched fixed-phase experiments and a full-text comparison of the exact synchronization predicate and header-location mechanism with recent adaptive-partition and authenticated RDHEI designs.

### Publication cautions

- Do not say “first CNN-based RDHEI,” “first adaptive partition,” “first authenticated RDHEI,” “first self-contained recovery,” or “first net-rate accounting.”
- Do not equate ER, gross payload, net payload, and EDR2 signed net bpp.
- Do not compare an article's average bits over a six-image set with EDR2's unweighted mean bpp without a declared aggregation method and identical image set.
- Do not treat a paper's stated exact recovery, encryption-key separation, or authentication as equivalent to EDR2's specific input contract and phase-discovery mechanism without reading its detailed protocol.
- The novelty matrix records the current reviewed set, not an exhaustive global proof of absence.


## Colour-RDH/RDHEI prior art relevant to CC-EDR2-RGB

| Work | Domain and mechanism | Relevance to CC-EDR2-RGB | Boundary for comparison |
|---|---|---|---|
| Li et al., “Reversible data hiding in encrypted color images using cross-channel correlations,” *Journal of Visual Communication and Image Representation* 78 (July 2021), article 103166, DOI [10.1016/j.jvcir.2021.103166](https://doi.org/10.1016/j.jvcir.2021.103166) | Direct encrypted-colour RDH. Preserves/utilizes R/G/B cross-channel correlation through a homomorphic encryption construction and difference-histogram shifting; abstract describes encrypted-domain cross-channel correlations. | Directly rules out claiming the first use of cross-channel correlation in encrypted colour RDH. This is the closest comparator for colour-domain encryption and cross-channel use. | Different encryption/embedding architecture and histogram-shifting primitive. Full-text protocol, key, and exact-rate accounting should be compared before any numerical claim. |
| Li et al., “Reversible data hiding scheme for color image based on prediction-error expansion and cross-channel correlation,” *Signal Processing* 93(9) (September 2013), DOI [10.1016/j.sigpro.2013.01.020](https://doi.org/10.1016/j.sigpro.2013.01.020) | Plaintext colour RDH. Uses edge information from another colour channel to improve prediction accuracy and prediction-error expansion. | Cross-channel predictive refinement of an individual channel is longstanding colour-RDH prior art. | Not an encrypted-domain protocol; its prediction/embedding details are context, not a directly matched EDR2 baseline. |
| “Color image reversible data hiding based on multi-channel synchronized histogram,” *Journal of King Saud University – Computer and Information Sciences* 35(10) (December 2023), article 101804, DOI [10.1016/j.jksuci.2023.101804](https://doi.org/10.1016/j.jksuci.2023.101804) | Plaintext colour RDH. Uses inter-channel correlation, adaptive capacity allocation among RGB channels, and a synchronized histogram. | Rules out claiming that joint channel allocation or inter-channel synchronization alone is new. | Not established by its abstract as an encrypted-domain, receiver-only CNN-synchronized protocol. |
| Wang et al., “Reversible data hiding for color images based on prediction-error value ordering and adaptive embedding,” *Journal of Visual Communication and Image Representation* 103 (August 2024), article 104239, DOI [10.1016/j.jvcir.2024.104239](https://doi.org/10.1016/j.jvcir.2024.104239) | Plaintext colour RDH. Prediction-error value ordering exploits inter- and intra-channel correlation; uses adaptive embedding, dynamic payload partitioning and an improved 2D mapping. | Related to cross-channel prediction and adaptive allocation/partitioning. | Not the same encrypted-domain reservation and receiver contract; do not compare rates directly. |
| “Inter-Channel Correlation Modeling and Improved Skewed Histogram Shifting for Reversible Data Hiding in Color Images,” *Mathematics* 12(9) (2024), article 1283, DOI [10.3390/math12091283](https://doi.org/10.3390/math12091283) | Plaintext colour RDH. Builds an inter-channel correlation model, chooses prediction context adaptively, and performs two-stage embedding. Evaluates USC-SIPI and Kodak image sources. | Related to cross-channel predictor context and multi-channel capacity/embedding design. | A plaintext RDH method; not a matched encrypted-domain comparison. |
| “Reversible data hiding for color images based on channel reference mapping and adaptive pixel prediction,” *Mathematics* 12(4) (2024), article 517, DOI [10.3390/math12040517](https://doi.org/10.3390/math12040517) | Plaintext colour RDH. Uses channel-reference mapping based on RGB variation correlation and adaptive local prediction. | Related to deterministic reference-channel construction and adaptive cross-channel prediction. | Different data-hiding domain and prediction/embedding primitive. |
| Wang et al., “Multi-predictor prediction-error expansion for reversible data hiding in color images with an actual capacity-distortion model,” *Digital Signal Processing* (1 November 2026), article 106367, DOI [10.1016/j.dsp.2026.106367](https://doi.org/10.1016/j.dsp.2026.106367) | Plaintext colour RDH. Fuses multiple predictors with adaptive weights, introduces a capacity-distortion model, and allocates payload across channels with visual sensitivity considerations. | Very recent prior art for predictor fusion and cross-channel colour RDH. It means that predictor fusion itself is not a novelty. | Abstract describes colour RDH, not necessarily encrypted-domain embedding. Compare its full prediction/weighting design, while keeping its native capacity-distortion metric separate from EDR2 signed net bpp. |

### CC-EDR2-RGB novelty boundary

The RGB version must not claim novelty for:
- RGB support itself;
- inter-channel correlation, cross-channel prediction, or per-channel prediction-error expansion;
- predictor fusion or adaptive prediction weights in general;
- adaptive payload allocation among channels;
- synchronized channel histograms or histogram shifting;
- reversible encryption of RGB images in general.

The candidate mechanism is the specific geometric synchronization protocol:
1. Assign three distinct members of the EDR2 step-2 four-phase lattice family to R, G and B.
2. Leave the fourth lattice untouched in all channels.
3. Use that common untouched lattice to calculate deterministic integer cross-channel regression coefficients.
4. Recompute the same coefficients at the receiver from the marked RGB image after decryption, without transmitting per-image coefficients.
5. Preserve the per-channel 3×3 masked CNN context and same-coordinate cross-channel reference samples after arbitrary writes to all three assigned lattices.
6. Search/authenticate the joint channel phase tuple using a single in-band header/tag and choose the permutation that maximizes aggregate signed net capacity after one joint directory and bootstrap backup cost.

This is a candidate mechanism, not a priority claim. The exact phase-staggered geometry, calibration-lattice use, regression synchronization and authenticated joint phase discovery need a targeted full-text search against the 2021 encrypted-colour paper and any later encrypted-colour RDHEI work before a novelty statement is finalized.
