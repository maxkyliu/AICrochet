## 1. Setup and dependencies

- [x] 1.1 Add `backend/output/stl/` to gitignore coverage (already under `backend/output/`); confirm `.gitignore`
- [x] 1.2 Add `trimesh` to `requirements.txt` (installed 4.12.2; scipy already present)
- [x] 1.3 Write a setup script that clones/locates the two GPL repos, applies the stdin patch to `graph_standalone.cpp` (replace the hardcoded `dotContent(jsInput)` with a `std::cin.rdbuf()` read), builds `graph_standalone` (g++ -O2) and `crochet_remesh` (cargo build --release), records upstream source URLs + GPL license + the patch, and prints the resulting binary paths — both binaries built + verified
- [x] 1.4 Document `GRAPH_STANDALONE_BIN` and `CROCHET_REMESH_BIN` env vars in `.env.example`

## 2. External tool lifecycle (backend/external_tools.py)

- [x] 2.1 Implement `resolve_binary(env_var, build_path)` → path or None
- [x] 2.2 Implement `check_binaries()` → sets module flags `graph_available`, `remesh_available`; verifies each executes; never raises
- [x] 2.3 Add `run_graph_standalone(graph_text)` → dict of name→(x,y,z) (subprocess, feed graph via stdin, parse `{"name","pos"}` JSON lines from stdout, ignore progress lines)
- [x] 2.4 Add `run_remesher(stl_path)` → pattern text (subprocess, `--input`/`--pattern-out`, read the pattern JSON file)
- [x] 2.5 Call `check_binaries()` in main.py startup handler; log availability

## 3. Grammar → DOT export (backend/dot_export.py)

- [x] 3.1 Inspect example DOT graphs in /tmp/cp_main to confirm the dialect, node/edge syntax, and weight convention graph_standalone expects
- [x] 3.2 Expose per-round stitch counts from `grammar.py` (additive accessor; no behavior change) — `compile_part_detailed` returns (instructions, round_counts)
- [x] 3.3 Implement `part_to_graph(round_stitch_counts)` → graph text: `3` dimension line, quoted per-stitch node names, intra-round cycle `--` edges, inter-round working edges by angular position reflecting increases/decreases, uniform `1.0` lengths, trailing `iterations=80` / `viscous_iterations=10`
- [x] 3.4 Validate round-trip: pipe a hand-checked sphere part's graph to the patched `graph_standalone` and confirm it returns `{"name","pos"}` coordinates without error (verified: 72-node graph, iterations=80, ~10ms)

## 4. Mesh comparison (backend/mesh_compare.py)

- [x] 4.1 Implement `normalize(mesh)` — center to origin, scale to unit bbox diagonal, align dominant principal axis vertical (PCA)
- [x] 4.2 Implement `silhouette_mask(mesh, angle)` — project to X-Y at a given Y-rotation, rasterize + column-envelope fill to binary mask
- [x] 4.3 Implement `shape_distance(mesh_a, mesh_b)` → `1 − mean(IoU)` over N=4 angles; degenerate inputs return 1.0, never raise — validated (self=0.0, sphere/cyl=0.77)
- [x] 4.4 Implement `coords_to_points(node_coords)` — wrap graph_standalone output as a point cloud for comparison

## 5. Refinement loop (backend/refine.py)

- [x] 5.1 Add job tracker: `_jobs[session_id] = {status, refined_parts, error}` with create/update/get
- [x] 5.2 Implement `objective(diameters, part_name, target_mesh)` — compile→graph→graph_standalone→points→shape_distance vs target
- [x] 5.3 Implement per-part optimization with `scipy.optimize.minimize` (Nelder-Mead, large initial simplex to cross stitch quantization), seeded from current diameters, ±40% bounds, capped evals; accept only if distance < seed AND re-compiles cleanly
- [x] 5.4 Implement `run(session_id, parts, glb_path)` — load target via trimesh, optimize each part, assemble refined_parts; flat_disc/short parts kept as-is; verified 3.7s/2 parts on fox glb
- [x] 5.5 Add `scipy` to requirements if not already present

## 6. Seamless mode (backend/seamless.py)

- [x] 6.1 Implement `glb_to_stl(glb_path, stl_path)` via trimesh (export STL)
- [x] 6.2 Implement `generate(session_id, glb_path)` → glb_to_stl → run_remesher (with bundled default_config.json) → return pattern text; verified 1.1s on fox glb

## 7. Backend endpoints (backend/main.py)

- [x] 7.1 After 3D `.glb` reaches done, schedule `asyncio.create_task(refine.run(...))` if `graph_available` — via `_refine_after_mesh` coordinator (awaits mesh, runs refine off-thread)
- [x] 7.2 Add `GET /refine/{session_id}` → refine job dict or 404
- [x] 7.3 Add `POST /generate-seamless/{session_id}` → 503 if `remesh_available` false, 409 if `.glb` not ready, else seamless pattern text
- [x] 7.4 Ensure `/generate` and the standard path are unchanged when binaries are absent — guarded by `graph_available`/`remesh_available` flags

## 8. Frontend (frontend/static/index.html)

- [x] 8.1 Add `startRefinePolling(sessionId)` — poll `GET /refine/{sessionId}`; on `done` swap per-part cards + previews to refined parts (via reusable `renderParts`); on failed/timeout keep original
- [x] 8.2 Call `startRefinePolling` after a standard pattern is generated
- [x] 8.3 Add "Generate One-Piece Pattern" button, disabled until `/preview` reports `done`
- [x] 8.4 Wire the button to `POST /generate-seamless/{sessionId}`; render pattern text in a new dedicated panel
- [x] 8.5 Add a refinement status badge ("Refining pattern to match 3D model…")

## 9. Integration tests

- [x] 9.1 Verify startup health check sets correct availability flags when binaries present/absent — both True with binaries; both False (no raise) with bogus paths
- [x] 9.2 End-to-end: upload fox.jpg (8 parts), preview done in 30s, refinement done in 10s with reshaped diameters
- [x] 9.3 End-to-end: /generate-seamless after mesh ready returns a 34KB seamless pattern
- [x] 9.4 Degradation: seamless returns 503 when remesh unavailable, 409 when mesh not ready, refine 404 for unknown session; 34 existing tests still pass (grammar refactor backward-compatible)
