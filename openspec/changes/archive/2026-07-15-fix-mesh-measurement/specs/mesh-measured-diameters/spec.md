# mesh-measured-diameters — Delta Specification

## MODIFIED Requirements

### Requirement: Derive per-part diameters from the session mesh by vertical band slicing
The backend SHALL provide a function `measure_part(mesh, bbox, n_slices=None)` that, given a normalized mesh and a part's 2D bounding box in image coordinates `[x_min, y_min, x_max, y_max]` (normalized 0..1), returns a list of float diameter values: it maps the bbox's `y_min`/`y_max` onto the mesh's vertical extent, takes N equally-spaced horizontal cross-sections within that band, and at each slice measures the diameter from the cross-section's horizontal extent (bounding-box diameter, not fitted circle). Each cross-section SHALL be restricted to vertices whose x-coordinate falls inside the part's bbox `x_min`/`x_max` mapped onto the mesh's x-extent, expanded by a small tolerance margin (~5% of the mesh's x-extent); vertices outside the window SHALL NOT contribute to the diameter. The z-extent remains unconstrained. The function SHALL skip slices with no intersection or with fewer than 2 in-window vertices, and SHALL never raise on degenerate input — it returns an empty list instead.

#### Scenario: Bbox y-range maps to mesh vertical band
- **WHEN** `measure_part` is called with a bbox whose `y_min`/`y_max` cover the upper third of the image
- **THEN** the slices are taken from the upper third of the mesh's vertical extent (image-y points down; mesh-y after PCA alignment points up)

#### Scenario: Bboxes are rescaled to subject-relative coordinates before mapping
- **WHEN** the subject occupies only a sub-range of the photo frame (bbox union smaller than 0..1)
- **THEN** the coordinator rescales all bboxes so their union spans 0..1 in x and y before orientation checking and measurement, because the mesh spans exactly the subject rather than the photo frame

#### Scenario: Geometry outside the bbox x-window is excluded
- **WHEN** the mesh has geometry at a slice height that lies outside the part's bbox x-window (e.g. an arm beside the body)
- **THEN** that geometry does not contribute to the measured diameter for the part

#### Scenario: Cross-section diameter uses bounding-box extent of in-window vertices
- **WHEN** a slice intersects the mesh in a polyline
- **THEN** the returned diameter for that slice is the maximum of the in-window vertices' x-extent and z-extent (not a fitted-circle radius)

#### Scenario: Degenerate input does not raise
- **WHEN** the bbox falls outside the mesh's vertical extent, or no slice has at least 2 in-window vertices
- **THEN** the function returns an empty list without raising

### Requirement: Mesh is normalized before measurement
The backend SHALL provide `load_normalized_mesh(glb_path)` that loads the GLB via `trimesh`, centers it at the origin, and aligns its dominant principal axis to vertical (+Y). The function SHALL NOT rescale to unit dimensions — absolute mesh dimensions are preserved so measured diameters retain physical meaning relative to one another within the same mesh. Because the PCA eigenvector sign is arbitrary, the backend SHALL disambiguate vertical orientation by comparing the mesh's width-per-height profile against the width profile predicted from the parts' bounding boxes, flipping the mesh about y when the flipped correlation is higher, and SHALL report an orientation confidence score.

#### Scenario: Mesh is centered and upright
- **WHEN** `load_normalized_mesh` is called on a session GLB
- **THEN** the returned mesh has its centroid at the origin and its principal axis aligned to +Y

#### Scenario: Upside-down PCA alignment is corrected
- **WHEN** the PCA alignment leaves the mesh inverted relative to the photo's part layout (e.g. widest part at the top while the bboxes place it at the bottom)
- **THEN** the mesh is flipped about y before measurement so bands map to the intended parts

### Requirement: Per-part measurement failure falls back to the hardcoded part
The backend SHALL recompile each part's instructions from the regularized measured profile via `CrochetGrammar.compile_part`, passing through the existing `primitive_type`. A part's measurement SHALL be rejected — retaining the initial-estimate part — when any of the following hold: the measured array is empty; any value is zero or negative; the measured length differs from the part's initial profile round count by more than ±50%; or the regularized profile fails the swap quality gate. A direction-flip fraction above 30% does NOT reject the part; it forces the shape-blend weight α to 0 (see regularization requirement) so the measurement contributes amplitude only. The sanity check's expected length SHALL come from the initial profile's round count for that part, not from the measured array itself.

#### Scenario: Failed measurement keeps the original part
- **WHEN** `measure_part` returns an empty list for a given part
- **THEN** the response's `parts` entry for that part is the original initial-estimate version, not omitted

#### Scenario: Length drift is caught against the initial profile
- **WHEN** a part's initial profile has 12 rounds and the measurement yields 4 values
- **THEN** the measurement is rejected and the initial-estimate part is retained

## REMOVED Requirements

### Requirement: Measured diameters are calibrated against the hardcoded max
**Reason**: The single global factor `hardcoded_max / measured_max` divides by the most-inflated measurement, propagating one contaminated part's error to every part in the session.
**Migration**: Replaced by "Measured diameters are calibrated by the median per-part ratio against the initial estimate" below; no API or data migration required.

## ADDED Requirements

### Requirement: Measured diameters are calibrated by the median per-part ratio against the initial estimate
Hunyuan3D meshes have no absolute scale. The measurement coordinator SHALL collect raw measurements for all measurable parts first, compute each part's ratio `initial_profile_max / measured_max`, and apply the median of those ratios as a single session scale factor to every measured array before regularization and recompilation. This preserves the mesh's relative proportions between parts while remaining robust to a single inflated measurement.

#### Scenario: One inflated part does not shrink the others
- **WHEN** one part's raw measurement is inflated relative to its initial profile while the other parts' ratios agree
- **THEN** the session scale factor equals the median ratio, and the non-inflated parts' calibrated diameters land near their initial-profile range

### Requirement: Measured profiles are regularized against the primitive's prototype shape
For each measured part, the coordinator SHALL construct the recompilation profile by blending the calibrated measured curve with the part's market prototype curve (or the hardcoded profile when no prototype exists for the primitive type), both resampled to the target round count: `profile = α·measured + (1−α)·prototype` with `α` configurable via environment (`MESH_BLEND_ALPHA`, default 0.5). When the measured curve fails smoothness checks, α SHALL be treated as 0 (prototype shape, measured amplitude only).

#### Scenario: Noisy measured shape falls back to prototype shape
- **WHEN** a part's calibrated measurement passes the length check but exceeds the direction-flip threshold
- **THEN** the recompiled profile uses the prototype's shape scaled to the measured amplitude

#### Scenario: Primitive without a prototype uses the hardcoded profile as regularizer
- **WHEN** a measured part's primitive type has no entry in `market_profiles.json`
- **THEN** the blend regularizer is the hardcoded profile for that primitive at the part's scale

### Requirement: Recompiled round count derives from calibrated amplitude
The recompiled part's round count SHALL be derived from the calibrated maximum diameter using the same rounds-per-stitch rule the market prototype path uses (`rounds_per_max × max_stitches`, clamped to the engine's round bounds), not from the number of mesh slices taken.

