# Internal Cryptographic and Protocol Security Review — EDR2 / CC-EDR2-RGB

**Review type:** independent pass over the implementation and protocol specification within this project; not a third-party cryptographic audit  
**Review date:** 14 November 2026  
**Scope:** grayscale EDR2 and the R3D2 CC-EDR2-RGB extension  
**Disposition:** suitable for controlled research experiments after the recorded regression gates pass; not approved for production deployment

## 1. Executive assessment

The implementation uses a defensible separation of cryptographic domains: HKDF-SHA256 derives separate image-encryption and data-hiding roots, and the data-hiding root is expanded into independent header-bootstrap, header-final, directory, payload and authentication keys. RGB additionally derives separate image-encryption keys for the R, G and B planes. The packet integrity check is HMAC-SHA256 over the marked ciphertext image, dimensions and phase identity.

The principal cryptographic risk is operational rather than an observed break in the current test harness: **CTR nonce uniqueness is a hard security requirement, but the public protocol APIs do not maintain a persistent per-master-key nonce registry or reject nonce reuse across invocations.** A repeated master-key/nonce pair regenerates the same derived keys and therefore repeats the CTR counter streams. The benchmark runner now allocates a fresh nonce and reservation for every payload trial, but that does not enforce nonce uniqueness in a future deployed owner service.

The independent hider is also a trusted party. It receives the data-hiding capability, including the authentication key, and can therefore create a correctly authenticated but malicious marked image. The protocol must not claim resistance to a malicious authorized hider.

## 2. Reviewed construction

### Grayscale EDR2

- Master key: 32 bytes; packet nonce: unsigned 128-bit value.
- HKDF-SHA256 derives an EDR2 master root using the nonce as salt.
- The image-encryption key and data-hiding root use separate protocol context strings.
- The hider root is expanded into distinct bootstrap-header, final-header, directory, payload and authentication keys.
- AES-256-CTR is used under each derived key with counter initial value zero.
- HMAC-SHA256 authenticates the complete marked image, image dimensions and selected lattice phase, with the tag carrier bytes zeroed during MAC calculation.
- The receiver authenticates and bounds the in-band header and directory before directory decompression, prediction and pixel reconstruction.

### RGB R3D2

- R, G and B image-encryption keys are separately derived under channel-specific contexts.
- RGB hider keys use an EDR2RGB-specific root and separate header, directory, payload and authentication subkeys.
- The R3D2 encrypted directory carries the four-lattice phase assignment and the cross-channel blend numerator/denominator. The receiver uses this authenticated value rather than assuming a hard-coded blend.
- HMAC-SHA256 binds the marked RGB image, dimensions and complete four-phase tuple.
- The receiver searches the permitted phase assignments and accepts exactly one authenticated packet.

The project keeps EDR1, EDR2 and R3D2 protocol identifiers/key domains separate. Results from these protocol versions must not be pooled.

## 3. Positive findings

1. **Cryptographic domain separation is explicit.** Separate HKDF context strings distinguish image encryption, data hiding, header stages, directory, payload, authentication, RGB channels and the RGB protocol family. This follows the intended role of HKDF's `info` value: binding key material to application- and context-specific information.
2. **CTR is paired with authentication.** CTR provides confidentiality only. The implementation adds a separate HMAC key and verifies the tag before trusting packet metadata. This is materially stronger than using CTR alone.
3. **Header and directory processing are bounded.** Header fields are length-checked against the candidate lattice. Compressed directories are decompressed with an explicit maximum output length and checked for end-of-stream, unused data and trailing input.
4. **Tampering and wrong-key cases are tested.** The regression suite checks authentication failure for changed marked images and incorrect keys, alongside exact image and payload recovery tests.
5. **The RGB blend is now packet-bound.** R3D2 stores the blend ratio inside the encrypted, authenticated directory. The receiver no longer reconstructs with a compile-time 1/4 blend when the sender used another ablation setting.
6. **The benchmark runner separates packets.** Each distinct image/blend/payload experiment receives a fresh reservation and nonce. A random namespace is generated for each benchmark run. These values are public test material, not production secrets.
7. **Receiver-side sidecar claims are bounded.** The receiver uses the marked encrypted image, master key, nonce and installed shared protocol/checkpoint. The owner-to-hider capability-key handoff is separate and must not be described as absent.

## 4. Findings and required controls

### F-01 — CTR nonce reuse is catastrophic for confidentiality

**Severity:** Critical if violated; operational control required.

The APIs accept a nonce but do not persistently track whether it has already been used with the same master key. Because all derived keys are deterministic functions of the master key and nonce, reusing the pair repeats the same per-domain AES-CTR keys. Each CTR call starts its counter at zero, so the same key reuses counter blocks across packets. Reuse can expose relations between plaintexts and can reveal unknown plaintext where corresponding plaintext is known.

**Required control before deployment:** the content-owner service must allocate a unique nonce per packet under each master key, atomically and persistently. A durable monotonic counter or a collision-checked random 128-bit nonce scheme is suitable; the service must survive restarts, backups and concurrent writers without resetting the nonce state. Reject duplicate allocations. Do not treat the benchmark runner's random namespace as a deployment mechanism.

