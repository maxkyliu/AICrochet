## Why

QA testing revealed four output quality bugs: the grammar emits dead rounds after a shape closes, uses malformed stitch notation `(sc 0, inc)`, generates magic-ring construction for flat ears that should be worked in flat rows, and Gemini misclassifies stubby limbs as sphere instead of capsule/cylinder.

## What Changes

- Fix grammar terminator: stop emitting rounds once stitch count reaches minimum (6), append `sl st to first st, fasten off`
- Fix stitch notation: `(sc 0, inc) x N` → `(inc) x N`; `(sc 0, dec) x N` → `(dec) x N` when interval == 1
- Pass `primitive_type` through `compile_part()` so construction method can vary by shape
- `flat_disc` construction: chain foundation + back-and-forth flat rows instead of magic ring spiral; append `Do NOT stuff. Sew flat.`
- Gemini prompt: add explicit rule that parts named arm/leg/paw/flipper must be `capsule` or `cylinder`, never `sphere`
- Server-side coercion: if part name matches limb keywords and Gemini returns `sphere`, override to `capsule`

## Capabilities

### New Capabilities
- `grammar-terminator`: grammar closes parts correctly with sl st + fasten off once minimum count is reached
- `stitch-notation`: stitch instruction strings are always valid (no `sc 0` terms)
- `flat-disc-construction`: flat_disc parts use chain + flat-row construction instead of magic-ring spiral
- `primitive-type-routing`: `compile_part` receives and uses `primitive_type` to select construction method

### Modified Capabilities
- `primitive-labeler`: Gemini prompt and server-side coercion ensure limb parts are never classified as sphere

## Impact

- `backend/grammar.py`: `generate_round`, `compile_part` — core changes
- `backend/main.py`: `GEMINI_PROMPT` string, dependency graph builder (coercion logic)
- No database schema changes, no new dependencies
