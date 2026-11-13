# Experiment Preflight — RDHEI_FIXED_V1

**Date**: 2026-10-13  
**Scope**: Phase 1 preflight for reproducible grayscale / RGB / ablation / runtime experiments  
**Working directory**: `RDHEI_FIXED_V1/`  

## 1. Goal

Confirm that the repaired project is in a state where the planned experiments can be executed with the existing checkpoints, datasets, and scripts, without retraining or touching model weights. This report is the preflight artifact required before any experiment runs.

## 2. Checkpoints present

All five expected ablation/functional checkpoints were found under `RDHEI_FIXED_V1/models/`:

| File | Size (bytes) | SHA-256 |
|---|---|---|
| `v1_full.pth` | 456,871 | `51406640acaf6f3702481829d4562663b02336b8a6b96750a58eec6598815937` |
| `v2_no_residual.pth` | 456,725 | `173f462155c1075d849350453db22328fb9ff5410ad899d77cb590f6321fbb32` |
| `v3_no_weighted_loss.pth` | 457,695 | `1fa025e252d5a3c95509ab1a8321e0b46ca72aa083161c2e9b8c30c2ab5e5c41` |
| `v4_patch3.pth` | 195,291 | `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d` |
| `v5_patch7.pth` | 850,651 | `e6996df5f942fca9b95cf51719dc6c29df17c626f40f6eb22ffe0f6a467d7e72` |

Two additional checkpoint files were also present:

- `cnn_model.pth`
- `_smoketest.pth`

All seven files were loadable from CPU. None were modified during this preflight.

## 3. Checkpoint architecture vs instantiated models

Each checkpoint was loaded with `src/cnn_model.load_model()` and the inferred architecture was recorded. The result:

| Checkpoint | Inferred patch | Inferred residual | Inferred params |
|---|---|---|---|
| `v1_full.pth` | 5×5 | True | 112,417 |
| `v2_no_residual.pth` | 5×5 | False | 112,353 |
| `v3_no_weighted_loss.pth` | 5×5 | True | 112,417 |
| `v4_patch3.pth` | 3×3 | True | 46,881 |
| `v5_patch7.pth` | 7×7 | True | 210,721 |

Those inferred values match the canonical variant table used by the ablation script and the validation report:

- `v1_full` → 5×5 residual, 112,417 params
- `v2_no_residual` → 5×5 no residual, 112,353 params
- `v3_no_weighted_loss` → 5×5 residual, 112,417 params
- `v4_patch3` → 3×3 residual, 46,881 params
- `v5_patch7` → 7×7 residual, 210,721 params

Therefore, architecture inference is consistent between the checkpoint loader and the expected model definitions. No architecture mismatch was found.

## 4. Experiment scripts and imports

Preflight checked that the following scripts are present and parse cleanly:

- `baselines_comparison.py`
- `baselines_rgb_comparison.py`
- `eval_ablation.py`
- `run_anal_v2.py`

In addition, the core import path needed by the grayscale and RGB scripts was inspected:

- `src/rdhei_core.py`
- `src/rdhei_color.py`
- `src/cnn_model.py`
- `src/predictor.py`
- `src/baselines.py`
- `src/metrics.py`
- `src/encryption.py`
- `src/utils.py`

All of those modules imported successfully during the smoke test run. No import-time defect was found in the scripts or in the core source tree.

## 5. `run_anal_v2.py` syntax status

`run_anal_v2.py` currently parses cleanly with Python’s `ast` module.

During preflight inspection, the script’s CNN benchmark loop contained this visually broken indentation:

```python
        print("\nBenchmarking CNN Variants...\n")

            # ==========================================================
            # CNN Runtime
            # ==========================================================

        for (
            name,
            model_file,
            patch_size,
            residual
        ) in CNN_MODELS:
```

Even though that block is indented incorrectly, it is **not** currently a Python syntax error because the misplaced comment lines sit inside a parenthesized expression started by `print("\nBenchmarking CNN Variants...\n")`. So at this moment:

- The file is syntactically valid.
- The indentation is still wrong and would be misleading or fragile.

