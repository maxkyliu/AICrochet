# QA Report — AICrochet pattern buttons

- **Date:** 2026-05-29
- **Mode:** Report-only via API (browser can't launch in this sandbox — Chromium no-sandbox failure; the two UI buttons were tested by driving the endpoints they call and reading the actual generated pattern text)
- **Input:** `fox.jpg`
- **Criterion (user):** output must be human-readable for a crocheter to build the doll, and relatively close to the preview
- **Endpoints exercised:** `POST /generate`, `GET /preview/{id}`, `GET /refine/{id}`, `POST /generate-seamless/{id}` — all returned HTTP 200

## Verdict

| Button | Works? | Human-readable? | Close to preview? |
|---|---|---|---|
| **1. Generate Pattern** (multi-part) | Yes (8 parts, ~8.6 s) | Format yes; **shape no** (puckers) | Pattern ↔ preview consistent (same diameter source); both lumpy |
| **2. Generate One-Piece** (seamless) | Yes (~1 s) | **No** — raw op-token JSON | N/A (whole-doll single piece) |

Both buttons function and return fast. Neither currently produces a pattern a crocheter could use to build the intended doll.

## Findings

### F1 — HIGH — Sphere/learned parts pucker (non-monotonic stitch counts)
The base `/generate` output (pre-refinement) for the Head reads:
```
Rnd 2: sc in each st around [6]
Rnd 3: 3 sc in each st around [18]   ← jump to 18
Rnd 4: (sc 1, dec) x 6 [12]          ← shrink to 12
Rnd 5: (inc) x 12 [24]               ← balloon to 24
```
Increasing → decreasing → increasing in consecutive rounds makes a lumpy gourd, not a head.
- **Root cause:** `USE_LEARNED_MODEL=true` in `.env`; the trained `sphere_regressor.joblib` emits noisy, non-monotonic diameters `[2.04, 2.09, 5.32, 2.92, 7.96, …]`. With the model **off**, the same head is a clean `[2,4,6,8,8,8,6,4,2]` → `6→18→30→42…→18→12` (smooth, buildable).
- **Refinement does not fix it:** the mesh-driven refine loop only nudges within ±40% per-diameter and keeps the seed when it can't improve, so the early `5.32→2.92` dip survives into the final swapped pattern.
- **Pre-existing** (model trained May 27), not introduced by this session's mesh-driven work.
- **Recommended fix:** set `USE_LEARNED_MODEL=false` (one line in `.env`, gitignored) until the regressor enforces monotonic, smooth profiles or is retrained. Immediate, reversible.

### F2 — HIGH — Seamless button returns machine JSON, not instructions
`POST /generate-seamless` returns 75 KB of the Remesher's internal sequence:
```json
{"l":0.0588,"traversals":[{"sequence":[-2,-2,-2,…,[1,1.0],[2,0.5],-7,…]}]}
```
No stitch words, no rounds — a crocheter cannot build from `-2, [2,0.5], -7`. The frontend shows this verbatim.
- The design assumed the Remesher emits readable CrochetPARADE-DSL prose and chose "display as-is in Phase 1." It does **not** — it emits this op-token sequence. That assumption was wrong.
- **Recommended fix:** add a translator from the Remesher op-sequence (-2 = ?, -7 = ?, `[n,f]` = ?) into readable rounds, or at minimum render a human summary (stitch count, op legend). Until then, the button over-promises.

### F3 — MEDIUM — Tubes/parts have no closure instruction
The Left Arm (cylinder) ends at `Rnd 18: sc in each st around [12]` with no `fasten off` / `stuff` line. Open tubes and any part whose last round isn't ≤6 stitches just stop. A crocheter doesn't know to fasten off, weave in, or stuff.
- **Recommended fix:** emit a terminal `fasten off` (and a stuff/don't-stuff note) for every 3D part, not only when the decreasing tail reaches the minimum.

### F4 — MEDIUM — flat_disc "Ears" is a rectangle, labeled plural, single piece
`Ears` → `Ch 26, turn` + 13 identical `sc across [25]` rows + "Sew flat" = a 25×13 flat rectangle, not an ear shape, and one piece for a plural part with no "make 2".
- **Recommended fix:** taper the flat-disc rows toward a point/curve for ear-like shapes; detect plural/symmetric parts and add "make 2".

## What's working
- Button 1's notation is genuinely crocheter-readable: magic ring start, `(sc 2, dec) x 6 [18]`, bracketed round counts — standard amigurumi shorthand.
- Pattern ↔ preview consistency: the LatheGeometry preview and the written pattern are both derived from the same diameter array, so the pattern matches what the preview shows (the shared problem is the diameters themselves under F1).
- All four endpoints respond fast and correctly; refinement completes in ~10 s, seamless in ~1 s.

## Top 3 to fix
1. **F1** — `USE_LEARNED_MODEL=false` (or fix the regressor). Single biggest win; makes Button 1 output buildable.
2. **F2** — translate seamless op-tokens to readable rounds, or relabel/hide the button until it's readable.
3. **F3** — add closure/stuffing instructions to every part.

No code changed (report-only mode; dirty multi-project tree).
