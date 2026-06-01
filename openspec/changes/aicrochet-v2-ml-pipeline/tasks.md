## 1. Phase 1 — Foundation Fixes (Scale + Primitives + 3D Preview)

- [x] 1.1 Rewrite `GeometryEngine.get_diameters_for_primitive()` to accept `scale` and return amplitude-scaled diameter profiles
- [x] 1.2 Implement `sqrt(scale)` flat-round extension for `sphere` and `teardrop` shapes
- [x] 1.3 Add base diameter profiles for 5 new primitives: `frustum`, `capsule`, `teardrop`, `flat_disc`, `torus`
- [x] 1.4 Add fallback-to-cylinder with warning log for unrecognized primitive types
- [x] 1.5 Update Gemini prompt to enumerate all 8 primitive types with one-line descriptions
- [x] 1.6 Update `DependencyGraph` Pydantic schema to reflect expanded type literal (8 values)
- [x] 1.7 Pass `scale` through `process_dependency_graph()` output so grammar can use it
- [x] 1.8 Add unit tests for all 8 primitives at multiple scale values verifying amplitude and round count

## 2. Phase 1 — Gauge-Aware Grammar

- [x] 2.1 Add `gauge_stitches_per_10cm` and `gauge_rows_per_10cm` optional fields to the `/generate` request schema
- [x] 2.2 Update `CrochetGrammar.__init__()` to accept `stitch_width_cm` and `stitch_height_cm` as parameters derived from gauge
- [x] 2.3 Wire gauge from request body into `CrochetGrammar` instantiation in `main.py`
- [x] 2.4 Add collapsible "Gauge Settings" panel to `index.html` with stitches/rows inputs
- [x] 2.5 Add yarn weight preset dropdown (Fingering, Sport, DK, Worsted, Bulky) that populates gauge fields
- [x] 2.6 Send gauge fields with the `/generate` form submission from the frontend
- [x] 2.7 Verify stitch counts change correctly when gauge is varied (manual test with worsted vs fingering values)

## 3. Phase 1 — 3D Browser Preview

- [x] 3.1 Add Three.js CDN `<script>` tag to `index.html`
- [x] 3.2 Write `buildLatheGeometry(diameters)` JS function that converts a diameter array to Three.js `LatheGeometry` points
- [x] 3.3 Create a `renderPart(partName, diameters, canvasEl)` function with ambient + directional lighting and soft purple material
- [x] 3.4 Add a `<canvas>` element per part card and call `renderPart` after each part is received from `/generate`
- [x] 3.5 Implement orbit controls (click-drag rotation) using Three.js `OrbitControls`
- [x] 3.6 Implement slow Y-axis auto-rotation that pauses on user interaction and resumes after 2s idle
- [x] 3.7 Build the combined multi-part scene with spatial heuristics for head/body/arm/leg/ear/tail keywords
- [x] 3.8 Add graceful degradation: catch WebGL unavailability and show fallback message without breaking text instructions

## 4. Phase 2 — Data Pipeline: Web Scraper

- [x] 4.1 Create `data/` directory structure: `data/raw/`, `data/models/`, `data/aicrochet.db`
- [x] 4.2 Implement Ravelry API client with OAuth or API key auth, 1 req/sec rate limiting, and exponential backoff on 429
- [x] 4.3 Implement pagination over Ravelry amigurumi pattern search results with cursor persistence
- [x] 4.4 Store raw Ravelry JSON responses and photo URLs to `data/raw/ravelry/`
- [x] 4.5 Implement duplicate-detection skip using stored pattern IDs
- [x] 4.6 Implement resumable scraper cursor (last page + last pattern ID stored to disk)
- [x] 4.7 Fine-tune a MobileNetV2 binary classifier on ~200 manually labeled finished-object vs WIP photos
- [x] 4.8 Integrate photo classifier into scraper with 0.85 confidence threshold gate
- [x] 4.9 Write rejected photo URLs to a `data/raw/review_log.jsonl` file
- [x] 4.10 Implement HTML scraper for Amigurumi Today free pattern pages (pattern text + main photo)
- [x] 4.11 Add scraper CLI: `python -m data.scraper run --source ravelry|amigurumitoday [--limit N]`

