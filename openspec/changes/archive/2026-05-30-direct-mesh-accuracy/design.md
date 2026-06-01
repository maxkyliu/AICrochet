## Context

Two CP-dependent features shipped last session pass automated tests but fail in real use (the seamless DSL is rejected by crochetparade.org; the refinement loop is bounded so tightly it can't restructure shape). This change removes both and rebuilds the accuracy story around the one piece of real geometry we already produce — the Hunyuan3D `.glb` — by slicing it per part. The LLM segmentation step is also fragile across providers and gets a small robustness fix.

A design doc is warranted because (a) bridging the photo → mesh coordinate gap is non-trivial and the chosen Phase-1 simplification deserves to be documented, (b) the async-swap UX needs to be specified carefully, and (c) we explicitly reject several "better" but expensive options (SAM, render-based segmentation, per-part Hunyuan).

## Goals / Non-Goals

**Goals:**
- Standard pattern's diameters reflect the actual generated 3D doll, not LLM-guessed scale × hardcoded primitive profile.
- The seamless button and refinement endpoint disappear (no broken features lingering).
- Provider-fragile LLM segmentation retries silently before defaulting to a smaller part set.
- `/generate` still returns immediately; the measured pattern arrives via polling and swaps in.

**Non-Goals:**
- Python reimplementation of `graph_standalone` or the Remesher (both deferred forever or until justified by use).
- SAM-based 2D segmentation, render-based mesh correspondence, per-part Hunyuan generation — Phase-2 candidates only.
- Topology handling beyond vertically-stacked amigurumi (sideways tails, octopus arms, handles — not addressed).
- Re-enabling `USE_LEARNED_MODEL` or retraining regressors.

## Decisions

### D1 — Phase-1 segmentation: LLM bounding boxes + vertical band slicing

**Decision**: extend the Gemini prompt + JSON schema so each part returns a normalized 2D bbox `[x_min, y_min, x_max, y_max]` (image coords, 0..1). On the mesh side, after PCA-aligning the principal axis vertical and centering, map the bbox `y_min/y_max` (image y, downward) onto the mesh's vertical extent and treat that as the part's vertical band. Slice horizontally inside the band at N equally-spaced heights; at each slice, measure the diameter from the slice's horizontal extent.

**Why over the alternatives**: SAM segments photos, not meshes — its masks can't be projected onto the `.glb` without solving camera-pose first (the `.glb` is in Hunyuan3D's canonical orientation, not the photo's camera). Render-based correspondence (re-render the `.glb`, run SAM, project back) is the principled answer but adds 3–4 days of work and an offscreen renderer dependency. Vertical band slicing assumes the doll is approximately upright — true for amigurumi-class subjects — and gets us 80% of the accuracy for 20% of the work.

**Known limitation**: a fox with a tail sticking out sideways will have head/tail/body bboxes overlapping in y, so the tail's "band" will include body geometry. This is documented as the Phase-1 trade-off; Phase 2 (render-based correspondence) is the upgrade path.

### D2 — Image-y to mesh-y mapping orientation

**Decision**: image y increases downward (top of photo = `y=0`); mesh y after PCA alignment increases upward. The mapping flips: `mesh_y = mesh_y_max - bbox_y * (mesh_y_max - mesh_y_min)`. We do NOT try to recover the photo's exact camera pose — we treat the photo and the mesh as "same upright orientation" and accept the resulting slop.

**Why**: full pose estimation is out of scope. The 80% case (head on top, body in middle, legs at bottom) works with the simple flip; the 20% case is unaddressed but no worse than the current LLM-guessed-scale path.

### D3 — Number of slices per part

**Decision**: `n_slices = max(4, round(band_height_mesh_units * SLICE_DENSITY))` where `SLICE_DENSITY` is calibrated so a full-doll-height part gets ~10 slices. Tune at implementation against the fox example. Floor of 4 avoids degenerate single-row patterns.

**Why**: matching slice count to part height keeps the pattern's row count proportional to physical size, the way real amigurumi patterns do. Fixed slice counts (e.g. always 9) lose this information.

### D4 — Diameter extraction per slice

**Decision**: at each horizontal plane, use `trimesh.intersections.mesh_plane` to get the cross-section polyline, then take its bounding-box diameter (max of x-extent and z-extent) as the diameter value. Skip slices with no intersection (degenerate). After collecting raw diameter values, scale them by `(circumference factor) / π` so they're in the same units the grammar expects (it treats `diameter` as cm-like, mapping to stitch count via `count = 6·round((d·π/w)/6)`).

**Why bounding-box diameter not fitted circle**: cross-sections of doll parts aren't perfectly circular (a fox head is slightly egg-shaped). Bounding-box of the silhouette is what the crocheter actually wraps around — closer to the right number. Fitted-circle (least-squares) would systematically underestimate.

### D5 — Async swap, mirroring the prior polling pattern

**Decision**: `/generate` returns the standard (hardcoded-geometry) pattern immediately. After the `.glb` reaches `done`, a background `_measure_after_mesh` task computes the per-part measured diameters, recompiles the parts through `CrochetGrammar`, and stores the result in a session-keyed in-memory dict. Frontend polls `GET /measured/{session_id}` every 4 s; on `done`, swaps the rendered cards + previews via `renderParts(measured_parts)`. On `failed`/timeout, keeps the original.

**Why**: identical mechanic to the previous refine polling (which we know works). No new UX patterns. The user gets a usable pattern fast, and a better one ~30–60 s later when the mesh + measurement complete.

**Error handling**: any per-part measurement failure (bbox missing, slicing degenerate, empty intersection) falls back to the original hardcoded-geometry part. The measurement job degrades gracefully to a partial swap.

### D6 — Bbox is optional in the response schema; providers without it degrade

**Decision**: the JSON schema gains `bbox` as an optional 4-tuple of floats. Gemini's prompt requests it explicitly; Claude can be added similarly later; Ollama may or may not comply. If a part returns without a bbox, mesh measurement skips that part (keeps the hardcoded version). If NO parts have bboxes, the measurement job is skipped entirely.

**Why**: keeps the multi-provider vision abstraction intact. Each provider returns its best effort; the measurement layer takes what it can use.

### D8 — Calibrate measured diameters against hardcoded max (discovered in implementation)

**Decision**: Hunyuan3D meshes have no absolute scale — `trimesh.load` gives diameters in arbitrary unit-cube-ish range (~0.5–2.0). The grammar expects cm-like values that map to stitch counts via `count = 6·round(d·π/w/6)`; raw measured diameters of ~1.0 all collapse to 6 stitches, making every part a degenerate tube. So `_measure_sync` runs in two passes: (1) collect raw measured diameter arrays for each measurable part; (2) compute a single global scale factor = `hardcoded_max / measured_max` across all parts, apply it to every measured array, then recompile through the grammar.

**Why**: this preserves the relative proportions the mesh actually shows (head smaller than body, tail thinner than torso) while landing the absolute values in the same range the user's existing hardcoded patterns work at. Global scaling (one factor for the whole doll) keeps the math simple and avoids per-part scale mismatch.

**Trade-off**: if the hardcoded max comes from a part the LLM mis-scaled, the calibration inherits that error. Acceptable — the measured *shape* is still the win; getting absolute scale right would require a real-world reference (gauge swatch + photo scale) which is a separate problem.

### D7 — LLM segmentation retry: silent, up to 2×

**Decision**: a new helper `analyze_with_retry(img_bytes, prompt)` wraps `analyze_image`. After the first call, count parts: if fewer than 4 OR missing Head OR missing Body (case-insensitive name match), retry with a strengthened prompt appending: *"IMPORTANT: include ALL visible body parts — head, body, BOTH arms, BOTH legs, ears, tail, etc. Do not omit symmetric parts."* Up to 2 retries total. Return whatever the last call produced.

**Why silent**: most of the time the retry succeeds and the user shouldn't notice. If it fails after retries, the standard pattern still runs with a smaller part set — better than blocking the user with an error.

**Threshold rationale**: amigurumi minimum = head + body. Adding "≥2 limb-class parts" catches the "only one arm and one leg" failure mode the user observed on ollama llava. Higher thresholds (e.g. require both pairs) would force retries on legitimately asymmetric or simplified dolls.

## Risks / Trade-offs

**Bbox/mesh-orientation mismatch** → If Hunyuan3D produces a `.glb` rotated unexpectedly (e.g. doll lying on its side in the canonical view), the vertical-band assumption fails and parts get sliced wrong. Mitigation: PCA alignment to vertical principal axis is robust for elongated objects; for nearly-spherical objects the principal axis is ambiguous but the slicing is also less position-sensitive. Document the assumption; consider a Phase-2 fix only if reports come in.

**Measurement makes the pattern worse** → A clean hardcoded sphere might become lumpy if the mesh has noise (Hunyuan3D meshes can have surface artifacts). Mitigation: each part's measured profile is sanity-checked: if monotonicity is wildly violated OR any diameter is zero/negative OR the array length differs from `n_slices` by more than 50%, keep the hardcoded version for that part.

**LLM retry latency** → Each retry adds another vision call (~5–10 s). Worst case: 3 calls = ~20–30 s before `/generate` returns. Mitigation: retries only fire on underclaim — and only the worst providers hit that path. Gemini almost always passes first time.

**.glb orientation flip** → If image-y vs mesh-y mapping is wrong (we get parts upside down), the head bbox lands at the leg region. Mitigation: visually verify on fox.jpg at implementation; add a sign flag if needed.

**Removing the refinement loop loses a "feature"** → Even if the loop was ineffective, removing it visibly changes UI behavior (no more refine badge/swap). Mitigation: replace with the measurement swap, which is the genuine version of what refinement was promising.

## Migration Plan

1. Remove the CP-dependent backend modules and endpoints in one commit so the codebase isn't half-broken.
2. Update `vision.py` schema + Gemini prompt to add bbox; add `analyze_with_retry`. Existing `analyze_image` callers continue to work (bbox just appears as an extra field).
3. Add `backend/mesh_measure.py` and the `_measure_after_mesh` coordinator + `/measured/{id}` endpoint.
4. Update `main.py` `/generate` to schedule measurement after the `.glb` is ready (when bboxes are present).
5. Frontend: delete seamless/refine UI, add measurement-swap polling.
6. Tests: delete `test_external_tools.py`; add `test_mesh_measure.py` (synthetic mesh fixture) and `test_vision_retry.py`.
7. `.env.example`: drop the three CP-tool env vars.
8. Manual verification on fox.jpg: confirm measurement runs and swaps in; confirm retry fires when forced underclaim.

## Open Questions

- **`SLICE_DENSITY` constant**: tune against fox.jpg at implementation. Probably in the range 0.5–2.0 (slices per mesh-unit height).
- **Image-y flip sign**: confirm at implementation by running fox.jpg end-to-end and checking head measurement lands at the head, not the legs.
- **Should Claude also be asked for bboxes?** Out of scope this change; the abstraction supports it but Gemini-only is the Phase-1 baseline.
