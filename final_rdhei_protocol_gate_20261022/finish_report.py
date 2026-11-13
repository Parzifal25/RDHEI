"""Verify preservation, then render the final decision from recorded evidence."""
import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
D=BASE/'evidence'


def read(name):
    return json.loads((D/name).read_text())


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |',
                      '| '+' | '.join(['---']*len(headers))+' |',
                      *['| '+' | '.join(map(str,r))+' |' for r in rows]])


before=json.loads((BASE/'preservation_before.json').read_text())
changed=[]
for path,digest in before.items():
    p=ROOT/path
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
        changed.append(path)
preservation=dict(historical_files_checked=len(before),changed_or_missing=changed,
                  excluded=['.git internals','__pycache__','new dedicated investigation directory'])
with (BASE/'preservation_check.json').open('x') as f:
    json.dump(preservation,f,indent=2)
assert not changed,changed
environment=dict(python=sys.version,platform=platform.platform(),
                 packages={k:importlib.metadata.version(k) for k in ['torch','numpy','pycryptodome','Pillow']})
with (BASE/'environment.json').open('x') as f:
    json.dump(environment,f,indent=2)
caps=read('capacities.json'); rows=read('roundtrips.json'); algebra=read('algebra.json')
restoration=json.loads((BASE/'restoration_checks.json').read_text())
natural=[r for r in caps if r['image'].endswith('.png')]
accepted=[r for r in natural if r['accepted']]
assert all(r['image_exact'] and r['payload_exact'] for r in rows)
assert len(rows)==4*sum(r['accepted'] for r in caps)
assert len(accepted)>=3
budget_table=table(['Image','Pixels','C','G0 bits','Directory bytes L','H pixels','Lost F bits','S bits','Backup 8H bits','Signed net bits','Net BPP','Decision'],[
    [r['image'],r.get('pixels','—'),r.get('candidates','—'),r.get('gross_slots','—'),
     r.get('stored_label_bits',0)//8 if 'stored_label_bits' in r else '—',r.get('bootstrap_pixels','—'),
     r.get('foregone_gross_slots','—'),r.get('stream_bits','—'),r.get('backup_bits','—'),
     r.get('signed_net_bits','—'),f"{r.get('net_bpp',0):.6f}",'ACCEPT' if r['accepted'] else 'REJECT'] for r in caps])
cost_table=table(['Image','Raw packed label bits','Stored label bits','Fixed header bits','Tag bits','Total metadata bits','Physical gross bits'],[
    [r['image'],r['packed_label_bits'],r['stored_label_bits'],160,256,r['metadata_total_bits'],r['physical_gross_bits']]
    for r in caps if 'gross_slots' in r])
timing=[]
for r in caps:
    rs=[v for v in rows if v['image']==r['image']]
    if rs:
        timing.append([r['image'],f"{r['prepare_seconds']:.3f}",
                       *[f"{statistics.mean(v[k] for v in rs):.3f}" for k in
                         ['reserve_encrypt_seconds','embed_seconds','embed_process_seconds','receiver_seconds','receiver_process_seconds']]])
