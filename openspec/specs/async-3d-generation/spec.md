## ADDED Requirements

### Requirement: Uploaded image is persisted for async processing
The `/generate` endpoint SHALL save the uploaded image bytes to `backend/output/uploads/{session_id}.jpg` before spawning the async 3D job. The `session_id` SHALL be a UUID supplied as a form field by the client (same session_id already used for feedback attribution).

#### Scenario: Image saved before async job starts
- **WHEN** `/generate` is called with a valid image file and session_id
- **THEN** the image is written to `backend/output/uploads/{session_id}.jpg` before the async task is created

### Requirement: 3D generation job runs asynchronously after pattern generation
The `/generate` endpoint SHALL return the pattern response immediately upon completion of the LLM + grammar pipeline. It SHALL then create an `asyncio` background task that runs `image-to-3d.mjs` via subprocess. The `COMFYUI_3D_STEPS` env var (default `20`) controls the `--steps` argument.

#### Scenario: Pattern returned while 3D generates
- **WHEN** `/generate` is called
- **THEN** the pattern JSON is returned without waiting for the 3D job to complete

#### Scenario: 3D job completes successfully
- **WHEN** `image-to-3d.mjs` exits with code 0 and the output `.glb` file exists
- **THEN** the session entry is updated to `{status: "done", glb_url: "/models/{session_id}.glb"}`

#### Scenario: 3D job fails
- **WHEN** `image-to-3d.mjs` exits with non-zero code or the output `.glb` is not created
- **THEN** the session entry is updated to `{status: "failed", error: <stderr tail>}`

### Requirement: Session status is queryable via GET /preview/{session_id}
The endpoint SHALL return a JSON object: `{status: "pending"|"generating"|"done"|"failed", glb_url: string|null, error: string|null}`. Status `pending` means the job is queued but not yet running. Status `generating` means `image-to-3d.mjs` is running. Unknown session_ids SHALL return 404.

#### Scenario: Status before job starts
- **WHEN** `GET /preview/{session_id}` is called immediately after `/generate`
- **THEN** response is `{status: "pending", glb_url: null, error: null}`

#### Scenario: Status when done
- **WHEN** `GET /preview/{session_id}` is called after generation completes
- **THEN** response is `{status: "done", glb_url: "/models/{session_id}.glb", error: null}`

#### Scenario: Unknown session
- **WHEN** `GET /preview/{session_id}` is called with an unrecognised session_id
- **THEN** response is HTTP 404

### Requirement: Generated .glb files are served via /models static mount
The `backend/output/models/` directory SHALL be mounted as FastAPI `StaticFiles` at the `/models` path. The directory SHALL be created automatically if absent.

#### Scenario: GLB accessible after generation
- **WHEN** a generation job completes and `glb_url` is `/models/{session_id}.glb`
- **THEN** `GET /models/{session_id}.glb` returns the binary GLB file with `Content-Type: model/gltf-binary`
