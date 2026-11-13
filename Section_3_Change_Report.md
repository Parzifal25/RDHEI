# Section 3 Change Report

**Source file:** `sec3_deliverable_b_section3_manuscript.md`
**Updated file:** `Section_3_Updated.md`
**Date:** 2026-10-18

This report lists the four requested corrections, the subsections they touch, and the
unresolved implementation-verification issue associated with Correction 4.

---

## Correction 1 — Label-map notation in Section 3.3.1

- **Target:** the malformed notation `a$\mathrm{label}\_{map}(\cdot)$`.
- **Location:** Section 3.3.1, first paragraph and the equation that introduces the
  per-pixel triplet.
- **Change:** Replaced the malformed notation with the consistent function notation
  `$f_{\mathrm{map}}(\cdot)$`. The function is introduced explicitly as the label-map
  routine in `src/rdhei_core.py`, and the same notation is used at the equation that
  defines `(b, e_min, e_max) = f_map(u)`.
- **Consistency check:** `f_{\mathrm{map}}` is now the only notation used for the
  label-map function in Section 3. No new mapping behavior was introduced and the
  operational description points to `_compute_bpp_and_range` as before.

## Correction 2 — Receiver lower-bit preservation constraint in Section 3.5.3

- **Target:** the receiver-side recovery description and Equation (recover).
- **Location:** Section 3.5.3.
- **Change:** The recovery text and equations now state the two required conditions
  explicitly:
  1. lower `8-b` bits must be preserved, i.e. `\hat{v} mod 2^{8-b} = \tilde{v} mod 2^{8-b}`;
  2. the prediction-error interval condition
     `L_min(y,x) <= |\hat{v} - P(y,x)| <= L_max(y,x)`.
- The text now explicitly says that satisfying the prediction-error interval alone is
  not sufficient.
- The description was checked against the current `src/rdhei_core.py`. The current
  `_recover_pixel` loop searches candidate upper bits, reconstructs a candidate by
  combining the candidate upper bits with the stego lower bits (`(combo << n_lower) | lower`),
  and selects the candidate whose prediction error falls in `[min_e, max_e]`. Because the
  candidate is built from the observed lower bits, the implemented routine does enforce
  lower-bit preservation implicitly. The manuscript now states that constraint explicitly
  rather than leaving it implicit.

No discrepancy was found between the stated constraint and the current implementation.

## Correction 3 — RGB BPP explanation in Section 3.3.2

- **Target:** the two BPP expressions presented as if they were different notions.
- **Location:** Section 3.3.2.
- **Change:** The text now states explicitly that, for an RGB image whose three channels
  have the same spatial dimensions, the two expressions are algebraically identical, and
  it shows the short algebraic equivalence. It states that the manuscript uses the
  per-channel-average definition `BPP_color` in Eq. (bppcolor1) throughout Section 3, and
  retains the total-capacity form only to document external artifacts that invoke it
  explicitly. It does not suggest that the two produce different results for a single RGB
  image.
- Existing definitions of `C_c`, `H`, `W`, and BPP were preserved. No experimental values
  were changed.

## Correction 4 — Qualify the full-image recovery claim in Section 3.5.2 and 3.5.5

- **Target:** the extraction-loop description and the claim that payload extraction stops
  after `C` bits while image recovery continues for every pixel.
- **Location:** Section 3.5.2, Section 3.5.5.
- **Verification performed:**
  - Inspected the current `src/rdhei_core.py` `receiver_extract_recover`.
  - In the current file, the outer pixel loop does **not** stop once extraction reaches
    `payload_len`. The extraction budget is enforced inside the extraction inner loop
    only, and `_recover_pixel` is still called for every pixel, including `n>0` pixels
    beyond the payload boundary.
  - Ran the repository's reproduction script `repro_receiver_payload_len.py` against the
    current `src/rdhei_core.py`. It reported exact image recovery and bit-accurate
    extraction for empty, short, capacity-1, full-capacity, and over-capacity payload
    lengths on a synthetic image.
- **Manuscript change:**
  - Section 3.5.2 now describes extraction and recovery as separate operations and states
    that the current receiver stops collecting new payload bits once `C` bits are gathered
    but continues the per-pixel recovery loop over the entire image.
  - Section 3.5.5 now adds a dedicated paragraph stating that this matches the current
    implementation, naming the script that was run, and scoping the verified behavior to
    the current `src/rdhei_core.py` and the specific payload-length cases exercised by that
    script.
- **Scope statement:** The updated manuscript does not claim universal, exact, or lossless
  recovery beyond what the current implementation and the available tests establish. It
  states the scope of verification explicitly.

### Unresolved implementation-verification issue

- The updated manuscript no longer asserts unconditional full-image recovery for arbitrary
  payloads. Instead, it scopes the claim to the current implementation and the payload-length
  cases verified by `repro_receiver_payload_len.py`.
- RGB end-to-end recovery with real 3-channel images was **not** re-verified in this edit.
  The repository artifacts indicate RGB verification was skipped in the prior full-pipeline
  sweep because images were loaded as 2-D arrays. The manuscript already states this
  explicitly and does not describe the skipped RGB cases as passed. This is retained as an
  open verification item, not as a passed result.

---

## Validation checklist performed before delivery

- [x] Searched the manuscript for the malformed label-map notation and confirmed it is gone.
- [x] Checked that `f_{\mathrm{map}}(\cdot)` is used consistently for the label-map function.
- [x] Verified that Section 3.5.3 explicitly includes the lower-bit preservation constraint
      and states that the prediction-error interval alone is insufficient.
- [x] Verified that the RGB BPP text states the two forms are algebraically identical under
      equal channel dimensions and does not present them as different results for one image.
- [x] Checked recovery/extract claims against the current `src/rdhei_core.py` and against
      the output of `repro_receiver_payload_len.py`, and scoped the claim accordingly.
- [x] Reviewed the edited Markdown/LaTeX for broken delimiters, malformed equations, and
      accidental deletions.
- [x] Produced a diff against the original and limited changes to the four corrections plus
      the necessary consistency wording around them.
- [x] Verified both output files exist, are non-empty, and can be read back.

---

## Files delivered

- `Section_3_Updated.md`
- `Section_3_Change_Report.md`