timing_table=table(['Image','Prepare incl. CNN','Reserve/encrypt','Embed','Embed process','Receiver incl. model import','Receiver process'],timing)
net_sum=sum(r['signed_net_bits'] for r in accepted)
report=f'''# Final RDHEI protocol gate

2026-10-22. **GO** for the specified EDR1 grayscale protocol on images passing its
explicit reversible-budget test. It performs actual payload insertion after image
encryption, preserves the trained CNN, and recovers without receiver sidecars.
**{len(accepted)}/{len(natural)} natural images have positive net payload** in the fixed local corpus;
their combined full payload is **{net_sum:,} bits**. All **{len(rows)}** accepted-image tests
(empty, short, partial and full net, including the synthetic constant control)
recover the original image and payload independently and exactly. No model was
trained, fine-tuned, or changed. This is an executable feasibility result, not
production integration or a universal positive-capacity guarantee.

## Parties, knowledge and receiver interface

The owner knows original X, 32-byte master encryption key K, and a unique 128-bit
nonce V. It reserves room and encrypts **without receiving any user payload**.
Only after that operation does the test driver create the payload. A separate
fresh-process data hider knows the reserved encrypted image, payload and three
per-packet capability keys: directory decryption, payload encryption and packet
authentication. It gets no original, image-decryption subkey, CNN, prediction,
allocation file or capacity argument. It reads capacity and locations from the
image. Capability distribution is a setup key-sharing requirement between owner
and hider; these keys contain no image-dependent map. They need not be transmitted
to the receiver.

The receiver gets only the final lossless grayscale PNG, K and V. Installed
protocol constants, decoder and checkpoint are shared software. Dimensions come
from the image. The decoder accepts no payload length, original image, labels,
predictions, or sender object. Its CLI also accepts output destinations, which
carry no decoding information. Each receiver is a new Python process. Its audited
reads of experiment artifacts contain exactly its ciphertext PNG; source-image
directory reads are explicitly prohibited. Outputs are compared against expected
arrays only after it exits. No PNG ancillary chunks carry hidden side information.

HKDF-SHA256 uses salt=V encoded in 16 big-endian bytes, info `EDR1/` followed by
`image`, `directory`, `payload` or `auth`, and emits distinct 32-byte keys. Each
AES-256-CTR domain starts at counter zero under its own derived key. Nonces must
be unique under K across packets; a reserved packet is single-use. The three
capability keys are already nonce-specific, so the hider need not process V.
The installed test key is public and serves reproducibility only.

## Allocation and bootstrap

The original dense scheme cannot simply run its CNN again on a decrypted marked
image: changed neighboring pixels change predictions. Its earlier mapless
allocation collisions remain unresolved. EDR1 reuses the existing 3×3 checkpoint
and per-pixel `(n,lo,hi)` rule on the prior prototype's isolated grid, with rows
and columns `range(2, dimension-2, 3)`. Only these centers ever change. Their
masked patches contain no other mutable center, so original and reconstructed
CNN inputs, predictions and rounded values agree. This deliberately sacrifices
dense coverage; it preserves the checkpoint and allocation rule, not the old
dense capacity figures. At 512×512 there are 28,900 candidates, or 11.0245% of pixels.

The fixed 15-class codebook is the sorted set of the existing mapping's tuples
for absolute errors 0…255. Four-bit labels identify both n and its error interval;
n alone does not identify that interval. Pack high nibble first, pad an odd final
nibble with zero, and choose zlib9 only if strictly shorter than raw packed bytes.
One label per candidate, including bootstrap candidates, avoids a circular
directory-length calculation. The shared inference settings are CPU, eval mode,
gradients disabled, four threads, float32 normalization by 255, center masking,
2048-patch batches and nearest-even rounding. Cross-platform inference identity
is not established by this same-host gate.

At the first candidate centers store a 20-byte big-endian `>4sB3xIQ` header:
magic `EDR1`, codec byte, three zero bytes, uint32 directory length L, uint64 user
bit length P. Next come L encrypted directory bytes and a 32-byte HMAC-SHA256 tag.
Thus H=52+L candidate pixels carry the bootstrap. Header positions are fixed;
their first 20 bytes reveal H, independently of any CNN or label. Verify bounded
framing and HMAC before directory decompression or model loading. Raw decoded
directory length must equal ceil(C/2), with valid class IDs and padding. Metadata
encryption has no expansion. Header length/codec/P are public; directory plaintext
is available to the authorized hider, not to outsiders without its capability.

## Mathematical sender, embedding and decoding protocol

Let T enumerate ordinary MSB slots of candidates H…C−1 in candidate order,
bit 7 down through 8−n. Let S=|T|, B=8H, N=S−B. Reject N≤0 before output.
T[:B] backs up the original H bootstrap bytes, MSB first; U=T[B:] is exclusively
payload room. A split within a pixel is allowed and preserves the other bits.

1. **Owner reservation:** Keep every ordinary pixel's low 8−n bits, and replace
   its n high bits with the stream `bootstrap originals || N zeros`. Set all H
   bootstrap bytes to zero, creating reserved image R. Encrypt R with the image
   subkey. Replace bootstrap ciphertext bytes by header(P=0), independently
   encrypted directory and tag. This is a reservation packet; even an empty final
   payload must pass through the hider operation.
2. **Encrypted-domain hider:** Authenticate, decrypt directory, derive T,B,N,
   and enforce 0≤P≤N. Form `payload || zero padding` of exactly N bits, pack
   with zero low-byte padding, encrypt ceil(N/8) bytes with the payload subkey,
   and directly replace U ciphertext positions with the first N encrypted bits.
   Update P and HMAC. The hider never decrypts image content or inserts user bits
   into a pre-encryption plaintext image. The backup prefix stays untouched.
3. **Receiver payload extraction:** Authenticate, decode directory and validate
   P against N. Read U ciphertext bits, pack/decrypt with the payload subkey,
   take the first N plaintext bits, require padding after P to be zero, and
   return exactly the first P bits. This handles P=0 and nonbyte lengths; ignored
   low-byte packing bits have no user meaning. N is derived from in-image labels.
4. **Receiver restoration of reservation ciphertext:** Generate image keystream
   Z. Replace U ciphertext positions with their Z bits and H bootstrap ciphertext
   bytes with their Z bytes. These locations were all zero in R. The result is
   exactly the owner's encrypted R; decrypt it. Extract B backup bits from T[:B].
5. **Receiver image recovery:** Recompute predictions from invariant contexts.
   For each ordinary candidate with n>0, define s=2^(8−n), retained residue
   r=R_i mod s and prediction p. Restore the unique c in 0…255 satisfying
   c mod s=r and lo≤|c−p|≤hi. Leave n=0 candidates unchanged. Finally restore
   all H bootstrap bytes from the B backup bits. Noncandidates are untouched.

This is an RRBE encrypted-domain protocol, not encryption after payload insertion.
CTR alone does not restore arbitrary overwritten ciphertext. It works here
because overwritten R bits were deliberately known zeros, and their ciphertext
can be recomputed. Original ordinary MSBs are recovered from residue/prediction/
class, while **every original bootstrap byte is explicitly backed up**. Original
ciphertext of X itself need not be backed up: X is reversibly reconstructed from R.

The class-conditioned local decoder was checked for all {algebra['pairs']:,} x,p
pairs, covering all {algebra['all_payload_words_covered']:,} payload words with zero failures.
For fixed x,p, every possible replaced high-bit word preserves the same residue,
so this exhaustive residue test covers all of them. Candidate prediction identity
was separately asserted after arbitrary overwriting of all candidate bytes on
every accepted image. Independent rechecks restored the exact reserved ciphertext
for all {len(rows)} final images and exercised {restoration['slot_split_checks']} slot splits.
In-image HMAC covers big-endian uint64 dimensions followed by all row-major image
bytes with the tag carriers zeroed. It detects outsider corruption; an authorized
hider holding its auth key is trusted. No malicious-hider or audited cryptosystem
claim is made.

## Complete capacity accounting and rejections

Let G0=sum(n over all candidates), F=sum(n over bootstrap candidates). Then
S=G0−F and **N=G0−F−8H**. Physical gross slots are S+8H, of which 8H hold
directory/framing/tag and 8H hold original-byte backups. Hence also
N=physical gross−metadata−backup. These are two consistent accounting bases;
subtracting metadata again from G0 would double count its bootstrap reservation.
Nonce and master K are the explicitly permitted out-of-band inputs; all map,
length and preservation costs are in-image. Installed codebook/model costs are
shared protocol software, not per-image sidecars.

{budget_table}

{cost_table}

Every fixed header costs 160 bits, including the 64-bit P field; tag costs 256
bits. Both are included in H and the equal-size original-byte backup. Raw odd
label streams include a four-bit pad. Payload CTR has zero transmitted expansion;
its at-most-seven discarded byte-packing bits are not stored. Empty/short/partial
messages leave N−P padded bits, not additional user data. Grayscale pixel-space
capacity is measured against all image pixels; PNG container overhead is not
embedding room. Rejected signed budgets are never counted as payload. tiny8 is
rejected before enough framing carriers exist; its capacity fields are undefined.

The corpus was fixed before measurements: all six existing local grayscale PNGs,
not a claim to be the 24-image Kodak benchmark, plus constant128, random256 and
tiny8 controls. No grid, codec or checkpoint was selected after inspecting these
outcomes. This is a modest classical-image feasibility set, not evidence of
general capacity or superiority on unseen datasets.

## Executed checks, runtime and evidence

Every accepted image ran empty, 37-bit short, floor(N/2) partial and N-bit full
payloads through a fresh hider and fresh receiver. All {len(rows)} image comparisons
and all {len(rows)} independent payload comparisons pass. There are no failed
round trips or discarded runs. Overlong payload, nonbinary input, corrupted image,
wrong receiver key, wrong nonce and wrong embedder authentication key are rejected.
An additional wrong payload capability test fails the padding check. Main test
nonces are distinct; no training or optimization operation occurs.

Times below are seconds, averaged across each image's four payload cases except
preparation, which is measured once. Receiver function timing includes lazy model
import/load; process timing adds interpreter/PIL/NumPy startup. Owner prepare
includes inference, labels and compression. Reserve/encrypt reuses that preparation.
The owner's model is preloaded; its one-time model load is not timed in these
columns. The fresh receiver columns include its own load.
These observations are feasibility timings, not controlled throughput benchmarks.

{timing_table}

Environment: Python {platform.python_version()}, Torch {environment['packages']['torch']},
NumPy {environment['packages']['numpy']}, PyCryptodome {environment['packages']['pycryptodome']},
Pillow {environment['packages']['Pillow']}; Linux/WSL2, CPU inference, four Torch threads.
Frozen checkpoint `models/v4_patch3.pth`, SHA-256
`a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`.
Its in-memory tensors remain bitwise unchanged. SHA-256 preservation check:
**{len(before)} pre-existing files checked; zero changed or missing**. Git internals
and bytecode caches were excluded from this content inventory. All new code,
reports and artifacts live in this dedicated directory. No manuscript was edited.

The authoritative decoding specification is [PROTOCOL.md](PROTOCOL.md), frozen
before implementation; its hash and source hashes are in
[protocol_identity.json](evidence/protocol_identity.json). Executable owner/receiver:
[protocol.py](protocol.py); independent hider: [wire.py](wire.py). Recorded budget,
round trips, negative checks, receiver read audits and model integrity are in
[evidence/](evidence/), with [exact ciphertext rechecks](restoration_checks.json)
and [preservation check](preservation_check.json). Cipher PNGs, payload arrays,
recovered arrays and logs are retained. No historical experiment is overwritten.

To reproduce into a **new** evidence directory, from the project root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 final_rdhei_protocol_gate_20261022/reproduce.py /tmp/edr1-fresh-evidence
```

Install the existing project's dependencies and keep its shared prototype/source
and checkpoint available. The driver requires the original corpus only to prepare
and compare tests; the receiver does not. Existing evidence directories are
refused rather than overwritten.

## Prior work and scope of the decision

Room reservation before encryption is established by
[Ma et al. (2013)](https://scholars.cityu.edu.hk/en/publications/reversible-data-hiding-in-encrypted-images-by-reserving-room-befo/).
Adaptive MSB allocation with coded auxiliary labels is established by
[Yin et al. (2020)](https://signalprocessingsociety.org/publications-resources/ieee-transactions-multimedia/2020/04/reversible-data-hiding-encrypted-images).
In-image compressed label maps read by the hider followed by adaptive encrypted
MSB insertion appear explicitly in the
[2023 multi-prediction/adaptive-Huffman paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10756882/).
Recent alternatives include
[prediction and group room reservation (2025)](https://cccisa.ccisa.org.tw/article/view/3194),
[predictor/error-map Huffman and ERLE compression (ICCS 2025)](https://www.iccs-meeting.org/archive/iccs2025/papers/159060097.pdf),
and [adaptive bit-plane/group coding with arithmetic-compressed labels (February 2026)](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.70310).
[PRIOR_WORK.md](PRIOR_WORK.md) records this targeted primary-source review and
its limits. Compression of labels, adaptive room allocation, and encrypted-domain
insertion are **not claimed as novel** here; no matched comparative benchmark
has been performed.

No non-negotiable constraint needs relaxation for this accepted-image protocol.
GO does not validate the old diagram, restore the dense scheme's advertised gross
BPP, cover RGB, ensure cross-platform floating-point identity, or guarantee space
on all images. Retaining every old dense location would require a new provably
decodable reconstruction schedule or further prediction metadata and budget work.
Guaranteeing positive payload for all unconstrained fixed-size images is impossible
by counting. EDR1 instead makes source-domain acceptance explicit, rejects deficient
budgets, and demonstrates positive net payload with complete receiver-only recovery.
'''
with (BASE/'FINAL_RDHEI_PROTOCOL_GATE.md').open('x') as f:
    f.write(report)
print('GO:',len(accepted),'/',len(natural),'natural images;',len(rows),'round trips;',net_sum,'natural-image net bits')