Because the experiment plan expects `run_anal_v2.py` to be used for runtime benchmarks, that file still needs a real fix before Phase 5, but it does **not** need to be treated as a blocking syntax defect at preflight time.

## 6. Datasets

Preflight verified the datasets directly.

### Grayscale

`data/kodak_gray/` contains 6 valid grayscale PNG images:

- `Airplane.png` — 512×512
- `Baboon.png` — 512×512
- `Goldhill.png` — 576×720
- `Jetplane.png` — 1024×1024
- `Lena.png` — 512×512
- `Peppers.png` — 512×512

### RGB

`data/kodak_color/` contains 6 valid RGB PNG images:

- `4.2.03.png` — 512×512×3
- `4.2.05.png` — 512×512×3
- `4.2.06.png` — 512×512×3
- `4.2.07.png` — 512×512×3
- `images.png` — 225×225×3
- `lena.png` — 512×512×3

Note: the dataset directories also contain `:Zone.Identifier` files. Those are Windows stream metadata artifacts and are not images. Scripts must ignore them. Both `baselines_comparison.py` and `baselines_rgb_comparison.py` already filter by image extension, so they should not treat these as images. `eval_ablation.py` does the same.

Image **counts are lower than the number mentioned in the project description**. The description and validation report both say “12 Kodak images” for grayscale and color, but only 6 valid grayscale and 6 valid RGB images are present here. This must be treated as a dataset reality and recorded in every experiment artifact. Do not assume 12 images.

## 7. Python environment and dependencies

The environment used for preflight was:

- Python `3.10.12`
- `numpy` `2.2.6`
- `torch` `2.14.0+cu130`
- `scipy` `1.15.3`
- `matplotlib` `3.10.9`
- `Pillow` present (imported through `from PIL import Image`)
- `pycryptodome` installed during this preflight because it was not already present in the active Python environment

Before this preflight, the active environment was missing `pycryptodome`. That dependency was installed with:

```bash
pip3 install pycryptodome
```

After that install, all required imports succeeded and the built-in encryption tests passed.

The project’s `requirements.txt` in `RDHEI_FIXED_V1/` lists:

- `numpy>=1.24`
- `Pillow>=9.0`
- `pycryptodome>=3.18`
- `torch>=2.0`
- `scipy>=1.10`
- `matplotlib>=3.7`

The current environment satisfies those bounds, except that `pycryptodome` was not pre-installed in the active environment. That is a real preflight finding.

A separate `venv/` directory was referenced in the parent workspace structure, but the active Python interpreter used for preflight did **not** correspond to that virtual environment. The preflight was therefore executed in the current system/user Python environment instead. This means the environment is usable, but it is not confirmed to match the project’s intended virtual environment.

## 8. Risk of overwriting existing results

Preflight checked the contents of the result directories:

- `results/gray/` — empty
- `results/rgb/` — empty
- `results/ablation/` — empty
- `results/runtime/` — empty
- `results/tables/` — empty
- `results/figures/` — empty
- `results/smoke_tests/` — newly created during this preflight and now contains:
  - `smoke_gray_20261013T013532.csv`
  - `smoke_gray_20261013T013532.png`
  - `smoke_rgb_20261013T013532.csv`

There is currently no `results/raw/` directory.

Because the experiment folders are empty, full experiments launched into the default `--results` locations would create new files rather than overwriting prior experiment outputs. That is good for reproducibility. However, a couple of script defaults are not aligned with the intended `results/` layout:

- `baselines_rgb_comparison.py` defaults to `--results results_ss`
- `run_anal_v2.py` writes to `results/runtime/` and references `models_ablation`

So the scripts are capable of writing into existing folders, and care is still needed when passing output paths. There are no preexisting experiment artifacts that can be silently clobbered right now, but the scripts do have different default result locations and must be invoked with explicit output directories when the plan requires the canonical `results/gray/`, `results/rgb/`, and `results/ablation/` structure.

## 9. Encryption fix verification

The encryption fix is present and was verified directly.

### What was fixed

The repaired code no longer encrypts all RGB channels with the same AES-CTR nonce. Instead:

