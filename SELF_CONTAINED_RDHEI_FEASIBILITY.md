# Self-contained RDHEI feasibility gate

2026-10-22. **A — reproducible predictions with joint mapless decoding: NO-GO. B — in-image metadata: conditional GO as a separate, restricted feasibility prototype. The current dense pipeline and the rejected paper's Figure 2 are NO-GO for the stated receiver interface.**

B produces positive net user payload and exact recovery on two tested natural images and a synthetic constant image. It rejects Baboon and random noise before embedding because its reversible budget is negative. It is not a universal codec or a production replacement. No trained weights, manuscript, existing source pipeline, or historical report was changed; no training was performed.

## Inspected evidence and paper identity

The user confirmed that Windows Downloads `main (5).pdf` is the same requested rejected paper as `main (5)(2).pdf`. The inspected eight-page PDF is “Learning-Based Pixel Prediction for High-Capacity Reversible Data Hiding in Encrypted Images”, SHA-256 `c14214efdb96707b10f6322c81992f75e903fff6174935f9c550dbf5ec2d8a2a`. Figure 2 was extracted from page 4 and visually inspected, not inferred from its caption; Equations (8)–(12) and Table 2 are on that page. Extracted text and the original figure bitmap are in this investigation directory. The separately found `main.pdf` has a different file hash and was not silently substituted.

Implementation inspected: `src/rdhei_core.py` (owner preparation at line 337, sender at 400, receiver at 463), `src/predictor.py`, `src/cnn_model.py`, `src/embedding.py`, `src/extraction.py` and `src/encryption.py`. The latest `NO_RETRAINING_CAPACITY_CALIBRATION_REPORT.md` establishes that previous recovery tests were conditioned on external maps, not an image-only receiver; its simple dense sidecar representation averaged 15.535591 bits/sample against 5.05063643 gross BPP. Those numbers were not net payload and that report remains unchanged.

All prototype payloads use the existing CNN-3×3 checkpoint `models/v4_patch3.pth`, SHA-256 `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`. The paper's 5×5 architecture is a different existing checkpoint, `models/v1_full.pth`; it was loaded only for a prediction-reproducibility diagnostic. The 3×3 weights were never reshaped into a 5×5 model. Both models ran in evaluation mode with gradients disabled and parameters frozen.

## Contradictions that prevent the original diagram from being implemented literally

