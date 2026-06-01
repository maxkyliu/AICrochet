## Why

The previously-shipped `mesh-driven-pattern-options` change passed every automated test but fails at the user-value boundary: the "Generate One-Piece Pattern" button produces CrochetPARADE DSL that crochetparade.org itself rejects (verified by the user; multiple manual fixes failed), and the physics-validated refinement loop is bounded so tightly by ±40% diameter limits and multiples-of-6 stitch quantization that it barely changes anything meaningful. Both features are theatre — they return data, the data is unusable.

The real accuracy gap stays unaddressed: AICrochet patterns come from LLM-guessed scale × hardcoded primitive profiles, with no contact with the real geometry of the doll in the photo. The Hunyuan3D `.glb` we already generate is the ground truth right there. Slicing it directly per part gives real diameter profiles without any crochet-physics simulation or external GPL tools.

Separately: the LLM segmentation step is provider-fragile (ollama llava routinely misses parts on the fox photo; only Gemini 2.5 Flash reliably returns the full set). Silent retry with a strengthened prompt fixes most cases without bothering the user.

## What Changes

- **Remove both halves of `mesh-driven-pattern-options`**: the seamless one-piece button + endpoint, the physics refinement loop + endpoint, all CP-tool dependencies. The CrochetPARADE binaries can stay under `.external_tools/` (gitignored) but the calling code goes away entirely.
- **Add direct mesh measurement**: a new `backend/mesh_measure.py` slices the session `.glb` vertically using each part's LLM-provided bounding box, extracts a real per-row diameter array, and feeds those measured diameters into `CrochetGrammar.compile_part` in place of `GeometryEngine`'s hardcoded profile output. Asynchronous swap, mirroring the previous polling pattern (`GET /measured/{session_id}`), so `/generate` returns immediately and the refined-by-measurement pattern lands when the mesh is ready.
- **Extend the vision call** to ask Gemini for a 2D bounding box per part. Providers that don't support bbox output (ollama llava) degrade gracefully — measured-diameter pipeline is skipped for that request, hardcoded profiles stand.
- **Add LLM segmentation robustness**: count parts after the vision call; if below threshold (need at least Head + Body + 2 limb-class parts), silently re-prompt up to 2× with stronger wording. If still under after retries, proceed with what we have.

## Capabilities

### New Capabilities
- `mesh-measured-diameters`: slice the Hunyuan3D `.glb` per part bounding box and emit a real diameter profile that replaces the hardcoded geometric profile, surfaced via async swap on a polling endpoint.
- `llm-segmentation-robustness`: silent retry up to twice when the vision response is missing core body parts.

### Modified Capabilities
- `primitive-labeler`: the Gemini prompt now also requests a normalized 2D bounding box per part; the response schema gains a `bbox` field; providers that don't comply gracefully omit it.
- `primitive-type-routing`: `compile_part` now accepts an optional measured-diameter override; when measured diameters are present for a part, they REPLACE the `GeometryEngine` profile; otherwise the hardcoded path runs unchanged.

### Removed Capabilities
- `seamless-pattern-mode`: the button outputs unusable CrochetPARADE DSL; removed entirely.
- `pattern-refinement-loop`: bounds + quantization make it ineffective; removed in favor of direct measurement.
- `mesh-comparison`: was only used by the refinement loop; no remaining caller.
- `grammar-dot-export`: was only used to feed `graph_standalone`; no remaining caller.
- `external-tool-lifecycle`: no remaining subprocess CLI in use; removed.

## Impact

- **Backend deletions**: `external_tools.py`, `dot_export.py`, `mesh_compare.py`, `refine.py`, `seamless.py`; `/generate-seamless` and `/refine` endpoints; `_refine_after_mesh` coordinator; `check_binaries()` startup call; `_STL_DIR`/`_SEAMLESS_DIR`; imports.
- **Backend additions**: `mesh_measure.py` (load + normalize + per-part vertical-band slicing + cross-section diameters via trimesh); `_measure_after_mesh` async coordinator; `GET /measured/{session_id}` polling endpoint.
- **Vision changes**: `_PARTS_SCHEMA` + Gemini TypedDict in `vision.py` gain optional `bbox` field; `analyze_image` keeps signature; new helper `analyze_with_retry` does the segmentation retry.
- **Frontend**: remove the seamless button + panel + `generateSeamless()`, the refinement badge + `startRefinePolling()`. Add a measurement status badge + `startMeasurePolling()` that swaps the rendered cards (reuse the existing `renderParts` swap).
- **Tests**: delete `test_external_tools.py` (3 tests). Add tests for mesh measurement (synthetic mesh fixture) and the LLM-retry logic.
- **Env**: remove `GRAPH_STANDALONE_BIN`, `CROCHET_REMESH_BIN`, `GRAPH_SOLVER_ITERATIONS` from `.env.example`.
- **No new dependencies** (trimesh already present); no API schema change to `/generate`.
