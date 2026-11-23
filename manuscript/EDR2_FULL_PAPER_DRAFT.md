# Context-Invariant Prediction and Overhead-Aware Phase Selection for Reversible Data Hiding in Encrypted Images

**Full manuscript working draft — 23 November 2026**

**Authors:** [Insert author names and affiliations]  
**Corresponding author:** [Insert email]  
**Target venue:** To be selected after technical and reference review

---

## Abstract

Prediction-based reversible data hiding in encrypted images (RDHEI) requires the encoder and decoder to reproduce compatible prediction contexts after embedding has modified the cover. This paper presents EDR2, a reserve-room-before-encryption grayscale RDHEI protocol built around a frozen residual convolutional neural network (CNN) with a masked 3 × 3 receptive field. The candidate centres are selected from one of four maximum-density step-2 lattice phases. Because the predictor masks each candidate centre and no other candidate centre occurs in its 3 × 3 neighbourhood, arbitrary writes to the selected carrier centres do not alter the predictor input at any candidate. The content owner evaluates the four phases independently and selects the one with the largest signed net payload after accounting for the compressed label directory, header and authentication-tag carrier opportunity cost, and the backup required to restore the bootstrap bytes. The selected phase is discovered from the authenticated in-band header location rather than transmitted in a sidecar.

The EDR2 implementation uses a nonce-derived, domain-separated key hierarchy, AES-256-CTR for encryption, and HMAC-SHA256 for packet integrity. Authentication is checked before directory decompression and CNN inference. The receiver requires the marked encrypted image, a 32-byte master key, a 128-bit nonce, and the preinstalled protocol decoder and frozen checkpoint. On a hash-pinned corpus of 243 native 8-bit grayscale USC-SIPI images, EDR2 produced positive signed net capacity for 163 images (67.1%). Six payload-size trials for each accepted image yielded 978/978 exact image and payload recoveries. Mean usable and pooled usable rates were 0.1432 and 0.0955 bpp, respectively. Same-corpus native-protocol reproductions of Multi-MSB+Huffman and corrected PPMR achieved substantially higher usable rates; these are contextual native-protocol comparisons, not a common-packet-cost leaderboard. A separate matched-grid predictor study found that the 5 × 5 no-weighted-loss checkpoint outperformed the selected 3 × 3 checkpoint on prediction MAE and positive-net coverage. EDR2 therefore makes a synchronization and protocol-composition contribution, not a claim that its CNN is the most accurate predictor or that it achieves state-of-the-art capacity. Runtime measurements also show a material computational penalty relative to classical predictors.

**Keywords:** reversible data hiding; encrypted images; prediction-context invariance; CNN predictor; safe lattice; reserve room before encryption; net payload; authenticated in-band metadata; exact recovery.

---

## 1. Introduction

Reversible data hiding (RDH) embeds auxiliary information in a digital object while preserving the ability to reconstruct the original object exactly after extraction. In image applications, reversibility is important when the cover carries evidential, medical, scientific, or archival value. Reversible data hiding in encrypted images (RDHEI) combines this requirement with image confidentiality: an owner encrypts an image, a data hider embeds a payload into the encrypted representation, and an authorised receiver extracts the payload and restores the original image without distortion.

RDHEI methods differ in the order in which room is created and encryption is applied, in the information available to the hider, and in whether payload extraction and image recovery are separable. Early encrypted-image RDH demonstrated that data can be embedded in encrypted images, while reserve-room-before-encryption (RRBE) designs create reversible room before encryption so that a hider can operate without access to the original image [1], [2]. Prediction-error methods, bit-plane methods, and compressed auxiliary maps have since been used to increase payload [3]–[9].

A recurring technical difficulty in prediction-based schemes is prediction-context synchronisation. An encoder may predict a pixel using a local neighbourhood and then modify that pixel or nearby pixels while embedding. If a later decoder applies the same predictor to a modified neighbourhood, the prediction may differ. A changed prediction can alter the prediction error, the selected label, the number of replaceable bits, or the admissible reconstruction interval. Exact reversibility therefore requires more than using the same trained model: it requires the encoder and decoder to evaluate the model on compatible inputs.

This paper addresses that problem for a fixed local predictor. EDR2 uses a residual CNN operating on 3 × 3 patches whose centre sample is explicitly masked. Candidate carrier centres lie on one of four step-2 phases. Distinct centres in a phase are separated by at least two pixels in the Chebyshev metric. Consequently, no other mutable candidate lies in a candidate's 3 × 3 receptive field, while the candidate's own value is removed by centre masking. The resulting property is a deterministic input-invariance condition for the selected CNN evaluation procedure: modifying candidate-centre values cannot alter the predictor patch supplied at any candidate.

The geometry is combined with an overhead-aware selection rule. Each of the four phases has the same maximum candidate density for supported even-sized images, but it can produce a different prediction-error sequence and compressed label directory. The content owner therefore evaluates all phases and selects the one with the largest signed net payload after charging the actual bootstrap carrier cost and the backup needed to restore bootstrap bytes. This matters because a geometrically dense carrier set is not equivalent to a positive usable payload: directory and bootstrap costs can exceed the available replaceable bits.

EDR2 also defines a self-locating, authenticated in-band packet. The encrypted header, encrypted compressed label directory, and HMAC-SHA256 tag are carried at the first candidate positions of the selected phase. The receiver tests the four public phases and accepts exactly one phase whose header framing, authentication tag, and bounded directory representation validate. The phase is therefore implied by the header's carrier location; no separate phase field or prediction-map sidecar is required. The receiver's per-image semantic inputs are the final marked encrypted image, a 32-byte master key, and a 128-bit nonce. The matching decoder, fixed protocol constants, and frozen CNN checkpoint are shared protocol software installed at both ends.

The intended contribution is deliberately narrow. CNN-based prediction in RDHEI, checkerboard-style prediction, bit replacement, MSB prediction, compressed label maps, and authenticated RDHEI have all appeared in prior literature [3]–[12]. EDR2 does not claim any of those components as independently novel. Instead, it provides a specific, implemented composition of (i) a formal local non-interference condition for a centre-masked radius-one CNN predictor, (ii) four maximum-density step-2 phases evaluated by signed net payload, and (iii) authenticated in-band phase discovery within a receiver-side external-image-side-information-free RRBE protocol.

The empirical results are intentionally reported without a superiority claim. EDR2 achieves a relatively low net payload compared with the reproduced Multi-MSB+Huffman and corrected PPMR implementations. Its CNN-3×3 predictor also has higher MAE and fewer positive-net images than the 5×5 no-weighted-loss ablation in a separate matched-grid study. Those outcomes are retained in the analysis. They motivate a clear interpretation: the value of EDR2 is its synchronization rule and protocol construction, not a demonstrated improvement in payload capacity or prediction accuracy over the strongest tested alternatives.

The paper makes the following contributions:

1. **A protocol-specific non-interference result.** We formalise why a centre-masked 3 × 3 predictor receives unchanged inputs before and after arbitrary modifications to the selected carrier centres on a step-2 phase.
2. **A maximum-density four-phase construction.** We define four parity-offset phases, prove their candidate count for even image dimensions under the stated separation constraint, and use all four as alternatives in owner-side preparation.
3. **Signed net-capacity phase selection.** We express the net payload after the compressed directory, bootstrap opportunity cost, and original-byte backup, and choose the phase that maximises this quantity.
4. **A receiver-side self-locating packet.** We specify an encrypted header, encrypted label directory, phase-bound HMAC tag, nonce-derived key hierarchy, and receiver procedure that authenticates before decompression and inference.
5. **A reproducible evaluation with explicit limits.** We report full-corpus capacity, exact recovery, predictor ablations, native-protocol external reproductions, parser robustness tests, runtime, and memory measurements, while separating experiments that use different candidate grids or packet assumptions.

