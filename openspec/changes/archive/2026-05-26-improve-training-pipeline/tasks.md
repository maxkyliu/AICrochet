## 1. Noise Filter

- [x] 1.1 Create blocklist constant in `data/normalizer/labeler.py` covering: ABBREVIATION, ABBREV, NOTE, MATERIAL, SUPPLY, GAUGE, TERMINOLOGY, SKILL, INTRODUCTION, TIP, INSTRUCTION, STITCH
- [x] 1.2 Implement `is_noise_record(part_name: str) -> bool` using case-insensitive substring matching against the blocklist
- [x] 1.3 Call `is_noise_record` in `normalizer.py` after `detect_parts` and skip noise records before DB insertion
- [x] 1.4 Verify: run `python -m data.normalizer run --source all` and confirm "Abbreviations", "Pattern Notes", "Stitches Used" records are no longer inserted

## 2. Scale Inference

- [x] 2.1 Implement `infer_scale(stitch_counts: list) -> float | None` in `data/normalizer/labeler.py`: `max(stitch_counts) / 24.0`, floored at `0.25`, returns `None` if empty
- [x] 2.2 Call `infer_scale` in `normalizer.py` and write the result to the `scale` field of each output record
- [x] 2.3 Verify: spot-check a few DB records after re-normalizing — `scale` column should be non-None for all records with non-empty stitch_counts

## 3. Primitive Labeler — Name Rules

- [x] 3.1 Implement `label_by_name(part_name: str) -> str | None` in `data/normalizer/labeler.py` using the keyword → primitive_type mapping defined in design.md
- [x] 3.2 Ensure keyword matching is case-insensitive and returns the first matched primitive type in priority order

## 4. Primitive Labeler — Shape Heuristic

- [x] 4.1 Implement `_compute_profile_stats(stitch_counts: list) -> dict` returning: `min_ratio`, `flat_fraction`, `rise_slope`, `fall_slope`, `symmetry_score`, `is_monotone_rise`
- [x] 4.2 Implement `label_by_shape(stitch_counts: list) -> str | None` using the decision tree from design.md; return `None` for sequences shorter than 4
- [x] 4.3 Verify heuristic on known-good sequences: `[6,12,18,24,24,24,18,12,6]` → sphere, `[6,12,18,24,24,24,24,24,18,12,6]` → capsule, `[6,12,18,24,30]` → cone, `[24,24,24,24,24]` → cylinder

## 5. Wire Labeling into Normalizer

- [x] 5.1 Add `label_primitive(part_name, stitch_counts)` orchestrator in `labeler.py` that calls `label_by_name` first, falls back to `label_by_shape`
- [x] 5.2 Call `label_primitive` in `normalizer.py` and write result to `primitive_type` field of each output record
- [x] 5.3 Re-run normalizer: `python -m data.normalizer run --source all` — confirm labeled record count in DB increases from 40 to well above 100

## 6. Backfill Existing Records

- [x] 6.1 Add `--relabel` flag to `data/normalizer/__main__.py` that re-reads all existing records from the DB, applies the labeler to any with `primitive_type = NULL`, and updates them in place
- [x] 6.2 Verify: after `python -m data.normalizer run --relabel`, `SELECT COUNT(*) FROM training_records WHERE primitive_type IS NOT NULL` should be significantly higher than 40

## 7. Richer Training Features

- [x] 7.1 Replace `_extract_features` in `models/train.py` with the 7-dimensional feature extractor specified in `specs/training-features/spec.md`
- [x] 7.2 Ensure feature extraction handles `stitch_counts = []` gracefully (all zeros for derived features)
- [x] 7.3 Update the profile-length padding logic in `_load_dataset` to still work correctly with the new feature vector (features and labels are separate)

## 8. Retrain and Evaluate

- [x] 8.1 Run `python -m models.train --all` — confirm train_count per primitive is now > 5 for labeled primitives
- [x] 8.2 Verify MAE values are still < 1.0 (promotion threshold) — if any primitive fails, investigate data quality for that primitive
- [x] 8.3 Check `data/models/eval_report.json` — document which primitives have the most real training samples and which are still sparse
