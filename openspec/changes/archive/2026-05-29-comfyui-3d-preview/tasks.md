## 1. Project scaffolding

- [x] 1.1 Add `backend/output/` to `.gitignore` (uploads/ and models/ subdirs are ephemeral)
- [x] 1.2 Create `backend/comfyui.py` module skeleton (empty functions: `start`, `stop`, `is_running`, `check_node`)

## 2. ComfyUI lifecycle management (backend/comfyui.py)

- [x] 2.1 Implement `is_running()` — GET `/system_stats` with 5 s timeout, returns bool
- [x] 2.2 Implement `check_node()` — run `node --version`, return version string or None; log warning if < 22 or absent
- [x] 2.3 Implement `start()` — if not `is_running()`, spawn `Popen(["~/comfyui-env/bin/python", "main.py", "--port", PORT], cwd="~/ComfyUI")`; store handle; log PID
- [x] 2.4 Implement `stop()` — if handle exists and process is alive, call `terminate()` + `wait(10)`, then `kill()` on timeout

## 3. In-memory job tracker (backend/comfyui.py)

- [x] 3.1 Add module-level `_jobs: dict[str, dict]` with thread-safe access pattern
- [x] 3.2 Implement `create_job(session_id)` → sets `{status:"pending", glb_url:None, error:None}`
- [x] 3.3 Implement `update_job(session_id, **kwargs)` → merges kwargs into existing entry
- [x] 3.4 Implement `get_job(session_id)` → returns dict or None

## 4. Async 3D generation (backend/comfyui.py)

- [x] 4.1 Implement `generate_3d(session_id, image_path, output_path)` — async function that:
  - Checks `is_running()`, sets failed if not
  - Updates job to `generating`
  - Runs `asyncio.create_subprocess_exec("node", IMAGE_TO_3D_SCRIPT, "--input", image_path, "--output", output_path, "--steps", STEPS)`
  - On exit code 0 + file exists → update job to `done` with `glb_url`
  - On failure → update job to `failed` with last 500 chars of stderr
- [x] 4.2 Add constants: `IMAGE_TO_3D_SCRIPT` path, `COMFYUI_URL` (from env), `COMFYUI_3D_STEPS` (from env, default `"20"`)

## 5. Wire lifecycle into main.py

- [x] 5.1 Add FastAPI `@app.on_event("startup")` handler: call `comfyui.check_node()`, then `comfyui.start()`
- [x] 5.2 Add FastAPI `@app.on_event("shutdown")` handler: call `comfyui.stop()`
- [x] 5.3 Mount `backend/output/models/` as `StaticFiles` at `/models` (auto-create dir)

## 6. New endpoints in main.py

- [x] 6.1 Add `GET /preview/{session_id}` endpoint — returns `comfyui.get_job(session_id)` or 404
- [x] 6.2 In `/generate`: save image bytes to `backend/output/uploads/{session_id}.jpg` (accept `session_id` as optional Form field; generate one if absent)
- [x] 6.3 In `/generate`: after pattern results are assembled, call `asyncio.create_task(comfyui.generate_3d(...))` if node is available

## 7. Frontend — polling and status badge

- [x] 7.1 Add `import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'` to the module script
- [x] 7.2 Add `startPreviewPolling(sessionId)` function — `setInterval` every 4 s, max 150 ticks, calls `GET /preview/{sessionId}`
- [x] 7.3 Add status badge element (e.g., `<div id="preview-status">`) rendered above `#combined-preview`; show/hide text during polling

## 8. Frontend — GLB scene render

- [x] 8.1 Implement `buildGlbScene(glbUrl)` — clears `#combined-preview`, creates a canvas, loads GLB with `GLTFLoader`, sets up scene/camera/lights/OrbitControls/auto-rotation, matches existing canvas dimensions (860×320)
- [x] 8.2 In `generatePattern()`: call `buildCombinedScene(data)` immediately as before, then call `startPreviewPolling(sessionId)` 
- [x] 8.3 In polling callback: on `done` → call `buildGlbScene(glbUrl)` and remove status badge; on `failed` → stop polling and remove status badge; on timeout → stop polling and remove status badge

## 9. Integration test

- [x] 9.1 Manual test: start AICrochet, verify ComfyUI auto-starts (check logs for PID)
- [x] 9.2 Manual test: upload fox.jpg, verify pattern returns immediately, combined LatheGeometry scene appears
- [x] 9.3 Manual test: wait for polling to resolve `done`, verify combined preview swaps to rotating GLB mesh
- [x] 9.4 Manual test: stop AICrochet, verify ComfyUI process is terminated
