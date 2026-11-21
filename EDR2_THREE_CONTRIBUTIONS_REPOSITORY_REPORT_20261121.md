# Three Final EDR2 Evaluation Contributions — Repository Evidence

Date: 2026-11-21  
Repository: Parzifal25/RDHEI (main)

## Executive status

Repository review completed. The active EDR2 runtime benchmark harness exists at `final_rdhei_protocol_gate_20261022/run_edr2_e2e_benchmark.py`, but no execution results for that harness were present in the inspected repository. The connected GitHub repository interface is read/write file access, not a Python execution environment. Thus no new runtime/tamper numbers are fabricated here.

Important protocol distinction: evidence in `final_rdhei_protocol_gate_20261022/FINAL_RDHEI_PROTOCOL_GATE.md` is for EDR1's self-contained authenticated protocol. Do not attribute its measurements or HMAC rejection results to the original EDR2/AES-CTR pipeline.

## 1. Computational scalability

### Existing code
The EDR2 benchmark script measures:
- preparation: prediction and directory generation;
- reservation and encryption;
- encrypted-domain embedding and re-authentication;
- receiver authentication, extraction and recovery;
- end-to-end total;
- exact image/payload recovery;
- process RSS sampled every 5 ms;
- environment, checkpoint hash, nonce uniqueness, warmups and repeated trials.

Default fixture: deterministic synthetic 512×512 grayscale. Optional native grayscale image support is implemented.

### Existing historical evidence (not EDR2)
The repository also contains older runtime scripts/results for predictor-only and traditional pipeline runtime. These are contextual only and are not EDR2 scalability results.

### Run
From repository root:
```bash
python final_rdhei_protocol_gate_20261022/run_edr2_e2e_benchmark.py --output-dir results/edr2_runtime_512 --size 512 --warmups 1 --repeats 5
python final_rdhei_protocol_gate_20261022/run_edr2_e2e_benchmark.py --output-dir results/edr2_runtime_1024 --size 1024 --warmups 1 --repeats 5
python final_rdhei_protocol_gate_20261022/run_edr2_e2e_benchmark.py --output-dir results/edr2_runtime_2048 --size 2048 --warmups 1 --repeats 5
```
Use distinct output directories. Report stage-wise median/mean/std, total time, megapixels/s, RSS baseline/peak/delta, and exact-recovery checks. Add one native image run if available. Current status: **harness implemented; fresh execution pending**.

## 2. Net payload and storage efficiency

### Verified repository evidence (EDR1 protocol gate)
The EDR1 gate report contains explicit capacity accounting for compressed label directory, header, authentication tag, bootstrap reservation, original-byte backup and remaining payload. It reports 4/6 natural grayscale images with positive net capacity and 72,357 total bits among accepted natural images. This is EDR1, not EDR2.

### Historical EDR2 figures requiring raw-file revalidation
Previously reported EDR2 summary: 243 grayscale images; 163/243 positive net capacity (67.1%); mean signed net capacity 0.11054 bpp; pooled signed net capacity 0.05982 bpp; mean usable capacity among accepted images 0.14322 bpp. The raw final table was not retrieved during this repository review, so these are **provisional and must be checked against the exact committed CSV/JSON before manuscript use**.

### Final accounting
- Net payload = gross payload − image-dependent recovery information − metadata/framing − protocol overhead.
- Total storage = marked/encrypted image + required sidecars + metadata + any separately stored payload.
- Compare against a conventional encrypted original plus separately stored/transmitted payload at identical payload lengths.
- Measure actual serialized bytes. Avoid double-subtracting bootstrap/reserved costs already excluded by the capacity formula.
- Report net BPP, accepted-image fraction, distribution, image bytes and total artifact bytes.

Status: accounting methodology documented; matched EDR2 storage baseline not verified in inspected evidence.

## 3. Integrity and tamper detection

### Verified design limitation
The original `src/encryption.py` uses AES-CTR and explicitly documents no authentication/integrity protection. CTR alone does not detect ciphertext modification.

### Separate EDR1 evidence
The EDR1 protocol gate uses an in-image HMAC-SHA256 tag and reports rejection for corrupted inputs and wrong key/nonce/capability cases. These results must not be described as EDR2 results.

### Required EDR2 tests
1. Flip ciphertext bits.
2. Alter embedded payload carrier bits.
3. Alter nonce/metadata/length/phase fields.
4. Alter recovery maps/directory entries.
5. Truncate header or packet.
6. Submit malformed dimensions, class IDs and invalid format.
7. Record parsing, authentication, extraction, recovery, exception, explicit corruption detection, silent output corruption, and exactness.

Status: security limitation established from source; active EDR2 tamper suite and results not verified. Do not claim tamper detection unless a verified authentication mechanism covers the artifact and relevant metadata.

## Publication-safe statements

Supported:
- An EDR2 end-to-end runtime/memory benchmark harness is implemented.
- The repository contains prior EDR1 evidence with explicit net-capacity accounting and authenticated tamper rejection.
- AES-CTR alone does not provide integrity/authentication.
- Historical EDR2 capacity summaries indicate positive net capacity is image-dependent and limited; revalidate raw results.

Not supported until new runs:
- EDR2 scalability across resolutions.
- EDR2 tamper detection.
- EDR2 storage advantage over a matched conventional baseline.
- Any attribution of EDR1 results to EDR2.

## Execution limitation

The GitHub connector permits repository inspection and file writes, but cannot execute repository code. The commands above are ready for execution in the project’s Python/Colab/WSL environment. Raw outputs should be committed alongside this report before the manuscript is finalized.
