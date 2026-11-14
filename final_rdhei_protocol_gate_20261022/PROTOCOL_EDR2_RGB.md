# CC-EDR2-RGB: Phase-Staggered Cross-Channel EDR2

Status: research prototype. This is a protocol specification and test plan, not a claim of measured superiority or novelty priority.

## 1. Scope

CC-EDR2-RGB is a separate RGB extension. It does not modify the validated grayscale protocol or overwrite its experiment outputs. Inputs are native 8-bit RGB, uint8 H×W×3 arrays with even height and width. No silent RGB conversion, resizing, cropping, or 16-bit down-conversion is permitted.

The frozen residual CNN-3×3 grayscale checkpoint is run independently on R, G and B planes. It is not retrained. A deterministic cross-channel correction is fitted from an unused calibration lattice and fused with the spatial prediction.

## 2. Phase-staggered geometry

The four step-2 safe lattice phases partition the even-sized interior coordinate rectangle into four disjoint parity classes. For one ordered assignment:

- Red uses phase qR.
- Green uses phase qG.
- Blue uses phase qB.
- The remaining phase qA is reserved as the calibration lattice.

The owner evaluates all 24 ordered permutations of three distinct phases for R/G/B. The remaining phase is qA. No channel writes to qA.

Because each channel uses a different phase, the co-located values in the other two channels are unchanged at every target-channel candidate centre. Because candidate centres within a single phase remain Chebyshev-separated by at least two pixels, the masked 3×3 CNN predictor context is also unchanged when other candidate centres in that channel are modified.

The calibration lattice is untouched in all three channels. Its samples are therefore available to the owner and receiver for deterministic regression fitting without transmitting regression coefficients or a per-image sidecar.

## 3. Cross-channel predictor

For target channel c, let a and b denote the other two channels. At any coordinate, the reference feature is the integer rounded mean:

    x = floor((I_a + I_b + 1) / 2)

On qA, fit an affine predictor y = m*x + b for each target channel, where y is that target channel's value. The prototype computes exact integer sums n, sum(x), sum(y), sum(x*x), and sum(x*y), then calculates Q8 coefficients using signed round-to-nearest, ties-to-even arithmetic:

    m_num = n*sum(x*y) - sum(x)*sum(y)
    m_den = n*sum(x*x) - sum(x)^2
    m_Q8 = round_even(256*m_num/m_den), or zero if m_den=0
    b_Q8 = round_even((256*sum(y)-m_Q8*sum(x))/n)

At a target candidate location:

    p_cross = clip(round_even((m_Q8*x+b_Q8)/256), 0, 255)

The frozen CNN spatial estimate is rounded with the established nearest-even rule. The current prototype uses a fixed blend of 3/4 spatial prediction and 1/4 cross-channel prediction:

    p = clip(round_even((3*p_spatial+p_cross)/4), 0, 255)

The fused prediction drives the existing EDR2 error-allocation and label mapping. The blend ratio is a protocol parameter, not a learned parameter. Required ablations should test 0, 1/4, 1/2 and 3/4 with identical source images and phase assignments.

## 4. Joint metadata and net-capacity accounting

The joint directory contains four phase identifiers (qR, qG, qB, qA) and one packed four-bit label sequence for each channel. The raw directory is compressed with zlib level 9 only if the compressed representation is shorter.

A single encrypted header, one encrypted joint directory and one HMAC-SHA256 tag are stored in the first H red-channel candidates of qR. Let GR, GG and GB denote gross ordinary MSB slots across all three candidate lattices. Let FR be the ordinary slots forfeited by the H red bootstrap carriers. The ordinary stream is:

    S = GR + GG + GB - FR

The protocol preserves the original H red bootstrap bytes using B=8H bits from the beginning of the ordinary stream. The remaining stream is the net payload budget:

    N_RGB = S - 8H

