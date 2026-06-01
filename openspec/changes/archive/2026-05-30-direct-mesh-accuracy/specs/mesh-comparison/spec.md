## REMOVED Requirements

### Requirement: Normalize meshes before comparison
**Reason**: Mesh normalization was a supporting utility for the refinement loop's comparison objective. With refinement removed, no caller remains.
**Migration**: Removed. The mesh-measurement module (`backend/mesh_measure.py`) has its own narrower normalization (PCA-align principal axis vertical, center, no need for unit scaling) and does not import this module.

### Requirement: Compute shape-distance via multi-angle silhouette overlap
**Reason**: The only consumer was the refinement loop's optimizer objective. No comparisons happen in the new pipeline — measurement produces diameters directly.
**Migration**: Removed.

### Requirement: Comparison returns a single scalar suitable for optimization
**Reason**: No optimization loop remains.
**Migration**: Removed. `backend/mesh_compare.py` is deleted.
