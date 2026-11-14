# EDR2 protocol specification

**Status:** research-branch protocol specification. EDR2 changes the EDR1 key hierarchy and packet magic; it is a distinct wire-protocol version. EDR1 packets and EDR2 packets are not interchangeable.

## 1. Scope and RDHEI classification

EDR2 is a grayscale, reversible data hiding in encrypted images (RDHEI) construction using the reserve-room-before-encryption (RRBE) architecture:

1. The content owner reserves embedding room in the plaintext image and encrypts the reserved image.
2. A separate data hider inserts the user payload by modifying the encrypted image only. It does not receive the original image, the image-encryption key, or the CNN.
3. The receiver extracts the payload and reconstructs the original plaintext image without any external image-dependent side information.

The receiver's **only per-image semantic inputs** are:
- the final lossless marked encrypted image;
- the 32-byte master key K;
- the 128-bit nonce V.

The matching decoder, protocol constants and frozen CNN checkpoint are preinstalled shared software. They are not transmitted as per-image side information. The receiver does not accept or read a prediction map, label map, error map, location map, payload-length file, model selector, backup file, directory file, or sender state.

All per-image framing and recovery metadata required by the receiver is carried inside the marked image: the header, encrypted label directory, authentication tag, bootstrap backup bits, and payload. Thus EDR2 is **receiver-side external-side-information-free** (apart from K, V, and the fixed installed software). It is not a claim that the marked image contains no auxiliary bits; those bits are embedded in-band and are part of the stego image itself.

The independent hider receives one cryptographic data-hiding key Kh from the owner over an authenticated confidential key-delivery mechanism, together with the encrypted reserved image and user payload. Kh is keying material, not an image-dependent map or sidecar. The hider never receives K or the image-encryption key. This key handoff is between the owner and hider; it is **not** a receiver input.

**Scope boundary:** EDR2 makes the receiver sidecar-free; it does not claim that absolutely no information is exchanged between every pair of parties. In particular, the present independent-hider implementation transfers Kh to the hider for each nonce-bound packet. This is an additional cryptographic key handoff, not an auxiliary image map. Standard separable RDHEI schemes commonly distinguish image-encryption and data-hiding keys. A stricter “encrypted image only from owner to hider” design is a separate requirement and is not claimed by this EDR2 version. Do not call EDR2 “no additional information transmission between owner and hider.”

## 2. Parties and inputs

| Party | Inputs | Outputs / capability |
|---|---|---|
| Content owner | Original image X, master key K, unique nonce V, installed CNN | Reserved encrypted image; one derived data-hiding key Kh for the hider |
| Data hider | Reserved encrypted image, payload, Kh | Final marked encrypted image; can authenticate and parse in-band directory but cannot decrypt image content |
| Receiver | Final marked encrypted image, K, V, installed decoder/CNN | Exact original image X and exact payload |

The owner performs reservation and encryption before it receives or creates the user payload. The hider never receives the original image, prediction values, plaintext label map, capacity argument, or image-encryption key.

## 3. EDR2 key hierarchy

Let K be exactly 32 bytes and V be an unsigned 128-bit integer. Define:

    s = I2OSP(V, 16)
    K_root = HKDF-SHA256(K, salt=s, info="EDR2/master-root", length=32)
    K_img  = HKDF-SHA256(K_root, salt=empty, info="EDR2/image-encryption", length=32)
    Kh     = HKDF-SHA256(K_root, salt=empty, info="EDR2/data-hiding-master", length=32)

The owner delivers only Kh to the authorized hider. From Kh, both hider and receiver derive three internally separated keys:

    Kd = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/directory", length=32)
    Kp = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/payload", length=32)
    Ka = HKDF-SHA256(Kh, salt=empty, info="EDR2/hider/auth", length=32)

From Kh, both owner/hider and receiver derive five 32-byte subkeys using independent HKDF-SHA256 info strings:

    K_header_bootstrap = HKDF-SHA256(Kh, info="EDR2/hider/header-bootstrap")
    K_header_final     = HKDF-SHA256(Kh, info="EDR2/hider/header-final")
    Kd                 = HKDF-SHA256(Kh, info="EDR2/hider/directory")
    Kp                 = HKDF-SHA256(Kh, info="EDR2/hider/payload")
    Ka                 = HKDF-SHA256(Kh, info="EDR2/hider/auth")

