# EDR2 and CC-EDR2-RGB: Static Cryptographic Security Review

**Review date:** 2026-11-15  
**Scope:** Grayscale EDR2 and the CC-EDR2-RGB extension, as implemented in this repository.  
**Review type:** Separate source-code-focused security review of the cryptographic design and implementation. This is **not** an external audit by an independent cryptographer, a formal proof, or a certification.

## Executive assessment

The implementation uses a coherent set of cryptographic building blocks: HKDF-SHA-256 for domain-separated key derivation, AES-256-CTR for confidentiality, and HMAC-SHA-256 for packet authentication. Grayscale EDR2 and RGB EDR2 derive separate image-encryption and data-hiding key domains. RGB further derives a distinct image key for each colour channel. Header stages, directory, payload, and authentication also have separate derived keys. The receiver authenticates the packet before decrypting or decompressing the label directory.

Those are positive design choices. They do not, by themselves, establish production security. The system remains a research protocol with custom packet framing and custom composition of encryption and authentication. The review identifies important deployment conditions and trust boundaries:

1. **Benchmark keys are public test material.** The RGB runner derives its benchmark master key from the public decoded-image hash and a fixed seed; the grayscale runner uses a public constant master key. These runs cannot demonstrate secrecy of the image or embedded payload. This is intentional benchmark behavior, but must never be confused with a production key setup.
2. **The authorized hider can forge authenticated packets.** The hider receives the derived data-hiding root, from which the HMAC key is derived. The HMAC therefore authenticates packets against parties without that capability; it does not provide owner-only origin authentication against a malicious/compromised hider.
3. **There is no anti-replay mechanism.** A previously valid marked image is accepted again when presented with its matching master key and nonce. The protocol needs external replay state or an authenticated application-level sequence/unique packet identifier if replay matters.
4. **Nonce uniqueness is a hard caller responsibility.** Reusing the same master key and 128-bit nonce recreates all per-packet derived keys; AES-CTR restarts its counter at zero. The production API does not maintain a persistent nonce registry or automatically prevent reuse.
5. **Key establishment and the owner-to-hider capability transfer are assumed, not implemented.** The specification requires an authenticated confidential channel for delivering the hider capability; this channel and its key lifecycle are outside the code reviewed here.

**Disposition:** suitable for continued research and controlled experiments, subject to the explicit benchmark-only key policy. Not ready to claim production-grade cryptographic security or to be deployed as a security product without addressing the findings and obtaining a genuinely independent cryptographic review.

## 1. Source scope inspected

| Component | Source reviewed | Purpose |
|---|---|---|
| Grayscale EDR2 | `final_rdhei_protocol_gate_20261022/wire.py` | HKDF, AES-CTR, HMAC framing, phase search, directory validation |
| Grayscale EDR2 | `final_rdhei_protocol_gate_20261022/protocol.py` | Owner reservation, receiver reconstruction, receiver input contract |
| Grayscale EDR2 | `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2.md` | Key/nonce, hider capability and threat-boundary statements |
| RGB extension | `final_rdhei_protocol_gate_20261022/rgb_wire.py` | Per-channel key derivation, CTR, HMAC, joint phase authentication |
| RGB extension | `final_rdhei_protocol_gate_20261022/rgb_protocol.py` | Regression synchronization, reservation, embed and receive paths |
| RGB benchmark | `final_rdhei_protocol_gate_20261022/run_rgb_gate.py` | Benchmark key policy, per-packet nonce namespace and payload trials |
| RGB specification | `final_rdhei_protocol_gate_20261022/PROTOCOL_EDR2_RGB.md` | Intended RGB cryptographic and receiver contract |

The RGB runner inspected includes a run-specific random nonce namespace and a distinct packet context for each image/blend/payload case. It creates a fresh reservation for each distinct payload length. Its run ledger explicitly labels benchmark keys as public test material. These are experiment-harness controls; they do not substitute for production nonce and key management.

## 2. Cryptographic construction observed

### 2.1 Key hierarchy

For both protocols, the receiver starts from a 32-byte master key (K) and a 128-bit nonce (V). The nonce bytes are used as the HKDF salt. A protocol-specific HKDF context derives a root, and separate context strings derive image and data-hiding roots.

Grayscale EDR2 derives one image-encryption key and one data-hiding root. RGB derives three channel-specific image keys, one each for R, G and B, plus a separate data-hiding root. From the data-hiding root, the implementation derives distinct keys for:
- bootstrap header encryption;
- final header encryption;
- encrypted label directory;
- payload bitstream encryption; and
- HMAC authentication.

The separate bootstrap/final header keys avoid reusing the same CTR key/counter stream for two different header plaintexts. The separate RGB image-channel keys avoid reusing one image CTR keystream across R, G and B.

