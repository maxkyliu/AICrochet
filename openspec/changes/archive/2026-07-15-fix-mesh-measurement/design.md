# Design — Fix Mesh Measurement

## Context

The direct-mesh-accuracy change (2026-05-30) measures per-part diameter profiles by slicing the session's Hunyuan3D `.glb` inside each part's vertical band, then recompiles the pattern and swaps it in over the initial estimate. The user reports the swapped pattern is consistently *worse* than the initial estimate — too far from a real pattern to hand-adjust.

Review (2026-07-15) found six concrete defects:

1. **Cross-part contamination**: `mesh.section()` cuts the entire mesh at each height; only the bbox's y-range is used, never x. Head slices include ears; body slices include both arms. Diameter = max extent over *all* section loops, including disconnected ones.
2. **Calibration spreads the error**: the single global factor `hardcoded_max / measured_max` divides by the most-inflated measurement, shrinking every other part toward the 6-stitch floor.
3. **Orientation ambiguity**: `eigh` eigenvector sign is arbitrary — the mesh can be aligned upside-down (head band measures legs); wide-posed dolls can have a horizontal dominant axis (mesh laid sideways).
4. **Round count from mesh units**: `n_slices = band_height × 5` in a ~unit-cube mesh gives every part 4–10 rounds regardless of physical size.
5. **No regularization**: raw slice noise (up to 50% direction flips passes the filter) feeds `grammar.compile_part` directly, producing jittery inc/dec sequences no published pattern contains.
6. **No-op sanity check**: `_measure_sync` calls `_is_reasonable(measured, len(measured))`, so the ±50% length check can never fire.

Since 2026-07-15 the initial estimate comes from market prototype curves (`data/models/market_profiles.json`, leave-one-out MAE better than hardcoded on 5/6 primitives). The measurement pass must now *beat* a good baseline or stay out of the way.

## Goals / Non-Goals

**Goals:**
- Measured slices reflect only the part being measured (bbox-constrained in x and y).
- The mesh contributes what it is actually good at — per-part relative size and coarse shape — while the market prototype constrains the profile to a crochetable curve.
- The swap never degrades the pattern: a quality gate keeps the initial estimate unless the measurement demonstrably agrees with a plausible profile.
- Orientation errors are detected and cause a safe skip, not a wrong pattern.

**Non-Goals:**
- Camera pose estimation or render-based mesh↔photo correspondence (still Phase 2).
- Changing the `/measured` polling API or frontend swap mechanics.
- Handling non-upright topologies (sideways tails, octopus arms) beyond gating them out.
- Retraining or enabling the GBR regressors.

## Decisions

### D1 — Constrain slices to the part's bbox x-range

At each slice height, map the part's bbox `x_min/x_max` (normalized image coords) onto the mesh's x-extent the same way y is mapped today (linear, no pose estimation). Keep only cross-section vertices whose x falls inside the band (with a small tolerance margin, e.g. 5% of mesh x-extent); measure the diameter as `max(x_extent, z_extent)` of the surviving vertices. If fewer than 2 vertices survive, skip the slice.

**Why over connected-component selection**: picking the section loop nearest the band center would be more principled but requires loop reconstruction from `trimesh` section output and fails on merged loops (arm touching body). The x-window is one line of masking, uses information we already have, and removes the dominant error (full-width arms/ears in the measurement). z stays unconstrained — the photo gives no depth information, and amigurumi parts are approximately rotationally symmetric so the z-extent of the *correct* part is what we want.

### D2 — Orientation confidence check, skip on failure