The distinct HKDF info strings provide cryptographic domain separation. Possession of Kh does not provide K_root or K_img, so the hider cannot derive the image-encryption key from its capability. The two header-stage keys are distinct because reusing one CTR key for the reservation header and final header would expose the XOR of the two header plaintexts to an observer who obtains both packet states.

AES-256-CTR starts at counter zero independently under each derived key. A nonce V must never be reused with the same master key K for another packet, including an empty-payload packet. Each reservation packet is single-use. Nonce reuse would repeat derived keys and CTR keystreams and is prohibited.

## 4. Shared predictor and candidate grid

The protocol scope is a same-size, two-dimensional, 8-bit grayscale image (uint8, mode L). The frozen CNN-3x3 checkpoint, preprocessing, CPU inference, rounding and class mapping are fixed protocol parameters. The owner and receiver must use the same checkpoint and numerically compatible runtime.

Candidate centers are row-major:

    y,x in range(2, dimension-2, 3)

Only candidate-center bytes are mutable. With the masked 3x3 predictor input, no other candidate center lies in a candidate's context. Therefore the context used for each prediction is invariant under changes to other candidate centers, including bootstrap carriers.

The existing allocation function maps each absolute integer prediction error to (n,lo,hi), where n is the number of replaced MSBs and [lo,hi] is the admissible error interval used for unique recovery. The 15 distinct tuples are lexicographically sorted into the fixed codebook. A four-bit class index is stored per candidate, two labels per byte, high nibble first; an odd final low nibble is zero. The packed directory is compressed with zlib level 9 only when the compressed result is strictly shorter.

## 5. In-band packet format

The first 20 candidate bytes contain a fixed-width header with the big-endian structure >4sB3xIQ. **The 20 header bytes are encrypted in-band**, not transmitted as plaintext:

| Field | Size | Meaning |
|---|---:|---|
| Magic | 4 bytes | EDR2 |
| Codec | 1 byte | 0 raw packed labels, 1 zlib-compressed labels |
| Reserved | 3 bytes | Must be zero |
| Directory length L | 4 bytes | Encrypted directory length in bytes |
| Payload length P | 8 bytes | User payload length in bits |

The header is encrypted using AES-256-CTR with the stage-specific HKDF-derived header key. The owner uses K_header_bootstrap for its reservation packet. The hider authenticates and decrypts the bootstrap header, then writes the completed header using K_header_final. The receiver derives K_header_final from K and V. Separate header keys prevent an observer who sees both packet states from cancelling a reused CTR keystream and recovering the XOR of the two header plaintexts.

The next L candidate bytes contain the encrypted packed label directory. The next 32 candidate bytes contain the HMAC-SHA256 authentication tag. The bootstrap length is therefore:

    H = 52 + L

The receiver knows the fixed header carrier coordinates from the installed protocol. It decrypts the fixed-size header using the final-header key, validates L against the candidate count, locates the directory and tag, and authenticates the packet before directory decompression or CNN inference. Directory length and payload length are not exposed in plaintext in the image header.

The tag covers the big-endian uint64 image dimensions followed by the full row-major marked-image bytes with the tag carrier bytes set to zero. This detects unauthorized packet modification. An authorized hider holding Ka can generate a valid tag; the design therefore trusts the authorized hider and does not claim malicious-hider security.

## 6. Capacity and bootstrap accounting

Let C be the number of candidate centers. For candidate i, let ni be its number of available MSB slots. The gross ordinary-slot count is:

    G0 = sum(ni for i=0,...,C-1)

The bootstrap consumes the first H candidate centers. Let:

    F = sum(ni for i=0,...,H-1)
    S = G0 - F

Enumerate the ordinary slots of candidates H,...,C-1, in candidate order and bit order 7 down through 8-ni, as T. Let B=8H be the number of bits required to preserve the original H bootstrap bytes. Split:

    T = T_backup || U
    |T_backup| = B
    N = |U| = S - B

Reject the image before packet creation when N<=0. The signed net capacity is:

    N = G0 - F - 8H

