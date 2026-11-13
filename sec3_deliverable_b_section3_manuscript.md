# 3. Proposed Methodology

This section describes the implemented prediction-based reversible data hiding pipeline evaluated in this work. The presentation follows the actual code and experiment artifacts: a CNN predictor is used to estimate each pixel from its local neighborhood, the resulting prediction errors are mapped to an embedding-capacity representation, payload bits are embedded by replacing selected most significant bits (MSBs) of the plaintext image, and the stego image is encrypted with AES-CTR before transmission. The receiver decrypts, extracts the payload, and recovers the original image using the same prediction-derived side information.

The emphasis in this paper is comparative rather than architectural novelty. We evaluate whether different lightweight CNN predictor configurations can improve prediction-based data-hiding performance, and we explicitly examine the trade-off among embedding capacity, prediction accuracy, reconstruction correctness, model complexity, and inference runtime. Where a mechanism is supported by the implementation, it is described precisely; where an implementation detail is ambiguous, incomplete, or not experimentally established, it is flagged rather than repaired silently.

## 3.1. System Overview and Problem Formulation

Let $\mathbf{I} \in \{0,\dots,255\}^{H\times W}$ be a grayscale image. In the implementation, the image owner first computes a prediction map
$\hat{\mathbf{I}} \in \mathbb{R}^{H\times W}$, rounds it to an integer prediction
$\mathbf{P} = \mathrm{round}(\hat{\mathbf{I}}) \in \mathbb{Z}^{H\times W}$, and forms the absolute prediction error map
\begin{equation}
\mathbf{E}_{\mathrm{abs}} = |\mathbf{I} - \mathbf{P}| \in \mathbb{Z}_{\ge 0}^{H\times W}.
\label{eq:errabs}
\end{equation}
The map $\mathbf{E}_{\mathrm{abs}}$ is not the payload; it is the quantity from which the embedding capacity is derived.

From $\mathbf{E}_{\mathrm{abs}}$, the system computes three side-information maps of the same spatial dimensions:
\begin{equation}
\mathbf{B} = \mathrm{label\_map}(\mathbf{E}_{\mathrm{abs}}),\quad
\mathbf{L}_{\min} = \mathrm{min\_range}(\mathbf{E}_{\mathrm{abs}}),\quad
\mathbf{L}_{\max} = \mathrm{max\_range}(\mathbf{E}_{\mathrm{abs}}),
\label{eq:mapseta}
\end{equation}
where $\mathbf{B}(y,x) \in \{0,\dots,7\}$ is the number of payload bits that may be embedded into pixel $(y,x)$, and $[\mathbf{L}_{\min}(y,x),\,\mathbf{L}_{\max}(y,x)]$ is the error interval used by the receiver to recover that pixel unambiguously. A pixel with $\mathbf{B}(y,x)=0$ carries no payload.

The total embedding capacity in bits is
\begin{equation}
C = \sum_{y=1}^{H}\sum_{x=1}^{W} \mathbf{B}(y,x),
\label{eq:capbits}
\end{equation}
and the embedding capacity in bits per pixel is
\begin{equation}
\mathrm{BPP} = \frac{C}{H\,W}.
\label{eq:bpp}
\end{equation}

A binary payload
\begin{equation}
\mathbf{p} = (p_1,\dots,p_C) \in \{0,1\}^C
\end{equation}
is generated deterministically from a fixed seed in the experiments. Let
$\mathrm{Embed}(\mathbf{I},\mathbf{B},\mathbf{p})$ denote the MSB-replacement embedding
and $\mathrm{Enc}_k(\cdot;\mathrm{nonce})$ denote AES-CTR encryption under key $k$ and
nonce. The owner produces
\begin{equation}
\mathbf{S}_{\mathrm{enc}} = \mathrm{Enc}_k\big(\mathrm{Embed}(\mathbf{I},\mathbf{B},\mathbf{p});\,\mathrm{nonce}\big),
\label{eq:ownerout}
\end{equation}
and transmits or stores $\mathbf{S}_{\mathrm{enc}}$ together with the side information
needed by the receiver. In the implemented pipeline, the stego image is formed in the
plaintext domain and only then encrypted; the ciphertext therefore contains a
stego plaintext image, not a plaintext image with embedded bits inserted after encryption.

