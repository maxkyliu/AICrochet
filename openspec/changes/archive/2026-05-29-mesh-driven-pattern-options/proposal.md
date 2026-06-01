## Why

The standard pattern path produces mathematically perfect diameter profiles that won't match the real generated 3D preview — a stuffed crochet sphere deforms differently than a formula predicts. Two external GPL tools from the CrochetPARADE project let us close this gap: `graph_standalone` simulates how a pattern actually crochets up (forward render), and `CrochetPARADE_Remesher` converts a 3D mesh directly into a seamless pattern (inverse). Together they enable a physics-validated refinement loop and a new one-piece pattern style, both leveraging the Hunyuan3D `.glb` we already generate.

## What Changes

- **Feature A — Physics-validated refinement loop**: After the standard pattern and its `.glb` are ready, a background job tunes each part's diameter array so a physics-simulated render matches the real generated mesh. Adds a grammar→DOT emitter, a mesh-comparison metric, a gradient-free optimizer over diameter arrays, and a `GET /refine/{session_id}` status endpoint. Frontend polls and swaps in the refined pattern.
- **Feature B — One-piece seamless pattern button**: New UI button "Generate One-Piece Pattern" that reuses the session `.glb`, converts it to STL, runs the Remesher, and displays a seamless single-piece CrochetPARADE-DSL pattern. Adds `POST /generate-seamless/{session_id}`.
- **External tool lifecycle**: Build/locate/health-check two GPL CLI binaries (`graph_standalone`, `crochet_remesh`) at setup, with graceful degradation when absent (mirrors the existing `comfyui._node_available` pattern).
- **New dependency**: Python `trimesh` for GLB→STL conversion and point-cloud/silhouette extraction.
- Both external tools are invoked **only as arm's-length subprocess CLIs** — no algorithm porting — to keep AICrochet's license separate from GPL-3.0.

## Capabilities

### New Capabilities
- `external-tool-lifecycle`: Build, locate, and health-check the two GPL CLI binaries; expose availability flags; degrade gracefully when missing.
- `grammar-dot-export`: Emit a DOT stitch-graph (nodes + stitch-distance edges) from CrochetGrammar instructions, in the format `graph_standalone` consumes.
- `mesh-comparison`: Normalize two 3D meshes (center/scale/orient) and return a scalar shape-distance via silhouette overlap.
- `pattern-refinement-loop`: Background job that optimizes per-part diameter arrays against the target mesh using the forward renderer + comparison metric; queryable status.
- `seamless-pattern-mode`: One-piece pattern generation via the Remesher; new endpoint and UI button.

### Modified Capabilities
- `async-3d-generation`: No requirement change — refinement and seamless modes consume the existing `.glb` and session job tracker without altering the 3D generation contract.

## Impact

- **Backend**: `backend/main.py` (two new endpoints, startup health checks), new modules `backend/external_tools.py` (binary lifecycle), `backend/dot_export.py` (grammar→DOT), `backend/mesh_compare.py` (normalize + silhouette distance), `backend/refine.py` (optimization loop + job tracker), `backend/seamless.py` (glb→STL→remesher). `backend/grammar.py` may expose a stitch-graph structure for the DOT emitter (additive, no behavior change).
- **Frontend**: `frontend/static/index.html` — new "Generate One-Piece Pattern" button, refinement polling + pattern swap, CP-DSL text display.
- **Dependencies**: Python `trimesh` (+ `numpy`, present). Build-time: `g++` for `graph_standalone`, `cargo` for `crochet_remesh`. Node ≥ 22 already required.
- **Licensing**: GPL-3.0 binaries shipped/built alongside AICrochet — subprocess use keeps AICrochet's own code separate, but distributing the binaries carries GPL source-availability obligations (documented in design).
- **New output**: `backend/output/stl/{session_id}.stl`, refinement intermediates under `backend/output/` (gitignored).
- **No breaking changes**: `/generate` response schema and the standard pattern path are unchanged; refinement is additive and optional.