The remainder of the paper is organised as follows. Section 2 reviews RDH/RDHEI, prediction, and authentication literature. Section 3 defines the problem and formal properties. Section 4 describes the EDR2 protocol. Section 5 describes experimental methodology. Section 6 reports results. Section 7 discusses interpretation, security, and limitations. Section 8 concludes the paper.

## 2. Related work

### 2.1 RDH and RDHEI architectures

Zhang introduced a reversible data-hiding construction for encrypted images, helping establish RDHEI as a distinct problem in which confidentiality, payload extraction, and exact image recovery must coexist [1]. Ma et al. proposed reserving room before encryption, creating a design in which the owner performs reversible preprocessing and the hider subsequently inserts data into the encrypted image [2]. The RRBE organisation is directly relevant to EDR2: the owner constructs the reversible carrier and the independent hider does not need the original image or image-encryption key.

RDHEI methods are often categorised by whether room is created before or after encryption, and by the operations available to the receiver. Puteaux et al. survey the first twelve years of the field and discuss representative families and design choices [7]. This taxonomy is important when comparing rates: two papers may both report bpp while using different encryption order, receiver assumptions, side information, recovery contracts, and overhead conventions. A rate should not be treated as directly comparable unless these details are aligned.

### 2.2 Prediction, checkerboard sampling, and MSB replacement

Prediction is used to exploit spatial correlation and to derive a compact representation of the original image or its prediction errors. Yi and Zhou proposed adaptive bit-level embedding with checkerboard-based prediction [3]. Their checkerboard mechanism predicts a substantial subset of pixels from the remaining subset. It establishes that checkerboard partitioning and bit replacement are prior art in encrypted-image data hiding. Their parametric method also distinguishes fully reversible operation from higher-rate configurations that permit some image distortion; rates obtained in the latter regime should not be compared with exact-recovery RDHEI as though the recovery guarantees were identical.

Puteaux and Puech proposed an MSB prediction-based method for high-capacity RDHEI [4]. Yin et al. introduced multi-MSB prediction with Huffman coding [5]. Yin et al. later proposed pixel prediction with multi-MSB-plane rearrangement (PPMR), using prediction-error structure and rearrangement of bit-plane blocks [6]. These methods demonstrate that prediction, MSB substitution, and compressed auxiliary information are established approaches. They are also the basis for the external native-protocol reproductions reported in Section 6.

Ren et al. combined multi-prediction and adaptive Huffman encoding [8], while Sui et al. described hybrid prediction and Huffman coding [9]. These works further establish compressed prediction labels and hybrid predictor selection as existing strategies. The design objective of EDR2 is different: rather than claiming a new predictor family, it imposes a specific condition on where mutable carrier centres may occur relative to a fixed local predictor's receptive field.

### 2.3 Learned and masked predictors

The use of convolutional neural networks in RDHEI is not new. Ping et al. proposed asymmetric CNN-based and adaptive-mean predictors in a two-stage prediction and embedding framework [10]. Cheng et al. proposed a pixel-level masked autoencoder with polar coding for a vacating-room-after-encryption setting [11]. These works make it inappropriate to claim novelty merely because EDR2 uses a CNN or masks part of a prediction input.

The relevant distinction is narrower. EDR2's guarantee is geometric and protocol-specific: the predictor's receptive field is radius one, the candidate centre is explicitly masked, and candidate centres are spaced so that no other mutable centre lies in the remaining receptive-field positions. The same frozen checkpoint and inference procedure are used by owner and receiver. This provides a simple condition under which the predictor input is unchanged by carrier writes. The claim is not that masked prediction, checkerboard partitioning, or learned prediction is new in general.

### 2.4 Authentication and integrity in RDHEI

Reversibility does not by itself guarantee integrity. Ren et al. proposed an RDHEI scheme that combines prediction-error compression with authentication of image content and embedded data [12]. Their work demonstrates that authentication is already an active component of RDHEI research. EDR2 therefore does not claim HMAC, authentication, or authenticated image recovery as novel primitives.

EDR2 uses standard cryptographic constructions in a particular packet organisation. HKDF-SHA256 derives distinct keys for image encryption, header stages, directory encryption, payload encryption, and authentication [19]. AES-256-CTR encrypts the image and protocol fields, while HMAC-SHA256 authenticates the marked packet [18], [20]. CTR mode alone does not provide integrity; the HMAC is a separate requirement. The protocol binds the selected phase and image dimensions into the authentication input and verifies the tag before directory decompression or CNN inference. The hider is authorised and receives a key capability that includes authentication authority; the design does not claim resistance to a malicious authorised hider.

### 2.5 Recent capacity-oriented RDHEI methods

Recent work continues to explore different ways of increasing payload. Wang et al. describe MSB sharing with overlapping sawtooth partitioning [13]. Zhou and Li et al. propose bit-plane classification and adaptive group coding [14]. Peng et al. combine two-stage bit-plane compression with block rearrangement and ciphertext-policy attribute-based recovery authorisation [15]. Hung et al. use D4-symmetry bidirectional pixel shifting and context-aware recovery [16]. Tram and Nguyen describe overlapping block partitioning with shared-MSB encoding [17].

These papers reinforce two points. First, high-capacity RDHEI is an active and competitive area, so EDR2's capacity must be reported in relation to contemporary alternatives rather than in isolation. Second, recent approaches exploit different redundancy sources and protocol structures. EDR2's net-rate results cannot establish general superiority over these methods, and the reproduced external baselines are not exhaustive state-of-the-art comparisons.

### 2.6 Positioning and novelty boundary

Table 1 summarises selected prior work and the principal distinction relevant to EDR2.

| Work | Main mechanism | Relevance to EDR2 | What EDR2 does not claim |
|---|---|---|---|
| Zhang [1] | Early RDH in encrypted images | RDHEI foundation | RDHEI itself is not new |
| Ma et al. [2] | Reserve room before encryption | Owner–hider–receiver separation | RRBE is not new |
| Yi and Zhou [3] | Checkerboard prediction and bit-level embedding | Spatial partitioning and prediction | Checkerboard or bit replacement is not new |
| Puteaux and Puech [4] | MSB prediction | Prediction-guided MSB capacity | MSB prediction is not new |
| Yin et al. [5], [6] | Multi-MSB prediction, Huffman coding, MSB-plane rearrangement | Close capacity-oriented references and reproduced methods | Compressed labels/MSB substitution are not new |
| Ren et al. [8]; Sui et al. [9] | Multi/hybrid prediction and Huffman coding | Prediction and auxiliary-data compression | Multi-prediction/Huffman coding are not new |
| Ping et al. [10] | CNN and adaptive-mean RDHEI predictors | CNN-based RDHEI prior art | CNN use is not new |
| Cheng et al. [11] | Pixel-level masked autoencoder and polar code | Learned masked prediction prior art | Masking or learned image prediction is not new |
| Ren et al. [12] | Prediction-error compression and authentication | Authentication in RDHEI prior art | Authentication is not new |
| [13]–[17] | Recent MSB, bit-plane, overlapping-block, and symmetry methods | Contemporary context for capacity and protocol alternatives | No state-of-the-art superiority claim is made |

The specific research question addressed here is: **under what simple geometric condition can an owner and receiver use the same fixed centre-masked local predictor after arbitrary modifications to the candidate carrier centres, and how can the candidate phase be selected and recovered without external image-dependent side information?** EDR2 provides one concrete answer for a radius-one predictor and even-sized grayscale images. Its empirical results test that construction; they do not prove that the same condition is optimal for other receptive fields, predictor families, image types, or embedding schemes.

