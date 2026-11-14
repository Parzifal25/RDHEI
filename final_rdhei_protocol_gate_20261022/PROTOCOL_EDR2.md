# EDR2 protocol specification

**Version:** EDR2. This packet format and key hierarchy are not wire-compatible with EDR1. EDR1 is retained only as a historical record; EDR1 measurements must not be pooled with EDR2.

## 1. Objective and receiver-side information model

EDR2 is a grayscale reversible data hiding in encrypted images (RDHEI) design using reserve-room-before-encryption (RRBE).

The receiver's only per-image semantic inputs are:
1. The final lossless marked encrypted image.
2. The 32-byte master key K.
3. The 128-bit nonce V.

The matching decoder, fixed protocol constants, and frozen CNN checkpoint are preinstalled shared software. No external prediction map, label map, error map, location map, backup file, payload-length file, directory file, model selector, or sender state is accepted by the receiver.

All image-dependent recovery information is embedded in the marked image: encrypted header, encrypted compressed label directory, authentication tag, bootstrap-byte backup, and payload. This is a receiver-side external-side-information-free design, not a claim that the image itself contains no metadata.

The independent hider receives a nonce-specific derived data-hiding key Kh from the owner, the reserved encrypted image, and the payload. Kh is keying material, not an image-dependent map or sidecar. The hider never receives the master key K or image-encryption key. This owner-to-hider key handoff is separate from the receiver's inputs. EDR2 does not claim that no communication of any kind occurs between owner and hider.

## 2. Parties and responsibilities

| Party | Inputs | Responsibilities |
|---|---|---|
| Content owner | Original image X, master key K, unique nonce V, installed CNN | Predicts, builds labels, compresses directory, reserves reversible room, encrypts reserved image, derives Kh |
| Independent data hider | Reserved encrypted image, payload, Kh | Authenticates and parses in-band bootstrap; inserts encrypted payload bits in ciphertext domain; updates encrypted header and tag |
| Receiver | Final marked encrypted image, K, V, installed decoder/CNN | Extracts payload and reconstructs exact original image without external image-dependent inputs |

The owner completes reservation and image encryption before the user payload is supplied to the hider. The hider receives no original image, plaintext prediction, CNN, image-encryption key, or externally supplied capacity/map file.

## 3. Key derivation and nonce discipline

Let K be exactly 32 bytes and V an unsigned 128-bit integer. Let s be the 16-byte big-endian encoding of V.

    K_root = HKDF-SHA256(K, salt=s, info="EDR2/master-root", length=32)
    K_img  = HKDF-SHA256(K_root, salt=empty, info="EDR2/image-encryption", length=32)
    Kh     = HKDF-SHA256(K_root, salt=empty, info="EDR2/data-hiding-master", length=32)

The owner sends only Kh to the authorized hider through an authenticated confidential key-delivery mechanism. The receiver independently derives the same Kh from K and V.

From Kh, owner, hider, and receiver derive five distinct 32-byte subkeys using HKDF-SHA256 with the following context strings:

    K_header_bootstrap = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/header-bootstrap", length=32)
    K_header_final     = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/header-final", length=32)
    K_directory        = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/directory", length=32)
    K_payload          = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/payload", length=32)
    K_auth             = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/auth", length=32)

The implementation uses PyCryptodome HKDF-SHA256 with the listed values as distinct HKDF context strings. The separate image and hider domains prevent the hider from deriving K_img from Kh. The two header-stage keys are separate because reusing a CTR key for both reservation and final headers would expose the XOR of the header plaintexts to an observer obtaining both packet states.

AES-256-CTR uses an initial counter value of zero independently under each derived key. V must never be reused with K for another packet, including an empty-payload packet. Every reservation packet is single-use. Reusing V repeats derived keys and CTR keystreams and is prohibited.

## 4. Predictor, safe-zone lattice, and label directory

The current EDR2 implementation supports same-size two-dimensional 8-bit grayscale images (uint8, native grayscale mode L). The frozen residual CNN-3x3 checkpoint, preprocessing, CPU inference, rounding, and mapping are fixed protocol software. Owner and receiver must use the same checkpoint and numerically compatible inference behavior.

Candidate centers are row-major and lie on the fixed step-2 lattice:

    y in range(2, height-2, 2)
    x in range(2, width-2, 2)

