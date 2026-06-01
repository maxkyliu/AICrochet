## 1. Grammar Notation Fix

- [x] 1.1 In `backend/grammar.py` `generate_round`: fix increase branch — when `interval == 1`, emit `(inc) x {delta} [{target_count}]` instead of `(sc 0, inc) x {delta}`
- [x] 1.2 In `backend/grammar.py` `generate_round`: fix decrease branch — when `interval - 2 <= 0`, emit `(dec) x {delta_abs} [{target_count}]` instead of `(sc 0, dec) x {delta_abs}`

## 2. Grammar Terminator

- [x] 2.1 In `backend/grammar.py` `compile_part`: after emitting each round, check if `current <= MIN_STITCHES` (6) and the profile was decreasing; if so, append `sl st to first st, fasten off` and break out of the round loop
- [x] 2.2 Verify that flat profiles (cylinder) with stitch count above minimum do not trigger early termination

## 3. primitive_type Routing in compile_part

- [x] 3.1 Add `primitive_type: str = "sphere"` parameter to `compile_part` signature in `backend/grammar.py`
- [x] 3.2 Update `main.py` to pass `part["type"]` (or equivalent) as `primitive_type` in each `grammar.compile_part(...)` call

## 4. flat_disc Flat-Row Construction

- [x] 4.1 In `backend/grammar.py`, add `_compile_flat_disc(self, name, target_diameters)` method that generates chain foundation + flat rows
- [x] 4.2 In `compile_part`, dispatch to `_compile_flat_disc` when `primitive_type == "flat_disc"`
- [x] 4.3 Verify flat_disc output starts with `Ch {width+1}, turn`, uses `Row N:` labels, ends with `Do NOT stuff. Sew flat.`, and contains no `magic ring`

## 5. Gemini Prompt + Server-Side Limb Coercion

- [x] 5.1 Update `GEMINI_PROMPT` in `backend/main.py` to add explicit rule: parts named arm, leg, paw, or flipper MUST use `capsule` or `cylinder`, never `sphere`
- [x] 5.2 In `backend/main.py` dependency graph builder, add coercion: if `part["type"] == "sphere"` and `part["name"].upper()` matches `ARM|LEG|PAW|FLIPPER`, override `type` to `"capsule"`
