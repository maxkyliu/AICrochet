## ADDED Requirements

### Requirement: Name-based primitive type assignment
The system SHALL assign a `primitive_type` to a normalized record by matching the record's `part_name` against a prioritized keyword list, case-insensitively.

#### Scenario: Known body-part name matches sphere
- **WHEN** `part_name` contains "HEAD", "SNOUT", or "MUZZLE"
- **THEN** `primitive_type` is set to `"sphere"`

#### Scenario: Known body-part name matches capsule
- **WHEN** `part_name` contains "BODY" or "TORSO"
- **THEN** `primitive_type` is set to `"capsule"`

#### Scenario: Known body-part name matches cylinder
- **WHEN** `part_name` contains "LEG", "ARM", "LIMB", "NECK", or "STALK"
- **THEN** `primitive_type` is set to `"cylinder"`

#### Scenario: Known body-part name matches cone
- **WHEN** `part_name` contains "TAIL", "BEAK", "HORN", "SPIKE"
- **THEN** `primitive_type` is set to `"cone"`

#### Scenario: Known body-part name matches flat_disc
- **WHEN** `part_name` contains "EAR", "WING", or "FIN"
- **THEN** `primitive_type` is set to `"flat_disc"`

#### Scenario: Known body-part name matches frustum
- **WHEN** `part_name` contains "FOOT", "BOOT", or "BASE"
- **THEN** `primitive_type` is set to `"frustum"`

#### Scenario: Known body-part name matches torus
- **WHEN** `part_name` contains "TORUS", "RING", or "COLLAR"
- **THEN** `primitive_type` is set to `"torus"`

#### Scenario: Unrecognised part name defers to shape heuristic
- **WHEN** no keyword matches `part_name`
- **THEN** `primitive_type` assignment is delegated to the shape heuristic labeler

---

### Requirement: Shape-heuristic primitive type assignment
The system SHALL assign a `primitive_type` to a record by analysing the shape of its stitch count sequence when name matching yields no result.

#### Scenario: Short sequence skips heuristic
- **WHEN** the stitch count sequence has fewer than 4 values
- **THEN** `primitive_type` remains `None` (heuristic is not applied)

#### Scenario: Non-zero floor indicates torus
- **WHEN** `min(stitch_counts) / max(stitch_counts) > 0.4`
- **THEN** `primitive_type` is set to `"torus"`

#### Scenario: Monotonically rising sequence indicates cone
- **WHEN** the stitch sequence is non-decreasing throughout
- **THEN** `primitive_type` is set to `"cone"`

#### Scenario: Symmetric rise-fall with small flat section indicates sphere
- **WHEN** rise and fall are within 20% of each other AND flat fraction < 0.3
- **THEN** `primitive_type` is set to `"sphere"`

#### Scenario: Symmetric rise-fall with moderate flat section indicates capsule
- **WHEN** rise and fall are within 20% of each other AND flat fraction is 0.3–0.6
- **THEN** `primitive_type` is set to `"capsule"`

#### Scenario: Large flat section indicates cylinder
- **WHEN** flat fraction > 0.6
- **THEN** `primitive_type` is set to `"cylinder"`

#### Scenario: Asymmetric tail indicates teardrop
- **WHEN** fall slope is more than 40% steeper than rise slope
- **THEN** `primitive_type` is set to `"teardrop"`

#### Scenario: Default fallback is frustum
- **WHEN** no other heuristic condition matches
- **THEN** `primitive_type` is set to `"frustum"`
