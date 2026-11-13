# Expanded EDR1 grayscale evaluation

This adds an evaluation harness and an input-preparation utility. **It does not modify** `protocol.py`, `wire.py`, the CNN checkpoint, the EDR1 grid, the label map, or the reservation/embed/receive algorithms.

## 1. Prepare the expanded grayscale corpus

From the repository root, run:

```bash
python final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py
```

The utility downloads the official USC-SIPI archive volumes (textures, rotated textures, aerials, miscellaneous, and sequences), reads TIFF members without extracting arbitrary archive paths, and retains only native single-frame 8-bit grayscale images. RGB inputs are not converted to grayscale. Original TIFF bytes are copied unchanged under `data/usc_sipi_gray/<volume>/`. Archive hashes and per-image hashes are written to `data/usc_sipi_gray/dataset_manifest.json`.

The official database describes its images as 8-bit grayscale or 24-bit color and provides the original TIFF files. Some copyright status is uncertain, so keep the acquired corpus local and review the database's copyright notice before redistributing images.


### Keep the added TIFFs inside `data/kodak_gray/`

To follow the existing project layout and place all extra grayscale files under the same directory as the original six, run the preparer with an explicit output path:

```bash
python final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py \
  --output-dir data/kodak_gray
```

The original six PNG files at the root of `data/kodak_gray/` are left untouched; the downloaded TIFFs are written into separate volume subfolders such as `data/kodak_gray/textures/` and `data/kodak_gray/aerials/`. Then run the EDR1 gate with only that directory:

```bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/kodak_gray
```

Use a clean expanded output location (or retain the TIFFs already there) because the preparer deliberately refuses to overwrite existing TIFF corpora.

## 2. Preserve the original six-image baseline

Keep the existing six source files in a directory named:

```
data/kodak_gray/
  Airplane.png
  Baboon.png
  Goldhill.png
  Jetplane.png
  Lena.png
  Peppers.png
```

The runner requires these six filename stems to exist in that directory. It does not accept a similarly named file from the USC-SIPI directory as a substitute for an original baseline image.

## 3. Run the complete EDR1 test

Install the runtime dependencies:

```bash
python -m pip install numpy pillow pycryptodome torch
```

Then run:

```bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/kodak_gray \
  --data-dir data/usc_sipi_gray
```

The runner scans recursively, accepts only native 8-bit grayscale files, records unsupported files, and deduplicates identical decoded pixel arrays with the same dimensions. The original baseline directory is processed first when passed first, so baseline files remain the retained representatives of exact duplicates.

For each natural image, it records gross candidate slots, bootstrap-carrier opportunity cost, metadata bytes stored in the bootstrap, backup bits, net payload bits, net bpp, and acceptance/rejection. The accounting identity is:

```
net payload bits
  = gross candidate slots
  - gross slots foregone in bootstrap carriers
  - bootstrap backup bits
```

The wire metadata storage (header + encrypted directory + authentication tag) is also reported separately. This avoids subtracting metadata bytes twice: the metadata is physically stored in the bootstrap carrier bytes, while its capacity opportunity cost is measured by the ordinary slots lost at those carriers.

Every accepted natural image is tested with four separately reserved packets: empty payload, a short payload (37 bits unless capacity is smaller), half-capacity payload, and full-capacity payload. The receiver is launched in a fresh process for each case and must exactly recover both the original image and the payload. The three synthetic controls from the original gate are also retained.

Output is written to a new `evidence_expanded_YYYYMMDD_HHMMSS/` directory. Important files include:

- `capacity_summary.csv` and `capacities.json`
- `roundtrip_summary.csv` and `roundtrips.json`
- `input_manifest.json`, `corpus.json`, and `pixel_duplicates.json`
- `negative_checks_and_rejections.json`, `integrity.json`, and `run_summary.json`

Intermediate reserved/cipher/recovered arrays are removed after each successful case to keep disk usage bounded. Pass `--keep-artifacts` to retain those files for every case. The random test nonce range is freshly generated per run; the test master key is explicitly a public test key, never a deployed secret.

## 4. Expanded-only diagnostic run

A corpus-only diagnostic without the original six is possible with:

```bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/usc_sipi_gray \
  --allow-missing-baseline
```

This run must be reported separately from the combined baseline-plus-expanded experiment.


## 5. Full-corpus run through GitHub Actions

The repository workflow has two modes. Ordinary pushes execute the quick smoke test. The full natural-image run is an explicit, longer CPU job:

1. Add the exact six original PNG files to `data/kodak_gray/` on the `research/capacity-aware-edr1` branch: `Airplane.png`, `Baboon.png`, `Goldhill.png`, `Jetplane.png`, `Lena.png`, and `Peppers.png`. The `.gitignore` permits only these six baseline files at the root; generated TIFF folders and archive downloads remain untracked.
2. Open the repository's **Actions** tab and select **EDR1 expanded-gate harness**.
3. Select **Run workflow** and set `run_full_corpus` to `true`.
4. The job downloads and filters the official grayscale TIFF archives into volume subfolders under `data/kodak_gray/`, runs the full EDR1 gate, and uploads `edr1-full-natural-corpus-evidence` as a workflow artifact.

The full job intentionally fails at the baseline check when any original image is missing. Do not substitute differently sourced images under the same filenames; the baseline must match the six files used in the original experiment.
