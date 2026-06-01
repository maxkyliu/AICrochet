## ADDED Requirements

### Requirement: One regressor model per primitive type
The system SHALL train a separate `GradientBoostingRegressor` (scikit-learn) for each primitive type. Each model predicts a fixed-length diameter profile array given the feature vector `(scale, aspect_ratio)`. Models SHALL be serialized to `/models/<primitive_type>_regressor.joblib`.

#### Scenario: Models trained for all supported primitives
- **WHEN** `train --all` is run with sufficient training data (≥ 50 records per primitive)
- **THEN** one `.joblib` file is created per primitive type under `/models/`

#### Scenario: Insufficient data falls back to synthetic seed
- **WHEN** a primitive type has fewer than 50 real training records
- **THEN** synthetic records are included with a 0.3 sample weight and a warning is logged

---

### Requirement: Feature-flag-controlled model swap in GeometryEngine
The `GeometryEngine.get_diameters_for_primitive()` method SHALL check the `USE_LEARNED_MODEL` environment variable. When `true`, it loads the corresponding `.joblib` model and predicts the diameter profile. When `false` (default), it uses the hardcoded lookup table.

#### Scenario: Learned model used when flag is true
- **WHEN** `USE_LEARNED_MODEL=true` and all `.joblib` files exist
- **THEN** `get_diameters_for_primitive()` returns a model-predicted profile, not the hardcoded array

#### Scenario: Missing model file falls back gracefully
- **WHEN** `USE_LEARNED_MODEL=true` but the model file for the requested primitive type is absent
- **THEN** the hardcoded profile is used and a warning is logged (no exception raised)

---

### Requirement: Model evaluation against held-out validation set
The training pipeline SHALL evaluate each model on the validation split and report: mean absolute error (MAE) per diameter position, per-primitive type breakdown, and overall mean. A model SHALL only be promoted to production if its overall MAE < 1.0 stitches.

#### Scenario: Model passes evaluation threshold
- **WHEN** training completes and validation MAE is 0.7 stitches
- **THEN** the model is written to `/models/` and the evaluation report is saved to `/models/eval_report.json`

#### Scenario: Model fails evaluation threshold
- **WHEN** training completes and validation MAE is 1.4 stitches
- **THEN** the new model is NOT written to `/models/`, the existing model is preserved, and a report is written to `/models/failed_eval_<timestamp>.json`

---

### Requirement: Model versioning and rollback
Each trained model file SHALL be accompanied by a metadata file recording: training date, record count used, validation MAE, scikit-learn version, and feature schema. The previous model SHALL be archived (not deleted) when a new model is promoted.

#### Scenario: Previous model archived on promotion
- **WHEN** a new model passes evaluation and replaces the existing `/models/sphere_regressor.joblib`
- **THEN** the old file is renamed to `/models/sphere_regressor_<timestamp>.joblib.bak` before the new file is written