| Evidence | Contradiction / missing reversible operation |
| --- | --- |
| Figure 2: “Replace MSB bits with Payload” | Equation (8), `floor(x/2^(8-l))*2^(8-l)+D`, replaces the lower `8-l` bits, preserving the upper l bits. These are different transforms and different recovery residue sets. The existing core implements MSB replacement. |
| §3.4 versus §3.5 preserved bits | l is defined as preserved MSBs, but the sentence after (8) calls the higher-order `8-l` planes preserved. The printed equation preserves l, not `8-l`. |
| Skip condition after (8) | Text says l=0 pixels remain unchanged. l=0 is absent from the stated alphabet; (8) with l=0 overwrites all eight bits. The actual no-embedding value in that convention is l=8. |
| Figure 2 “Store Label Map in LSB (3 bits)” | For n payload MSBs, only `8-n` low original bits survive. Writing three LSBs destroys those recovery bits whenever they change. For n=7 it also overlaps two payload positions; for n=6, one payload position. Even n=0 skip pixels cease to be unchanged if their labels are written there. No displacement/backup stream is specified. |
| Concrete diagram witness | x=0,p=0,n=7, seven zero payload bits produces marked value 0. Storing the natural three-bit allocation value 7 produces marked value 7: the surviving original LSB changes 0→1 and the extracted payload becomes `0000011`. `diagram_zero_payload_witness.json` records this. Relabeling codes cannot supply a missing restoration mechanism. |
| Equation (8) plus three-LSB labels | If D includes labels, at least three of its bits are metadata rather than user payload, and locations with `8-l < 3` cannot hold a local three-bit label. If labels are written afterward, they overwrite D. The merged-stream layout, overflow rule and bootstrap are absent. |
| Equation (9)/(10) | Sum of replaceable slots counts labels, framing, backups and user bits together. It is gross space, not net user capacity. A three-bit field at every pixel alone costs 3N bits, before preservation and framing. |
| Three-bit allocation versus actual recovery intervals | The actual map has 15 `(n,min,max)` classes, requiring four bits in a straightforward fixed code. n alone has eight values but does not identify an interval: n=5 means e=2 or e=5…7; n=6 means e=1 or e=3. The core receiver takes all interval maps explicitly. |
| Table 2 versus Figure 2 versus code | Table 2 stops embedding at e>=16; Figure 2 instead branches on e<128. Table 2 collapses ranges differently from the implementation (e=3 gives paper n=4, implementation n=6). The implementation's capacity map also has upward steps, e.g. n(2)=5, n(3)=6, unlike the monotone description. These cannot share an unspecified label decoder. |
| Equation (12) | Its equal-upper-bits set matches LSB replacement, not Figure 2/core MSB replacement. The printed condition `abs(v-p)<2^(8-l)` does not imply a unique candidate, even with exact p and l. At p=x=0,l=1 all 128 candidates 0…127 pass. At x=0,p=8,l=5 the true original fails the strict distance bound. |
| Reconstruct CNN prediction from marked image | Masking the target center removes its own value only. Embedding in adjacent pixels changes its context. The dense noncausal predictor cannot generally reproduce its original map on the decrypted marked image. |
| Receiver inputs | `receiver_extract_recover` explicitly requires `bpp_map,min_e_map,max_e_map,pred_int,payload_len`. The sender does not serialize those maps or a length. Installed weights do not replace these unavailable inputs. |
| Payload-length termination | Empty, short and full payloads cannot be distinguished from zero padding without framing or another agreed termination code. The core receives length externally; no in-image framing is created. |
| Encryption order | Equation (11), Figure 2 and the core embed in plaintext then encrypt; the abstract describes label storage in AES-CTR encrypted lower planes. These are different byte values. AES decryption is invertible and supplies no missing allocation, overwritten original bits, or framing. Key/nonce alone do not resolve the coding ambiguities. |
| Legacy “self-contained” helper | `src/extraction.py::full_extraction` uses a different threshold/PEE path and forces MED, not this frozen CNN scheme. Its header parser is not evidence that the core serialized a header. It encodes only a 16-bit length, beyond which lengths truncate. The associated embedding clips overflow without a reversible overflow map: on image `[255,255]`, distinct one-bit payloads 0 and 1 both mark `[255,255]` at T=1. This alternative is not a valid repair. |

The paper's printed Equation (12)/Table 2 rule was independently enumerated across all feasible x,p. Of **7696 embedding pairs**, **5086 have multiple admissible candidates** and **3912 exclude the original**; these categories can overlap. This tests the printed rule, not a hypothetical corrected decoder. `paper_equation12_gate.json` contains witnesses. The existing pipeline's supplied-map uniqueness proof therefore does not validate that paper rule.

## Prediction reproducibility and its capacity cost

Actual dense MSB embedding was applied to a 128×128 Airplane crop with arbitrary payload words under the existing map, then predictions were recomputed:

| Checkpoint | Changed integer predictions / 16,384 | Maximum float prediction change | Isolated center predictions |
| --- | --- | --- | --- |
| Existing CNN-3×3 | 16326 | 208.710052 | All 1,764 bitwise identical |
| Existing CNN-5×5 | 16330 | 210.334351 | All 1,764 bitwise identical |

Dense maps are not reproducible. For radius r, however, choose candidate centers with Chebyshev distance greater than r, mask each center as the existing predictor does, and modify only those centers. Every other sample in each candidate's input patch is unchanged. Therefore the masked normalized tensor, model output and rounded prediction at each candidate are identical. Overlap between two surrounding patches is harmless; the other candidate's *center* must be outside the patch. Evaluation-mode batch normalization and fixed inference batching are part of the shared decoding algorithm.

The prototype fixes rows/columns `2,5,8,… < dimension−2`: spacing 3, radius-2 border exclusion. It protects a 5×5 context and therefore also the selected 3×3 predictor, without reflected-border dependencies. Direct masked-patch equality and bitwise float-output equality were asserted for both checkpoints after arbitrarily overwriting **every candidate byte**, including future header carriers. No dense prediction map is sent. For 512×512 images only 28,900/262,144 = **11.0245%** of pixels are candidates. The bulk geometric limit is 1/9; it is not negligible. Fully disjoint 5×5 patches would reduce density further to about 1/25, and stride 8 to about 1/64; neither is required for this isolation proof.

