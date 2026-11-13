# Deliverable D — Final verification checklist

Use this list to cross-check Section 3 against the authoritative sources before
submission. Each item states what must be true in the manuscript and where it is
verified in the project.

## D1. Pipeline and terminology

- [ ] The manuscript states that the owner **predicts → embeds in plaintext → encrypts**,
      and that the ciphertext is an encrypted stego plaintext image.
      _Verified in:_ `src/rdhei_core.py` `sender_embed_encrypt()` →
      `encrypt_image()`; `content_owner_prepare()`.
- [ ] The manuscript consistently distinguishes the **CNN predictor** from the
      **RDHEI embedding/recovery mechanism**.
      _Verified in:_ `src/rdhei_core.py` uses the predictor only for `pred_map`;
      embedding/recovery use `_embed_pixel()` / `_recover_pixel()`.
- [ ] The manuscript does **not** claim embedding after encryption, lower-bit-plane
      embedding, or a custom encryption architecture unless the code is changed.
      _Verified in:_ current `src/rdhei_core.py` and `src/encryption.py`.

## D2. Predictor section

- [ ] The manuscript describes patch extraction, normalization by 255, reflect padding,
      center masking to 0, and the scalar sigmoid×255 output.
      _Verified in:_ `src/predictor.py` `cnn_predict_map()`.
- [ ] The manuscript states that $\mathbf{P} = \mathrm{round}(\hat{\mathbf{I}})$ and
      $\mathbf{E}_{\mathrm{abs}} = |\mathbf{I} - \mathbf{P}|$.
      _Verified in:_ `src/rdhei_core.py` `content_owner_prepare()`.
- [ ] Table 1 matches the five CNN configurations and the inspected parameter counts:
      3×3 residual = 46,881; 5×5 residual = 112,417; 5×5 no residual = 112,353;
      7×7 residual = 210,721.
      _Verified in:_ `src/cnn_model.py`, `tests/test_cnn_checkpoints.py`,
      `results/ablation/ablation_summary.csv`.
- [ ] The manuscript treats CNN-NoWeightedLoss as a **loss/ablation** variant, not as a
      separate architecture.
      _Verified in:_ `src/cnn_model.py` has no architectural weighted-loss switch;
      the difference is in training, which is under-documented in the artifacts.
- [ ] The manuscript does **not** claim architectural novelty unless a defensible
      contribution is demonstrated.
      _Verified in:_ current implementation is a compact regressor; the contribution is
      evaluation/trade-off analysis.

## D3. Capacity and label-map section

- [ ] Equations (capacity, BPP) match `bpp_map.sum()` and `capacity/(H*W)`.
      _Verified in:_ `src/rdhei_core.py` `content_owner_prepare()` and `src/metrics.py`.
- [ ] The manuscript uses **one** RGB BPP definition consistently and does not silently
      switch between per-channel-average and total-capacity-normalized forms.
      _Verified in:_ `src/rdhei_color.py` vs `FINAL_EXPERIMENT_REPORT.md` §8.
- [ ] The manuscript either reproduces the operational label-map rule faithfully or points
      to `_compute_bpp_and_range()` as the authoritative definition, including the special
      midpoint handling.
      _Verified in:_ `src/rdhei_core.py` `_compute_bpp_and_range()` and `generate_label_map_fast()`.
- [ ] The manuscript acknowledges that the mapping is a function of $|\mathbf{I}-\mathbf{P}|$
      only and that the band logic is discrete and piecewise.
      _Verified in:_ `src/rdhei_core.py`.

## D4. Embedding and encryption section

- [ ] The MSB-replacement equation matches `_embed_pixel()`: upper $n$ bits replaced,
      lower $8-n$ bits preserved.
      _Verified in:_ `src/rdhei_core.py` `_embed_pixel()` and `sender_embed_encrypt()`.
- [ ] The manuscript states that encryption is AES-CTR and that it provides confidentiality
      only, with no authentication/integrity.
      _Verified in:_ `src/encryption.py` docstring and implementation.
- [ ] For RGB, the manuscript gives the per-channel nonce derivation
      $nonce_c = base\_nonce + c + 1$ and states that the base nonce must reach the receiver.
      _Verified in:_ `src/encryption.py` `get_channel_nonce()` and `encrypt_rgb_channels()`;
      `src/rdhei_color.py`.
- [ ] The manuscript does **not** overstate AES-CTR security or claim tamper resistance.
      _Verified in:_ `src/encryption.py` limitations note.

## D5. Extraction and recovery section

