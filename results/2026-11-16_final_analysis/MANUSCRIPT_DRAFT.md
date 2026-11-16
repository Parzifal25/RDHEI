# Context-Invariant CNN Prediction for Reversible Data Hiding in Encrypted Images: An Adaptive Four-Phase Protocol

**Manuscript draft — 2026-11-16**  
**Status:** evidence-aligned working draft; not submission-ready.  
**Author and affiliation details:** to be completed by the authors.

## Abstract

This work investigates a convolutional-neural-network (CNN) predictor for reversible data hiding in encrypted images (RDHEI), with an emphasis on synchronizing prediction at the receiver while accounting explicitly for in-band recovery overhead. The grayscale EDR2 protocol uses a frozen residual CNN with a 3×3 masked neighbourhood and a step-2 safe lattice. Four maximum-density lattice phases are evaluated independently; the selected phase maximizes signed net payload after the encrypted header, compressed label directory, authentication tag, carrier opportunity cost and bootstrap-byte backup are accounted for. The selected phase is implicitly indicated by the authenticated in-band header location, and the receiver requires only the marked encrypted image, a 32-byte master key and a 128-bit nonce as per-image semantic inputs.

On a curated 243-image native grayscale USC-SIPI corpus, the native EDR2 gate produced positive signed net capacity for 163 images and passed 978/978 exact image/payload round-trip trials among accepted positive-capacity cases. A separate matched predictor comparison on the same curated images found that the proposed 3×3 checkpoint achieved 133/243 positive-capacity outcomes and mean candidate MAE 4.813, outperforming MED, GAP and a simplified CALIC-style predictor on those measures, but not the 5×5 no-weighted-loss CNN ablation, which achieved 140 positive cases and MAE 4.623. The 3×3 model was selected for its smaller compute footprint rather than best predictive accuracy. A separate RGB prototype evaluated 51 native RGB images, four spatial/cross-channel blend weights and all 24 ordered phase assignments. Seven images achieved positive net capacity under at least one blend, and all 162 exact-recovery trials over positive image/blend pairs passed. A reproducible CPU benchmark measured the 3×3 full-map predictor at 708.5 ms for a 512×512 input, approximately 185 times the measured MED runtime. These results demonstrate exact-recovery feasibility under the tested conditions, while also exposing sparse RGB coverage and a substantial CPU inference cost. Independent cryptographic review and broader security validation remain necessary.

**Keywords:** reversible data hiding; encrypted images; CNN prediction; safe lattice; bit-plane replacement; in-band metadata; exact recovery; RGB image processing.

## 1. Introduction

Reversible data hiding (RDH) embeds auxiliary data into a host signal while allowing exact recovery of both the embedded message and the original host. In encrypted-image RDH, the system must additionally distinguish the responsibilities of the content owner, data hider and receiver. Early RDHEI work established encrypted-domain data hiding and separable recovery, while reserve-room-before-encryption (RRBE) became an influential architecture for making reversible capacity available before image encryption [1,2].

Prediction-based approaches exploit spatial correlation: a predictor estimates a pixel from its neighbourhood, and a small prediction error can permit replacement of selected most significant bits (MSBs) while retaining enough information to recover the original value. CNN predictors offer a way to learn local prediction functions, but their use introduces a synchronization problem. If data embedding changes pixels that appear in the predictor's receptive field, the sender and receiver may no longer obtain identical predictions.

This paper studies a context-invariance construction for a masked 3×3 predictor. Only candidate centres on one of four step-2 lattices may be altered, and the candidate centre is masked during prediction. Since all distinct mutable centres in the selected lattice are Chebyshev-separated by at least two, no other mutable centre enters a candidate's 3×3 masked patch. Under fixed checkpoint weights, inference mode, preprocessing and rounding, the prediction input at each candidate is therefore unchanged by modifications to candidate-centre values.