## 3. Problem formulation and formal properties

### 3.1 Notation and scope

Let the original image be \(X\in\{0,\ldots,255\}^{H\times W}\). EDR2 currently supports native 8-bit grayscale images with even height and width. It does not resize, crop, or convert colour inputs to grayscale. Images with odd dimensions, RGB channels, or 16-bit samples are outside the core protocol version.

Let \(K\in\{0,1\}^{256}\) be a 32-byte master key and \(V\in\{0,1\}^{128}\) a per-packet nonce. The owner, authorised hider, and receiver share fixed protocol software and a frozen CNN checkpoint. The final receiver inputs specific to one image are the marked encrypted image, \(K\), and \(V\). The authorised hider additionally receives a nonce-specific data-hiding key capability \(K_h\) from the owner through an assumed authenticated confidential key-delivery channel. \(K_h\) is keying material, not an image-dependent map or sidecar.

The owner seeks to reserve enough room to carry a payload \(M\in\{0,1\}^{P}\) while allowing the receiver to reconstruct \(X\) exactly. The hider must not require access to \(X\), the prediction map, the label directory in plaintext, or the image-encryption key.

### 3.2 Four step-2 candidate phases

Define the phase index \(q\in\{0,1,2,3\}\), with offsets

\[
r_q=1+\left\lfloor\frac{q}{2}\right\rfloor,\qquad
c_q=1+(q\bmod 2).
\]

The candidate centres for phase \(q\) are

\[
\mathcal{G}_q =
\left\{(y,x):
y=r_q+2i,\;
x=c_q+2j,\;
1\le y\le H-2,\;
1\le x\le W-2
\right\}.
\]

The one-pixel border ensures that a full 3 × 3 patch exists around every candidate. Coordinates are traversed in row-major order. The four phases differ only in their row and column parity offsets.

For distinct \(a,b\in\mathcal{G}_q\), the coordinate differences are even integers in each dimension and at least one absolute difference is at least two. Therefore

\[
\|a-b\|_\infty \ge 2.
\]

This is the separation condition used below. The centre of each candidate patch is masked before inference.

### 3.3 Proposition 1: predictor-input invariance

**Proposition 1.** Let a predictor input at candidate centre \(a\in\mathcal{G}_q\) consist of the 3 × 3 image patch centred at \(a\), with the centre element replaced by a fixed mask value. Suppose that embedding modifies image samples only at coordinates in \(\mathcal{G}_q\). Then every candidate's masked 3 × 3 predictor input is identical before and after embedding.

**Proof.** Fix any \(a\in\mathcal{G}_q\). The patch support is the Chebyshev radius-one neighbourhood \(B_\infty(a,1)\). The centre sample at \(a\) is replaced by the fixed mask value in both the pre-embedding and post-embedding inputs, so a modification at \(a\) cannot change the predictor input. For any other candidate \(b\in\mathcal{G}_q\), Proposition's phase-separation condition gives \(\|a-b\|_\infty\ge2\); hence \(b\notin B_\infty(a,1)\). No other mutable candidate centre therefore occurs in the remaining eight patch positions. All non-candidate image samples remain unchanged by assumption. Every entry of the masked patch is consequently unchanged. Since \(a\) was arbitrary, the result holds for all candidates. \(\square\)

The proposition is a statement about the predictor's input, not a blanket guarantee of bitwise-identical output across arbitrary hardware and software. EDR2 additionally fixes the checkpoint, CPU inference path, input normalisation, batch protocol, evaluation mode, and rounding rule. Under a numerically compatible execution of that fixed procedure, identical inputs produce identical predictions. Cross-platform floating-point equivalence is not claimed.

### 3.4 Proposition 2: candidate-density bound

**Proposition 2.** On the valid-centre rectangle of an even-sized \(H\times W\) image, any candidate set satisfying pairwise Chebyshev separation of at least two contains at most

\[
C_{\max}=
\left\lceil\frac{H-2}{2}\right\rceil
\left\lceil\frac{W-2}{2}\right\rceil
\]

centres. Each of the four EDR2 phases attains this bound.

**Proof.** Partition the valid-centre rectangle into disjoint 2 × 2 tiles, with boundary handling consistent with the stated ceiling counts. Any two distinct integer coordinates within the same 2 × 2 tile differ by at most one in each dimension, and therefore have Chebyshev distance at most one. Such a pair would violate the separation condition. Each tile can contain at most one candidate, giving the bound. Each parity phase selects one coordinate from every corresponding complete tile and attains the bound for even \(H,W\). For a 512 × 512 image, each phase contains \(255\times255=65{,}025\) candidate centres, or approximately 24.81% of all image pixels. \(\square\)

This is a geometric candidate-count bound only. It is not a lower bound on usable payload and does not imply that a positive net payload can be carried after directory and bootstrap costs.

### 3.5 Prediction, labels, and exact reconstruction

The active EDR2 checkpoint is a frozen residual CNN with a 3 × 3 input patch and 32 feature channels. Its centre sample is set to zero after normalisation. The owner and receiver use the same checkpoint, CPU inference implementation, evaluation mode, and deterministic nearest-even rounding. Let the rounded prediction at candidate \(i\) be \(p_i\), and let

\[
e_i=|X_i-p_i|.
\]

The allocation function maps each error to a tuple

\[
a(e_i)=(n_i,\ell_i,u_i),
\]

where \(n_i\) is the number of replaceable most-significant bits and \([\ell_i,u_i]\) is the admissible error interval used for recovery. The active codebook contains 15 distinct tuples, ordered lexicographically:

| Class | \(n\) | \(\ell\) | \(u\) |
|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 |
| 1 | 0 | 64 | 64 |
| 2 | 1 | 32 | 32 |
| 3 | 1 | 65 | 127 |
| 4 | 2 | 16 | 16 |
| 5 | 2 | 33 | 63 |
| 6 | 3 | 8 | 8 |
| 7 | 3 | 17 | 31 |
| 8 | 4 | 4 | 4 |
| 9 | 4 | 9 | 15 |
| 10 | 5 | 2 | 2 |
| 11 | 5 | 5 | 7 |
| 12 | 6 | 1 | 1 |
| 13 | 6 | 3 | 3 |
| 14 | 7 | 0 | 0 |

One four-bit label is stored per candidate. Two labels are packed into one byte, high nibble first; an unused final low nibble is zero. The packed directory is compressed using zlib level 9 only when the compressed representation is strictly shorter than the raw packed representation.

For a candidate whose low-bit residue is \(s\), whose prediction is \(p\), and whose label represents \((n,\ell,u)\), the decoder considers

\[
\mathcal{R}(s,p,n,\ell,u)=
\left\{v\in\{0,\ldots,255\}:
v\equiv s\pmod{2^{8-n}},
\quad
\ell\le |v-p|\le u
\right\}.
\]

The active allocation is valid only when this set contains exactly one value, namely the original sample. The implementation's exhaustive finite-domain check covers all \(256^2=65{,}536\) original/prediction pairs and 396,032 payload words with positive allocation, with zero reported mapping failures. The allocation count is not globally monotone at every boundary; the correctness claim is the finite-domain uniqueness property, not monotonicity.

### 3.6 Signed net-capacity accounting

For one candidate phase, let \(C\) be the candidate count and define the gross number of ordinary replaceable slots as

\[
G_0=\sum_{i=0}^{C-1}n_i.
\]

Let \(L\) be the encrypted directory length in bytes. The bootstrap occupies

\[
H_b=20+L+32=52+L
\]