The receiver is given the key $k$, the nonce, the payload length $C$, and the
owner-computed maps $\mathbf{B}, \mathbf{L}_{\min}, \mathbf{L}_{\max}, \mathbf{P}$.
It decrypts
\begin{equation}
\tilde{\mathbf{I}} = \mathrm{Dec}_k(\mathbf{S}_{\mathrm{enc}};\,\mathrm{nonce}),
\label{eq:dec}
\end{equation}
extracts the payload bits from the MSB-replaced pixels, and recovers an image
$\hat{\mathbf{I}}_{\mathrm{rec}}$ using $\tilde{\mathbf{I}}$, $\mathbf{P}$, and the
interval maps. The recovered image is compared with the original via exact equality,
and the extracted payload is compared with the embedded payload bit-by-bit.

Two roles should be distinguished clearly. The **CNN predictor** is only one
component used to obtain $\hat{\mathbf{I}}$. The **RDHEI embedding and recovery
procedure** is the label-map construction, MSB replacement, AES-CTR encryption, and
candidate-based pixel recovery. The predictor influences capacity and prediction error,
but the reversibility mechanism is defined by the error-to-bits mapping and the
recovery search, not by the predictor alone.

A system-flow description suitable for a figure is:

1. owner: $\mathbf{I} \;\rightarrow\; \hat{\mathbf{I}} \;\rightarrow\; \mathbf{P} \;\rightarrow\; \mathbf{E}_{\mathrm{abs}} \;\rightarrow\; (\mathbf{B},\mathbf{L}_{\min},\mathbf{L}_{\max}) \;\rightarrow\; \mathrm{Embed} \;\rightarrow\; \mathrm{Enc} \;\rightarrow\; \mathbf{S}_{\mathrm{enc}}$;
2. channel: $\mathbf{S}_{\mathrm{enc}}$ and side information $(\mathbf{B},\mathbf{L}_{\min},\mathbf{L}_{\max},\mathbf{P},C,k,\mathrm{nonce})$;
3. receiver: $\mathrm{Dec} \;\rightarrow\; \tilde{\mathbf{I}} \;\rightarrow\; \mathrm{Extract}(\tilde{\mathbf{I}},\mathbf{B},\mathbf{P},C) \;\rightarrow\; \mathbf{p}_{\mathrm{ext}}$ and $\mathrm{Recover}(\tilde{\mathbf{I}},\mathbf{P},\mathbf{B},\mathbf{L}_{\min},\mathbf{L}_{\max}) \;\rightarrow\; \hat{\mathbf{I}}_{\mathrm{rec}}$.

## 3.2. CNN-Based Pixel Prediction

### 3.2.1. Predictor input, preprocessing, and output

For a target pixel at $(y,x)$, the predictor extracts a square patch of size
$P\times P$ from a padded version of the image. The implementation uses reflection
padding by $P/2$ on all sides and then masks the central pixel to zero before
presenting the patch to the network. Formally, for a patch centered at $(y,x)$,
\begin{equation}
\mathbf{X}_{y,x} \in [0,1]^{P\times P},\quad
\mathbf{X}_{y,x}[c,c] = 0,
\end{equation}
where the patch is normalized by $255$ and the center index $c = P/2$ (integer
division in the implementation). The network outputs a single scalar
$\hat{v}_{y,x} \in [0,1]$, which is rescaled to pixel units and interpreted as the
predicted intensity:
\begin{equation}
\hat{\mathbf{I}}(y,x) = 255 \cdot \hat{v}_{y,x}.
\label{eq:cnnout}
\end{equation}
The final integer prediction used downstream is $\mathbf{P}(y,x) = \mathrm{round}(\hat{\mathbf{I}}(y,x))$.

Prediction is performed patch-by-patch over the whole image in batches. The
implementation processes all $H\times W$ patches with a fixed inference batch size
and no gradient computation, so the reported cost is inference-only prediction.

### 3.2.2. Architecture and the five configurations

All CNN configurations share the same overall structure: two $3\times 3$
convolutional blocks with batch normalization and ReLU, followed by a flatten layer
and a small fully connected head that ends in a sigmoid scaled by $255$. The
configurations differ in receptive field size and, for one ablation, in the presence
of a residual connection.

