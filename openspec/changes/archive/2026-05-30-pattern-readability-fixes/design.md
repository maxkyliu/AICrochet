## Context

A QA pass (report `.gstack/qa-reports/qa-report-aicrochet-2026-05-29.md`) found four issues. F1 (the learned model emitting non-monotonic puckering profiles) was fixed by setting `USE_LEARNED_MODEL=false`. This change addresses the remaining three, all in the symbolic output layer — the crochet grammar and the seamless-pattern adapter. None touch the vision/geometry/mesh pipeline.

These are small, contained fixes. A design doc is warranted only because F2 rests on a non-obvious discovery about the remesher's output and F4 has a shape decision worth recording.

## Goals / Non-Goals

**Goals:**
- Every part either closes cleanly (tapered tip) or tells the crocheter to fasten off and sew (open end), and 3D parts say whether to stuff.
- flat_disc parts come out shaped (leaf/teardrop) following their profile, not as rectangles; paired parts say "(make 2)".
- The seamless button shows readable CrochetPARADE notation with framing, not raw op-tokens.
- Existing 34 grammar tests stay green.

**Non-Goals:**
- Transpiling the seamless CrochetPARADE DSL into hand-crochet rounds (would mean reimplementing the CP parser; lossy; out of proportion).
- Per-part mesh segmentation or refinement-loop changes.
- Gemini prompt changes (make-2 is done in post-process code).

## Decisions

### D1 — F2: return the remesher's existing `crochetparade` field, framed

**Decision**: `run_remesher` parses the pattern JSON and returns the top-level `crochetparade` string field (the readable DSL the remesher already emits: `sc`, `scinc`, `scdec`, `ch`, `DEF:`/`COLOR:` directives). If the field is absent or empty, fall back to the current `json.dumps` behavior. The frontend (or the endpoint) prepends a plain-English header: that this is a one-piece seamless pattern in CrochetPARADE notation, worked as a single continuous piece plus sewing edges, the total stitch count, and a line: "Paste this into crochetparade.org to render and follow it visually."

**Why**: Verified the remesher pattern JSON already carries `crochetparade` (≈1.7 KB of DSL) — we were displaying `traversals.sequence` (raw op-tokens) by mistake. The seamless pattern is a continuous surface-grown spiral with per-stitch inc/dec and sewing edges; it does not decompose into tidy uniform rounds. Its natural readable form is the CP DSL, which crochetparade.org renders. This is the agreed "middle option" on the readability spectrum — honest about what the artifact is, no fake transpile.

**Total stitch count**: derive cheaply by counting stitch tokens in the DSL (or from the JSON `traversals` sequence length, excluding markers). Approximate is fine for a header.

### D2 — F3: terminal closure for every 3D part

**Decision**: In `compile_part_detailed`, keep the existing early-break fasten-off for parts that decrease to `MIN_STITCHES` (6). After the loop, if no fasten-off line was emitted, append:
- last round count ≤ 6 → "Fasten off, weave tail through remaining sts to close."
- last round count > 6 → "Fasten off, leave a long tail for sewing."

And for all non-flat_disc parts, emit a stuffing note before the closure: "Stuff firmly." (closed tip) or "Stuff before sewing." (open end). flat_disc keeps its existing "Do NOT stuff. Sew flat." and is unaffected by this block.

**Why**: A pattern that just stops at "Rnd 18: sc in each st around [12]" leaves the crocheter without instruction to fasten off, stuff, or sew. The closed/open distinction matters: a tapered head closes by cinching the tail; an open arm needs a sewing tail. Track whether the early-break already fired with a simple flag so we never double-emit.

**Edge case**: the existing terminator spec says a flat cylinder (all rounds equal, above minimum) emits no premature terminator. That stays true mid-pattern — the new closure is a single terminal block appended once at the end, not a per-round change.

### D3 — F4: shaped flat rows following the profile

**Decision**: `_compile_flat_disc` stops using `max(width)` for every row. Instead it derives a per-row target width from each diameter in the profile (e.g. `width_i = max(1, round(d_i * π / w))`, halved if a flat sheet reads better — tuned at implementation). Construction:
- Foundation: `Ch {w1 + 1}, turn`; Row 1: `sc in 2nd ch from hook, sc across [{w1}]`.
- Each subsequent row turns (`Ch 1, turn`) and works `sc across` with edge shaping to reach the next target width: increases = "2 sc in first and last st" (+2/row), decreases = "sc2tog at each end" (−2/row). When the target equals the current width, plain `sc across`.
- End: "Do not stuff. Sew flat."

This widens to the profile's max then tapers to a point — a leaf/teardrop/triangle for pointed ears, wings, fins.

**Why pointed rows over a flat circle**: the user wants pointed ears. A flat circle worked in rounds would suit round eyes/buttons but not pointed ears; shaped rows cover the pointed case and still read row-by-row in plain notation. Width changes are ±2 per row (one increase/decrease at each edge), which is what hand-crocheted flat shaping actually does.

### D4 — F4: "(make 2)" for plural/paired parts

**Decision**: A small post-process helper detects plural or inherently-paired part names. Keyword set (case-insensitive, whole-word-ish): ears, eyes, arms, legs, paws, wings, fins (and their singular forms when the LLM emitted a bare plural). When matched, the part label is singularized for display and the pattern appends "(make 2)".

**Why code not prompt**: the Gemini prompt is non-deterministic about singular/plural and pairing; a deterministic post-process is reliable. Phase-1 scope is at least the flat_disc/plural case; applying the same helper to symmetric 3D parts (two arms) is a natural extension but only required where the LLM returns a single plural part.

## Risks / Trade-offs

**Seamless DSL still isn't hand-crochet rounds** → A crocheter who won't use crochetparade.org still can't hand-follow it. Mitigation: the framing header is explicit that this is CP notation for the visualizer; the multi-part button remains the hand-crochetable option. Accepted — full transpile is out of scope.

**flat_disc width formula tuning** → The per-row width mapping (full vs half circumference) affects whether ears look right. Mitigation: pick the formula at implementation by eyeballing a couple of profiles; it's a one-line constant.

**Plural detection false positives** → A part literally named "Glasses" or a non-paired "Eyes" motif could wrongly get "(make 2)". Mitigation: keep the keyword set tight to common amigurumi pairs; "(make 2)" is a low-harm hint a crocheter can ignore.

**Test churn** → Existing flat_disc and terminator tests assert the old rectangle/closure behavior and will need updating. Mitigation: update those tests as part of the change (they encode the old, now-wrong behavior) and add new ones; keep all other grammar tests untouched.

## Migration Plan

1. `backend/grammar.py`: add terminal-closure block (F3) and rewrite `_compile_flat_disc` (F4) + make-2 helper. Update affected tests.
2. `backend/external_tools.py`: `run_remesher` returns `crochetparade` field (F2).
3. `backend/main.py` / frontend: add the framing header + crochetparade.org line to the seamless panel.
4. Run the full pytest suite; add new tests; manual re-run of both buttons with fox.jpg.
5. No DB or dependency changes.

## Open Questions

- **flat_disc width formula** (full vs half circumference per row) — decide at implementation against real ear/wing profiles.
- **make-2 for symmetric 3D parts** — include now or defer? Default: handle the plural/flat_disc case required by the QA finding; extend to 3D pairs only if trivial.
