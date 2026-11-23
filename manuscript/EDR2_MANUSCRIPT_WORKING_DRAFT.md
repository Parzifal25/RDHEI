# EDR2 manuscript package — technical audit and writing plan

**Status: draft in progress; not submission-ready.** This package is intentionally isolated from `main`. It records exactly what can and cannot be claimed from the repository evidence currently inspected.

## Critical decision: establish the EDR2 protocol identity before writing

The repository contains multiple protocol histories. They are not interchangeable. In particular, the 22 October 2026 protocol gate describes a distinct self-contained authenticated reservation protocol. Its protocol document names that design EDR1. Its results (four of six local images accepted, 72,357 total net bits, HMAC checks, receiver-only recovery) must never be attributed to EDR2.

The 21 November 2026 EDR2 report states:
- The EDR2 end-to-end runtime harness exists, but no execution results were found in the inspected repository.
- Historical EDR2 243-image capacity summary (163/243 positive, signed mean 0.11054 bpp, pooled 0.05982 bpp, usable mean 0.14322 bpp) is provisional until raw CSV/JSON is reconciled.
- The original EDR2 AES-CTR path has no authentication/integrity protection; AES-CTR alone cannot detect tampering.
- A matched EDR2 side-information/storage baseline was not verified.
- EDR2 multi-resolution runtime/scalability results were not verified.

Therefore, no claim of EDR2 HMAC authentication, in-band authenticated metadata, parser-fuzz success, 978 exact recovery trials, or 512/1024/2048 resolution scalability should enter the paper unless a separate EDR2-specific source artifact directly proves it. The previous draft-level summaries are not enough to override this repository audit.

## Exact manuscript improvements required

| Priority | Improvement | Exact action | Why it matters |
|---|---|---|---|
| P0 | Freeze protocol identity | Write a one-page EDR2 protocol contract from the EDR2 implementation and tests; enumerate sender, hider, receiver inputs, operation order, stored/transmitted fields, keys/nonces, and recovery dependencies. | Current repo has conflicting protocol histories. |
| P0 | Reconcile capacity | Recompute every aggregate from the final EDR2 per-image raw CSV/JSON; publish formula, denominator, failed/zero/negative entries, accepted fraction and all-image vs accepted-only means. | Historical EDR2 numbers are marked provisional. |
| P0 | Correct security claims | Unless EDR2-specific AEAD/MAC code and tests are found, describe AES-CTR as confidentiality-only. Explicitly state integrity/tamper detection are not provided. | CTR is malleable and unauthenticated. |
| P0 | Distinguish gross from net payload | Include every recovery-map, phase, header, directory, authentication, bootstrap/backup and framing bit in the budget exactly once. | Gross capacity is not a fair usable payload metric. |
| P0 | Remove unsupported results | Remove EDR1 measurements and any EDR2 numbers whose raw artifact is not cited. | Prevents false attribution and irreproducible claims. |
| P1 | Clarify geometric proposition | State the receptive-field radius, mutable-center set, Chebyshev separation, border convention and proof that no mutable center enters another candidate's masked input. | This is a plausible narrow technical contribution, but must match actual EDR2 code. |
| P1 | Prove decoder uniqueness | Give the complete label/interval definition and prove exactly one original sample satisfies the residue and prediction interval for every supported class. | Exact reversibility depends on uniqueness, not merely successful sample trials. |
| P1 | Separate predictor experiments | Keep the 3×3 vs MED/GAP/CALIC study (step-4/16-phase grid) separate from the native EDR2 step-2/four-phase protocol. Label the 5×5 no-weighted-loss ablation accurately. | Prevents non-matched comparisons. |
| P1 | Compare external methods cautiously | Use Multi-MSB+Huffman and corrected PPMR only as native-protocol same-corpus replications; disclose all compatibility changes and different packet/metadata/security assumptions. | Do not present as a same-protocol leaderboard. |
| P1 | Add complexity limitations | Report parameter count, MACs, predictor-only time, full pipeline time, hardware/software, warmups, repetitions and RSS scope. | CNN is materially slower than classical predictors. |
| P2 | Demote RGB | Put the 51-image exploratory study in a clearly labelled subsection or supplement; do not imply a mature RGB protocol unless the complete receiver contract is established. | Sparse positive outcomes do not support a broad RGB claim. |
| P2 | Journal-specific formatting | Only after technical audit, adapt abstract length, section order, figures and references to the selected journal. | Premature formatting causes rework. |