The phase assignment is rejected when N_RGB is non-positive. Net bpp is N_RGB divided by H_image times W_image, i.e. bits per RGB pixel. The 24 assignments are ranked by signed N_RGB. Ties are resolved lexicographically by the phase tuple.

The evidence ledger must report gross slots, red bootstrap opportunity cost, metadata bytes, backup bits, signed net payload, net bpp, channel phase assignment and calibration phase separately.

## 5. Encryption and authentication

A new EDR2RGB HKDF context is used. R, G and B image planes receive three independent AES-256-CTR keys derived from the master key and nonce with channel-specific context strings. This avoids reusing one CTR key/keystream across three planes.

The RGB data-hiding capability and its header-bootstrap, header-final, directory, payload and authentication keys are separately derived under the EDR2RGB context. The grayscale EDR2 key domains are not reused.

The HMAC covers the full marked RGB array, image dimensions and four-phase tuple. The tag is stored in the red bootstrap lattice. The receiver first tests the red header location, then authenticates all six ordered G/B phase assignments possible for that red phase. It must find exactly one valid assignment before decrypting or decompressing the directory. The decrypted directory phase tuple must match the authenticated tuple.

The hider receives the reserved encrypted RGB image and one RGB data-hiding capability. It does not receive the original image, image-encryption keys, predictor maps, label maps, regression coefficients or a phase sidecar.

## 6. Receiver reconstruction

The receiver semantic inputs are the marked RGB image, master key and nonce. It:

1. Discovers the red header phase and authenticates exactly one full phase assignment.
2. Decrypts and validates the bounded joint label directory.
3. Extracts and decrypts the aggregate payload bitstream, checking zero padding.
4. Restores payload-carrier ciphertext bits using the per-channel AES-CTR zero-reservation keystreams.
5. Restores red bootstrap ciphertext bytes using the red-channel keystream.
6. Decrypts each channel with its own image key.
7. Recomputes cross-channel regressions from the untouched calibration lattice.
8. Recomputes the frozen spatial predictions and deterministic integer fusion.
9. Reconstructs each ordinary candidate value using the EDR2 residue and admissible-error interval uniqueness check.
10. Restores the original red bootstrap bytes from the aggregate backup stream.

No sender-side per-image data or external regression/label/phase sidecar is an input to the receiver.

## 7. Required experiments

Before any performance claim, run:

- Exact RGB image and payload recovery on every eligible RGB image.
- Wrong-key and tamper rejection.
- Bit-exact payload lengths, including zero, non-byte-aligned and capacity-boundary payloads.
- Cross-channel blend weights 0, 1/4, 1/2 and 3/4.
- All 24 phase permutations versus a fixed predeclared phase assignment.
- Calibration-lattice regression versus no cross-channel correction.
- Per-channel prediction MAE and aggregate signed net RGB capacity.
- Metadata, bootstrap opportunity cost, backup bits, net bpp, and rejection rate.
- Correlation-aware statistics by source image family and sequence.

Do not count correlated video frames or transformed copies as independent scenes. Keep source-image hashes and all exclusions.

## 8. Novelty boundary

RGB RDHEI, cross-channel prediction, colour-channel correlation and adaptive channel allocation are established research directions. RGB support or cross-channel prediction alone is not novel.

The narrower candidate contribution to investigate is the co-design of:
- Three mutually disjoint channel-specific EDR2 lattices.
- A fourth jointly untouched calibration lattice.
- Deterministically recomputed cross-channel regression without coefficient side information.
- CNN/cross-channel predictor synchronization after arbitrary writes to all three channel lattices.
- Joint phase-permutation selection by aggregate signed net capacity with authenticated in-band phase discovery.

This remains a candidate contribution. A full-text comparison with existing encrypted-colour RDHEI methods and matched experiments is required before using novelty or superiority language.

## 9. Implementation status

The RGB code is a research prototype. It has not yet passed CI, full-corpus evaluation, independent security review or publication-level matched experiments. The grayscale protocol and its existing results remain the baseline and are not modified by this branch.
