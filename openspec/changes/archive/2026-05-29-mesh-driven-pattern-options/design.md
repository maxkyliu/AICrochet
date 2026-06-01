## Context

AICrochet generates multi-part amigurumi patterns from a doll photo via a neuro-symbolic pipeline (LLM → GeometryEngine → CrochetGrammar). The `comfyui-3d-preview` change added async Hunyuan3D `.glb` generation with a session job tracker and `/preview/{session_id}` polling. The `.glb` is currently used only for visualization — its real geometry never feeds back into the pattern.

Two GPL-3.0 tools from the CrochetPARADE project unlock that feedback:
- **`graph_standalone`** (C++, `int main()`, reads a DOT stitch-graph from stdin): the *forward* renderer. It embeds a pattern's stitch-graph into 3D "rest geometry" via geodesic-metric MDS + viscous spring relaxation. This simulates how a pattern actually crochets up.
- **`CrochetPARADE_Remesher`** (Rust CLI): the *inverse* tool. It takes an STL, grows a seamless stitch patch over the surface (curvature-driven theta decisions), and emits a CrochetPARADE-DSL pattern.

These are the two halves of a closed loop. This change uses the forward renderer to refine the standard pattern, and the inverse tool to offer a one-piece pattern alternative.

## Goals / Non-Goals

**Goals:**
- Refine the standard multi-part pattern's diameter arrays so a simulated render better matches the real `.glb`.
- Offer a one-piece seamless pattern as a second UI option.
- Keep AICrochet's license separate from GPL via subprocess-only integration.
- Degrade gracefully: if binaries or `trimesh` are absent, the standard pattern path is unaffected.

**Non-Goals:**
- Per-part Hunyuan3D / mesh part-segmentation (deferred — GPL-porting risk + unsolved segmentation).
- Translating the Remesher's CrochetPARADE-DSL output into AICrochet round notation (display DSL as-is in Phase 1).
- Replacing GeometryEngine's hardcoded profiles — refinement adjusts the diameters downstream, not the source profiles.
- Real-time/interactive refinement — it is a background job, allowed to take 1–2 minutes.

## Decisions

### D1 — Subprocess-only integration, no algorithm porting

**Decision**: Invoke both `graph_standalone` and `crochet_remesh` strictly as arm's-length subprocess CLIs. Never copy their source into AICrochet modules.

**Why**: Both are GPL-3.0-or-later. Porting their logic into AICrochet would make AICrochet a derivative work, forcing it to GPL. Exec'ing a separate binary is the established boundary that keeps licenses separate.

**stdin patch (discovered during implementation)**: `graph_standalone.cpp` does NOT read stdin — line 31274 (`std::getline(std::cin, dotContent)`) is commented out and it uses a hardcoded demo graph (`std::string dotContent(jsInput)`). To drive it programmatically we apply a **minimal one-line patch**: replace that line with a read of all stdin (`std::stringstream ss; ss << std::cin.rdbuf();`), falling back to the demo input when stdin is empty. This is a modification to *their* GPL program, not porting their code into ours — AICrochet still calls it arm's-length and stays non-GPL. The patch is applied by the build script (a `.patch`/sed step) before compilation. Verified: the patched binary builds clean with `g++ -O2`.

**Distribution caveat**: shipping the built binaries alongside AICrochet triggers GPL source-availability obligations for *those binaries*, and because we patch `graph_standalone` we must offer the **modified** source. The build script records upstream source URLs, license text, and the patch. Documented, not blocking.

### D2 — Comparison metric: multi-angle silhouette overlap

**Decision**: Normalize both meshes (center to origin, scale to unit bounding-box diagonal, align principal axis vertically), render each orthographically from N=4 angles (every 90° around the vertical axis), rasterize to binary masks, and compute shape-distance as `1 − mean(IoU)` across angles.

