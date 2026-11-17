# External full-system RDHEI baselines

This directory contains independent adapters and evaluation infrastructure. It does not vendor third-party MATLAB source.

1. Multi-MSB Prediction and Huffman Coding — Yin, Xiang & Zhang, IEEE Transactions on Multimedia, 22(4), 874–884 (2020), DOI 10.1109/TMM.2019.2936314. Repository edu-yinzhaoxia/Reversible-Data-Hiding-in-Encrypted-Images-Based-on-multi-MSB-Prediction-and-Huffman-Coding, pinned commit 1e69ae2713dededa56595ff09255cda1e17896d9.
2. Pixel Prediction and Multi-MSB Planes Rearrangement (PPMR) — Yin et al., Signal Processing 187 (2021), 108146, DOI 10.1016/j.sigpro.2021.108146. Repository edu-yinzhaoxia/RDH-EI-based-on-pixel-prediction-and-multi-MSB-planes-rearrangement, pinned commit 21f397890289049798ced0f98d1482d629f93b06.

Original upstream .m functions are checked out at pinned commits and not edited. Runs use GNU Octave on Linux rather than MATLAB; equivalence of their rand('seed',...) streams is not claimed. The exact 243-image corpus.json is downloaded from completed EDR2 native run 43579225461 / artifact edr2-full-natural-corpus-evidence, then verified by path, source-file SHA-256, decoded uint8 pixel SHA-256 and dimension. A 6-image smoke test is a hard gate for both methods.

Both methods receive deterministic 8*W*H binary payload requests. Baseline 1 passes length(emD), the actual payload count returned by upstream Embed_Data, to upstream extraction/recovery rather than the overlong request used by the demo driver. This is an adapter-level correction; upstream algorithm functions are unchanged. PPMR preserves the original Main612.m rate expression: (num_emubD + num_NUBD - length(compress_predict) - 8 - 16*8 - 16*8)/(row*col).

The public upstream repositories show no visible LICENSE/SPDX metadata at the pinned commits. They are temporary checkouts and are not redistributed. No EDR2 model, checkpoint or existing result is modified. Results and full logs are uploaded as the external-rdhei-baseline-results workflow artifact.