A 3×3-only spacing-2 diagnostic has bulk density 1/4 but is not safe for a 5×5 input neighborhood and is not the B packet tested here:

| Image | 3×3-only step-2 gross BPP | 5×5-compatible step-3 gross BPP | Dense gross BPP |
| --- | --- | --- | --- |
| Airplane.png | 1.427704 | 0.634434 | 5.750191 |
| Baboon.png | 1.131195 | 0.502666 | 4.557613 |
| Lena.png | 1.352615 | 0.601013 | 5.459320 |
| constant128 | 1.695740 | 0.753662 | 7.000000 |
| random256 | 0.392700 | 0.171066 | 1.589874 |

These are measured gross slots per whole grayscale image pixel, not candidate-only BPP or net payload. For example, Airplane falls from 5.750191 dense gross BPP to 0.634434 before a single metadata bit is charged.

## A: joint mapless allocation/original decoding — NO-GO

For a known reproducible integer p, enumerate x=0…255, set n from the unmodified error map, and enumerate **every one of the 2^n payload patterns**, including n=0 pass-through. Record `(p,marked) -> (x,n,payload)`. A valid decoder must recover x **and** n and the payload word uniquely; supplying n or the interval to this test is forbidden.

The MSB case enumerated all 65,536 original/prediction pairs and **396032 payload words**. All 65,536 possible `(p,marked)` observations occur; **65272 observations are nonunique**, including **65256 with different allocations**. For example p=0,marked=2 arises from x=0,n=7,payload=`0000001`, or x=2,n=5,payload=`00000`. Both follow the actual map and produce the same receiver inputs.

As a bit-position control, switching to LSB replacement while retaining the same allocation map also fails: 48962 nonunique observations. This control is distinct from the separate printed-paper Table 2/Equation (12) test above.

The counting obstruction is structural: for fixed p, accepting all 256 original byte values already requires at least 256 marked-byte codewords with no payload. Allowing multiple payload words for any such original requires additional distinct codewords, but only 256 exist. Spatial isolation reproduces p; it does not create more marked-byte states. A different block/source-compression architecture, explicit metadata, or a restricted accepted source domain is necessary. Unknown payload length adds another ambiguity; it cannot fix these collisions.

**No A end-to-end performance comparison or valid net BPP is reported.** A fails the mathematics and was not promoted to an image-only decoder. “Recover original with allocation supplied” was used only as a separate B component check, never as an A pass.

## B: self-contained in-image metadata — conditional GO

This is a separate feasibility packet, not Figure 2 coded literally and not a production pipeline. Its receiver is exactly `receive(encrypted_image,key,nonce)` in `prototype.py`. Image dimensions/dtype belong to the encrypted image input. The checkpoint, grid, label codebook, header format and algorithm are installed constants. It accepts no maps, threshold, original image, candidate file or length argument.

B's reversible layout is:

1. Compute the isolated candidate predictions and original error classes. A shared 15-entry codebook represents `(n,min,max)`, including pass-through. Pack two four-bit classes per byte (pad one nibble if needed). Measure zlib level-9 bytes and use the shorter of compressed and raw packed bytes. The labels include all candidates, including the future bootstrap region, making its size computable without a circular allocation decision.
2. Let L be the stored label byte count and **H=20+L**. The first H isolated candidate centers carry H complete metadata bytes. The first 20 form fixed `>4sB3xIQ` framing: four-byte magic, one-byte codec, three reserved bytes, four-byte L, and **eight-byte user payload bit length**. This is 160 framing bits, of which 64 are payload-length framing. Dimensions and candidate count are derived from the image, not a separate file.
3. Save the **original H carrier bytes** verbatim: 8H bits. Prepend them to the user payload. In all remaining candidate centers, embed this stream using the existing n-MSB replacement map. Pad unused capacity with zeros. Noncandidate pixels remain unchanged. Header carriers are fully overwritten, but their originals are not discarded.
4. Encrypt the complete marked image with the existing AES-CTR routine. The receiver decrypts, reads the fixed first 20 candidate bytes, reads/decompresses the labels, and recomputes predictions from the unchanged neighborhoods. It extracts the ordinary stream, uniquely recovers those ordinary candidate originals using the internally decoded classes, then restores the H bootstrap originals from the first 8H extracted bits. It returns exactly the following framed user bits.