Only these candidate-center bytes are mutable. A 3x3 masked predictor has Chebyshev radius one. Distinct step-2 lattice centers are separated by at least two pixels in at least one coordinate, so no other mutable candidate center can occur inside a candidate's 3x3 predictor patch. Consequently, changing any candidate center—including bootstrap carriers—does not alter the masked predictor input of any other candidate. This is the synchronization condition used by both owner and receiver.

For a 512x512 image with the fixed two-pixel border, the lattice contains 254x254 = 64,516 candidate centers (24.61% of all image pixels). The previous step-3 lattice contained 170x170 = 28,900 candidates (11.02%). The step-2 lattice has asymptotic density 1/4. The 64,516 figure is a geometric candidate count, not a measured net payload capacity.

For each candidate i, the owner predicts p_i, rounds using the fixed nearest-even rule, and computes the absolute error e_i. The existing allocation function maps e_i to a tuple (n_i, lo_i, hi_i), where n_i is the number of MSBs available for replacement and [lo_i, hi_i] is the admissible error interval used in recovery. The 15 distinct tuples are lexicographically sorted into a fixed codebook. One 4-bit class label is stored per candidate, two labels per byte, high nibble first; an unused final low nibble is zero. The packed directory is compressed with zlib level 9 only when the compressed result is strictly shorter than the raw packed directory.

## 5. In-band encrypted packet format

The first 20 candidate bytes carry a fixed-width header using the big-endian structure >4sB3xIQ:

| Field | Size | Meaning |
|---|---:|---|
| Magic | 4 bytes | EDR2 |
| Directory codec | 1 byte | 0 raw packed labels; 1 zlib-compressed labels |
| Reserved | 3 bytes | Must be zero |
| Directory length L | 4 bytes | Encrypted directory length in bytes |
| Payload length P | 8 bytes | User payload length in bits |

The 20-byte header is encrypted in-band using AES-256-CTR. The owner uses K_header_bootstrap for its reservation packet. After verifying and decrypting the bootstrap header, the hider writes the completed header using the distinct K_header_final. The receiver derives K_header_final from K and V. The distinct header keys prevent reservation/final header keystream reuse.

The next L candidate bytes contain the encrypted packed label directory. The next 32 candidate bytes contain an HMAC-SHA256 authentication tag. Therefore the total bootstrap is:

    H = 20 + L + 32 = 52 + L candidate bytes

The receiver knows the fixed header carrier coordinates from the installed protocol. It decrypts only those 20 header bytes, checks L against the candidate count before indexing the directory/tag, then verifies the HMAC before directory decompression or CNN inference. Directory length and payload length are encrypted in-band, not sent as external fields.

The HMAC input is the big-endian uint64 image dimensions followed by the full row-major marked-image bytes with the 32 tag-carrier bytes set to zero. This detects modification by parties without K_auth. The authorized hider holds the authentication capability; a malicious authorized hider can modify the packet and recompute its tag, so malicious-hider resistance is not claimed.

## 6. Capacity accounting and bootstrap reservation

Let C be the number of candidate centers and n_i the number of ordinary MSB slots assigned to candidate i. Define total gross ordinary slots:

    G0 = sum(n_i for i = 0,...,C-1)

The first H candidates hold the encrypted header, directory, and tag. Their ordinary slots are unavailable. Define:

    F = sum(n_i for i = 0,...,H-1)
    S = G0 - F

Enumerate ordinary slots at candidates H,...,C-1 in candidate order and bit order 7 down to 8-n_i as T. The owner must preserve the original H bootstrap candidate bytes. The required backup is B=8H bits. Split T into:

    T_backup = first B bits of T
    U        = remaining bits of T
    N        = |U| = S - B

Reject before packet creation if N<=0. Signed net capacity is:

    N = G0 - F - 8H

The physical metadata storage is 8H bits in the bootstrap. Its opportunity cost against the ordinary candidate budget is F, because the bootstrap candidates no longer supply their normal n_i slots. The separate backup prefix costs B=8H ordinary slots. These terms must not be double-counted. The equivalent physical accounting is:

    physical slots = 8H + S
    physical metadata = 8H
    original bootstrap backup = 8H
    net payload = physical slots - metadata - backup = S - 8H

The experiment ledger reports physical metadata bits, lost ordinary slots F, backup bits B, and N separately. Net bpp is N divided by the total image pixel count.

## 7. Owner reservation and encryption

