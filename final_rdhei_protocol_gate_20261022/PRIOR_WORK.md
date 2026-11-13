# Prior-work check (2026-10-22)

This is a targeted feasibility review, not a systematic review or a claim that
every recent method was reproduced. Sources below are primary papers, publisher
pages, author manuscripts or an author institution's publication record.

| Work | Relevant established technique | Implication for this gate |
| --- | --- | --- |
| Ma et al., IEEE TIFS 2013, DOI 10.1109/TIFS.2013.2248725 | Reserve room in the original image before encryption, then let the data hider embed into the encrypted image. | Reservation in plaintext is compatible with RDHEI when actual user insertion happens after encryption; the reservation architecture is established. |
| Yin, Xiang and Zhang, IEEE TMM 22(4), 874–884, 2020, DOI 10.1109/TMM.2019.2936314 | Adaptive multi-MSB prediction, Huffman marking, stream encryption, then substitution into vacated room. | Neither variable MSB allocation nor coding its auxiliary labels is new. |
| Mohammadi, “A general framework for reversible data hiding in encrypted images by reserving room before encryption,” arXiv:2103.15240v3, 2021; journal reference 2022 | Predictor-based errors, blocking, labeling, and room reservation; discusses compression as an optional capacity aid. | A frozen predictor within a reservation framework does not establish architectural novelty. |
| “Reversible data hiding in encrypted images with multi-prediction and adaptive huffman encoding,” Scientific Reports 13:23104, 29 December 2023, DOI 10.1038/s41598-023-50186-1 | MED+GAP predictions, compressed labels embedded in the encrypted image, labels read by data hider, adaptive multi-MSB replacement. | This directly precedes the claimed combination of compressed label maps, adaptive capacity and encrypted-domain insertion. |
| Yang et al., Communications of the CCISA 31(2), 17–31, May 2025 | Group prediction-error ranges receive Huffman labels; account for group identifiers, encrypt image, embed encrypted message into reserved encrypted room. | Error-adaptive group allocation and its metadata cost are already investigated. Publisher abstract reviewed; full text was not available through the displayed PDF link. |
| Martyniak and Dzwonkowski, ICCS 2025, DOI 10.1007/978-3-031-97635-3_13 | Blockwise predictor choice; Huffman/ERLE compression of errors; auxiliary stream includes reference pixels and model map; subsequent encrypted-domain payload insertion. | Source compression, predictor maps and reserving a contiguous payload region are existing alternatives. Its reported key-length-based location convention is not imported into EDR1. |
| Zhou et al., IET Image Processing 20(1), e70310, first published 24 February 2026, DOI 10.1049/ipr2.70310 | Prediction-error bit-plane classification, adaptive fixed/Huffman group coding, arithmetic compression of label/sign maps, explicit lengths and reserved room, then encrypted-domain embedding. | Even recent adaptive map and bit-plane coding is established; EDR1's simple zlib directory is not a new high-capacity compression contribution. |

Sources supporting each row:

- [Ma et al., author institution publication record and abstract](https://scholars.cityu.edu.hk/en/publications/reversible-data-hiding-in-encrypted-images-by-reserving-room-befo/).
- [Yin et al., IEEE Signal Processing Society article page](https://signalprocessingsociety.org/publications-resources/ieee-transactions-multimedia/2020/04/reversible-data-hiding-encrypted-images).
- [Mohammadi author preprint](https://arxiv.org/abs/2103.15240).
- [2023 Scientific Reports full paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10756882/).
- [2025 CCISA publisher abstract](https://cccisa.ccisa.org.tw/article/view/3194).
- [ICCS 2025 author camera-ready manuscript](https://www.iccs-meeting.org/archive/iccs2025/papers/159060097.pdf).
- [2026 IET publisher full paper](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.70310).

EDR1 is an engineering feasibility repair for this repository's frozen CNN, not
a demonstrated scientific advance over these papers. No numerical superiority,
novel compression, first use of learned prediction, or publishable novelty is
asserted. Their reported BPP figures are not compared with this restricted grid:
corpora, prediction dependencies, security assumptions and overhead conventions
differ. Improving compression and recovering dense dependencies would require a
separate investigation.
