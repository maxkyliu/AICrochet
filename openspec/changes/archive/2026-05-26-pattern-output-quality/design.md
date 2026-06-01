## Context

`CrochetGrammar` in `backend/grammar.py` converts diameter profiles (lists of floats) into row-by-row stitch instructions. Currently it has three correctness bugs: (1) it emits rounds indefinitely even after a shape closes to its minimum stitch count, producing 30-50 dead `sc in each st around [6]` rounds; (2) when `delta == prev_count` (increase every stitch), it emits `(sc 0, inc) x N` which is invalid notation; (3) `compile_part()` has no `primitive_type` parameter, so all shapes get the same magic-ring spiral construction regardless of geometry.

Gemini's vision prompt in `backend/main.py` does not constrain limb part types, causing stubby arms and legs to be classified as `sphere` instead of `capsule`/`cylinder`.

## Goals / Non-Goals

**Goals:**
- Grammar closes parts cleanly with `sl st to first st, fasten off` once stitch count hits minimum
- Stitch instructions never contain `sc 0` terms
- `flat_disc` parts output chain + flat-row instructions, not magic-ring spiral
- `compile_part` accepts `primitive_type` and routes to appropriate construction logic
- Limb parts reliably classified as `capsule` or `cylinder`

**Non-Goals:**
- Not changing the diameter profile generation or learned model
- Not adding new primitive types
- Not changing the UI or API surface
- Not rewriting the full grammar engine

## Decisions

**D1: Terminator via stitch-count floor, not profile length**

Stop emitting rounds when `target_count <= MIN_STITCHES` (6) and the shape is decreasing. Emit `sl st to first st, fasten off` as the final line. Alternative considered: truncate the profile upstream in `GeometryEngine`. Rejected because grammar should be robust to any profile and the fix is cleaner as a grammar concern.

**D2: Notation fix in `generate_round` using interval check**

When `interval == 1` (every stitch is an increase), emit `(inc) x {delta}` instead of `(sc 0, inc) x {delta}`. Same logic for decreases: when `interval - 2 == 0`, emit `(dec) x {delta_abs}`. This is a targeted one-liner fix with no structural change.

**D3: `compile_part` gains optional `primitive_type` parameter (default `"sphere"`)**

Adding a parameter is backward-compatible. Callers in `main.py` pass the type explicitly. Inside `compile_part`, dispatch to `_compile_flat_disc()` for `flat_disc`, else use existing spiral logic. No inheritance or class hierarchy needed.

**D4: `flat_disc` construction uses chain foundation + flat rows**

Flat ears/fins are worked back and forth, not in spiral rounds. Pattern:
```
Ch {width+1}, turn
Row 1: sc in 2nd ch from hook, sc across [{width}]
Row 2-N: Ch 1, turn, sc in each st across [{width}]
Fasten off. Do NOT stuff. Sew flat.
```
Width is derived from `max(target_counts)`. Rows use the diameter profile length. Alternative: separate `CrochetGrammar` subclass. Overkill for one shape type.

**D5: Gemini prompt gets explicit limb constraint + server-side coercion**

Add to `GEMINI_PROMPT`: "Parts named arm, leg, paw, or flipper MUST use `capsule` or `cylinder`, never `sphere`." Also add server-side coercion in the dependency-graph builder: if `name.upper()` matches limb keywords and `type == "sphere"`, override to `"capsule"`. Defense-in-depth: prompt fails occasionally, coercion is deterministic.

## Risks / Trade-offs

- [Risk] Flat-row stitch count may not match spiral count exactly → Mitigation: use `max(target_counts)` as row width, which is consistent with largest diameter
- [Risk] Terminator fires too early on low-stitch cylinders → Mitigation: only trigger when `target_count <= MIN_STITCHES AND delta < 0` (shape is decreasing)
- [Risk] Adding `primitive_type` to `compile_part` signature breaks existing callers → Mitigation: default value `primitive_type="sphere"` keeps old callers working

## Migration Plan

No database changes. No API breaking changes. Deploy is a straight file replacement. Rollback by reverting `grammar.py` and `main.py`.

## Open Questions

None — all decisions resolved during explore session.