candidate bytes: a 20-byte header, the encrypted directory, and a 32-byte HMAC-SHA256 tag. The ordinary carrier slots that would have been available at these first \(H_b\) candidates are forfeited:

\[
F=\sum_{i=0}^{H_b-1}n_i.
\]

The remaining ordinary carrier stream contains \(S=G_0-F\) bits. The owner must also preserve the original \(H_b\) bootstrap candidate bytes, requiring

\[
B=8H_b
\]

backup bits. The first \(B\) bits of the remaining ordinary stream store this backup; the rest carry the user payload. The signed net capacity is therefore

\[
N=S-B=G_0-F-8H_b.
\]

A phase is rejected if \(N\le0\). The signed net rate and usable net rate are

\[
R_{\mathrm{signed}}=\frac{N}{HW},
\qquad
R_{\mathrm{usable}}=\frac{\max(0,N)}{HW}.
\]

The metadata's physical in-band storage size is \(8H_b\) bits. Its opportunity cost in the ordinary carrier budget is \(F\), because the bootstrap candidates no longer contribute their normal \(n_i\) slots. The original bootstrap-byte backup is a separate cost \(B=8H_b\). These quantities must not be counted twice: the net equation is \(N=G_0-F-B\), not \(G_0-F-B-8H_b\).

The owner evaluates each phase independently, recomputing its prediction labels, compressed directory, bootstrap length, and net capacity. It selects

\[
q^\star=\arg\max_{q\in\{0,1,2,3\}} N_q,
\]

with the lowest phase index used to break ties. The owner rejects the image if \(\max_qN_q\le0\). The phase identifier is implicit in the location of the encrypted header and is not stored in an additional sidecar or charged as a separate phase field.

## 4. EDR2 protocol

### 4.1 Parties and information flow

EDR2 separates the content owner, independent data hider, and receiver.

| Party | Per-image inputs | Operations |
|---|---|---|
| Content owner | Original grayscale image \(X\), master key \(K\), unique nonce \(V\), installed frozen CNN | Evaluates phases, constructs labels and directory, selects phase, reserves room, preserves bootstrap bytes, encrypts the reserved image, derives the hider capability |
| Independent data hider | Reserved encrypted image, user payload \(M\), derived data-hiding capability \(K_h\) | Authenticates and parses bootstrap, inserts encrypted payload bits in the encrypted domain, finalises header and authentication tag |
| Receiver | Final marked encrypted image, \(K\), \(V\), installed decoder and checkpoint | Discovers phase, authenticates, extracts payload, decrypts, restores backup, reconstructs exact original image |

The owner sends the reserved encrypted image and the nonce-specific \(K_h\) to the authorised hider. The hider never receives \(K\), the image-encryption key, the original image, or the CNN prediction map. The protocol assumes secure, authenticated delivery of \(K_h\). The receiver derives the necessary keys from \(K\) and \(V\) and does not need the hider capability as a separate input.

### 4.2 Key derivation and encryption domains

Let \(s\) be the 16-byte big-endian encoding of nonce \(V\). EDR2 derives a root and separate image/data-hiding key domains using HKDF-SHA256:

\[
K_{\mathrm{root}}=\mathrm{HKDF}(K,s,\texttt{EDR2/master-root},32),
\]
\[
K_{\mathrm{img}}=\mathrm{HKDF}(K_{\mathrm{root}},\epsilon,\texttt{EDR2/image-encryption},32),
\]
\[
K_h=\mathrm{HKDF}(K_{\mathrm{root}},\epsilon,\texttt{EDR2/data-hiding-master},32).
\]

From \(K_h\), distinct 32-byte keys are derived for bootstrap header encryption, final header encryption, directory encryption, payload encryption, and authentication. Each domain uses a distinct HKDF context string. This prevents the hider, which receives \(K_h\), from deriving \(K_{\mathrm{img}}\).

AES-256-CTR is used under the derived per-packet keys. The protocol requires that a nonce never be reused with the same master key. Reuse would repeat derived keys and CTR keystreams and is prohibited. CTR encryption by itself is malleable and is not treated as an integrity mechanism; integrity is provided separately by HMAC-SHA256 [18]–[20].

### 4.3 In-band packet structure

The fixed 20-byte header uses the big-endian field layout shown in Table 2.

| Field | Bytes | Meaning |
|---|---:|---|
| Magic | 4 | ASCII protocol marker EDR2 |
| Directory codec | 1 | 0 = raw packed labels; 1 = zlib-compressed labels |
| Reserved | 3 | Must decrypt to three zero bytes |
| Directory length | 4 | Encrypted directory length \(L\) |
| Payload length | 8 | User payload length in bits \(P\) |

The header is encrypted in-band using AES-256-CTR. The owner writes a bootstrap header with \(P=0\) under the bootstrap-header key. The authorised hider validates the bootstrap, inserts the user payload, and writes a final header under the separate final-header key. The separation avoids using the same CTR keystream for the two header states.

The next \(L\) candidate bytes contain the encrypted packed label directory. The following 32 candidate bytes contain the HMAC-SHA256 tag. The bootstrap length is \(H_b=20+L+32\) bytes. The payload length and directory length are in the encrypted header; they are not external per-image fields.

### 4.4 Authentication and phase discovery

For a candidate phase, the tag input contains the big-endian image dimensions, the one-byte phase index, and the complete row-major marked-image bytes with that phase's 32 tag-carrier bytes set to zero. The HMAC key is derived in its own authentication domain. Binding the phase prevents the same valid packet from being interpreted under a different candidate lattice.

The receiver or hider tests the four public phase-specific header locations. For each candidate phase it:
1. decrypts only the fixed-size header;
2. checks the protocol magic, codec identifier, reserved bytes, and directory/tag bounds;
3. reads the tag carrier and verifies HMAC-SHA256;
4. only after successful authentication, decrypts and decompresses the bounded label directory;
5. validates directory length, codebook identifiers, and padding.

Exactly one phase must pass these checks. Zero valid phases indicates an invalid or modified packet; more than one valid phase is rejected as ambiguous. Directory decompression and CNN inference occur only after successful authentication. The authenticated header location therefore enables phase discovery without transmitting a separate phase field.

The authorised hider holds the authentication capability and can calculate a new valid tag. EDR2 consequently protects against modification by parties lacking the authentication key but does not claim resistance to a malicious authorised hider. This trust assumption is explicit.

### 4.5 Owner reservation

For each image, the owner performs the following operations:

1. Validate native 8-bit grayscale mode and even dimensions.
2. Load the frozen residual CNN-3×3 in evaluation mode and evaluate the four candidate phases independently. Inference batches are processed phase by phase using the fixed batch size and preprocessing.
3. For each phase, compute prediction errors, allocation labels, packed label directory, optional zlib compression, bootstrap length \(H_b\), forfeited ordinary slots \(F\), backup cost \(B\), and signed net capacity \(N_q\).
4. Select the phase with the greatest \(N_q\), using the lowest phase index for ties. Reject if the maximum is non-positive.
5. Preserve the original \(H_b\) candidate bytes as \(B=8H_b\) bits.
6. Write the backup followed by zero payload-reservation bits into the remaining ordinary candidate slots. Set the bootstrap candidate bytes to zero and form the reserved plaintext image.
7. Encrypt the reserved image under \(K_{\mathrm{img}}\), encrypt the label directory under its directory key, install the bootstrap header and directory, and seal the reserved packet with HMAC.
8. Deliver the reserved encrypted image and \(K_h\) to the authorised hider.

The user payload is not an input to the owner-side reservation step. The room is prepared before the hider receives the payload.

### 4.6 Encrypted-domain hider

