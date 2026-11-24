# JISA submission-readiness and risk note

## Journal fit
JISA explicitly covers multimedia security and practice-driven security applications. It also states that formal-only work without implementation/empirical testing, and routine applications of existing AI/ML models without a substantive security contribution, are not considered. The EDR2 manuscript therefore leads with an implemented receiver/recovery contract and a concrete predictor-input non-interference property rather than a generic CNN application.

## Major editorial risk
The measured EDR2 pooled usable rate is 0.09550 bpp. The two same-corpus native-protocol reproductions are 1.97350 and 2.11817 bpp pooled. Recent JISA papers also report native rates around 2.35–3.88 bpp on BOSSBase/BOWS-2. These numbers are not directly comparable because datasets, encryption order, carrier construction, auxiliary data and rate definitions differ, but the magnitude gap is substantial. EDR2 must not claim high capacity or superiority. A reviewer may still conclude that the narrow geometric synchronization property is insufficient originality for JISA.

## Required author actions before submission
1. Supply the frozen checkpoint training manifest and prove the training/evaluation separation.
2. Perform a full-text comparison against the nearest JISA work on bit-plane label-map encoding and the recent adaptive block-level pixel-difference method.
3. Get an independent cryptographic review or explicitly retain a conservative engineering-security scope.
4. Archive the raw per-image ledgers, code commits and artifacts in a persistent repository with a DOI.
5. Confirm figure rights and author/funding declarations.
6. Have a subject expert check the mathematical statement, data-hiding inverse, capacity accounting and exact protocol code line by line.

## Format note
The source uses Elsevier's elsarticle class in a single-column preprint layout with numbered references. Elsevier's general “Your Paper Your Way” guidance does not impose a formal layout or length at initial submission, so this is an editable JISA-oriented first-submission format, not a claim to reproduce a journal-specific proprietary template. The manuscript uses a concise abstract, up to six keywords, separate highlights and editable tables.
