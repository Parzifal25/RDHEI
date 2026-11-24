# JISA submission-readiness and editorial-risk note

## Journal fit

Elsevier describes JISA as a journal for original research and practice-driven applications relevant to information security. Its listed topics explicitly include multimedia security and forensics, making reversible data hiding in encrypted images within the journal's stated subject area. The journal also states that cryptographic protection should be evaluated in real system/application context rather than relying solely on pure mathematical proofs without demonstrated practical relevance. EDR2 includes an implemented owner–hider–receiver protocol, packet authentication, exact-recovery tests and a 243-image experiment, but the importance and originality of its synchronization contribution remain editorial judgements.

Official journal information: https://shop.elsevier.com/journals/journal-of-information-security-and-applications/2214-2126

## Main editorial risk

The measured EDR2 pooled usable rate is 0.09550 bpp. The same-corpus native-protocol reproductions are 1.97350 and 2.11817 bpp pooled. Recent JISA RDHEI papers report substantially higher native rates, including 3.8770/3.9036 bpp on BOSSBase and 3.7944/3.8431 bpp on BOWS-2 for the DBS/AEBS variants of Ankur et al., 3.76/3.37 bpp for Huang et al., and 2.4938/2.3508 bpp for Ren et al.'s ABPDE method. These rates are not a controlled like-for-like comparison with EDR2 because of different datasets, encryption order, carrier construction, auxiliary costs and native rate definitions. Nevertheless, the magnitude of the gap is material and must remain prominent.

The paper therefore makes no high-capacity, state-of-the-art or superiority claim. A JISA reviewer may still conclude that a narrow geometric synchronization condition and one implementation, despite exact-recovery evidence, do not constitute sufficient novelty or practical payload value compared with recent methods. This is a genuine acceptance risk, not a wording issue.

## Pre-submission blockers

1. **Checkpoint training provenance:** supply the frozen checkpoint's training image inventory and hashes, image-level split, random seed, preprocessing, loss, optimizer, schedule/epochs, validation results and checkpoint-selection record. Until then, training/test leakage cannot be independently excluded.
2. **Closest-work comparison:** read the full texts of the nearest label-map/block-code, bidirectional-flag and adaptive block-level pixel-difference methods. Explain the difference in synchronization guarantee, protocol assumptions, and accounting in a concise technical comparison.
3. **Cryptographic review:** obtain an independent protocol/cryptographic review or retain the current conservative engineering-security scope. Do not imply formal security proof or malicious-hider protection.
4. **Persistent reproducibility release:** archive source, checkpoint metadata (not necessarily weights if licensing forbids), all per-image CSV/JSON ledgers, dataset manifests and test reports in a persistent repository with a DOI. GitHub Actions artifacts alone are not archival.
5. **Figure/image rights:** use original vector schematics or verify rights for any USC-SIPI examples shown in a paper figure. Current submission figures are vector diagrams/charts rather than copyrighted source images.
6. **Author declarations:** supply names, affiliations, corresponding-author contact, CRediT contributions, funding, acknowledgements and competing-interest declaration.
7. **Final reference audit:** independently verify every author list, title, year, volume/article number and DOI against publisher records; the connected Scite MCP plan is inactive, so Scite's citation-context/retraction audit has not been run.
8. **AI-use declaration:** confirm the ChatGPT assistance statement is accurate and that all authors have reviewed and edited the material, verified claims/references and accept full responsibility. Elsevier requires such a declaration for generative-AI use in manuscript preparation.\n9. **Final supervisor review:** have a subject expert audit the mathematical statement, code-to-paper protocol mapping, inverse mapping, net-capacity accounting, results and nearest prior art.

## Format and build status

The manuscript uses Elsevier's `elsarticle` class in an A4 single-column initial-submission layout, numerical references and editable LaTeX tables/figures. Highlights are supplied separately; the abstract is 240 words and the keyword list has six items. The graphical abstract is a standalone vector source. The GitHub Actions workflow validates citation keys and highlight lengths, compiles the manuscript with BibTeX, compiles the graphical abstract and packages the PDFs and source files.

This is a JISA-oriented first-submission source package, not a claim that an editor has approved its format or that the manuscript is ready to submit.