- [ ] The manuscript states that the receiver is given $\mathbf{B}, \mathbf{L}_{\min},
      \mathbf{L}_{\max}, \mathbf{P}, C, k, nonce$.
      _Verified in:_ `src/rdhei_core.py` `receiver_extract_recover()` signature.
- [ ] The manuscript discloses that recovery is **not** ciphertext-only / fully blind with
      respect to prediction side information.
      _Verified in:_ current pipeline passes owner maps directly to the receiver.
- [ ] The recovery equation matches `_recover_pixel()`: enumerate $2^n$ upper-bit candidates,
      select the one with $|\hat{v}-\mathbf{P}|$ in $[\mathbf{L}_{\min},\mathbf{L}_{\max}]$.
      _Verified in:_ `src/rdhei_core.py` `_recover_pixel()`.
- [ ] The manuscript states that exact recovery is verified by $\mathbf{I} ==
      \hat{\mathbf{I}}_{\mathrm{rec}}$ and $\mathbf{p} == \mathbf{p}_{\mathrm{ext}}$, with
      scope limited to the tested images/variants.
      _Verified in:_ `FINAL_VERIFY_FULL_PIPELINE.py`, `results/verification/`.

## D6. RGB section

- [ ] The manuscript states that RGB channels are processed independently, without a
      color-space conversion.
      _Verified in:_ `src/rdhei_color.py`.
- [ ] The manuscript does not call `images.png` an RGB image.
      _Verified in:_ `RGB_VALIDATION_COMPLETE.md` and `RGB_AUDIT_REPORT.md`.
- [ ] The manuscript reconciles the grayscale full-pipeline verification (all 5 variants,
      all available gray images) and the RGB evidence (solid for completed runs only).
      _Verified in:_ `results/verification/final_verification_summary.*` and
      `RGB_VALIDATION_COMPLETE.md`.

## D7. Experiments and metrics section

- [ ] The manuscript lists only metrics actually measured and distinguishes prediction MAE
      from reconstruction MAE/PSNR/SSIM.
      _Verified in:_ `src/metrics.py`, `results/gray/baselines_results.txt`,
      `results/ablation/ablation_summary.csv`, `results/runtime/runtime_results.csv`.
- [ ] Runtime is described as **predictor-only** on CPU, with warm-up/repetition/aggregation
      stated, and the single full-pipeline sample is labeled as a sample, not a benchmark.
      _Verified in:_ `results/runtime/runtime_report.txt` and one full-pipeline timing in
      `FINAL_EXPERIMENT_REPORT.md` §8/§9.
- [ ] The manuscript states honestly that the CNN predictors are much slower than MED/GAP/CALIC
      and does **not** call the method computationally lightweight relative to them.
      _Verified in:_ `results/runtime/runtime_results.csv`.
- [ ] The dataset is described as 6 grayscale and 6 RGB images, with the grayscale
      `images.png` excluded from RGB.
      _Verified in:_ `RGB_VALIDATION_COMPLETE.md`, `RGB_AUDIT_REPORT.md`,
      `FINAL_EXPERIMENT_REPORT.md`.

## D8. Sources that must exist before the manuscript is finalized

- [ ] If the paper references a JISA-style methodology structure, the actual reference text
      must be supplied; it was not found in the project tree during this inspection.
- [ ] If Section 4 revisions are referenced, `Section_4_Updated_Review_Fixes_v2.md` must be
      located or its absence acknowledged.
- [ ] If training provenance is cited, the training run log/provenance must be added so that
      the v1/v3 distinction and any dataset claims are reproducible.
- [ ] If RGB correctness is claimed broadly, a clean full RGB verification artifact must be
      produced that does not rely on a dataset-loading path that previously yielded 2-D arrays.

## D9. Last-pass consistency checks

- [ ] All method names are consistent: MED, GAP, CALIC, CNN-3×3, CNN-5×5,
      CNN-NoResidual, CNN-NoWeightedLoss, CNN-7×7.
- [ ] Symbols are consistent across subsections: $\mathbf{I}, \hat{\mathbf{I}}, \mathbf{P},
      \mathbf{E}_{\mathrm{abs}}, \mathbf{B}, \mathbf{L}_{\min}, \mathbf{L}_{\max}, C,
      \mathrm{BPP}$.
- [ ] The “proposed” framing is used only where defensible; otherwise the section reads as a
      comparative predictor/configuration evaluation.
- [ ] No fabricated dataset size, hardware spec, hyperparameter set, citation, or result
      appears in the section.

If every item above is satisfied, Section 3 is consistent with the inspected implementation
and experiment artifacts and does not assert more than the evidence supports.
