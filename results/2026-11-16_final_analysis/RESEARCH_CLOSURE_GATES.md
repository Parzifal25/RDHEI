# Research closure gates before manuscript freeze

Branch: `research/edr2-runtime-optimization`

This file records evidence gates, not manuscript claims. A gate is not passed by a literature-only comparison, a source review, or a unit test when its acceptance criterion requires a system experiment or independent reviewer.

## Gate 1 — strongest CNN predictor

**Current status: partially addressed; full-system selection pending.**

Matched predictor evaluation: all predictors were tested on the same 243-image grayscale corpus using the same step-4 / 16-phase lattice. Within the tested CNN ablations, v3 (5x5 residual, without weighted loss) has the lowest reported MAE (4.6233) and highest positive-capacity count (140/243). v4 (3x3 residual) has MAE 4.8130 and 133/243 positive cases in that matched geometry. v4 has 46,881 parameters, versus 112,417 for v3.

These results do not establish that v3 is the best full EDR2 predictor. Its 5x5 receptive field has radius 2; it cannot use the current step-2 / four-phase production geometry without risking prediction-context interference. An isolated full-system experiment has therefore been added for v3 with a step-3 / nine-phase lattice and a two-pixel border. This is experimental geometry and is not a production wire-format change.

**Pass criteria:**
- Reproduce v3-v4 prediction metrics on one hash-pinned native corpus.
- Run each model using geometry safe for its actual receptive radius.
- Compare full-pipeline signed net capacity (including all directory, header, HMAC, bootstrap backup and opportunity costs), positive-image count, exact image/payload recovery, CPU time and memory.
- Freeze one model/geometry pair only after the matched full-system evidence is reviewed.
- Report other CNN variants and classical predictors; do not call v4 the best predictor solely because it is compact.

## Gate 2 — CPU execution speed

**Current status: open; baseline weakness confirmed; exact-equivalence sweep running.**

Existing native 512x512 EDR2 end-to-end measurement: mean 2.5060 s over 10 repeats (SD 0.1036 s), including preparation, reservation/encryption, data-hider embedding/authentication, and receiver authentication/extraction/recovery. This was measured on one USC-SIPI image, not across the corpus.

Previous 512x512 predictor benchmarks show CNN-v4 substantially slower than MED and with run-to-run instability. A new benchmark sweep compares the existing patch extraction with vectorized extraction, batch sizes 1,024–32,768, and CPU thread counts 1, 2 and 4. It requires patch arrays to be exactly equal and floating predictions to agree within a stated tolerance, with zero rounded-pixel mismatches.

**Pass criteria:**
- Identify the fastest setting that preserves exact patch arrays and rounded predictions.
- Apply only semantically equivalent inference changes.
- Re-run grayscale and RGB protocol regression tests, full native EDR2 exact-recovery tests, and the 10-repeat end-to-end benchmark.
- Publish mean, median, standard deviation, peak RSS and machine/CPU/software details.
- Do not describe a faster patch microbenchmark as an end-to-end speedup until the full pipeline is remeasured.

## Gate 3 — external RDHEI comparisons

**Current status: open; relevant papers and repositories identified; head-to-head reproduction not complete.**

Priority methods:

