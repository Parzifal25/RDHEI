# Deliverable A — Implementation audit

Audit stance: the authoritative sources are the imported runtime modules
`src/rdhei_core.py`, `src/rdhei_color.py`, `src/encryption.py`,
`src/predictor.py`, `src/cnn_model.py`, `src/train.py`, `src/embedding.py`,
`src/extraction.py`, `src/metrics.py`, `src/comp.py`, plus the final
experiment artifacts under `results/`, `results/verification/`,
`results/gray/`, `results/rgb/`, `results/ablation/`, `results/runtime/`,
and `RDHEI_FIXED_V1/results/`.

Where a manuscript claim would be needed to reconcile the code and the
recorded numbers, the entry is marked **Partially verified** or
**Unverified** and the discrepancy is stated explicitly.

| # | Implementation detail | Supporting source / file | Verification status | Discrepancy / flag |
|---|---|---|---|---|
| A1 | Three-party flow: image owner predicts, embeds in plaintext, then encrypts; receiver decrypts, extracts, recovers. | `src/rdhei_core.py`: `content_owner_prepare()` → `sender_embed_encrypt()` → `encrypt_image()`; `receiver_extract_recover()` → `decrypt_image()` | Verified | The owner-side embedding happens **before** encryption, so the pipeline is plaintext-then-encrypt for the stego image, not embed-after-encryption. The “encrypted image” container carries the stego plaintext under AES-CTR. |
| A2 | CNN predictor is independent of the RDHEI embedding/recovery mechanism. | `src/rdhei_core.py` uses `cnn_predict()`/`cnn_predict_map()` only to produce `pred_map`; embedding/recovery use `_embed_pixel()` / `_recover_pixel()` with `bpp_map`, `min_e_map`, `max_e_map`, `pred_int`. | Verified | The predictor is plug-in; the RDHEI scheme is the label-map / MSB-replacement layer. |
| A3 | Five CNN configurations: CNN-3×3, CNN-5×5, CNN-NoResidual, CNN-NoWeightedLoss, CNN-7×7. | `src/cnn_model.py` class `CNNPredictor`; `src/comp.py` `build_variants()`; `results/ablation/ablation_summary.csv` | Verified for architecture, parameter counts, and labels used in experiments | “CNN-NoWeightedLoss” is **not** a separate architecture in `CNNPredictor`; it is the same 5×5 residual model trained with a different loss. The codebase supports this ablation only if the checkpoint was actually trained that way; that training provenance is **not** verified here. |
| A4 | Patch sizes 3, 5, 7 with masked center pixel; prediction is a single scalar per patch. | `src/predictor.py` `cnn_predict_map`; `src/cnn_model.py` `forward()` returns `out * 255.0` after a `Sigmoid` head. | Verified | Model output is `[0,255]` because of `Sigmoid*255`; prediction is not unconstrained regression. |
| A5 | Input preprocessing: divide by 255, reflect pad by `HALF = patch_size//2`, mask center to 0. | `src/predictor.py` | Verified | Predictors see normalized patches with the center zeroed; MED/CNN predictors are not computed from the same representation. |
| A6 | Prediction errors are **absolute** errors `|image - round(pred)|`, used for capacity only. | `src/rdhei_core.py`: `error_abs = np.abs(image.astype(np.int32) - pred_int)` | Verified | The scheme does **not** use signed error direction for capacity allocation; capacity is a function of `|e|` only. |
| A7 | Label map emits `bpp_map`, `min_e_map`, `max_e_map` per pixel. | `src/rdhei_core.py` `generate_label_map_fast()` and `_compute_bpp_and_range()` | Verified against `tests/test_mapping.py`, `tests/test_mapping_ascii.py`, and `tests/test_smoke.py` | Verified logic, but the **interpretation** of `min_e`/`max_e` as a unique-recovery band is correct only together with the recovery routine; see A12 and C-items. |
| A8 | `_compute_bpp_and_range()` is the mathematical core of the capacity model. | `src/rdhei_core.py` | Verified by boundary tests in `tests/test_mapping.py` (ASCII-safe table also exists in `tests/test_mapping_ascii.py`) | The function works on `e_abs`, not signed error; boundary handling around the `mid` values is subtle and is exactly where the capacity model becomes non-monotonic; see C-items. |
| A9 | Capacity is `bpp_map.sum()` bits; BPP is `capacity / (H*W)`. | `src/rdhei_core.py` `content_owner_prepare()`; `src/metrics.py` `bpp()` | Verified | In color, `rdhei_color.py` reports **per-channel-average BPP**, not `total_capacity/(H*W*3)` in the color wrapper’s top-level `bpp`; the experiment report uses `total_capacity/(H*W*3)` for “Colour BPP” in the ablation table. These are two consistent but **different** aggregation conventions; see C-items. |
| A10 | Embedding replaces the upper `n` MSBs of selected pixels with payload bits; lower `8-n` bits are unchanged. | `src/rdhei_core.py` `_embed_pixel()`; `sender_embed_encrypt()` | Verified by `tests/test_mapping.py` `_embed_pixel` tests and smoke tests | “MSB replacement” is accurate; the replaced bits are the **most significant** `n` bits, not an arbitrary bit plane. |
| A11 | Encryption is AES-CTR with a per-channel nonce `base_nonce + channel_index + 1`. | `src/encryption.py`; `src/rdhei_color.py` | Verified; encryption tests pass; no keystream reuse across channels in the repaired RGB path | AES-CTR here gives confidentiality only; there is **no authentication/integrity**. This must be stated explicitly in the paper. |
| A12 | Recovery searches all `2^n` upper-bit candidates for a value whose `|candidate - pred|` lies in `[min_e, max_e]`. | `src/rdhei_core.py` `_recover_pixel()` | Verified functionally by mapping+recovery tests and full-pipeline verification | Uniqueness of recovery depends on the `[min_e,max_e]` band logic; the code does **not** guarantee uniqueness for every band mathematically in the file as written — the band logic and recovery are tested together empirically, which is strong but not the same as a standalone uniqueness proof. |
| A13 | Receiver gets `bpp_map`, `min_e_map`, `max_e_map`, `pred_int`, `key`, `nonce`, and `payload_len`. | `src/rdhei_core.py` `receiver_extract_recover()` signature; `run_rdhei()` passes `co[...]` directly. | Verified | Recovery is **not** ciphertext-only or blind with respect to the prediction side information; the owner-computed maps are handed to the receiver. This must be disclosed. |
| A14 | Full-pipeline perfect recovery verified for all 5 CNN variants on grayscale Kodak images; RGB verified on a subset of variants/images in the final verification artifacts. | `results/verification/final_verification_summary.json` and `.csv`; `FINAL_EXPERIMENT_REPORT.md` §8; `RGB_VALIDATION_COMPLETE.md` | Partially verified | The CSV/summary companion files show color columns as `SKIPPED` (loaded as 2-D), whereas `RGB_VALIDATION_COMPLETE.md` and smoke tests show genuine RGB PNGs and RGB PASS. The RGB evidence is real but split across inconsistent artifacts; see C-items. |
| A15 | Runtime measured predictor-only on Lena 512×512 CPU: warm-up 5, repeats 10. | `results/runtime/runtime_results.csv`, `results/runtime/runtime_report.txt` | Verified | Numbers are **predictor-only**, not full pipeline. CNN inference is orders of magnitude slower than MED/GAP/CALIC; this is the central trade-off and must be reported honestly. |
| A16 | Computational complexity table (Table 3) is produced by `src/comp.py`. | `src/comp.py` | Unverified for current run | The script reads `results/runtime/runtime_results.csv`; if that file or `ptflops` availability differs, Table 3 numbers can change. Flop counts for the CNN variants are computed analytically or via `ptflops` and should be regenerated, not copy-pasted from an earlier draft. |
| A17 | Training procedure: `src/train.py` with `WeightedL1Loss(alpha=2.0)`, 5×5 patches, `PATCH=5`, `HALF=2`, `SEED=42`, cosine LR schedule, 20 epochs, BOSSbase-style `.pgm` training dir. | `src/train.py` | Partially verified | The training script exists and is concrete, but the actual training logs, exact training image set, exact number of training patches, and exact checkpoint selection path are **not** present in the inspected artifacts. The checkpoint differences (e.g. v1_full vs v3_no_weighted_loss) are **not** independently proven to arise from the documented training procedure. |
| A18 | Baseline methods: MED, GAP, CALIC, and a histogram-shifting-related entry “HistShift” in the grayscale baseline table. | `results/gray/baselines_results.txt`; `src/baselines.py` (MED, GAP, CALIC wrappers) | Verified for BPP/MAE table existence | “HistShift” appears in the baseline BPP table at ~0.02 bpp, which is not comparable to the prediction-error methods; any claim that histogram shifting is a strong competitor must be qualified against this actual result. |
| A19 | RGB processing: channels processed independently, per-channel nonces, aggregate color BPP is mean of channel BPPs in the color wrapper. | `src/rdhei_color.py` | Verified | Consistent with smoke test and RGB validation report, but the wrapper signature uses `nonce=` while some docs/comments say `base_nonce`; calling convention must be described carefully. |
| A20 | Metrics used in experiments: BPP, prediction MAE/MPE, reconstruction PSNR/SSIM/MAE, bit accuracy, parameter count, runtime. | `src/metrics.py`; `results/gray/baselines_results.txt`; `results/ablation/ablation_summary.csv`; `results/runtime/runtime_results.csv` | Verified | Prediction error is reported as MAE/MPE before embedding; reconstruction fidelity is reported after recovery. These are distinct and must not be conflated. |

