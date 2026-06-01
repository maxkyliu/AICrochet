## Context

AICrochet currently runs a 144-line, three-module backend (main, geometry, grammar) with a minimal HTML/JS frontend. The pipeline is entirely deterministic after the Gemini Vision call: hardcoded diameter arrays → rule-based stitch counts. No database, no ML framework, no persistence. The Google Gemini API is the only external dependency beyond FastAPI and Pillow.

The v2 plan introduces five independent new subsystems (scraper, normalizer, dataset, regressor, feedback) that must be grafted onto this architecture without breaking the existing `/generate` endpoint. The 3D preview and gauge input are frontend-only additions. The profile regressor eventually replaces the internals of `GeometryEngine` while keeping its public interface stable.

Stakeholders: solo developer, end users are crochet crafters, data sources are public pattern websites.

## Goals / Non-Goals

**Goals:**
- Replace hardcoded diameter lookup with a trained model without changing the `/generate` API contract
- Build a scraping + normalization pipeline that produces labeled training data from real patterns
- Add crafter feedback that flows back into model retraining
- Add 3D visual preview in the browser using only existing part geometry data
- Expand primitive vocabulary to cover common amigurumi shapes
- Make stitch counts physically accurate via user-supplied yarn gauge

**Non-Goals:**
- Real-time model retraining (batch offline only)
- Pattern generation for non-amigurumi crochet (garments, flat items)
- Yarn purchasing, supplier integration, or color matching
- Mobile-native app (browser only)
- Multi-user accounts or authentication in Phase 1-2

## Decisions

### Decision 1: Keep the neuro-symbolic split; don't go end-to-end

**Chosen**: Vision (Gemini) + Geometry (learned) + Grammar (rules). Three separate stages.

**Alternative considered**: Single end-to-end model — photo in, pattern text out. Feasible with GPT-4V or a fine-tuned multimodal model, but requires orders of magnitude more training data and produces outputs that cannot be structurally validated. A garbled diameter calculation would produce syntactically plausible but geometrically nonsensical instructions.

**Rationale**: The Grammar stage guarantees valid crochet math regardless of upstream errors. Errors degrade shape fidelity, not pattern correctness. This is the right property for a tool used by real crafters.

---

### Decision 2: scikit-learn for the profile regressor, not PyTorch

**Chosen**: `scikit-learn` `GradientBoostingRegressor` or `RandomForestRegressor` per primitive type.

**Alternative considered**: PyTorch CNN operating on image crops to predict diameter profiles directly. Powerful but requires GPU, complex training infra, and thousands of labeled pairs per primitive type.

**Rationale**: The feature vector for the regressor is small: `(scale, aspect_ratio, primitive_type_one_hot)`. With ~500-1000 training samples per primitive (realistic from Ravelry), a tree ensemble significantly outperforms a small CNN and trains in seconds on CPU. The CNN path is the Phase 5 stretch goal once dataset volume justifies it.

---

### Decision 3: Ravelry API as primary data source

**Chosen**: Ravelry REST API (`api.ravelry.com`) as primary; Amigurumi Today HTML scraper as secondary.

**Alternative considered**: Pinterest (image-heavy but pattern text rarely co-located), Etsy (paywalled patterns), general web crawl (noise-to-signal ratio too high).

**Rationale**: Ravelry has structured fields (gauge, hook size, yarn weight, finished measurements) that are training features — not just pattern text. Its API is documented, rate-limited at 1 req/sec for free use, and terms permit non-commercial research. The `pattern_type: amigurumi` filter narrows to exactly the doll domain.

---

### Decision 4: Photo classifier before training pair creation

**Chosen**: A binary classifier step — "is this a finished-object photo?" — before any image is added to the training dataset.

**Alternative considered**: Manually curate all photos. Too slow at Ravelry scale.

**Rationale**: Ravelry patterns have multiple photos: in-progress WIP shots, yarn close-ups, packaging. The regressor must train on finished-object images only. A lightweight MobileNetV2 fine-tuned on ~200 manually labeled samples can achieve >90% precision on this binary task before any training pairs are created.

---

### Decision 5: SQLite for feedback + dataset registry

**Chosen**: SQLite with two tables: `training_records` (scraped + normalized) and `feedback_corrections` (crafter deltas).

