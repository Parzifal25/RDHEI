# Phase B1 — Benchmark dataset inventory

- Gray dir: `/home/parzifal/RDHEI_Project/data/kodak_gray`
- RGB dir: `/home/parzifal/RDHEI_Project/data/kodak_color`
- Train dir: `/home/parzifal/RDHEI_Project/data/train` (count only, see below)

| File | Set | Mode | WxH | Channels | Range | Inter-ch max diff | Genuine RGB | In RGB agg | SHA256 (first 16) |
|---|---|---|---|---|---|---|---|---|---|
| Airplane.png | GRAY | L | 512x512 | 1 | 16..231 | 0 | False | n/a (gray set) | `7f8b1f59666ca174` |
| Baboon.png | GRAY | L | 512x512 | 1 | 16..214 | 0 | False | n/a (gray set) | `011facaeced92069` |
| Goldhill.png | GRAY | L | 720x576 | 1 | 16..235 | 0 | False | n/a (gray set) | `bb30071d1326e30a` |
| Jetplane.png | GRAY | L | 1024x1024 | 1 | 4..192 | 0 | False | n/a (gray set) | `5387655110fe834b` |
| Lena.png | GRAY | L | 512x512 | 1 | 25..245 | 0 | False | n/a (gray set) | `5ca92b8fbb3f446a` |
| Peppers.png | GRAY | L | 512x512 | 1 | 0..227 | 0 | False | n/a (gray set) | `e554728dd6b60a0c` |
| 4.2.03.png | RGB | RGB | 512x512 | 3 | 0..255 | 251 | True | True | `95968aa6b8262955` |
| 4.2.05.png | RGB | RGB | 512x512 | 3 | 0..234 | 226 | True | True | `45680d4e72298b12` |
| 4.2.06.png | RGB | RGB | 512x512 | 3 | 0..249 | 224 | True | True | `4d51b4ba7747828b` |
| 4.2.07.png | RGB | RGB | 512x512 | 3 | 0..237 | 227 | True | True | `a370df5e3d7bcd0c` |
| images.png | RGB | L | 225x225 | 1 | 0..223 | 0 | False | False | `a3e5fec1ec58382c` |
| lena.png | RGB | RGB | 512x512 | 3 | 3..255 | 235 | True | True | `7e497501a28bcf9a` |

- Valid grayscale benchmark images: **6**
- Genuine 3-channel RGB benchmark images: **5**
- RGB-directory files excluded (not genuine RGB): **1**
- Training directory `/home/parzifal/RDHEI_Project/data/train`: **200** .pgm files present on disk

Training-set note: the confirmed training description (BOSSBase, 10,000 training
images, 20 epochs, trained on another computer) is user-confirmed experimental
information; the local folder does not independently verify it.
