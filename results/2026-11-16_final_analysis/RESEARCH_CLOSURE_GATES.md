# Research closure gates before manuscript freeze

Branch: `research/edr2-runtime-optimization`

This file records evidence gates, not manuscript claims. A gate is not passed by a literature-only comparison, a source review, or a unit test when its acceptance criterion requires a system experiment or independent reviewer.

## Gate 1 — strongest CNN predictor

**Current status: partially addressed; full-system selection pending.**

Matched predictor evaluation: all predictors were tested on the same 243-image grayscale corpus using the same step-4 / 16-phase lattice. Within the tested CNN ablations, v3 (5x5 residual, without weighted loss) has the lowest reported MAE (4.6233) and highest positive-capacity count (140/243). v4 (3x3 residual) has MAE 4.8130 and 133/243 positive cases in that matched geometry. v4 has 46,881 parameters, versus 112,417 for v3.

These results do not establish that v3 is the best full EDR2 predictor. Its 5x5 receptive field has radius 2; it cannot use the current step-2 / four-phase production geometry without risking prediction-context interference. An isolated full-system experiment has therefore been added for v3 with a step-3 / nine-phase lattice and a two-pixel border. This is experimental geometry and is not a production wire-format change.

### Gate 1 full-system v3 result (2026-11-17)

