# Tasks — Fix Mesh Measurement

## 1. Bbox-constrained slicing (mesh_measure.py)

- [x] 1.1 Extend `measure_part` to map bbox `x_min`/`x_max` onto the mesh x-extent and mask each cross-section to in-window vertices (+5% tolerance margin); skip slices with <2 surviving vertices
- [x] 1.2 Add tests: geometry outside the x-window (offset second sphere at the same height) does not inflate the measured diameter; degenerate x-windows return `[]` without raising

## 2. Orientation disambiguation (mesh_measure.py)

- [x] 2.1 Add `resolve_orientation(mesh, bboxes)`: compute mesh width-per-height curve (~10 bands), compute the bbox-predicted width curve, correlate both ways, flip the mesh about y when the flipped correlation wins, return the winning correlation as confidence
- [x] 2.2 Add tests: an inverted cone mesh with head-high/body-low bboxes gets flipped; a shuffled/no-signal case returns low confidence

## 3. Sanity check and calibration (mesh_measure.py, main.py)

- [x] 3.1 Fix `_measure_sync` to pass the initial profile's round count as `expected_n` to `_is_reasonable`; tighten the flip-fraction threshold to 0.30 and update the existing threshold test
- [x] 3.2 Replace the global-max calibration with the median of per-part `initial_max / measured_max` ratios; add a test that one inflated part does not shrink the others

## 4. Prototype regularization and round count (geometry.py, main.py)

- [x] 4.1 Expose a `GeometryEngine` helper returning the unit-amplitude reference curve and `rounds_per_max` for a primitive (market prototype, falling back to the normalized hardcoded profile)
- [x] 4.2 In `_measure_sync`, derive each part's target round count from calibrated amplitude via `rounds_per_max` (clamped to engine bounds), resample the measured curve to that length, and blend `α·measured + (1−α)·reference` with `MESH_BLEND_ALPHA` (env, default 0.5); force α=0 when the measured curve fails smoothness
- [x] 4.3 Add tests: noisy measured shape falls back to reference shape at measured amplitude; missing-prototype primitive regularizes against the hardcoded profile; round count follows amplitude not slice count

## 5. Quality gate (main.py)

- [x] 5.1 Score each regularized part (unit-amplitude MAE vs reference ≤ 0.25, measured flip fraction ≤ 0.30); failed parts keep the initial version; all-fail or low orientation confidence completes the job `done` with original parts
- [x] 5.2 Add tests: gated part retains initial instructions; low-confidence session performs no recompilation; `/measured` response shape unchanged in all gate outcomes

## 6. Configuration, docs, and end-to-end verification

- [x] 6.1 Add `MESH_BLEND_ALPHA` to `.env.example` with a comment; document the gate and orientation skip in ARCHITECTURE.md's measurement section
- [x] 6.2 Run the full backend test suite; then verify live: generate a pattern from a test image with the 3D pipeline enabled and confirm the measured swap either improves the pattern or visibly leaves the initial estimate in place
