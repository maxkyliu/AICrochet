# scale-inference Specification

## Purpose
TBD - created by archiving change improve-training-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Scale value inferred from stitch count magnitude
The normalizer SHALL compute a `scale` value for each record by dividing the maximum stitch count in the sequence by a reference value of 24 (representing the maximum stitch count of a "size 1.0" part at worsted gauge).

#### Scenario: Scale computed from max stitch count
- **WHEN** `stitch_counts` is non-empty
- **THEN** `scale = max(stitch_counts) / 24.0`, rounded to 2 decimal places

#### Scenario: Scale floor prevents zero or negative values
- **WHEN** `max(stitch_counts)` is less than 6
- **THEN** `scale` is set to `0.25` (minimum meaningful size)

#### Scenario: Empty stitch counts leave scale as None
- **WHEN** `stitch_counts` is empty
- **THEN** `scale` remains `None`