## Manuscript structure and required content

### Title (working)
**Context-Invariant Prediction and Overhead-Aware Phase Selection for Reversible Data Hiding in Encrypted Images**

Use this title only if the EDR2 implementation confirms the step-2 masked 3×3 grid and four-phase selection described in the current EDR2 draft. Do not put “authenticated” in the title unless that property is verified in EDR2.

### Abstract
Write only after P0. Use this order:
1. The specific RDHEI problem: prediction-based recovery can fail when embedding changes samples in another candidate's predictor receptive field.
2. The EDR2 construction: masked radius-one CNN predictor; mutually non-interfering step-2 candidate phases; explicit owner-side phase scoring after recovery-information overhead.
3. Protocol statement: who embeds when, what the receiver needs, and whether metadata is in-band or side-channel.
4. Exact dataset and sample count, source hashes, and the accepted/positive-capacity fraction.
5. Net capacity metrics with a fully defined denominator; exact recovery test count and independent comparison method.
6. Runtime and known limitations.
7. No SOTA/superiority claim unless a genuinely matched protocol benchmark supports it.

### 1. Introduction
- Define RDH and RDHEI and distinguish reversibility of the cover from extraction of the payload.
- Explain prediction-context synchronization as the specific problem.
- Explain why geometric non-interference is useful: it makes prediction reproducible after candidate modifications.
- State the research questions, not inflated claims.
- End with precise contributions and a “not claimed” paragraph.

### 2. Related work
Organise by technical problem, not paper-by-paper chronology:
- RDH foundations and prediction-error methods.
- RDHEI architectures: vacating room before encryption, reserving room before encryption, and separable/non-separable receiver arrangements.
- Prediction-based encrypted-domain schemes and compressed auxiliary maps.
- Learned predictors and CNN-based RDHEI.
- Candidate scheduling, checkerboard/lattice sampling and predictor-context preservation.
- Integrity/authentication in RDHEI and limits of unauthenticated encryption.
- Capacity accounting and reproducibility.

For each work, state: input domain; encryption order; predictor; recovery side information; map compression; integrity protection; capacity definition; dataset. Do not compare bpp unless definitions are aligned.

### 3. Problem formulation and threat model
Specify:
- Image domain and dimensions, bit depth and border handling.
- Exact encoder/hider/receiver roles and their knowledge.
- Key generation and nonce uniqueness assumptions.
- Adversary capabilities and whether the hider is trusted.
- Whether integrity, authenticity, confidentiality and exact recovery are each properties actually delivered.
- What the paper does not claim.

### 4. EDR2 method
- Fixed CNN architecture and checkpoint provenance.
- Masked receptive-field input and deterministic rounding.
- Step-2 lattice and four phase definitions.
- Formal non-interference theorem, with assumptions and proof.
- Predictor output to error class and interval assignment.
- Candidate directory representation and lossless coding.
- Phase scoring objective, including every overhead term and deterministic tie-break.
- In-band framing or external inputs; exact byte/bit layout.
- Encoder, hider and receiver pseudocode.
- Formal inverse/recovery proof.
- Complexity analysis.

### 5. Experimental protocol
- Dataset provenance, exact filenames, source hashes, pixel hashes, image dimensions and exclusions.
- Hardware, OS, Python and package versions.
- Frozen checkpoint hashes and model settings.
- Predictor comparison protocol (step-4/16 phases) separated from native EDR2 protocol.
- External baseline reproduction environment and compatibility patches.
- Capacity formula, all denominators, aggregation rules, confidence interval method and clustering.
- Exact recovery, wrong-key, mutation and parser tests; report only tests actually run on EDR2.
- Runtime measurement protocol.

