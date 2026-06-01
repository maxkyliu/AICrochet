## REMOVED Requirements

### Requirement: Refinement runs as a background job after the target mesh is ready
**Reason**: The loop is ineffective in practice — bounded by ±40% per-diameter limits AND multiples-of-6 stitch quantization, so candidate moves rarely cross a stitch-count boundary. Verified on fox.jpg: refined Head differed from seed only in two middle rounds (`7.96, 7.9, 7.93` → `7.96, 8.69, 8.73`), no structural change. Replaced by direct mesh measurement, which restructures the diameter array using real cross-sections instead of nudging it.
**Migration**: `backend/refine.py` is deleted; the `_refine_after_mesh` coordinator and the refinement scheduling block inside `/generate` are removed. Direct mesh measurement (`mesh-measured-diameters` capability) is the replacement accuracy path.

### Requirement: Optimize each part's diameter array against the target mesh
**Reason**: See above — the optimizer's effective search space (within bounds + grammar quantization) is too narrow to produce meaningful improvements.
**Migration**: Removed. Direct measurement supersedes per-part optimization.

### Requirement: Refinement status is queryable and returns refined parts
**Reason**: No more job to query.
**Migration**: `GET /refine/{session_id}` endpoint is removed. The new `mesh-measured-diameters` capability exposes a similar `GET /measured/{session_id}` polling endpoint with the same response shape (status, parts, error).

### Requirement: Frontend swaps in the refined pattern when ready
**Reason**: No more refined pattern to swap.
**Migration**: `startRefinePolling()` and the refinement status badge are removed. The new measurement-swap polling reuses the same `renderParts` swap mechanism with a new status badge.
