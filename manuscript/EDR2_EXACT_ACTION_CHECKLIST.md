# EDR2 manuscript completion checklist — refreshed 23 November 2026

This checklist reflects evidence already present. Checked items should not be re-run without a reason.

## A. Verified and completed

- [x] EDR2 protocol source identified separately from EDR1.
- [x] Four step-2 lattice phases and centre-masked 3×3 predictor specified.
- [x] Radius-one non-interference proposition written with assumptions.
- [x] Four-phase signed net-capacity rule and bootstrap costs expressed algebraically.
- [x] EDR2 HKDF key domains, AES-256-CTR, HMAC-SHA256 and authenticate-before-decompress flow documented.
- [x] 243-image native grayscale capacity ledger recomputed.
- [x] Dataset curation corrected to 232 natural + 11 constructed.
- [x] 978/978 accepted-image image-and-payload recovery trials confirmed.
- [x] Exhaustive label mapping checks (65,536 pairs and 396,032 payload words) documented.
- [x] Predictor-only common-grid comparison separated from native EDR2.
- [x] External baselines pinned and matched by source/pixel corpus hashes.
- [x] PPMR four compatibility changes disclosed.
- [x] Corrected 243-row baseline merge validation checked.
- [x] Parser fuzz campaign and limitations documented.
- [x] Optimized vectorized patch extraction and Run #118 E2E timing incorporated.
- [x] 2021–2026 related work expanded and DOI bibliography prepared.
- [x] Full paper draft, technical audit, checklist and BibTeX placed on a non-main branch.

## B. Must complete before submission

- [ ] Attach the final training manifest for checkpoint `a9021862c753e11b0100fb11eba0d3b55800915654ed962fcdede8449b159d5d`: training image inventory and hashes, image-level split, seed, preprocessing, loss, optimizer, schedule/epochs, validation metric and checkpoint-selection record.
- [ ] Add immutable implementation commit links and artifact IDs/hashes to the supplementary material or data-availability section.
- [ ] Verify figure/image redistribution rights. Prefer newly drawn lattice/protocol schematics where rights are uncertain.
- [ ] Run a final DOI/title/author/volume/issue/article-number/retraction check for every bibliography entry. Scite verification remains unavailable on the connected free/inactive plan; use publisher/Crossref manual checks or enable Scite access.
- [ ] Re-run Academic Writing Toolkit citation consistency, paragraph logic and British-English checks after reference numbering is final.
- [ ] Generate final tables and plots directly from committed CSV/JSON artifacts and verify every plotted value.
- [ ] Insert author names, affiliations, corresponding email, funding statement, acknowledgements and conflict-of-interest declaration.
- [ ] Select a journal only after checking its current scope, indexing/coverage years, article type, APCs/fees, page limits and review process.
- [ ] Apply target-journal formatting and produce a submission PDF plus source bundle.
- [ ] Have the supervisor/co-author review the final novelty statement, equations, protocol and all quantitative claims.

## C. Do not do

- [ ] Do not retrain or fine-tune the model.
- [ ] Do not chase a larger bpp by tuning against this test corpus.
- [ ] Do not merge results from the separate EDR1 protocol.
- [ ] Do not compare native-protocol baseline bpp as if packet costs and security guarantees were identical.
- [ ] Do not state that 3×3 is the best predictor; the 5×5 no-weighted-loss ablation performed better in the matched-grid experiment.
- [ ] Do not claim formal security, external cryptographic certification, malicious-hider resistance or multi-resolution scalability.
- [ ] Do not call the method state of the art or superior in capacity.

## D. Acceptance test

The paper is ready for submission only after every B item is resolved, all numeric claims trace to a fixed raw artifact, all protocol statements match the EDR2 implementation, all citations support the corresponding sentence, and the final PDF has been checked page by page.
