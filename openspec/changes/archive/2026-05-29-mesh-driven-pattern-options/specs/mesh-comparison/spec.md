## ADDED Requirements

### Requirement: Normalize meshes before comparison
The system SHALL normalize any two meshes before comparing them: translate each to center its bounding box at the origin, scale each to a unit bounding-box diagonal, and align each so its dominant principal axis is vertical. Comparison SHALL operate only on normalized meshes.

#### Scenario: Differing scale and position are removed
- **WHEN** two meshes of the same shape but different absolute scale and position are normalized
- **THEN** their normalized forms have matching bounding-box diagonals and centered origins

### Requirement: Compute shape-distance via multi-angle silhouette overlap
The system SHALL compute a scalar shape-distance between two normalized meshes by rendering each orthographically from N=4 viewpoints spaced 90° around the vertical axis, rasterizing each view to a binary silhouette mask, computing intersection-over-union (IoU) per view, and returning `1 − mean(IoU)`. A distance of 0 means identical silhouettes; 1 means no overlap.

#### Scenario: Identical meshes score zero distance
- **WHEN** a mesh is compared to a copy of itself
- **THEN** the shape-distance is approximately 0

#### Scenario: Dissimilar meshes score higher distance
- **WHEN** a sphere mesh is compared to a tall thin cylinder mesh of equal bounding-box diagonal
- **THEN** the shape-distance is substantially greater than for two similar spheres

### Requirement: Comparison returns a single scalar suitable for optimization
The comparison function SHALL return one finite float in [0, 1] so it can serve directly as an optimizer objective. Degenerate inputs (empty mask, zero-area mesh) SHALL return a large finite penalty rather than raising.

#### Scenario: Degenerate mesh yields penalty not crash
- **WHEN** one input rasterizes to an empty silhouette
- **THEN** the function returns a large finite distance (e.g. 1.0) without raising