### F-02 — The authorized hider is trusted with packet authentication

**Severity:** High; trust-model limitation.

The hider receives the derived data-hiding capability and can derive the HMAC key. A malicious or compromised authorized hider can modify arbitrary ciphertext bytes and recompute a valid tag. The current construction therefore protects against unauthorized modification by parties that do not possess the authentication capability; it does not provide malicious-hider resistance.

**Required control:** document the hider as trusted. Use a separate policy and review if an untrusted or semi-trusted hider is a deployment requirement. Do not claim end-to-end integrity against the authorized hider.

### F-03 — Capability-key delivery is an external security dependency

**Severity:** High; system-integration requirement.

The independent hider receives a nonce-specific data-hiding capability from the owner. The repository specifies this as an authenticated confidential handoff but does not implement or validate a key-delivery protocol.

**Required control:** specify mutual authentication, confidentiality, key binding to the image/nonce/protocol version, rotation, revocation, storage and audit logging. The paper should state this channel as an assumption, not a solved contribution.

### F-04 — Replay and freshness are not provided

**Severity:** Medium; depends on application.

A valid previously generated marked image remains cryptographically valid for its matching key and nonce. The receiver does not maintain anti-replay state or an application-level sequence number.

**Required control if freshness matters:** bind a unique packet identifier or monotonic sequence to the authenticated packet and maintain receiver replay state. Do not claim replay resistance in the current protocol.

### F-05 — AES-CTR plus HMAC is not an AEAD construction

**Severity:** Medium; design/claim boundary.

The design uses AES-CTR for confidentiality and a separately derived HMAC-SHA256 key for authentication. This is a custom encrypt-then-authenticate packet construction, not a standardized AEAD mode. Its security depends on the exact MAC coverage, canonical parsing, key separation and order of verification.

**Required control:** preserve authentication-before-decompression/parsing. Have the complete construction independently reviewed. Do not describe AES-CTR itself as authenticated encryption or claim formal AEAD security.

### F-06 — Metadata and traffic-pattern leakage remain

**Severity:** Low/Medium; inherent observability.

The marked image dimensions and outer file/container size are visible. A receiver or observer can also infer that a marked packet exists. Header and directory contents are encrypted, but this does not hide all traffic metadata.

**Required control:** state this limitation in the security model. Do not claim metadata-oblivious transmission.

### F-07 — Cross-platform predictor identity is not established

**Severity:** Medium for reproducibility and exact recovery, not a direct cryptographic break.

Receiver reconstruction depends on the same frozen CNN checkpoint, preprocessing, rounding and deterministic integer regression procedure. The project records checkpoint hashes, but broad CPU/GPU, framework-version and hardware reproducibility has not yet been demonstrated.

**Required control:** pin software/checkpoint versions and run cross-environment exact-recovery tests before claiming platform-independent decoding.

## 5. Recommended deployment hardening

- Add a persistent nonce allocator keyed by master-key identifier; test concurrent allocation and restart/restore behaviour.
- Add key lifecycle controls for master keys and data-hiding capabilities, including secure provisioning, rotation, revocation and storage.
- Bind an authenticated packet identifier/protocol version into the MAC if replay detection is required.
- Retain distinct HKDF context strings for every protocol, channel and cryptographic purpose.
- Keep tag verification before decompression, prediction or expensive reconstruction.
- Add property/fuzz tests for malformed header lengths, compressed-directory edge cases, ambiguous phase discovery, modified tags and malformed RGB blend ratios.
- Commission a qualified external cryptographic review before production use.

## 6. Validation evidence reviewed

The source branches contain:
- exhaustive finite-domain EDR2 allocation/reconstruction checks;
- exact image and payload recovery tests;
- wrong-key and tamper rejection tests;
- RGB channel-key separation and partial-byte CTR tests;
- R3D2 receiver round trips for all four blend ratios using both mocked predictor fixtures and the frozen CNN checkpoint;
- fail-closed corpus and evidence-analysis gates.

These are implementation and protocol regression checks. They do not constitute a proof of cryptographic security or a substitute for an independent third-party audit.

## 7. External references

- NIST SP 800-38A, *Recommendation for Block Cipher Modes of Operation*: CTR requires distinct counter blocks across all messages encrypted under a given key. <https://csrc.nist.gov/pubs/sp/800/38/a/final>
- IETF RFC 5869, *HMAC-based Extract-and-Expand Key Derivation Function (HKDF)*: the `info` input binds derived keys to application-specific contexts. <https://www.rfc-editor.org/rfc/rfc5869>

## 8. Review conclusion

The current code has a clear cryptographic separation model and meaningful authentication/reversibility tests. The dominant unresolved risk is nonce lifecycle enforcement, followed by the trusted-hider and key-delivery assumptions. For an academic paper, describe these assumptions and limitations precisely and position the implementation as a research protocol. It is not yet a production-approved or independently certified cryptosystem.
