# Deliverable C — Critical issues

Issues are grouped into three buckets: confirmed implementation/experiment defects,
missing evidence, and writing/reproducibility improvements. Only material items are
included; minor style items are left to Deliverable D.

## C1. Confirmed implementation/experiment defects or inconsistencies

1. **Plaintext-then-encrypt embedding vs terminology.**
   The implemented owner pipeline embeds in the plaintext image and then encrypts.
   Any wording that implies embedding into an encrypted image, or embedding after
   encryption, would be inconsistent with `src/rdhei_core.py`. Fix: state the order
   explicitly and use it consistently.

2. **RGB encryption nonce handling is correct in the repaired RGB path, but the
   wrapper parameter naming is messy.**
   `src/rdhei_color.py` exposes `nonce=` in the public entry point, while internal
   comments and the helper `pack_metadata(base_nonce)` use `base_nonce`. The paper
   must not invent a second public parameter; it should describe the derivation
   `nonce_c = base_nonce + c + 1` and state that the base nonce is provided to the
   receiver.

3. **Color BPP aggregation is used inconsistently across artifacts.**
   The color wrapper reports mean-of-channel-BPPs; the ablation summary text says
   `total_capacity / (H*W*3)`. For equal-sized channels those can coincide, but they
   are not identical definitions and the paper must choose one.

4. **CNN-NoWeightedLoss is a training-loss label, not an architectural variant.**
   In `src/cnn_model.py`, there is no architectural “weighted loss” switch. Calling all
   five items “CNN variants” without distinguishing architecture from training loss is
   misleading. Fix: label CNN-NoWeightedLoss as a loss/ablation variant and keep the
   architectural versus training ablations visually or verbally separate.

5. **The training-loss ablation is under-supported relative to the checkpoint naming.**
   The checkpoints `v1_full` and `v3_no_weighted_loss` are different files, but the
   inspected artifacts do not include the training run that produced the loss-variant
   checkpoint or its log. If the paper presents v3 as “trained with plain L1”, that
   claim depends on training provenance that is not fully present here.

6. **RGB verification evidence is split and partially contradictory across artifacts.**
   - `results/verification/final_verification_summary.*` shows all color images as
     `SKIPPED` with 2-D shapes.
   - `RGB_VALIDATION_COMPLETE.md` and the RGB smoke artifacts show genuine 3-channel
     PNGs and RGB PASS on completed runs.
   This is a dataset-loading/import inconsistency between runs, not a proof that the
   files are grayscale. The paper must not merge these into one unqualified “RGB
   verified for all variants and all images” claim. State exactly which RGB evidence is
   solid and which is not.

7. **Dataset size and composition are smaller than some project descriptions suggest.**
   The artifacts identify 6 grayscale and 6 RGB images, with one RGB-directory file
   (`images.png`) being grayscale. Any claim of “12 Kodak images per set” must be
   reconciled with the actual files or dropped.

8. **`run_anal_v2.py` contains an indentation defect and was not used for the runtime
   numbers.**
   If the paper cites runtime numbers and attributes them to that script, the citation
   is wrong. The runtime numbers came from a separate direct benchmark. This must be
   stated accurately.

## C2. Missing evidence that blocks publication-ready claims

1. **Training provenance is incomplete.**
   `src/train.py` is concrete, but the actual training corpus, number of training
   images, number of patches, training logs, and checkpoint-selection history are not
   in the inspected artifacts. As a result:
   - “trained on BOSSbase-style data” cannot be verified here;
   - the justification that CNN-NoWeightedLoss differs only in loss cannot be confirmed
     from artifacts alone.

2. **No standalone mathematical uniqueness proof for the recovery bands.**
   The recovery logic is tested extensively and the full-pipeline verification passes,
   but the code does not include an explicit lemma that every `[min_e,max_e]` band used
   by `_compute_bpp_and_range` guarantees a unique recoverable pixel under the
   low-bits constraint. The paper can still claim empirical correctness, but should not
   present the scheme as algebraically guaranteed for all images unless that proof is
   added.

3. **No full 5-variant × all-images RGB full-pipeline verification in a single clean
   artifact.**
   There is RGB smoke and bounded RGB evidence, plus a color-sweep artifact that
   recorded SKIPPED due to a dataset-loading issue. A clean, consistent full RGB
   verification artifact is still desirable before claiming broad RGB correctness.

4. **No full-pipeline runtime benchmark, only predictor-only runtime plus one
   full-pipeline sample.**
   The paper can report predictor-only runtime honestly, but any claim about end-to-end
   throughput or “real-time” performance is not supported by the current artifacts.

5. **No reproduced training or full experiment regeneration from a clean environment in
   this inspection.**
   The existing artifacts are strong, but the paper’s reproducibility claim is stronger
   if a clean regeneration command and environment spec are included.

6. **No accessible reference paper full text or Section 4 revision file in the project.**
   I did not find `Section_4_Updated_Review_Fixes_v2.md` or a JISA reference PDF in the
   project tree. If those are needed for style or structural alignment, they must be
   supplied; otherwise Section 3 is written from the implementation alone.

## C3. Writing and reproducibility improvements that are not defects but matter

1. **Define BPP for RGB once and use it everywhere.**
   Choose either per-channel-average BPP or total-capacity-normalized BPP and keep it
   consistent across the methodology, results, and tables.

2. **Separate prediction error from reconstruction fidelity explicitly.**
   The manuscript should never use “prediction MAE” and “reconstructed-image MAE/PSNR/SSIM”
   interchangeably.

3. **Do not claim computational lightweightness versus classical predictors.**
   The measured predictor-only numbers contradict that claim. If “lightweight” is meant
   only relative to larger CNNs, say so precisely; otherwise drop the term.

4. **State security limits explicitly.**
   AES-CTR here provides confidentiality only; there is no authentication. The base nonce
   must be transmitted/stored separately. The paper should not imply integrity or
   tamper resistance.

5. **Disclose receiver side information.**
   The receiver uses owner-computed prediction and label maps. If the paper claims
   blind or ciphertext-only recovery, that claim is not supported by the current
   implementation.

6. **Keep the “proposed” framing honest.**
   The implementation supports a comparative evaluation of lightweight CNN predictors in
   an RDHEI pipeline. Unless there is a defensible contribution beyond that, the wording
   should reflect evaluation and trade-off analysis rather than invented novelty.

7. **Add an explicit statement of what the reported perfect recovery means.**
   It is verified by exact array equality for the tested images and variants, with the
   scope clearly limited to those runs. It is not a universal guarantee for all possible
   images.

8. **If the paper uses a system figure, base it on the verified flow.**
   Owner predict → round → absolute error → label maps → MSB embedding → AES-CTR →
   transmit; receiver decrypt → extract → candidate recovery. Do not base the figure on
   an embed-after-encryption or lower-bit-plane story unless the code changes.
