# No-retraining capacity calibration investigation

Date: 2026-10-22. **Decision: NO-GO for the tested scalar calibration.** Identity wins calibration; no nonzero offset qualifies for deployment. Held-out hard BPP and MAE are unchanged. This is a small exploratory negative result, not proof that every possible fixed-weight correction must fail. No novelty or final scientific performance improvement is claimed.

## Aborted retraining experiment

The host trainer `python3 -u capacity_experiment_20261022/train.py` (PID 3523978) was sent SIGINT on the user's instruction. It exited with `KeyboardInterrupt` during the next training epoch after seven fully logged epochs of A_seed44. A subsequent host process check found no matching trainer. No SIGKILL, checkpoint deletion, checkpoint replacement, resume, or further training launch occurred.

| Run | Status | Completed epochs logged |
| --- | --- | --- |
| A_seed42 | completed | 20 |
| A_seed43 | completed | 20 |
| A_seed44 | interrupted | 7 |
| B_seed42 | not_started | 0 |
| B_seed43 | not_started | 0 |
| B_seed44 | not_started | 0 |

A_seed42 and A_seed43 have their original `complete.json` records and 20 epoch rows each. A_seed44 has seven rows, no completion record, and checkpoints from epochs 1, 2 and 5; progress within its interrupted epoch was not saved as a new checkpoint. All original logs, manifests, checkpoints and selection records remain in place. **The A/B retraining comparison is ABORTED; all its partial results are EXPLORATORY ONLY.** There is no completed B arm and no valid arm comparison. Interruption was a change in requirements, not an observed scientific failure of an arm. The separate authoritative status overlay is `no_retraining_capacity_calibration_20261022/aborted_retraining_status.json`; historical manifests were not rewritten.

## Frozen checkpoint and separation

Only existing `models/v4_patch3.pth` was loaded: CNN-3×3, residual enabled, 46,881 parameters. SHA-256: `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`. All new code and evidence are under `no_retraining_capacity_calibration_20261022/`; nothing is written to the abandoned experiment or historical results/manuscript/pipeline.

The model ran in evaluation/inference mode, gradients globally disabled, all parameters frozen. There were no backward passes, optimizer steps, fine-tuning, training or checkpoint saves in this investigation. The in-memory model state was compared bitwise before/after. PyTorch 2.14.0+cu130, NumPy 2.2.6, CPU with four Torch threads.

## Exact-recovery constraints and map audit

For original pixel x, integer predictor p, and n overwritten upper bits, surviving residue is `x mod s`, where `s=2^(8−n)`. Given the stored error interval [a,b], recovery is valid exactly when:

`{c in [0,255]: c mod s = x mod s and a <= abs(c-p) <= b} = {x}`.

Payload changes only the upper bits, so this condition covers every payload word, not just a random payload. Independent enumeration of all **65,536** (x,p) pairs verified zero missing originals, zero non-unique sets for embedded pixels, and zero recovery failures using the existing receiver's pixel routine. The scalar map and vectorized map remain unmodified.

The exact map is: e=0 gives n=7; e=2^k (k=0…6) gives n=6−k; integers `2^k < e < 2^(k+1)` give n=7−k; e>=128 gives n=0. The k=0 open interval is empty. This map is non-monotone, for example n(2)=5 but n(3)=6; MAE alone cannot measure capacity.

For open bands, spacing is s=2^(k+1). Two same-side admissible candidates differ by less than s. Two opposite-side candidates have summed distances strictly between s and 2s, hence cannot differ by a multiple of s. Singleton power-of-two bands need spacing strictly larger than 2e to avoid the ±e collision. The audit records a concrete extra-bit collision for every nonzero existing band, including e=64 (x=0,p=64 would collide with 128 if one MSB were replaced).

