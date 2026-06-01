## Why

The ML model training pipeline is structurally broken: all 222 real scraped records have `primitive_type = NULL`, so the regressor trains only on 40 synthetic seeds (5 per primitive), memorises them, and reports near-zero MAE that is statistically meaningless. The learned model adds no value over the hardcoded geometry rules until real data is labelled and features are meaningful.

## What Changes

- Add a **noise filter** to discard non-body-part records (abbreviation lists, material sections, notes headers) before they enter the DB
- Add a **rule-based primitive labeler** that maps part names (HEAD, BODY, LEG, ARM, EAR, TAIL, BEAK, …) to primitive types at normalization time
- Add a **shape-heuristic labeler** that infers primitive type from stitch count curve shape for records whose part names don't match keywords
- Add **scale inference** from stitch count magnitude so `scale` is no longer always `1.0` for every real record
- Add **richer training features** derived from the stitch sequence (max count, length, rise/fall slopes, flat fraction, symmetry score) replacing the current 2-feature `(scale, aspect_ratio)` vector
- Update `models/train.py` feature extraction to use the new feature set

## Capabilities

### New Capabilities

- `primitive-labeler`: assigns `primitive_type` to normalized training records via rule-based name matching and shape-curve heuristics
- `noise-filter`: rejects records whose part names match non-body-part patterns (abbreviation lists, material sections, etc.) before DB insertion
- `scale-inference`: infers a meaningful `scale` value from stitch count magnitude during normalization
- `training-features`: richer derived feature set for the regressor (6-8 features instead of 2)

### Modified Capabilities

## Impact

- `data/normalizer/normalizer.py` — add noise filter, primitive labeler, and scale inference calls
- `data/normalizer/` — new `labeler.py` module
- `models/train.py` — replace `_extract_features()` with richer feature extraction
- `data/database.py` — no schema changes needed; `primitive_type` and `scale` columns already exist
- No API or frontend changes
- No new dependencies
