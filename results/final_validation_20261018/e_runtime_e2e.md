# Phase E — end-to-end pipeline runtime

- Started (UTC): 2026-10-18T18:29:30.835635+00:00
- Scope: FULL PIPELINE = prediction + label maps + MSB embedding + AES-CTR
  encryption + decryption + extraction + recovery.
- Repeats: 3 per (image, method); values are arithmetic means over repeats.
- CNN = v4_patch3 (proposed). Grayscale payload = full capacity; RGB = full
  capacity on each of the 3 channels with unique per-channel nonces.

| Image | Method | Capacity (bits) | Prepare ms | Embed+Encrypt ms | Decrypt+Extract+Recover ms | Total ms | Std ms |
|---|---|---:|---:|---:|---:|---:|---:|
| gray Airplane 512x512 | med | 1,431,289 | 48.2 | 1322.3 | 3692.6 | 5063.1 | 203.7 |
| gray Airplane 512x512 | cnn | 1,507,378 | 1705.5 | 1280.3 | 4053.8 | 7039.6 | 276.5 |
| rgb 4.2.03 512x512x3 (3 ch) | med | 3,094,742 | 102.7 | 3039.5 | 5152.7 | 8295.0 | 419.2 |
| rgb 4.2.03 512x512x3 (3 ch) | cnn | 3,319,470 | 6798.3 | 3462.3 | 5992.0 | 16252.6 | 1978.9 |
