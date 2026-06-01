## Context

AICrochet is a FastAPI backend + vanilla JS frontend with no build step. The combined 3D preview renders procedural LatheGeometry via Three.js. ComfyUI is already installed at `~/ComfyUI` with Hunyuan3D model and custom nodes present. A standalone Node.js script (`image-to-3d.mjs` from image-blaster) bridges to ComfyUI's REST+WebSocket API and outputs a `.glb` file. Pattern generation takes ~2–5 s; 3D generation takes 45–62 s warm, ~2 min cold.

The core challenge is coordinating two very different latencies: the synchronous pattern pipeline (fast) and the 3D generation (slow). The frontend must not be blocked waiting for the mesh.

## Goals / Non-Goals

**Goals:**
- ComfyUI starts automatically when AICrochet starts; stops when AICrochet stops.
- After `/generate`, a `.glb` is produced async and swaps into the combined preview when ready.
- LatheGeometry scene stays visible as fallback throughout — 3D failure never degrades pattern usability.
- No new Python packages required.

**Non-Goals:**
- Per-part `.glb` meshes (Phase 2).
- Using the `.glb` geometry to improve crochet diameter profiles (Phase 2/3).
- Multi-user concurrency — single-user local tool, one generation at a time is fine.
- Persisting `.glb` files across server restarts (ephemeral output directory is acceptable).

## Decisions

### D1 — ComfyUI lifecycle: subprocess.Popen with health-check guard

**Decision**: On FastAPI `startup`, call `GET /system_stats` on `http://127.0.0.1:8188`. If it responds, ComfyUI is already running — do nothing. If it fails, spawn ComfyUI via `subprocess.Popen(["python", "main.py", "--port", "8188"], cwd=expanduser("~/ComfyUI"))` with the venv Python. Store the `Popen` handle in a module-level variable. On FastAPI `shutdown`, call `handle.terminate()` and `handle.wait(timeout=10)`.

**Why not**: A systemd service or Docker would be more robust but requires user setup. A shell script wrapper adds indirection. Direct `Popen` is the minimum that works for a single-user local tool.

**Risk**: If ComfyUI is externally running but on a different port, the health check passes but `image-to-3d.mjs` talks to the wrong server. Mitigation: always use the env var `COMFYUI_URL` consistently in both places.

---

### D2 — 3D job tracking: in-memory dict keyed by session_id

**Decision**: Maintain a module-level `dict[str, dict]` in `backend/comfyui.py`:
```
{session_id: {status: "pending"|"generating"|"done"|"failed", glb_url: str|None, error: str|None}}
```
`/generate` creates the entry and spawns `asyncio.create_task` to run the generation subprocess. `/preview/{session_id}` reads from this dict.

**Why not SSE/WebSocket**: Polling is simpler for a frontend with no bundler and keeps the JS minimal. With a 3–5 s poll interval the user gets the mesh within one poll tick of completion.

**Why not a task queue (Celery/RQ)**: Overkill for a single-user local tool with one concurrent generation.

**Persistence**: Jobs are ephemeral — lost on server restart. Acceptable since the user can re-submit.

---

### D3 — Running image-to-3d.mjs: asyncio subprocess

**Decision**: Use `asyncio.create_subprocess_exec("node", script_path, "--input", img_path, "--output", glb_path, "--steps", "20")` with `--steps 20` as the default (faster, lower quality acceptable for preview). Capture stdout for the result JSON; log stderr for progress. Set `--no-rembg` as an option to skip background removal if the image already has a white background (not applicable by default — most doll photos have backgrounds, so rembg is on).

**Why 20 steps not 50**: Preview quality doesn't need full fidelity. 20 steps cuts warm time from ~60 s to ~30 s. Can be overridden via `COMFYUI_3D_STEPS` env var.

**Why node not Python**: `image-to-3d.mjs` is the established, tested entry point. Wrapping it in Python is one `subprocess.exec` call.

---

### D4 — .glb storage and serving: `/models` static mount

**Decision**: Store generated files at `backend/output/models/{session_id}.glb`. Mount this directory as a FastAPI `StaticFiles` at `/models`. The frontend fetches `/models/{session_id}.glb` when the poll endpoint returns `done`.

**Why not stream the bytes through the API**: Static file serving is simpler and Three.js `GLTFLoader` expects a URL.

**Cleanup**: No automatic cleanup in Phase 1. `backend/output/` is gitignored. Users can clear manually. This is acceptable for a local tool.

---

### D5 — Frontend swap strategy: replace combined-preview content on ready

**Decision**: After `/generate` returns, the frontend:
1. Immediately calls `buildCombinedScene(data)` to show the existing LatheGeometry scene (unchanged path).
2. Starts a `setInterval` polling `GET /preview/{session_id}` every 4 seconds.
3. When status is `done`, calls `buildGlbScene(glbUrl)` which clears `#combined-preview` and renders the `.glb` with `GLTFLoader`.
4. When status is `failed`, stops polling (LatheGeometry scene stays).
5. A "3D preview generating…" status badge is shown during polling.

**GLTFLoader import**: Already available via the existing importmap: `"three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"` → `import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'`.

**Why not replace LatheGeometry immediately**: The LatheGeometry scene gives the user something to look at while the 45–60 s generation runs. Swapping on completion is the best UX.

---

### D6 — Image persistence for the async job

**Decision**: When `/generate` receives the uploaded file, save a copy to `backend/output/uploads/{session_id}.jpg` before processing. The async 3D job reads from this path. The file is ephemeral (same gitignored output dir).

**Why**: The `UploadFile` object is closed by the time the async task runs. The image bytes must be persisted so `image-to-3d.mjs` can read them from disk.

## Risks / Trade-offs

**ComfyUI cold start (~2 min)** → The first generation after a fresh AICrochet start will take 2 minutes. Mitigation: show a spinner with an estimated wait ("This may take up to 2 minutes on first run"). Subsequent generations are 30–60 s.

**ComfyUI crashes silently** → The `Popen` handle won't detect the crash; the health check on startup only fires once. Mitigation: `/generate` checks ComfyUI health before spawning the 3D job and sets status=`failed` with a descriptive error if it's unreachable.

**Port conflict** → If port 8188 is in use by something else, ComfyUI won't start. Mitigation: log the error clearly; `COMFYUI_PORT` env var overrides the default.

**Node.js not on PATH** → `image-to-3d.mjs` requires Node ≥ 22. Mitigation: check `node --version` at startup and log a clear warning if Node is absent or < 22. Disable 3D generation gracefully (pattern generation still works).

**GLTFLoader CORS** → `.glb` files served from `/models` are same-origin (FastAPI on the same port as `/static`). No CORS issue.

## Migration Plan

1. Add `backend/output/` to `.gitignore`.
2. New module `backend/comfyui.py` — isolated, no changes to existing modules until wired.
3. Wire lifecycle hooks and new endpoints into `backend/main.py`.
4. Update `frontend/static/index.html` — additive changes only; LatheGeometry path untouched.
5. No database migration. No dependency changes (Node.js pre-existing; no new pip packages).

## Open Questions

- **Steps default**: 20 steps chosen for speed. If preview quality is poor on test images, bump to 30. Decided at implementation time after a test run.
- **Concurrent uploads**: Two users submitting at the same time share one ComfyUI queue (it serialises). Acceptable for Phase 1.