**Scope of maximality:** the assigned n is maximal as a uniform assignment over each existing nonzero band and all possible x,p. A separate exhaustive check (`per_error_maximality.json`) also tested each e=0…127 independently, considering all feasible x,p and n=1…8 with that error's existing interval: every e=1…127 already has its maximum uniform valid n. It need not be maximal for an individual boundary pixel or with richer side information. At e=0, n=8 is mathematically recoverable from p alone, while the existing map caps n at 7. For e>=128, the current alphabet supplies no qualifying recovery interval and uses pass-through; this does not prove zero capacity under every conceivable alternative encoding. Thus a blanket claim of global per-error optimality is unjustified. No alternative label assignment, sign flag, or 8-bit mode is implemented or proposed for adoption here; all comparisons use the exact existing map.

Existing mapping/smoke pytest checks reported **14 passed, 9 warnings**. Direct execution of `tests/test_mapping.py` exits 1 (4/6 checks pass): obsolete boundary expectations at e=5,6 and an ambiguity test that compares cases with different decoder side information. These are pre-existing test limitations. They are preserved and documented; the pytest headline is not used as a substitute for the independent assert-based exhaustive gate and actual end-to-end checks.

## Calibration protocol and leakage controls

Before evaluating held-out images, `protocol.json` fixed seven offsets d in {0, −1, −0.5, −0.25, 0.25, 0.5, 1}. Correction is `round(clip(p+d,0,255))` with NumPy ties-to-even rounding, matching baseline rounding for bounded sigmoid outputs. It is a single deterministic global parameter; no per-image or per-channel fitting is permitted.

Twelve local grayscale images from `data/train` were selected by ascending SHA-256 of filename: first eight for calibration, next four for validation. Calibration maximizes image-mean **exact hard-label** BPP subject to hard MAE increasing by at most 0.05 gray levels; ties prefer smaller absolute offset. The selected candidate is locked before validation. Independent validation must improve BPP by >0.001 and increase MAE by <=0.05, otherwise deployment retains identity. These small thresholds are engineering gates, not statistical significance claims.

| Offset (gray levels) | Calibration hard BPP | Calibration hard MAE |
| --- | --- | --- |
| 0 | 5.77075958 | 2.71519470 |
| -1 | 5.51775551 | 3.04685402 |
| -0.5 | 5.66998291 | 2.83319664 |
| -0.25 | 5.74364853 | 2.74748802 |
| 0.25 | 5.76935959 | 2.72046661 |
| 0.5 | 5.71767044 | 2.78193665 |
| 1 | 5.55389786 | 2.99125671 |

The selected offset is **0**. Validation baseline/selected BPP is 5.71666336 and hard MAE is 3.04051208; no improvement, so validation acceptance is **false**, deployment offset **0**. No second candidate, larger search, changed MAE threshold or test-driven tuning followed.

Held-out images are the six saved grayscale benchmark images and five RGB images (21 channel maps). Every RGB image stays together; no channel is used for calibration. File/pixel hashes and splits are recorded, with exact pixel-hash exclusions against calibration/validation, including held-out channels. These benchmarks were previously analyzed by the project and are not a new blind external benchmark. Original CNN training provenance, near-duplicate independence and source representativeness cannot be fully established from available artifacts. The split establishes separation for this calibration investigation only. Lena-related benchmark images may share content; channels/images are not independent statistical replicates. No confidence or broad generalization claim is made.

## Held-out comparison

RGB BPP/MAE below average its three channels; grayscale uses its single map. The overall summary weights each of the 11 named images equally. BPP is per channel sample (RGB value is bits per color sample; multiply by three for bits per RGB spatial pixel). Every selected-calibrator prediction is identical to baseline because identity was selected. There is no accepted nontrivial calibrated model.

