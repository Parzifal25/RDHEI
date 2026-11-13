# Current protocol: EDR2

The active implementation in this directory is **EDR2**.

- Canonical EDR2 design: [PROTOCOL_EDR2.md](PROTOCOL_EDR2.md)
- Historical EDR1 design (not wire-compatible): [PROTOCOL_EDR1.md](PROTOCOL_EDR1.md)
- Historical EDR1 feasibility results: [FINAL_RDHEI_PROTOCOL_GATE.md](FINAL_RDHEI_PROTOCOL_GATE.md)

EDR2 packet magic is `EDR2`. Its receiver semantic inputs are exactly the final marked encrypted image, the master key (K), and the nonce (V), with the matching decoder and frozen CNN preinstalled as shared protocol software.

The EDR2 implementation uses a separate derived data-hiding key for the independent hider. That is keying material, not a per-image map or sidecar. The hider never receives the image-encryption key. The receiver does not receive that hider key; it derives the required subkeys from (K,V).

Do not combine EDR1 result tables with EDR2 measurements. EDR2 must be evaluated independently before any manuscript table is updated.
