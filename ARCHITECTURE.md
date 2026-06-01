# AICrochet — Architecture & Algorithm Documentation

## Project Overview

AICrochet converts a photo of a doll into row-by-row crochet stitch instructions that a crafter can follow to manually build a matching 3D amigurumi-style doll. The system is designed to improve over time as better shape priors and learned parameters replace the current hardcoded defaults.

---

## System Architecture

```
User Browser
     │
     │  POST /generate (multipart image)
     ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Backend  (backend/main.py)             │
│                                                 │
│  1. Image ingest & validation                   │
│  2. Gemini Vision API call ──► Google Cloud     │
│  3. Parse JSON part graph                       │
│  4. GeometryEngine.process_dependency_graph()   │
│  5. CrochetGrammar.compile_part()               │
│  6. Return List[PatternResponse]                │
└─────────────────────────────────────────────────┘
     │
     │  JSON: [{name, instructions[]}, …]
     ▼
Frontend  (frontend/static/index.html)
  Renders per-part instruction cards
```

### Component Breakdown

| Component | File | Responsibility |
|---|---|---|
| API Server | `backend/main.py` | HTTP routing, image I/O, orchestration |
| Geometry Engine | `backend/geometry.py` | Maps 3D primitives → cross-section diameter profiles |
| Crochet Grammar | `backend/grammar.py` | Converts diameter profiles → stitch instructions |
| Frontend | `frontend/static/index.html` | Image upload UI, results display |

---

## Pipeline (5 Stages)

### Stage 1 — Image Ingestion
The FastAPI `/generate` endpoint accepts a multipart-uploaded image. The raw bytes are decoded into a PIL Image object for downstream use.

### Stage 2 — Semantic Analysis via Gemini Vision
The image is sent to `gemini-1.5-flash` with a structured prompt asking it to decompose the doll into named anatomical parts, each tagged with:
- **name** — e.g. `"Head"`, `"Body"`, `"Left Arm"`
- **type** — one of `"sphere"`, `"cylinder"`, `"cone"`
- **scale** — relative size multiplier (float)

The model returns structured JSON conforming to the `DependencyGraph` schema (enforced via `response_mime_type="application/json"`).

```
Photo → Gemini → DependencyGraph
{
  "parts": [
    {"name": "Head",  "type": "sphere",   "scale": 1.0},
    {"name": "Body",  "type": "cylinder", "scale": 1.5},
    {"name": "Arm",   "type": "cone",     "scale": 0.6}
  ]
}
```

### Stage 3 — Geometry Engine: Primitive → Diameter Profile
`GeometryEngine.process_dependency_graph()` iterates the part list and maps each primitive type to an ordered array of cross-section diameters (one per crochet round):

| Primitive | Diameter Profile | Shape Rationale |
|---|---|---|
| `sphere` | `[2,4,6,8,8,8,6,4,2]` | Widens then narrows symmetrically |
| `cylinder` | `[4,4,4,4,4,4]` | Constant cross-section |
| `cone` | `[2,4,6,8,10]` | Monotonically widens from tip |

The `scale` field is threaded through but not yet applied to the diameter values — this is the primary extensibility hook for learned refinement (see [Future Learning](#future-learning)).

### Stage 4 — Crochet Grammar: Diameters → Stitch Instructions
`CrochetGrammar.compile_part()` performs two sub-steps:

#### 4a. Diameter → Stitch Count
For each diameter `d`, the target stitch count per round is:

```
count = max(6, 6 × round((d × π / w) / 6))
```

Where `w` is `stitch_width` (default 1.0). This uses the circumference formula `C = π × d`, divides by stitch width to get raw stitch count, then snaps to the nearest multiple of 6 — a crochet convention that keeps increases and decreases evenly distributed.

#### 4b. Stitch Count → Round Instruction
`generate_round(prev_count, target_count)` computes the delta and emits the correct crochet directive:

| Condition | Emitted Instruction | Example |
|---|---|---|
| `prev_count == 0` | Start with magic ring | `6 sc in magic ring [6]` |
| `delta == 0` | Single-crochet each stitch | `sc in each st around [24]` |
| `delta > 0` | Evenly spaced increases | `(sc 3, inc) x 6 [30]` |
| `delta < 0` | Evenly spaced decreases | `(sc 2, dec) x 6 [18]` |

The interval between increases/decreases is computed as `prev_count // |delta|` to spread them evenly around the round.

### Stage 5 — Response
A `List[PatternResponse]` is returned as JSON. Each object carries:
- `name` — part label
- `instructions` — ordered list of round strings (including a header separator)

---

## Data Flow Summary

```
Image
  │
  ▼ Gemini Vision
[{name, type, scale}, …]          ← Semantic part graph
  │
  ▼ GeometryEngine
[{name, diameters[]}, …]          ← Cross-section profiles
  │
  ▼ CrochetGrammar
[{name, instructions[]}, …]       ← Stitch-level pattern text
```

---

## Future Learning

The current system uses **hardcoded diameter profiles** for each primitive type. The architecture isolates this in `GeometryEngine.get_diameters_for_primitive()`, making it the primary replacement target for a learned model.

### Planned Learning Paths

#### Path 1 — Scale-Aware Profiles
Apply `scale` to stretch or compress the diameter array non-uniformly (e.g., a scaled sphere should have more flat-top rounds, not just scaled-up diameters). A simple regression model trained on (scale, primitive_type) → diameter_profile pairs could replace the lookup table.

#### Path 2 — Feedback-Driven Refinement
Crafters who complete a pattern and find it inaccurate can submit corrections (e.g., "the head was too pointy — needed 2 more flat rounds"). These corrections map to diameter profile adjustments and can train a per-primitive profile predictor.

#### Path 3 — Richer Vision Understanding
Replace single-primitive-per-part classification with a model that predicts a full diameter profile directly from the cropped region of the doll image. This collapses Stages 2–3 into a single learned step:

```
Cropped part image → CNN/ViT → diameter profile[]
```

#### Path 4 — Grammar Parameter Learning
`stitch_width` and `stitch_height` in `CrochetGrammar` are currently fixed at 1.0. Real yarn gauges vary. A user-provided gauge swatch (stitches per cm) lets the grammar compute physically accurate round counts, and this measurement can be stored per-user.

### Extension Points in Current Code

| Location | What to Replace | With |
|---|---|---|
| `geometry.py:3-9` | Hardcoded diameter lookup | Learned profile model |
| `geometry.py:14` | `node.get('scale', 1.0)` ignored | Scale-conditioned profile generation |
| `main.py:59` | `gemini-1.5-flash` fixed model | Fine-tunable vision model |
| `grammar.py:4-5` | Fixed stitch dimensions | User gauge input |

---

## Key Design Decisions

**Neuro-symbolic pipeline** — Vision understanding (neural, via Gemini) is separated from pattern generation (symbolic, via Grammar). This keeps the generated patterns always valid crochet; errors in the vision step affect shape fidelity, not pattern correctness.

**Multiples-of-6 quantization** — Crochet rounds increase/decrease most naturally in multiples of 6. Snapping stitch counts to this grid ensures evenly distributed increases with whole-number intervals.

**Magic ring start** — Every part begins with a magic ring (`6 sc`), the standard amigurumi technique for closed-bottom 3D shapes.

**Geometric primitives as vocabulary** — Constraining Gemini's output to three primitive types (sphere, cylinder, cone) limits ambiguity and makes the geometry→diameter mapping tractable with simple rules. More primitives (torus, frustum) can be added incrementally.