### 6. Results
Keep separate:
- Native EDR2 end-to-end net payload and acceptance coverage.
- Prediction-only study.
- CNN ablations.
- External native-protocol replication.
- RGB exploratory results.
- Runtime and memory.
- EDR2 security/error tests.

Do not combine predictor-only “bpp” with net EDR2 payload. Show zero and rejected cases; do not calculate accepted-only means without simultaneously reporting coverage.

### 7. Discussion
- Explain why EDR2 capacity is lower than reproduced external methods without obscuring the result.
- Explain trade-offs between invariance, predictor context and candidate density.
- Discuss CNN runtime penalty.
- Discuss image-dependent overhead and negative-capacity cases.
- Discuss baseline protocol differences.
- Discuss generalisation and dataset provenance limits.

### 8. Limitations and conclusion
State limitations as observed, not as future work that silently implies solved capabilities. Conclude on the exact verified construction and evidence.

## Literature screening: retrieved and reviewed records

Consensus literature search returned the following relevant candidates. Search records were fetched before use. The metadata displayed by Consensus did not provide DOI for these records, so the references below are discoverable links, not yet DOI-verified citations. Scite MCP was unavailable because the account has no active paid plan/trial, and Consensus research-agent mode was blocked by monthly allowance. Do not claim Scite citation-context analysis or a completed deep Consensus review.

