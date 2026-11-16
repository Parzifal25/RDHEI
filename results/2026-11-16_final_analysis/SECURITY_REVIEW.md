# Security review — active EDR2 and CC-EDR2-RGB

**Type:** source-level implementation review, not an independent cryptographic audit.  
**Active implementation revision inspected:** `af872d0d984356eda66bd83ec8972dccb40f239c` (grayscale parser exception normalisation). The expanded deterministic adversarial regression suite passed in [Run #93](https://github.com/Parzifal25/RDHEI/actions/runs/43875481127).

## 1. Scope and active implementation

The review covers the active protocol implementations:
- `final_rdhei_protocol_gate_20261022/wire.py`
- `final_rdhei_protocol_gate_20261022/rgb_wire.py`
- `final_rdhei_protocol_gate_20261022/protocol.py`
- `final_rdhei_protocol_gate_20261022/rgb_protocol.py`
- `final_rdhei_protocol_gate_20261022/rgb_receiver_cli.py`
- the corresponding `PROTOCOL_EDR2.md` and `PROTOCOL_EDR2_RGB.md` specifications and receiver tests.

The older `src/encryption.py` is a legacy AES-CTR helper. Its own documentation says it has no authentication/integrity protection. It is not a basis for the security claims of the active EDR2/RGB packet implementation and must not be described as authenticated encryption.

## 2. Positive controls visible in the implementation

### 2.1 Key separation and nonce discipline

The grayscale EDR2 code derives a packet root from the 32-byte master key and a 128-bit nonce using HKDF-SHA256. Separate context strings derive image-encryption and data-hiding roots. Further context-separated keys are derived for bootstrap header, final header, directory, payload and authentication. The RGB protocol uses a distinct `EDR2RGB` domain and separate image keys for R, G and B channels.

The protocol uses AES-256-CTR under these derived keys. Counter streams start at zero per key domain; therefore the security condition is that the same key/nonce context must never be reused for a different packet. The implementation/specification explicitly prohibits reusing a packet nonce with the same master key. In RGB, channel separation is accomplished by distinct derived channel keys, not by reusing one channel key across the three planes.

This construction is consistent with the need for domain separation in a protocol-specific KDF, but an implementation review is not a proof that the complete key schedule is secure. HKDF is specified in RFC 5869.

### 2.2 Packet authentication and parsing order

The active protocol uses HMAC-SHA256 with a separate derived authentication key. The tag binds the marked image bytes, dimensions and the grayscale phase or RGB four-phase tuple. Tag-carrier bytes are set to zero when the tag message is formed, so the tag can be embedded in the carrier region without self-reference.

The receiver validates framing bounds and checks authentication before decrypting/decompressing the label directory. Directory parsing checks exact expected lengths, label classes and padding. The zlib decompression path is bounded to expected output length plus one byte and checks end-of-stream and unused/unconsumed data. This is a meaningful defensive parsing property, not a complete denial-of-service analysis.

HMAC is a message-authentication code. AES-CTR itself is a confidentiality mode, not an authenticated-encryption mode; the integrity property in this design comes from the separate HMAC construction and its key handling. NIST SP 800-38A defines CTR among confidentiality modes. RFC 2104 specifies HMAC.

### 2.3 Receiver input contract and tests

The receiver semantic inputs are the marked encrypted image, master key and nonce, with the common decoder/checkpoint installed as shared software. It does not accept sender-produced image-dependent prediction, label, location, error, payload-length or capacity sidecars.

The receiver test suite covers exact image/payload reconstruction, wrong key, wrong nonce, marked-image tampering, RGB distinct channel keys, non-default RGB blend recovery and partial-byte payload lengths. A new deterministic adversarial suite additionally mutates the grayscale header, encrypted directory, HMAC tag, payload carrier and non-carrier image body; checks malformed header modes/reserved fields/length bounds; authenticates a deliberately malformed compressed directory before verifying parser rejection; and applies 64 seeded one-bit packet mutations plus malformed dimensions. The new suite and existing grayscale/RGB protocol regressions passed in [Run #93](https://github.com/Parzifal25/RDHEI/actions/runs/43875481127). The grayscale parser now converts zlib decompression failures into a controlled packet-format ValueError. This is deterministic mutation/regression testing, not coverage-guided parser fuzzing or an independent cryptographic test programme.

## 3. Threat model: claims and exclusions

| Threat / property | Current evidence or behaviour | Claim boundary |
|---|---|---|
| Passive observer of marked encrypted image | AES-256-CTR encryption plus HMAC over packet | Do not claim a formal confidentiality proof for the entire RDHEI construction |
| Unauthorized packet modification | HMAC verification fails closed in implemented tests | Assumes secret authentication key remains secret |
| Wrong master key / nonce | Receiver rejects in tests | Does not address weak key generation or compromised key storage |
| Malformed directory | Framing, size, label and bounded decompression checks | Not a full fuzzing/DoS analysis |
| Authorized data hider | Hider possesses data-hiding capability and authentication key | A malicious authorized hider can modify and recompute the tag; no malicious-hider resistance claim |
| Nonce reuse | Explicitly prohibited by protocol | Deployment requires persistent, auditable uniqueness under each master key |
| Receiver access to original image | Guarded Python file opens and per-case audit records | Not an OS-level sandbox; lower-level file syscalls or code execution paths are not comprehensively contained |
| Timing/side channels | No dedicated measurement or mitigation assessment | No side-channel resistance claim |
| External cryptanalysis | None completed | No independent security certification or formal proof |

## 4. Critical deployment risks

1. **Nonce uniqueness is mandatory.** Reuse of a master-key/nonce context repeats derived keys and CTR keystreams. Production nonce allocation must be generated and durably recorded so uniqueness is maintained across crashes, retries, hosts and all users sharing the key.
2. **The experiment nonce policy is not a production policy.** Run #79 derived deterministic per-packet test keys/nonces from image identity, blend and payload case to make the experiment reproducible. Those values are not a recommendation for deployment.
3. **Hider capability distribution is security-critical.** The owner sends the derived hider capability through an authenticated confidential key-delivery mechanism. That channel and its lifecycle are assumed, not implemented/audited as part of the experiment.
4. **The authorized hider is trusted with authentication authority.** Because it has the MAC capability, it can create valid tags for modified packets. This threat is not covered.
5. **Replay/freshness is not enforced by the packet format.** A previously valid marked image and its matching key/nonce may be replayed to a receiver that does not maintain an external freshness ledger. Applications needing freshness must bind the packet to an authenticated transaction identifier or enforce one-time nonce/packet acceptance outside this prototype.
6. **The Python source-read guard is a measurement aid, not confinement.** It patches `builtins.open` and `io.open`; it does not create an OS namespace, seccomp policy, container boundary or filesystem sandbox.
6. **Legacy code must not be confused with active protocol code.** `src/encryption.py` implements raw AES-CTR without a packet MAC and documents that limitation. Use the active EDR2/RGB codepaths when describing the evaluated method.

## 5. Required security work before a strong security claim

- Commission an independent review of key hierarchy, HKDF context strings, AES-CTR key/counter separation, HMAC binding, bootstrap/final header handling, nonce lifecycle and key delivery.
- Extend the successful Atheris campaign beyond its initial 20,000 inputs, preserve a longer-lived seed corpus and crash corpus, and fuzz grayscale plus RGB framing/decompression entry points. The completed run is evidence, not exhaustive parser assurance.
- Expand tamper testing across all RGB and grayscale header/directory/tag carrier bytes, all truncation boundaries, oversized dimensions, decompression bombs and ambiguous phase candidates. The current grayscale regression covers representative authenticated regions, not every possible byte/length combination.
- Run static analysis and dependency review; pin library versions and hash the frozen decoder/checkpoint artifacts.
- Define the operational owner–hider–receiver trust model, including whether the hider may be malicious and how capability keys are delivered, rotated, revoked and stored.
- Evaluate denial-of-service and resource-exhaustion behaviour on adversarial dimensions and compressed directories.
- Document what image properties remain observable (dimensions, file container, image length, possible timing and traffic metadata).

## 6. Safe manuscript wording

Use:

> The evaluated implementation combines domain-separated HKDF-derived AES-256-CTR encryption keys with a separate HMAC-SHA256 packet-authentication key. The receiver authenticates the packet before directory decompression and rejects invalid framing or authentication. Wrong-key, wrong-nonce and tamper rejection are covered by implementation tests. These checks provide implementation-level integrity evidence; an independent cryptographic audit and formal security analysis remain future work.

Do not use:
- “military-grade encryption”;
- “unbreakable” or “100% secure”;
- “authenticated encryption with AES-CTR” (CTR is not AEAD);
- “zero-knowledge”;
- “receiver runs in a sandbox”;
- “resistant to malicious hiders”;
- “formally proven secure”.
