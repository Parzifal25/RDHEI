# FINAL_CLOSURE_REPORT.md

**RDHEI Project — Final Technical Closure Pass**
Date: 2026-10-20 · Workspace: `/home/parzifal/RDHEI_Project/RDHEI_FIXED_V1` (project root)
Scope: evidence-driven closure for the manuscript (CNN-3×3 RDHEI). No retraining, no new
experiments, no architecture changes, no manuscript rewrite. Every "verified" item below was
executed or directly inspected in this pass; reported statuses from the task brief were
re-checked, not assumed.

---

## 1. Checks performed and actual outcomes

| # | Check | Command / evidence | Outcome |
|---|---|---|---|
| C1 | Project pytest suite | `python3 -m pytest tests/ -q` | **16 passed, 11 warnings, 0 failed, 0 skipped** (warnings = `PytestReturnNotNoneWarning` in `tests/test_mapping_ascii.py` — tests return bools instead of asserting; pre-existing, cosmetic) |
| C2 | Root-level pytest collection | `python3 -m pytest -q` (as `run_tests.sh` does) | **collection ERROR** (see §4/F1) — pre-existing; not fixed (would require path-code changes) |
| C3 | Reconciliation script | `python3 scripts/fv_f_reconcile.py` | **EXIT=0**; 32 reconciliation rows; **0 DISAGREEMENT** rows (REPRODUCED/RECONCILED/CORRECTED/VERIFIED/RESOLVED/SUPERSEDED/NEW EVIDENCE as recorded in `f_reconciliation.md`) |
| C4 | 410-value baseline check | `phase_a_baseline.py` re-run (backup taken first) | **410/410 match, 0 mismatch, 0 missing**; largest \|diff\| 7.47e-07; all four output CSVs and `phase_a_log.md` **byte-identical** to pre-run copies |
| C5 | 88 fast-path e2e checks | `phase_b_improvement.py` re-run (log: `phase_b_rerun_20261020.log`) | **88/88 PASS** re-executed (48 gray + 40 RGB); equivalence A **4/4 bitwise-identical**; equivalence B **8/8** stego/extract/recover identical; `fast_validation_gray.csv` + `fast_validation_rgb.csv` **byte-identical** to pre-run copies |
| C6 | Programmatic self-audit | `review_audit.py` re-run (twice, incl. final state) | **51/51 PASS**; `review_audit.md` byte-identical after re-run |
| C7 | Checkpoint hashes vs Table 3 / §6.4 info | `sha256sum models/*.pth` vs `Final_report.md` §6.4 | **5/5 prefixes match**: v4 `a9021862c753e11b`, v1 `51406640acaf6f37`, v2 `173f462155c1075d`, v3 `1fa025e252d5a3c9`, v5 `e6996df5f942fca9` |
| C8 | Parameter counts / architecture | `load_model()` (prints patch/residual/params), `tests/test_cnn_checkpoints.py`, `b3_ablation_params.csv`, independent formula re-derivation from state dicts | **5/5 match**: 46,881 / 112,417 / 112,353 / 112,417 / 210,721. Formula (K=32 convs+BN+optional 1×1 residual+FC head) == checkpoint parameters for all five; raw tensor-element counts exceed these by exactly 130 BN running-stat buffer entries (not parameters) |
| C9 | Table 3 (complexity) regeneration | `python3 src/comp.py` | **Crashed** with `KeyError: 'Mean(ms)'` against the actual runtime CSV schema → minimal fix applied (§5) → **regenerated successfully** to `results/complexity/` (see §3) |
| C10 | Rendered-table verification (Tables 1–10) | programmatic extraction of every numeric cell of Final_report §8.1–§8.10 vs `b2_*`, `b3_*`, `e_runtime_*`, `d_*`, `results/runtime/runtime_results.csv` | **0 mismatches** (checked at each table's printed precision: 4 dp for Tables 1–8, 1 dp for Table 9 CNN rows / 3 dp for Table 9 classical rows, 1 dp for Table 10). Re-run after all edits: identical result |
| C11 | Table 8 / per-channel CNN entries | vs `b2_rgb_per_channel.csv` +4 corroborating raw sources | **verified — see §2** |
| C12 | Section-3 validation | `bash validate_section3.sh` | **9/10 OK**; the single FAIL (lower-bit equation "missing") is the documented check-script escaping false positive — equation confirmed present by fixed-string search (`Section_3_Updated.md:433`). Script exit=1 for this reason only (see F2) |
| C13 | Receiver payload-length reproduction | `python3 repro_receiver_payload_len.py` | **EXIT=0**: empty/short/full/over-capacity cases — image exact, extraction length-correct |
| C14 | Legacy receiver regression test | `python3 RDHEI_FIXED_V1/test_receiver_fix.py` | **EXIT=0**: all payload-length cases `image_exact=True payload_exact=True` |
| C15 | Dataset inventory hashes | `dataset_inventory.csv` SHA-256 vs actual files in `../data/` | **12/12 match** (6 gray + 6 color-dir files; `images.png` correctly flagged mode L / excluded) |
| C16 | Training-config claims (§6.3) | `src/train.py` inspection | **matches report**: `PATCH=5` (⇒ the disclosed provenance gap is real), α=2.0 weighted L1, Adam lr 1e-4 wd 1e-4, CosineAnnealing(T_max=epochs, eta_min=1e-6), batch 256, stride 4, flips, seed 42, 20 epochs, 10% val split. `../data/train` contains exactly **200 `.pgm`** files (report claim correct) |
| C17 | Cryptographic workflow claims | `src/encryption.py`, `src/rdhei_color.py`, `fv_e_runtime.py` | **matches report**: AES-CTR, 128-bit counter, per-channel nonces `base+c+1`, validation runs use 32-byte (256-bit) keys, `pack_metadata` covers (base_nonce, key_size) only |
| C18 | Recovery-claim counts (§10) | `d_e2e_gray.csv` (84 PASS + 1 DOCUMENTED), `d_e2e_rgb.csv` (40 PASS), `d_variants_gray/rgb.csv` (30 + 25 PASS) | **180 = 179 valid PASS + 1 documented over-capacity** exactly as stated; gray capacity ranges match §10.2 (MED 1,107,311–5,217,367; CNN 1,194,751–5,354,348) |
| C19 | Security/limitation overclaim scan | `Final_report.md` §12/§15/§16, `Section_3_Updated.md` | **no overclaims found**: no authenticated-encryption, no blind/ciphertext-only, no real-time, no universal-superiority claims; bibliography honestly absent (no `.bib` anywhere; entries marked TO BE VERIFIED, none fabricated) |
| C20 | Source-consistency (62/62) and rendered-table (109/109) checks | greps across workspace for the counts/scripts | **not found in this workspace** — the manuscript, `CNN_RDHEI_table_fix.zip`, and those check scripts are not present. Equivalent coverage performed instead: C10 (all rendered tables vs sources), C3, C6. Recorded as unresolved (F3), **not** claimed as passed |
| C21 | Final repository status / diff | `git status`, `git diff`, `git log` | see §5.4 — workspace untracked inside the parent repo; only tracked modification is a **pre-existing** 2-line receiver-fix diff in `../src/rdhei_core.py` (outside this workspace, untouched); no commits made |

---

## 2. Table 8 reconciliation (CNN red-channel, image 4.2.06: 4.5647 vs 4.5648)

**Verdict: RESOLVED — the correct four-decimal value is `4.5648`; `4.5647` is a truncation
of the same raw measurement, not an alternative measurement.**

Authoritative raw values (all independent artifacts agree):

| Source | Value |
|---|---|
| `results/final_validation_20261018/b2_rgb_per_channel.csv` (row `4.2.06.png,CNN3x3,R`) | **4.564750671** (MAE 7.686001, capacity 1,196,622 bits) |
| `results/raw/per_image_rgb.csv` | 4.564750671386719 |
| `results/rgb_complexity_error_analysis_20261019/rgb_per_channel_comparison.csv` and `prediction_error_statistics.csv` | 4.564750671386719 |
| `results/rgb_audit_20261013T100000/rgb_per_image_per_variant.csv` / `rgb_audit2_log.txt` (independent 10-13 audit run) | 4.564751, `bpp=4.564751 cap=1196622` |
| `baseline_reconciliation.csv` (fresh recomputation vs stored) | 4.564750671 vs 4.564750671, diff 3.87e-10, **match** |

Rounding: 4.564750671 → **4.5648** at 4 decimals (digits beyond the 4th are `50671…` > half
of 10⁻⁴). Truncation at 4 decimals yields 4.5647 — which explains the disputed manuscript
value.

All 15 per-channel CNN entries of the channel-wise table (and their row means) were verified
against `b2_rgb_per_channel.csv`: **0 mismatches**. `Final_report.md` §8.5 already carries
4.5648.

**Note:** the manuscript file containing "Table 8" (and the `CNN_RDHEI_table_fix.zip`) is not
in this workspace, so the manuscript cell itself could not be edited here. Claude should
set 4.2.06 / red / CNN to **4.5648** and check whether other cells were produced by
truncation instead of rounding (every other entry of this table verified correct).

---

## 3. Runtime and model-complexity reconciliation

### 3.1 Predictor-only runtime (ms)

- **Protocol (all three measurement sets):** Lena.png 512×512 grayscale, CPU device,
  warm-up 5, 10 timed repeats, `time.perf_counter` per full prediction map, model loading
  excluded; arithmetic mean/std over the 10 runs; unit = **milliseconds**.
- **2026-10-13 artifact:** `results/runtime/runtime_results.csv` + `runtime_report.txt`
  (protocol, host, Python/torch versions all recorded there).
- **2026-10-18 fresh run:** `results/final_validation_20261018/e_runtime_predictor.{csv,md}`
  produced by `scripts/fv_e_runtime.py` (protocol in the script header). Every number in
  `Final_report.md` §8.9 "fresh" column equals this CSV exactly (MED 6.709, GAP 21.254,
  CALIC 13.119, CNN-3×3 1,707.3, CNN-5×5 5,484.8, NoResidual 3,466.3, NoWeighted 4,573.0,
  CNN-7×7 8,518.9); the "artifact" column equals `runtime_results.csv` exactly
  (6.217 / 20.025 / 14.628 / 1,763.4 / 3,952.1 / 3,556.0 / 3,996.7 / 7,237.0).
- **2026-10-19 run (Phase D):** `runtime_summary.csv`/`runtime_raw.csv` +
  `runtime_meta.txt` (WSL2, CPU, Python 3.10.12, torch 2.14.0). Every number in
  `RGB_Complexity_Error_Analysis.md` §7 equals this CSV (6.40 / 20.33 / 10.97 / 2,082.2 /
  3,257.7 / 5,320.8 / 6,184.6 / 15,623.4 / vectorized 1,761.1).
- The two reports explicitly **do not pool** cross-day numbers; ordering and magnitudes
  agree (1,707 vs 1,763 vs 2,082 ms for CNN-3×3 — same protocol, laptop-class load/thermal
  variation).
- **Historical manuscript values** (11.578 / 46.368 / 32.844 / 2,877.455 / … 13,636.553 ms):
  confirmed present **only** in disclosure records ("not traceable", "superseded"); no
  artifact in the repository contains them. They remain **superseded and must not be used**.

### 3.2 End-to-end and stage-level timings

- `Final_report.md` §8.10 = `e_runtime_e2e.csv`/`.md` exactly (4 rows). Stage split in
  `fv_e_runtime.py`: `prepare` (content_owner_prepare) | `embed+encrypt`
  (sender_embed_encrypt) | `decrypt+extract+recover` (receiver_extract_recover);
  `total = sum of the three`; 3 repeats; RGB aggregated over 3 channels with nonces 1/2/3;
  payload = full capacity. Boundaries verified as disjoint in the code.
- Stage-level provenance (the finer split quoted in `RGB_Complexity_Error_Analysis.md` §7):
  `phase_d_runtime.py` header defines disjoint boundaries
  `label_map | embed | encrypt | decrypt | extract+recover | TOTAL` (embed = pixel loop
  only, encrypt/decrypt = AES only, extract+recover = receiver loop only), 3 repeats,
  full-capacity payloads; output `runtime_summary.csv`. All quoted totals reproduce exactly
  (Airplane MED 4,665.7 → 1,622.0 fast; Airplane CNN 8,044.3; 4.2.03 MED 7,803.0;
  4.2.03 CNN 15,504.5 → 10,317.4 fast; AES ≤ 4 ms).
- **Predictor-only vs full pipeline are clearly distinguished** in both reports:
  predictor-only = one prediction map (ms); full pipeline = predict + label map + MSB
  embed + AES-CTR + decrypt + extract + recover (seconds; dominated by Python per-pixel
  loops — e.g., recovery = 75% of Airplane-MED total). No real-time claim exists.

### 3.3 Parameter counts and MACs/FLOPs

- Parameter counts verified three ways (checkpoint load, `b3_ablation_params.csv`,
  independent formula re-derivation): **46,881 / 112,417 / 112,353 / 112,417 / 210,721** —
  consistent with §6.4 hashes and Section-3 Table 1.
- MACs are reliable because the architecture is fully known and verified
  (K=32; conv1 1→32 3×3, conv2 32→32 3×3, optional 1×1 residual projection, FC
  K·P²→128→1): per-patch MACs **122,816 (P=3) / 340,928 (P=5, residual) /
  340,128 (P=5, no-residual) / 668,096 (P=7)** — re-derived in this pass and equal to
  `complexity_analysis.md` §C2 and `review_audit.md` rows 45–51.
- `src/comp.py` (the "Table 3" producer) was **broken** against the repository's own
  runtime CSV (schema mismatch, `KeyError: 'Mean(ms)'`) and had never been run here — a
  concrete defect (also flagged as risk A16 in `sec3_deliverable_a_implementation_audit.md`).
  After the minimal fix (§5), Table 3 regenerates: `results/complexity/complexity_report.txt`
  / `complexity_results.csv` (+3 figures), runtime column sourced from
  `runtime_results.csv`, "Approx FLOPs" = 2×MACs per patch via the in-script analytic path
  (`ptflops` not installed → documented fallback): CNN-3×3 **245,632**; 5×5 **681,856**;
  NoResidual **680,256**; NoWeighted **681,856**; 7×7 **1,336,192** — all exactly 2× the
  verified MACs.
- Caveats kept explicit: comp.py's classical "Approx FLOPs" (9/18/38) are hard-coded
  per-pixel constants, and CNN FLOPs are per-patch (= per-pixel, since the model runs once
  per pixel); these are per-pixel-scale figures, not whole-image counts. Whole-image cost is
  Θ(H·W·…) as stated in `complexity_analysis.md`.
- One corrected report sentence: §8.9's "2.0× (5×5)" was wrong — fresh means give
  5,484.8/1,707.3 = **3.2×** (no-residual 2.0×, no-weighted 2.7×, 7×7 5.0× were correct).

---

## 4. Test results (including failures and skipped tests)

- `python3 -m pytest tests/ -q` → **16 passed, 11 warnings, 0 failed, 0 skipped** (before
  and after this pass's edits).
- `python3 -m pytest -q` at project root → **1 collection error, 0 tests run**:
  `tests/test_smoke.py` fails to import `encrypt_rgb_channels` because previously-collected
  `RDHEI_FIXED_V1/test_receiver_fix.py` / `scripts/rgb_variant_test.py` insert the hard-coded
  path `/home/parzifal/RDHEI_Project` (the pre-repair parent tree) at `sys.path[0]`, so
  `src.encryption` resolves to the parent's older copy. Pre-existing; **not fixed** (that
  would be changing code to make a test run; the designated suite is `pytest tests/`, which
  passes). Recorded as unresolved F1.
- `RDHEI_FIXED_V1/test_receiver_fix.py` (run directly) → EXIT=0, all cases exact.
- `repro_receiver_payload_len.py` → EXIT=0.
- `validate_section3.sh` → 9 OK / 1 FAIL / exit 1; the FAIL is the known escaping false
  positive (equation present, verified by fixed-string grep at line 433; also documented in
  `final_section3_validation.md`). Not modified — the check script, not the file, is wrong.
- No test was skipped, weakened, or xfailed; no retraining was performed.

---

## 5. Files changed and reasons

All changes are inside this workspace; pipeline source (`src/rdhei_core.py`,
`src/rdhei_color.py`, `src/encryption.py`, `src/predictor.py`, `src/baselines.py`,
`src/cnn_model.py`), checkpoints, and datasets were **not** touched.

| File | Change | Reason (evidence) |
|---|---|---|
| `src/comp.py` | `load_runtime_results()`: accept `Mean(ms)` **or** `Mean_ms`; map runtime labels (`CNN-3x3 (v4_patch3)` → table names) via `_DISPLAY`/`_norm_method`. No other behavior change. | Script crashed (`KeyError: 'Mean(ms)'`) against the actual `results/runtime/runtime_results.csv`; source evidence = the CSV header vs the script's expected schema. Enables Table 3 regeneration (A16) |
| `Final_report.md` §8.9 | "2.0× (5×5)" → "3.2× (5×5)" + spelled-out ratios | `e_runtime_predictor.csv`: 5484.8/1707.3 = 3.21; the other three ratios in the sentence were correct |
| `Final_report.md` §8.6 | Weighted-loss direction corrected ("both help" → residual helps; plain-L1 v3 slightly beats weighted-L1 v1 on gray, with provenance caveat) | `ablation_summary.csv` + `b3_ablation_gray.csv`: v3 5.1727/4.5130 vs v1 5.1653/4.5244 |
| `Final_report.md` §11 | Weighted-loss sentence direction corrected (v3 exceeds v1 by ~0.007/~0.017 bpp and has ~0.06 *lower* RGB MAE) | `b3_ablation_rgb.csv`: v3 4.8537/6.7637 vs v1 4.8372/6.8238; magnitudes unchanged |
| `Section_3_Updated.md` (3 spots: §3.2.2 bullet, Table 1 row, §3.7.1) | "full/proposed" designation of CNN-5×5 → "full reference configuration"; CNN-3×3 named the proposed configuration | Contradiction with the authoritative record (`Final_report.md` §1 "proposed configuration is CNN-3×3"; `RGB_Complexity_Error_Analysis.md` §4 "CNN-3×3 stays the proposed configuration") and with the evidence (CNN-3×3 wins both benchmarks and is the smallest). Original draft `sec3_deliverable_b_section3_manuscript.md` preserved unchanged |
| `CHANGELOG.md` | New "Technical closure pass — 2026-10-20" entry | Record every change (required by the task) |
| **New outputs** | `results/complexity/` (5 files, Table 3 regeneration); `phase_a_rerun_20261020.log`; `phase_b_rerun_20261020.log`; `pre_closure_backup_20261020/` (pre-run SHA-256 + byte-copies of every file the re-run scripts overwrite, plus the rerun's `improvement_experiments_rerun_20261020.csv`) | Reproducible evidence of this pass; originals preserved |
| **Restored** | `improvement_experiments.csv` — re-run overwrote only its 5 load-dependent timing rows; original restored (it is the record cited by `RGB_Complexity_Error_Analysis.md` §4/§7); rerun copy archived | Preserve original evidence; both retained |
| Unchanged (verified byte-identical after re-runs) | `baseline_reconciliation.csv`, `rgb_per_image_comparison.csv`, `rgb_per_channel_comparison.csv`, `gray_per_image_comparison.csv`, `phase_a_log.md`, `fast_validation_gray.csv`, `fast_validation_rgb.csv`, `review_audit.md` | Deterministic re-execution confirms stability |
| `FINAL_CLOSURE_REPORT.md` | This file | Required deliverable |

**Git:** repository root is the parent `/home/parzifal/RDHEI_Project` (2 commits, 5 tracked
`src/*.py` files). This workspace appears as untracked `?? RDHEI_FIXED_V1/` (44 status
entries before and after; all new files land inside that single entry). The only tracked
modification is `../src/rdhei_core.py` — a **pre-existing** uncommitted 2-line deletion of
the premature-`payload_len` break (the receiver fix), outside this workspace, untouched.
No commits, no pushes.

---

## 6. Resolved vs remaining unresolved issues

### Resolved in this pass
1. **Table 8 red-channel discrepancy** → 4.5648 (5 raw sources agree; §2).
2. All rendered report tables (Tables 1–10) verified cell-by-cell against source CSVs — 0 mismatches.
3. Predictor-only and stage-level runtime provenance traced end-to-end (scripts, protocols, units, image dims, host env); historical manuscript runtimes confirmed untraceable → superseded.
4. Parameter counts and MACs/FLOPs verified from architecture and checkpoints; Table 3 producer repaired and Table 3 regenerated (`results/complexity/`).
5. §8.9 CNN-family ratio error (2.0× → 3.2× for 5×5) corrected.
6. §8.6/§11 weighted-loss direction error corrected (plain-L1 checkpoint is the better one on all four metrics).
7. Manuscript Section-3 "CNN-5×5 (full/proposed)" wording corrected to keep CNN-3×3 as the proposed configuration.
8. All executable checks re-run after edits: pytest 16/16, Phase A 410/410, fast-path 88/88, self-audit 51/51, reconciliation 0 disagreements, dataset hashes 12/12, checkpoint hashes 5/5.

### Remaining unresolved (clearly separated)
1. **F1 — root-level `pytest -q` collection error** caused by hard-coded absolute paths
   (`/home/parzifal/RDHEI_Project`) in `RDHEI_FIXED_V1/test_receiver_fix.py`,
   `RDHEI_FIXED_V1/audit_day1*.py`, `scripts/rgb_*.py`, `scripts/gate1_*.py`,
   `scripts/test_v4_v5.py`/`test_v5_only.py`, `scripts/short_payload_rgb_test.py`.
   These also mean those legacy scripts import the *pre-repair* parent `src/` when run
   standalone. Not fixed here (would be code changes beyond the closure scope's "do not
   modify code merely to make tests pass"; the designated suite `pytest tests/` passes).
2. **F2 — `validate_section3.sh` exits 1** on a regex-escaping false positive in the
   check itself; the equation is present (line 433). The script was not modified.
3. **F3 — manuscript-side tooling absent:** the manuscript with Tables 5–8, the
   `CNN_RDHEI_table_fix.zip`, and the reported 62/62 source-consistency and 109/109
   rendered-table check scripts do not exist in this workspace (searched; not found).
   Those reported statuses could **not** be re-executed and are **not** claimed verified
   here; equivalent coverage is C10 + C3 + C6. The Table 8 value (§2) must be applied to
   the manuscript by Claude, ideally with a truncation-vs-rounding sweep of its tables.
4. **F4 — training provenance unverifiable** (BOSSBase 10k/20 epochs user-confirmed only;
   `src/train.py` as written can only train 5×5; v3's plain-L1 label depends on
   unrecorded training history). Honest disclosure retained (now also noted in corrected §11).
5. **F5 — dataset provenance unverified** (no manifest/license; USC-SIPI-style naming only).
6. **F6 — bibliography absent**; placeholders marked TO BE VERIFIED (nothing fabricated).
7. **F7 — `complexity_analysis.md` references `phase_c_run.log`, which does not exist**
   in the artifact directory (the same checks live in `review_audit.md` and were
   independently re-executed in this pass — all pass). Provenance gap noted, file not fabricated.
8. **F8 — independent-model review unavailable** (self-audit disclosed in both reports; unchanged).
9. **F9 — workspace is untracked** in the parent git repository; the pre-existing
   2-line diff in `../src/rdhei_core.py` remains uncommitted outside this workspace.
10. **F10 — timing rows are load-sensitive:** the 2026-10-19 `improvement_experiments.csv`
    timing row for the CNN predictor was already flagged superseded in
    `RGB_Complexity_Error_Analysis.md` §7; this pass's re-run produced different timing
    rows again (e.g., RGB recover speedup not reproduced under this run's conditions).
    Original evidence preserved; rerun archived; acceptance/equivalence rows were
    byte-identical. Timing claims should continue to rely on the controlled
    `e_runtime_*`/`runtime_summary.csv` protocols, not this file.

---

## 7. Final status

# READY WITH DISCLOSED LIMITATIONS

Rationale: every in-workspace check executed in this pass passed (16/16 tests, 410/410
baseline values, 88/88 fast-path cases, 51/51 self-audit rows, 0 table mismatches,
hashes and counts verified), the Table 8 discrepancy is resolved with source evidence
(4.5648), runtime and complexity are fully traced, and the three defects found
(comp.py schema breakage; two direction/ratio errors in `Final_report.md`; the
proposed-configuration wording in Section 3) were corrected with evidence and recorded.
The status is not "READY FOR MANUSCRIPT UPDATE" without conditions because the manuscript
and its 62/62 and 109/109 check tooling are absent from this workspace (F3), the root-level
pytest collection quirk and check-script false positive remain (F1/F2), and the inherited
limitations — training/dataset provenance, missing bibliography, superseded historical
runtimes, absent independent review — persist as honestly disclosed (F4–F8).