1. Puteaux, P., Ong, S., Wong, K.-S., & Puech, W. (2021). [A survey of reversible data hiding in encrypted images – The first 12 years](https://consensus.app/papers/details/w:7f4f5ab3-39da-47e9-add3-ab7707a6d0aa/). *Journal of Visual Communication and Image Representation*, 77, 103085. Cited by 80 in Consensus metadata. Use as a broad RDHEI taxonomy entry; verify DOI and full text before final use.
2. Shi, Y.-Q., Li, X., Zhang, X., Wu, H.-T., & Ma, B. (2016). [Reversible data hiding: Advances in the past two decades](https://consensus.app/papers/shi-li-reversible-data-hiding-advances-in-the-past-two/w:e1458200-8385-4fec-9cdf-1895da25dcc6/). *IEEE Access*, 4, 3210–3237. Cited by 622 in Consensus metadata. General RDH survey, not an RDHEI-specific primary method.
3. Yin, Z., Peng, Y., & Xiang, Y. (2020). [Reversible Data Hiding in Encrypted Images Based on Pixel Prediction and Bit-plane Compression](https://consensus.app/papers/yin-peng-reversible-data-hiding-in-encrypted-images-based/w:4f27484e-6367-4d81-a543-5df37e00d91b/). *IEEE Transactions on Dependable and Secure Computing*, 19, 1–1 (metadata may be early-online; verify final pagination). Consensus abstract indicates prediction-error bit-plane rearrangement/compression and multi-LSB substitution after encryption.
4. Ren, H., Bai, G., Chen, T., Yue, Z., & Ren, R. (2023). [Reversible data hiding in encrypted images with multi-prediction and adaptive Huffman encoding](https://consensus.app/papers/ren-bai-reversible-data-hiding-in-encrypted-images-with/w:3e897943-7a59-47d9-bbd9-eed2dee5c96b/). *Scientific Reports*, 13, 23104. Search result reports MED+GAP multi-prediction and Huffman-compressed labels embedded before payload room use. This is directly relevant prior art for predictor plus compressed auxiliary labels.
5. Ping, P., Huo, J., & Guo, B. (2024). [Novel asymmetric CNN-based and adaptive mean predictors for reversible data hiding in encrypted images](https://consensus.app/papers/ping-huo-novel-asymmetric-cnnbased-and-adaptive-mean/w:c5dc0042-3cf0-4be3-921f-ec639cff4aa0/). *Expert Systems with Applications*, 246, 123270. CNN predictor in RDHEI is established prior art. Abstract not exposed in fetched record; inspect full publisher text before specifying its exact mechanics.
6. Ren, F., Zhang, Z., Jiang, K., Zhang, P., & Yang, T. (2025). [Reversible data hiding and authentication scheme for encrypted image based on prediction error compression](https://consensus.app/papers/ren-zhang-reversible-data-hiding-and-authentication-scheme/w:0c2885eb-c3bd-4739-a054-517fc6f13719/). *Scientific Reports*, 15, 11636. The retrieved abstract describes ISGAP prediction, adaptive Huffman error coding and plaintext/ciphertext authentication. This establishes relevant authentication prior art; do not conflate it with EDR2's AES-CTR path.
7. Qiu, Y., Peng, W., & Lin, X. (2025). [Improved CNN Prediction Based Reversible Data Hiding for Images](https://consensus.app/papers/qiu-peng-improved-cnn-prediction-based-reversible-data/w:4c865956-cb6c-472e-8307-a5d391dcfb5a/). *Entropy*, 27, 159. This is RDH rather than necessarily RDHEI; its Circle/Square split and CNN prediction/complexity maps demonstrate learned prediction and partitioned context are established beyond RDHEI.
8. Sui, L., Li, H., Liu, J., Xiao, Z., & Tian, A. (2023). [Reversible Data Hiding in Encrypted Images Based on Hybrid Prediction and Huffman Coding](https://consensus.app/papers/sui-li-reversible-data-hiding-in-encrypted-images-based/w:748a564a-b278-436a-8f1d-5aa77595ac6d/). *Symmetry*, 15, 1222. Retrieved abstract describes hybrid prediction, MSB vacancy and Huffman tag-map coding.

**Important literature limitation:** These search records identify prior art but are not enough for a novelty claim about a particular lattice or formal non-interference condition. Run targeted citation chasing and read full text for the closest methods; search specifically for “checkerboard prediction”, “quincunx/checkerboard lattice”, “context invariant prediction”, “masked CNN pixel prediction”, and “RDHEI CNN asymmetric predictor”. Scite must verify the final DOI/reference set before submission. Consensus Pro research-agent mode can be retried when the monthly allowance resets on 1 December 2026.

## Exact remaining evidence tasks

### Must complete before manuscript is called complete
- [ ] Identify the exact EDR2 protocol implementation path/commit and freeze its code hash.
- [ ] Identify the exact EDR2 final evaluation directory and raw per-image CSV/JSON; reconcile all 243-image figures or remove them.
- [ ] Confirm whether current EDR2 code genuinely implements in-band framing, phase metadata, HKDF key domains, HMAC and receiver authentication. The 21 Nov report says original EDR2 AES-CTR has no authentication; therefore this check is mandatory.
- [ ] Confirm whether 978 receiver trials are EDR2-specific, what each trial means, and whether source-image and extracted-payload comparisons were independent.
- [ ] Verify the capacity equation from the actual EDR2 sender and receiver code, including every overhead.
- [ ] Confirm baseline raw artifacts and exact source/pixel hash matches for Multi-MSB+Huffman and PPMR; preserve the four disclosed PPMR compatibility changes.
- [ ] Confirm runtime harness results, or omit performance claims beyond measured predictor-only results.
- [ ] Verify all bibliography records and DOI, publication details, corrections and retractions.

### Do not do
- Do not retrain or fine-tune checkpoints.
- Do not run speculative capacity calibration or tune against held-out images.
- Do not add EDR1 protocol results to EDR2.
- Do not claim superiority over SOTA based on different native protocols.
- Do not describe AES-CTR as authenticated encryption.
- Do not call a source “Scopus indexed” without checking the journal's current coverage and year.

## Acceptance test for a submission-ready manuscript
A section is accepted only when every quantitative claim points to a committed raw evidence artifact; every protocol claim matches the corresponding implementation; every citation has verified bibliographic metadata and supports the sentence; and limitations are stated at the same prominence as the positive results. The work is not submission-ready until all P0 items above are resolved.
