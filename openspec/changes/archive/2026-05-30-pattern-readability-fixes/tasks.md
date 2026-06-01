## 1. F3 — Terminal closure + stuffing for every 3D part (backend/grammar.py)

- [x] 1.1 In `compile_part_detailed`, track whether the existing early-break fasten-off fired (a `closed` flag); after the round loop, if `closed` is false AND `primitive_type != "flat_disc"`, append the terminal closure block
- [x] 1.2 Closure block — closed tip (last actual round count ≤ 6): emit `Stuff firmly.` then existing `sl st to first st, fasten off` (tapered path); for open-end ≤ 6 case use the same close-and-cinch
- [x] 1.3 Closure block — open end (last actual round count > 6): emit `Stuff before sewing.` then `Fasten off, leave a long tail for sewing.`
- [x] 1.4 Leave `flat_disc` untouched by this block (it has its own `Do NOT stuff. Sew flat.` ending)

## 2. F4 — Shaped flat_disc rows + make-2 (backend/grammar.py)

- [x] 2.1 Add `_PLURAL_PAIRED = {"ears","eyes","wings","fins"}` and `_singularize_and_make2(name) -> (display_name, needs_make2)`
- [x] 2.2 Rewrite `_compile_flat_disc(name, target_diameters)`: per-row widths from `round(d*π/w/2)` (halved formula), singularize + `(make 2)`, foundation+Row1, edge-shaped rows via `_flat_row_body(prev, new)` helper (handles even/odd Δ, splits between left/right edges), end `Do NOT stuff. Sew flat.`
- [x] 2.3 No existing flat_disc grammar tests to update (only test_geometry.py existed); new behavior covered by tests in Group 4

## 3. F2 — Surface readable CP DSL from the seamless endpoint (backend/external_tools.py + main.py + frontend)

- [x] 3.1 In `run_remesher`, after loading the pattern JSON, return a dict with `text` = `data["crochetparade"]` if present/non-empty, else fall back to `json.dumps(data)`; include `stitch_count` and `format` ("crochetparade-dsl" or "raw")
- [x] 3.2 Compute stitch count from `traversals[*].sequence` lengths, excluding -7 yarn-start markers (approximate; cheap)
- [x] 3.3 `seamless.generate` returns the same dict shape; `/generate-seamless` builds `{"pattern": result["text"], "stitch_count": ..., "format": ...}` (keeps existing `pattern` field for backward compat)
- [x] 3.4 Frontend `generateSeamless()` renders a framing intro paragraph (one-piece + sewing edges, stitch count, paste into crochetparade.org link) before the `<pre>`

## 4. Tests

- [x] 4.1 Grammar: terminal closure on a cylinder Leg [8]×6 — `Stuff before sewing.` + leave-tail line present, doesn't end on a bare round
- [x] 4.2 Grammar: terminal closure on a capsule Arm ending at [12]
- [x] 4.3 Grammar: tapered sphere still ends with `sl st to first st, fasten off`, preceded by `Stuff firmly.`
- [x] 4.4 Grammar: `flat_disc [1,3,5]` widens row-by-row (Row 2 has "2 sc in", w2 > w1)
- [x] 4.5 Grammar: `flat_disc [1,3,5,5,3,1]` widens then tapers (sc2tog appears, widths grow then shrink)
- [x] 4.6 Grammar: `"Ears"` → `--- EAR ---` + `(make 2)`; `"Hat Brim"` gets neither
- [x] 4.7 External tools: `run_remesher` returns `crochetparade` DSL when present (synthetic JSON fixture, subprocess stubbed)
- [x] 4.8 External tools: falls back to JSON dump when DSL absent or empty (format=raw, non-empty text)
- [x] 4.9 Full pytest: 47 passed (34 existing + 13 new). Bonus: stitch_count test verifies yarn markers excluded

## 5. Manual verification (live server, fox.jpg)

- [x] 5.1 Verified: all 6 fox parts (Head/Body/Arms/Legs/Tail) end with stuffing line + fasten-off/sewing-tail; Head closes tapered, open tubes get sewing-tail variant
- [x] 5.2 Verified: flat_disc Ear shows shaped widening rows (`2 sc in each of first N sts, sc across to last N sts, 2 sc in each of last N sts`) instead of a rectangle. (LLM returned singular "Ear" so no make-2 fired — that's correct per the conservative detection; unit test covers the plural case.)
- [x] 5.3 Verified: `/generate-seamless` returns `{"format":"crochetparade-dsl","stitch_count":54,"pattern":"COLOR: rgb…\\nDEF:scdec=…\\nDEF: scinc=sc@[@]…"}` — the readable DSL, not raw op-tokens. Frontend framing header renders for `format=="crochetparade-dsl"`.
- [x] 5.4 All three QA findings (F2/F3/F4) resolved end-to-end
