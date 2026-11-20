# Related-work positioning and novelty boundary

**Checked:** 2026-11-20. Focused prior-art map, not a systematic review. Two external methods have now been reproduced on the same 243-image native grayscale corpus; other closest methods remain untested head-to-head. Complete the final reference audit before submission.

## Closest prior art

| Work | Relevant mechanism | Consequence for our novelty claim |
|---|---|---|
| Yi & Zhou (2018), PRDHEI / adaptive checkerboard-based prediction (ACBP), *Signal Processing* 150, 171–182, [doi:10.1016/j.sigpro.2018.04.016](https://doi.org/10.1016/j.sigpro.2018.04.016) | Predicts three-quarters of pixels using a one-quarter checkerboard reference set and combines it with adaptive bit-level embedding / bit replacement. Exact reversibility is reported at ε=1; the 4.5 bpp result is for ε=255 with recovered-image PSNR above 32 dB. | Quarter-grid/checkerboard occupancy and bit replacement are prior art. The 4.5 bpp operating point is not exact recovery. Our distinction must be the CNN receptive-field invariance argument and signed-net accounting, not a new checkerboard pattern. |
| Ping, Huo & Guo (2024), asymmetric CNN and adaptive-mean predictors for RDHEI, *Expert Systems with Applications* 246, 123270, [doi:10.1016/j.eswa.2024.123270](https://doi.org/10.1016/j.eswa.2024.123270) | Asymmetric CNN predictor plus adaptive-mean second stage in a two-stage RDHEI scheme, with multi-MSB substitution and separate recovery/extraction. | CNN prediction for RDHEI is established. Do not claim “first CNN predictor for RDHEI” or general novelty from using a CNN. |
| Cheng, Chen & Guan (2025), pixel-level masked autoencoder and polar code for RDHEI, *Signal Processing* 226, 109664, [doi:10.1016/j.sigpro.2024.109664](https://doi.org/10.1016/j.sigpro.2024.109664) | Pixel-level masked autoencoder for carrier-pixel prediction in a VRAE scheme; polar coding for payload. | Masked-pixel learned recovery is prior art. Our narrow distinction is deterministic local input invariance for a frozen 3×3 CNN under a separated mutable-centre lattice, not masking in general. |
| Ren et al. (2025), prediction-error compression and authentication, *Scientific Reports* 15, article 11636, [doi:10.1038/s41598-025-95433-9](https://doi.org/10.1038/s41598-025-95433-9) | ISGAP prediction, adaptive Huffman coding of prediction errors, plaintext/ciphertext authentication; 100 images each from BOSSBase and BOWS-2. | Reports average 3.39 bpp on BOSSBase and 3.27 bpp on BOWS-2, with exact image recovery. Prediction-error compression and authentication are close overlap; any comparison must normalize protocol and overhead definitions. |
| Wang et al. (online 12 Dec 2025; volume 38, 2026), MSB sharing and overlapping sawtooth partition, *Journal of King Saud University Computer and Information Sciences*, article 24, [doi:10.1007/s44443-025-00238-5](https://doi.org/10.1007/s44443-025-00238-5) | MSB-sharing encoding with overlapping sawtooth partition and block permutation/XOR encryption. | MSB sharing and overlapping partition/reuse are established. |
| Zhou et al. (2026), bit-plane classification and adaptive group coding (BCAGC), *IET Image Processing* 20(1), e70310, [doi:10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310) | MED prediction errors are decomposed into bit-planes, classified using 4-bit sequence patterns and encoded with adaptive fixed-length or Huffman group coding. Reports 4.1472 bpp (BOSSbase), 4.0565 bpp (BOWS-2) and 3.4465 bpp (UCID). | Current high-capacity bit-plane RDHEI is directly relevant. Published rates are not directly comparable without identical datasets and overhead accounting; their magnitude makes a normalized comparison essential. |
| Hung et al. (2026), D4-symmetry bidirectional pixel shifting and context-aware recovery, *Applied Sciences* 16(20), 10343, [doi:10.3390/app162010343](https://doi.org/10.3390/app162010343) | D4-symmetry bidirectional pixel shifts and context-aware recovery for high-capacity RDHEI. | A contemporary recovery alternative that should be discussed and, where feasible, compared. |
| Tram & Nguyen (published 9 Nov 2026), overlapping block partitioning and shared-MSB encoding, *CTU Journal of Innovation and Sustainable Development* 18, Special Issue ISDS, 1–10, [doi:10.22144/ctujoisd.2026.049](https://doi.org/10.22144/ctujoisd.2026.049) | Overlapping blocks and shared-MSB encoding. | Very recent prior art; do not imply overlapping/block-sharing mechanisms are new. |
| Peng et al. (published 8 Aug 2026), dual-stage bit-plane compression and CP-ABE recovery authorization, *Scientific Reports*, [doi:10.1038/s41598-026-65778-w](https://doi.org/10.1038/s41598-026-65778-w) | RRBE-based scheme using predictors, global compression of consecutive all-zero high-order bit planes, adaptive hierarchical block variable-length coding of remaining bit planes, block rearrangement by embedding capacity, and ciphertext-policy attribute-based recovery authorization. Evaluated on BOSSBase, BOWS-2 and UCID. | Highly relevant modern RRBE/bit-plane comparator and a multi-user authorization design not covered by the current protocol. The published abstract establishes the method and datasets, but detailed numeric results should be extracted from the full paper before any numerical comparison. |
| Yin, Xiang & Zhang (2020), Multi-MSB prediction + Huffman coding, *IEEE Transactions on Multimedia* 22(4), 874–884, [doi:10.1109/TMM.2019.2936314](https://doi.org/10.1109/TMM.2019.2936314) | Adaptive multi-MSB prediction; Huffman-coded location information; stream-cipher encryption; multi-MSB substitution. Public implementation pinned and executed on the same 243 native grayscale images. | This reproduction: 243/243 exact payload and host recoveries; positive net payload on 243/243; mean usable native net rate 2.088477 bpp; pooled usable rate 1.973505 bpp. | Same image set and exact-recovery gate; original method's carrier geometry, encryption order and native accounting remain different from EDR2. |
| Yin, She, Tang & Luo (2021), pixel prediction and multi-MSB planes rearrangement (PPMR), *Signal Processing* 187, 108146, [doi:10.1016/j.sigpro.2021.108146](https://doi.org/10.1016/j.sigpro.2021.108146) | Pixel prediction, uniform/non-uniform block classification, multi-MSB-plane rearrangement and separate UB/NUB embedding. Public implementation pinned and executed on the same 243 native grayscale images with four disclosed temporary compatibility corrections. | This corrected reproduction: 243/243 exact payload and host recoveries; positive net payload on 238/243; mean usable native net rate 2.228173 bpp; pooled usable rate 2.118172 bpp. | Result must be called corrected PPMR, not unmodified upstream execution; patch provenance and native rate expression are disclosed. Not a same-packet-cost or same-security-model comparison with EDR2. |

## What can and cannot be claimed

### Do not claim
- First CNN predictor for RDHEI.
- First masked-pixel or learned predictor for RDHEI.
- A new checkerboard/quarter-grid pattern in itself.
- Newness of bit-plane replacement, MSB substitution, adaptive coding, overlapping partitions or generic adaptive phase selection.
- State-of-the-art/high-capacity performance on the current evidence.
- A formal security proof or a novel authenticated-encryption primitive.

### Candidate contribution to defend

The narrow technical claim is a **specific context-invariance condition**: with the v4 3×3 predictor's candidate centre masked and all mutable centres in one step-2 parity phase, modifications to other candidate centres cannot enter the remaining coordinates of a candidate's 3×3 receptive field. This is a sufficient geometric condition for deterministic sender/receiver prediction synchronization, conditional on identical frozen weights, preprocessing, inference mode and rounding. The 2×2 tiling argument gives a density bound for this local noninterference constraint; it does not make the underlying checkerboard pattern new.

Additional engineering/evaluation contributions are maximum-signed-net four-phase selection with explicit metadata/bootstrap-backup accounting, an in-band authenticated packet/receiver input contract, and an evaluated RGB extension with all 24 channel-phase assignments and authenticated blend metadata. These are implementation claims unless a systematic search establishes stronger novelty.

## Completed matched-corpus comparison and remaining gap

The following direct reproductions are now complete:

- Native grayscale EDR2: positive signed net capacity on 163/243 images; pooled signed net 0.059821 bpp; unweighted mean signed net 0.110539 bpp; 978/978 exact receiver trials among accepted images.
- Multi-MSB prediction + Huffman: 243/243 exact payload and host recoveries; positive native net payload on 243/243 images; mean usable net 2.088477 bpp; pooled usable 1.973505 bpp.
- Corrected PPMR: 243/243 exact payload and host recoveries; positive native net payload on 238/243 images; mean usable net 2.228173 bpp; pooled usable 2.118172 bpp.

The 243 source-file and decoded-pixel hashes match exactly across all three methods. The final corpus labels are 239 natural and four constructed; the 29 provenance/correlation clusters are unchanged and were used for 10,000-replicate paired cluster bootstrap (seed 20261119).

The native-protocol comparison does not support a capacity-superiority claim for EDR2. Its usable mean rate is 0.143220 bpp, compared with 2.088477 bpp for Multi-MSB+Huffman and 2.228173 bpp for corrected PPMR. Paired usable-rate differences (baseline minus EDR2) were +1.945257 bpp [95% cluster-bootstrap interval 1.683675, 2.241206] for Multi-MSB+Huffman and +2.084953 bpp [1.769685, 2.403087] for corrected PPMR. Corrected PPMR exceeded Multi-MSB+Huffman by +0.139695 bpp on average [0.049659, 0.213056], but was lower on 40 of 243 images. These are per-image paired mean differences under the methods' own native accounting, not identical packet-cost comparisons.

The 4.5 bpp ACBP point reported by Yi and Zhou is at ε=255, whereas exact recovery is reported at ε=1. Do not cite 4.5 bpp as an exact-recovery point. Zhou et al. report 4.1472, 4.0565 and 3.4465 bpp on BOSSBase, BOWS-2 and UCID for BCAGC. Published rates remain contextual, not head-to-head, unless data, embedding/encryption order and all auxiliary, backup and authentication costs are normalized.

The remaining direct-comparison gap is ACBP/PRDHEI at its exact-recovery operating point, Ping et al.'s asymmetric CNN/adaptive-mean scheme, Cheng et al.'s pixel-level masked-autoencoder scheme, BCAGC, and the recent Peng et al. dual-stage bit-plane/CP-ABE method. Their mechanisms and relevance should remain in related work, but none should be described as reproduced in this study.

## Sources consulted

- [Yin, Xiang & Zhang, 2020 — IEEE Signal Processing Society](https://signalprocessingsociety.org/publications-resources/ieee-transactions-multimedia/2020/04/reversible-data-hiding-encrypted-images)
- [Yin, She, Tang & Luo, 2021 — DOI](https://doi.org/10.1016/j.sigpro.2021.108146)
- [Yi & Zhou, 2018 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0165168418301427)
- [Ping et al., 2024 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0957417424001350)
- [Cheng et al., 2025 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0165168424002846)
- [Wang et al., 2025/2026 — Springer](https://link.springer.com/article/10.1007/s44443-025-00238-5)
- [Zhou et al., 2026 — Wiley](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.70310)
- [Hung et al., 2026 — MDPI](https://www.mdpi.com/10.3390/app162010343)
- [Tram & Nguyen, 2026 — CTU Journal](https://ctujs.ctu.edu.vn/index.php/ctujs/article/view/3142)
- [Peng et al., 2026 — Scientific Reports](https://www.nature.com/articles/s41598-026-65778-w)
