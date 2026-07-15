# AICrochet — Architecture & Algorithm Documentation

## Project Overview

AICrochet converts a photo of a doll into row-by-row crochet stitch instructions that a crafter can follow to manually build a matching 3D amigurumi-style doll. A neuro-symbolic pipeline separates vision understanding (neural) from pattern generation (symbolic), so generated patterns are always mathematically valid crochet. Two learning mechanisms improve shape fidelity over time: direct measurement of an AI-generated 3D mesh, and a crafter-feedback loop that retrains per-primitive geometry models.

---

## System Architecture

```
User Browser
     │
     │  POST /generate (multipart image + optional gauge)
     ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (backend/main.py)                          │
│                                                              │
│  Synchronous path (returns in one request):                  │
│  1. Image ingest, persist upload for async jobs              │
│  2. Vision analysis (vision.py) ──► Gemini / Claude / Ollama │
│  3. Part-type coercion guards (limbs, ears)                  │
│  4. GeometryEngine.process_dependency_graph()                │
│  5. CrochetGrammar.compile_part()                            │
│  6. Return List[PatternResponse]                             │
│                                                              │
│  Async path (spawned per session, polled by the browser):    │
│  A. comfyui.generate_3d() ──► Hunyuan3D .glb  → GET /preview │
│  B. mesh_measure: slice .glb per part, recompile pattern     │
│     with measured diameters              → GET /measured     │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
Frontend  (frontend/static/index.html)
  Per-part instruction cards + Three.js LatheGeometry previews,
  combined 3D scene, correction sliders → POST /feedback
```

### Component Breakdown

| Component | File | Responsibility |
|---|---|---|
| API server | `backend/main.py` | HTTP routing, orchestration, async job trackers, retrain trigger |
| Vision providers | `backend/vision.py` | Gemini/Claude/Ollama abstraction, structured output, silent retry |
| Geometry engine | `backend/geometry.py` | Scale-aware primitive → diameter profiles; optional learned model |
| Crochet grammar | `backend/grammar.py` | Gauge-aware diameter profiles → stitch instructions |
| 3D generation | `backend/comfyui.py` | ComfyUI lifecycle, Hunyuan3D image→.glb jobs, job tracker |
| Mesh measurement | `backend/mesh_measure.py` | PCA alignment, vertical band slicing, per-part diameters |
| Frontend | `frontend/static/index.html` | Upload UI, 3D previews, gauge settings, feedback sliders |
| Data pipeline | `data/` | SQLite store, scrapers, pattern normalizer, dataset export |
| Model training | `models/train.py` | Per-primitive GradientBoosting regressors + eval gate |

---

## Pipeline

### Stage 1 — Image Ingestion
`POST /generate` accepts a multipart image plus optional gauge fields (`gauge_stitches_per_10cm`, `gauge_rows_per_10cm`). The image is decoded via PIL and persisted to `backend/output/uploads/{session_id}.jpg` so the async 3D job can read it after the HTTP request completes.

### Stage 2 — Vision Analysis
`vision.analyze_with_retry()` sends the image to the provider selected by `VISION_PROVIDER` (default `gemini`, model from `GEMINI_MODEL`, default `gemini-2.0-flash`; alternatives: Claude via tool-forced JSON, Ollama via structured output). The call runs in a worker thread (`asyncio.to_thread`) so it never blocks the event loop.

The prompt asks the model to decompose the doll into parts, each with:
- **name** — e.g. `"Head"`, `"Left Arm"`
- **type** — one of 8 primitives: `sphere`, `cylinder`, `cone`, `frustum`, `capsule`, `teardrop`, `flat_disc`, `torus`
- **scale** — relative size multiplier (1.0 = medium)
- **bbox** *(optional)* — normalized 2D bounding box `[x_min, y_min, x_max, y_max]` in image coordinates, used later by mesh measurement

Schema enforcement is native per provider (Gemini `response_schema`, Claude `input_schema`, Ollama `format`).

Two robustness layers sit on top of the raw call:
- **Silent retry** — if the response has < 4 parts or is missing a head/body, the call is retried (up to 2×) with a strengthened prompt demanding all visible parts. The last response is used regardless.
- **Type coercion guards** — parts named arm/leg/paw/flipper classified as `sphere` are coerced to `capsule`; parts named ear/wing/fin are coerced to `flat_disc`. These correct the most common LLM misclassifications deterministically.

### Stage 3 — Geometry Engine: Primitive → Diameter Profile
`GeometryEngine.process_dependency_graph()` maps each part to an ordered array of cross-section diameters (one per crochet round). Profiles are **scale-aware** in two dimensions:

1. **Amplitude** — every diameter is multiplied by `scale`.
2. **Round count** — sphere, capsule, and teardrop extend their flat-plateau rounds proportionally to `√scale`, so a large body is taller as well as wider, not just inflated.