After PCA alignment, verify the mesh's vertical mass layout agrees with the bbox layout from the photo: compute the mesh's vertex-count-weighted centroid height of the top and bottom thirds, and compare the widest part's band position (from bboxes, typically the body low, head high) against the mesh's width profile (x/z extent per y-band). Concretely: compute width(y) at ~10 heights on the whole mesh; compute the correlation between that curve and the same curve predicted from bboxes (each part's width span painted over its y-band). If the correlation is higher with the mesh flipped (y → −y), flip it. If both correlations are weak (< 0.3), mark orientation unreliable and skip measurement for the session (job status `done` with original parts).

**Why correlation over head-heuristics**: "head is on top" fails for non-figurative subjects. The width-profile correlation uses all parts, is cheap (two 10-point curves), and gives a natural confidence score for the gate.

### D3 — Prototype-regularized profiles: mesh sets amplitude and length, prototype sets shape

For each measured part, extract from the calibrated measurement only:
- `measured_max` → target max diameter (amplitude),
- band height relative to whole mesh → relative length signal.

Then build the profile by sampling the part's market prototype curve (`GeometryEngine` market path) at the round count derived from amplitude (existing `rounds_per_max` rule), scaled to the measured amplitude. Blend in measured *shape* only where it is trustworthy: resample the measured curve to the same length and take `profile = α·measured + (1−α)·prototype` with `α = 0.5` when the measured curve passes smoothness checks, `α = 0` otherwise. Primitives without a prototype (teardrop, frustum) use the hardcoded profile as the regularizer.

**Why blend instead of raw measurement**: the mesh genuinely knows relative proportions (head vs body diameter) — that is the original motivation for this feature — but its per-slice noise is worse than the prototype's shape error. Amplitude is where the mesh beats the LLM's guessed `scale`; shape is where the prototype beats the mesh. α as a constant (not learned) keeps this debuggable; tuning it is a follow-up once feedback data exists.

### D4 — Per-part calibration replaces the global max factor

Calibrate each part's measured max against the *initial estimate's* max for that same part, then take the median of those per-part factors as the session scale factor. A single global factor is still applied (mesh proportions between parts are the signal we want to keep), but deriving it from the median per-part ratio instead of the single global max makes it robust to one inflated part.

**Why median-of-ratios over global max ratio**: with contamination fixed (D1) the max ratio is less biased, but any residual outlier (overlapping bboxes) still lands on the max. The median costs nothing and is insensitive to a single bad part.

### D5 — Quality gate on the swap

Before storing `done` parts, score each measured part: normalized-curve MAE between the regularized profile and its prototype (or hardcoded) shape, plus the direction-flip count of the measured curve. A part fails the gate if MAE > 0.25 (on unit-amplitude curves) or flips > 30% of rounds; failed parts keep the initial version (existing per-part fallback path). If **all** measurable parts fail, the job completes with the original parts — the frontend swap then visibly changes nothing, which is correct.

**Why per-part gating over whole-session**: partial wins are real (body measured cleanly, ears contaminated); the per-part fallback plumbing already exists.

### D6 — Fix the sanity-check contract

`_is_reasonable(measured, expected_n)` gets its `expected_n` from the initial profile's round count for that part (available in `parts_in[i]["diameters"]`), restoring the ±50% length check. The flip-fraction threshold tightens from 50% to 30% to match the gate.

### D7 — Subject-relative bbox mapping (discovered in live verification)

The photo frame is larger than the subject, but the Hunyuan3D mesh spans exactly the subject. Mapping raw image coordinates onto mesh extents offsets every band (a head bbox starting at image y=0.12 landed 12% below the mesh top, which *is* the head top). All bboxes are therefore rescaled so their union spans 0..1 in x and y (`normalize_bboxes`) before orientation checking and measurement. On the live test mesh this took orientation confidence from 0.215 (below threshold, session skipped) to 0.527 and turned flat nonsense head measurements into a clean bell curve.

## Risks / Trade-offs

- [Bbox x-mapping assumes photo x ≈ mesh x after PCA] → The orientation check (D2) only validates the y-axis. A mesh rotated 90° about y (front-facing photo vs side-facing mesh) makes the x-window select the wrong slab; z-extent still measures the full part, and the gate (D5) catches shape disagreement. Residual risk accepted for Phase 1.
- [α = 0.5 blend is a guess] → Gate (D5) bounds the damage; feedback corrections (existing `/feedback` flow) give data to tune α later.
- [Median calibration can still drift when most bboxes overlap] → Overlap is bounded for upright amigurumi; the gate rejects the resulting shape mismatch.
- [Skipping sessions with weak orientation confidence reduces feature coverage] → Correct trade: the user explicitly prefers the initial estimate over a wrong measurement.
- [Prototype regularization makes measured output resemble the initial estimate] → That is the point: the measurement's job narrows to amplitude + proportions, where it has real signal.

## Migration Plan

Pure backend change, no API or data migration. Deploy = restart server. Rollback = revert commit; the `/measured` contract is unchanged in both directions. The feature can be effectively disabled by the existing no-bbox path if needed.

## Open Questions

- Should α be exposed as an env knob (`MESH_BLEND_ALPHA`) for tuning during dogfooding? Default plan: yes, env-gated with default 0.5, since it costs one line.
- The orientation correlation threshold (0.3) is a first guess; needs calibration against a handful of real session meshes before tightening.