- `encrypt_rgb_channels()` encrypts R, G, B with unique nonces
- `decrypt_rgb_channels()` decrypts with the same unique-nonce derivation
- Nonce derivation is `base_nonce + channel_index + 1`
  - R → `base_nonce + 1`
  - G → `base_nonce + 2`
  - B → `base_nonce + 3`
- `rdhei_color.run_rdhei_color()` uses unique nonces per channel and records each channel’s nonce in its per-channel results

### Security property that can be established

It can be established that, under the current implementation:

- The three channels do **not** reuse the same AES-CTR keystream under the same key when using `encrypt_rgb_channels()` / `decrypt_rgb_channels()`.
- The unique nonce allocation is deterministic and verifiable.
- Repeated encryption calls with a different `base_nonce` produce different ciphertext, because the nonce changes.

The built-in encryption test suite passed:

- Grayscale encrypt/decrypt
- Unique nonce derivation
- RGB encrypt/decrypt with unique nonces
- No keystream reuse

### What cannot be claimed here

It cannot be established that the overall system provides authenticated encryption. AES-CTR alone does not give integrity or tamper resistance. Also, the receiver still depends on `base_nonce` being communicated separately. Those limitations were already documented in `src/encryption.py` and `FINAL_VALIDATION_REPORT.md`, and they remain true.

### Conclusion on the encryption question

The distinct-channel and repeated-operation properties requested for preflight can be confirmed, so security-related claims may continue for the fixed RGB encryption path, within the documented limitations. There is no need to stop security claims at this time for the fixed code path.

## 10. Preflight status summary

| Check | Result |
|---|---|
| All five expected checkpoints present | **PASS** |
| Checkpoint architectures match instantiated models | **PASS** |
| Grayscale/RGB scripts present and parse cleanly | **PASS** |
| Core imports work | **PASS** |
| `run_anal_v2.py` syntax error | **NO BLOCKING SYNTAX ERROR**, but indentation defect present |
| Datasets accessible | **PASS**, 6 grayscale + 6 RGB valid images, not 12 |
| Python environment and dependencies available | **PASS after installing pycryptodome** |
| Existing result files at risk of overwrite | **LOW risk** (target dirs empty), but script defaults differ from intended layout |

## 11. Blockers

No blocking defect was found that would stop the planned smoke test or later experiments, with one caveat:

- RGB and grayscale execution should proceed only after `pycryptodome` is installed in the execution environment.
- Any runtime benchmark using `run_anal_v2.py` should still repair the indentation defect before being relied on, even though the file is currently syntactically valid.

## 12. Immediate next actions

- Run the automated smoke tests.
- Run one grayscale image and one RGB image through the evaluation scripts.
- Then proceed to full grayscale, RGB, ablation, and runtime experiments with explicit output paths under `results/`.

## 13. Reproduction commands for this preflight

```bash
cd RDHEI_FIXED_V1

python3 src/encryption.py

python3 - <<'PY'
import ast
for p in [
    "../baselines_comparison.py",
    "../baselines_rgb_comparison.py",
    "../eval_ablation.py",
    "../run_anal_v2.py",
]:
    with open(p, "r") as f:
        ast.parse(f.read())
    print(p, "SYNTAX_OK")
PY

python3 - <<'PY'
import sys, hashlib
from pathlib import Path
sys.path.insert(0, ".")
from src.cnn_model import load_model
for name in [
    "v1_full.pth",
    "v2_no_residual.pth",
    "v3_no_weighted_loss.pth",
    "v4_patch3.pth",
    "v5_patch7.pth",
]:
    p = Path("models") / name
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    model, patch, residual, n_params = load_model(str(p), device="cpu")
    print(name, sha[:12], "patch", patch, "residual", residual, "params", n_params)
PY
```

## 14. Notes for later phases

- Record actual image counts and filenames in every experiment artifact.
- Use explicit `--results` paths so outputs land under `results/gray/`, `results/rgb/`, `results/ablation/`, and `results/runtime/`.
- Preserve the existing `cnn_model.pth` and `_smoketest.pth` files untouched; they were present and loadable, but they are not the five ablation checkpoints listed in the experiment plan.