### Immediate cross-file discrepancies to reconcile before writing Section 3

1. **Color BPP definition differs between artifacts.**
   - `src/rdhei_color.py` returns `bpp = mean(per-channel BPP)`.
   - `FINAL_EXPERIMENT_REPORT.md` §8 ablation table says “Colour BPP uses … `total_capacity / (H * W * 3)`.”
   - For equal-shaped channels these can coincide, but they are not identically defined in the inspected files, and the paper must pick one and use it consistently.

2. **RGB verification evidence is split and partially contradictory.**
   - `results/verification/final_verification_summary.*` records all color images as `SKIPPED` with 2-D shapes.
   - `RGB_VALIDATION_COMPLETE.md` and the RGB smoke artifacts record genuine 3-channel PNGs and RGB PASS.
   - The most defensible wording is that grayscale full-pipeline verification is solid for all 5 variants, while RGB full-pipeline verification is solid for the images/run variants that were actually completed and recorded, with a separate dataset-loading inconsistency in the later verification sweep.

3. **“CNN-NoWeightedLoss” is a training-loss ablation, not an architecture ablation.**
   - The model class does not have a “weighted loss” switch; the variant label reflects training, not architecture.
   - If the paper presents all five as “CNN variants”, it must distinguish architectural variants (patch size, residual) from the loss-variant.

4. **`run_rdhei_color()` parameter naming is inconsistent inside the codebase.**
   - The public entry uses `nonce=`, while comments/helper `pack_metadata(base_nonce)` and some notes refer to `base_nonce`.
   - The paper should describe the nonce derivation without inventing a second parameter name.

5. **Training provenance is under-documented relative to the claims the section may want to make.**
   - The training script is concrete, but the exact trained dataset, schedule output, and checkpoint provenance are not in the inspected artifacts.
   - Section 3 should not imply a fully specified training corpus or guaranteed causal link between the documented loss and the specific saved weights unless that evidence is added.

### Sources not accessible / not found

- `Section_4_Updated_Review_Fixes_v2.md`: **not found** in the project tree.
- A JISA reference paper full text: **not found** in the project tree; I did not load one from the web.
- `configs/` directory: **empty / absent**.
- Any separate paper draft/manuscript file beyond the report artifacts above: **not found** in the inspected tree.

Because of that, Section 3 below is written from the implementation and experiment artifacts alone, with the missing items flagged rather than inferred.
