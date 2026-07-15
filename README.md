---
title: AICrochet
emoji: 🧶
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AICrochet

Upload a photo of a doll and get row-by-row crochet instructions to build it by hand. The system uses a vision LLM (Gemini by default; Claude and Ollama supported) to decompose the doll into 3D geometric parts, a geometry engine to compute cross-section diameter profiles, and a rule-based grammar to emit mathematically valid stitch instructions. A 3D preview renders in the browser; when the optional Hunyuan3D pipeline is available, the pattern is refined with diameters measured from an actual 3D mesh of the photo. Crafter feedback feeds back into a learned geometry model that improves over time.

---

## Architecture Overview

```
Photo → Vision LLM     → Part graph (8 primitives + scale + bbox)
      → GeometryEngine  → Diameter profiles (scale-aware)
      → CrochetGrammar  → Stitch instructions (gauge-aware)
      → Browser         → 3D LatheGeometry preview + text pattern
      → Crafter         → Correction feedback → Model retraining

Async (optional, needs Node ≥ 22 + ComfyUI):
Photo → Hunyuan3D .glb  → per-part mesh measurement → refined pattern swap
```

Full design: [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## Requirements

- Python 3.12+
- A Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com)) — or set `VISION_PROVIDER` to use Claude or a local Ollama vision model instead

Optional, for the true-mesh 3D preview and mesh-measured patterns:

- Node.js ≥ 22
- A local ComfyUI install at `~/ComfyUI` (venv at `~/comfyui-env`) with the Hunyuan3D workflow
- The image-blaster `image-to-3d.mjs` pipeline script

Without these, the app still works — parts render as profile-based 3D previews and patterns use the geometry engine's profiles.

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd AICrochet
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the template and fill in your keys:

```bash
cp .env.example .env   # or edit .env directly
```

Open `.env` and set at minimum:

```env
GOOGLE_API_KEY=your-google-api-key-here
```

All variables and their defaults:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | With gemini provider | — | Gemini Vision API key |
| `VISION_PROVIDER` | No | `gemini` | Vision backend: `gemini`, `claude`, `ollama`, or `agnes` |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |
| `AGNES_API_KEY` | With agnes provider | — | Agnes AI key (`AGNES_BASE_URL`, `AGNES_MODEL` optional) |
| `ANTHROPIC_API_KEY` | With claude provider | — | Claude API key (`ANTHROPIC_MODEL` optional) |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server (`OLLAMA_MODEL` default `llava`) |
| `COMFYUI_URL` | No | `http://127.0.0.1:8188` | ComfyUI endpoint for 3D generation |
| `COMFYUI_PORT` | No | `8188` | Port used when auto-launching ComfyUI |
| `COMFYUI_3D_STEPS` | No | `20` | Hunyuan3D sampling steps |
| `RAVELRY_USERNAME` | Phase 2 only | — | Ravelry account username |
| `RAVELRY_API_KEY` | Phase 2 only | — | Ravelry personal API key |
| `AICROCHET_DB` | No | `data/aicrochet.db` | Path to SQLite database |
| `USE_MARKET_PROFILES` | No | `true` | Use market-learned prototype profiles (`data/models/market_profiles.json`) |
| `USE_LEARNED_MODEL` | No | `false` | Use trained regressor instead of hardcoded profiles |
| `RETRAIN_THRESHOLD` | No | `100` | Crafter corrections before auto-retraining |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
| `GENERATE_RATE_LIMIT` | No | `5/minute` | Per-IP rate limit on `/generate` |
| `FEEDBACK_RATE_LIMIT` | No | `20/minute` | Per-IP rate limit on `/feedback` |
| `GENERATE_DAILY_LIMIT` | No | `0` (unlimited) | Global daily cap on generations (vision-API spend guard) |
| `MAX_UPLOAD_MB` | No | `8` | Maximum accepted photo size |
| `OUTPUT_TTL_HOURS` | No | `24` | Uploads/meshes older than this are deleted |

> `.env` is listed in `.gitignore` and will never be committed.

---

## Running the Server

```bash
.venv/bin/uvicorn backend.main:app --reload
```

Then open **http://localhost:8000/static/index.html**

To use a custom host/port from `.env`:

```bash
.venv/bin/python -m backend.main
```

---

## Using the Web UI

