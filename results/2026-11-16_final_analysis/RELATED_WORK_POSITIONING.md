# Related-work positioning and novelty boundary

**Checked:** 2026-11-16. Focused prior-art map, not a systematic review. Complete the final reference audit before submission.

## Closest prior art

| Work | Relevant mechanism | Consequence for our novelty claim |
|---|---|---|
| Yi & Zhou (2018), PRDHEI / adaptive checkerboard-based prediction (ACBP), *Signal Processing* 150, 171–182, [doi:10.1016/j.sigpro.2018.04.016](https://doi.org/10.1016/j.sigpro.2018.04.016) | Predicts three-quarters of pixels using a one-quarter checkerboard reference set and combines it with adaptive bit-level embedding / bit replacement. Exact reversibility is reported at ε=1; the 4.5 bpp result is for ε=255 with recovered-image PSNR above 32 dB. | Quarter-grid/checkerboard occupancy and bit replacement are prior art. The 4.5 bpp operating point is not exact recovery. Our distinction must be the CNN receptive-field invariance argument and signed-net accounting, not a new checkerboard pattern. |
| Ping, Huo & Guo (2024), asymmetric CNN and adaptive-mean predictors for RDHEI, *Expert Systems with Applications* 246, 123270, [doi:10.1016/j.eswa.2024.123270](https://doi.org/10.1016/j.eswa.2024.123270) | Asymmetric CNN predictor plus adaptive-mean second stage in a two-stage RDHEI scheme, with multi-MSB substitution and separate recovery/extraction. | CNN prediction for RDHEI is established. Do not claim “first CNN predictor for RDHEI” or general novelty from using a CNN. |
| Cheng, Chen & Guan (2025), pixel-level masked autoencoder and polar code for RDHEI, *Signal Processing* 226, 109664, [doi:10.1016/j.sigpro.2024.109664](https://doi.org/10.1016/j.sigpro.2024.109664) | Pixel-level masked autoencoder for carrier-pixel prediction in a VRAE scheme; polar coding for payload. | Masked-pixel learned recovery is prior art. Our narrow distinction is deterministic local input invariance for a frozen 3×3 CNN under a separated mutable-centre lattice, not masking in general. |
| Wang et al. (online 12 Dec 2025; volume 38, 2026), MSB sharing and overlapping sawtooth partition, *Journal of King Saud University Computer and Information Sciences*, article 24, [doi:10.1007/s44443-025-00238-5](https://doi.org/10.1007/s44443-025-00238-5) | MSB-sharing encoding with overlapping sawtooth partition and block permutation/XOR encryption. | MSB sharing and overlapping partition/reuse are established. |
| Zhou et al. (2026), bit-plane classification and adaptive group coding (BCAGC), *IET Image Processing* 20(1), e70310, [doi:10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310) | MED prediction errors are decomposed into bit-planes, classified using 4-bit sequence patterns and encoded with adaptive fixed-length or Huffman group coding. Reports 4.1472 bpp (BOSSbase), 4.0565 bpp (BOWS-2) and 3.4465 bpp (UCID). | Current high-capacity bit-plane RDHEI is directly relevant. Published rates are not directly comparable without identical datasets and overhead accounting; their magnitude makes a normalized comparison essential. |
| Hung et al. (2026), D4-symmetry bidirectional pixel shifting and context-aware recovery, *Applied Sciences* 16(20), 10343, [doi:10.3390/app162010343](https://doi.org/10.3390/app162010343) | D4-symmetry bidirectional pixel shifts and context-aware recovery for high-capacity RDHEI. | A contemporary recovery alternative that should be discussed and, where feasible, compared. |
| Tram & Nguyen (published 9 Nov 2026), overlapping block partitioning and shared-MSB encoding, *CTU Journal of Innovation and Sustainable Development* 18, Special Issue ISDS, 1–10, [doi:10.22144/ctujoisd.2026.049](https://doi.org/10.22144/ctujoisd.2026.049) | Overlapping blocks and shared-MSB encoding. | Very recent prior art; do not imply overlapping/block-sharing mechanisms are new. |

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

## Critical performance comparison gap

- Native grayscale EDR2 gives pooled signed net 0.059821 bpp over the 243-image corpus (negative outcomes retained) and positive capacity on 163/243 images.
- The separate matched predictor comparison reports mean signed net 0.021603 bpp for v4 under the step-4 / 16-phase grid.
- BCAGC reports average rates of 4.1472, 4.0565 and 3.4465 bpp on BOSSbase, BOWS-2 and UCID. These rates cannot be treated as direct head-to-head results without reconciling datasets, encryption/embedding order and all metadata, backup and authentication costs. The difference in scale nevertheless requires explanation and controlled replication.
- Yi & Zhou report 4.5 bpp at ε=255, whereas exact recovery is reported at ε=1. Do not cite 4.5 bpp as an exact-recovery point.

Do not describe the current system as high-capacity or state-of-the-art until same-dataset, same-overhead and exact-recovery comparisons support that conclusion.

## Required work before submission

1. Reproduce Yi & Zhou's exact-recovery ε=1 case and the ε>1 capacity/distortion trade-off separately; use the same dataset and payload accounting if assumptions permit.
2. Reproduce Ping et al.'s asymmetric CNN/adaptive-mean scheme or provide a detailed source-verified comparison if code is unavailable.
3. Compare with BCAGC on a common subset; normalize headers, maps, backup bits, authentication overhead and exact image/payload recovery.
4. Compare with Cheng et al.'s masked-autoencoder design without conflating its VRAE/polar-code receiver with our RRBE-style protocol.
5. Assess whether D4-symmetry and overlapping/shared-MSB methods can be reproduced.
6. Search patents, conferences, preprints and terminology variants around masked-predictor synchronization, independent sets/checkerboard phases and deterministic learned prediction before asserting novelty.

## Sources consulted

- [Yi & Zhou, 2018 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0165168418301427)
- [Ping et al., 2024 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0957417424001350)
- [Cheng et al., 2025 — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0165168424002846)
- [Wang et al., 2025/2026 — Springer](https://link.springer.com/article/10.1007/s44443-025-00238-5)
- [Zhou et al., 2026 — Wiley](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.70310)
- [Hung et al., 2026 — MDPI](https://www.mdpi.com/10.3390/app162010343)
- [Tram & Nguyen, 2026 — CTU Journal](https://ctujs.ctu.edu.vn/index.php/ctujs/article/view/3142)
