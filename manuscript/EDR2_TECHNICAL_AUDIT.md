# Manuscript audit findings — 23 November 2026

## Stop-ship issues
1. Protocol histories in the repository differ. The 22 Oct protocol gate is explicitly named EDR1. It is a self-contained authenticated protocol; its 4/6 positive natural images, 72,357 bits, 20/20 recovery cases and HMAC tamper checks are not EDR2 results.
2. The 21 Nov EDR2-specific report says the historical 243-image numbers are provisional pending raw CSV/JSON verification.
3. That report says the EDR2 end-to-end runtime harness exists but had no execution outputs at the time of inspection.
4. It says the original EDR2 AES-CTR path has no authentication. AES-CTR alone cannot support tamper-detection or integrity claims.
5. It says the matched EDR2 storage/side-information baseline and multi-resolution scalability were not verified.

## Strong manuscript direction, conditional on code verification
The narrow potential contribution is the combination of (i) a deterministic geometric non-interference condition for a frozen masked local predictor, and (ii) an overhead-aware phase-choice rule that optimises signed net payload after the cost of recovery information and framing. These need a formal statement/proof and exact implementation trace. CNN use, bit-plane replacement, compressed auxiliary maps and checkerboard-style schedules are prior art individually.

## Predictor comparison interpretation
The predictor-only experiment uses a common step-4/16-phase grid and should not be merged with the native EDR2 step-2/four-phase protocol. The 3×3 predictor has MAE 4.8130, while a 5×5 no-weighted-loss ablation has MAE 4.6233 and 140/243 positive predictor outcomes versus 133/243 for 3×3. The 3×3 model should be presented as a smaller/cheaper CNN trade-off if raw records confirm these figures, not as the universally best predictor.

## External baselines
Multi-MSB+Huffman and corrected PPMR are potentially useful context, but the reported comparisons are native-protocol replications on a common corpus, not identical packet/security/cost leaderboards. Keep all their overhead and protocol differences visible. Disclose the four PPMR compatibility fixes.

## Writing improvements
- Lead with the decoder-synchronisation problem, not “CNN improves capacity”.
- Define net payload before reporting any BPP.
- State the four phase definitions, masked neighborhood and radius-one proof compactly.
- Put the selection objective in an equation with every cost term.
- State that geometric maximum density is not a positive-capacity guarantee.
- Separate prediction accuracy, gross payload, net payload, exact-recovery trials and runtime.
- Keep RGB exploratory and subsidiary.
- Make runtime penalty and poor external capacity comparison prominent.
- Use a limitations section that identifies unverified dataset provenance, training provenance, cross-platform inference, security and coverage.
- Do not claim formal security proof or independent cryptographic audit.