The metadata has 8H physical in-band storage bits (header + encrypted directory + tag); its opportunity cost in the ordinary-slot budget is F, because those H bootstrap centers no longer contribute their ordinary candidate slots. The separate backup prefix costs B=8H ordinary slots. Hence the correct ordinary-slot accounting is N=G0-F-B. Do not subtract the physical metadata bytes a second time from G0; that would double-count the bootstrap.

## 7. Owner reservation and encryption

1. Predict X, generate the class labels and compressed directory, compute H, T, B, and N. Reject if N<=0.
2. Save the original H bootstrap bytes as B bits, byte order then most-significant bit first.
3. For every ordinary candidate, preserve its low 8-ni bits and replace its ni MSBs with the stream bootstrap backup || N zero bits. Set all H bootstrap bytes to zero. This forms the reserved plaintext R, with no user payload yet.
4. Encrypt all of R with AES-256-CTR under K_img.
5. Encrypt the packed/compressed label directory with AES-256-CTR under Kd. Install the EDR2 header with P=0, the encrypted directory and the HMAC tag in the first H bootstrap candidate bytes.
6. Deliver the reserved encrypted image and Kh to the authorized data hider through the system's authenticated confidential key-delivery mechanism. No prediction or label sidecar is delivered.

## 8. Encrypted-domain data hider

The hider derives Kd,Kp,Ka and the bootstrap/final header keys from its single Kh, then:

1. Verifies the HMAC, parses the bounded header, decrypts the directory, validates the directory length/classes/padding, and reconstructs T,B,N.
2. Checks that the payload is a one-dimensional binary sequence and 0<=P<=N.
3. Forms payload || zero padding of exactly N bits, packs it with zero low-byte padding, encrypts the packed bytes under Kp, and takes the first N ciphertext bits.
4. Replaces only the ciphertext positions U with these encrypted payload bits. The hider does not decrypt the image and does not insert payload into the pre-encryption plaintext image.
5. Encrypts the updated header containing P using K_header_final and recomputes the HMAC. The directory and backup prefix remain unchanged.

The hider needs no CNN, original image, image-encryption key, original prediction map or external per-image capacity map.

## 9. Receiver: only marked image, K and V

The receiver takes exactly the final marked encrypted image, K, and V as per-image semantic inputs.

1. Derives K_img and Kh from K,V, then K_header_final, Kd,Kp,Ka.
2. Decrypts the fixed-size header, checks its bounds, and authenticates the marked image before decompressing the directory or running the CNN. It validates the decoded directory length, labels, padding and payload length.
3. Reads the encrypted payload bits from U, decrypts them under Kp, checks that all bits after P are zero padding, and returns exactly the first P bits. This includes P=0 and non-byte-aligned payload lengths.
4. Generates the image keystream Z under K_img. Replaces U ciphertext bits with the corresponding keystream bits and restores the H bootstrap ciphertext bytes to Z. These positions were zero in the reserved plaintext R, so their ciphertext is exactly recomputable.
5. Decrypts to the exact reserved plaintext R, reads the B backup bits, recomputes predictions from invariant contexts, and restores each ordinary candidate's original value as the unique c in [0,255] satisfying:

       c mod 2^(8-ni) = Ri mod 2^(8-ni)
       lo_i <= |c-p_i| <= hi_i

   Candidates with ni=0 remain unchanged. It restores every bootstrap byte from the backup bits. Noncandidate pixels were never modified.

The receiver must not access source images, payload files, capability-key files, maps, or sender-process memory. CLI output paths and audit destinations are not semantic decoding inputs.

## 10. Security and scope limits

- EDR2 is an RDHEI/RRBE protocol design, not a certified or independently audited cryptosystem.
- The data hider is authorized to read the label directory and holds the data-hiding/authentication capability derived from Kh. A malicious authorized hider can alter the packet and recompute its tag; this threat is outside the current model.
- The header fields, directory length and payload bit length are encrypted in-band. The image dimensions and total outer file size remain observable; image-level traffic analysis and length leakage through the PNG/container size are not claimed to be eliminated.
- The fixed CNN checkpoint and arithmetic environment are shared protocol software; cross-runtime floating-point equivalence has not been established.
- Positive net capacity is image-dependent. The algorithm rejects N<=0. No universal positive-capacity claim is made.
- EDR2 uses a different magic and key hierarchy from EDR1. Never decode an EDR1 packet as EDR2 or mix EDR1 results with EDR2 measurements.