The hider derives its domain-specific subkeys from \(K_h\), locates the bootstrap phase, checks the bootstrap authentication tag, decrypts and decompresses the directory, and reconstructs the ordinary carrier positions. It verifies that the supplied payload length does not exceed the reserved net capacity. The payload is encrypted under its dedicated payload key and written into the designated ordinary slots. The hider then writes the final header, updates the phase-bound authentication tag, and returns the final marked encrypted image.

The hider operates on the reserved encrypted image and does not decrypt the original image or the image-encryption domain.

### 4.7 Receiver extraction and exact image recovery

The receiver derives the image and data-hiding key domains from \(K,V\), discovers exactly one valid phase, verifies the HMAC, and only then decrypts and decompresses the directory. It reconstructs the carrier positions, extracts and decrypts the payload stream, and checks padding bits. It then restores the known-zero reservation ciphertext positions before image decryption, recovers the saved bootstrap bytes from the backup stream, and reconstructs each modified candidate sample using the label interval and preserved low-bit residue. The receiver rejects a candidate if its admissible reconstruction set contains zero or multiple values. Finally, it restores the original bootstrap bytes and returns the recovered image and extracted payload.

## 5. Experimental methodology

### 5.1 Frozen implementation and checkpoint

All final evaluation experiments used frozen checkpoints; no retraining or fine-tuning was performed during the reported evaluation. The EDR2 checkpoint is v4_patch3.pth, a residual CNN-3×3 with 46,881 parameters. Its SHA-256 is:

\[
\texttt{a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d}.
\]

The model implementation contains two 3 × 3 convolutional blocks with 32 channels, batch normalisation and ReLU, a 1 × 1 residual projection, and a flattened regression head with 128 hidden units and a scalar output. The final checkpoint is frozen and loaded in evaluation mode. Prediction patches are normalised to float32, the centre is masked, and output values are rounded with the protocol's nearest-even convention. The EDR2 inference path uses CPU execution, four PyTorch threads, and batches of 2,048 patches.

**Training-provenance item to complete before submission:** the published artifact bundle records the checkpoint hash and that no training occurred during evaluation, but the final training-manifest file for this checkpoint is not present in the inspected evidence bundle. Before submission, attach the training manifest that records the source image inventory and hashes, image-level train/validation split, exact optimizer/loss/epoch configuration, and best validation checkpoint selection. Do not infer those run-specific details solely from default arguments in the training script.

### 5.2 Grayscale corpus and provenance

The grayscale evaluation uses 243 distinct native 8-bit grayscale USC-SIPI images. The corpus preparation process retained file and decoded-pixel SHA-256 hashes, accepted only native grayscale mode-L inputs, and removed two files with duplicate decoded pixel arrays. Five nonconforming inputs were skipped. The final curation classification is 239 natural-labelled images and four constructed texture mosaics. The dataset spans 256 × 256 (62 images), 512 × 512 (152 images), and 1024 × 1024 (29 images). It includes 29 source-family/correlation clusters; rotated texture variants and related sequence frames are not treated as independent photographs.

An earlier matched-run manifest used a different natural/constructed label assignment (232/11), but the final curation manifest reclassified seven texture items while preserving the same 243 decoded pixel arrays and the 29 correlation clusters. The final stratification was recomputed under the canonical 239/4 classification. Capacity calculations are per-image and are unaffected by this metadata-only reclassification. Statistical uncertainty is estimated at the correlation-cluster level rather than by treating all 243 images as independent observations.

### 5.3 Capacity metrics and aggregation

For image \(j\), let \(N_j\) be signed net payload and \(P_j=H_jW_j\) its pixel count. We report:

- positive-net coverage: number of images for which \(N_j>0\), divided by 243;
- signed net bpp: \(N_j/P_j\), retaining negative values;
- usable net bpp: \(\max(0,N_j)/P_j\);
- mean usable bpp: arithmetic mean of per-image usable rates;
- pooled usable bpp: \(\sum_j\max(0,N_j)/\sum_jP_j\);
- pooled signed bpp: \(\sum_jN_j/\sum_jP_j\).

The mean and pooled quantities answer different questions and are both reported. Non-positive cases are retained in the coverage denominator and have zero usable rate. The positive-image mean is not substituted for the corpus mean. Confidence intervals use cluster-level resampling over the 29 provenance/correlation clusters. For paired native-protocol comparisons, resampling preserves matched image identities within each cluster.

### 5.4 Exact recovery tests

For every positive-net EDR2 image, six payload cases were embedded and independently received: empty, one-bit, short, partial, near-maximum, and full measured-capacity payloads. Image recovery and payload extraction were checked independently against the original image and supplied payload. The native grayscale ledger contains 978 receiver trials across 163 positive-net images. Exhaustive label-map tests cover every 8-bit prediction/original pair and all valid payload words under positive allocation.

### 5.5 Predictor comparison

The predictor-only comparison deliberately uses a different common grid from native EDR2. All predictor alternatives use a step-4 lattice with 16 implicit phases and a border of three pixels, allowing the largest tested 7 × 7 predictor and the classical predictor contexts to use the same candidate positions. This experiment assesses predictor-dependent MAE and net-positive coverage; it is not the native step-2/four-phase EDR2 capacity experiment.

The compared methods are MED, GAP, a simplified CALIC-style predictor, and five frozen CNN checkpoints: 5 × 5 residual, 5 × 5 without residual connection, 5 × 5 without weighted loss, the proposed 3 × 3 residual checkpoint, and 7 × 7 residual. The CALIC implementation is a simplified predictor baseline, not a full canonical CALIC codec.

### 5.6 External native-protocol reproductions

Multi-MSB+Huffman and PPMR were reproduced on the same 243 decoded source images and pixel arrays as EDR2. Their native protocol operations, payload definitions, and overhead conventions were retained as far as possible. The Multi-MSB+Huffman reference was pinned to the upstream implementation commit 1e69ae2713dededa56595ff09255cda1e17896d9. PPMR required four narrow compatibility corrections in the private reproduction: separate lower-level control flow for bit planes 7 and 8 in encoder/decoder paths and corrected active-plane ordering in the uniform/non-uniform block extraction paths. The resulting method is therefore labelled **corrected PPMR**, not an unmodified run of the upstream implementation.

These runs are matched by corpus identity, not by identical packet cost, encryption order, authentication model, receiver input, or metadata accounting. They are presented as native-protocol context, not as a same-security or same-packet-cost leaderboard.

### 5.7 Security and parser robustness tests

The regression suite exercises four-phase header discovery, wrong-key and wrong-nonce rejection, header mutations, directory mutations, tag mutations, payload-carrier mutations, non-carrier mutations, malformed codec identifiers, reserved-field validation, invalid lengths, malformed authenticated compressed data, and deterministic seeded mutations. The finite-domain reconstruction mapping is exhaustively enumerated. A 20,000-input coverage-guided parser fuzz campaign using Atheris reported no crashes, with 121 coverage counters and 188 feature counters. These are implementation robustness tests; they are not a formal security proof or independent cryptographic certification.

### 5.8 Runtime and memory methodology

Three complementary timing records are reported with their execution scopes kept separate.

First, a predictor-only comparison used a deterministic synthetic 512 × 512 grayscale input, five warm-ups, and ten measured CPU repeats. The original candidate-patch extraction path used four PyTorch threads and measured full-map CNN-3×3 prediction at 708.479 ms, compared with 3.826 ms for MED. This benchmark permits a controlled timing comparison with the classical predictors, but it predates the later vectorised patch-extraction optimisation.

