# CAPACITY_AWARE_NOVELTY_FEASIBILITY.md
## Feasibility and novelty assessment — a capacity-aware (expected-label-capacity) training objective for the CNN-3×3 RDHEI predictor

Date: 2026-10-22 · Scope: **analysis only**. No training was run, no checkpoint was created or
altered, no manuscript file was edited, no result CSV was modified. The only artifact created by
this pass is this document (read-only checks produced incidental `.pytest_cache`/`__pycache__`
churn; no tracked or result file was touched — verified via `git status` and mtime sweep).

**GO/NO-GO up front: GO — conditional and qualified.** There *is* a testable research hypothesis
("optimizing a differentiable surrogate of the exact, non-monotone label-to-capacity map changes
the BPP/MAE operating point of the predictor in a way weighted-L1 does not"), the machinery to
test it exists in this repository, and the minimum experiment is ~3 h of CPU time on this machine.
However, (a) novelty is **not** established — no bibliography or prior-paper exists anywhere in
this project and the external field is crowded (§2); (b) a structural property of the label map
(§3.4, exhaustively verified in this pass) **bounds the distinct headroom** of the idea and makes
a small or null effect plausible; (c) two concrete repo defects (training-data path/provenance,
bool-returning tests) must be worked around before any comparison is defensible. All three are
handled in the plan (§5–§7).

---

## 0. What was asked, and what was found where

| Item requested | Status in this workspace |
|---|---|
| `main_JISA_reframed.tex` | **Not present.** No `.tex`, `.bib`, `.bibx`, paper PDF, or reference list exists anywhere in the project tree (checked `find` over all extensions; audits `sec3_deliverable_a_implementation_audit.md` §A65-line, `sec3_deliverable_c_critical_issues.md` line 96 independently recorded the same absence). The de-facto manuscript is `Final_report_REVISED_20261020.md` (+ rendered PDF), with `Section_3_Updated.md` as the Section-3 manuscript; all claims below are checked against those. |
| "Recent papers supplied in the project" | **None supplied.** The literature review (`Final_report_REVISED_20261020.md` §4, §15) attests only GAP/CALIC/MED (docstrings), AES (NIST), BOSSbase — all marked "TO BE VERIFIED"; no paper copies exist. External literature was therefore surveyed for *overlap checking only* (§2); no citation is asserted as verified. |
| Code, training scripts, checkpoints, result CSVs, `FINAL_CLOSURE_REPORT.md`, audits | Present and used: `src/rdhei_core.py`, `src/train.py`, `src/cnn_model.py`, `src/predictor.py`, `src/utils.py`, `models/*.pth` (5 checkpoints), `results/final_validation_20261018/*.csv`, `results/rgb_complexity_error_analysis_20261019/*`, `tests/`, `RDHEI_FIXED_V1/RDHEI_DAY1_AUDIT.md`, `FINAL_CLOSURE_REPORT.md`, `RGB_Complexity_Error_Analysis.md`. |

---

## 1. Verified current label-to-capacity mapping and its recovery conditions (Task 1)

### 1.1 Where it lives

- `_compute_bpp_and_range(e_abs)` and its vectorised twin `generate_label_map_fast(error_abs)` —
  `src/rdhei_core.py` lines 92–213. Per pixel, the map emits `(n, min_e, max_e)` where
  `n ∈ {0..7}` is the number of MSBs replaced (`_embed_pixel`, Eq. 1 of the manuscript) and
  `[min_e, max_e]` is the unique-recovery band consumed by `_recover_pixel`.
- Consumer: `content_owner_prepare()` (line ~363) computes
  `pred_int = round(pred_map)`, `e_abs = |image − pred_int|`, then
  `capacity = Σ bpp_map`. The receiver (`receiver_extract_recover`) enumerates all `2^n`
  candidates sharing the preserved low `8−n` bits and returns the unique `c ∈ [0,255]` with
  `min_e ≤ |c − pred_int| ≤ max_e`.

### 1.2 Exact mapping — re-derived independently and verified executably in this pass

The scalar and vectorised implementations were re-run over the full domain: **identical**
(`scalar==vector: True`). The exact map `n(e)` for `e = |e|`:

| e | 0 | 1 | 2 | 3 | 4 | 5–7 | 8 | 9–15 | 16 | 17–31 | 32 | 33–63 | 64 | 65–127 | ≥128 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **n(e)** | 7 | 6 | **5** | 6 | **4** | 5 | **3** | 4 | **2** | 3 | **1** | 2 | **0** | 1 | **0** |
| band | [0,0] | [1,1] | [2,2] | [3,3] | [4,4] | [5,7] | [8,8] | [9,15] | [16,16] | [17,31] | [32,32] | [33,63] | [64,64] | [65,127] | — |

Closed form (verified for all 256 values): `n(0)=7`; for `1 ≤ e ≤ 127`,
`n(e) = 7 − floor(log2 e)` if `e` is **not** a power of two, and `n(e) = 6 − log2 e` if
`e = 2^k`; `n(e) = 0` for `e ≥ 128`. Equivalently, 15 interval indicators:
`n = 7·1{e=0} + Σ_{k=0..6} [(6−k)·1{e=2^k} + (7−k)·1{e ∈ (2^k, 2^(k+1)−1]}]`.

**The map is genuinely non-monotone**, with upward steps exactly at
`e ∈ {2,4,8,16,32,64}` (verified: `(2,5→6), (4,4→5), (8,3→4), (16,2→3), (32,1→2), (64,0→1)`).
Two consequences, relevant to the paper's own wording:

- The manuscript's phrase "monotone-style function" (`Final_report_REVISED_20261020.md` §3.2) is
  imprecise; and the collapsed reward table in `RGB_Complexity_Error_Analysis.md` §5
  ("2–3 → 5, 4–7 → 4, 8–15 → 3, …") assigns each band its **lower-edge (singleton) value** and
  therefore understates the true per-pixel map (e.g. it states 4 bits for all of |e| ∈ 4–7 while
  the implementation gives 5 bits for |e| ∈ {5,6,7}). Any capacity-aware objective must be built
  from the **implementation's** table, not the report's simplification. (Documentation fix
  recommended; no file was edited in this pass.)
- The MAE/capacity mismatch the paper reports (lower MAE but lower BPP on 4.2.06 R/G, 4.2.07;
  `RGB_Complexity_Error_Analysis.md` §5 point 1) is fully explained by this table: capacity is
  driven by mass at exactly `e=0` (7 bits) and by the dead zones at `e=64` and `e≥128`, not by MAE.

### 1.3 Mathematical recovery conditions (verified, not assumed)

For a pixel with original value `x`, prediction `p`, `e=|x−p|`, label `(n, mn, mx)`: embedding
replaces the top `n` bits (`p' = q·2^(8−n) + (x mod 2^(8−n))`), so the receiver's candidate set is
`C = { c ∈ [0,255] : c ≡ x (mod 2^(8−n)) }`, spaced `s = 2^(8−n)` apart. Exact recovery requires
`C ∩ {c : mn ≤ |c−p| ≤ mx} = {x}`. Conditions encoded by the label map:

1. **Interval bands** `e ∈ (2^k, 2^(k+1)−1] → n = 7−k`, band `[2^k+1, 2^(k+1)−1]` (for
   k = 0…6; e.g. `e ∈ (64,127] → n=1, band [65,127]`): the band width and the candidate
   spacing `s = 2^(8−n) = 2^(k+1)` are tuned so at most one candidate can qualify — two
   candidates at admissible distances would need `|c−c'| ≤ 2·mx`, and the algebra closes
   only for the exact `(n, band)` pairs chosen. One more bit would fail: e.g. `e ∈ (64,127]`
   admits `n=1` but **not** `n=2` — for `x=50, p=150` (e=100) both `x=50` (dist 100) and
   `242` (dist 92) qualify under `n=2` — counterexample checked in this pass.
2. **Singletons** `e = 2^k → n = 6−k`, band `[2^k, 2^k]`: uniqueness needs spacing `s > 2·e`,
   i.e. `2^(8−n) > 2^(k+1) ⇒ n ≤ 6−k`. One more bit would make `x` and `x + s` both at distance
   `2^k` from `p = x ± 2^k` (ambiguity), which is exactly why `n(2)=5` (not 6), `n(4)=4` (not 5),
   … and why `n(64)=0`: the dead zone at 64 is a **recovery-uniqueness constraint**, not a bug.
3. `e=0 → n=7, band [0,0]`: the preserved LSB plus the constraint `c = p` pins the candidate.
4. `e ≥ 128 → n=0`: outside every band; pass-through, trivially recovered.

Independent exhaustive re-verification in this pass over the entire concrete domain
(all 65,536 `(x, p) ∈ [0,255]²` pairs, random payloads, full candidate-set enumeration):
**0 recovery failures, 0 non-unique candidate sets, 0 pixels whose `x` falls outside its own
band.** This reproduces the Day-1 audit result (`RDHEI_FIXED_V1/RDHEI_DAY1_AUDIT.md`) with a
fresh implementation-independent check.

**Key structural property (new in this pass — see §3.4):** for every dip `v = 2^k`,
`n(v−1) ≥ n(v+1)`; consequently, for **all** `v ∈ [0,255]` and **all** `D ∈ [1,127]`,
`max_{|d|≤D} n(v+d) = max_{u ∈ [max(0,v−D), v]} n(u)` — i.e. the best capacity reachable by
moving an error in *either* direction within `D` gray levels is always reachable by **shrinking**
it. Verified exhaustively (0 violations over all 32,512 `(v, D)` pairs).

### 1.4 A latent test-harness defect (relevant to any future evaluation)

`tests/test_mapping.py::test_boundary_values` contains **stale expectations** for `|e|=5` and
`|e|=6` (it expects `n=4, band none`; the implementation — correctly, per §1.2–1.3 — gives
`n=5, band [5,7]`). The function returns `False` with 3 printed FAIL lines, yet
`pytest tests/ -q` reports **16 passed** because these tests *return* booleans instead of
asserting (the documented `PytestReturnNotNoneWarning`). The "16 passed" headline therefore
masks the mismatch; correctness rests on the exhaustive checks above, not on the suite. The
comparison experiment must use **assert-based** recovery tests (new test file or the audit
scripts), not the current bool-returning ones.

---

## 2. Prior work and overlap assessment (Tasks 2 & 3)

**In-project prior work:** exactly what §0 says — none beyond docstring attributions. The
closure report (F6) and the manuscript §15 both flag the bibliography as absent; nothing was
fabricated then and nothing is asserted as verified now.

**External landscape (overlap check only; every entry TO BE VERIFIED against full text before
any related-work or novelty statement):**

| Line of work | Representative items (from search; unverified) | Overlap with the proposed contribution |
|---|---|---|
| CNN predictors for RDH/RDHEI | Hu et al., "Reversible Data Hiding by Using CNN Prediction and Adaptive Embedding" (2021, ResearchGate 356678717); Qiu et al., ICNNP, arXiv:2301.01420 / Entropy 2025 27(2):159; Panchikkil et al. 2022 (Optik 250:68137); Arai et al. 2022 (Sensors, PMC9317712) | **Predictor-architecture overlap: high.** A learned predictor improving RDH capacity is standard practice by now. Architecture/parameter count is explicitly excluded by the task from any novelty argument — correctly so. |
| Predicting local complexity / adaptive location selection | ICNNP's **complexity prediction module** (sorts prediction errors by predicted complexity, embeds low-complexity first); "Efficient CNN Prediction with Smoothness Factor for RDH" (2024); "Texture-Aware CNN Predictor for RDH" (Shah & Choi, MDPI Mathematics 14(9):1542, 2026 — explicitly counts **zero prediction errors** as its fidelity proxy); transformer predictor + adaptive embedding (2026); Ping et al. 2024 (ESWA, asymmetric CNN + adaptive mean for RDHEI) | **Mechanism overlap: partial but distinct.** These methods change *where* to embed or *which errors to use* (selection/sorting at embedding time), or add complexity/texture branches. The proposed objective changes *what the predictor is trained to produce*, by optimizing the **exact non-monotone capacity functional of this project's label map**, with no change to the embedding algebra and no extra branch. ICNNP and the texture-aware paper are the two must-read full texts: if either trains its predictor with a loss that is a differentiable proxy of *its* embedding yield (rather than MAE/MSE + a complexity branch), the "first-of-kind" framing dies and the contribution becomes incremental. |
| Optimizing zero-valued prediction errors | Shah & Choi 2026 (zero-error counting as an evaluation metric); histogram-of-error shaping appears throughout PEE/histogram-shifting RDH | Counting/promoting zero errors is evaluation-level or metric-level in the accessible snippets. A surrogate of the **full 15-interval label functional** (including the `e=64` and `e≥128` dead zones and the singleton dips) is not something we found; but absence in search snippets ≠ absence in literature. Verification obligation recorded in §7. |
| Differentiable rate/yield surrogates (machinery, other fields) | Soft/temperature binning, soft histograms and differentiable rate terms are standard in learned compression/steganography rate–distortion training | The *machinery* is not novel; the application to this label map may be. Novelty, if any, lives in (i) the exact functional, (ii) its non-monotone structure and the analysis in §3.4, (iii) the measured BPP/MAE operating-point shift vs weighted-L1. |

**Explicit anti-claims (per the task's instruction):** no argument in this document rests on
parameter count (46,881 is the smallest in the family, but that is an engineering fact, not a
contribution), on aggregate BPP (5.1897 gray / 4.8838 RGB means are already achieved by the
existing checkpoint and are not evidence for a new objective), or on "the label map is
non-monotone" alone (a property, not a method).

**Distinctness statement, phrased defensibly:** the candidate contribution is *"training the
RDHEI predictor against a differentiable surrogate of the deployed, exactly-verified hard label
map (including its dead zones), and characterizing when that changes the capacity–distortion
frontier relative to MAE-type training"*. Whether that is novel is a **related-work verification
question, not a code question**, and is unresolved until the full texts above are read.

---

## 3. Technical design: is the capacity-aware loss well-defined? (Task 4)

### 3.1 What must be optimized, exactly

Deployment capacity is the **hard** functional
`C_hard(pred) = Σ_i n(| I_i − round(pred_i) |)` with `n` the verified table of §1.2, and
`BPP = C_hard / (H·W)`. It is piecewise-constant in `pred` ⇒ gradient zero almost everywhere ⇒
a surrogate `ĉ(e) ≈ E[n(e)]` is required for training. The training pipeline already exposes
everything needed: `src/train.py` produces continuous `pred ∈ [0,255]` (Sigmoid×255) against
integer targets `t ∈ [0,255]`; per-patch `e = |pred − t|` is the exact quantity that becomes
`e_abs` after rounding at deployment. The surrogate is trained on the batch expectation
("expected label capacity"), and evaluated on the hard map.

### 3.2 Candidate differentiable surrogates

Notation: `e ≥ 0` continuous, `τ > 0` temperature, `σ` the logistic sigmoid.

**S1 — Sigmoid-interval decomposition (recommended primary).**
Using the 15-interval form of §1.2:
`ĉ_S1(e) = 7·σ((e+0.5)/τ)·σ((0.5−e)/τ) + Σ_k (6−k)·σ((e−2^k+0.5)/τ)·σ((2^k+0.5−e)/τ) + (7−k)·σ((e−2^k)/τ)·σ((2^(k+1)−1−e)/τ)`.
- Exact in the limit `τ → 0` on integer `e`; bounded in `[0,7]`; preserves every dip and both
  dead zones; `O(15)` ops per pixel.
- Limitations: gradients live only within ~`τ` of the 30 band edges — errors deep inside a band
  (e.g. `e=40` in `(33,63]`) receive ~zero signal, so the loss **cannot** by itself reproduce
  weighted-L1's continuous pressure toward 0 (see risk R2, §3.5). Temperature couples two
  demands: small `τ` sharpens the dips (the interesting signal) but starves gradients; large `τ`
  blurs exactly the singleton-vs-band distinctions the objective exists for. Pre-register
  `τ = 1.0`, sensitivity `τ ∈ {0.5, 2.0}`.

**S2 — Kernel-smoothed table.** `ĉ_S2(e) = Σ_{v=0}^{127} n(v)·K_τ(e−v)` with normalized kernel
`K_τ` (Gaussian/triangular). Equivalent to S1 with softer edges; simplest to implement and to
prove bounded; slightly more expensive (`O(128)` or a folded fast form). Limitations: same flat
interior; normalization must be renormalized near `e=0` and `e=127` to avoid edge bias.

**S3 — Soft-round + piecewise-linear table.** Differentiable rounding of the prediction
(`pred_soft = pred + (round(pred) − pred).detach()` STE, or a tanh-based soft round), then
piecewise-linear interpolation `n_lin` of the staircase over integer `e`. Aligns the surrogate
with the deployed `round()`. Limitation: interpolation *cuts across* each dip (a ramp between
`n(2)=5` and `n(3)=6` invents values), so the dead zone at 64 becomes a V of width 1 — the
surrogate then under-penalizes the true `n(64)=0` cliff. Use only as an ablation.

**S4 — Soft-histogram / distribution-level loss.** Soft-bin the batch errors into 256 bins
(softmax with temperature), dot with the `n` table, average. Literally optimizes "expected label
capacity" and generalizes to distribution constraints (e.g. cap the `n=7` fraction to control
recovery cost, or a MAE-budgeted variant). Same gradient-support caveats as S1; useful later,
not needed for the minimum experiment.

**Recommended composite (pre-registered):**
`L(θ) = −(1/B) Σ_i ĉ_S1(e_i) + λ·(1/B) Σ_i w(e_i)·|e_i|`, with the project's existing
`w(e) = 1 + 2e/255`, `λ = 0.1`, and an STE through the rounding so `ĉ` sees the deployed error.
`λ>0` is not a trick — it is required by risk R2 (flat band interiors would otherwise stop being
improved at all, likely worsening MAE for no capacity gain). The baseline arm is the existing
`WeightedL1Loss(α=2.0)` unchanged (`src/train.py` lines 24–37).

### 3.3 How the exact hard-label capacity is evaluated (no surrogate in evaluation)

At evaluation time the surrogate is discarded. For every checkpoint and every test image
(6 grayscale + 5 genuine RGB, per channel — identical sets and conventions as
`scripts/fv_b2_baselines.py` / `fv_b3_ablation.py`):
1. `pred_map = cnn_predict_map(...)` (`src/predictor.py`), `pred_int = round(pred_map)`;
2. `e_abs = |image − pred_int|`; `bpp_map, min_e_map, max_e_map = generate_label_map_fast(e_abs)`;
3. hard `capacity = Σ bpp_map`, `BPP = capacity/(H·W)` (RGB: mean over 3 per-channel BPPs —
   the report's stated convention);
4. cross-check: hard capacity computed by the vectorised map equals the scalar map on the
   realized `e_abs` values (guards against any future divergence; currently identical, §1.2).
This is bit-for-bit the quantity the manuscript tables report; the comparison stays
apples-to-apples because the label map, embedding and receiver are untouched and shared.

### 3.4 The structural bound the design must confront (verified in this pass)

From §1.3: for every error `v` and every move radius `D`, the best capacity attainable by moving
the error in **either** direction is attainable by **shrinking** it (0 violations over all
`(v, D)`, `D ≤ 127`). Applied to real data: re-computing the **hard integer** `|e|` histograms of
the existing CNN-3×3 checkpoints from `results/rgb_complexity_error_analysis_20261019/histogram_bins.csv`
(abs bins are delimited at `x.5`; decoding `value = bin_left + 0.5`), the reconstructed label
distributions reproduce `label_histograms.csv` **exactly for all 21 units**, and the derived BPPs
reproduce the published values exactly (gray mean **5.1897**, 4.2.07 **4.7330** — matching
`Final_report_REVISED` §8 / `b3_ablation_gray.csv`). On those histograms the `±D`-oracle and the
shrink-only oracle are **identical for every one of the 21 units** (`extraD1 = extraD4 = 0.0000`):

| Set (CNN-3×3, hard) | hard BPP now | shrink/±D=1 oracle (gain) | shrink/±D=4 oracle (gain) |
|---|---|---|---|
| gray (6 images) | 5.190 | 5.793 (+0.603) | 6.392 (+1.202) |
| RGB (15 channels, per image) | 4.221–5.641 | +0.415–0.654 | +0.951–1.260 |

Interpretation for the hypothesis:
- The **total** bounded-move headroom is large (+0.60 bpp at `D=1` on gray) but it is *shared*
  headroom — any better MAE predictor harvests it; it is **not** an argument for the
  capacity-aware objective.
- The headroom **distinct** to "moving errors uphill toward capacity peaks" is structurally
  zero on this map: every dip `2^k` has a left neighbor that is at least as good
  (`n(2^k−1) = 8−k ≥ n(2^k+1) = 7−k`), and shrinking never needs to be resisted on net.
- What *is* distinct is the **gradient weighting during finite training**: weighted-L1 keeps
  pushing mid-band errors (e.g. 40→20) where capacity is flat, and takes transient capacity
  losses crossing dips (33→32 loses 1 bit, 3→2 loses 1 bit, 65→64 loses 1) en route; the
  surrogate refuses those crossings and ignores the flat interior. Whether the resulting
  equilibrium has **higher BPP at matched MAE** is exactly the empirical question.
- Size of the pool the two losses *dispute*: the mass sitting exactly *at* the dips
  (each pixel at `e ∈ {2,4,8,16,32,64}` is worth +1 bit by an up-move and +2 bits by a
  down-move for `k≥2`) is **0.199–0.312 bpp** across the 21 CNN-3×3 units (gray mean **0.281**,
  RGB mean ≈ **0.260**; per-unit values in Appendix A). The up-move share (+1 bit at +1 MAE)
  is the capacity-aware-only slice; realistic realized effects should be expected in the
  **±0.01–0.06 bpp** band, i.e. the same order as the existing v1-vs-v3 loss-ablation deltas
  (0.007–0.017 bpp, `Final_report_REVISED` §11). The experiment must be powered
  (multi-seed, paired) accordingly. Mass at `e ≥ 128` (CNN-3×3) is ≈ 0.00000 bpp — the tail
  dead zone is not a lever for this checkpoint (it was for MED, 0.19%).

### 3.5 Risks (technical)

- **R1 — Surrogate gap:** optimizing `ĉ_S1` need not optimize `n`; the STE rounding adds a
  second gap. Mitigation: hard-capacity validation each epoch (§5), `τ` sensitivity.
- **R2 — Gradient starvation in band interiors:** flat `n` ⇒ no pressure to shrink 40→20.
  Mitigation: the `λ=0.1` MAE anchor (pre-registered).
- **R3 — Degenerate operating point:** a pure capacity loss accepts `+1` MAE for `+1` bit
  wherever model capacity allows; report the BPP/MAE pair, never BPP alone; optionally plot the
  `{λ}` path as follow-up, not in the minimum run.
- **R4 — Side effects on the pipeline:** none by construction — the predictor is plug-in
  (audit A2, `sec3_deliverable_a_implementation_audit.md`); maps are recomputed from predictions,
  so exact recovery cannot be violated by *how* predictions are trained. Re-test e2e anyway (§6).
- **R5 — Secondary cost metrics:** higher `n=7` mass raises expected receiver work
  `Σ frac(n)·2^n` (measured 38.3–41.3 in `RGB_Complexity_Error_Analysis.md` §5) and raises
  stego distortion at full-payload embedding (capacity and distortion are coupled in this
  scheme). Both must be reported as secondary endpoints.

---

## 4. Can the project support a reproducible retraining comparison? (Task 5)

### 4.1 What matches

- **Architecture:** `build_model(patch_size=3, residual=True)` is exactly the deployed
  CNN-3×3 (46,881 params, 122,816 MACs/patch — verified by loading `models/v4_patch3.pth`
  in this pass: `Patch 3x3 | Residual True | 46,881`). Both arms use the identical class; only
  the loss differs ⇒ params/MACs identical by construction.
- **Optimizer/schedule:** Adam `lr=1e-4, wd=1e-4`, `CosineAnnealing(T_max=epochs, eta_min=1e-6)`,
  batch 256, stride 4, flip augmentation, 10% patch-level val split, `set_seed(42)`,
  best-val checkpointing — all specified in `src/train.py` and confirmed by closure check C16.
- **Dependencies:** Python 3.10.12, torch 2.14.0 (CPU), numpy 2.2.6, Pillow, pycryptodome —
  all import cleanly **in this environment** (checked). `requirements.txt` satisfied.
- **Test suite baseline:** `pytest tests/ -q` → 16 passed (7.4 s) — with the caveat in §1.4.
- **Evaluation harness:** `scripts/fv_b2_baselines.py`, `fv_b3_ablation.py`,
  `fv_d_e2e.py`, `fv_d_variants.py`, `fv_e_runtime.py` define the exact BPP/MAE/e2e/runtime
  protocols used by the manuscript; a new checkpoint can be dropped into their `VARIANTS` lists
  with a one-line addition (evaluation-only change, in new script copies — existing scripts and
  CSVs stay untouched).

### 4.2 What is missing or constraining (all solvable; none blocks a GO)

| # | Gap | Evidence | Consequence / fix |
|---|---|---|---|
| M1 | **`src/train.py` cannot train the 3×3 model** (`PATCH = 5` module constant; `src/utils.py` `PATCH_SIZE = 5`) | `Final_report_REVISED` §6.3 (provenance gap), code lines 8–9 | A new parameterized training script (patch size, loss, seed as arguments) must be added; historical `v4_patch3` provenance remains unverifiable, so the **baseline arm must be a retrain** under the same script — the historical checkpoint is an external reference point only, never "the baseline" (closure F4). |
| M2 | **Training data is not in the repository.** 200 `.pgm` files exist at `../data/train` (verified present, **256×256** each; note the "BOSSBase 10k" claim is user-confirmed only, closure F5) | `ls ../data/train`, PIL header check (200×{256,256}) | Point `train_dir` at `../data/train` (path default in `train.py` is `data/train`, which does not exist here). Both arms share the identical file list and order ⇒ internally matched. Provenance stays disclosed as unverified. |
| M3 | **Hardware: CPU-only, 4 GB RAM host** (i5-8265U, torch sees 4 threads, CUDA unavailable; measured in this pass) | `torch.cuda.is_available() == False`, `free -g` | Measured throughput: 3×3 ≈ **138 steps/s**, 5×5 ≈ 80 steps/s (batch 256). At stride 4 over 200×(256×256) images ×3 flips = 2,457,600 patches ⇒ ≈8,640 steps/epoch ⇒ **≈63 s/epoch, ≈21 min per 20-epoch run** for 3×3. Six runs (2 arms × 3 seeds) ≈ **2.5–3 h** plus evaluation. RAM: the current list-based `PatchDataset` materializes ≈2.46M small arrays (≈0.4–0.6 GB) — fits, but tight on a 4 GB host; a contiguous-array dataset (≈130 MB) is the safe route and must be **stream-equivalence-tested** against the original on a small subset (same patches, same order, same targets) so the "matched training data" claim survives. |
| M4 | **Bool-returning tests** mask mismatches (§1.4) | executed: `test_boundary_values` returns False, pytest still "passes" | New assert-based unit tests for the label map + a fresh exhaustive recovery check (the §1.3 script) become part of the experiment's gate. |
| M5 | No training logs/configs exist for any checkpoint | closure F4 | The new script must write a run manifest (config, seed, git state, data file list hash, per-epoch val MAE **and** val hard-BPP) per run — this is also what makes the comparison publishable-grade reproducible. |

### 4.3 Reproducibility protocol (matched by construction)

- One script, two loss modes, all else identical: data files (sorted `../data/train/*.pgm`),
  patch extraction (stride 4, reflect pad, center mask, flips), model init seed, split
  (`random_split` after `set_seed`), loader shuffle, batch 256, Adam/cosine as above,
  20 epochs, best-checkpoint rule.
- Seeds `{42, 43, 44}` per arm (the historical single-seed, single-checkpoint deltas of
  0.007–0.017 bpp are inside plausible seed noise; multi-seed is mandatory, not optional).
- **Selection rule (pre-registered):** best validation **hard-label BPP** (the study's primary
  endpoint) for *both* arms, with val MAE recorded as secondary. Test images are never used for
  selection, so the primary comparison stays unbiased.
- Checkpoints written to a new directory (e.g. `models/cap_aware_study/`), never over
  `models/v*.pth`. The candidate loss lives in a new module; `src/train.py` and `src/rdhei_core.py`
  remain untouched (preserving closure state, including the receiver fix at HEAD).

---

## 5. Minimum defensible experiment (Task 6)

**Arms.** A = baseline retrain, `WeightedL1Loss(α=2.0)` (bit-identical to `src/train.py`);
B = candidate, `L = −mean ĉ_S1(e) + 0.1·WeightedL1(e)`, `τ=1.0`, STE rounding. Both 3×3+residual,
20 epochs, seeds {42,43,44}. (Optional seventh run, only if budget remains: pure `λ=0` arm to
isolate the anchor's effect — explicitly secondary.)

**Primary endpoint (paired, per test image/channel, seed-mean):** hard-label `BPP`
(`generate_label_map_fast` on `round(cnn_predict_map)`) on the fixed 11-image/15-channel
benchmark. Report Δ(B−A) per unit, mean, and seed spread.

**Secondary endpoints (all pre-registered, all from existing harness conventions):**
1. Prediction MAE (gray levels, per §7.3 of the report) — with a non-inferiority margin.
2. Label distributions: `frac(n=0..7)`, mass at `{0,1,2,3,4,8,16,32,63,64,65,127,128}`
   (the dip/dead-zone masses — the *mechanism* evidence: a capacity-aware win must show as
   reduced mass exactly at `{2,4,8,16,32,64}` and/or `≥128`, not as generic histogram shrink).
3. Parameters (both 46,881) and MACs/patch (both 122,816) — equality asserted, not compared.
4. Predictor-only runtime — `fv_e_runtime.py` protocol (Lena 512×512, CPU, warm-up 5, 10 repeats).
5. Expected recovery cost `Σ frac(n)·2^n` per image.
6. Stego PSNR of the full-capacity marked plaintext vs original (capacity/distortion coupling).
7. Exact-recovery matrix: both arms' seed-42 checkpoints through `fv_d_e2e`-style payload
   matrix (payloads ∈ {0, 1, 1000, 25%, 75%, capacity−1, capacity}, 6 gray + 5 RGB with
   per-channel nonces), verified by direct array comparison, **with assert-based tests** (M4).
   Reuse the vectorized-but-output-identical fast path from
   `results/rgb_complexity_error_analysis_20261019/fast_impl.py` for speed, after the
   bitwise-equivalence check it already passed (88/88, 8/8).

**Budget.** 6 training runs ≈ 2.5–3 h; evaluation ≈ 1–1.5 h; total < 1 working day on this host.
Storage: 6 × 46,881-param checkpoints ≈ 1.2 MB. No GPU needed; none available.

**Power sanity check.** Observed single-checkpoint loss-axis deltas are 0.007–0.017 bpp with
unknown seed variance; the disputed dip pool is 0.199–0.312 bpp (capacity-aware-only up-move slice smaller). With 3 seeds
× 11 paired images the design resolves ~0.02 bpp mean shifts if seed SD ≲ 0.01 bpp (to be
confirmed from the baseline seeds themselves — the first run of the study measures its own
noise floor; if seed SD exceeds 0.02 bpp, extend to 5 seeds before interpreting).

---

## 6. Failure criteria (pre-registered; a failure is a result, not a defect)

- **F0 — Optimization failure:** NaN/Inf loss, or >90% of batches with surrogate gradient norm
  below 1e-6 (starvation), or τ-sensitivity flips the sign of ΔBPP between 0.5 and 2.0.
  ⇒ surrogate design rejected (try S2/S4); no claim either way about the hypothesis.
- **F1 — Null effect:** seed-mean ΔBPP ≤ +0.01 bpp **or** win-sign inconsistent (<8 of 21
  paired units positive at seed-mean). ⇒ hypothesis unsupported on this benchmark: the
  non-monotone map's *distinct* headroom is practically zero under matched training (consistent
  with the §3.4 dominance property). This is a publishable negative result together with the
  analysis of §3. (Note: the baseline arm's own seed spread is measured first; if it exceeds
  0.02 bpp, widen to 5 seeds before applying F1.)
- **F2 — Net-harmful operating point:** ΔBPP ≤ +0.02 bpp **and** ΔMAE > +0.15 gray levels
  (or recovery-cost per pixel up >15% at equal BPP). ⇒ candidate objective dominated.
- **F3 — Reversibility regression:** any e2e exact-recovery or bit-exactness failure in §5.7.
  ⇒ experiment invalid until explained (structurally unexpected — predictor is plug-in — so
  this indicates an implementation error, not a scientific finding).
- **F4 — Feasibility failure:** RAM/time budget exceeded on this host (M3) even after the
  contiguous-array dataset; fall back to a pre-registered stride-8 pilot **for both arms
  equally**, clearly labelled as a pilot.

---

## 7. GO / NO-GO recommendation

**GO — for a testable research hypothesis, not for novelty or publication.**

Why GO:
1. The objective is **technically well-defined**: the exact hard functional is verified over the
   full domain (§1.2–1.3), a bounded, exact-in-the-limit differentiable surrogate exists (S1),
   and the evaluation path from surrogate training to hard-label BPP is unambiguous (§3.3).
2. The mechanism is **distinct from embedding-time selection**: complexity/texture prediction
   and adaptive location selection (ICNNP-type) change *which* errors are used; this changes
   *what the predictor optimizes*, including the dead zones at `e=64`/`e≥128` that no MAE-type
   loss represents. The overlap risk is real but currently only *partial* on accessible evidence
   (§2), and the two must-read full texts (ICNNP arXiv:2301.01420; Shah & Choi, Mathematics
   14(9):1542) are identifiable and obtainable.
3. The project **can support the comparison today**: data present (`../data/train`), deps
   installed, checkpoints loadable, harness defined, cost ~3 h CPU (§4).
4. Both outcomes are informative: §3.4's exhaustively verified dominance property
   ("non-monotone dips add no up-move headroom beyond shrinking") means a positive result would
   be a subtle and interesting *training-dynamics* finding, and a null result (F1) is a clean,
   analysis-backed negative that closes the idea rigorously.

Why the GO is qualified (conditions, all pre-registered above):
- **C1 (novelty gate):** before any related-work or novelty sentence exists in the manuscript,
  the full texts in §2's overlap table — especially ICNNP's and the texture-aware predictor's
  *training losses* — must be read. If either optimizes a differentiable embedding-yield proxy,
  reframe as incremental-comparison work. Do not claim novelty on params/BPP (task constraint,
  honored here).
- **C2 (protocol gate):** matched two-arm × 3-seed retrain under one parameterized script
  (M1–M5 fixes); historical checkpoints referenced, never used as the baseline arm.
- **C3 (expectation gate):** effect-size expectation set to ±0.01–0.06 bpp distinct headroom;
  the experiment is powered to that scale; failure criteria F0–F4 stand as written.
- **C4 (integrity gate):** all existing artifacts preserved (done in this pass); new outputs go
  to new directories; the label map, embedding, receiver, and all `src/` pipeline files remain
  untouched; the documentation discrepancies noted in §1.2 ("monotone-style" wording; the
  collapsed reward table; the stale test expectations) are fixed in a *separate, reviewed*
  documentation/test pass, not incidentally here.

**NO-GO triggers:** failure of C1 (direct prior art found), or F1/F2 in the pilot, or F4 without
the pilot fallback holding.

---

### Appendix A — Executable evidence produced by this pass (all read-only)

| Check | Result |
|---|---|
| `generate_label_map` vs `generate_label_map_fast` over all 256 values | identical |
| Exact `n(e)` table + closed form `7−⌊log2 e⌋ − 1{e=2^k}` (1≤e≤127) | matches implementation at all 256 points |
| Upward steps (non-monotonicity) | exactly at `{2,4,8,16,32,64}` |
| Exhaustive recovery, all 65,536 `(x,p)` pairs, random payloads, full candidate enumeration | 0 failures, 0 ambiguities, 0 out-of-band originals |
| `n=2` rejected for `e ∈ (64,127]` (counterexample x=50, p=150 → candidates 50 & 242 both qualify) | confirms band/`n` pairing necessity |
| Dominance property: `max_{|d|≤D} n(v+d) = max_{u≤v, u≥v−D} n(u)` for all v, all D≤127 | 0 violations (32,512 pairs) |
| Hard `|e|` histograms reconstructed from `histogram_bins.csv` (abs bins at `x.5` edges) → label distributions vs authoritative `label_histograms.csv` | **exact match, all 21 units**; derived BPP reproduces published gray mean 5.1897 and 4.2.07 = 4.7330 |
| ±D oracle vs shrink-only oracle on those hard histograms (21 units, D=1,4) | identical (`extra = 0.0000` bpp everywhere); gray hard 5.190 → D=1 5.793 → D=4 6.392; RGB per-image D=1 gains +0.415…+0.654, D=4 +0.951…+1.260 |
| Dip-position mass at `{2,4,8,16,32,64}` (disputed pool) | 0.199–0.312 bpp per unit (gray mean 0.281; RGB mean 0.260) |
| Tail mass `e≥128` (CNN-3×3) | 0.00000–0.00001 bpp — negligible lever for this checkpoint |
| Checkpoints load (`v4_patch3`, `v1_full`, `v3_no_weighted_loss`) | patch/residual/params: 3/T/46,881 · 5/T/112,417 · 5/T/112,417 |
| `pytest tests/ -q` | 16 passed (7.4 s) — but `test_boundary_values` internally returns False (3 stale expectations; bool-return masking) |
| Environment | Python 3.10.12, torch 2.14.0 CPU (no CUDA), 4 GB RAM host, i5-8265U |
| Throughput benchmark | 3×3: 138 steps/s; 5×5: 80 steps/s (batch 256, CPU) |
| Training data | `../data/train`: 200 `.pgm`, all 256×256; `data/train` (train.py default) absent |

### Appendix B — Minimum file additions for the future experiment (none created in this pass)

1. `scripts/train_capacity_study.py` — parameterized patch/loss/seed; contiguous-array dataset
   (stream-equivalence tested); per-epoch val MAE + val hard-BPP; run manifest JSON per run.
2. `src/losses_capacity.py` — `CapacitySurrogateLoss` (S1 + λ-weighted-L1 + STE), unit-tested
   against the hard table (integer `e`, `τ→0` convergence).
3. `scripts/eval_capacity_study.py` — copies of the `fv_b2/b3` conventions over the new
   checkpoint directory; emits the §6 endpoint table.
4. `tests/test_capacity_loss.py` — assert-based: surrogate boundedness, `τ→0` exactness,
   gradient non-starvation at band edges, plus the §1.3 exhaustive recovery check as a proper
   asserting test (fixes M4 without touching the legacy bool-returning tests).
