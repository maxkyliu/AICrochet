## ADDED Requirements

### Requirement: Generate a one-piece seamless pattern from the session mesh
The backend SHALL expose `POST /generate-seamless/{session_id}` that converts the session's Hunyuan3D `.glb` to STL, runs `crochet_remesh` on it, and returns the resulting CrochetPARADE-DSL pattern as text. The endpoint SHALL require `remesh_available` to be true.

#### Scenario: Seamless pattern generated
- **WHEN** `POST /generate-seamless/{session_id}` is called and the session `.glb` exists
- **THEN** the `.glb` is converted to STL, `crochet_remesh` is run, and the response contains the CrochetPARADE-DSL pattern text

#### Scenario: Mesh not ready yet
- **WHEN** the endpoint is called before the session `.glb` has reached `done`
- **THEN** the response is HTTP 409 indicating the mesh is not ready

### Requirement: GLB-to-STL conversion for the remesher
The backend SHALL convert the session `.glb` to a watertight STL at `backend/output/stl/{session_id}.stl` before invoking the remesher, since the remesher consumes STL and assumes a closed surface.

#### Scenario: STL written before remesher runs
- **WHEN** seamless generation proceeds
- **THEN** an STL file is produced from the `.glb` and passed to `crochet_remesh`

### Requirement: Seamless output is displayed as a distinct pattern style
The frontend SHALL provide a "Generate One-Piece Pattern" button alongside the existing "Generate Pattern" button. The button SHALL be disabled until the session `.glb` is ready. Seamless output SHALL be shown in its own results panel as CrochetPARADE-DSL text, separate from the per-part amigurumi cards.

#### Scenario: Button enabled when mesh ready
- **WHEN** `/preview/{session_id}` reports `done`
- **THEN** the "Generate One-Piece Pattern" button becomes enabled

#### Scenario: Seamless result shown separately
- **WHEN** the seamless pattern is returned
- **THEN** it is rendered in a dedicated panel as CP-DSL text, leaving the multi-part cards intact