| Primitive | Profile shape (scale = 1.0) | Typical use |
|---|---|---|
| `sphere` | ramp 2→8, 3 flat rounds, taper 8→2 | Head, ball body |
| `cylinder` | constant 4 × 6 rounds | Neck, straight limb |
| `cone` | monotonic 2→10 | Beak, horn |
| `frustum` | ramp 4→10, holds flat, no tail | Boxy torso, foot |
| `capsule` | like sphere with a longer plateau | Plush limb, sausage body |
| `teardrop` | ramp, short plateau, long asymmetric taper | Pear body, snout |
| `flat_disc` | thin, reaches max width fast | Flat ear, hat brim |
| `torus` | 4→8→4, non-zero minimum | Collar, ring |

Unknown primitive types fall back to `cylinder` with a logged warning; `scale <= 0` is rejected.

**Market-prototype path (default)** — when `USE_MARKET_PROFILES=true` (default) and `data/models/market_profiles.json` exists, `get_diameters_for_primitive()` samples a per-primitive prototype curve learned from real scraped patterns (`models/prototypes.py`): a quality-filtered, length/amplitude-normalized median stitch-count curve. Amplitude is `24 × scale` stitches (matching the scale reference used when labeling training data) and round count comes from the learned rounds-per-stitch ratio. Primitives without enough market samples fall through to the paths below.

**Learned-model path** — when `USE_LEARNED_MODEL=true`, `get_diameters_for_primitive()` next tries a per-primitive GradientBoosting regressor (`data/models/{type}_regressor.joblib`) fed a 7-feature vector (scale, round count, max count, mean rise, mean fall, flat fraction, symmetry). Any failure — missing model file, prediction error — logs a warning and falls back to the hardcoded profile.

### Stage 4 — Crochet Grammar: Diameters → Stitch Instructions
`CrochetGrammar` is **gauge-aware**: `stitch_width_cm` and `stitch_height_cm` are derived from user-supplied gauge (`10 / stitches_per_10cm`), defaulting to 1.0 when no gauge is given.

**Round-based parts** (everything except `flat_disc`):

For each diameter `d`, the target stitch count is

```
count = max(6, 6 × round((d × π / w) / 6))
```

— circumference divided by stitch width, snapped to the nearest multiple of 6 so increases/decreases distribute evenly. `generate_round(prev, target)` then emits the correct directive:

| Condition | Emitted instruction |
|---|---|
| first round | `6 sc in magic ring [6]` |
| no change | `sc in each st around [n]` |
| increase | `(sc k, inc) x m [n]` — evenly spaced |
| increase > prev count | `j sc in each st around` (exact multiple) or capped doubling |
| decrease | `(sc k, dec) x m [n]` — evenly spaced |

Each part ends with a **terminal closure**: tapered-closed parts get `Stuff firmly.` + fasten-off-and-weave; open-ended parts get `Stuff before sewing.` + long-tail fasten-off. Compilation stops early once a taper closes back to 6 stitches.

**Flat parts** (`flat_disc`) compile to back-and-forth **rows** instead of rounds: `Ch n, turn` foundation, edge increases/decreases (`2 sc in first st`, `sc2tog`) to follow the width profile, ending with `Do NOT stuff. Sew flat.` Bare plural names (`Ears`, `Wings`, …) emit a singularized label plus `(make 2)`.

### Stage 5 — Response + Async Refinement

The synchronous response is a `List[PatternResponse]`: `{name, instructions[], diameters[], primitive_type}` per part, where `diameters` is trimmed to the rounds actually emitted. The browser renders each part immediately as a rotatable Three.js `LatheGeometry` plus its instruction card.

If Node.js ≥ 22 is available, two background jobs are spawned per session:

**A. 3D preview** (`backend/comfyui.py`) — the uploaded photo is run through a Hunyuan3D ComfyUI workflow (via the image-blaster `image-to-3d.mjs` script) producing `backend/output/models/{session_id}.glb`. The frontend polls `GET /preview/{session_id}` and swaps the true mesh into the combined scene when done. The backend starts/stops a local ComfyUI instance on app startup/shutdown if one isn't already running.

**B. Mesh measurement** (`backend/mesh_measure.py`) — once the .glb exists, each part's diameter profile is re-derived from actual mesh geometry:

1. Load the mesh and PCA-align its dominant axis to +Y (no rescaling).
2. **Orientation check**: the PCA sign is arbitrary, so the mesh's width-per-height curve is correlated against the width profile predicted from the parts' bboxes; the mesh is flipped when the inverted orientation correlates better. If neither orientation correlates above 0.3, measurement is skipped and the initial parts are returned unchanged.
3. Map each part's vision bbox to a band on the mesh — bboxes are first rescaled so their union spans 0..1 (the mesh spans the subject, not the photo frame), then mapped vertically from `y_min/y_max`, with each cross-section masked to the bbox's `x_min/x_max` window (+5% margin) so neighboring parts at the same height (arms beside a body) don't inflate the measurement. Phase-1 assumption: photo and mesh share approximate upright orientation; no camera pose estimation.
4. Slice the band at the initial profile's round count; each slice's max horizontal extent (of in-window vertices) becomes one diameter. Measurements failing sanity checks (empty, non-positive, length drift >±50% vs the initial profile) fall back per part.
5. **Calibrate**: Hunyuan3D meshes have no absolute scale, so all measured values are multiplied by the **median** of per-part `initial_max / measured_max` ratios — robust to a single inflated measurement.
6. **Regularize**: each part's profile is `α·measured + (1−α)·reference` (unit-amplitude curves; `MESH_BLEND_ALPHA`, default 0.5), where the reference is the market prototype (or normalized hardcoded profile). A measured curve with >30% direction flips contributes amplitude only (α forced to 0). Round count derives from the calibrated amplitude via the prototype's `rounds_per_max`, not slice count.
7. **Gate and recompile**: a part whose regularized shape diverges from the reference by unit-amplitude MAE > 0.25 keeps its initial-estimate pattern; passing parts are recompiled through the grammar. `flat_disc` parts and parts without bboxes always keep the initial pattern.

The frontend polls `GET /measured/{session_id}` and swaps in the measured pattern when the job completes (typically ~40 s after generation); a fully gated or orientation-skipped session returns the original parts, making the swap a no-op. Both job trackers are in-memory dicts with a 1-hour TTL, evicted opportunistically on job creation.

---

## Feedback & Learning Loop

- **Correction UI** — each part's card has per-round diameter sliders; submitting posts original vs. corrected profiles to `POST /feedback`.
- **Storage** — corrections land in SQLite (`data/aicrochet.db`) via `data/database.py`. If the DB layer is unavailable the endpoint returns 503 rather than failing silently.
- **Retraining trigger** — after each submission, a background task checks the count of unincorporated corrections; at `RETRAIN_THRESHOLD` (default 100) it spawns `python -m models.train --all`. The spawn is lock-guarded with a process-liveness check so concurrent submissions can't start overlapping trainings.
- **Training** (`models/train.py`) — per-primitive GradientBoosting regressors trained on the dataset (scraped + synthetic + feedback records). A model is only promoted to `data/models/{type}_regressor.joblib` if validation MAE < 1.0 stitches; failed evals are recorded, and the previous model is kept as `.bak`.
- **Serving** — promoted models are used only when `USE_LEARNED_MODEL=true`; the hardcoded profiles remain the default and the fallback.

### Data Pipeline (feeds training)

```
scraper (Ravelry API, WordPress pattern blogs)
   │  (photo, raw pattern text) pairs + photo quality filter
   ▼
normalizer (US/UK terminology detection → instruction tokenizer
   │         → stitch-count extraction → diameter reconstruction)
   ▼
dataset (SQLite; versioned, deduplicated, train/val split, synthetic seeding)
```

---

## HTTP Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/generate` | Photo (+ optional gauge, session_id) → per-part patterns; spawns async jobs |
| GET | `/preview/{session_id}` | Poll 3D generation job → `{status, glb_url, error}` |
| GET | `/measured/{session_id}` | Poll mesh-measurement job → `{status, parts, error}` |
| POST | `/feedback` | Submit a diameter-profile correction (validates lengths match) |
| GET | `/feedback/stats` | Correction counts and stats |
| GET | `/` | Health check |

---

## Key Design Decisions

**Neuro-symbolic pipeline** — vision understanding (neural) is separated from pattern generation (symbolic). Vision errors degrade shape fidelity, never pattern validity: every emitted pattern is arithmetically consistent crochet.

**Direct mesh measurement over refinement loops** — an earlier physics-based refinement loop and seamless-pattern exporter passed all internal tests but failed at the user boundary (quantization-bounded refinement, output rejected by external tools). Both were removed in the `direct-mesh-accuracy` change in favor of measuring the Hunyuan3D mesh directly — ground-truth geometry with one calibration step instead of iterative approximation.

**Graceful degradation everywhere** — no Node/ComfyUI → patterns still generate, 3D preview is skipped; no vision bboxes → measurement is skipped; learned model failure → hardcoded profiles; no database → feedback endpoints return 503. The core photo→pattern path has no optional dependency.

**Multiples-of-6 quantization** — crochet rounds increase/decrease most naturally in multiples of 6; snapping to this grid guarantees whole-number increase spacing.

**Magic ring start / flat-row split** — round parts start with the standard amigurumi magic ring; flat parts compile to turned rows with edge shaping, because treating them as degenerate cylinders produces unusable pieces.

**Primitives as constrained vocabulary** — limiting the vision model to 8 named primitives (plus deterministic coercion guards for limbs and ears) keeps the geometry mapping tractable and the LLM's failure modes correctable.
