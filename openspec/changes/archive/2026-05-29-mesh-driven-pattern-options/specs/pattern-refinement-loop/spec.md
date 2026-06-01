## ADDED Requirements

### Requirement: Refinement runs as a background job after the target mesh is ready
After `/generate` returns and the session's Hunyuan3D `.glb` reaches `done`, the backend SHALL start a background refinement job keyed by `session_id`. The job SHALL NOT block `/generate` and SHALL only run when `graph_available` is true.

#### Scenario: Refinement scheduled after mesh completes
- **WHEN** a session's 3D job reaches `done` and `graph_available` is true
- **THEN** a refinement job for that session is created with status `pending`/`running` and `/generate` has already returned

#### Scenario: Refinement skipped without forward renderer
- **WHEN** `graph_available` is false
- **THEN** no refinement job is created and the standard pattern remains the final result

### Requirement: Optimize each part's diameter array against the target mesh
For each part, the job SHALL optimize the diameter array using a gradient-free optimizer, seeded from the GeometryEngine diameters, with the objective being the mesh-comparison shape-distance between the part's forward-rendered simulation and the target. The number of objective evaluations per part SHALL be capped.

#### Scenario: Optimization improves or preserves shape-distance
- **WHEN** a part is optimized
- **THEN** the accepted diameter array's shape-distance is less than or equal to the seed array's shape-distance

#### Scenario: Refined array must compile through the grammar
- **WHEN** an optimized diameter array is produced
- **THEN** it is re-compiled via `CrochetGrammar.compile_part` and only accepted if compilation succeeds; otherwise the original array is kept

### Requirement: Refinement status is queryable and returns refined parts
The backend SHALL expose `GET /refine/{session_id}` returning `{status, refined_parts, error}` where `status` is `pending`|`running`|`done`|`failed`, and `refined_parts` (when `done`) is the same shape as the `/generate` response with updated diameters and instructions. Unknown session IDs SHALL return 404.

#### Scenario: Status while running
- **WHEN** `GET /refine/{session_id}` is called during optimization
- **THEN** the response status is `running` and `refined_parts` is null

#### Scenario: Refined pattern returned when done
- **WHEN** `GET /refine/{session_id}` is called after the job completes
- **THEN** the response status is `done` and `refined_parts` contains per-part name, instructions, diameters, and primitive_type

#### Scenario: Unknown session
- **WHEN** `GET /refine/{session_id}` is called with an unrecognized session id
- **THEN** the response is HTTP 404

### Requirement: Frontend swaps in the refined pattern when ready
After generating a standard pattern, the frontend SHALL poll `GET /refine/{session_id}` and, on `done`, replace the displayed instructions and previews with the refined parts. On `failed` or timeout, the original pattern SHALL remain.

#### Scenario: Pattern swapped on completion
- **WHEN** refinement polling returns `done` with refined parts
- **THEN** the per-part instruction cards and previews update to the refined diameters

#### Scenario: Original kept on failure
- **WHEN** refinement polling returns `failed`
- **THEN** the originally displayed pattern remains unchanged
