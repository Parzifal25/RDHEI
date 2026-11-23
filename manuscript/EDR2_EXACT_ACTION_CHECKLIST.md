# EDR2 manuscript: exact execution checklist

Run this checklist before journal formatting. No model retraining is requested.

## Gate 1 — Protocol identity
- [ ] Name the exact EDR2 implementation file(s), tests, checkpoint SHA-256 and commit SHA.
- [ ] Trace the actual data path in code: prediction → reservation/embedding → encryption (or encryption → embedding) → extraction → recovery.
- [ ] Record sender, hider and receiver knowledge separately.
- [ ] List all transmitted/in-band/out-of-band fields and key/nonce inputs.
- [ ] Confirm whether EDR2 has a MAC/AEAD. If not, explicitly state AES-CTR confidentiality only and remove tamper-detection claims.
- [ ] Keep EDR1 protocol and evidence out of the EDR2 manuscript.

## Gate 2 — Capacity table
- [ ] Identify the final EDR2 per-image raw results file.
- [ ] Recompute gross, metadata, directory/map, tag, bootstrap/backup and net payload.
- [ ] Check that each cost is subtracted exactly once.
- [ ] Report image dimensions and bpp denominator.
- [ ] Report all-image signed mean, pooled signed rate, positive-image fraction, conditional usable mean, median and quartiles.
- [ ] Include zero/negative capacity images in the coverage denominator.
- [ ] Bootstrap at the image/provenance-cluster level; do not treat correlated images/channels as independent samples.
- [ ] Verify every summary number against the raw file.

## Gate 3 — Prediction and geometry
- [ ] Define CNN architecture, receptive-field radius, masking and deterministic inference.
- [ ] Define exact candidate phase coordinates and border rule.
- [ ] Prove candidate non-interference for every modified position.
- [ ] Separate predictor accuracy evaluation from native EDR2 payload evaluation.
- [ ] Report the 5×5 no-weighted-loss ablation honestly; 3×3 is a size/runtime trade-off, not universally the best predictor.
- [ ] Do not mix step-4/16-phase predictor experiments with step-2/four-phase EDR2 outcomes.

## Gate 4 — Baselines
- [ ] Pin each external method source/commit and dataset manifest.
- [ ] Verify image source and pixel hashes.
- [ ] Record all compatibility modifications (including PPMR).
- [ ] Explain native protocol differences, metadata and encryption order.
- [ ] Avoid claims of same-packet-cost or same-security leaderboard unless exact parity exists.
- [ ] Use separate tables for predictor-only, native EDR2 and external native-protocol outcomes.

## Gate 5 — Security and correctness
- [ ] Explain threat model and trust in owner/hider/receiver.
- [ ] Record key derivation, domain separation and nonce uniqueness.
- [ ] If authentication is implemented, verify code path and exact authenticated bytes.
- [ ] Test mutations only in the actual EDR2 packet; keep test logs and seeds.
- [ ] Independently compare original image and extracted payload.
- [ ] State that successful tests are implementation evidence, not a formal cryptographic proof.

## Gate 6 — Runtime and scalability
- [ ] Execute the existing EDR2 benchmark harness without changing its algorithm.
- [ ] Record hardware/software, warmups, repeats, mean/median/std, per-stage and end-to-end time.
- [ ] Record throughput and memory with measurement scope.
- [ ] Only claim multi-resolution scalability when 512/1024/2048 results are present and checks pass.

## Gate 7 — Literature and writing
- [ ] Organise related work by technical problem.
- [ ] Compare each nearest paper by predictor, protocol order, side information, map coding, security and capacity denominator.
- [ ] Verify every DOI and title/year/journal metadata in Scite or publisher/Crossref.
- [ ] Check citation-to-claim fit and contradictory later evidence.
- [ ] Run paragraph-logic, citation-consistency and British-English checks.
- [ ] Generate figures from committed raw files; include captions and units.
- [ ] Only now select target journal and apply its format.

## Decision
A paper is ready only when gates 1, 2 and 5 pass. A good-looking narrative cannot substitute for missing raw results or protocol evidence.