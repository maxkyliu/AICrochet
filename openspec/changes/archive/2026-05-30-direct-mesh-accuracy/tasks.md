## 1. Remove the CP-dependent features (backend + frontend)

- [x] 1.1 Delete `backend/external_tools.py`, `backend/dot_export.py`, `backend/mesh_compare.py`, `backend/refine.py`, `backend/seamless.py`
- [x] 1.2 `backend/main.py`: remove imports of the deleted modules; remove `external_tools.check_binaries()` from startup; remove `_STL_DIR` and `_SEAMLESS_DIR` setup
- [x] 1.3 `backend/main.py`: remove the `_refine_after_mesh` async coordinator and the refinement scheduling block inside `/generate`
- [x] 1.4 `backend/main.py`: remove the `GET /refine/{session_id}` endpoint
- [x] 1.5 `backend/main.py`: remove the `POST /generate-seamless/{session_id}` endpoint
- [x] 1.6 `frontend/static/index.html`: remove the "Generate One-Piece Pattern" button, `#seamless-panel` div, `#refine-status` div, related CSS rules, and `generateSeamless()` function
- [x] 1.7 `frontend/static/index.html`: remove `startRefinePolling()` and its invocation in `generatePattern()`; remove the seamless-button enable line from `startPreviewPolling()`'s `done` branch
- [x] 1.8 Delete `backend/tests/test_external_tools.py` (3 tests covering the removed module)
- [x] 1.9 `.env.example`: remove `GRAPH_STANDALONE_BIN`, `CROCHET_REMESH_BIN`, `GRAPH_SOLVER_ITERATIONS` block; keep a one-line comment that the External GPL tools section was removed in change `direct-mesh-accuracy`
- [x] 1.10 Confirm `.external_tools/` stays gitignored (no change needed); `scripts/build_external_tools.sh` is retained but unused (no change needed)

## 2. Vision schema + Gemini bbox + retry wrapper

- [x] 2.1 `backend/vision.py`: add an optional `bbox` field (`{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4}`) to `_PARTS_SCHEMA` for Claude/Ollama; add a `bbox: te.NotRequired[list[float]]` field to the Gemini `PartNode` TypedDict
- [x] 2.2 `backend/main.py`: update `GEMINI_PROMPT` to additionally request a normalized 2D bounding box per part — format `[x_min, y_min, x_max, y_max]`, image coords 0..1, image-y points down. Make it clear bboxes are required for the standard pattern path but downstream tolerates missing.
- [x] 2.3 `backend/vision.py`: add `analyze_with_retry(img_bytes, prompt)` helper — calls `analyze_image`; if response misses Head/Body or has fewer than 4 parts, re-issues the call with the strengthened prompt suffix `"\n\nIMPORTANT: include ALL visible body parts — head, body, BOTH arms, BOTH legs, ears, tail, etc. Do not omit symmetric parts."`. Up to 2 retries (3 calls total). Returns the last response regardless. Silent (info-level log only).
- [x] 2.4 `backend/main.py`: `/generate` switches from `analyze_image(...)` to `analyze_with_retry(...)`

## 3. Mesh measurement module (backend/mesh_measure.py)

- [x] 3.1 Implement `load_normalized_mesh(glb_path)` — `trimesh.load(force="mesh")` → center at origin → PCA-align principal axis to +Y → return mesh (absolute scale preserved)
- [x] 3.2 Implement `measure_part(mesh, bbox, n_slices=None)` — map bbox `y_min`/`y_max` to mesh y-range with the image-y-flip (image-y points down, mesh-y points up); compute `n_slices = max(4, round(band_height * SLICE_DENSITY))` if not given; for each horizontal plane in the band, call `trimesh.intersections.mesh_plane`; for each non-empty intersection polyline, measure `max(x_extent, z_extent)` as the diameter; skip degenerate slices; return list of floats (empty on total failure, never raises)
- [x] 3.3 Calibrate `SLICE_DENSITY` constant against fox.jpg at implementation (aim for ~10 slices on a full-doll-height part); document as a module-level constant
- [x] 3.4 Add a small sanity check helper `_is_reasonable(diameters, n_slices)` — rejects empty / contains zero or negative / length far from n_slices / wildly non-monotonic (used by the coordinator to decide fall-back)

## 4. Measurement coordinator + endpoint (backend/main.py)