There is no prediction-map sidecar. Label information exists **inside the encrypted image**, and the original header-carrier bytes are restored from inside that same image. The apparent circularity is broken by a fixed read location and explicit displacement backup; a reserved overwrite with no backup would fail.

B's local recovery component was exhaustively checked over **65,536 x,p pairs and 396,032 payload words**, including pass-through, with zero failures. The supplied class in that component check is recovered from B's internal metadata in the actual receiver. All 15 classes, nibble packing/unpacking and odd counts were checked. This does not reverse A's negative result.

### Exact overhead accounting

Let G0 be the ordinary n-MSB gross slots summed over all C candidate centers; let G_H be the ordinary slots those H bootstrap centers would have offered. The remaining ordinary stream capacity is `S = G0 − G_H`. It must carry `8H` original bootstrap bits plus the user payload:

`net user bits = S − 8H = G0 − G_H − 8(20+L)`.

The actual physical slots used by the proposed packet are `Gphysical = S + 8H`, because the H bootstrap pixels use all eight bits. Of those, `8H` are metadata/framing and another `8H` are original backups in the ordinary stream, leaving the same `S−8H` net bits. This formulation prevents either treating header pixels as free or double-subtracting the same reservation against inconsistent gross definitions. The table reports both G0 and Gphysical. No original bootstrap bytes are assumed compressible. Images with insufficient space are rejected before output; negative arithmetic budgets are never reported as usable payload.

Actual measured labels and storage locations:

| Image | Candidates C | Raw packed labels (bits) | Measured zlib labels (bytes) | Bootstrap pixels H | Remaining ordinary slots S |
| --- | --- | --- | --- | --- | --- |
| Airplane.png | 28900 | 115600 | 9823 | 9843 | 108959 |
| Baboon.png | 28900 | 115600 | 11768 | 11788 | 81844 |
| Lena.png | 28900 | 115600 | 10474 | 10494 | 99944 |
| constant128 | 1764 | 7056 | 17 | 37 | 12089 |
| random256 | 7056 | 28224 | 2532 | 2552 | 7039 |

The natural images each require 115,600 raw class bits before compression. Compression is measured, not presumed; Baboon still fails the full budget despite compression. The codebook, compression level, prefix carrier rule and payload cases were fixed in this feasibility design, not selected to reproduce the paper's capacity figures. This is a deliberately simple codec, not a claim of minimum possible metadata size. A better codec might accept additional images but has not been demonstrated here.

| Image | Dense gross BPP (reference) | Isolated gross G0/N | Actual physical slots/N | Metadata + framing bits | Displaced originals (bits) | Foregone G0 slots | Signed user budget (bits) | Usable net BPP | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Airplane.png | 5.750191 | 0.634434 | 0.716030 | 78744 | 78744 | 57354 | 30215 | 0.115261 | GO |
| Baboon.png | 4.557613 | 0.502666 | 0.671951 | 94304 | 94304 | 49927 | -12460 | 0.000000 | REJECT |
| Lena.png | 5.459320 | 0.601013 | 0.701508 | 83952 | 83952 | 57608 | 15992 | 0.061005 | GO |
| constant128 | 7.000000 | 0.753662 | 0.755920 | 296 | 296 | 259 | 11793 | 0.719788 | GO |
| random256 | 1.589874 | 0.171066 | 0.418930 | 20416 | 20416 | 4172 | -13377 | 0.000000 | REJECT |

For Airplane, metadata/framing occupy 9,843 candidate bytes (78,744 bits), those 9,843 originals require 78,744 backup bits, and they forego 57,354 ordinary gross slots. Net is 108,959−78,744 = **30,215 user bits (0.115261 BPP)**. Lena carries **15,992 bits (0.061005 BPP)**. The synthetic constant result is not averaged into a natural-image claim. Baboon's signed budget is −12,460 bits; noise is −13,377. Neither can even carry this packet's complete restoration information, so neither was embedded.

### Executed receiver-only round trips

Each accepted image ran empty, 37-bit short, half-net partial and full-net user payloads: **12 fresh-process checks**, **zero image recovery failures**, **zero payload recovery failures**. Full means all *net* user space, after backup/framing/labels, not the earlier dense gross capacity. AES encryption/decryption are exercised on every check. Bit equality and byte equality were asserted independently of any pipeline success flag.