Second, the optimisation was validated without changing the checkpoint or rounded predictions. The vectorised `sliding_window_view` patch extractor was checked against the original slice-and-stack implementation; the extracted arrays were identical. The optimisation sweep also compared predictions with the original four-thread, batch-2048 reference and reported zero rounded-prediction mismatches for compatible settings. The selected active configuration uses two CPU threads, batch size 2,048, and vectorised patch extraction. The optimisation change is recorded at commit `dceed5cbb3ec4b0e0b15cf7eb559aa58d50689b7` on the EDR2 runtime-optimisation branch.

Third, the updated single-image E2E benchmark used USC-SIPI 5.2.08.tiff, a 512 × 512 native grayscale image, the unchanged checkpoint SHA-256, two warm-ups, and ten measured CPU repeats with the model resident. It used 39,655 payload bits (0.151272 bpp) at full measured net capacity for each iteration, with ten distinct nonces and exact image and payload recovery in all ten trials. The in-memory benchmark includes preparation, reservation/encryption, encrypted-domain embedding, authentication, extraction, and recovery, but excludes process startup, checkpoint loading, file I/O, and dataset acquisition. RSS was sampled every 5 ms; short-lived transient peaks may be missed.

## 6. Results

### 6.1 Native EDR2 grayscale capacity

The final EDR2 ledger contains 243 image-level capacity records. A positive signed net payload was obtained for 163 images (67.1%); 80 images had non-positive capacity and were rejected. Across all 243 images, mean signed net capacity was 0.110540 bpp and pooled signed capacity was 0.059821 bpp. Mean usable capacity was 0.143222 bpp, while pooled usable capacity was 0.095497 bpp. The median usable rate was 0.047054 bpp, with first and third quartiles of 0 and 0.194965 bpp, respectively.

A cluster-bootstrap 95% interval for mean usable capacity was 0.0614–0.2504 bpp. The corresponding interval for positive-net coverage was 50.2%–82.4%. These intervals are wide, reflecting image-family dependence and substantial heterogeneity across the corpus. In particular, the 1024 × 1024 stratum had 10 positive-net images among 29, while the 512 × 512 stratum had 105 among 152. The 256 × 256 stratum had 18 among 62. These values should not be interpreted as a monotonic resolution trend: source content, label-directory compression, and bootstrap overhead also affect net capacity.

Six payload sizes were tested for each positive-net image. The resulting 978 image/payload receiver trials all reconstructed both the original image and the supplied payload exactly (978/978). This result applies to the accepted positive-net cases and the specified six-payload test design; it does not mean all 243 images carried a positive payload.

### 6.2 Effect of the four-phase selection rule

Each image's four phase capacities were calculated from the same frozen predictor and protocol accounting. The selected phase was the maximum-net phase, with deterministic lowest-index tie-breaking. The selection gain is image-dependent because the phase changes prediction-error labels, directory compression, and the number of ordinary slots forfeited by the bootstrap. The geometric candidate count is identical across phases for supported image dimensions; the observed net-rate difference is due to prediction and overhead, not to different theoretical lattice density.

The selected phase is not transmitted explicitly. The receiver tests the four candidate header locations, and exactly one location must pass authenticated framing and bounded directory validation. This is the operational link between adaptive owner-side selection and receiver-side self-location.

### 6.3 Matched-grid predictor comparison

Table 3 reports the separate step-4/16-phase matched-grid predictor study. It is not the native EDR2 step-2/four-phase experiment.

| Predictor | Positive-net images | Candidate MAE |
|---|---:|---:|
| MED | 49/243 | 7.9503 |
| GAP | 58/243 | 7.8408 |
| Simplified CALIC-style | 49/243 | 8.2021 |
| CNN 5 × 5 residual | 138/243 | 4.6324 |
| CNN 5 × 5 without residual | 139/243 | 4.6573 |
| CNN 5 × 5 without weighted loss | 140/243 | 4.6233 |
| CNN 3 × 3 residual (EDR2 checkpoint) | 133/243 | 4.8130 |
| CNN 7 × 7 residual | 140/243 | 4.6882 |

The CNN predictors reduce candidate MAE relative to MED, GAP, and the simplified CALIC-style predictor in this matched-grid experiment. However, the 5 × 5 no-weighted-loss checkpoint achieves the lowest MAE (4.6233) and the highest positive-net coverage among the learned predictors (140/243). The selected 3 × 3 checkpoint achieves 133/243 positive-net outcomes and MAE 4.8130. It is therefore not the strongest predictor by either of those two metrics. It was selected for EDR2 because its smaller patch aligns with the radius-one non-interference condition and because it has a substantially lower parameter and runtime cost than the larger tested CNNs. The choice is a protocol/compute trade-off, not an accuracy-superiority claim.

### 6.4 Same-corpus native-protocol external comparison

Table 4 gives the same-corpus native-protocol comparison reproduced from the final grayscale evaluation. The usable rates retain each method's own protocol and overhead definitions.

| Method | Positive-net images | Mean usable rate (bpp) | Pooled usable rate (bpp) | Exact recovery |
|---|---:|---:|---:|---:|
| EDR2 | 163/243 | 0.1432 | 0.0955 | 978/978 accepted-image trials |
| Multi-MSB+Huffman | 243/243 | 2.0885 | 1.9735 | 243/243 |
| Corrected PPMR | 238/243 | 2.2282 | 2.1182 | 243/243 |

The reproduced methods carry substantially more payload under their native protocol implementations. Paired cluster-bootstrap differences in mean usable rate were 1.945257 bpp for Multi-MSB+Huffman minus EDR2 (95% interval 1.683675–2.241206 bpp) and 2.084953 bpp for corrected PPMR minus EDR2 (95% interval 1.769685–2.403087 bpp). Corrected PPMR exceeded Multi-MSB+Huffman by 0.139695 bpp (95% interval 0.049659–0.213056 bpp).

These differences should be interpreted directly rather than obscured: EDR2's current net payload is much lower than the two reproduced alternatives. At the same time, the comparison does not establish that EDR2 is inferior under an identical security/packet-cost contract, because the methods differ in encryption order, auxiliary information, carrier construction, and authentication assumptions. The evidence supports a transparent same-corpus comparison of native implementations, not a controlled same-packet-cost contest. A future matched-protocol study would be needed to isolate the contribution of the lattice and phase-selection mechanism from all other design differences.

### 6.5 Runtime and memory

The original predictor-only CPU benchmark measured 708.479 ms mean full-map time for CNN-3×3 on the deterministic synthetic 512 × 512 input, compared with 3.826 ms for MED, 11.242 ms for GAP, and 7.257 ms for the simplified CALIC predictor. CNN-3×3 was approximately 185.2 times slower than MED in that original four-thread measurement. The checkpoint contains 46,881 parameters and uses 122,816 multiply-accumulate operations per input patch. Its sampled peak RSS increase in the predictor-only benchmark was 23.90 MiB. This comparison predates vectorised patch extraction and is retained as the predictor-only baseline because the classical predictors were measured under the same original comparison harness.

