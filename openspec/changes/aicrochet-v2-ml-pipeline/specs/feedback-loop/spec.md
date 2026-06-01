## ADDED Requirements

### Requirement: Crafter correction API endpoint
The backend SHALL expose `POST /feedback` accepting: `session_id`, `part_name`, `primitive_type`, `original_diameters` (array), `corrected_diameters` (array), and an optional `notes` string. The correction SHALL be stored in the `feedback_corrections` table.

#### Scenario: Correction stored successfully
- **WHEN** a crafter submits a correction with valid fields
- **THEN** HTTP 201 is returned and the record is inserted into `feedback_corrections` with `created_at` timestamp

#### Scenario: Malformed correction rejected
- **WHEN** `corrected_diameters` has a different length than `original_diameters`
- **THEN** HTTP 422 is returned with a descriptive validation error

---

### Requirement: Correction UI in the frontend
The frontend SHALL render an "Adjust Shape" toggle per part card after pattern generation. When toggled, a set of sliders SHALL appear — one per round — allowing the crafter to adjust each diameter value up or down. Submitting the adjustment SHALL call `POST /feedback`.

#### Scenario: Sliders reflect current diameters
- **WHEN** the user opens the "Adjust Shape" panel for a part
- **THEN** each slider is initialized to the corresponding diameter value from the generated pattern

#### Scenario: Correction submitted on confirm
- **WHEN** the user adjusts sliders and clicks "Submit Correction"
- **THEN** the frontend POSTs to `/feedback` with the original and corrected diameter arrays and shows a success confirmation

---

### Requirement: Retraining triggered on batch threshold
The system SHALL monitor the count of unincorporated corrections in `feedback_corrections`. When the count reaches a configurable threshold (default 100), a retraining job SHALL be triggered. After retraining, incorporated corrections SHALL be marked `incorporated=true`.

#### Scenario: Retraining triggered at threshold
- **WHEN** the 100th unincorporated correction is inserted
- **THEN** the retraining job starts within 60 seconds, logging its start to the system log

#### Scenario: Corrections incorporated after successful retraining
- **WHEN** a retraining run completes and the new model passes evaluation
- **THEN** all corrections used in that training run are marked `incorporated=true`

---

### Requirement: Corrections weighted by quality in training
Feedback corrections SHALL be included in the training dataset with a higher sample weight (default 2.0×) than scraped records, to prioritize crafter-validated signal over scraped ground truth.

#### Scenario: Correction weight applied during training
- **WHEN** the training pipeline loads the dataset
- **THEN** records with `source_type=feedback` are assigned sample_weight=2.0 in the scikit-learn `fit()` call