## 5. Phase 2 — Data Pipeline: Pattern Normalizer

- [x] 5.1 Implement US/UK terminology detector (marker phrase scan + header keyword check)
- [x] 5.2 Build instruction tokenizer: regex-based parser for round instruction strings → canonical op tokens
- [x] 5.3 Implement repetition block expander `(... ) × N` → flat token list
- [x] 5.4 Map all increase/decrease notation variants to canonical `inc`/`dec` tokens
- [x] 5.5 Implement stitch-count checksum validator (compare parsed total vs stated bracket total)
- [x] 5.6 Implement diameter reconstruction from stitch counts using inverse circumference formula
- [x] 5.7 Implement part boundary detector (look for "--- PART NAME ---" style separators and Ravelry section headers)
- [x] 5.8 Compute per-record quality score: 1.0 if all rounds validate, discounted for ambiguous terminology or missing checksums
- [x] 5.9 Write normalizer output to SQLite `training_records` table with full provenance fields
- [x] 5.10 Add normalizer CLI: `python -m data.normalizer run [--source ravelry|amigurumitoday]`

## 6. Phase 2 — Training Dataset Tooling

- [x] 6.1 Create SQLite schema with `training_records`, `feedback_corrections`, `schema_version` tables
- [x] 6.2 Implement automatic schema migration runner on database open
- [x] 6.3 Implement `dataset export` command: stratified train/val split (80/20) with quality threshold filter
- [x] 6.4 Implement `dataset stats` command: record counts by primitive, synthetic ratio, mean quality, date range
- [x] 6.5 Seed synthetic records by scaling hardcoded base profiles at scale 0.5/1.0/1.5/2.0/2.5, marked `is_synthetic=true`

## 7. Phase 3 — Profile Regressor

- [x] 7.1 Add `scikit-learn` to project dependencies
- [x] 7.2 Implement feature extractor: `(scale, aspect_ratio)` vector from a training record
- [x] 7.3 Train one `GradientBoostingRegressor` per primitive type using the training dataset export
- [x] 7.4 Implement validation evaluation: MAE per diameter position, per-primitive breakdown, overall mean
- [x] 7.5 Implement promotion gate: only write model to `data/models/` if overall MAE < 1.0 stitches
- [x] 7.6 Implement model archiving: rename existing `.joblib` to `.joblib.bak` with timestamp before promotion
- [x] 7.7 Write model metadata file alongside each `.joblib`: training date, record count, MAE, sklearn version
- [x] 7.8 Add `USE_LEARNED_MODEL` env var check in `GeometryEngine.get_diameters_for_primitive()`
- [x] 7.9 Implement graceful fallback: if model file missing and flag is true, use hardcoded profile + log warning
- [x] 7.10 Add training CLI: `python -m models.train [--primitive all|<type>] [--eval-only]`

## 8. Phase 4 — Feedback Loop

- [x] 8.1 Create `feedback_corrections` SQLite table with all required fields including `incorporated` flag
- [x] 8.2 Implement `POST /feedback` FastAPI endpoint with Pydantic validation (matching array lengths)
- [x] 8.3 Add "Adjust Shape" toggle button per part card in the frontend
- [x] 8.4 Build per-round diameter slider panel in the frontend (one slider per round, initialized to current diameter)
- [x] 8.5 Wire "Submit Correction" button to call `POST /feedback` with original and corrected diameter arrays
- [x] 8.6 Add success/error confirmation message after feedback submission
- [x] 8.7 Implement correction batch counter: monitor `feedback_corrections` for unincorporated count ≥ 100
- [x] 8.8 Implement retraining trigger: when threshold hit, run training pipeline and incorporate corrections with 2.0× sample weight
- [x] 8.9 Mark incorporated corrections with `incorporated=true` after successful model promotion
- [x] 8.10 Add `GET /feedback/stats` endpoint returning total corrections, unincorporated count, last retraining date