1. Run the fixed CNN on the original image X at all step-2 candidate centers. Build the label directory, compress it, calculate L, H, T, B, and N. Reject if N<=0.
2. Save the original H bootstrap candidate bytes as B bits in byte order, most-significant bit first.
3. In the ordinary candidate slots T, write the backup bits followed by N zero bits. Set all H bootstrap candidate bytes to zero. This produces the reserved plaintext R with no user payload.
4. Encrypt all of R using AES-256-CTR under K_img.
5. Encrypt the packed/compressed label directory using K_directory. Install the encrypted bootstrap header (P=0), encrypted directory, and HMAC tag in the first H candidate bytes.
6. Deliver the reserved encrypted image and Kh to the authorized hider. No label/prediction sidecar is created or transmitted.

## 8. Encrypted-domain data hider

The hider derives K_header_bootstrap, K_header_final, K_directory, K_payload, and K_auth from its single Kh.

1. Decrypt the fixed-size bootstrap header using K_header_bootstrap, validate framing bounds, and verify the packet HMAC.
2. Decrypt and decompress the label directory, validate its exact expected length, class IDs and padding, and reconstruct T, B, U, and N.
3. Check that the supplied payload is a one-dimensional binary sequence with P<=N.
4. Form payload || zero padding to exactly N bits. Pack with zero low-byte padding, encrypt the packed bytes under K_payload, and use the first N ciphertext bits.
5. Replace only the ciphertext positions U with those encrypted payload bits. The hider does not decrypt the image or insert the payload into a pre-encryption plaintext image.
6. Encrypt the updated header containing P using K_header_final and recompute the HMAC. The directory and bootstrap backup prefix remain unchanged.

The hider needs no original image, image-encryption key, CNN, plaintext prediction map, or externally provided per-image capacity map. It does receive Kh as a cryptographic capability; this is not receiver-side metadata and is not a map.

## 9. Receiver: only marked image, K, and V

The receiver takes exactly the final marked encrypted image, K, and V as per-image semantic inputs. The decoder and frozen checkpoint are installed software.

1. Derive K_img and Kh from K,V; derive K_header_final, K_directory, K_payload, and K_auth.
2. Decrypt the fixed-size final header. Validate its bounds, verify the HMAC, decrypt/decompress the directory, and validate its length, labels, and padding before running the CNN.
3. Reconstruct T, B, U, N. Read the N encrypted payload bits from U, decrypt them under K_payload, require zero padding after P, and return exactly the first P bits. This supports P=0 and non-byte-aligned payloads.
4. Generate the AES-CTR image keystream Z under K_img. Restore U ciphertext bits and the H bootstrap ciphertext bytes to the corresponding keystream bits/bytes. These locations were zero in R, so their ciphertext can be recomputed exactly.
5. Decrypt the restored ciphertext to R. Read B bootstrap-backup bits. Recompute predictions from the invariant masked contexts. For each ordinary candidate with n_i>0, find the unique c in [0,255] satisfying:

       c mod 2^(8-n_i) = R_i mod 2^(8-n_i)
       lo_i <= |c-p_i| <= hi_i

   Fail closed unless exactly one candidate value satisfies the conditions. Candidates with n_i=0 remain unchanged. Restore all H original bootstrap bytes from the backup. Noncandidate pixels were never modified.

The receiver process must not open source images, payload files, capability-key files, prediction maps, label maps, directories, or any sender-side artifact. Its only data-file input is the marked encrypted image; its other per-image semantic inputs are K and V. The installed CNN checkpoint and decoder are shared software.

## 10. Security and research limits

- EDR2 is a research protocol, not a certified or independently audited cryptosystem.
- AES-CTR is used with independent HKDF-derived domain keys and unique nonce-bound keys. HMAC authenticates the packet against outsiders; the authorized hider is trusted.
- The encrypted header and directory conceal their contents. Image dimensions, outer image/container size, and the fact that a packet exists remain observable.
- The frozen checkpoint's original training provenance must be supported by a training manifest before detailed training claims are made. Current EDR2 tests use the existing v4_patch3 checkpoint; the repaired training script is a separate reproducibility path.
- Exact cross-platform floating-point prediction identity has not yet been established.
- Positive net capacity is image-dependent. The method rejects N<=0; no universal positive-capacity claim is made.
- EDR2 uses different magic and key derivation from EDR1. Never mix EDR1 and EDR2 packets, tables, or experiment results.