The complete 243-image v3 safe-geometry job passed in [run 44054088540](https://github.com/Parzifal25/RDHEI/actions/runs/44054088540), job `v3-safe-lattice-experiment`, artifact `14315159838`. The overall workflow is marked failed because its separate complexity step used the earlier benchmark script revision with the missing-`sys` defect; the v3 job itself concluded success.

- v3 checkpoint SHA-256: `1fa025e252d5a3c95509ab1a8321e0b46ca72aa083161c2e9b8c30c2ab5e5c41`.
- Geometry: step 3, nine phases, two-pixel border, 5x5 receptive radius 2.
- Positive images: 153/243 (62.96%).
- Mean signed net bpp over all images: 0.0499319; positive-only mean: 0.1032192; positive-only median: 0.0676651.
- Prediction invariance passed 243/243 images.
- Exact image and payload recovery passed 765/765 trials (five payload lengths per positive image).
- The run is explicitly experimental; its nine-phase packets are not compatible with the production four-phase EDR2 receiver.

Interpretation: v3 remains the strongest tested checkpoint by matched predictor MAE, but its geometry-safe full-system capacity is lower than the previously validated v4 production configuration (v4: 163/243 positive, mean signed net bpp 0.059821; 978/978 exact trials). Because the geometry differs, present these as system-configuration outcomes, not a controlled single-variable ablation. Retain v4 for the current system unless a better safe geometry or a separately authorised trained model demonstrates a stronger full-system result.

No retraining was launched; the prior retraining/calibration investigation records that retraining was stopped on the user's instruction and is prohibited unless that instruction is explicitly superseded.

**Pass criteria:**
- Reproduce v3-v4 prediction metrics on one hash-pinned native corpus.
- Run each model using geometry safe for its actual receptive radius.
- Compare full-pipeline signed net capacity (including all directory, header, HMAC, bootstrap backup and opportunity costs), positive-image count, exact image/payload recovery, CPU time and memory.
- Freeze one model/geometry pair only after the matched full-system evidence is reviewed.
- Report other CNN variants and classical predictors; do not call v4 the best predictor solely because it is compact.

## Gate 2 — CPU execution speed

**Current status: open; baseline weakness confirmed; exact-equivalence sweep running.**

Exact-equivalence sweep results (two independent workflow runs, 512x512, one phase / 65,025 patches, 1 warmup + 3 timed repeats):
- Patch construction: legacy 45.36 ms vs vectorized 2.64 ms in run 44055399791; repeat 69.09 ms vs 3.16 ms in run 44055419609.
- Best tested setting: 2 CPU threads, batch 2,048. Inference means varied from 73.57 ms to 126.93 ms across the two hosted runs; the legacy 4-thread/2,048 setting measured 144.92 ms and 161.00 ms.
- Across every candidate configuration: patch arrays matched exactly; maximum raw prediction delta was 0.0; rounded prediction mismatches were zero.
- Checkpoint remained the same frozen v4 SHA-256: `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`.

The vectorized extractor and two-thread setting have been applied on the research branch only. The exact-output microbenchmark confirms zero raw prediction deltas and zero rounded prediction mismatches. A corrected 10-repeat native-image E2E benchmark then completed successfully in [run 44056835389](https://github.com/Parzifal25/RDHEI/actions/runs/44056835389), artifact `14316686389`:
- Same native 512x512 USC-SIPI image (5.2.08.tiff), same v4 checkpoint, two warmups, ten measured repeats, CPU and actual two PyTorch threads.
- Mean complete pipeline: 1.114019 s (SD 0.058079, median 1.120437 s); 2.25x faster / 55.55% less elapsed time than the earlier 2.506018 s baseline on the same image. This is a combined patch-vectorization and thread-configuration comparison, not an isolated causal estimate for one change.
- Preparation mean 0.582318 s; reserve/encrypt 0.070166 s; embed/authenticate 0.043262 s; receiver/extract/recover 0.418273 s.
- All 10 full-capacity payload trials recovered the image and payload exactly; unique benchmark nonces; 39,655 payload bits (0.151272 bpp).
- Sampled RSS baseline 392.51 MiB, peak 403.38 MiB, incremental peak 10.87 MiB.
- The earlier 0.787740 s run report was superseded because its benchmark metadata incorrectly stated four threads; the corrected run reports the actual two-thread model configuration.

The complete 243-image exact-recovery audit on the optimized predictor branch remains a separate active job in [run 44056245803](https://github.com/Parzifal25/RDHEI/actions/runs/44056245803). Do not close the regression gate until that job succeeds and its artifact is inspected.

Existing native 512x512 EDR2 end-to-end measurement: mean 2.5060 s over 10 repeats (SD 0.1036 s), including preparation, reservation/encryption, data-hider embedding/authentication, and receiver authentication/extraction/recovery. This was measured on one USC-SIPI image, not across the corpus.

Previous 512x512 predictor benchmarks show CNN-v4 substantially slower than MED and with run-to-run instability. A new benchmark sweep compares the existing patch extraction with vectorized extraction, batch sizes 1,024–32,768, and CPU thread counts 1, 2 and 4. It requires patch arrays to be exactly equal and floating predictions to agree within a stated tolerance, with zero rounded-pixel mismatches.

**Pass criteria:**
- Identify the fastest setting that preserves exact patch arrays and rounded predictions.
- Apply only semantically equivalent inference changes.
- Re-run grayscale and RGB protocol regression tests, full native EDR2 exact-recovery tests, and the 10-repeat end-to-end benchmark.
- Publish mean, median, standard deviation, peak RSS and machine/CPU/software details.
- Do not describe a faster patch microbenchmark as an end-to-end speedup until the full pipeline is remeasured.

### Gate 1 current experiment status (2026-11-17)

The isolated v3 step-3 / nine-phase native experiment has been added and its workflow has successfully compiled the harness, acquired the native USC-SIPI corpus, and built the 243-image allowlist. The 243-image full-system run was still in progress at the latest status check: [run 44054088540](https://github.com/Parzifal25/RDHEI/actions/runs/44054088540). Do not select v3 based only on the matched step-4 predictor table; wait for the net-capacity and exact-recovery report under the safe geometry.

## Gate 3 — external RDHEI comparisons

**Current status: open; relevant papers and repositories identified; head-to-head reproduction not complete.**

A first pass of implementation discovery found author code for ACNNP and public repositories for 2020/2023 bit-plane methods. The ACNNP author repository and both MATLAB implementation repositories have no declared GitHub licence; do not reuse/redistribute their code without permission. BCAGC and PLMAE official implementations were not located. This is still literature/repository due diligence, not a head-to-head comparison.

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

Both grayscale and RGB parser targets now have 20,000-input authenticated/coverage-guided fuzz runs with no crash reported. RGB: 20,000 runs in 14 seconds, 123 coverage counters, [run 44054823526](https://github.com/Parzifal25/RDHEI/actions/runs/44054823526), artifact `14315551603`. This closes an internal finite fuzzing task, not the independent audit.

The reviewer scope and threat model are in `INDEPENDENT_CRYPTO_REVIEW_SCOPE.md`. Existing evidence includes deterministic malformed packet tests and 20,000 grayscale Atheris inputs from an earlier successful run. An authenticated RGB parser fuzz target has been added; its run must pass and its artifact be inspected.

**Pass criteria:**
- An independent cryptographic engineer reviews a frozen commit and the complete threat model.
- Written findings include severity, reproducible evidence, fixes, retest results and residual risks.
- Critical/high findings are fixed or formally accepted.
- Reviewer identity, qualifications, review date and commit hash are recorded.
- No independent-audit claim is made before this deliverable exists.

## Paper-start rule

Do not start the results/manuscript draft as if all four gates passed while any gate above is open. Background literature organization and method documentation may be prepared separately, but quantitative claims and final novelty positioning must wait for the matched system comparison, CPU remeasurement, external baselines and independent review status.


---

## User-directed closure decision — 2026-11-17

**Model/training constraint:** Existing trained checkpoints are frozen. No retraining, fine-tuning, or checkpoint replacement is authorised. All comparison work below must use the already-trained checkpoints and paper-derived or permission-cleared external baselines.

### Gate 3 — fair external RDHEI comparison

**Status remains OPEN.** The current repository's full-corpus grayscale comparator is useful but is not an external SOTA reproduction. It compares MED, GAP, simplified CALIC-style prediction, five frozen CNN checkpoints and a histogram-shifting reference on one 243-image USC-SIPI corpus. The predictor comparison uses a common step-4 / 16-phase experiment geometry. These numbers must not be relabelled as comparisons against ACBP, ACNNP, PLMAE, BCAGC or the published bit-plane coding papers.

The literature review file `EDR2_LITERATURE_COMPARISON.md` records the published methods, their original datasets and rate definitions, and why their headline bpp values are not directly comparable to EDR2's signed net payload capacity. In particular:
- ACNNP and two MATLAB bit-plane repositories have no declared licence; do not copy or redistribute their code without author permission.
- Official PLMAE and BCAGC implementations have not been located in the current due diligence.
- ACBP must be assessed at its reversible setting (epsilon=1); its lossy epsilon=255 result is not a reversible baseline.
- The 2020/2023 bit-plane methods can be independently reimplemented from their papers or tested after permission is obtained, but their repository code should not be presumed reusable.

**Fair-comparison acceptance:** At least one strong external reversible baseline must be independently reproduced on identical decoded pixels, with method-native preprocessing disclosed, all metadata and recovery costs counted consistently, and exact image + payload recovery verified. Publish paired per-image results and failures. Until that exists, external-SOTA superiority remains unsupported.

### Gate 4 — independent cryptographic audit

**Status remains OPEN — external reviewer required.** The refreshed audit brief now targets frozen commit `bb5a8c0672a4ae58340edc641cbb6a9260d9f820` on this branch and explicitly prohibits retraining. It includes the grayscale/RGB protocol files, threat model, nonce/key lifecycle, HMAC coverage, parser/decompression checks, replay, malicious-hider trust and expected written findings. See `INDEPENDENT_CRYPTO_REVIEW_BRIEF.md`.

New internal evidence: the optimized research-branch native grayscale final audit and regression job passed in [run 44056245803](https://github.com/Parzifal25/RDHEI/actions/runs/44056245803); RGB authenticated parser fuzzing completed 20,000 inputs without a reported crash in [run 44054823526](https://github.com/Parzifal25/RDHEI/actions/runs/44054823526). These tests strengthen implementation evidence; they are not an independent audit, proof or certification.

**Audit acceptance:** A named independent cryptographic engineer reviews the frozen commit and supplies a dated written report with scope, qualifications, severity-ranked reproducible findings, remediation/retest results and residual risks. Critical/high findings must be fixed or formally accepted. Do not call this gate passed before that report exists.

### Closure rule

The two requested gates cannot honestly be marked complete by internal code changes alone. Gate 3 requires permission-cleared or independently reproduced external methods and matched data. Gate 4 requires a qualified person outside the project implementation team. No retraining is needed for either gate, and none is to be launched. Once both acceptance criteria are met, freeze the evidence and begin final manuscript writing.
