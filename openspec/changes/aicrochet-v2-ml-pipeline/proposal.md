## Why

AICrochet's MVP proves the concept — a photo can drive crochet instruction generation — but the output quality is fundamentally capped by hardcoded geometry, an ignored `scale` field, a vocabulary of only three shape primitives, and no mechanism for the system to learn from real patterns or crafter feedback. Shipping to real users in this state would produce instructions that frequently mismatch the source doll's proportions, eroding trust in the tool before a learning flywheel can develop. The path to a genuinely useful product requires a data pipeline, a learned geometry model, a richer shape vocabulary, and a visual feedback layer — all of which compose naturally from the existing neuro-symbolic architecture.

## What Changes

- **Fix scale-aware geometry**: the `scale` field returned by Gemini is currently ignored; it must drive both diameter amplitude and round count so a large body is actually larger than a small head.
- **Expand primitive vocabulary**: add `frustum`, `capsule`, `teardrop`, `flat_disc`, and `torus` alongside the existing `sphere`, `cylinder`, `cone` — covering the full range of amigurumi body parts.
- **Build a web scraping pipeline**: collect (finished-object photo, pattern text) pairs from Ravelry API, Amigurumi Today, and Reddit r/amigurumi for use as training data.
- **Build a pattern normalizer**: convert raw pattern text (US/UK notation variants) into a canonical token format, then reconstruct ground-truth diameter profiles from stitch counts.
- **Train a profile regressor**: replace the hardcoded lookup table in `GeometryEngine` with a model that maps (image crop, primitive type, scale) → diameter profile array.
- **Add a crafter feedback loop**: expose correction UI so crafters can report shape inaccuracies; corrections are stored and used to periodically retrain the profile regressor.
- **Add 3D browser preview**: render each part's diameter profile as a Three.js `LatheGeometry` and compose parts spatially using the Gemini dependency graph — zero new backend data required.
- **Gauge-aware stitch counts**: allow users to input yarn weight and hook size so `CrochetGrammar` computes physically accurate round counts instead of using fixed stitch dimensions.

## Capabilities

### New Capabilities

- `scale-aware-geometry`: Scale-driven diameter amplitude and round-count computation in GeometryEngine; replaces the single hardcoded profile per primitive type.
- `expanded-primitives`: Seven additional primitive types recognized by Gemini and mapped through GeometryEngine; covers frustum, capsule, teardrop, flat_disc, torus.
- `web-scraper`: Automated collection of amigurumi image-pattern pairs from Ravelry API and open pattern sites; includes finished-object photo classifier to filter partial/construction photos.
- `pattern-normalizer`: US/UK terminology detection, instruction tokenizer, stitch-count extractor, and diameter-profile reconstructor; produces canonical training records.
- `training-dataset`: Managed dataset schema and tooling for combining scraped, synthetic, and feedback-derived records; versioned, deduplicated, train/val split.
- `profile-regressor`: Learned model replacing the hardcoded lookup in `GeometryEngine`; trained on the dataset; evaluated against held-out patterns from the scraper.
- `feedback-loop`: Crafter correction UI and backend; corrections map to diameter profile deltas; retraining triggered when correction batch threshold is reached.
- `3d-preview`: Client-side Three.js renderer; diameter profile → LatheGeometry per part; parts positioned using Gemini spatial graph; real-time rotatable in browser.
- `gauge-aware-grammar`: User-supplied yarn gauge (stitches per 10cm) drives `stitch_width` and `stitch_height` in `CrochetGrammar`; persisted per user session.

### Modified Capabilities

- None — existing `/generate` endpoint contract is preserved; all changes are additive or internal replacements.

## Impact

- **`backend/geometry.py`**: complete rewrite to support scale arithmetic, 8-primitive vocabulary, and pluggable profile backend (hardcoded → learned model).
- **`backend/grammar.py`**: add gauge parameter plumbing; `stitch_width` becomes a runtime input, not a constructor constant.
- **`backend/main.py`**: new endpoints for feedback submission and dataset health; gauge field added to `/generate` request.
- **New packages**: `torch` or `scikit-learn` (profile regressor), `scrapy` or `httpx` + `beautifulsoup4` (scraper), `three.js` via CDN (3D preview), `sqlite` or `postgresql` (feedback + dataset storage).
- **New infrastructure**: dataset store, model artifact storage, retraining job scheduler.
- **Gemini prompt**: expanded primitive list must be injected into the structured prompt and schema.
