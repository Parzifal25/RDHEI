# RDHEI project

## Current research implementation: EDR2

The active publication-hardening branch is research/edr2-publication-hardening (based on research/capacity-aware-edr1). Its current protocol implementation is **EDR2**, a grayscale RRBE/RDHEI design with receiver-side external-side-information-free recovery. The current maximum-density four-phase lattice requires even image height and width; odd-sized inputs are rejected rather than processed under an unproven phase-count assumption.

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
| final_rdhei_protocol_gate_20261022/predictor.py | Frozen 3x3 CNN prediction, four-phase maximum-density step-2 lattice, signed-net-capacity phase selection, error-class labels and compressed directory |
| final_rdhei_protocol_gate_20261022/wire.py | EDR2 encrypted header, directory, payload, HMAC and encrypted-domain hider |
| final_rdhei_protocol_gate_20261022/protocol.py | Owner reservation, encryption, receiver payload extraction and exact image reconstruction |
| final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md | Canonical current EDR2 protocol specification |
| final_rdhei_protocol_gate_20261022/run_gate.py | Natural-image-only full capacity and exact-recovery evaluation |
| final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py | Native 8-bit grayscale USC-SIPI corpus preparation |
| src/train.py | Repaired CNN training utility with image-level train/validation split and a training manifest |
| src/rdhei_core.py | Legacy dense baseline; its receiver requires external maps and is not the EDR2 decoder |

### Natural-image evaluation

The EDR2 paper-facing evaluation excludes synthetic images and unreviewed files. It accepts the six fixed grayscale baseline PNGs at the root of data/kodak_gray/. Additional native 8-bit grayscale USC-SIPI files are considered only when their relative paths, source-file SHA-256 hashes, natural-image classification and curation notes appear in a manually reviewed natural_image_allowlist.json. Unsupported RGB/16-bit inputs are recorded; they are never silently converted. Exact pixel duplicates are deduplicated by dimensions and decoded pixel content. The run ledger records excluded synthetic and unreviewed files with reasons.

Prepare the added USC-SIPI grayscale corpus:

~~~bash
python final_rdhei_protocol_gate_20261022/prepare_usc_sipi_gray.py \
  --output-dir data/usc_sipi_gray \
  --archive-dir data/usc_sipi_archives
~~~

Run the full EDR2 gate:

~~~bash
python final_rdhei_protocol_gate_20261022/run_gate.py \
  --data-dir data/kodak_gray \
  --output-dir /tmp/edr2-natural-corpus-evidence
~~~

For expanded USC-SIPI data, prepare a curator-reviewed file-level allowlist after inspecting the inventory. Each entry must contain a relative path, exact file SHA-256, classification "natural", and a short curation note; no archive is automatically approved as a natural-image evaluation set.

For every accepted natural image, the runner records gross ordinary slots, bootstrap opportunity cost, physical metadata storage, backup bits, signed net payload bits, net bpp, and acceptance. It tests payload lengths 0, 1, short, half-capacity, capacity−1 and full capacity in fresh hider/receiver processes. Both recovered pixels and extracted payload bits must match exactly. Rejected natural images remain in the capacity table with their rejection reason.

The full corpus job is opt-in via GitHub Actions workflow dispatch. The exact original six baseline files must be available on this branch. The default CI path runs compile and unit tests only.

### Publication-hardening artifacts

- `EDR2_RESEARCH_POSITIONING.md` records the narrow contribution hypothesis, finite-domain lattice argument, prior-art checklist, experimental requirements, limitations and paper-writing gate.
- `final_rdhei_protocol_gate_20261022/natural_image_allowlist.example.json` documents the schema for manual natural-image curation. It is a template, not a valid allowlist.
- `tests/test_mapping.py` now uses real assertions and exhaustively checks all 65,536 original/prediction pairs and all 396,032 valid payload words under the deployed map.
- `tests/test_edr2_publication_hardening.py` checks the maximal-density lattice, header framing, image-state binding and corpus allowlist enforcement.
- `tests/test_edr2_receiver_only.py` checks receiver inputs, encrypted packet recovery and related protocol controls. Generated images in tests are unit fixtures only.
- `.github/workflows/edr2-natural-image-gate.yml` runs these tests on the publication-hardening branch.

The publication-hardening branch removes all committed constant-image feasibility result artifacts (56 files). No synthetic-image result is used in EDR2 metrics, aggregates, plots or paper claims. Generic generated arrays remain only as isolated unit-test fixtures for exact finite-domain and protocol checks; they are not experimental samples. Older EDR1 narrative records may still mention superseded synthetic controls, but those records are historical and must not be cited or reused in the EDR2 paper.

### Training status and frozen-checkpoint provenance

**No retraining is part of this EDR2 revision.** The existing residual CNN-3×3 checkpoint remains frozen; its SHA-256 is recorded at run time in the protocol identity and model identity files. The author confirms that the existing models were trained using 10,000 BOSSBase grayscale images. The current project does not contain the original per-checkpoint image manifest, training logs or complete split record, so the corpus and schedule are author-attested rather than independently reconstructed from the binary checkpoint.

A historical rejected-manuscript draft describes 200 sampled images, while the later project record and author confirmation describe 10,000 images. The revised paper must use one accurate account consistently and remove the stale 200-image statement if it does not describe the actual training run. Do not invent missing training logs, split membership or validation scores. The EDR2 work evaluates the supplied weights; it does not make a new training claim.

The repaired src/train.py is retained only as a future reproducibility utility. Its existence is not evidence that the historical checkpoint was created by that script.

### Version boundary and research claims

- PROTOCOL_EDR2.md is the active protocol specification.
- PROTOCOL_EDR1.md and FINAL_RDHEI_PROTOCOL_GATE.md are historical EDR1 records. Their capacity and recovery metrics must not be mixed with EDR2; the old synthetic-control observations are not part of the current publication dataset.
- The old src/rdhei_core.py receiver requires external maps and a payload length; it is retained as a legacy baseline and is not evidence for EDR2's receiver contract.
- CNN prediction and compressed in-band label maps are established RDHEI components. The candidate contribution is narrower: evaluate four maximum-density, context-invariant parity phases of the fixed 3×3 CNN lattice and select the phase with the greatest signed net payload after directory, header, authentication and bootstrap-backup costs. The selected phase is discovered from its phase-bound authenticated header location, not an external phase field. This adaptive phase-selection mechanism and its novelty remain conditional on full natural-image evaluation and comparison with current partitioning and adaptive-capacity RDHEI methods.
- Do not update the manuscript with EDR2 numerical results until the full natural-image workflow has completed and its evidence has been independently reviewed.
