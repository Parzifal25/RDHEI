# Independent cryptographic review request — EDR2

**Purpose:** Request an independent, written cryptographic review of the active EDR2 grayscale and CC-EDR2-RGB protocol implementations before any publication claim stronger than implementation-level integrity testing.

**Repository:** https://github.com/Parzifal25/RDHEI  
**Branch:** research/edr2-rgb-extension  
**Primary specifications:** final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md and PROTOCOL_EDR2_RGB.md  
**Implementation:** wire.py, rgb_wire.py, protocol.py, rgb_protocol.py, rgb_receiver_cli.py  
**Test entry points:** tests/test_edr2_publication_hardening.py, tests/test_edr2_receiver_only.py, tests/test_edr2_rgb.py, tests/test_edr2_rgb_dataset.py, tests/test_edr2_adversarial_packets.py

## 1. Protocol summary

The evaluated implementation separates a content owner, data hider and receiver.

- The content owner starts with the original image, a 32-byte master key and a 128-bit per-packet nonce. It prepares/reserves data-hiding space, encrypts the reserved image and creates a data-hiding capability for the hider.
- The hider receives the reserved encrypted image, payload and capability. It embeds encrypted payload bits and updates authenticated in-band framing without access to the original plaintext image or image-encryption key.
- The receiver receives the marked image, master key and nonce. It discovers framing/phase information from the packet, authenticates the packet before directory decompression, extracts the payload and reconstructs the original image.

The key hierarchy uses HKDF-SHA256 with domain-separated contexts. AES-256-CTR is used for confidentiality under derived keys. HMAC-SHA256 is used separately for packet integrity/authentication. RGB uses an EDR2RGB domain and channel-separated derived keys for R, G and B. AES-CTR is not an AEAD mode; the construction relies on the separate HMAC and the correctness of its key separation, packet binding and verification order.

The active receiver's semantic per-image inputs are the marked image, master key and nonce; the checkpoint and decoder are shared software. No sender-created per-image prediction, label, location or capacity sidecar is intended.

## 2. Threat model to review

Please state which guarantees hold under each of the following:

1. Passive observation of the encrypted/marked image, including visible dimensions and file length.
2. Active packet tampering, truncation, extension, reordering or malformed metadata.
3. Wrong-key and wrong-nonce attempts.
4. Reuse of a master-key/nonce pair across two different packets, including after crashes, retries or across hosts.
5. Replay of a previously valid packet to a receiver that does not maintain external freshness state.
6. A malicious or compromised authorized data hider. The current hider capability includes authentication authority; can it therefore create a new valid tag for a modified packet, and is that trust model explicit enough?
7. Compromise, rotation, revocation or leakage of the owner-to-hider capability.
8. Adversarial image dimensions, directory lengths, decompression inputs and resource-exhaustion attempts.
9. Timing/error-oracle behaviour, side channels, dependency compromise and unsafe parser/file-I/O paths.

## 3. Specific review questions

### Key derivation and nonce lifecycle
- Are the HKDF salt, input key material and every info/context string correctly constructed and collision-resistant across grayscale, RGB, channels, header, directory, payload and authentication domains?
- Does the actual AES-CTR API use counter state safely, with no possible counter wrap or accidental stream overlap for the largest supported packet?
- Is a 128-bit externally supplied nonce adequate for the intended deployment, and how should uniqueness be generated, persisted and enforced under each master key?
- Is the experiment's deterministic nonce derivation strictly isolated from deployment guidance?

### Authentication coverage and packet framing
- Does HMAC bind every security-relevant field, including the entire marked image, dimensions, framing, phase/blend tuple and all encrypted payload/directory carrier bytes?
- Is the tag-carrier zeroing/canonicalization rule unambiguous and identical between sender and receiver?
- Is authentication verified before any attacker-controlled decompression or data-dependent expensive processing?
- Are all alternate header locations/phases checked without ambiguous acceptance, parser differentials or authentication bypass?
- Are malformed, truncated, oversized and non-canonical directory encodings rejected safely and consistently?

### Trust separation and application security
- Does the owner-to-hider capability expose more authority than necessary?
- Is malicious-hider resistance possible or explicitly out of scope?
- Does the application need replay protection, transaction binding or one-time packet acceptance outside the image format?
- Are error messages and timing differences likely to reveal key, framing or payload information?
- What formal security model, reduction or proof would be appropriate for this protocol, and which claims should be removed?

## 4. Existing implementation evidence (not a substitute for your review)

- HKDF-SHA256 key separation and separate AES-256-CTR/HMAC-SHA256 keys are visible in the active source.
- The receiver checks authentication before decrypting/decompressing the directory.
- The grayscale parser converts malformed zlib streams into a controlled packet rejection.
- Regression tests cover wrong keys/nonces, tampering of representative authenticated regions, malformed headers, authenticated malformed compressed metadata and a deterministic 64-case mutation sweep.
- The expanded grayscale/RGB regression workflow passed in GitHub Actions Run #93: https://github.com/Parzifal25/RDHEI/actions/runs/43875481127

These are implementation/regression controls only. There is no independent cryptographic audit, formal proof, coverage-guided parser fuzz campaign, side-channel evaluation or security certification at this time.

## 5. Requested review deliverable

Please provide a dated report containing:

- Executive assessment and precise scope/version examined.
- Threat model and explicit assumptions.
- Findings ranked Critical / High / Medium / Low / Informational, with affected files/lines and reproducible examples.
- Assessment of KDF, key separation, CTR counter/nonce use, HMAC binding, packet parsing/decompression, replay handling and key-distribution trust.
- Required code changes and a retest plan.
- Exact claims that are supportable in a paper, claims that must be qualified and claims that must be prohibited.
- Clear statement of whether the work was an informal review, an independent audit under a defined scope, or something else. Do not describe it as a certification unless a certification scheme was actually used.

## 6. Publication-safe interim wording

Until an independent review is completed, the manuscript should say that the implementation combines domain-separated HKDF-derived AES-256-CTR keys with a separate HMAC-SHA256 packet-authentication key, verifies the packet before directory decompression, and passes the listed implementation regression tests. It must also state that nonce uniqueness is a deployment requirement and that independent cryptographic review and formal security analysis remain future work.