| Method | Published source | Comparison requirement / blocker |
|---|---|---|
| ACBP / PRDHEI | Yi & Zhou, Signal Processing (2018), DOI [10.1016/j.sigpro.2018.04.016](https://doi.org/10.1016/j.sigpro.2018.04.016) | Reproduce ε=1 for full reversibility. The often-quoted 4.5 bpp corresponds to ε=255, where image recovery is lossy; it is not a reversible-rate result. No official implementation was located in this search. |
| Asymmetric CNN + adaptive mean (ACNNP) | Ping et al., ESWA (2024), DOI [10.1016/j.eswa.2024.123270](https://doi.org/10.1016/j.eswa.2024.123270) | Author-linked repository [Hohai-PingPing/ACNNP](https://github.com/Hohai-PingPing/ACNNP) contains an archive (`ACNNP.zip`) and trained model, but no repository licence is declared. Need to establish permission, extract the code, validate its test path, and reproduce on the same input pixels. Published BOSSBase rate is 3.461 bpp; not directly comparable to current USC-SIPI EDR2 results. |
| Pixel-level masked autoencoder + polar code (PLMAE) | Cheng et al., Signal Processing (2025), DOI [10.1016/j.sigpro.2024.109664](https://doi.org/10.1016/j.sigpro.2024.109664) | A VRAE method, unlike EDR2's reserve-room-before-encryption pipeline. No official implementation located. Need an author/code release or faithful implementation from the paper, with protocol family and cost accounting kept explicit. |
| Pixel prediction + bit-plane compression | Yin et al., IEEE TDSC (2022), DOI [10.1109/TDSC.2020.3019490](https://doi.org/10.1109/TDSC.2020.3019490) | Public MATLAB repository exists: [edu-yinzhaoxia implementation](https://github.com/edu-yinzhaoxia/Reversible-Data-Hiding-in-Encrypted-Images-Based-on-Pixel-Prediction-and-Bit-plane-Compression). No repository licence found. Reimplement from the paper or obtain permission before reuse. |
| Global zero-valued high-bit-plane compression + block rearrangement | Yao et al., IEEE TMM (2023), DOI [10.1109/TMM.2023.3314975](https://doi.org/10.1109/TMM.2023.3314975) | Public MATLAB repository [wangke517 implementation](https://github.com/wangke517/RDH-EI-Using-Global-Compression-of-Zero-valued-High-Bit-planes-and-Block-Rearrangement). No repository licence found. Need a permission-compliant reproduction or independent implementation. |
| Bit-plane classification + adaptive group coding (BCAGC) | Zhou & Li, IET Information Processing (2026), DOI [10.1049/ipr2.70310](https://doi.org/10.1049/ipr2.70310) | Recent strong published baseline; reported averages 4.1472 BOSSbase, 4.0565 BOWS-2 and 3.4465 UCID bpp. No public implementation located. Must reproduce before claiming head-to-head superiority. |
| Dual-stage bit-plane compression + CP-ABE | Peng et al., Scientific Reports (2026), DOI [10.1038/s41598-026-65778-w](https://doi.org/10.1038/s41598-026-65778-w) | Recent RRBE baseline. Need same-corpus, same-overhead comparison; no implementation located in this search. |

Published rates above are context only. Dataset, operating mode (RRBE/VRAE/CRBE), payload construction, metadata accounting, and exact-recovery criteria differ. None of these rates establishes an apples-to-apples result against EDR2.

**Pass criteria:**
- Reproduce at least the accessible direct RRBE bit-plane baselines (2020 and 2023) and the ACNNP method, or document why reproduction is infeasible and seek author-provided outputs/code.
- Reproduce ACBP at ε=1 and account for its reversible mode separately from lossy parameter settings.
- Include PLMAE as a distinct VRAE comparison; do not conflate protocol families.
- Evaluate on the same decoded pixel arrays where compatible, disclose image-set exclusions, and provide exact recovery for every claimed reversible method.
- Include all overheads when the method permits them to be counted: prediction/label maps, coding tables, bootstrap, headers, authentication and backup.
- Compare capacity distributions per image, not only mean bpp; report positive-image coverage and failures.

## Gate 4 — independent cryptographic audit

**Current status: pending external reviewer. Internal security evidence has been expanded, but this gate cannot be self-certified.**

The reviewer scope and threat model are in `INDEPENDENT_CRYPTO_REVIEW_SCOPE.md`. Existing evidence includes deterministic malformed packet tests and 20,000 grayscale Atheris inputs from an earlier successful run. An authenticated RGB parser fuzz target has been added; its run must pass and its artifact be inspected.

**Pass criteria:**
- An independent cryptographic engineer reviews a frozen commit and the complete threat model.
- Written findings include severity, reproducible evidence, fixes, retest results and residual risks.
- Critical/high findings are fixed or formally accepted.
- Reviewer identity, qualifications, review date and commit hash are recorded.
- No independent-audit claim is made before this deliverable exists.

## Paper-start rule

Do not start the results/manuscript draft as if all four gates passed while any gate above is open. Background literature organization and method documentation may be prepared separately, but quantitative claims and final novelty positioning must wait for the matched system comparison, CPU remeasurement, external baselines and independent review status.