| Image | Baseline hard BPP | Selected hard BPP | Hard MAE (both) | Compressed sidecar BPP, baseline | Budget after sidecar, baseline |
| --- | --- | --- | --- | --- | --- |
| Airplane.png | 5.750191 | 5.750191 | 2.087349 | 13.491211 | -7.741020 |
| Baboon.png | 4.557613 | 4.557613 | 8.666386 | 16.840515 | -12.282902 |
| Goldhill.png | 5.320402 | 5.320402 | 3.531783 | 15.240181 | -9.919780 |
| Jetplane.png | 5.106304 | 5.106304 | 4.407509 | 14.571106 | -9.464802 |
| Lena.png | 5.459320 | 5.459320 | 2.910179 | 15.367615 | -9.908295 |
| Peppers.png | 4.944420 | 4.944420 | 5.165810 | 16.192963 | -11.248543 |
| 4.2.03.png | 4.220924 | 4.220924 | 11.851489 | 17.378387 | -13.157463 |
| 4.2.05.png | 5.641024 | 5.641024 | 2.418072 | 13.743825 | -8.102801 |
| 4.2.06.png | 4.590504 | 4.590504 | 7.970571 | 16.350199 | -11.759696 |
| 4.2.07.png | 4.733008 | 4.733008 | 6.614175 | 16.059825 | -11.326817 |
| lena.png | 5.233290 | 5.233290 | 3.924861 | 15.655670 | -10.422380 |

Overall baseline/selected **gross hard-label BPP = 5.05063643**; baseline/selected **hard MAE = 5.41347112**. Delta BPP=0 and delta MAE=0 for every image/channel. Baselines were reconciled against the existing saved grayscale and RGB per-channel CSVs: maximum absolute BPP discrepancy 0, MAE discrepancy 0. Saved CSVs were read, never overwritten. Prediction caches use Python's process-dependent hash keys, so fresh inference from the frozen checkpoint avoids uncertain cache-to-image attribution.

Pixel-pooled label distribution (larger images contribute more samples):

| n (MSBs/pixel) | Baseline count | Selected count | Pixel fraction |
| --- | --- | --- | --- |
| 0 | 389 | 389 | 0.000060 |
| 1 | 11643 | 11643 | 0.001807 |
| 2 | 127211 | 127211 | 0.019741 |
| 3 | 581346 | 581346 | 0.090215 |
| 4 | 1401648 | 1401648 | 0.217511 |
| 5 | 1953443 | 1953443 | 0.303140 |
| 6 | 1768455 | 1768455 | 0.274433 |
| 7 | 599897 | 599897 | 0.093093 |

Pixel-pooled absolute prediction-error distribution:

| Absolute error | Count (both) | Pixel fraction |
| --- | --- | --- |
| 0 | 599897 | 0.093093 |
| 1 | 1080997 | 0.167752 |
| 2–3 | 1545596 | 0.239849 |
| 4–7 | 1647690 | 0.255692 |
| 8–15 | 1088005 | 0.168839 |
| 16–31 | 401504 | 0.062306 |
| 32–63 | 75591 | 0.011730 |
| 64 | 385 | 0.000060 |
| 65–127 | 4363 | 0.000677 |
| 128–255 | 4 | 0.000001 |

Full signed errors (−255…255), absolute errors (0…255), labels, timings and per-channel metrics are in `heldout_results.json`. All distributions are exactly identical between baseline and selected calibration.

## Runtime, exact recovery and side information

Mean CNN inference time over the 21 channel maps was 2.9278 s/channel. Inference is shared between variants. Mean correction/rounding time was 1.6286 ms for baseline and 1.2296 ms for the selected identity path. Mean measured time for label construction plus three full sender/encrypt/decrypt/receiver checks was 11.8272 s/channel baseline and 12.6821 s/channel selected. These are single-pass audit timings, not a controlled speed benchmark; ordering and warm-up can explain differences. Identity can bypass its wrapper entirely and has no required deployment runtime increase. Compression is outside the reported round-trip timings.

Each of 21 channel maps × 2 variants was tested at empty, 37-bit (or capacity-limited) short, and full gross-capacity random payloads: **126 end-to-end checks**, all with byte-exact recovered image and bit-exact extracted payload, independently asserted using existing sender/receiver/encryption functions. These checks condition on decoder side information and do not establish a self-contained image-only codec.

The current receiver requires prediction, n, minimum-error and maximum-error maps. It cannot simply rerun the noncausal CNN on the marked/decrypted image to reconstruct those predictions. Raw int32 arrays cost **128 bits/sample** in memory; a lossless uint8 representation of all four maps costs **32 bits/sample** before compression. Even an optimized shared label alphabet would still need a valid serialized decoder design, not an assumption that metadata is free.