1. **Gauge Settings** (optional, collapsible) — select a yarn weight preset or enter stitches/rows per 10 cm. This makes stitch counts physically accurate for your yarn.

   | Preset | Stitches/10cm | Rows/10cm |
   |---|---|---|
   | Fingering | 28 | 36 |
   | Sport | 24 | 32 |
   | DK | 22 | 28 |
   | Worsted | 20 | 24 |
   | Bulky | 14 | 18 |

2. **Upload** a photo of a doll and click **Generate Pattern**.

3. **Results** — a combined 3D scene appears at the top; each part gets a rotatable 3D preview and its stitch instructions below. If the ComfyUI pipeline is available, a true 3D mesh of the photo replaces the combined scene (~1–2 min), and shortly after, patterns are refreshed with diameters measured from that mesh.

4. **Adjust Shape** — per-part slider panel lets you correct each round's diameter and submit the correction back to the server (feeds the learning loop).

---

## Testing

### Unit tests (no API key needed)

```bash
.venv/bin/python -m pytest backend/tests/ -v
```

65 tests covering all 8 primitive types, scale arithmetic, flat-round extension, grammar output (rounds, flat rows, closures), mesh measurement on synthetic geometry, vision retry logic, and job-tracker eviction.

### Smoke test (no server, no API key)

```bash
.venv/bin/python -c "
from backend.geometry import GeometryEngine
from backend.grammar import CrochetGrammar

geo = GeometryEngine()
grammar = CrochetGrammar(stitch_width_cm=0.5)  # worsted gauge

parts = geo.process_dependency_graph([
    {'name': 'Head', 'type': 'sphere',    'scale': 1.0},
    {'name': 'Body', 'type': 'capsule',   'scale': 1.5},
    {'name': 'Ear',  'type': 'flat_disc', 'scale': 0.4},
])
for p in parts:
    print('\n'.join(grammar.compile_part(p['name'], p['diameters'])))
    print()
"
```

### API tests (server must be running)

```bash
# Health check (/ redirects to the UI)
curl http://localhost:8000/healthz

# Generate pattern from image
curl -X POST http://localhost:8000/generate \
  -F "file=@/path/to/doll.jpg" \
  -F "gauge_stitches_per_10cm=20" \
  -F "gauge_rows_per_10cm=24"

# Submit a shape correction
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-abc",
    "part_name": "Head",
    "primitive_type": "sphere",
    "original_diameters": [2,4,6,8,8,8,6,4,2],
    "corrected_diameters": [2,4,6,8,8,8,8,6,4,2]
  }'

# Check feedback stats
curl http://localhost:8000/feedback/stats
```

---

## Deploying a Public Demo (Hugging Face Spaces)

The repo ships a `Dockerfile` and the HF Spaces frontmatter at the top of this README, so the whole repo *is* the Space. The demo runs the CPU-only pattern path — 3D mesh generation and mesh measurement are skipped gracefully (no GPU/Node on the free tier); crafters still get patterns and rotatable profile previews.