Let the convolutional feature extractor produce a feature tensor
\begin{equation}
\mathbf{F} = \mathrm{Block}_2(\mathrm{Block}_1(\mathbf{X})) \in \mathbb{R}^{C\times P\times P},
\end{equation}
where $C$ is the channel width used in the implementation and the blocks are
$3\times 3$ convolutions with padding that preserves spatial size. If a residual
connection is enabled, a $1\times 1$ convolution projects the input patch to the same
channel dimension and is added to $\mathbf{F}$:
\begin{equation}
\mathbf{F}' =
\begin{cases}
\mathbf{F} + \mathrm{Proj}_{1\times1}(\mathbf{X}), & \text{residual on},\\
\mathbf{F}, & \text{residual off}.
\end{cases}
\label{eq:res}
\end{equation}
The head then flattens $\mathbf{F}'$ and maps it to a scalar:
\begin{equation}
\hat{v} = 255 \cdot \sigma\big(\mathbf{w}_2\,\mathrm{ReLU}(\mathbf{W}_1\,\mathrm{flatten}(\mathbf{F}') + \mathbf{b}_1) + b_2\big),
\label{eq:head}
\end{equation}
where $\sigma(\cdot)$ is the sigmoid function.

The five evaluated configurations are:

- **CNN-3×3**: $P=3$, residual connection present.
- **CNN-5×5**: $P=5$, residual connection present. This is the full/proposed
  configuration referenced in the experiments.
- **CNN-NoResidual**: $P=5$, residual connection removed.
- **CNN-NoWeightedLoss**: $P=5$, residual connection present. This variant differs
  from CNN-5×5 in training loss rather than in the forward architecture of the saved
  model; see Section 3.7 and the audit in Deliverable A.
- **CNN-7×7**: $P=7$, residual connection present.

For the $P=5$ residual model, the saved checkpoints used in the experiments contain
$112{,}417$ parameters; for the $P=5$ non-residual model, $112{,}353$ parameters;
for CNN-3×3, $46{,}881$ parameters; and for CNN-7×7, $210{,}721$ parameters. These
counts are read from the inspected checkpoints and comp/analysis scripts.

Table 1 summarizes the verified architectural properties. The “loss” row reflects the
experiment labeling rather than a runtime architectural difference in the saved
weights.

**Table 1. CNN predictor configurations verified from the implementation and checkpoints.**

| Configuration | Patch $P$ | Residual | Loss variant (experiment label) | Trainable parameters |
|---|---|---|---|---|
| CNN-3×3 | 3 | yes | weighted L1 (default) | 46,881 |
| CNN-5×5 (full/proposed) | 5 | yes | weighted L1 (default) | 112,417 |
| CNN-NoResidual | 5 | no | weighted L1 (default) | 112,353 |
| CNN-NoWeightedLoss | 5 | yes | plain L1 (ablation label) | 112,417 |
| CNN-7×7 | 7 | yes | weighted L1 (default) | 210,721 |

The predictor itself is not claimed to be architecturally novel. It is a compact
fully convolutional regressor with a scalar sigmoid output, used here as one of
several predictors whose effect on RDHEI capacity and error is being compared.

### 3.2.3. Training dataset and procedure

The repository contains a concrete training script, `src/train.py`, which builds
patches from grayscale images, uses a weighted L1 loss
\begin{equation}
\mathcal{L}_{\mathrm{wL1}} = \frac{1}{N}\sum_{i=1}^{N} \bigl(1 + \alpha\,\frac{|e_i|}{255}\bigr)\,|e_i|,
\qquad e_i = \hat{v}_i - v_i^{\star},
\label{eq:wl1}
\end{equation}
with $\alpha=2.0$ in the default configuration, and trains with the Adam optimizer,
weight decay $10^{-4}$, cosine annealing learning-rate schedule, and a 10% validation
split. The script also records augmentation as horizontal and vertical flips and uses
a fixed random seed.

What is **not** established by the inspected artifacts is the exact training corpus,
the exact number of training images, the exact number of patches, the full training
log, and the precise reason each checkpoint ended in its particular configuration. The
checkpoints exist and load correctly, and their architectures match the expected
patch/residual settings, but the causal link between the documented training procedure
and the specific saved weights should not be overstated. For that reason, the training
description in this section is kept at the level supported by the script and the
checkpoint metadata, without inventing dataset size or provenance.

## 3.3. Prediction-Error Representation and Embedding Capacity

### 3.3.1. From absolute error to per-pixel bit allocation

The implementation does not use the signed error $e = \mathbf{I}-\mathbf{P}$ directly
for capacity. Instead, it computes $\mathbf{E}_{\mathrm{abs}}$ and assigns each pixel
a triplet $(b, e_{\min}, e_{\max})$ using a$\mathrm{label}\\_{map}(\\cdot)$ implemented in `src/rdhei_core.py`. The routine is
defined by iterating over ranges of absolute error and assigning bits according to
thresholds derived from powers of two.

For a given absolute error value $u = \mathbf{E}_{\mathrm{abs}}(y,x)$, the core
routine `_compute_bpp_and_range` computes:
\begin{equation}
(b,\, e_{\min},\, e_{\max}) = f_{\mathrm{map}}(u),
\label{eq:fmap}
\end{equation}
where $f_{\mathrm{map}}$ is the implemented label-map routine in `src/rdhei_core.py`, $b$ is the number of MSB positions that may be overwritten, and $[e_{\min}, e_{\max}]$ is the admissible range for the recovered pixel’s absolute error. If $b=0$, the pixel receives no payload and no recovery interval is used.

The mapping is defined operationally in the code by scanning candidate bit counts from
high to low and testing whether $u$ falls into ranges of the form
$[\,2^{r-1}-1,\;2^{r}-1\,]$ with special handling at the midpoint
$u = 2^{r-1}$. The exact conditions are best stated as implemented rather than as a
compact closed form, because the midpoint case is treated separately and the band
assignment is not monotonic in the usual sense. For the paper, it is enough to say
that $b$ is a deterministic function of $u$ and that the admissible interval
$[e_{\min},e_{\max}]$ is defined together with $b$ by the same routine.

### 3.3.2. Capacity and BPP equations

Given $\mathbf{B}$, capacity and BPP are given by (\ref{eq:capbits}) and
(\ref{eq:bpp}). In the grayscale pipeline, $C$ is exactly the sum of the label map
entries, and the implementation asserts $\textit{capacity} = \sum \mathbf{B}$ in the
verification scripts. In the RGB pipeline, the color wrapper processes each channel
independently and reports a color BPP. Two aggregation conventions appear in the
artifacts:

1. **Per-channel-average BPP** used by the color wrapper:
   \begin{equation}
   \mathrm{BPP}_{\mathrm{color}} = \frac{1}{3}\sum_{c\in\{R,G,B\}} \frac{C_c}{H\,W}.
   \label{eq:bppcolor1}
   \end{equation}

2. **Total-capacity-normalized BPP** sometimes used in ablation summaries:
   \begin{equation}
   \mathrm{BPP}_{\mathrm{color}}^{\text{total}} = \frac{\sum_{c} C_c}{H\,W\cdot 3}.
   \label{eq:bppcolor2}
   \end{equation}

   For an RGB image whose three channels have the same spatial dimensions, the two
expressions are algebrai|cally identical. Factoring the constant $1/(H\,W\cdot 3)$ out of
the sum gives
   \begin{equation}
   \frac{1}{3}\sum_{c} \frac{C_c}{H\,W}
   = \frac{1}{H\,W\cdot 3}\sum_{c} C_c
   = \frac{\sum_{c} C_c}{H\,W\cdot 3},
   \end{equation}
   so for any single image the per-channel-average form and the
total-capacity-normalized form produce the same number. They can differ only if channels
have unequal sizes. The manuscript therefore uses the per-channel-average definition in
Eq.\,\eqref{eq:bppcolor1} as the image-level RGB BPP throughout Section 3 and does not
treat Eqs.\,\eqref{eq:bppcolor1} and \eqref{eq:bppcolor2} as different formulas for a
single RGB image. The total-capacity form is retained only to document artifacts that
explicitly invoke it; it is the same quantity under the equal-dimension assumption.

### 3.3.3. Verification of the label-map and range logic

The mapping logic is tested directly in the repository through boundary tests and
random recovery tests. The boundary table used in `tests/test_mapping_ascii.py`
includes entries such as:

- $u=0 \rightarrow b=7,\ [0,0]$
- $u=1 \rightarrow b=6,\ [1,1]$
- $u=7 \rightarrow b=5,\ [5,7]$
- $u=8 \rightarrow b=3,\ [8,8]$
- $u=15 \rightarrow b=4,\ [9,15]$
- $u=16 \rightarrow b=2,\ [16,16]$
- $u=31 \rightarrow b=3,\ [17,31]$
- $u=32 \rightarrow b=1,\ [32,32]$
- $u=63 \rightarrow b=2,\ [33,63]$
- $u=64 \rightarrow b=0,\ [64,64]$
- $u=127 \rightarrow b=1,\ [65,127]$
- $u=128 \rightarrow b=0,\ [0,0]$

A broader automated test in `tests/test_mapping.py` checks boundary and random cases,
and a random-sample recovery test checks many $(u,\mathrm{payload})$ combinations. These
tests establish that the implemented label map and recovery routine are mutually
consistent on the tested inputs. They do **not** constitute a standalone mathematical
proof that every admissible band guarantees a unique recovered pixel for all possible
$( \mathrm{pred}, \mathrm{stego})$ pairs; that property is verified empirically as part
of the full-pipeline tests rather than as an algebraic lemma.

### 3.3.4. Limitations and ambiguities in the implementation

Two points should be stated openly:

1. The capacity mapping is a function of $|\mathbf{I}-\mathbf{P}|$ only. It does not
   exploit the sign of the error, and the mapping rules around the midpoint values are
   discrete and piecewise-defined. A reader looking for a simple analytic capacity
   formula in terms of the prediction-error distribution should be told that the actual
   capacity model is the implemented routine, not a continuous approximation.

2. In the inspected `_compute_bpp_and_range` routine, the “$l0$” low-error branch and
   the “$l1$”/“$l2$” stopping branches are interleaved in a way that makes the mapping
   correct by construction for the tested cases but not trivially interpretable as a
   single threshold per bit level. If the paper presents the capacity rule, it should
   either reproduce the operational definition faithfully or point to the routine as the
   authoritative definition.

## 3.4. Data Embedding and Encryption

### 3.4.1. Embedding sequence

Embedding is performed on the plaintext image. For each pixel $(y,x)$ with
$b = \mathbf{B}(y,x) > 0$, the upper $b$ bits of the pixel value are replaced by the
next $b$ payload bits, and the lower $8-b$ bits are left unchanged.

Let the original pixel be $v \in [0,255]$ and let the payload bits to embed be
$(m_0,\dots,m_{b-1})$ in MSB-first order. Write $v$ as
\begin{equation}
v = u \cdot 2^{8-b} + \ell,\qquad
u \in \{0,\dots,2^{b}-1\},\quad
\ell \in \{0,\dots,2^{8-b}-1\},
\label{eq:pixsplit}
\end{equation}
where $\ell = v \bmod 2^{8-b}$ are the preserved low bits. The stego pixel is
\begin{equation}
v_{\mathrm{stego}} = \Bigl(\sum_{j=0}^{b-1} m_j\,2^{\,b-1-j}\Bigr)\cdot 2^{8-b} + \ell.
\label{eq:embed}
\end{equation}
In the implementation, this corresponds to overwriting the $b$ most significant bits
with the payload bits and keeping the low $8-b$ bits intact.

Pixels with $b=0$ are not modified by embedding. The sender iterates pixels in raster
order and consumes payload bits sequentially; if the payload is shorter than the total
capacity, the remaining embedding opportunities are effectively filled with zeros in the
current sender loop, but the receiver is configured with the actual payload length and
stops extracting at that point.

### 3.4.2. Encryption position and method

After embedding, the stego plaintext image is encrypted with AES-CTR:
\begin{equation}
\mathbf{S}_{\mathrm{enc}} = \mathrm{AES\text{-}CTR}_{k,\mathrm{nonce}}(\mathrm{Embed}(\mathbf{I},\mathbf{B},\mathbf{p})).
\end{equation}
In this implementation, embedding therefore occurs **before** encryption.
The ciphertext is not an encrypted original image with payload inserted afterwards; it
is an encrypted stego plaintext image.

AES-CTR in the implementation uses a 128-bit counter initialized with
`Counter.new(128, initial_value=nonce)`. Encryption and decryption are the same XOR with
this keystream, and `encrypt_image(..., nonce)` is used for both. The RGB pipeline calls this
per channel with distinct nonces, so the three channels do not share a keystream under the same
key. The paper must not claim that this mode provides authenticity or integrity. The implemented
system provides confidentiality under the standard assumptions for AES-CTR, with the
well-known caveats that ciphertext integrity is not verified and that the nonce must not be
reused with the same key.

### 3.4.3. RGB channel encryption

For RGB images, each channel is encrypted with a distinct nonce derived as
\begin{equation}
\mathrm{nonce}_c = \mathrm{base\_nonce} + c + 1,\qquad c\in\{0,1,2\},
\label{eq:noncederiv}
\end{equation}
so that the three channels do not share a keystream under the same key. The nonces are
derived deterministically from a single base nonce and must be available to the receiver
for decryption. The repaired RGB pipeline records the per-channel nonces and is
constructed specifically to avoid the earlier keystream-reuse defect, but the paper
should still state the residual limitations: no authentication, and the base nonce must
be communicated separately.

### 3.4.4. What is not described

The implementation does **not** use lower-bit-plane embedding as a separate mechanism;
the replaced bits are the upper MSBs determined by $\mathbf{B}$. The implementation does
**not** present a custom encryption architecture, and it does not claim cryptographic
integrity or authentication. The paper should avoid presenting the encryption as an
RRBE/RRAE framework with stronger security properties than the code provides.

## 3.5. Data Extraction and Image Recovery

### 3.5.1. Receiver inputs

The implemented receiver does not operate from the ciphertext alone. In addition to the
key $k$ and nonce, it receives:
- $\mathbf{B}$, the per-pixel bit-allocation map;
- $\mathbf{L}_{\min}$ and $\mathbf{L}_{\max}$, the per-pixel admissible error intervals;
- $\mathbf{P}$, the integer prediction map;
- $C$, the payload length.

These are exactly the objects returned by the owner-side preparation and passed into
`receiver_extract_recover`. In the implementation, `run_rdhei()` computes
`pred_int`, `bpp_map`, `min_e_map`, and `max_e_map` on the owner side and passes them
directly into the receiver function; the evaluation harness therefore supplies the receiver with
precomputed owner-side side information rather than requiring the receiver to derive it from the
ciphertext. The same maps are also the basis for the reported capacity and BPP. This is the
information that must be available to the receiver for extraction and recovery; it is not separate
encrypted metadata in the current pipeline.

### 3.5.2. Extraction

After decryption to $\tilde{\mathbf{I}}$, extraction reads the $b$ upper bits of each
pixel with $b>0$, in raster order, until $C$ payload bits have been collected. For a
pixel with $b>0$, the extracted bits are
\begin{equation}
(\tilde{m}_0,\dots,\tilde{m}_{b-1}) =
\big(\text{MSB}_b(\tilde{v})\big),
\label{eq:extract}
\end{equation}
where $\text{MSB}_b(\cdot)$ denotes the $b$ most significant bits of the decrypted
pixel value $\tilde{v}$. Extraction and image recovery are separate operations. In the
current implementation, `receiver\_extract\_recover` stops collecting new payload bits
once $C$ bits have been gathered, but it continues to process every remaining pixel so
that image recovery is attempted over all pixels, not only those processed before the
extraction budget is exhausted.

### 3.5.3. Recovery

Recovery exploits two facts about each stego pixel with $b>0$:

1. The embedding operation overwrites only the $b$ upper (MSB) bits of the pixel; the
   lower $8-b$ bits observed in the decrypted stego pixel are exactly the lower $8-b$
   bits of the original pixel and must therefore be preserved by any valid
   reconstruction.
2. The admissible prediction-error interval $[\mathbf{L}_{\min}(y,x),\,
   \mathbf{L}_{\max}(y,x)]$ from the owner-side label map restricts the prediction error
   of the recovered pixel.

For a pixel with $b>0$, the receiver enumerates all $2^{b}$ possible upper-bit
combinations and selects a candidate $\hat{v}$ that satisfies **both** of the following
conditions:

- **Lower-bit preservation:**
  \begin{equation}
  \hat{v} \bmod 2^{8-b} = \tilde{v} \bmod 2^{8-b},
  \end{equation}
  i.e., the candidate must preserve the lower $8-b$ bits present in the decrypted stego
  pixel $\tilde{v}$.
- **Admissible prediction error:**
  \begin{equation}
  \mathbf{L}_{\min}(y,x) \le |\hat{v} - \mathbf{P}(y,x)| \le \mathbf{L}_{\max}(y,x).
  \label{eq:recover}
  \end{equation}

If $b=0$, the pixel is returned unchanged, since no embedding occurred and the stego
pixel is the original pixel.

The recovery routine is a small exhaustive search over the upper-bit space. Because $b$
is at most 7 in the implemented mapping, the search space is modest per pixel. The
implemented routine `\_recover\_pixel` in `src/rdhei_core.py` enforces the lower-bit
preservation above and then selects the candidate whose prediction error falls in the
interval $[\mathbf{L}_{\min},\,\mathbf{L}_{\max}]$ produced by the same label-map routine
that determined $b$. Satisfying the prediction-error interval alone is not sufficient;
the candidate must also share the observed lower bits.

### 3.5.4. Blindness and side-information disclosure

Because $\mathbf{B}$, $\mathbf{L}_{\min}$, $\mathbf{L}_{\max}$, and $\mathbf{P}$ are
computed by the owner and supplied to the receiver, the implemented recovery is **not**
ciphertext-only and is **not** claimed to be fully blind with respect to the prediction
side information. The paper should state this explicitly: the receiver reconstructs the
image exactly because it is given the owner’s prediction-derived maps, not because it
independently infers them from the encrypted stego image.

### 3.5.5. When exact recovery is expected and how it is verified

Exact recovery is expected whenever three conditions hold together:

1. decryption recovers the exact stego plaintext (AES-CTR with matching key and nonce);
2. the embedding/conservation of low bits is consistent, i.e., the low $8-b$ bits in
   $\tilde{\mathbf{I}}$ equal the low bits of the original pixel;
3. for every embedded pixel, the admissible interval contains exactly one candidate
   matching the low bits, so (\ref{eq:recover}) returns the original pixel.

In the repository, reversibility is verified by direct array equality checks:
\begin{equation}
\mathbf{I} \stackrel{?}{=} \hat{\mathbf{I}}_{\mathrm{rec}},\qquad
\mathbf{p} \stackrel{?}{=} \mathbf{p}_{\mathrm{ext}}.
\label{eq:exactchecks}
\end{equation}
The final verification artifacts record these checks for all five CNN variants on the
available grayscale Kodak images, with `perfect=True` and bit accuracy $100\%$ reported
by the pipeline and confirmed by independent equality checks. For RGB, explicit
per-channel exact image and payload checks were recorded for the completed runs.
The later full-pipeline verification artifact recorded the RGB images as SKIPPED because
that run loaded them as 2-D arrays; the manuscript does not describe those skipped cases as passed. This is strong empirical evidence for the tested images and variants, but the
scope is limited to the images and checkpoints that were actually run; exact recovery is
therefore reported as verified for that scope, not as a universal guarantee for all
possible images.

The manuscript's extraction description states that extraction stops after $C$ bits
while image recovery continues over all pixels. This description matches the current
receiver implementation, where `receiver_extract_recover` stops collecting new payload
bits once $C$ bits have been gathered but continues the per-pixel recovery loop over the
entire image. That behavior was verified for the tested cases by running the repository's
reproduction script `repro_receiver_payload_len.py`, which exercised empty, short,
capacity $- 1$, full-capacity, and over-capacity payload lengths on a synthetic image and
reported exact image recovery and bit-accurate extraction for all valid payload lengths in
that test. The verified scope is therefore the concrete implementation reachable from the
current `src/rdhei_core.py` and the specific payload-length cases tested by that script;
it is not an independent mathematical proof that every conceivable short-payload embedding
state recovers every pixel, nor a claim that the pipeline has been validated for arbitrary
payload lengths beyond the tested cases. Where this manuscript refers to full-image
recovery, it should be read as recovery over all pixels in the tested implementation and
test scope, subject to the stated assumptions about decryption, low-bit conservation, and
the label-map interval.

## 3.6. RGB Image Processing

### 3.6.1. Channel-independent processing

The RGB pipeline processes each channel independently as a grayscale image. For each
channel $c\in\{R,G,B\}$, it computes a prediction map, forms the absolute error map,
derives the label maps, embeds payload bits, and encrypts with a channel-unique nonce
as in (\ref{eq:noncederiv}). The recovered RGB image is reconstructed by stacking the
three recovered channels.

No color-space transformation such as YCbCr conversion is used in the implementation.
The method is applied directly to the R, G, and B channels as supplied.

### 3.6.2. Aggregation of capacity and BPP

Let $C_c$ be the capacity in bits for channel $c$. The color wrapper reports
\begin{equation}
\mathrm{BPP}_{\mathrm{color}} = \frac{1}{3}\sum_{c} \frac{C_c}{H\,W},
\end{equation}
which is the mean of the three per-channel BPP values. This definition is used in the
RGB baseline output and in the smoke-test and RGB validation artifacts. Where an ablation
summary uses the total-capacity-normalized form, the manuscript must not mix the two
without stating which is which.

### 3.6.3. What the implementation does not assume

The implementation does not assume that the three channels have identical statistics or
that embedding capacity should be allocated jointly across channels. It treats the RGB
image as three independent grayscale RDHEI problems, coupled only by the shared key and
the per-channel nonce derivation.

## 3.7. Experimental Configurations and Evaluation Metrics

### 3.7.1. Predictor variants and baselines

The experiments compare five CNN predictor variants described in Section 3.2.2:
CNN-3×3, CNN-5×5, CNN-NoResidual, CNN-NoWeightedLoss, and CNN-7×7. CNN-5×5 is treated
as the full/proposed configuration. The classical baselines in the experiments are MED,
GAP, and CALIC. A histogram-shifting-related entry appears in the grayscale baseline
table, but its capacity is far lower than that of the prediction-error methods and it is
not directly comparable on BPP; the paper should therefore treat it as a different class
of method rather than as a like-for-like capacity competitor.

It is important to distinguish two kinds of ablation:
- **Architectural** variants: patch size ($3,5,7$) and residual connection (on/off).
- **Training-loss** variant: CNN-NoWeightedLoss uses the same 5×5 residual
  architecture but is labeled as a plain-L1-loss ablation in the experimental naming.

### 3.7.2. Metrics

The following metrics are used in the actual experiments:

- **BPP**: embedding capacity in bits per pixel, defined by (\ref{eq:bpp}) for
  grayscale. For RGB, the reported BPP is the mean of per-channel BPP values unless
  another convention is explicitly stated.
- **Prediction MAE / MPE**: mean absolute prediction error before embedding,
  $\mathrm{MAE}_{\mathrm{pred}} = \mathrm{mean}(|\mathbf{I} - \mathbf{P}|)$. This
  measures predictor accuracy, not reconstruction fidelity.
- **Reconstruction MAE**: mean absolute error between $\mathbf{I}$ and
  $\hat{\mathbf{I}}_{\mathrm{rec}}$, used to quantify recovered-image fidelity.
- **PSNR and SSIM**: computed between $\mathbf{I}$ and $\hat{\mathbf{I}}_{\mathrm{rec}}$.
  In the perfect-recovery experiments, PSNR is reported as infinite and SSIM as $1.0$
  for methods that achieve exact recovery.
- **Bit accuracy**: fraction of extracted payload bits equal to the embedded bits.
- **Runtime**: wall-clock inference time for the predictor only, measured on CPU with a
  documented warm-up and repetition policy.
- **Parameter count**: number of trainable parameters in each CNN configuration.
- **Computational complexity**: approximate FLOP and memory figures produced by the
  complexity script; see the audit in Deliverable A for the status of those numbers.

Prediction accuracy and reconstructed-image fidelity are distinct. A predictor may reduce
prediction error and increase capacity without changing the fact that the implemented
reversibility mechanism can perfectly recover the image for the tested images. The paper
should not use prediction MAE as if it were an image-quality metric.

### 3.7.3. Runtime measurement scope and environment

The runtime numbers in the artifacts are **predictor-only**. They measure the time to
produce the prediction map, not the time for label-map construction, embedding,
encryption, extraction, or recovery. The measurement setup recorded in
`results/runtime/runtime_report.txt` is:

- device: CPU;
- benchmark image: `Lena.png`, $512\times512$ grayscale;
- warm-up runs: $5$;
- repeats: $10$;
- aggregation: mean, std, min, max, median over the repeat wall-clock timings.

Under this setup, the classical predictors are fast (MED in milliseconds, GAP and CALIC
in tens of milliseconds), while the CNN predictors are orders of magnitude slower
(CNN-3×3 on the order of $1.76$ s and CNN-7×7 on the order of $7.24$ s for the same
image). One full-pipeline run with CNN-3×3 on a single 512×512 image was also recorded
at roughly $8$ seconds, showing the order of magnitude of the complete pipeline on CPU,
but this is a single datapoint, not a full runtime benchmark.

These numbers refute any claim that the CNN-based method is computationally lightweight
relative to the classical baselines. The trade-off is real and should be described
honestly: the CNN predictors can change capacity and prediction error, but they add
substantial inference cost.

### 3.7.4. Dataset transparency

The evaluation uses the images present in the repository, which the artifacts identify as
6 grayscale and 6 RGB files, not the larger dataset sizes sometimes assumed in project
descriptions. The CNN training dataset is separate from the evaluation images, and its
exact composition is not fully specified in the inspected artifacts. The paper should
therefore describe the evaluation set accurately and avoid implying that it is large or
statistically representative.

### 3.7.5. What the experiments do and do not establish

The experiments establish, for the tested images and checkpoints:

- that the CNN predictors produce different prediction-error and capacity outcomes than
  the classical baselines;
- that the implemented embedding, encryption, extraction, and recovery pipeline can
  achieve exact reconstruction and bit-accurate payload recovery on the tested images;
- that the CNN predictors incur substantially higher inference cost than the classical
  predictors.

The experiments do **not** establish, without additional evidence:

- that the CNN architecture or loss is novel;
- that the model is computationally lightweight compared with classical predictors;
- that the training procedure and dataset are fully reproducible from the available
  artifacts;
- that the system provides authenticated or tamper-resistant encryption.

These boundaries are respected in the wording of this section.