HKDF's `info`/context input is intended to bind derived key material to application-specific context and prevent the same input key material from producing the same key across different uses. That is consistent with the purpose described in RFC 5869. [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869/)

### 2.2 Encryption

Image planes, headers, directories and payload data are encrypted with AES-256-CTR under their respective derived keys. The implementation starts the CTR counter at zero for each derived key. This is safe only when the derived key is packet-specific and is not reused for a different plaintext/ciphertext operation. Under a fixed master key, reuse of (V) recreates the derived keys and hence the same counter keystreams.

For CTR, counter blocks must remain unique across all messages encrypted under the same key. When a counter block/keystream is reused for two different plaintexts, XORing the ciphertexts exposes the XOR of the plaintexts. This is the standard CTR-mode failure condition described in NIST SP 800-38A. [NIST SP 800-38A](https://csrc.nist.gov/pubs/sp/800/38/a/final)

The experiment runner now handles the benchmark case by allocating a run-specific random namespace and deriving packet-specific nonces from the image and payload-case context. The production API itself accepts a caller-supplied nonce and does not enforce global uniqueness. Production code therefore needs a persistent unique nonce allocator per master key, including for empty payloads.

### 2.3 Authentication

The implementation derives a distinct authentication key and computes a full-length HMAC-SHA-256 tag. The tag covers the marked encrypted image, dimensions and phase information; the tag's own carrier bytes are zeroed for the MAC calculation. Verification uses `hmac.compare_digest`.

The RGB verifier tests candidate red-header locations and authenticates the six possible ordered G/B phase assignments for each red phase. It requires exactly one authenticated phase tuple before decrypting and bounded-decompressing the joint directory. The grayscale verifier similarly tests the four possible lattice phases and requires one valid authenticated parse before directory decompression.

HMAC is a standard keyed message-authentication construction; its security depends on the underlying hash and correct key management. [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)

This is a custom encrypt-then-authenticate-style packet composition, not a standardized AEAD API. RFC 5116 describes an AEAD interface that returns either authenticated plaintext or failure and requires distinct nonces for distinct invocations under a particular key. It is a useful design reference for future protocol revisions. [RFC 5116](https://www.rfc-editor.org/rfc/rfc5116/)

## 3. Positive implementation findings

| ID | Finding | Assessment |
|---|---|---|
| P1 | Image-encryption and data-hiding roots are derived under distinct HKDF contexts. | Good domain separation. |
| P2 | Header bootstrap, final header, directory, payload and authentication keys are distinct. | Reduces accidental cross-purpose keystream/key reuse. |
| P3 | RGB derives one image key per channel. | Avoids same-key CTR keystream reuse across channels. |
| P4 | RGB benchmark runner uses a fresh random namespace per run and distinct packet contexts; it creates a fresh reservation per tested payload. | Correctly addresses the earlier repeated-reservation nonce-reuse bug in the experiment harness, assuming cryptographic RNG and no namespace collision. |
| P5 | HMAC covers the complete marked image except the tag carrier itself, and binds dimensions and phase tuple. | Detects arbitrary ciphertext modification by parties without the authentication key. |
| P6 | HMAC verification is constant-time through `compare_digest`. | Appropriate tag-comparison primitive. |
| P7 | Directory decryption/decompression happens only after successful authentication; decompression is bounded and checks for trailing or incomplete streams. | Good parser hardening. |
| P8 | The receiver derives keys from the marked image, master key and nonce; no external image-dependent predictor/label/directory sidecar is loaded by the reconstruction functions. | Consistent with the stated receiver-side information model. |

## 4. Findings requiring remediation or explicit threat-model limits

### S1 — Benchmark keys are intentionally predictable
**Severity:** Critical for interpreting security experiments; not a production implementation defect if strictly confined to benchmarking.

The RGB benchmark master key is deterministically derived from the public image pixel hash and fixed benchmark seed. The grayscale gate uses a constant public test key. The RGB runner records `benchmark_keys_are_public_test_material: true`. Anyone who knows the evaluated image and seed can reproduce the benchmark keys. Thus the corpus experiments validate protocol mechanics, deterministic recovery, and evidence generation; they do not validate confidentiality against an adversary.

**Required action:** Keep these keys confined to tests. For deployment, generate/store a uniformly random 256-bit master key using a cryptographic random generator or a proper key-establishment protocol. Never reuse benchmark keys as credentials. State this limitation in the paper's security evaluation.

### S2 — Nonce uniqueness is not enforced by the production API
**Severity:** High.

The key derivation depends on (K,V), while AES-CTR begins from counter zero. Reusing (V) with the same (K) recreates the same image, header, directory, payload and authentication keys. Re-encrypting different plaintext under a repeated key/counter stream leaks XOR relationships and can destroy confidentiality. The documentation correctly prohibits nonce reuse; the API does not maintain state to enforce this requirement.

**Required action:** Add a persistent per-master-key nonce allocator or packet-sequence service, with atomic reservation, collision checks and durable storage. Fail closed on any duplicate ((K,V)) pair. The rule applies to empty-payload and failed/aborted packet attempts as well as successful payloads. Record the nonce in the packet/session metadata available to the receiver, while not treating it as secret.

NIST specifies CTR's unique-counter-block requirement across all messages under a key; the practical risk of nonce/IV reuse is also emphasized for authenticated encryption schemes. [NIST SP 800-38A](https://csrc.nist.gov/pubs/sp/800/38/a/final) [NIST SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final)

### S3 — The authorized hider holds the packet-authentication key
**Severity:** High trust-boundary limitation.

The owner gives the hider the data-hiding capability root. The HMAC key is derived from that root, so the hider can calculate valid tags for arbitrary modified packet contents, not only for payload changes performed by the prescribed embedding routine. The hider cannot derive the separate image-encryption key from the data-hiding root, but it can forge the packet's authentication tag and construct authenticated headers/directories. Consequently, the tag establishes integrity against parties that do not possess the hider capability; it does not protect the owner/receiver from a malicious or compromised authorized hider.

**Required action:** State this trust assumption explicitly. If owner-origin authentication is required, add a separate owner-only authentication mechanism (for example, a signature or an owner-only authenticator over the pre-hiding ciphertext and a defined image identity) that the hider cannot forge. Do not claim that the HMAC proves the final image was only modified by a correct/non-malicious hider.

### S4 — No replay protection
**Severity:** High when application freshness matters.

A valid marked image with its original (K,V) can be replayed. The cryptographic packet authentication does not tell the receiver whether the packet is fresh or whether a later packet has already been processed. The current receiver accepts an authentic replay unless an application layer rejects it.

**Required action:** Bind a packet identifier, sequence number, transaction ID or freshness epoch into the authenticated header/tag and keep receiver-side replay state. If a stateless receiver is a design requirement, document that replay prevention is outside the protocol's security guarantees.

### S5 — Key delivery and lifecycle are not part of the implementation
**Severity:** High operational dependency.

The protocol specification assumes the owner transfers the data-hiding capability to the independent hider over an authenticated confidential channel. The code returns the capability key but does not implement or verify a key-delivery mechanism, access-control policy, key expiry, revocation, rotation, or secure deletion.

**Required action:** Specify and test authenticated key establishment/delivery, per-hider authorization, revocation and rotation. The hider must receive only the intended data-hiding capability, not the master key or image-encryption key.

### S6 — Header fields are parsed before the packet MAC can be verified
**Severity:** Medium; bounded parser behavior is present.

The receiver must decrypt the bootstrap header to learn where the tag and directory are located. It validates magic, reserved bytes, codec and basic directory bounds before computing the HMAC. The implementation does not decompress or consume the directory until after authentication, which is good. Nevertheless, pre-authentication header parsing creates an exposed malformed-input path and can consume CPU/memory.

**Required action:** Keep strict maximum dimensions, directory lengths and total message sizes; fuzz malformed headers and boundary lengths; normalize public errors; rate-limit remote receiver interfaces. Where feasible, redesign framing so the minimum authenticated bootstrap can be located without trusting attacker-controlled unbounded lengths.

### S7 — Custom CTR/HMAC composition has no protocol-level proof
**Severity:** High for production deployment.

AES-CTR provides confidentiality, not authentication by itself. The separate HMAC key and full-packet tag are positive, but the overall construction also includes staged headers, in-band directory offsets, phase discovery, ciphertext-domain writes, and receiver reconstruction. The source review does not establish a formal proof for this composition or cover subtle interaction/rollback/oracle behavior.

**Required action:** Obtain review by a cryptographer independent of the project. Develop a formal threat model and packet-security argument. Evaluate whether the custom construction can be reduced to a standard AEAD design (e.g. an AEAD-protected packet metadata/payload with image bytes as associated data), while preserving the RDHEI reversible-carrier constraints. Do not substitute a superficial AES-GCM swap without analyzing the reversible format and nonce requirements.

### S8 — Replay/oracle and availability testing is incomplete
**Severity:** Medium.

The code includes wrong-key and tamper-rejection test paths, and bounded decompression. The review did not find a complete adversarial test suite for replay, nonce collision, key delivery, malicious hider behavior, parser fuzzing, error-message/timing or resource-exhaustion behavior. RGB phase discovery hashes the full image for multiple candidate phase tuples; malformed inputs can cause repeated full-image HMAC work.

**Required action:** Add adversarial test cases and fuzzing around header framing, directory bounds, duplicate/ambiguous phases, payload lengths, wrong key/nonce, replay, truncated images, oversized images and repeated failed authentications. Consider a cheaper bounded pre-authentication rejection path and receiver rate limits.

## 5. RGB-specific protocol observations

- The three RGB planes derive distinct image keys using channel-specific HKDF context labels.
- The hider subkeys are under a distinct RGB protocol context; the grayscale EDR2 hider hierarchy is not reused.
- The HMAC message includes image dimensions and the full four-phase tuple; the encrypted directory is itself included in the authenticated marked array and carries the phase tuple and blend ratio.
- The verifier authenticates the candidate phase tuple before decrypting/decompressing the label directory.
- The 24 phase permutations, four blend values, and exact-recovery cases are experimental/protocol correctness tests; they do not constitute cryptographic security proofs.
- The run-specific random nonce namespace in `run_rgb_gate.py` fixes the runner's repeated-packet issue. It must not be presented as a production nonce allocator.
- `stable_ids` derives the benchmark key from public input identity and seed. That is explicitly benchmark-only and cannot establish confidentiality.
- The owner-to-hider capability includes the authentication key by derivation, so a malicious hider can forge a tag. This is a threat-model boundary, not a bug in HMAC itself.

## 6. Threat model suitable for the current research paper

A narrow, defensible statement is:

> The protocol uses HKDF-SHA-256 for key separation, AES-256-CTR for image/directory/payload confidentiality under packet-specific derived keys, and HMAC-SHA-256 to authenticate the marked encrypted image and in-band recovery metadata. The receiver verifies the packet tag before decrypting and bounded-decompressing the label directory. The security model assumes a high-entropy secret master key, strict non-reuse of the per-packet nonce under that key, and authenticated confidential delivery of the derived data-hiding capability to an authorized hider. The current benchmark keys are public test material and are not used to claim confidentiality. The design does not currently provide replay protection or owner-only authentication against a malicious authorized hider.

Do not claim:
- formal cryptographic security proof;
- production certification;
- protection against a malicious authorized hider;
- replay resistance;
- confidentiality demonstrated by the public benchmark keys; or
- independent external audit completed.

## 7. Recommended security acceptance gates before deployment

1. Replace public benchmark keys with generated 256-bit secret keys in a deployment-only test harness.
2. Implement durable per-key nonce uniqueness, atomic allocation and collision detection.
3. Define and test the authenticated owner-to-hider key-delivery mechanism, revocation and rotation.
4. Decide whether an authorized hider is trusted to create the final HMAC; if not, introduce a separate owner-authentication mechanism and formalize exactly which fields the hider may change.
5. Add replay-state or a documented no-replay guarantee at the application layer.
6. Fuzz framing and directory parsing; add maximum image/directory limits and uniform external failure behavior.
7. Obtain a genuinely independent cryptographer's review and a protocol proof/analysis before production use.

## References

- NIST, **SP 800-38A**, *Recommendation for Block Cipher Modes of Operation: Methods and Techniques*, especially CTR mode and counter-block uniqueness. https://csrc.nist.gov/pubs/sp/800/38/a/final
- NIST, **SP 800-38D**, *Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC*, uniqueness requirements on IVs under a key. https://csrc.nist.gov/pubs/sp/800/38/d/final
- Krawczyk and Eronen, **RFC 5869**, *HMAC-based Extract-and-Expand Key Derivation Function (HKDF)*, including application/context-specific `info`. https://www.rfc-editor.org/rfc/rfc5869/
- Krawczyk, Bellare and Canetti, **RFC 2104**, *HMAC: Keyed-Hashing for Message Authentication*. https://www.rfc-editor.org/rfc/rfc2104/
- McGrew, **RFC 5116**, *An Interface and Algorithms for Authenticated Encryption*, including AEAD nonce and authenticated-decryption interface requirements. https://www.rfc-editor.org/rfc/rfc5116/

## Final reviewer conclusion

The implementation demonstrates deliberate key-domain separation, full-packet HMAC verification, bounded authenticated directory parsing and, in the RGB runner, fresh per-packet benchmark nonces. Those are meaningful engineering strengths. The principal security limitations are equally clear: predictable benchmark keys, caller-enforced nonce uniqueness, an authorized hider that also knows the MAC key, no replay defense, and unimplemented key-delivery/lifecycle mechanisms. This document is a source-based static assessment only. An external cryptographic audit remains outstanding.
