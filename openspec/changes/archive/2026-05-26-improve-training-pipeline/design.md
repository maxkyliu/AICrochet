## Context

The normalizer currently writes `primitive_type = None` and `scale = None` for every real scraped record. The training pipeline filters to `primitive_type IS NOT NULL`, so the 222 real records are never used. The model trains on 40 synthetic seeds only, achieving near-zero MAE by memorisation. The regressor's feature vector is `(scale=1.0, aspect_ratio)` — one constant input renders the model incapable of learning scale-dependent shape variation.

Current data flow:
```
scraper → raw JSON → normalizer → DB (primitive_type=NULL, scale=NULL)
                                          ↓
                                  train (5 synthetic samples/primitive → memorised)
```

Target data flow:
```
scraper → raw JSON → normalizer
                       ├── noise filter   (drop abbreviation/note sections)
                       ├── scale infer    (max_stitches / gauge_reference)
                       ├── primitive label (name rules → shape heuristic)
                       └── DB (primitive_type set, scale set, ~150+ labeled records)
                                          ↓
                                  train (20-40 real samples/primitive → genuine learning)
```

## Goals / Non-Goals

**Goals:**
- Label ~80% of real records with a `primitive_type` without any API calls or human annotation
- Produce a meaningful `scale` value for real records
- Replace the 2-feature model input with a 6-8 feature vector that captures shape variation
- Keep the change entirely within Python; no new dependencies, no schema changes

**Non-Goals:**
- LLM-assisted labeling (useful long-term, out of scope here)
- Retraining the scraper or changing raw data format
- Changing the frontend or API surface
- Achieving production-grade model accuracy (this is a data quality foundation step)

## Decisions

### 1. Labeling order: name rules first, shape heuristic fallback

Rule-based name matching is fast, transparent, and covers the majority of well-named parts (HEAD, BODY, LEG, ARM, EAR, TAIL, BEAK, WING, FOOT, HAND, NECK). Shape heuristic runs only when name matching yields no result, avoiding false overrides on records where the name is unambiguous.

Alternatives considered:
- **Shape heuristic only**: would mislabel records where the curve is ambiguous (e.g., a short capsule looks like a cylinder)
- **LLM only**: expensive, adds latency, introduces an external dependency for a batch process

### 2. Name matching: keyword list, case-insensitive substring match

```
HEAD, SNOUT, MUZZLE            → sphere
BODY, TORSO, TRUNK             → capsule
LEG, ARM, LIMB, NECK, STALK    → cylinder
EAR                            → flat_disc
TAIL, BEAK, HORN, SPIKE, SNOUT → cone
FOOT, BOOT, BASE               → frustum
WING, FIN                      → flat_disc
TORUS, RING, COLLAR            → torus
```

"SNOUT" appears in both sphere and cone — sphere takes priority (rounder snouts are more common in amigurumi). The match uses the first keyword hit in priority order.

### 3. Shape heuristic: classify by profile statistics

Four discriminating statistics computed from the normalised diameter profile:
- **monotone_rise**: profile only goes up → cone
- **symmetry**: rise ≈ fall (within 20%) → sphere or capsule
- **flat_fraction**: proportion of rounds within 10% of max → cylinder if >60%, capsule if 30-60%, sphere if <30%
- **min_ratio**: min/max diameter → torus if > 0.4 (non-zero floor throughout)

Decision tree:
```
if min_ratio > 0.4                     → torus
elif monotone_rise                     → cone
elif flat_fraction > 0.6               → cylinder
elif symmetry AND flat_fraction < 0.3  → sphere
elif symmetry AND flat_fraction < 0.6  → capsule
elif not symmetry AND tail tapers      → teardrop
else                                   → frustum
```

### 4. Scale inference: max_stitch_count / 24

A "size 1.0" part in the synthetic seeds uses a max diameter that corresponds to approximately 24 stitches at worsted gauge. Dividing `max(stitch_counts)` by 24 gives a scale relative to that baseline. This is a heuristic, not a ground-truth measurement, but it gives the model a continuous input that correlates with actual doll size rather than being a constant.

Alternative: use `mean_stitch_count / 12`. Rejected because max is more stable against noisy round-level counts and better reflects the part's physical extent.

### 5. Noise filter: blocklist of non-body-part section names

Rather than an allowlist (which would be brittle), use a blocklist of patterns that are definitively not body parts:
```
Abbreviations, Notes, Materials, Supplies, Gauge, Stitches Used,
Terminology, Skills, Pattern Notes, Instructions, Introduction,
You Will Need, Tips, Special Stitches, Stitch Count
```

Case-insensitive substring match. Any record whose part_name matches the blocklist is dropped before DB insertion. This is conservative — false positives (valid parts missed) are less harmful than false negatives (noise in training data).

### 6. Richer features: 7-dimensional input vector

```python
features = [
    inferred_scale,          # max_stitches / 24
    sequence_length,         # number of rounds
    max_stitch_count,        # absolute size
    rise_slope,              # mean increase in first half
    fall_slope,              # mean decrease in second half (negative)
    flat_fraction,           # proportion near max diameter
    symmetry_score,          # 1 - abs(rise - fall) / (rise + fall + ε)
]
```

These are all derivable from `stitch_counts` already stored in the DB. No new data collection needed.

## Risks / Trade-offs

- **Mislabeling risk**: rule-based name matching will mislabel edge cases (e.g., "BODY" on a cone-shaped fish body). Mitigation: crafter feedback corrections are already weighted 2× in training, so errors self-correct over time.
- **Noise filter false positives**: a real body part named "Notes" or "Instructions" would be dropped. Risk is low — amigurumi patterns rarely name body parts with these words.
- **Scale heuristic inaccuracy**: `max_stitches / 24` is a rough proxy. For Ravelry patterns with very tight or loose gauge, scale will be off. Mitigation: the model learns a continuous function, so systematic bias in scale still produces useful predictions.
- **Shape heuristic edge cases**: very short sequences (< 4 rounds) produce unreliable slope estimates. Mitigation: skip shape heuristic for sequences shorter than 4 rounds; leave those records unclassified.

## Migration Plan

1. Apply code changes (new `labeler.py`, updated `normalizer.py`, updated `train.py`)
2. Re-run normalizer to label existing records: `python -m data.normalizer run --source all`
3. Re-run training: `python -m models.train --all`
4. Compare new eval report against existing `data/models/eval_report.json`
5. No rollback risk — `USE_LEARNED_MODEL=false` by default; old models remain in `.joblib.bak` archives

## Open Questions

- Should the shape heuristic also update records already in the DB that were inserted with `primitive_type = NULL` (i.e., a backfill), or only apply to new normalizer runs? Recommendation: backfill via a one-shot migration in `data.dataset` or a `--relabel` flag on the normalizer.