#### Scenario: Large part gets a proportionally long profile
- **WHEN** a part's calibrated max diameter corresponds to 36 stitches and its primitive's `rounds_per_max` is 0.4
- **THEN** the recompiled profile has approximately 14 rounds regardless of how many slices the mesh band produced

### Requirement: Measured swap is quality-gated per part
Before a measurement job stores `done` parts, the coordinator SHALL score each measured part by the mean absolute error between its unit-amplitude regularized profile and the primitive's unit-amplitude reference shape. A part whose MAE exceeds 0.25 SHALL retain its initial-estimate version. (The measured curve's direction-flip fraction is enforced upstream: above 0.30 the blend weight α is forced to 0, making the regularized shape equal the reference shape.) When the session's orientation confidence is below threshold, the job SHALL complete with status `done` and the original parts, so the frontend swap is a no-op rather than a degradation.

#### Scenario: Gated part keeps the initial estimate
- **WHEN** a measured part's unit-amplitude MAE against the reference shape exceeds 0.25
- **THEN** the `done` response contains the initial-estimate version of that part

#### Scenario: Low orientation confidence skips the whole swap
- **WHEN** the orientation check's correlation is below the confidence threshold in both orientations
- **THEN** the measurement job completes with the original parts and no measured recompilation is attempted