Prior art substantially constrains the novelty claim. Yi and Zhou's adaptive checkerboard-based prediction (ACBP) already predicts three-quarters of pixels from a one-quarter reference set and combines this with adaptive bit-level embedding; exact recovery is reported at \(\varepsilon=1\), while the reported maximum of 4.5 bpp occurs at \(\varepsilon=255\), with nonzero recovered-image distortion [11]. Ping et al. subsequently introduced an asymmetric CNN predictor and adaptive-mean second stage for RDHEI [12]. Cheng et al. used a pixel-level masked autoencoder and polar coding in a VRAE design [13]. Thus checkerboard occupancy, bit replacement, CNN prediction for RDHEI and masked-pixel prediction are not claimed as new. More recent work includes MSB sharing with overlapping sawtooth partitions [4], adaptive bit-plane classification/group coding [5], D4-symmetry pixel shifting with context-aware recovery [6], and overlapping-block/shared-MSB encoding [7].

The candidate contribution here is narrower: a deterministic local input-invariance condition for a frozen, centre-masked 3×3 CNN under a step-2 separated candidate-centre phase, coupled to an overhead-aware four-phase signed-net selection rule. The project also provides an authenticated in-band packet and an evaluated RGB variant. These are candidate contributions to defend with direct comparison; they are not evidence that the general checkerboard, CNN, masking or bit-replacement ideas are first-of-kind.

The second design concern is accounting. Gross replaceable bits are not payload capacity. The protocol charges the ordinary slots lost to the in-band header/directory/tag carriers and the additional bits required to preserve the original bootstrap candidate bytes. We therefore use signed net capacity and explicitly report the terms in its accounting identity.

The paper also reports a separate RGB research prototype. The RGB extension assigns three distinct lattice phases to the R, G and B channels and keeps the remaining phase untouched for deterministic cross-channel regression fitting. It is evaluated as an extension experiment, not as a mature or broadly feasible replacement for grayscale EDR2.

## 2. Contributions and scope

The evidence-supported contributions are:

1. **A context-invariant candidate geometry for a masked 3×3 CNN.** Four step-2 phases are alternatives over the valid interior grid. Each phase reaches the 2×2-tile upper bound for the stated radius-one noninterference condition.
2. **Adaptive phase selection under explicit signed net-capacity accounting.** The owner evaluates each phase and selects the greatest signed net payload after metadata-carrier opportunity cost and bootstrap restoration bits. The authenticated header location identifies the selected phase without a phase sidecar.
3. **An in-band EDR2 packet and receiver contract.** Recovery information is stored in the marked encrypted image; the receiver's per-image semantic inputs are the marked image, master key and nonce. The packet uses separated key domains and an authentication tag checked before label-directory decompression.
4. **A matched grayscale predictor/ablation study and native end-to-end evaluation.** Classical predictors and five fixed CNN checkpoints are evaluated under a common comparison grid; native EDR2 is separately tested over the curated grayscale corpus.
5. **An exploratory RGB extension.** A phase-staggered RGB variant combines a frozen spatial CNN predictor with a deterministic cross-channel regression predictor, and exhaustively tests the 24 ordered channel phase assignments and four blend values.

These are implementation and evaluation contributions. The paper does not claim that CNN-based RDH, RRBE, MSB replacement, prediction-error classification, adaptive block/phase selection, compressed in-band maps, RGB prediction or phase assignment are individually new. The novelty boundary against recent RDHEI work must be supported by a careful prior-art comparison and not by a claim of first use.

## 3. Methodology

### 3.1 Grayscale protocol overview

Let the native grayscale image be \(I\in\{0,\ldots,255\}^{H\times W}\), where both dimensions are even under the current implementation. The fixed 3×3 CNN predicts candidate pixel values from a masked neighbourhood. The predictor checkpoint and inference configuration are common protocol software and are not transmitted per image.

For a candidate centre \((y,x)\), the centre value is masked before CNN inference. Let \(G_q\) denote the candidate coordinates for phase \(q\in\{0,1,2,3\}\). The phase offsets are

