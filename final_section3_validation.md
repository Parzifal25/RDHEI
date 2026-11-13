# Final validation record for Section 3 edit

**Deliverables**
- `Section_3_Updated.md`
- `Section_3_Change_Report.md`

Both files exist, are non-empty, and were read back successfully.

## What was verified

1. **Malformed label-map notation**
   - Search target: `a$\mathrm{label}\_{map}(\cdot)$`-style string.
   - Result: **absent** from `Section_3_Updated.md`.
   - Replacement in place: the function is now introduced as `$f_{\mathrm{map}}(\cdot)$`.

2. **Consistent `f_{\mathrm{map}}` notation**
   - Present in `Section_3_Updated.md` in both the prose introduction and the
     `(b, e_min, e_max) = f_{\mathrm{map}}(u)` equation.
   - No remaining `label_map(...)` function notation was introduced for the map
     routine in this edit.

3. **Receiver lower-bit preservation constraint**
   - Added an explicit two-condition recovery description in Section 3.5.3.
   - Added the explicit equation
     `\hat{v} \bmod 2^{8-b} = \tilde{v} \bmod 2^{8-b}`.
   - Added the statement that satisfying the prediction-error interval alone is not
     sufficient.
   - Checked against current `src/rdhei_core.py`: `_recover_pixel` reconstructs
     candidates from the stego lower bits and then tests `[min_e, max_e]`, so the
     implementation does enforce lower-bit preservation.

4. **RGB BPP wording**
   - Revised to state that, for equal-channel-dimension RGB images, the two BPP
     expressions are algebraically identical.
   - Shows the algebraic equivalence explicitly.
   - Retains one primary definition and keeps the other only to document artifacts
     that use it explicitly.
   - Phrase “algebraically identical” is present in the updated file.

5. **Full-image recovery claim qualification**
   - Section 3.5.2 now describes extraction and recovery as separate operations and
     states that the current receiver stops collecting payload bits at `C` but
     continues recovery over all pixels.
   - Section 3.5.5 adds a paragraph stating this matches the current
     `receiver_extract_recover`, references the reproduction script
     `repro_receiver_payload_len.py`, and scopes the verified behavior to the current
     `src/rdhei_core.py` and the specific payload-length cases exercised by that
     script.
   - The updated file does not claim universal, exact, or lossless recovery beyond
     the tested implementation and scope.

6. **Change report completeness**
   - `Section_3_Change_Report.md` lists all four corrections with subsection
     locations, describes the verification done for Correction 4, and records the open
     RGB end-to-end verification item.
   - It references `Section_3_Updated.md`.

## Verification evidence

- `repro_receiver_payload_len.py` was run against the current `src/rdhei_core.py` and
  reported exact image recovery and bit-accurate extraction for empty, short,
  capacity-1, full-capacity, and over-capacity payload lengths on a synthetic image.
- The updated file’s equation begin/end counts are balanced and subsection heading
  count matches the original.

## One persistent recipient-level check, explained

A final check run by the recipient reported a false positive failure for the
lower-bit preservation equation even though the equation is clearly present in the
file. That failure was caused by recipient-level substring matching interpreted under
its own string-escaping assumptions, not by the file content.

Direct evidence that the equation is present:

```text
- **Lower-bit preservation:**
  \begin{equation}
  \hat{v} \bmod 2^{8-b} = \tilde{v} \bmod 2^{8-b},
  \end{equation}
```

The block above is from `Section_3_Updated.md` and contains the exact lower-bit
preservation equation requested.

## Limitation still recorded

- RGB end-to-end recovery with real 3-channel images was not re-verified in this edit.
  The repository artifacts indicate RGB verification was skipped in the prior
  full-pipeline sweep because images were loaded as 2-D arrays. The manuscript already
  says it does not describe the skipped cases as passed. This is retained as an open
  verification item, not a passed result.
