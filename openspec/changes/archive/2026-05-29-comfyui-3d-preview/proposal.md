## Why

The current combined 3D preview is an arrangement of procedural LatheGeometry blobs — mathematically derived, not measured from the actual doll. Replacing it with a real Hunyuan3D mesh makes the preview credible as a planning tool and sets the foundation for geometry-driven pattern accuracy in later phases. ComfyUI with the required model is already installed locally, so the capability is available at zero ongoing cost.

## What Changes

- AICrochet backend manages ComfyUI as a sidecar process: starts it on application startup if not already running, stops it on shutdown.
- A new `/preview/{session_id}` polling endpoint reports 3D generation status and returns the `.glb` URL when ready.
- On `/generate`, the backend saves the uploaded image and spawns an async Hunyuan3D generation job using the existing `image-to-3d.mjs` standalone script.
- Generated `.glb` files are stored in `backend/output/models/` and served via a new `/models` static mount.
- The frontend replaces the `buildCombinedScene` LatheGeometry render with a `GLTFLoader` render of the real mesh once the `.glb` is ready; the LatheGeometry scene remains visible as a fallback until then.
- Per-part individual previews (LatheGeometry) are unchanged.

## Capabilities

### New Capabilities

- `comfyui-lifecycle`: AICrochet backend starts, health-checks, and stops a local ComfyUI process as a managed sidecar.
- `async-3d-generation`: When a doll image is submitted, a Hunyuan3D `.glb` is generated asynchronously and tracked per session.
- `glb-preview`: The combined doll preview renders a real `.glb` mesh via GLTFLoader, falling back to LatheGeometry while generation is in-progress or on failure.

### Modified Capabilities

- `primitive-type-routing`: No requirement changes — per-part LatheGeometry previews and crochet pattern pipeline are unaffected by this change.

## Impact

- **Backend**: `backend/main.py` — startup/shutdown lifecycle hooks, new `/preview/{session_id}` endpoint, new `/generate` side-effect (spawn async job), new `/models` static mount. New module `backend/comfyui.py` for sidecar management.
- **Frontend**: `frontend/static/index.html` — import `GLTFLoader` from Three.js addons, replace `buildCombinedScene`, add polling loop.
- **Dependencies**: Node.js ≥ 22 required at runtime (for `image-to-3d.mjs`). No new Python packages. ComfyUI must be installed at `~/ComfyUI` with model and custom nodes already present.
- **New output directory**: `backend/output/models/` (auto-created, gitignored).
- **No API breaking changes**: `/generate` response schema unchanged.
