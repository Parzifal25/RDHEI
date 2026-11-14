# RDHEI project

## Current research implementation: EDR2

The active research branch is research/capacity-aware-edr1. Its current protocol implementation is **EDR2**, a grayscale RRBE/RDHEI design with receiver-side external-side-information-free recovery.

### Receiver contract

The receiver's only per-image semantic inputs are:

- Final marked encrypted image
- 32-byte master key K
- 128-bit nonce V

The decoder and frozen CNN-3x3 checkpoint are installed shared protocol software. No external prediction map, label map, error map, location map, backup file, payload-length file, directory file, or sender state is required by the receiver. The label directory, framing, bootstrap backup, authentication tag, and payload are embedded in-band in the marked image.

The independent data hider receives one nonce-specific derived data-hiding capability key Kh from the owner. Kh is cryptographic keying material, not an image-dependent map; the hider does not receive K or the image-encryption key. The owner-to-hider key handoff is not a receiver input, and EDR2 does not claim to eliminate all owner-hider communication.

### Key implementation files

| File | Role |
|---|---|
| final_rdhei_protocol_gate_20261022/predictor.py | Frozen 3x3 CNN prediction, step-2 safe-zone lattice, error-class labels and compressed directory |
| final_rdhei_protocol_gate_20261022/wire.py | EDR2 encrypted header, directory, payload, HMAC and encrypted-domain hider |
| final_rdhei_protocol_gate_20261022/protocol.py | Owner reservation, encryption, receiver payload extraction and exact image reconstruction |
| final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md | Canonical current EDR2 protocol specification |
| final_rdhei_protocol_gate_20261022/run_gate.py | Natural-image-only full capacity and exact-recovery evaluation |
| final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py | Native 8-bit grayscale USC-SIPI corpus preparation |
| src/train.py | Repaired CNN training utility with image-level train/validation split and a training manifest |
| src/rdhei_core.py | Legacy dense baseline; its receiver requires external maps and is not the EDR2 decoder |

### Natural-image evaluation

The EDR2 research evaluation excludes synthetic images. It requires the exact original six grayscale test PNGs at the root of data/kodak_gray/ and can additionally evaluate the native grayscale USC-SIPI subset. Unsupported RGB/16-bit inputs are skipped and recorded; they are not silently converted to grayscale. Exact pixel duplicates are deduplicated by dimensions and decoded pixel content.

Prepare the added USC-SIPI grayscale corpus:

~~~bash
python final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py \
  --output-dir data/kodak_gray \
  --archive-dir data/usc_sipi_archives
~~~

Run the full EDR2 gate:

~~~bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/kodak_gray \
  --output-dir /tmp/edr2-natural-corpus-evidence
~~~

For every accepted natural image, the runner records gross ordinary slots, bootstrap opportunity cost, physical metadata storage, backup bits, signed net payload bits, net bpp, and acceptance. It then runs empty, short, half-capacity, and full-capacity packets through a fresh hider and a fresh receiver process, comparing both the recovered image and extracted payload exactly. Rejected natural images remain in the capacity table with their rejection reason.

The full corpus job is opt-in via GitHub Actions workflow dispatch. The exact original six baseline files must be available on this branch. The default CI path runs compile and unit tests only.

### Training status

The legacy trainer had two issues: it passed the device string as the model's patch-size positional argument, and it split overlapping patches after extraction, allowing nearly identical patches from the same image into training and validation. src/train.py now uses explicit model keywords, splits source images first, then lazily extracts training/validation patches. It supports a 3x3 model and writes a reproducibility manifest with source file hashes and split membership.

This repair does not prove the provenance of the existing models/v4_patch3.pth checkpoint. Do not claim exact training corpus, training schedule, or validation metrics for that checkpoint without its original training manifest. Retraining is a separate controlled experiment and must use an explicit, documented dataset.

### Version boundary and research claims

- PROTOCOL_EDR2.md is the active protocol specification.
- PROTOCOL_EDR1.md and FINAL_RDHEI_PROTOCOL_GATE.md are historical EDR1 records. Their metrics—including synthetic-control results—must not be mixed with EDR2.
- The old src/rdhei_core.py receiver requires external maps and a payload length; it is retained as a legacy baseline and is not evidence for EDR2's receiver contract.
- CNN prediction and compressed in-band label maps are established RDHEI components. The step-2 synchronization-safe lattice, encrypted staged header/bootstrap, and exact receiver-only reconstruction are candidate contributions that require a full natural-image evaluation and a careful prior-art comparison before novelty or superiority can be claimed.
- Do not update the manuscript with EDR2 numerical results until the full natural-image workflow has completed and its evidence has been independently reviewed.
