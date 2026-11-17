# Independent cryptographic review scope — EDR2 / CC-EDR2-RGB

Status: **external review not completed**. This document defines the review target and evidence package; it is not an audit opinion, certification, or proof.

## Systems under review

- Grayscale EDR2: `final_rdhei_protocol_gate_20261022/protocol.py`, `wire.py`, `predictor.py`.
- Colour branch CC-EDR2-RGB: `rgb_protocol.py`, `rgb_wire.py`.
- Key derivation, packet framing, authentication, decompression, and receiver recovery.
- Frozen checkpoints and codebook are common static dependencies. The receiver's per-image semantic inputs are the marked encrypted image, 32-byte master key, and 128-bit nonce.

## Security goals

1. Confidentiality of the original image against a party that sees the encrypted/marked image but does not know the master key.
2. Confidentiality of embedded payload bits against a party without the derived payload key.
3. Integrity/authenticity of the complete marked packet, including header, directory, payload carrier and image body, before parser or recovery processing.
4. Exact recovery of image and payload for a valid packet and correctly provisioned receiver.
5. Separation of owner, data-hider and receiver capabilities.

## Explicit trust assumptions and exclusions

- The 32-byte master key is generated, stored, and delivered securely outside this repository.
- The 128-bit nonce is unique for every packet under a given master key. The current stateless packet interface cannot enforce global nonce allocation or detect replay on its own.
- The authorised data-hider is trusted with its derived data-hiding capability. It can generate valid authentication tags and can therefore create or authenticate packets that do not represent the owner's intended payload. The system does not claim protection against a malicious authorised hider.
- AES-256-CTR is a confidentiality mode, not an AEAD mode. Integrity depends on the separate HMAC-SHA256 and strict authenticate-before-parse ordering.
- No claim is made here about side-channel resistance, compromised endpoints, secure key storage, availability/DoS resistance under arbitrary resource exhaustion, or formal cryptographic security proofs.

## Design elements for review

- HKDF-SHA256 derives a master root using the packet nonce as salt and domain-separated image/hider keys.
- Further HKDF-SHA256 derivations separate bootstrap header, final header, directory, payload and authentication keys. RGB also separates the three image-channel keys.
- AES-256-CTR uses independently derived per-domain keys; the nonce is reflected in those keys rather than passed as the AES-CTR counter nonce. Reusing the same master-key/nonce pair repeats derived keys and is therefore prohibited.
- HMAC-SHA256 authenticates the marked packet. The reviewer must verify exact byte coverage, tag construction, phase/header binding, constant-time tag comparison and that verification precedes directory decryption/decompression and all payload/image reconstruction.
- The receiver applies bounded decompression and validates directory shape, labels, payload length, phase assignment and capacity before recovery.
- Header and metadata are carried in-band. The receiver must use the exact frozen predictor/codebook/preprocessing convention; this is a correctness dependency rather than a secret per-image sidecar.

## Review questions requiring independent answers

1. Is the complete key hierarchy sound, with correct HKDF context separation and adequate key sizes?
2. Is AES-CTR used safely under the unique-nonce assumption? Are there counter/length edge cases?
3. Does HMAC cover every security-relevant byte and all interpretation metadata? Can any parser decision occur before successful authentication?
4. Are the header bootstrap/final stages and RGB phase-discovery process free of ambiguity or substitution attacks?
5. Can malformed lengths, decompression bombs, oversized arrays, integer overflow, malformed labels, or unusual dimensions cause memory exhaustion, unbounded CPU, or unexpected exceptions?
6. Are error paths, timing, logging, and process behavior exposing useful side-channel information?
7. Does the hider capability expose more authority than required? Is the authorised-hider trust assumption acceptable for the intended deployment?
8. What replay/freshness controls should be added at the application layer?
9. Are key generation, nonce allocation, key rotation, backup, revocation, and delivery sufficiently specified?
10. What formal security model and proof obligations are appropriate for publication?

## Existing test evidence (not certification)

- Deterministic grayscale packet tests include wrong key/nonce, tampering of header, directory, tag, payload and image body, authenticated malformed zlib content, invalid dimensions and framing.
- Grayscale parser: 20,000 Atheris coverage-guided inputs were run in a prior successful workflow. This is a finite run.
- RGB tests cover exact recovery, wrong key, packet tampering, key-domain separation and 24-phase assignment handling.
- RGB parser: 20,000 authenticated Atheris inputs completed in 14 seconds, 123 coverage counters, no crash artifact reported; CI run [44054823526](https://github.com/Parzifal25/RDHEI/actions/runs/44054823526), artifact ID `14315551603`. This is a bounded fuzz run, not an exhaustive proof.
- Exact image/payload recovery tests are correctness evidence, not cryptographic security proofs.

## Required independent deliverable

A reviewer with demonstrable cryptographic engineering experience should provide:
- Named reviewer(s), qualifications, review date, commit hash and files reviewed.
- Threat model and security-goal assessment.
- Findings classified by severity, reproducible evidence, and remediation recommendations.
- Retest of fixes, including key/nonce misuse, packet malleability, parser edge cases, and role/capability compromise.
- Explicit limitations and residual risks.

**Gate rule:** Do not change this status to “passed” until an independent reviewer has delivered a written report against a frozen commit and all critical/high findings have been resolved or formally accepted. A self-review or an automated test/fuzz run must not be described as an independent audit.
