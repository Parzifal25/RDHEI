# EDR2 natural-image evaluation

This evaluation is **natural-image only**. The paper-facing corpus contains the exact original six grayscale baselines plus the additional native USC-SIPI grayscale TIFFs. No generated or synthetic images are included in the capacity table or natural-image experiment. Small generated fixtures may be used inside isolated unit tests for file-format and input-validation assertions only; they are never passed to the EDR2 experiment runner and are never experimental observations.

## Dataset preparation

From the repository root, prepare the official USC-SIPI native grayscale subset:

~~~bash
python final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py \
  --output-dir data/kodak_gray \
  --archive-dir data/usc_sipi_archives
~~~

This retains only native, single-frame, 8-bit grayscale TIFF images (Pillow mode L, uint8, 2D). It does not convert RGB images to grayscale, resize, crop, or recompress source images. New TIFFs are placed in volume subdirectories under data/kodak_gray/; the six original PNGs stay at the root. Archive and per-file hashes are recorded in dataset_manifest.json. Review the USC-SIPI copyright notice before redistributing the dataset.

Required baseline files:

~~~text
data/kodak_gray/
  Airplane.png
  Baboon.png
  Goldhill.png
  Jetplane.png
  Lena.png
  Peppers.png
  textures/*.tiff
  rotate/*.tiff
  aerials/*.tiff
  misc/*.tiff
  sequences/*.tiff
~~~

Do not replace the original six baseline images with other files bearing the same names.

## Run EDR2 natural-image gate

Install dependencies:

~~~bash
python -m pip install numpy pillow pycryptodome torch
~~~

Run:

~~~bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/kodak_gray \
  --output-dir /tmp/edr2-natural-corpus-evidence
~~~

The runner recursively discovers files, accepts only native 8-bit grayscale images, records unsupported inputs, and deduplicates identical decoded pixel arrays with identical dimensions. The original six are required and must remain present. Every retained natural image receives a complete capacity row. The exact net-capacity identity is:

~~~text
net payload bits = gross ordinary slots
                 - bootstrap-carrier opportunity cost
                 - bootstrap backup bits
~~~

Physical in-band metadata storage (header + encrypted directory + tag) is also reported separately. It is not subtracted a second time because its opportunity cost is already represented by the ordinary slots lost at bootstrap carrier positions.

For every accepted natural image, the runner makes four independent packets: empty payload, a short payload (37 bits unless capacity is smaller), half-capacity, and full-capacity. The hider runs as a fresh process with one derived data-hiding key; the receiver runs as a fresh process with only the marked encrypted image, master key and nonce as semantic inputs. Both recovered image and extracted payload are compared exactly.

The output directory contains:
- capacity_summary.csv and capacities.json
- roundtrip_summary.csv and roundtrips.json
- corpus.json, input_manifest.json, skipped_inputs.json, pixel_duplicates.json
- negative_checks_and_rejections.json, integrity.json, protocol_identity.json, run_summary.json

Intermediate reserved/cipher/recovered arrays are removed after each successful case to bound disk use. Pass --keep-artifacts only when full per-case image/payload files are needed for a debugging run. The test master key is a public reproducibility key, never a deployed secret; the nonce sequence is unique within each test run.

## GitHub Actions

The EDR2 workflow runs compilation and isolated unit tests by default. Its unit tests create small temporary fixtures to verify grayscale-mode filtering, duplicate detection, archive-path confinement, the receiver input signature, and key-domain separation. These temporary test objects are not passed to the full EDR2 experiment runner. The opt-in full natural-image job verifies that the exact six baseline PNGs are present, downloads the native grayscale USC-SIPI TIFF subset, runs the complete EDR2 gate, and uploads the evidence artifact.

No synthetic-image capacity, bpp, PSNR, SSIM, MAE, or round-trip result may appear in the manuscript. Historical EDR1 synthetic-control rows are legacy software-feasibility checks and are excluded from all EDR2 research results.