**Why over chamfer distance**: Silhouette IoU is cheap (2D mask ops via numpy), robust to the simulated mesh being a thin shell vs the target being solid, and matches what a crocheter cares about (outline/proportion). Chamfer needs careful point sampling and is sensitive to surface vs volume differences. Silhouette is good enough for a ~9-dimensional optimization.

**Normalization is essential**: `graph_standalone` output and Hunyuan3D output have arbitrary scale/orientation; comparison is meaningless without alignment first.

### D3 — Optimizer: per-part coordinate descent via scipy

**Decision**: Optimize each part's diameter array independently with `scipy.optimize.minimize` (Nelder-Mead), objective = D2 shape-distance between the part's simulated render and the corresponding region of the target. Seed from the current GeometryEngine diameters. Cap at ~30 function evaluations per part.

**Why**: The space is small (~9 floats) and well-behaved (smooth, single-basin near the formula seed). Nelder-Mead needs no gradients and handles the black-box simulator. Per-part keeps each optimization low-dimensional and parallelizable.

**Per-part target (implemented Phase-1 choice)**: the unified `.glb` is not segmented (segmentation was the deferred Idea 2), so a clean per-part target isn't available. Phase-1 uses the whole normalized `.glb` as the comparison target for each part, with two safety guards: (1) each diameter is bounded to ±40% of its seed value so a small part cannot balloon toward the whole-doll shape, and (2) a refined array is accepted only if its shape-distance is strictly better than the seed AND it re-compiles through the grammar — otherwise the original is kept. This makes refinement safe (worst case = no change) and still leverages the real mesh. Per-part segmentation for a sharper target is deferred to a later phase.

### D4 — Refinement runs as a background job, polled separately

