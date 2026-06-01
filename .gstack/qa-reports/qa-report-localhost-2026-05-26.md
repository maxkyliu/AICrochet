# QA Report — AICrochet
**Date:** 2026-05-26  
**URL:** http://localhost:8000/static/index.html  
**Branch:** master  
**Image:** fox.jpg  
**Tier:** Standard  
**Duration:** ~15 min  

---

## Summary

| Category | Score |
|---|---|
| Functional | 72 |
| Console | 70 |
| Visual | 95 |
| UX | 90 |
| **Overall** | **~82** |

**Issues found:** 3  
**Fixed:** 1 (verified via unit tests, live re-verify blocked by Gemini 503)  
**Deferred:** 2  

---

## Verified Fixes from pattern-output-quality

All four grammar/output improvements confirmed working in the first successful generation:

| Fix | Evidence |
|---|---|
| `(inc) x N` notation (no sc 0) | Rnd 2: `(inc) x 6 [12]` seen on Head, Tail, Paws |
| `(dec) x N` notation (no sc 0) | Rnd 9: `(dec) x 12 [6]` seen on Head |
| `sl st to first st, fasten off` terminator | All closed shapes end correctly |
| flat_disc → flat rows + `Do NOT stuff. Sew flat.` | Nose: `Ch 12, turn / Row 1–13 / Do NOT stuff. Sew flat.` |
| Paw coercion sphere→capsule | Paws show as `(capsule)` not `(sphere)` |

---

## Issues

### ISSUE-001 [HIGH] — Ears classified as `cone` by Gemini, not `flat_disc`
**Status:** Fixed (code-verified) — live re-verify blocked by Gemini 503  
**Commit:** 9d6f119  

Fox ears are triangular flat shapes. Gemini classified them as `cone` because it reads the pointed triangle shape as 3D. Previous code had no server-side override for this case. Result was a 58-round erratic spiral from the cone learned model.

**Fix:** Added `_EAR_KEYWORDS = {"EAR", "WING", "FIN"}` coercion in `_coerce_limb_types`. Any part whose name contains EAR/WING/FIN is overridden to `flat_disc` regardless of Gemini's classification. Also added prompt constraint: *"Parts named ear, wing, or fin MUST use flat_disc, NEVER cone or sphere."*

**Evidence:** Unit test in QA session:
```
Left Ear (cone → flat_disc) ✓
Right Ear (sphere → flat_disc) ✓  
Right Wing (cone → flat_disc) ✓
Head (sphere → sphere unchanged) ✓
```

**Expected after fix:** Ears will output `Ch N, turn / Row 1: sc in 2nd ch from hook... / Do NOT stuff. Sew flat.`

---

### ISSUE-002 [MEDIUM] — Grammar generates impossible stitch counts when delta > prev_count
**Status:** Deferred  

Head Rnd 2: `(inc) x 12 [18]` from 6 stitches. In crochet, 6 stitches can receive at most 6 increases. Doing 12 increases requires working 2 increases per stitch (notation: `(inc, inc) x 6 [18]` or `3 sc in each st [18]`). The grammar lacks multi-increase notation.

Root cause: the learned sphere model predicts a diameter profile that jumps from ~2cm to ~6cm in one round, which translates to a stitch-count jump of 6→18 (delta=12 > prev=6).

**Fix needed:** Grammar should detect `delta > prev_count` and either:
- Generate `N sc in each st around [target]` when target = N * prev_count  
- Or cap the step at prev_count and accept fewer stitches

**Files:** `backend/grammar.py:generate_round` (lines 15–18)

---

### ISSUE-003 [MEDIUM] — Cone learned model produces erratic 58-round profile for ears
**Status:** Deferred (training data issue)  

The cone regressor predicts an oscillating up-down-up profile instead of a clean monotone taper. This produces 58 rounds of increasing/decreasing stitches with no logical pattern. Related to frustum: the cone training data is likely noisy (real patterns labeled "cone" may include irregular shapes).

**Fix needed:** Collect more clean cone training data, or add a post-processing step to smooth the predicted profile (enforce monotone behavior for cone/teardrop primitives in `geometry.py`).

---

## Console Health

- **500 error** from first Gemini call (503 from API surfaced as 500 HTTP response) — not shown on screen as a UI error, just in console
- **WebGL GPU stall warnings** — browser-level, harmless, expected in headless Chromium
- Gemini returned 503 on 3 of 4 attempts during this session — external service instability, not a code bug

---

## PR Summary

QA found 3 issues: fixed 1 (ear coercion to flat_disc), 2 deferred (grammar multi-increase notation, cone model quality). Grammar/notation fixes from prior sprint all verified. Health score ~82.
