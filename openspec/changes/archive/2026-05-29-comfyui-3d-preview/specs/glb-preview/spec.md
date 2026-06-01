## ADDED Requirements

### Requirement: Combined preview shows LatheGeometry immediately after generation
After `/generate` returns, the frontend SHALL render the existing LatheGeometry combined scene at `#combined-preview` without waiting for the `.glb`. This ensures the user has immediate visual feedback.

#### Scenario: LatheGeometry renders on pattern response
- **WHEN** `/generate` returns pattern data
- **THEN** `buildCombinedScene(data)` is called and the LatheGeometry scene is visible within one render frame

### Requirement: Frontend polls for 3D generation status
After `/generate` returns, the frontend SHALL begin polling `GET /preview/{session_id}` at 4-second intervals. While polling, a status badge SHALL display "3D preview generating…" near the combined preview. Polling SHALL stop when status is `done`, `failed`, or after 10 minutes (150 ticks).

#### Scenario: Polling starts after generate
- **WHEN** `/generate` returns successfully
- **THEN** the frontend starts polling `/preview/{session_id}` every 4 seconds

#### Scenario: Polling stops on timeout
- **WHEN** 150 poll ticks elapse without a `done` or `failed` response
- **THEN** polling stops and the LatheGeometry scene remains

### Requirement: Combined preview swaps to GLB render when ready
When `GET /preview/{session_id}` returns `status: "done"`, the frontend SHALL stop polling, clear `#combined-preview`, and load the `.glb` via `GLTFLoader`. The loaded scene SHALL be centered, auto-rotated, and controllable via `OrbitControls`. The status badge SHALL be removed.

#### Scenario: GLB loads successfully
- **WHEN** poll returns `{status: "done", glb_url: "/models/{session_id}.glb"}`
- **THEN** `#combined-preview` is replaced with a GLTFLoader render of the mesh with OrbitControls and auto-rotation

#### Scenario: GLTFLoader import path
- **WHEN** the GLB preview function is called
- **THEN** `GLTFLoader` is imported from `three/addons/loaders/GLTFLoader.js` via the existing importmap (no new CDN URLs required)

### Requirement: LatheGeometry scene is the fallback on generation failure
If the poll returns `status: "failed"`, the frontend SHALL stop polling, remove the status badge, and leave the LatheGeometry combined scene visible. No error message is shown in the main UI (failure is silent to the user — the preview is still useful).

#### Scenario: Generation fails
- **WHEN** poll returns `{status: "failed"}`
- **THEN** polling stops, status badge disappears, LatheGeometry combined scene remains unchanged

### Requirement: Per-part previews are unaffected
The per-part LatheGeometry canvas previews SHALL continue to render using `createScene(canvas, diameters)` exactly as before. The GLB preview and polling logic SHALL not modify or replace per-part canvases.

#### Scenario: Per-part canvases render independently
- **WHEN** pattern data is returned
- **THEN** each part card's canvas renders a LatheGeometry preview regardless of 3D generation status