The later vectorised implementation preserved the extracted patch arrays exactly and produced zero rounded-prediction mismatches against the original reference during the optimisation sweep. The updated active E2E configuration uses two CPU threads, batch size 2,048, and vectorised patch extraction. In the 512 × 512 USC-SIPI E2E benchmark (run #118), EDR2 carried 39,655 bits (0.151272 bpp) in each of ten measured iterations. Mean total pipeline time was 1.114019 s (standard deviation 0.058079 s; median 1.120437 s). Mean stage times were 0.582318 s for prediction and directory preparation, 0.070166 s for reservation and image encryption, 0.043262 s for encrypted-domain embedding and authentication, and 0.418273 s for receiver authentication, extraction, and recovery. All ten image and payload recoveries were exact. Sampled process RSS increased from 392.51 MiB baseline to 403.38 MiB peak, an incremental 10.87 MiB. The earlier, non-vectorised E2E run measured 2.506018 s and a 16.59 MiB sampled RSS increase; it is retained only as a pre-optimisation baseline. The updated result is still one warmed CPU image benchmark, not a corpus-wide latency or multi-resolution scalability result.

### 6.6 Protocol correctness and parser robustness

The regression suite passed the reported EDR2 protocol checks, including phase discovery across all four phases, label padding and reserved-field validation, exact mapping, prepared-state identity checks, and exact receiver recovery. The mapping audit enumerated all 65,536 original/prediction pairs and 396,032 positive-allocation payload words without a reconstruction-uniqueness failure. The 20,000-input Atheris parser campaign reported no crash. These findings provide implementation-level evidence for exactness and parser robustness under the tested inputs. They do not establish resistance to every adversarial input or prove the cryptographic construction secure.

### 6.7 Exploratory RGB extension

A separate RGB research prototype was evaluated on 51 native colour images, four blend settings, and all 24 ordered channel-phase assignments. Depending on blend setting, three, three, five, and seven images achieved positive net capacity. Seven distinct images were positive under at least one tested blend; 44 were not positive in any tested blend. The 162 exact-recovery trials over positive image/blend cases passed. These results are sparse and exploratory. RGB is outside the core EDR2 grayscale protocol and is not used to support the main contribution or the grayscale capacity claims. It should be reported, if retained, in a clearly separated appendix or supplementary document.

## 7. Discussion

### 7.1 What the results establish

The strongest evidence is the combination of a clear local input-invariance argument and a working end-to-end protocol whose in-band packet identifies the chosen phase. The geometric condition is easy to state and independently test. It separates the question "does the prediction input change after carrier writes?" from the question "is the predictor accurate?" The former is controlled by candidate geometry and masking; the latter depends on the learned checkpoint and image content.

The full-corpus ledger and receiver trials show that the implementation can carry payload and recover the original data exactly on the positive-net subset under the stated protocol and test design. The capacity accounting makes negative-net outcomes visible instead of hiding them behind positive-only averages. The authentication mechanism adds an integrity check to the in-band packet and ensures that the receiver does not decompress an unauthenticated directory.

### 7.2 Why capacity remains low

The positive-net rate is limited by several costs. First, only a subset of pixels are candidate centres. Second, each candidate's prediction error determines how many MSBs may be replaced. Third, the compressed label directory occupies candidate bytes that would otherwise provide ordinary replaceable slots. Fourth, the owner preserves the original bootstrap bytes, and the backup stream consumes additional ordinary slots. The phase-selection rule can choose the best of four alternatives, but it cannot remove these structural costs.

The external native-protocol reproductions show that EDR2's current capacity is substantially below Multi-MSB+Huffman and corrected PPMR. This should be acknowledged as a real limitation. The current experiments do not demonstrate that the EDR2 construction is a high-capacity alternative to those methods. Its defensible contribution is instead a formal synchronisation condition and an authenticated self-locating packet with explicit net accounting. If the target journal requires a capacity-focused novelty claim, the current results will be difficult to defend without a new matched comparison or a substantially improved capacity design; this paper should not make that claim.

### 7.3 Predictor selection and compute trade-off

The 5 × 5 no-weighted-loss checkpoint performs better in the matched predictor study, with lower MAE and more positive-net images than the 3 × 3 checkpoint. EDR2 retains the 3 × 3 network because the radius-one receptive field supports the stated step-2 non-interference construction and because the checkpoint has fewer parameters and lower inference time than the 5 × 5 and 7 × 7 alternatives. Even so, the full-map predictor is roughly 185 times slower than MED on the measured CPU input. That cost may be unacceptable for time-sensitive or large-scale deployments. The present experiments do not include GPU serving or a complete multi-resolution runtime study.

### 7.4 Security interpretation

EDR2 uses nonce-derived, domain-separated keys for image encryption, headers, directory, payload, and authentication. The owner and receiver derive these keys from the master key and nonce; the hider receives only the dedicated data-hiding capability. The HMAC covers the marked image, image dimensions, and selected phase, with the tag carrier normalised to zero. A receiver that lacks the authentication key cannot make a modified packet pass the HMAC with feasible probability under the standard MAC assumption.

Several limitations remain. AES-CTR does not itself authenticate ciphertext, and EDR2 relies on the separately keyed HMAC for integrity. The authorised hider has the capability to recompute the tag, so a malicious hider is outside the threat model. Nonce uniqueness under a master key is mandatory. The owner-to-hider key handoff is assumed secure. No formal cryptographic proof, independent cryptographic audit, side-channel review, or malicious-hider analysis has been completed. Fuzzing and deterministic mutation tests are useful engineering evidence but are not substitutes for cryptographic analysis.

### 7.5 Dataset dependence and generalisation

The corpus includes natural-labelled images, constructed mosaics, rotated texture series, and related sequence frames. These correlated groups make a naive independent-image confidence interval inappropriate. Cluster-aware uncertainty estimation reduces but does not eliminate dataset-specific uncertainty. The current evaluation is restricted to even-sized native 8-bit grayscale images. Odd dimensions, colour images, 16-bit imagery, and cross-platform inference determinism are not covered by the core protocol.

The model checkpoint training manifest should accompany the final submission. Although the evaluation reused a fixed checkpoint and performed no training or fine-tuning, the training corpus, image-level split, seed, full training configuration, and checkpoint-selection record must be auditable. These details should be provided in a reproducibility supplement, not inferred from the evaluation code.

### 7.6 Limitations

The limitations can be summarised as follows:

1. Net capacity is low relative to the reproduced external methods, and positive capacity is obtained on 163 of 243 images.
2. The 3 × 3 CNN is not the most accurate or highest-coverage learned predictor in the matched-grid ablation.
3. Predictor inference is substantially slower than classical prediction on the measured CPU setup.
4. The core protocol is limited to even-sized native 8-bit grayscale images.
5. Exact predictor synchronisation depends on a fixed checkpoint and numerically compatible inference settings; cross-platform bitwise determinism is not claimed.
6. The authorised hider has authentication authority; malicious-hider resistance is not claimed.
7. There is no formal cryptographic proof or independent cryptographic audit.
8. The RGB extension is exploratory and does not establish a general colour-image solution.
9. The native-protocol baseline comparison is not a controlled common-packet-cost or same-security-model evaluation.
10. The checkpoint training manifest must be included with the final research release.

### 7.7 Reproducibility and reporting recommendations

Before submission, archive the exact EDR2 source commit, checkpoint SHA-256, dataset source/pixel manifests, per-image capacity CSV, round-trip ledger, baseline implementation commits and compatibility patches, runtime artifacts, and parser-fuzz artifacts. The manuscript's tables should be generated from these versioned records. The exact curation policy and 29 cluster identifiers should be included in the supplement. Figures should be regenerated from the committed CSV files and should not reuse any image whose publication rights have not been checked. The USC-SIPI database includes material whose reuse permissions may differ; publication figures need image-specific rights review.

## 8. Conclusion

This paper presented EDR2, a reserve-room-before-encryption RDHEI protocol that combines a centre-masked residual CNN-3×3 predictor, four maximum-density step-2 candidate phases, overhead-aware signed net-capacity selection, and authenticated in-band phase discovery. A formal argument shows that, within one selected phase, modifications to candidate carrier centres do not alter any candidate's masked 3 × 3 predictor input. The phase with the highest signed net payload is selected after directory, bootstrap, and backup costs are included. The receiver discovers that phase from the authenticated header location and restores the original image and payload without external image-dependent maps.

The 243-image grayscale evaluation yielded positive net capacity on 163 images and 978/978 exact receiver trials on the accepted subset. The mean usable rate was 0.1432 bpp and pooled usable rate was 0.0955 bpp. Reproduced Multi-MSB+Huffman and corrected PPMR methods obtained substantially higher native-protocol usable rates, and a separate matched-grid study found that a 5 × 5 no-weighted-loss CNN outperformed the selected 3 × 3 model on prediction MAE and positive-net coverage. EDR2 also incurs a significant CPU inference penalty. These results preclude a claim of state-of-the-art capacity or predictor superiority.

The contribution should therefore be understood as a protocol-specific synchronisation and accounting construction, supported by exact-recovery and parser-robustness evidence. Future work may investigate whether the same formal non-interference principle can be adapted to other receptive-field geometries and whether a lower-cost predictor or a more compact directory can improve net capacity without weakening the receiver contract. Such extensions are outside the claims of the present paper.

---

## References

[1] X. Zhang, “Reversible data hiding in encrypted image,” *IEEE Signal Processing Letters*, vol. 18, no. 4, pp. 255–258, 2011, doi: 10.1109/LSP.2011.2114651.

[2] K. Ma, W. Zhang, X. Zhao, N. Yu, and F. Li, “Reversible data hiding in encrypted images by reserving room before encryption,” *IEEE Transactions on Information Forensics and Security*, vol. 8, no. 3, pp. 553–562, 2013, doi: 10.1109/TIFS.2013.2248725.

[3] S. Yi and Y. Zhou, “Parametric reversible data hiding in encrypted images using adaptive bit-level data embedding and checkerboard based prediction,” *Signal Processing*, vol. 150, pp. 171–182, 2018, doi: 10.1016/j.sigpro.2018.04.016.

[4] P. Puteaux and W. Puech, “An efficient MSB prediction-based method for high-capacity reversible data hiding in encrypted images,” *IEEE Transactions on Information Forensics and Security*, vol. 13, no. 7, pp. 1670–1681, 2018, doi: 10.1109/TIFS.2018.2799381.

[5] Z. Yin, Y. Xiang, and X. Zhang, “Reversible data hiding in encrypted images based on multi-MSB prediction and Huffman coding,” *IEEE Transactions on Multimedia*, vol. 22, no. 4, pp. 874–884, 2020, doi: 10.1109/TMM.2019.2936314.

[6] Z. Yin, X. She, J. Tang, and B. Luo, “Reversible data hiding in encrypted images based on pixel prediction and multi-MSB planes rearrangement,” *Signal Processing*, vol. 187, Art. no. 108146, 2021, doi: 10.1016/j.sigpro.2021.108146.

[7] P. Puteaux, S. Ong, K.-S. Wong, and W. Puech, “A survey of reversible data hiding in encrypted images—The first 12 years,” *Journal of Visual Communication and Image Representation*, vol. 77, Art. no. 103085, 2021, doi: 10.1016/j.jvcir.2021.103085.

[8] H. Ren, G. Bai, T. Chen, Z. Yue, and R. Ren, “Reversible data hiding in encrypted images with multi-prediction and adaptive Huffman encoding,” *Scientific Reports*, vol. 13, Art. no. 23104, 2023, doi: 10.1038/s41598-023-50186-1.

[9] L. Sui, H. Li, J. Liu, Z. Xiao, and A. Tian, “Reversible data hiding in encrypted images based on hybrid prediction and Huffman coding,” *Symmetry*, vol. 15, no. 6, Art. no. 1222, 2023, doi: 10.3390/sym15061222.

[10] P. Ping, J. Huo, and B. Guo, “Novel asymmetric CNN-based and adaptive mean predictors for reversible data hiding in encrypted images,” *Expert Systems with Applications*, vol. 246, Art. no. 123270, 2024, doi: 10.1016/j.eswa.2024.123270.

[11] Z. Cheng, K. Chen, and Q. Guan, “Reversible data hiding in encrypted images based on pixel-level masked autoencoder and polar code,” *Signal Processing*, vol. 226, Art. no. 109664, 2025, doi: 10.1016/j.sigpro.2024.109664.

[12] F. Ren, Z. Zhang, K. Jiang, P. Zhang, and T. Yang, “Reversible data hiding and authentication scheme for encrypted image based on prediction error compression,” *Scientific Reports*, vol. 15, Art. no. 11636, 2025, doi: 10.1038/s41598-025-95433-9.

[13] X. Wang et al., “High-capacity reversible data hiding in encrypted images based on MSB sharing and overlapping sawtooth partition,” *Journal of King Saud University Computer and Information Sciences*, vol. 38, Art. no. 24, 2026, first published 12 Dec. 2025, doi: 10.1007/s44443-025-00238-5.

[14] G. Zhou et al., “Reversible data hiding in encrypted images based on bit-plane classification and adaptive group coding,” *IET Image Processing*, vol. 20, no. 1, Art. no. e70310, 2026, doi: 10.1049/ipr2.70310.

[15] S. Peng et al., “High-capacity reversible data hiding in encrypted images using dual-stage bit-plane compression and CP-ABE-based recovery authorization,” *Scientific Reports*, 2026, published 8 Aug. 2026, doi: 10.1038/s41598-026-65778-w.

[16] N. N. Hung, C. T. Luyen, and P. V. At, “High-capacity reversible data hiding in encrypted images using D4-symmetry bidirectional pixel shifting and context-aware recovery,” *Applied Sciences*, vol. 16, no. 20, Art. no. 10343, 2026, doi: 10.3390/app162010343.

[17] H. N. Tram and T.-S. Nguyen, “Reversible data hiding in encrypted images based on overlapping block partitioning and shared-MSB encoding,” *CTU Journal of Innovation and Sustainable Development*, vol. 18, Special Issue, pp. 1–10, 2026, doi: 10.22144/ctujoisd.2026.049.

[18] National Institute of Standards and Technology, *Recommendation for Block Cipher Modes of Operation: Methods and Techniques*, NIST Special Publication 800-38A, 2001, doi: 10.6028/NIST.SP.800-38A.

[19] H. Krawczyk, M. Bellare, and R. Canetti, “HMAC: Keyed-Hashing for Message Authentication,” RFC 2104, Internet Engineering Task Force, 1997, doi: 10.17487/RFC2104.

[20] H. Krawczyk and P. Eronen, “HMAC-based Extract-and-Expand Key Derivation Function (HKDF),” RFC 5869, Internet Engineering Task Force, 2010, doi: 10.17487/RFC5869.

---

## Submission-critical author checks

The following are not claims to leave implicit; they must be completed before submission:

1. Insert author names, affiliations, corresponding author, funding, acknowledgements, and conflict-of-interest statement.
2. Attach the checkpoint training manifest with actual training dataset inventory/hashes, source-image split, seed, optimizer, loss, epochs, and validation record. The evaluation did not retrain or fine-tune the checkpoint.
3. Confirm the four PPMR compatibility patches against the actual private reproduction diff and cite that diff in the supplementary material.
4. Link every main-paper table to the exact raw CSV/JSON artifact and record the source commit and artifact SHA-256.
5. Regenerate figures from the final CSV evidence and verify image-use rights before publication.
6. Verify every reference's final volume/issue/pages/article number and any corrections or editorial notices immediately before submission.
7. Select the target journal only after its scope, current indexing, article type, word limit, open-access options, and publication charges are verified.
8. Do not add a claim of superior capacity, prediction accuracy, formal cryptographic security, malicious-hider resistance, or multi-resolution scalability.
