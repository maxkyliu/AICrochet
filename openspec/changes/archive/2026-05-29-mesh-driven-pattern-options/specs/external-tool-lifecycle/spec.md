## ADDED Requirements

### Requirement: External GPL binaries are health-checked at startup
The backend SHALL resolve the paths to two external CLI binaries at startup — `graph_standalone` (from `GRAPH_STANDALONE_BIN` env var or a conventional build path) and `crochet_remesh` (from `CROCHET_REMESH_BIN` or build path) — verify each executes, and set module-level availability flags `graph_available` and `remesh_available`. Resolution and verification SHALL NOT raise; failures set the flag to false and log a warning.

#### Scenario: Both binaries present
- **WHEN** the backend starts and both binaries execute successfully
- **THEN** `graph_available` and `remesh_available` are both true and the refinement and seamless features are enabled

#### Scenario: A binary is missing or non-executable
- **WHEN** the backend starts and `crochet_remesh` cannot be resolved or fails to execute
- **THEN** `remesh_available` is set to false, a warning is logged, and startup completes normally

### Requirement: Features degrade gracefully when their binary is unavailable
Endpoints that depend on an external binary SHALL check the relevant availability flag and return a clear unavailable response instead of erroring. The standard `/generate` pattern path SHALL be unaffected by the absence of either binary.

#### Scenario: Seamless requested without remesher
- **WHEN** `POST /generate-seamless/{session_id}` is called and `remesh_available` is false
- **THEN** the response is HTTP 503 with a message indicating the seamless feature is unavailable

#### Scenario: Standard pattern unaffected by missing binaries
- **WHEN** both binaries are unavailable and `POST /generate` is called
- **THEN** the standard multi-part pattern is generated and returned normally

### Requirement: Subprocess-only invocation preserves license separation
The backend SHALL invoke both binaries only via subprocess execution and SHALL NOT import, link, or embed their source. `graph_standalone` requires a minimal build-time patch to read its graph from stdin (its stdin read is commented out upstream); this patch modifies the external GPL program, not AICrochet, and is applied by the build script. The setup process SHALL record each binary's upstream source URL, license text, and the applied patch to satisfy GPL distribution obligations (including offering the modified `graph_standalone` source).

#### Scenario: Binaries invoked as subprocesses
- **WHEN** either external tool is used during a request
- **THEN** it is run via a subprocess call (e.g. `asyncio.create_subprocess_exec`) and its output captured from stdout, with no AICrochet module importing GPL source

#### Scenario: graph_standalone reads stdin after patch
- **WHEN** the build script builds `graph_standalone`
- **THEN** it first applies the stdin patch so the compiled binary reads its graph from standard input