**Alternative considered**: PostgreSQL (operational overhead for a solo project), plain JSON files (no query capability for dataset splits and filtering).

**Rationale**: Dataset is read-mostly, single-process, no concurrent writes. SQLite is zero-infrastructure and sufficient for tens of thousands of records. Migrating to Postgres is straightforward if needed.

---

### Decision 6: Three.js LatheGeometry for 3D preview, client-side only

**Chosen**: The browser computes the 3D mesh from the diameter array returned by the existing API. No new backend data or endpoints.

**Alternative considered**: Server-side mesh generation (e.g., trimesh, Open3D) returned as glTF. Adds latency and backend complexity for a purely visual feature.

**Rationale**: The diameter profile IS a lathe profile. Three.js `LatheGeometry` takes exactly this format. The client already receives all the data it needs; rendering is a frontend concern.

---

### Decision 7: Scale encodes relative centimeter size

**Chosen**: `scale` is treated as the diameter of the widest cross-section in centimeters (normalized: `scale=1.0` → 8cm). Diameter profiles are then scaled linearly; round count grows as `floor(base_rounds × sqrt(scale))` to prevent unrealistically many flat rounds at large sizes.

**Alternative considered**: Scale as a pure aspect multiplier (dimensionless). Loses physical grounding; makes gauge integration harder.

**Rationale**: Centimeter grounding lets gauge arithmetic work correctly: stitch count = (diameter × π) / stitch_width_in_cm. A user who inputs their gauge gets physically accurate stitches.

## Risks / Trade-offs

- **Ravelry API access** → Mitigation: apply for API key early; cache all responses locally to avoid re-scraping during development; respect rate limits with exponential backoff.

- **Pattern text parsing accuracy** → Mitigation: start with patterns whose total stitch counts are explicitly stated in the text (Ravelry shows stitch counts per round); use total as a checksum against the parsed reconstruction.

- **Regressor quality at small data volume** → Mitigation: seed with synthetic profiles (scale the hardcoded arrays) until scraped data accumulates; flag synthetic records so they can be downweighted or excluded once real data is available.

- **Gemini primitive classification errors for new types** → Mitigation: add a confidence threshold; fall back to the nearest supported primitive if classification is low-confidence rather than propagating a bad label.

- **Photo classifier false positives** → Mitigation: err on the side of precision over recall; it's better to have a smaller clean dataset than a large noisy one. Log all rejections for manual review.

- **3D preview not matching physical result** → Mitigation: lathe geometry is a visualization aid, not a simulation. Add a disclaimer: "3D preview is approximate — the pattern instructions are the authoritative guide."

## Migration Plan

### Phase 1 (no model, no data): Scale + expanded primitives + 3D preview
- `geometry.py` gets new primitives and scale math. Existing `/generate` contract unchanged.
- Frontend gains Three.js `<script>` tag and canvas element. No backend change.
- No migration needed: purely additive.

### Phase 2: Data pipeline (scraper + normalizer)
- New standalone scripts, not part of the FastAPI app.
- SQLite database created in `/data/aicrochet.db` on first run.
- No impact on production endpoint.

### Phase 3: Profile regressor replaces GeometryEngine internals
- `GeometryEngine.get_diameters_for_primitive()` signature unchanged; implementation swapped.
- Model artifact serialized to `/models/profile_regressor.joblib`.
- Feature flag: `USE_LEARNED_MODEL=true` env var; defaults to `false` (hardcoded) until model passes eval threshold (mean absolute diameter error < 1.0 stitches on held-out set).

### Rollback
- Set `USE_LEARNED_MODEL=false` to revert to hardcoded profiles without redeployment.
- Feedback corrections are append-only; no data is deleted on rollback.

## Open Questions

1. **Ravelry terms for ML training**: does using scraped pattern text to train a model fall within non-commercial research use? Should a lawyer review before releasing a trained model publicly?
2. **Feedback incentive**: what motivates crafters to submit corrections? Should completed patterns be downloadable (PDF export) as an incentive for feedback?
3. **Part assembly**: the Gemini graph returns parts but no spatial positions (e.g., "head is 2cm above body"). Should we ask Gemini for relative positions to place parts correctly in the 3D preview?
4. **Retraining cadence**: how many corrections trigger a retraining job? 50? 200? What is the deployment flow for a new model artifact?