1. Create a Space at [huggingface.co/new-space](https://huggingface.co/new-space) — SDK: **Docker**, hardware: **CPU basic (free)**.
2. In the Space's **Settings → Variables and secrets**, add:
   - Secret `GOOGLE_API_KEY` — your Gemini key (never commit it)
   - Variable `GENERATE_DAILY_LIMIT` — e.g. `200`, caps daily vision-API spend
3. Push this repo to the Space:

   ```bash
   git remote add space https://huggingface.co/spaces/<user>/aicrochet
   git push space main
   ```

The Space builds the Dockerfile and serves the UI at its public URL.

**Abuse guards baked in:** per-IP rate limits on `/generate` and `/feedback`, a global daily generation cap, an upload size cap (413), image validation (400), generic error messages (internals only go to server logs), and 24 h TTL cleanup of uploaded photos.

**Known tradeoff:** Space storage is ephemeral — the SQLite feedback DB resets on rebuild/restart. Fine for a demo; attach persistent storage (or point `AICROCHET_DB` at a mounted volume) if crafter corrections start mattering.

---

## Data Pipeline (Phase 2)

Collect real crochet patterns to train the geometry model.

### Initialize the database and seed synthetic data

```bash
.venv/bin/python -m data.dataset seed
.venv/bin/python -m data.dataset stats
```

### Scrape free pattern blogs (no extra API key)

Uses WordPress REST APIs from crochet pattern blogs (currently: 1dogwoof.com).
`amigurumitoday.com` is defunct as of 2026 and has been replaced by this source.

```bash
.venv/bin/python -m data.scraper run --source amigurumitoday --limit 50
```

### Scrape Ravelry (requires Ravelry API key in `.env`)

```bash
.venv/bin/python -m data.scraper run --source ravelry --limit 200
```

### Normalize scraped patterns into training records

```bash
.venv/bin/python -m data.normalizer run --source amigurumitoday
.venv/bin/python -m data.normalizer run --source ravelry
# or both at once:
.venv/bin/python -m data.normalizer run --source all
```

### Export a train/val split

```bash
.venv/bin/python -m data.dataset export --split train --output data/train.json
.venv/bin/python -m data.dataset export --split val   --output data/val.json
```

---

## Training the Profile Regressor (Phase 3)

Requires data in the database (run the pipeline steps above first).

```bash
# Train all 8 primitive types
.venv/bin/python -m models.train --all

# Train one primitive
.venv/bin/python -m models.train --primitive sphere

# Evaluate existing models without retraining
.venv/bin/python -m models.train --all --eval-only
```

Models are saved to `data/models/` and only promoted if validation MAE < 1.0 stitches. Enable the learned model by setting `USE_LEARNED_MODEL=true` in `.env`.

### Market prototype profiles (default initial-profile source)

Per-primitive canonical stitch-count curves learned from real scraped patterns. Rebuild after re-ingesting data:

```bash
# Re-extract training records from data/raw with the normalizer
.venv/bin/python -m data.normalizer run --source all

# Build prototype curves and compare against hardcoded profiles (leave-one-out MAE)
.venv/bin/python -m models.prototypes build
.venv/bin/python -m models.prototypes eval
```

Prototypes are written to `data/models/market_profiles.json` and used by `GeometryEngine` when `USE_MARKET_PROFILES=true` (the default). Primitives without enough market samples fall back to hardcoded profiles automatically.

---

## Photo Classifier Training (Phase 2 — optional)

Improves photo quality filtering in the scraper. Requires ~200 manually labeled photos.

```bash
# Create labeled data directory:
# data/labeled_photos/finished/   ← photos of complete dolls
# data/labeled_photos/wip/        ← in-progress / yarn-only photos

.venv/bin/python -m data.scraper.photo_classifier train \
  --data-dir data/labeled_photos \
  --epochs 5
```

---

## Project Structure

```
AICrochet/
├── .env                        # secrets and config (not committed)
├── .env.example                # template to copy
├── requirements.txt
├── backend/
│   ├── main.py                 # FastAPI server, endpoints, async job coordination
│   ├── vision.py               # Gemini/Claude/Ollama provider abstraction + retry
│   ├── geometry.py             # 8-primitive scale-aware geometry engine
│   ├── grammar.py              # gauge-aware stitch instruction generator
│   ├── comfyui.py              # ComfyUI lifecycle + Hunyuan3D image→.glb jobs
│   ├── mesh_measure.py         # per-part diameter measurement from the .glb
│   └── tests/                  # 65 unit tests
├── frontend/
│   └── static/
│       └── index.html          # upload UI, 3D preview, feedback sliders
├── data/
│   ├── database.py             # SQLite schema + migrations
│   ├── dataset.py              # export, stats, synthetic seeding
│   ├── scraper/
│   │   ├── ravelry.py          # Ravelry API client
│   │   ├── amigurumitoday.py   # HTML scraper
│   │   └── photo_classifier.py # MobileNetV2 finished/WIP classifier
│   └── normalizer/
│       ├── terminology.py      # US/UK detection
│       ├── tokenizer.py        # regex instruction tokenizer
│       ├── diameter.py         # stitch count → diameter reconstruction
│       └── normalizer.py       # orchestration
└── models/
    └── train.py                # GradientBoosting regressor training + eval
```

---

## Supported Primitives

| Type | Shape | Typical use |
|---|---|---|
| `sphere` | Round, tapered both ends, flat middle grows with size | Head, ball body |
| `cylinder` | Uniform width | Neck, straight limb |
| `cone` | Widens from tip to base | Beak, horn, pointed ear |
| `frustum` | Widens then holds flat, no taper at end | Boxy torso, foot |
| `capsule` | Cylinder with rounded caps (longer flat than sphere) | Plush limb, sausage body |
| `teardrop` | Pear-shaped, asymmetric taper | Pear body, raindrop snout |
| `flat_disc` | Thin, rapidly reaches max width | Flat ear, hat brim |
| `torus` | Ring/donut, non-zero minimum diameter | Collar, bracelet |
