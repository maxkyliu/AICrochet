## MODIFIED Requirements

### Requirement: Generate a one-piece seamless pattern from the session mesh
The backend SHALL expose `POST /generate-seamless/{session_id}` that converts the session's Hunyuan3D `.glb` to STL, runs `crochet_remesh` on it, and returns the readable CrochetPARADE-DSL pattern text. The endpoint SHALL require `remesh_available` to be true. The returned text SHALL be the value of the top-level `crochetparade` field from the remesher's pattern JSON output (the readable DSL using `sc`/`scinc`/`scdec`/`ch`/`DEF:`/`COLOR:` tokens), not the raw `traversals.sequence` op-token array. If the `crochetparade` field is absent or empty, the backend MAY fall back to returning the pattern JSON as a degraded form, but normal operation SHALL surface the DSL.

#### Scenario: Seamless pattern generated returns DSL
- **WHEN** `POST /generate-seamless/{session_id}` is called and the session `.glb` exists
- **THEN** the `.glb` is converted to STL, `crochet_remesh` is run, and the response contains the readable CrochetPARADE-DSL text (with stitch tokens such as `sc`, `scinc`, `scdec`, `ch`, and any `DEF:`/`COLOR:` directives), not the raw op-token sequence

#### Scenario: Mesh not ready yet
- **WHEN** the endpoint is called before the session `.glb` has reached `done`
- **THEN** the response is HTTP 409 indicating the mesh is not ready

#### Scenario: Missing DSL field falls back rather than failing
- **WHEN** the remesher pattern JSON does not contain a `crochetparade` field
- **THEN** the endpoint returns a non-empty pattern text (degraded form) without raising a 500

### Requirement: GLB-to-STL conversion for the remesher
The backend SHALL convert the session `.glb` to a watertight STL at `backend/output/stl/{session_id}.stl` before invoking the remesher, since the remesher consumes STL and assumes a closed surface.

#### Scenario: STL written before remesher runs
- **WHEN** seamless generation proceeds
- **THEN** an STL file is produced from the `.glb` and passed to `crochet_remesh`

### Requirement: Seamless output is displayed as a distinct pattern style with framing
The frontend SHALL provide a "Generate One-Piece Pattern" button alongside the existing "Generate Pattern" button. The button SHALL be disabled until the session `.glb` is ready. Seamless output SHALL be shown in its own results panel as CrochetPARADE-DSL text, separate from the per-part amigurumi cards. The panel SHALL prepend a short plain-English framing header that: (1) names the pattern as a one-piece seamless construction in CrochetPARADE notation, (2) states the approximate total stitch count, and (3) instructs the user to paste the text into crochetparade.org to render and follow it visually.

#### Scenario: Button enabled when mesh ready
- **WHEN** `/preview/{session_id}` reports `done`
- **THEN** the "Generate One-Piece Pattern" button becomes enabled

#### Scenario: Seamless panel shows framing header
- **WHEN** the seamless pattern is returned and rendered
- **THEN** the panel contains a plain-English header explaining that the body is CrochetPARADE notation, the total stitch count, and a `crochetparade.org` instruction line before the DSL text

#### Scenario: Seamless result shown separately
- **WHEN** the seamless pattern is returned
- **THEN** it is rendered in a dedicated panel, leaving the multi-part cards intact
