## Why

A QA pass with fox.jpg found that both pattern buttons produce output a crocheter can't build from. F1 (learned-model puckering) was already fixed via config. Three issues remain: the seamless button shows raw machine op-tokens, multi-part tubes never say "fasten off" or "stuff", and flat_disc parts come out as featureless rectangles. These are the difference between a pattern someone can follow and one they can't.

## What Changes

- **F2 — Seamless pattern shows readable notation**: `run_remesher` returns the remesher's existing `crochetparade` DSL field (sc/scinc/scdec/ch tokens) instead of the raw traversal op-token JSON. The frontend frames it with a plain-English header (one-piece construction, total stitch count) and a "paste into crochetparade.org to view/follow" line.
- **F3 — Every 3D part gets closure + stuffing**: the grammar appends a terminal instruction to any 3D part that doesn't already close — "Fasten off, weave tail through remaining sts to close" for a tapered tip, "Fasten off, leave a long tail for sewing" for an open end — plus a stuffing note. No 3D part can end mid-air.
- **F4 — flat_disc becomes shaped rows + make-2**: `_compile_flat_disc` follows the diameter profile, widening with edge increases and tapering with edge decreases to make a leaf/teardrop (pointed ears, wings, fins) instead of a rectangle. Plural/paired part names ("Ears", "Eyes") emit "(make 2)" and a singularized label.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `grammar-terminator`: closure is now required for ALL 3D parts (including open-ended tubes that never decrease to the minimum), with stuffing notes added.
- `flat-disc-construction`: rows follow the diameter profile with edge shaping (leaf/teardrop) instead of fixed-width rectangle rows; plural/paired parts get "(make 2)".
- `seamless-pattern-mode`: the endpoint returns the readable `crochetparade` DSL field with a plain-English framing header, not the raw op-token JSON.

## Impact

- **Code**: `backend/grammar.py` (`compile_part_detailed` closure logic, `_compile_flat_disc` shaped rows + make-2 helper), `backend/external_tools.py` (`run_remesher` returns the `crochetparade` field), `backend/main.py` / `frontend/static/index.html` (seamless panel framing header + crochetparade.org link).
- **Tests**: `backend/tests/` — existing 34 must stay green; add tests for closure presence on tubes, shaped flat_disc rows, plural make-2, and seamless returning the DSL field.
- **No new dependencies. No API shape change** (`/generate-seamless` still returns `{"pattern": text}`; the text is now readable). `/generate` response schema unchanged.
- **Out of scope**: F1 (already fixed), full transpile of seamless DSL to hand rounds, mesh segmentation/refinement changes, Gemini prompt changes.