For an explicit measured accounting proxy, four uint8 maps were concatenated in the fixed order (p,n,min,max), losslessly zlib-compressed (level 9), and charged a fixed 32-byte framing/header allowance per channel plus one byte for the candidate offset index. Lossless decompression was asserted byte-for-byte. That header allowance can hold version/codec, dimensions, nonce, payload length and compressed length; key material is preshared. This is an external-sidecar cost model, not an implemented embedded metadata protocol, optimal compression scheme, or lower bound on achievable overhead. Offset information is redundant if the corrected p map is sent, so charging one byte is conservative; identity deployment needs no added byte.

Baseline mean compressed sidecar cost is **15.535591 bits/sample**, leaving a signed gross-minus-sidecar budget of **-10.484954 bits/sample**. Candidate cost is 15.535618, leaving -10.484982; the only difference is the conservative unnecessary diagnostic byte. Negative budgets mean overhead exceeds gross slots for that serialization; usable capacity cannot be negative. Positive budgets are conditional accounting estimates and **not demonstrated net payload**: no sidecar embedding/bootstrap protocol was implemented. Full-capacity recovery tests use external maps and therefore demonstrate gross capacity only. No net payload improvement is established.

## Related work and novelty decision

The targeted search covered prediction bias correction, CNN predictor improvements, multi-prediction and auxiliary-label encoding, before making the decision:

- Wu and Memon's [CALIC author/institutional record](https://experts.mcmaster.ca/scholarly-works/1909058) describes context-conditioned prediction-error feedback. Predictor correction is established prior art.
- Celik et al., [Reversible Data Hiding, ICIP 2002](https://hajim.rochester.edu/ece/sites/gsharma/papers/reversiblehidingICIP02.pdf), uses prediction with context bias removal and accounts for compressed recovery information within embedding. A scalar bias correction and auxiliary-data accounting are not novel in themselves.
- Qiu et al., [Improved CNN Prediction Based Reversible Data Hiding (2023)](https://arxiv.org/abs/2301.01420), combines CNN pixel/complexity prediction with error ordering. Its mechanism differs from this frozen-output offset, but improving RDH by refining prediction/complexity is established. The related [Entropy 2025 paper](https://www.mdpi.com/1099-4300/27/2/159/pdf?version=1738565597) was located; the publisher HTML fetch was rate-limited, so no stronger full-text comparison is asserted here.
- [High-Capacity RDHEI using Adaptive Encoding (2021)](https://arxiv.org/abs/2102.12620) and [Multi-prediction and adaptive Huffman encoding (2023)](https://www.nature.com/articles/s41598-023-50186-1) address prediction-error/label coding and overhead. The latter's publisher abstract was available in search, while direct access redirected to an unavailable login endpoint; comparison is limited accordingly.

This targeted review cannot certify exhaustive novelty. It supplies no defensible basis for claiming a new contribution from the tested scalar correction. Identity already wins, no held-out gross gain exists, and a net-capacity transport protocol is absent. **NO-GO: retain the existing trained CNN-3×3 checkpoint and predictor/map behavior.** Broader calibration families are outside this smallest experiment; they were not searched after seeing held-out outcomes. Retraining remains prohibited.

## Preservation and reproducibility

SHA-256 comparison of **1524 pre-existing files** after the investigation found **0 changed or missing files**; model state was bitwise unchanged. Original pipeline sources, models, result CSVs, manuscript files and abandoned experiment artifacts were preserved. This comparison begins after the authorized graceful stop, so the trainer's final appended KeyboardInterrupt log is retained as the stop evidence.

Audit files: `preservation_before.json`, `preservation_check.json`, `aborted_retraining_status.json`, `protocol.json`, `checkpoint.json`, `recovery_gate.json`, `locked_selection.json`, `input_manifest.json`, `heldout_results.json`, `investigation.log`, and both existing-test logs. `investigate.py` uses exclusive-create outputs to prevent accidental overwrite; an independent repetition must use a fresh output directory. No checkpoint is produced by this code.
