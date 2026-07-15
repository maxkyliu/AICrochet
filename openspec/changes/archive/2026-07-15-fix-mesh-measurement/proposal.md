# Fix Mesh Measurement

## Why

The mesh-measured recompile pass produces patterns worse than the initial estimate — far enough from a real pattern that the user cannot even hand-adjust them (user report, 2026-07-15). Root causes identified in review: slices measure the whole mesh at each height (a body slice includes both arms; a head slice includes ears), the single global calibration factor spreads that inflation to every part, PCA alignment can leave the mesh upside-down or sideways, round counts come from arbitrary mesh units, raw slice noise feeds the grammar unregularized, and the length sanity check is a no-op (`_is_reasonable(measured, len(measured))`). Since 2026-07-15 the initial estimate uses market-learned prototype curves validated better than hardcoded profiles, so an unreliable measured swap now actively degrades a good pattern.

## What Changes

- Restrict each cross-section measurement to the geometry inside the part's bbox x-range, instead of the whole mesh's extent at that height.
- Resolve the PCA orientation ambiguity (sign flip / wrong axis) with a mass-distribution check against the bbox layout, and fall back to skipping measurement when orientation confidence is low.
- Regularize measured profiles against the market prototype for the part's primitive type: the mesh contributes amplitude, length, and coarse shape; the prototype constrains the curve to a crochetable profile.
- Derive the recompiled part's round count from the calibrated size (same rounds-per-stitch rule the market prototypes use), not from slice count in mesh units.
- Gate the frontend swap on measurement quality: the measured pattern replaces the initial one only when it passes a shape-agreement check against the expected profile; otherwise the initial pattern is kept.
- Fix the no-op length sanity check by validating measured length against the initial profile's round count.

## Capabilities

### New Capabilities

_None — this change repairs an existing capability without introducing a new surface._

### Modified Capabilities

- `mesh-measured-diameters`: slicing becomes bbox-constrained in x as well as y; mesh normalization gains an orientation-confidence requirement; calibration/recompilation is regularized against market prototype curves with a size-derived round count; the swap becomes quality-gated (measured output must beat a shape-agreement threshold or the initial pattern is retained); the sanity check compares measured length against the initial profile's expected round count.

## Impact

- **Code**: `backend/mesh_measure.py` (slicing, orientation, sanity checks), `backend/main.py` (`_measure_sync` calibration/recompile/gating), `backend/geometry.py` (expose prototype curve lookup for regularization).
- **Data**: reads `data/models/market_profiles.json` (already produced by `models/prototypes.py`); no schema changes.
- **API**: `GET /measured/{session_id}` response shape unchanged; a `done` job may now legitimately return the original parts (gate rejected the measurement) — frontend behavior already tolerates this.
- **Tests**: `backend/tests/test_mesh_measure.py` extended; new tests for bbox-x restriction, orientation check, regularization, and gating.
- **Dependencies**: none added (trimesh/numpy already present).
