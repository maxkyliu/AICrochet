## ADDED Requirements

### Requirement: Derive per-part diameters from the session mesh by vertical band slicing
The backend SHALL provide a function `measure_part(mesh, bbox, n_slices=None)` that, given a normalized mesh and a part's 2D bounding box in image coordinates `[x_min, y_min, x_max, y_max]` (normalized 0..1), returns a list of float diameter values: it maps the bbox's `y_min`/`y_max` onto the mesh's vertical extent, takes N equally-spaced horizontal cross-sections within that band, and at each slice measures the diameter from the cross-section's horizontal extent (bounding-box diameter, not fitted circle). The function SHALL skip slices with no intersection and SHALL never raise on degenerate input — it returns an empty list instead.

#### Scenario: Bbox y-range maps to mesh vertical band
- **WHEN** `measure_part` is called with a bbox whose `y_min`/`y_max` cover the upper third of the image
- **THEN** the slices are taken from the upper third of the mesh's vertical extent (image-y points down; mesh-y after PCA alignment points up)

#### Scenario: Cross-section diameter uses bounding-box extent
- **WHEN** a slice intersects the mesh in a polyline
- **THEN** the returned diameter for that slice is the maximum of the polyline's x-extent and z-extent (not a fitted-circle radius)

#### Scenario: Degenerate input does not raise
- **WHEN** the bbox falls outside the mesh's vertical extent, or the mesh has no intersection at any slice
- **THEN** the function returns an empty list without raising

### Requirement: Mesh is normalized before measurement
The backend SHALL provide `load_normalized_mesh(glb_path)` that loads the GLB via `trimesh`, centers it at the origin, and aligns its dominant principal axis to vertical (+Y). The function SHALL NOT rescale to unit dimensions — absolute mesh dimensions are preserved so measured diameters retain physical meaning.

#### Scenario: Mesh is centered and upright
- **WHEN** `load_normalized_mesh` is called on a session GLB
- **THEN** the returned mesh has its centroid at the origin and its principal axis aligned to +Y

### Requirement: Slice count scales with part band height
The default `n_slices` SHALL be `max(4, round(band_height * SLICE_DENSITY))` where `band_height` is the part's vertical extent in mesh units and `SLICE_DENSITY` is a tunable constant calibrated so a full-doll-height part receives ~10 slices.

#### Scenario: Tall part gets more slices than short part
- **WHEN** two parts on the same mesh have different bbox y-ranges
- **THEN** the part with the larger y-range receives a larger `n_slices` (with the floor of 4)

### Requirement: Measured pattern is delivered via async polling endpoint
The backend SHALL expose `GET /measured/{session_id}` returning `{status, parts, error}` where `status` is `pending`|`running`|`done`|`failed` and `parts` (when `done`) has the same shape as the `/generate` response (each part has `name`, `instructions`, `diameters`, `primitive_type`). Unknown session IDs SHALL return HTTP 404.

#### Scenario: Status while running
- **WHEN** `GET /measured/{session_id}` is called during measurement
- **THEN** the response status is `running` and `parts` is null

#### Scenario: Measured parts returned when done
- **WHEN** measurement completes successfully
- **THEN** the response status is `done` and `parts` contains the per-part instructions recompiled from the measured diameters

#### Scenario: Unknown session
- **WHEN** the endpoint is called with a session id with no measurement job
- **THEN** the response is HTTP 404

### Requirement: Measurement runs only after the session mesh is ready
The backend SHALL schedule the measurement background job after the session's Hunyuan3D `.glb` reaches `done`. The job SHALL NOT block `/generate`. If the LLM response contained no bounding boxes for any part, the measurement job SHALL NOT be scheduled.

#### Scenario: Scheduled after mesh ready
- **WHEN** the session's 3D job reaches `done` and at least one part has a bbox
- **THEN** a measurement job for that session is created with status `pending`/`running`

#### Scenario: Skipped when no bboxes
- **WHEN** the LLM response contained no `bbox` field on any part
- **THEN** no measurement job is created and `GET /measured/{session_id}` returns 404

### Requirement: Per-part measurement failure falls back to the hardcoded part
The backend SHALL recompile each part's instructions from the measured diameters via `CrochetGrammar.compile_part`, passing through the existing `primitive_type`. If measurement returns an empty array, or the recompiled pattern would be obviously worse (zero/negative diameters, wildly non-monotonic where the seed was smooth, length differs from `n_slices` by more than 50%), the original hardcoded-geometry part SHALL be retained for that part.

#### Scenario: Failed measurement keeps the original part
- **WHEN** `measure_part` returns an empty list for a given part
- **THEN** the response's `parts` entry for that part is the original hardcoded-geometry version, not omitted

### Requirement: Frontend swaps in the measured pattern when ready
The frontend SHALL poll `GET /measured/{session_id}` after a standard pattern is generated, display a measurement status badge during polling, and on `done` swap the per-part cards + previews using the existing `renderParts` mechanism. On `failed` or timeout, the original pattern remains and the badge is hidden.

#### Scenario: Pattern swapped on completion
- **WHEN** measurement polling returns `done` with parts
- **THEN** the per-part cards update to the measured diameters and the badge is hidden

#### Scenario: Original kept on failure
- **WHEN** polling returns `failed` or 150 ticks elapse without `done`
- **THEN** the displayed pattern remains unchanged and the badge is hidden
