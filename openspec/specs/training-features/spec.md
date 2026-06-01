# training-features Specification

## Purpose
TBD - created by archiving change improve-training-pipeline. Update Purpose after archive.
## Requirements
### Requirement: 7-dimensional feature vector for regressor training
The model training pipeline SHALL extract a 7-dimensional feature vector from each training record, replacing the previous 2-dimensional `(scale, aspect_ratio)` vector.

#### Scenario: Feature vector includes inferred scale
- **WHEN** a training record is loaded
- **THEN** feature[0] is `scale` (from `record["scale"]`, defaulting to `1.0`)

#### Scenario: Feature vector includes sequence length
- **WHEN** a training record is loaded
- **THEN** feature[1] is the number of rounds (length of `stitch_counts`)

#### Scenario: Feature vector includes absolute size
- **WHEN** a training record is loaded
- **THEN** feature[2] is `max(stitch_counts)`, representing the physical extent of the part

#### Scenario: Feature vector includes rise slope
- **WHEN** a training record is loaded
- **THEN** feature[3] is the mean positive difference between consecutive stitch counts in the first half of the sequence (0 if sequence is non-increasing throughout)

#### Scenario: Feature vector includes fall slope
- **WHEN** a training record is loaded
- **THEN** feature[4] is the mean negative difference between consecutive stitch counts in the second half of the sequence (0 if sequence is non-decreasing throughout), stored as a positive number

#### Scenario: Feature vector includes flat fraction
- **WHEN** a training record is loaded
- **THEN** feature[5] is the proportion of stitch counts within 10% of `max(stitch_counts)`

#### Scenario: Feature vector includes symmetry score
- **WHEN** a training record is loaded
- **THEN** feature[6] is `1 - abs(rise_slope - fall_slope) / (rise_slope + fall_slope + 1e-6)`, bounded to [0, 1]

#### Scenario: Graceful handling of very short sequences
- **WHEN** `stitch_counts` has fewer than 2 values
- **THEN** rise_slope, fall_slope, flat_fraction, and symmetry_score are all set to `0.0`