- [x] 4.1 Add an in-memory job dict `_measure_jobs: dict[str, dict]` with shape `{status, parts, error}` and helpers `_measure_create/update/get(session_id, ...)`
- [x] 4.2 Implement `_measure_after_mesh(session_id, parts_from_llm, glb_path, grammar)` async helper — waits for `comfyui.get_job(session_id)` status `done` (polling sleep 4s, ~10 min cap); on done, runs measurement off the event loop via `asyncio.to_thread`: load normalized mesh, for each part with a bbox call `measure_part` then `CrochetGrammar.compile_part(name, measured_diameters, primitive_type)`; truncate effective diameters to rounds_used (mirror existing `/generate` logic); assemble per-part dicts; for parts missing a bbox or with failed measurement, copy through the original hardcoded-geometry part; update job status
- [x] 4.3 In `/generate`, after building the standard `results`, collect bboxes per part name; if any bbox exists AND `comfyui._node_available` AND the 3D generation was scheduled, `_measure_create(session_id)` and `asyncio.create_task(_measure_after_mesh(...))`
- [x] 4.4 Add `GET /measured/{session_id}` endpoint — returns `_measure_get(session_id)` or 404

## 5. Frontend measurement polling (frontend/static/index.html)

- [x] 5.1 Add `#measure-status` div in markup (near the existing `#preview-status` slot) and CSS rule matching the existing badge style
- [x] 5.2 Implement `startMeasurePolling(sessionId)` — `setInterval` every 4s, max 150 ticks; calls `GET /measured/{sessionId}`; on `done` calls `renderParts(job.parts)` and hides the badge; on `failed`/404/timeout hides the badge and keeps the original pattern; on any other status keeps polling
- [x] 5.3 In `generatePattern()`, after `startPreviewPolling(sessionId)`, also call `startMeasurePolling(sessionId)`

## 6. Tests

- [x] 6.1 Add `backend/tests/test_mesh_measure.py` — construct a synthetic trimesh (e.g. an icosphere via `trimesh.creation.icosphere(subdivisions=3, radius=1.0)`), call `measure_part` with a top-half bbox `[0.2, 0.0, 0.8, 0.5]`, assert returned list is non-empty, all floats are positive, length matches `n_slices`, monotonically rises then falls (sphere top-half should taper)
- [x] 6.2 Test `load_normalized_mesh` — load a known asymmetric mesh, assert principal axis ends up aligned to +Y (PCA axis vs Y dot product close to 1.0)
- [x] 6.3 Test `_is_reasonable` — happy path returns True; zero in array returns False; wildly variable lengths returns False
- [x] 6.4 Add `backend/tests/test_vision_retry.py` — mock `analyze_image` so first call returns 2 parts (no Head/Body), second call returns 4 parts with Head/Body; assert `analyze_with_retry` returns the second response; assert with `mock.call_count == 2`
- [x] 6.5 Test the strengthened-prompt logic — assert the retried call's prompt arg ends with the IMPORTANT instruction
- [x] 6.6 Test "all retries fail" path — mock all 3 calls returning 2 parts; assert `analyze_with_retry` returns the third response, doesn't raise, `mock.call_count == 3`
- [x] 6.7 Run full pytest suite — 34 geometry tests + the grammar tests still pass; new tests pass; deleted external_tools tests are gone

## 7. Live verification (fox.jpg)

- [x] 7.1 Start server; `POST /generate` with fox.jpg + session_id; confirm response shape unchanged and parts have `bbox` field present (Gemini)
- [x] 7.2 Poll `/preview/{sid}` to `done`; then poll `/measured/{sid}` to `done`; inspect the measured Head's diameters and confirm they reflect the actual fox mesh (e.g. roughly fox-head shape, not the hardcoded `[2,4,6,8,8,8,6,4,2]`)
- [x] 7.3 Confirm the measurement-swap badge appears + disappears; the per-part cards swap to the measured pattern
- [x] 7.4 Confirm there is no longer a "Generate One-Piece Pattern" button, no `/generate-seamless` or `/refine` endpoint (curl returns 404), and the standard pattern path is unaffected
- [x] 7.5 LLM retry sanity check: with `VISION_PROVIDER=ollama` and the `llava` model (which under-segments), upload fox.jpg and confirm logs show the retry firing (and either succeeds or eventually returns the under-segmented response without erroring)
