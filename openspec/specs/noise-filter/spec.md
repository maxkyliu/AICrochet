# noise-filter Specification

## Purpose
TBD - created by archiving change improve-training-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Non-body-part record rejection
The normalizer SHALL discard any normalized record whose `part_name` matches a blocklist of known non-body-part section headers before writing to the database.

#### Scenario: Abbreviation section is discarded
- **WHEN** `part_name` contains "ABBREVIATION" or "ABBREV"
- **THEN** the record is not inserted into `training_records`

#### Scenario: Notes and metadata sections are discarded
- **WHEN** `part_name` contains "NOTE", "MATERIAL", "SUPPLY", "GAUGE", "TERMINOLOGY", "SKILL", "INTRODUCTION", "TIP", or "INSTRUCTION"
- **THEN** the record is not inserted into `training_records`

#### Scenario: Stitch reference sections are discarded
- **WHEN** `part_name` contains "STITCH" (e.g., "Stitches Used", "Special Stitches")
- **THEN** the record is not inserted into `training_records`

#### Scenario: Valid body-part records pass through
- **WHEN** `part_name` does not match any blocklist entry
- **THEN** the record proceeds normally to labeling and DB insertion

#### Scenario: Matching is case-insensitive
- **WHEN** `part_name` is "abbreviations" or "Abbreviations" or "ABBREVIATIONS"
- **THEN** the record is discarded regardless of case

