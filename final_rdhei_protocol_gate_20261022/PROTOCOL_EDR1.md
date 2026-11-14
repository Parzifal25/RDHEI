# Frozen protocol EDR1 (specified before implementation)

Scope: same-size 2D uint8 grayscale image; lossless pixel transport. Shared grid,
codebook, CNN-3x3 checkpoint, CPU inference and rounding match the existing B
prototype. No learning. Parties: owner has original X, master K and unique 128-bit
nonce V; embedder has only encrypted reserved image, V, payload, and per-image
directory/payload/authentication capability keys; receiver has final image, K, V
and installed decoder/model. Setup capability keys are cryptographic keys, never
maps. Receiver derives them from K,V; no extra receiver input. The owner never
receives the user payload. Embedder does not have the image encryption key.

KDF: HKDF-SHA256, salt=16-byte big-endian V, info=b'EDR1/'+domain,
32-byte outputs for domains image, directory, payload, auth. AES-256-CTR starts
at counter zero independently per derived key. A fresh V is mandatory for each
packet under K, including empty payloads; a reserved packet is single-use.
Payload encryption is independent of image encryption. No key reuse between
domains. Directory confidentiality is from outsiders, not the authorized embedder.
The public header reveals protocol, compressed-directory size, and payload length.
No semantic secrecy against the authorized directory reader is claimed.

Candidates are row-major (y,x) with y,x in range(2,dimension-2,3). All mutable
bytes are candidate centers. The masked 3x3 context of every candidate therefore
stays fixed, including when every bootstrap carrier changes. Shared predictor:
normalize float32 by 255, center=0, frozen eval model, CPU, four threads,
2048-patch batches, numpy nearest-even rint. Codebook is lexicographically sorted
distinct (n,lo,hi) values of the existing _compute_bpp_and_range(e), e=0..255.
Two 4-bit labels per byte, high nibble first; odd last low nibble zero. Choose
zlib9 only if strictly shorter than packed raw. Store one label per candidate.

Header: >4sB3xIQ, 20 bytes: magic EDR1, codec 0/1, three zero bytes, uint32 L,
uint64 payload bit length P. Next L bytes: directory ciphertext. Next 32 bytes:
HMAC-SHA256 tag. Hence H=52+L bootstrap candidate bytes. Header/directory/tag
overwrite those candidate ciphertext bytes. L and H are bounded by candidate
count; decoded raw directory must be exactly ceil(C/2) bytes. H<C.

Let ordered ordinary slots T list bit positions 7 down to 8-n at candidates
i=H..C-1; S=|T|. Let B=8H and N=S-B. Reject if N<=0, before producing a packet.
Split T into backup prefix T[:B] and payload suffix U=T[B:]. Splits may occur
inside a pixel. G0=sum(n over all C); F=sum(n over first H); S=G0-F.
Physical gross=8H+S. Net N=G0-F-8H. Metadata/framing/tag=8H; original
bootstrap backup=B. Payload encryption adds zero bits; unused slots are padding.

Owner reservation and encryption:
1. Predict from X; compute labels and H, T, B, N. Save original H carrier bytes
   as B bits, byte order then MSB first. In ordinary pixels keep original low
   8-n bits and replace their MSBs by backup || N zero bits. Set H carrier bytes
   to zero. This reserved image R has no user payload.
2. Encrypt all R with image subkey. Independently encrypt packed/compressed
   directory under directory subkey and install header(P=0), directory, tag
   at H carriers. Authenticate dimensions (>QQ) || full row-major image bytes
   with the 32 tag carrier bytes set to zero. Pass this packet to embedder.

Encrypted-domain embedder:
1. Verify packet HMAC, parse header, decrypt directory; derive T,B,N from labels.
   Needs no prediction/model/original/image subkey. Check 0<=P<=N and binary input.
2. Form payload || zeros to exactly N bits. Pack with zero low-byte padding,
   encrypt ceil(N/8) bytes using payload subkey, take first N ciphertext bits.
   Replace U ciphertext positions directly with those bits. Neither decrypt
   the image nor XOR user data into a pre-encryption plaintext image.
3. Update public P and HMAC; directory and backup prefix stay unchanged.

Receiver, only image,K,V:
1. Derive subkeys; bound header, authenticate before decompressing/inference.
   Decrypt directory, validate count/codebook/padding, reconstruct T,B,N, check P.
2. Read N ciphertext bits at U, pack with zero low-byte padding, apply payload
   CTR, take first N bits. Require decoded padding after P to be zero; return
   exactly first P bits (including P=0). Ignored low packing bits are never data.
3. Generate image keystream Z. Set ciphertext U positions to corresponding Z
   bits and H carrier ciphertext bytes to Z bytes, restoring their known-zero
   reservation plaintexts. All other ciphertext is already intact. Decrypt to R.
4. Extract B backup bits from T[:B]. Predict from unchanged noncandidate
   contexts in R. For each ordinary candidate, n=0 means leave byte unchanged;
   otherwise enumerate c in [0,255] with c mod 2^(8-n)=R_i mod 2^(8-n) and
   lo<=abs(c-p_i)<=hi. Require exactly one; restore it. Restore all H original
   carrier bytes from backup. Noncandidates were never changed.

Proof obligations: (a) contexts identical by grid geometry and center masking;
(b) exhaustive all x,p in 0..255 class-conditioned original uniqueness;
(c) backup T[:B] and U are disjoint even at within-byte split; (d) R ciphertext
is exactly restored before CTR inversion. Arbitrary overwritten ciphertext is
not magically recovered: U and bootstrap originals encrypt known zeros in R,
so their ciphertext is computable. Original ordinary MSBs are inferred from
residue,p,class; bootstrap original bytes are explicitly backed up. Their
arbitrary original ciphertext need not be stored because exact X is recovered.
CTR invertibility alone is not the recovery proof.

Authentication detects outsiders' modifications, not a malicious authorized
embedder holding auth capability. This is a feasibility codec, not an independently
audited cryptosystem. Model identity is installed by protocol version; no per-image
model selector is supplied. Cross-runtime floating point equivalence is not assumed.
Fixed test set: all six local kodak_gray PNGs, plus constant128, random256, tiny
image. Four payloads per accepted image: empty, 37 bits, floor(N/2), N. Reject
oversize input; test tamper and wrong keys; compare payload/image independently
after receiver exits. No tuning of grid/codebook/compression based on results.
