# AICrochet

Upload a photo of a doll and get row-by-row crochet instructions to build it by hand. The system uses Google Gemini Vision to decompose the doll into 3D geometric parts, a geometry engine to compute cross-section diameter profiles, and a rule-based grammar to emit mathematically valid stitch instructions. A 3D preview renders in the browser. Crafter feedback feeds back into a learned geometry model that improves over time.

---

## Architecture Overview

```
Photo → Gemini Vision → Part graph (sphere/cylinder/cone/…)
      → GeometryEngine  → Diameter profiles (scale-aware, 8 primitives)
      → CrochetGrammar  → Stitch instructions (gauge-aware)
      → Browser         → 3D LatheGeometry preview + text pattern
      → Crafter         → Correction feedback → Model retraining
```

Full design: [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## Requirements

- Python 3.12+
- A Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

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
| `GOOGLE_API_KEY` | Yes | — | Gemini Vision API key |
| `RAVELRY_USERNAME` | Phase 2 only | — | Ravelry account username |
| `RAVELRY_API_KEY` | Phase 2 only | — | Ravelry personal API key |
| `AICROCHET_DB` | No | `data/aicrochet.db` | Path to SQLite database |
| `USE_LEARNED_MODEL` | No | `false` | Use trained regressor instead of hardcoded profiles |
| `RETRAIN_THRESHOLD` | No | `100` | Crafter corrections before auto-retraining |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |

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

3. **Results** — a combined 3D scene appears at the top; each part gets a rotatable 3D preview and its stitch instructions below.

4. **Adjust Shape** — per-part slider panel lets you correct each round's diameter and submit the correction back to the server (feeds the learning loop).

---

## Testing

### Unit tests (no API key needed)

```bash
.venv/bin/python -m pytest backend/tests/ -v
```

34 tests covering all 8 primitive types, scale arithmetic, flat-round extension, and validation.

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
# Health check
curl http://localhost:8000/

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
│   ├── main.py                 # FastAPI server + endpoints
│   ├── geometry.py             # 8-primitive scale-aware geometry engine
│   ├── grammar.py              # gauge-aware stitch instruction generator
│   └── tests/
│       └── test_geometry.py    # 34 unit tests
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