\[
r_q=1+\left\lfloor q/2\right\rfloor,\qquad
c_q=1+(q\bmod 2),
\]

\[
G_q=\{(r_q+2i,c_q+2j):(r_q+2i,c_q+2j)\in
\{1,\ldots,H-2\}\times\{1,\ldots,W-2\},\ i,j\in\mathbb{Z}_{\geq0}\}.
\]

For any two distinct centres \(g,g'\in G_q\), the design enforces

\[
\lVert g-g'\rVert_\infty\geq2.
\]

No other mutable centre can occur within the candidate's 3×3 patch. Since its own centre is masked, arbitrary modifications to all selected carrier centres leave every masked predictor input unchanged. This establishes an input-geometry invariance property, conditional on identical model weights, inference mode, numerical preprocessing and rounding.

**Candidate-density bound.** The valid interior coordinates form a rectangle with \((H-2)(W-2)\) positions. Partition it into disjoint 2×2 tiles. At most one centre in each tile can be selected under the Chebyshev-separation condition, so

\[
|G_q|\leq
\left\lceil\frac{H-2}{2}\right\rceil
\left\lceil\frac{W-2}{2}\right\rceil.
\]

Each of the four parity-offset step-2 phases attains this bound for the supported even dimensions. For a 512×512 image, this gives \(255\times255=65{,}025\) candidate centres per phase. This is a geometric density bound, not a positive-payload guarantee: directory, authentication and bootstrap-restoration overhead can still make signed net capacity nonpositive.

The candidate's absolute prediction error is mapped to an allocation label that determines the number of replaceable MSBs and an admissible recovery interval. A four-bit label codebook is packed two labels per byte. The packed directory is compressed using zlib level 9 only when compression shortens the representation.

### 3.2 Adaptive phase and signed net capacity

For each phase, let \(G_0\) be the number of gross ordinary replaceable slots, \(F\) the ordinary slots forfeited by metadata-carrier use, \(H_b\) the number of bootstrap carrier bytes, and \(B=8H_b\) the bits needed to preserve the original bootstrap bytes. The signed net payload is

\[
N=G_0-F-B=G_0-F-8H_b.
\]

The owner evaluates all four phases independently, including directory compression, and chooses the phase with maximum \(N\), with the lowest phase index resolving ties. The protocol rejects the image when the maximum \(N\) is nonpositive. Net bpp is \(N/(HW)\). Gross slots, metadata wire-storage bits, foregone ordinary slots and backup bits are separately recorded to avoid double counting.

### 3.3 Encrypted packet and receiver

The EDR2 header contains a magic identifier, directory codec, reserved bytes, encrypted directory length and payload length. It is followed by the encrypted packed label directory and a 32-byte HMAC-SHA256 tag. The packet authenticates the image dimensions, selected phase and marked image bytes, with the tag carrier bytes zeroed for authentication calculation.

A 32-byte master key \(K\) and 128-bit nonce \(V\) feed HKDF-SHA256. Domain-separated keys are derived for image encryption and the data-hiding capability; the capability is further separated into bootstrap-header, final-header, directory, payload and authentication keys. AES-256-CTR is used with distinct derived keys, and HMAC-SHA256 provides the separate packet-integrity check. The same master-key/nonce context must never be reused for another packet.

The owner reserves room and encrypts the reserved image before the independent hider receives the reserved encrypted image, the payload and its data-hiding capability. The hider inserts encrypted payload bits into the designated ciphertext slots and updates the authenticated header/tag without access to the original image or image-encryption key. The receiver discovers the phase from authenticated in-band framing, verifies the tag, decrypts and validates the directory, extracts the payload and reconstructs the original image. Its per-image semantic inputs are the final marked encrypted image, \(K\) and \(V\); shared decoder/checkpoint software is installed.

### 3.4 RGB extension

For RGB input \(I\in\{0,\ldots,255\}^{H\times W\times3}\), the extension assigns three distinct phase lattices to R, G and B and reserves the fourth as a calibration lattice. All 24 ordered R/G/B assignments are evaluated. For each target channel \(c\), the reference feature at a calibration coordinate is the rounded mean of the other two channels,

\[
x=\left\lfloor\frac{I_a+I_b+1}{2}\right\rfloor,
\]

where \(a,b\) denote the two non-target channels. The target-channel values on the untouched calibration lattice form the regression targets \(y\). Let \(n\) be the number of calibration samples and define the integer sums \(s_x=\sum x\), \(s_y=\sum y\), \(s_{xx}=\sum x^2\), and \(s_{xy}=\sum xy\). The deterministic Q8 affine regression coefficients are

\[
m_{\mathrm{num}}=n s_{xy}-s_xs_y,\qquad
m_{\mathrm{den}}=n s_{xx}-s_x^2,
\]

\[
m_{Q8}=
\begin{cases}
0,&m_{\mathrm{den}}=0,\\
\operatorname{round}_{\mathrm{even}}\left(256\frac{m_{\mathrm{num}}}{m_{\mathrm{den}}}\right),&\text{otherwise},
\end{cases}
\qquad
b_{Q8}=\operatorname{round}_{\mathrm{even}}\left(\frac{256s_y-m_{Q8}s_x}{n}\right).
\]

At an embedding candidate, the cross-channel estimate is

\[
p_c=\operatorname{clip}_{[0,255]}
\left(\operatorname{round}_{\mathrm{even}}\frac{m_{Q8}x+b_{Q8}}{256}\right).
\]

The receiver recomputes the same integer sums and Q8 coefficients from the untouched calibration lattice; no per-image regression coefficients are transmitted. The frozen grayscale CNN checkpoint is applied independently to each RGB channel. For spatial prediction \(p_s\), cross-channel prediction \(p_c\), and blend numerator/denominator \(a/d\), the fused prediction is

\[
p=\operatorname{clip}_{[0,255]}
\left(
\operatorname{round}_{\mathrm{even}}
\left(\frac{(d-a)p_s+ap_c}{d}\right)
\right).
\]

The tested settings are \(a/d\in\{0,1/4,2/4,3/4\}\). The R3D2 packet authenticates the blend ratio and four-phase tuple in the encrypted directory and derives distinct image-encryption keys for the R, G and B channels. The extension remains a research prototype; the present 51-image run demonstrates feasibility only for a minority of the corpus.

## 4. Experimental protocol

### 4.1 Datasets

The grayscale corpus contains 243 curated unique native 8-bit USC-SIPI images. Its provenance structure includes rotated texture series, texture scans, sequences and 11 constructed texture mosaics. The manifest groups the 243 images into 29 curator-defined correlation clusters. The RGB corpus contains 51 distinct native 8-bit RGB images, comprising 37 aerial-colour and 14 miscellaneous-colour images. All source and decoded-pixel hashes were unique in the RGB run.

### 4.2 Baselines and ablations

The matched grayscale predictor comparison includes MED, GAP, a simplified CALIC-style predictor and CNN variants v1–v5. All methods use the same step-4 / 16-phase comparison grid for that experiment. The histogram-shift reference is reported separately because its embedding construction and encryption order differ.

The CNN variants comprise:
- v1: 5×5 residual CNN;
- v2: 5×5 CNN without residual connection;
- v3: 5×5 residual CNN trained without weighted loss;
- v4: proposed 3×3 residual CNN;
- v5: 7×7 residual CNN.

No training or fine-tuning was performed during the reported end-to-end evaluations.

### 4.3 End-to-end correctness

The native grayscale EDR2 gate tested accepted images at multiple payload sizes (978 total receiver trials). The RGB gate tested nine payload sizes for every positive image/blend pair, creating 162 receiver subprocesses. A round-trip passes only when both restored image pixels and extracted payload bits match exactly.

### 4.4 Complexity benchmark

The corrected benchmark used a deterministic synthetic 512×512 input, four CPU threads, five warmups and ten timed repetitions per method, each method in a fresh process. Convolutional and linear MACs were counted from actual layer output shapes; one MAC was reported as two FLOPs. Full-map predictor timing is separated from end-to-end RDHEI latency.

## 5. Results

### 5.1 Native grayscale end-to-end

The native grayscale EDR2 gate yielded positive signed net capacity on 163 of 243 images. The 80 remaining images had nonpositive net capacity and were rejected for payload insertion. Among accepted positive-capacity images, 978 of 978 image/payload round-trip cases recovered exactly. The pooled signed net rate was 0.059821 bpp; the unweighted per-image mean was 0.110540 bpp.

### 5.2 Matched grayscale predictors and ablations

The proposed 3×3 v4 checkpoint achieved positive net capacity on 133/243 images, mean signed net 0.021603 bpp and mean candidate MAE 4.8130 in the separate matched predictor study. MED achieved 49 positives and MAE 7.9503; GAP 58 and 7.8408; simplified CALIC-style 49 and 8.2021. Thus v4 improved coverage and MAE versus these three implementations under the matched grid.

CNN v3 (5×5, no weighted loss) achieved 140 positive images and MAE 4.6233; it led the CNN ablation table on these measures. v4 should therefore be justified as the smaller 46,881-parameter model and lower-compute design, not as the overall most accurate CNN. The cluster-bootstrap coverage difference between v4 and v3 was -0.0288 with a 95% interval [-0.0878, 0.0258], which does not support a v4 coverage advantage. The v4-minus-v3 MAE interval was positive [0.1017, 0.2735], favouring v3.

### 5.3 RGB feasibility

The RGB evaluation covered 51 native images, four blends and 24 ordered phase assignments for each image/blend. Seven images achieved positive net capacity under at least one blend; 44 did not. At 0/4, 3 images were positive; at 1/4, 3; at 2/4, 5; and at 3/4, 7. All 162 receiver trials over positive image/blend pairs recovered the original RGB image and payload exactly.

Across directory-fit image/blend pairs, adaptive selection among all 24 ordered R/G/B phase assignments was compared against the fixed assignment (0,1,2). Mean net-capacity gains were 970.3, 1,223.3, 567.2 and 1,543.1 bits for blends 0/4, 1/4, 2/4 and 3/4, with 3, 3, 6 and 8 directory-fit pairs, respectively. The gains are conditional on directory fit and do not make a negative signed net capacity payload-positive.\n\nAt 3/4, all positive examples came from the miscellaneous-colour group (7/14), with no positive aerial-colour image (0/37). The 0/4 fit-only mean bpp was 1.557 over three images; the 3/4 mean was 0.367 over seven images. The blend study thus shows a change in feasible-image coverage, not uniform capacity improvement.

### 5.4 Complexity

The 3×3 model contains 46,881 parameters and 122,816 MACs per candidate patch. It has lower operation count and sampled RSS than the larger CNN ablations. On a full 512×512 synthetic CPU input its mean predictor time was 708.479 ms, while MED was 3.826 ms. The CNN is about 185.2× slower than MED under this particular predictor-only benchmark. The measured predictor cost is a material practical limitation.

## 6. Security and limitations

The active EDR2 code combines HKDF-derived key domains, AES-256-CTR and HMAC-SHA256 authentication. The receiver checks authentication before directory decompression and has bounded directory parsing. Tests cover wrong keys/nonces and tampering. This is implementation-level evidence, not a formal security proof. AES-CTR is a confidentiality mode; integrity in this design is provided separately by HMAC. The hider's data-hiding capability includes authentication authority, so malicious-hider resistance is not claimed. Nonce uniqueness under each master key is mandatory.

The RGB receiver's file-access test patches Python open functions. It is not an OS sandbox. Run #79's top-level source-read count was corrected after identifying a serialized-empty-array aggregation bug: all 162 per-case records contain empty source-read arrays and false source-access flags. No independent cryptographic audit or side-channel assessment has been completed.

The RGB capacity coverage is sparse. The matched predictor baseline includes a simplified CALIC-style implementation. The work has not been directly compared against the closest checkerboard ACBP, asymmetric-CNN RDHEI, PLMAE or BCAGC methods; published rates use different protocols and accounting. The novelty and capacity positioning therefore remain provisional until controlled comparisons are completed. The grayscale corpus includes correlated sequences/texture groups. Complexity timings are CPU- and implementation-specific, and the sampled RSS method may miss transients. The present work has no GPU timing or fully measured active-protocol end-to-end throughput benchmark.

## 7. Conclusion

The native grayscale EDR2 implementation demonstrates positive net payload for a majority of the curated 243-image grayscale set and exact recovery across every attempted positive-capacity trial. The matched predictor experiment indicates that the proposed 3×3 CNN improves on the classical predictors tested, while a 5×5 no-weighted-loss ablation achieves better prediction accuracy and matched capacity coverage. The 3×3 choice is a model-size/compute trade-off, with an important CPU-runtime penalty. The RGB extension verifies the mechanics of authenticated, exact recovery in positive-capacity cases, but its coverage on the tested corpus remains limited. Further work should prioritize a third-party security review, improved RGB feasibility, and end-to-end runtime optimisation.

## References

[1] X. Zhang, “Reversible data hiding in encrypted image,” *IEEE Signal Processing Letters*, vol. 18, no. 4, pp. 255–258, 2011, doi: [10.1109/LSP.2011.2114651](https://doi.org/10.1109/LSP.2011.2114651).

[2] K. Ma, W. Zhang, X. Zhao, N. Yu and F. Li, “Reversible data hiding in encrypted images by reserving room before encryption,” *IEEE Transactions on Information Forensics and Security*, vol. 8, no. 3, pp. 553–562, 2013, doi: [10.1109/TIFS.2013.2248725](https://doi.org/10.1109/TIFS.2013.2248725).

[3] P. Puteaux and W. Puech, “An efficient MSB prediction-based method for high-capacity reversible data hiding in encrypted images,” *IEEE Transactions on Information Forensics and Security*, vol. 13, no. 7, pp. 1670–1681, 2018, doi: [10.1109/TIFS.2018.2799381](https://doi.org/10.1109/TIFS.2018.2799381).

[4] X. Wang et al., “High-capacity reversible data hiding in encrypted images based on MSB sharing and overlapping sawtooth partition,” *Journal of King Saud University Computer and Information Sciences*, vol. 38, article 24, 2026 (first published online 12 Dec. 2025), doi: [10.1007/s44443-025-00238-5](https://doi.org/10.1007/s44443-025-00238-5).

[5] G. Zhou et al., “Reversible data hiding in encrypted images based on bit-plane classification and adaptive group coding,” *IET Image Processing*, vol. 20, no. 1, e70310, 2026, doi: [10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310).

[6] N. N. Hung, T. L. Cao and V. A. Pham, “High-capacity reversible data hiding in encrypted images using D4-symmetry bidirectional pixel shifting and context-aware recovery,” *Applied Sciences*, vol. 16, no. 20, article 10343, 2026, doi: [10.3390/app162010343](https://doi.org/10.3390/app162010343).

[7] H. N. Tram and T.-S. Nguyen, “Reversible data hiding in encrypted images based on overlapping block partitioning and shared-MSB encoding,” *CTU Journal of Innovation and Sustainable Development*, vol. 18, Special Issue: ISDS, pp. 1–10, 2026, doi: [10.22144/ctujoisd.2026.049](https://doi.org/10.22144/ctujoisd.2026.049).

[8] M. Dworkin, *Recommendation for Block Cipher Modes of Operation: Methods and Techniques*, NIST Special Publication 800-38A, 2001, doi: [10.6028/NIST.SP.800-38A](https://doi.org/10.6028/NIST.SP.800-38A).

[9] H. Krawczyk, M. Bellare and R. Canetti, “HMAC: Keyed-Hashing for Message Authentication,” RFC 2104, IETF, 1997, [https://www.rfc-editor.org/rfc/rfc2104](https://www.rfc-editor.org/rfc/rfc2104).

[10] H. Krawczyk and P. Eronen, “HMAC-based Extract-and-Expand Key Derivation Function (HKDF),” RFC 5869, IETF, 2010, [https://www.rfc-editor.org/rfc/rfc5869](https://www.rfc-editor.org/rfc/rfc5869).


[11] S. Yi and Y. Zhou, “Parametric reversible data hiding in encrypted images using adaptive bit-level data embedding and checkerboard based prediction,” *Signal Processing*, vol. 150, pp. 171–182, 2018, doi: [10.1016/j.sigpro.2018.04.016](https://doi.org/10.1016/j.sigpro.2018.04.016).

[12] P. Ping, J. Huo and B. Guo, “Novel asymmetric CNN-based and adaptive mean predictors for reversible data hiding in encrypted images,” *Expert Systems with Applications*, vol. 246, article 123270, 2024, doi: [10.1016/j.eswa.2024.123270](https://doi.org/10.1016/j.eswa.2024.123270).

[13] Z. Cheng, K. Chen and Q. Guan, “Reversible data hiding in encrypted images based on pixel-level masked autoencoder and polar code,” *Signal Processing*, vol. 226, article 109664, 2025, doi: [10.1016/j.sigpro.2024.109664](https://doi.org/10.1016/j.sigpro.2024.109664).

## Figure captions and source files

All nine plots are editable SVGs in the sibling `figures/` directory. The plotted values come from the committed CSV tables.

1. **Figure 1.** Positive-net coverage in the matched grayscale predictor comparison. All predictor implementations use the common step-4 / 16-phase grid; the histogram-shift reference is omitted from the direct comparison because it uses a different embedding path.
2. **Figure 2.** Mean candidate MAE in the matched grayscale predictor comparison. Lower values indicate lower prediction error; CNN v3 is the strongest CNN on this metric.
3. **Figure 3.** Cluster-bootstrap intervals for the positive-net coverage difference (v4 minus each comparator), resampling the 29 curator-defined correlation clusters.
4. **Figure 4.** Number of native RGB images with positive signed net capacity under each tested spatial/cross-channel blend, out of 51.
5. **Figure 5.** Mean signed RGB net bpp conditional on encrypted bootstrap-directory fit. The sample count is shown because the denominators differ substantially.
6. **Figure 6.** Mean full-map predictor runtime for the 512×512 CPU benchmark. The horizontal axis is in milliseconds.
7. **Figure 7.** CNN parameter count against measured predictor runtime for the five CNN checkpoints.
8. **Figure 8.** Descriptive grayscale v4 positive-net coverage by broad corpus label and image resolution.
9. **Figure 9.** Mean per-image gain from adaptive selection among 24 ordered RGB channel-phase assignments relative to the fixed assignment (0,1,2), conditional on a fitted bootstrap directory.

## Submission checklist

- [ ] Verify complete author details, affiliations, funding and declarations.
- [ ] Resolve the final intended title and journal/conference scope.
- [ ] Verify all bibliographic fields against publisher records and add any further primary references.
- [ ] Replace figure placeholders with the final figure set and validate image licensing.
- [ ] Check every table cell against the committed CSV and the immutable workflow artifacts.
- [ ] Have the custom cryptographic construction independently reviewed.
- [ ] Add end-to-end active-protocol runtime/memory results and a fuller RGB comparison if these are retained as major claims.
- [ ] Obtain a human subject-matter review before submission.