Each receiver invocation starts a fresh Python process with only the ciphertext image file, key and nonce as semantic inputs; its two output paths are destinations. No sender model object or map survives into that process, no original/source image is loaded by receiver code, and no external payload-length file is read. Ciphertext, recovered image, extracted bits and receiver logs are retained for audit. Expected payload/original arrays exist only in the driver for the **post-decoding comparison**, not as receiver inputs. Test nonces use disjoint counter ranges for the test image sizes.

| Image | Sender prepare incl. inference (s) | Sender embed/encrypt (s) | Receiver incl. model load (s) | Fresh receiver process wall time (s) | Checks | Recovery failures |
| --- | --- | --- | --- | --- | --- | --- |
| Airplane.png | 0.2978 | 0.2400 | 1.8388 | 8.6113 | 4 | 0 |
| Lena.png | 0.6016 | 0.1701 | 1.8707 | 9.6805 | 4 | 0 |
| constant128 | 0.0369 | 0.0137 | 0.2826 | 5.9348 | 4 | 0 |

Sender preparation includes candidate inference, labels and compression; subsequent sender timing uses that prepared data. Receiver timing includes model loading, inference, parsing and restoration; process wall time also includes Python/Torch startup. These are four audit observations per image, not a controlled throughput benchmark. No A throughput is invented because A is undecodable. The tested packet is grayscale; an RGB framing/nonce layout was not prototyped, and no RGB GO is claimed. Installed model/runtime/rounding conventions are shared; cross-platform floating-point reproducibility is not established by these same-host tests.

## Decision and minimum architectural change

- **Original dense code / paper Figure 2: NO-GO** for ciphertext+key+nonce-only decoding. It lacks reproducible contexts, a consistent bit allocation, reversible label storage and length bootstrap.
- **A: NO-GO.** Its exhaustive allocation/original/payload enumeration fails despite perfectly reproducible isolated predictions. No positive uniquely decodable net payload is demonstrated for A.
- **B: conditional GO for the isolated, framed packet on inputs passing the measured budget.** It demonstrates positive net payload and image-only receiver recovery using existing CNN-3×3 weights. It is **NO-GO as an unconditional drop-in replacement covering all images or preserving the old gross BPP**. Baboon/noise rejection is a capacity limitation, not a hidden exception or a claimed recovery pass.

The minimum demonstrated architectural change is to restrict embedding to a deterministic set whose predictor contexts remain unchanged, add an internally parseable label/interval representation and bit-length frame, and reversibly relocate every original bit displaced by that bootstrap. The alternative would require a separately proved invertible block/source code or a causal/multistage reconstruction schedule; the existing noncausal checkpoint cannot simply be rerun on the dense marked image. CNN retraining is not required for the demonstrated restricted B design. A same-sized lossless image representation cannot guarantee positive arbitrary payload for every possible unconstrained original image: this is a counting limitation, not a training problem.

No manuscript correction, novelty assertion, broad benchmark, production integration or training was performed. The fact that a restricted B prototype passes does not validate the rejected diagram or convert historical gross capacities to self-contained net capacities.

## Audit and preservation

All new executable work and evidence are in `self_contained_rdhei_feasibility_20261022/`. `prototype.py` contains the isolated packet/receiver; `run_gate.py` is its driver. Definitive successful data are in `attempt2/protocol.json`, `attempt2/prediction_reproducibility.json`, `attempt2/capacity_measurements.json`, `attempt2/end_to_end_results.json` and `attempt2/model_integrity.json`. Independent checks are `joint_mapless_enumeration.json`, `metadata_math_gate.json`, `bit_allocation_gate.json`, `diagram_zero_payload_witness.json` and `document_audit.json`. Figure 2 is preserved as `paper_page4_image0_Im4.png`.

The initial driver completed and verified its first empty-payload round trip, then stopped on a duplicate logging-key TypeError. This was a harness error after successful decoding, not a recovery failure. Its outputs/log remain preserved. The duplicate key was removed and the full driver reran into the separate `attempt2/` directory without overwriting that first attempt or changing the codec/selection rules. The definitive 12 checks all passed. No failed scientific gate was silently retried with altered parameters.

SHA-256 verification found **1541 pre-existing files, 0 changed or missing**. Historical checkpoints, manuscript files, pipeline sources, experiment artifacts and reports are intact. The CNN-3×3 in-memory state is bitwise unchanged. New output creation and the report do not modify any historical project artifact.
