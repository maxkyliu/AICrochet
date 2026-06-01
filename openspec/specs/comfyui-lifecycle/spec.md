## ADDED Requirements

### Requirement: ComfyUI starts on application startup
The backend SHALL check whether ComfyUI is reachable at `COMFYUI_URL` (default `http://127.0.0.1:8188`) during FastAPI startup. If unreachable, it SHALL spawn ComfyUI as a subprocess using the venv Python at `~/comfyui-env/bin/python` running `~/ComfyUI/main.py --port <port>`. The spawned process handle SHALL be stored for later shutdown. If Node.js < 22 or `node` is absent, 3D generation SHALL be disabled with a logged warning; pattern generation SHALL still work.

#### Scenario: ComfyUI not running at startup
- **WHEN** AICrochet starts and `GET /system_stats` at `COMFYUI_URL` fails or times out
- **THEN** the backend spawns ComfyUI as a subprocess and logs "Started ComfyUI (PID: <n>)"

#### Scenario: ComfyUI already running at startup
- **WHEN** AICrochet starts and `GET /system_stats` returns HTTP 200
- **THEN** the backend logs "ComfyUI already running — skipping launch" and stores no subprocess handle

#### Scenario: Node.js absent or too old
- **WHEN** AICrochet starts and `node --version` returns a version < 22 or exits non-zero
- **THEN** the backend logs a warning and sets a flag that disables 3D generation; the `/generate` endpoint still returns pattern data

### Requirement: ComfyUI stops on application shutdown
The backend SHALL terminate the ComfyUI subprocess it started (and only that subprocess) on FastAPI shutdown. It SHALL call `terminate()` followed by `wait(timeout=10)`. If the process does not exit within 10 seconds, it SHALL call `kill()`.

#### Scenario: Graceful shutdown
- **WHEN** AICrochet shuts down and it started ComfyUI
- **THEN** the backend sends SIGTERM to the ComfyUI process and waits up to 10 s for it to exit

#### Scenario: Shutdown when ComfyUI was pre-existing
- **WHEN** AICrochet shuts down and ComfyUI was already running before AICrochet started
- **THEN** the backend does NOT terminate the ComfyUI process

### Requirement: ComfyUI health is checked before each 3D generation job
Before spawning a generation job, the backend SHALL verify ComfyUI is reachable. If unreachable, the job SHALL be set to `failed` status immediately with a descriptive error message.

#### Scenario: ComfyUI unreachable at generation time
- **WHEN** `/generate` is called and the subsequent ComfyUI health check fails
- **THEN** the session entry is set to `{status: "failed", error: "ComfyUI unreachable"}` and the pattern response is returned normally