**Decision**: New job state keyed by `session_id` (separate dict from comfyui's, or a shared module). `/generate` schedules `asyncio.create_task(refine.run(session_id))` *after* the `.glb` is ready (chained off the existing 3D job completion, or polled-for inside the refine task). Frontend polls `GET /refine/{session_id}` → `{status, refined_parts | null, error}` and swaps the pattern + previews when `done`.

**Why**: Refinement needs the `.glb` (25–60 s) plus its own loop (1–2 min). Blocking `/generate` is unacceptable. Reusing the established poll-and-swap UX from `comfyui-3d-preview` keeps the frontend simple (no SSE).

### D5 — Grammar→DOT emitter is the core new backend module

**Decision**: New `backend/dot_export.py` maps a part's round-by-round stitch counts to the exact format `graph_standalone`'s `readDotFile` parses (verified against `/tmp/cp_main` source during implementation):
- **First line**: the embedding dimension, `3`.
- **Node lines**: one quoted opaque name per stitch, e.g. `"r0s0"`, `"r1s3"`. (The demo's `"layer,index|id"` is just naming convention; the parser treats the quoted string as an opaque ID.)
- **Edge lines**: `"src" -- "dst" <length>` — intra-round cycle edges between adjacent stitches, and inter-round "working" edges mapping each previous-round stitch to its child(ren) by angular position. Length = stitch-scale distance (start uniform `1.0`).
- **Param lines**: `iterations=80` and `viscous_iterations=10` appended to cap solver cost.

Output from the binary is **JSON lines**, one per node: `{"name": "r4s10","pos": "x,y,z"}` (plus per-iteration progress on stdout that the parser must skip).

**Why**: This is the bridge between AICrochet's symbolic pattern and CrochetPARADE's physics. Connectivity is derived from the actual stitch counts the grammar emits (the `[N]` round counts), not the diameters, so increases/decreases produce the correct graph topology (which is what drives simulated curvature). `grammar.py` exposes its internal per-round stitch-count list to avoid re-parsing instruction strings.

### D6 — GLB→STL and point clouds via trimesh

**Decision**: Add `trimesh` as a dependency. Use it to load `.glb`, export `.stl` for the Remesher, and rasterize silhouettes / sample points for D2.

**Why**: `trimesh` is the standard Python mesh library, handles GLB and STL natively, and provides the geometry primitives (bounding box, principal axes, ray/section) the comparison needs. Avoids hand-rolling mesh I/O.

### D7 — Seamless mode reuses the session `.glb`

**Decision**: `POST /generate-seamless/{session_id}` looks up the session's `.glb`; if not yet ready, returns a 409 with `retry_after`; the button is disabled in the UI until `/preview` reports `done`. On success: glb→STL (D6) → `crochet_remesh` → capture CP-DSL stdout → return as text. Displayed verbatim in a new results panel.

**Why**: Reuses already-generated geometry (no second Hunyuan3D run). The seamless pattern is a fundamentally different artifact (one continuous piece, CP-DSL syntax), so it gets its own panel rather than being forced into the per-part card layout.

### D8 — Binary lifecycle mirrors the comfyui pattern

**Decision**: New `backend/external_tools.py` with `check_binaries()` run at startup: resolves `GRAPH_STANDALONE_BIN` and `CROCHET_REMESH_BIN` env vars (or conventional build output paths), verifies they execute, and sets module flags `graph_available` / `remesh_available`. Endpoints check the relevant flag and return a clear "feature unavailable" response if false. A setup script builds both (`g++` for graph_standalone, `cargo build --release` for the remesher) and records their source URLs + license for GPL compliance.

**Why**: Directly mirrors the proven `comfyui._node_available` degradation pattern. Keeps the standard pattern path working on machines without the toolchains.

## Risks / Trade-offs

**DOT dialect mismatch** → The grammar→DOT output may not parse in `graph_standalone`. Mitigation: validate the emitter against real example inputs in `/tmp/cp_main` early (first implementation task); start with a single hand-checked part before wiring the loop.

**Per-part target ambiguity (D3)** → Comparing a part's render to an unsegmented whole-doll target is approximate. Mitigation: accept proportional/rough correction in Phase 1; document; revisit with per-part meshes in a later phase.

**Refinement makes the pattern worse** → The optimizer could move diameters somewhere the grammar produces awkward stitch counts. Mitigation: only accept the refined array if its shape-distance is strictly better than the seed's, and re-validate it compiles cleanly through the grammar; otherwise keep the original.

**GPL distribution obligations** → Shipping the binaries requires offering their source. Mitigation: setup records upstream URLs + license files; document in README; never statically link into AICrochet.

**Build toolchain absent** → Many environments lack `cargo`/`g++`. Mitigation: D8 graceful degradation — both features simply don't appear; standard pattern unaffected.

**Performance** → graph_standalone runs N times per part × parts. **Verified during implementation**: a realistic 72-node part graph at `iterations=80` runs in ~10 ms (the demo's 120s+ runtime was its 500-iteration default on a ~300-node graph, not representative). With ~30 evals/part this is sub-second per part. Mitigation: cap iterations at ~80 via the param line (D5), cap evals (D3), run as background job (D4).

## Migration Plan

1. Add `backend/output/stl/` to gitignore (under existing `backend/output/`).
2. Add `trimesh` to requirements.
3. Build the two binaries via setup script; set env paths; verify health check.
4. Land backend modules in isolation (`external_tools`, `dot_export`, `mesh_compare`, `refine`, `seamless`) with unit tests before wiring endpoints.
5. Wire endpoints + frontend additively; existing `/generate` path untouched.
6. No DB migration.

## Open Questions

- **Edge weights**: resolved to start uniform `1.0` per stitch (the format takes a per-edge length after `--`). If single-crochet vs increase/decrease should carry different rest-lengths, tune later; uniform is a valid starting point.
- **Per-part vs whole-doll refinement**: D3 uses a whole-doll target band per part. If accuracy is poor, fall back to refining a single representative part or whole-doll silhouette only. Decide after first end-to-end run.
- **Seamless DSL → round notation**: out of scope now; revisit if users want the seamless pattern in AICrochet's notation.
